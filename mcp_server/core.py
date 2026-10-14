"""Auditable local LCI helpers. Not a SimaPro engine or native CSV generator."""
from __future__ import annotations
import csv
import hashlib
import json
import math
import os
from collections import defaultdict
from pathlib import Path

LCI_COLUMNS = (
    'process_id','process_name','flow_id','flow_name','flow_role','amount','unit',
    'provider_type','provider_ref','geography','source','notes'
)
ROLES = {'reference_output','technosphere_input','elementary_input','elementary_output','waste_output'}
RESULT_COLUMNS = ('scenario','indicator','value','unit')


def workspace() -> Path:
    return Path(os.environ.get('SIMAPRO_WORKSPACE') or os.getcwd()).expanduser().resolve()


def safe_path(filename: str, create_parent: bool = False) -> Path:
    if not filename or not filename.strip():
        raise ValueError('A nonempty workspace-relative file path is required')
    root = workspace()
    if Path(filename).is_absolute() or Path(filename).drive:
        raise ValueError('Use a workspace-relative path')
    path = (root / filename).resolve()
    if path != root and root not in path.parents:
        raise ValueError('Path must remain inside SIMAPRO_WORKSPACE')
    if create_parent:
        path.parent.mkdir(parents=True, exist_ok=True)
    elif not path.is_file():
        raise FileNotFoundError(str(path))
    return path


def _load_csv(file: Path, mandatory: tuple[str, ...]):
    with file.open('r', encoding='utf-8-sig', newline='') as fp:
        reader = csv.DictReader(fp)
        fields = list(reader.fieldnames or [])
        if len(fields) != len(set(fields)) or any(not f.strip() for f in fields):
            raise ValueError('CSV headers must be nonempty and unique')
        missing = sorted(set(mandatory) - set(fields))
        if missing:
            raise ValueError('Missing CSV columns: ' + ', '.join(missing))
        rows = []
        for i, row in enumerate(reader, 2):
            if None in row or any(v is None for v in row.values()):
                raise ValueError(f'CSV row {i}: number of cells does not match header')
            rows.append({k: v.strip() for k, v in row.items()})
        return fields, rows


def _number(value: str) -> float:
    try:
        n = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f'Not a number: {value!r}') from exc
    if not math.isfinite(n):
        raise ValueError('A finite number is required')
    return n


def validate_inventory(filename: str):
    path = safe_path(filename)
    _, rows = _load_csv(path, LCI_COLUMNS)
    errors, warnings = [], []
    if not rows:
        errors.append('Inventory is empty')
    product = defaultdict(int)
    process_names = {}
    graph = defaultdict(set)
    providers = set()
    unique_flows = set()
    for i, row in enumerate(rows, 2):
        prefix = f'row {i}'
        process_id, role = row['process_id'].strip(), row['flow_role'].strip()
        flow_key = (process_id, row['flow_id'].strip())
        if flow_key in unique_flows:
            errors.append(f'{prefix}: duplicate (process_id, flow_id) {flow_key}')
        unique_flows.add(flow_key)
        if not all(row[k] for k in ('process_id','process_name','flow_id','flow_name')):
            errors.append(f'{prefix}: process_id, process_name, flow_id and flow_name are required')
        if role not in ROLES:
            errors.append(f'{prefix}: invalid flow_role {role!r}')
        try:
            n = _number(row['amount'])
            if n <= 0:
                errors.append(f'{prefix}: amount must be positive; zero/missing must be documented separately')
        except ValueError as exc:
            errors.append(f'{prefix}: {exc}')
        if not row['unit'].strip():
            errors.append(f'{prefix}: unit is empty')
        if not row['source'].strip():
            warnings.append(f'{prefix}: data source missing')
        if 'DEMO' in row['source'].upper():
            warnings.append(f'{prefix}: DEMO data; never report as measurements')
        if process_id in process_names and process_names[process_id] != row['process_name'].strip():
            errors.append(f'{prefix}: inconsistent process_name for {process_id}')
        process_names[process_id] = row['process_name'].strip()
        if role == 'reference_output':
            product[process_id] += 1
        if role == 'technosphere_input':
            provider_type = row['provider_type'].strip().lower()
            provider_ref = row['provider_ref'].strip()
            if provider_type not in ('foreground','background'):
                errors.append(f'{prefix}: input provider_type must be foreground or background')
            if not provider_ref:
                errors.append(f'{prefix}: input has no provider_ref; link unresolved')
            elif provider_type == 'foreground':
                graph[process_id].add(provider_ref)
                providers.add(provider_ref)
            elif provider_type == 'background':
                warnings.append(f'{prefix}: external dataset {provider_ref!r} is not verified in SimaPro')
        elif row['provider_type'].strip() or row['provider_ref'].strip():
            warnings.append(f'{prefix}: provider fields are generally used for technosphere inputs')
    for pid in process_names:
        if product[pid] == 0:
            errors.append(f'process {pid}: no reference_output flow')
        if product[pid] > 1:
            warnings.append(f'process {pid}: multiple reference outputs; verify allocation/multifunctionality')
    for name in providers:
        if name not in process_names:
            errors.append(f'foreground provider {name!r} does not exist in this inventory')
    visited, active = set(), set()
    def dfs(node):
        if node in active:
            errors.append(f'Cycle detected in foreground providers at {node}')
            return
        if node in visited:
            return
        active.add(node)
        for dep in graph[node]:
            if dep in process_names:
                dfs(dep)
        active.remove(node)
        visited.add(node)
    for pid in process_names:
        dfs(pid)
    return {'ok': not errors, 'file': str(path), 'rows':len(rows),
            'processes':len(process_names), 'errors':errors, 'warnings':warnings,
            'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
            'remark':'Validated canonical inventory only; not imported or calculated in SimaPro.'}


def inventory_summary(filename: str):
    report = validate_inventory(filename)
    if not report['ok']:
        return report
    _, rows = _load_csv(safe_path(filename), LCI_COLUMNS)
    groups = defaultdict(float)
    for row in rows:
        key = (row['process_id'],row['flow_role'],row['flow_name'],row['unit'])
        groups[key] += _number(row['amount'])
    return {'ok':True, 'lines':[dict(process_id=k[0],flow_role=k[1],flow_name=k[2],unit=k[3],amount=round(v,9))
                               for k,v in sorted(groups.items())],
            'warnings':report['warnings'], 'remark':'No impact assessment calculated.'}


def create_scenario_inventories(filename: str, process_id: str, flow_id: str,
                                multipliers: list[float], output_dir: str = 'outputs/scenarios'):
    check = validate_inventory(filename)
    if not check['ok']:
        return check
    original = safe_path(filename)
    fields, rows = _load_csv(original, LCI_COLUMNS)
    hits = [r for r in rows if r['process_id']==process_id and r['flow_id']==flow_id]
    if len(hits) != 1:
        raise ValueError('Target process_id+flow_id must match exactly one row')
    if not 1 <= len(multipliers) <= 20:
        raise ValueError('Use 1 to 20 multipliers')
    factors = [_number(str(v)) for v in multipliers]
    if any(not 0 < f <= 10 for f in factors):
        raise ValueError('Multiplier must be >0 and <=10; zero is not represented in this inventory schema')
    for f in factors:
        _number(str(_number(hits[0]['amount']) * f))
    output_base = safe_path(output_dir, create_parent=True)
    if output_base == original:
        raise ValueError('Output directory cannot equal inventory file')
    targets = [output_base / f'scenario_{idx:02d}_x{f:g}.csv' for idx,f in enumerate(factors,1)]
    for out in targets:
        if out.exists():
            raise FileExistsError(f'Will not overwrite existing scenario: {out}')
    output_base.mkdir(parents=True, exist_ok=True)
    written = []
    for f, out in zip(factors, targets):
        with out.open('x', encoding='utf-8-sig', newline='') as fp:
            writer = csv.DictWriter(fp, fieldnames=fields)
            writer.writeheader()
            for row in rows:
                updated = dict(row)
                if row['process_id']==process_id and row['flow_id']==flow_id:
                    updated['amount'] = f'{_number(row["amount"]) * f:.12g}'
                    updated['notes'] = (updated['notes']+' | '+f'LOCAL SCENARIO multiplier {f:g}').strip(' |')
                writer.writerow(updated)
        written.append({'multiplier':f, 'file':str(out), 'sha256':hashlib.sha256(out.read_bytes()).hexdigest()})
    return {'ok':True,'created':written,
            'remark':'Local scenario inventories only. None have been imported to or calculated with SimaPro.'}


def compare_results(filename: str, baseline: str):
    path = safe_path(filename)
    _, rows = _load_csv(path, RESULT_COLUMNS)
    groups = {}
    warnings = []
    for i,r in enumerate(rows, 2):
        scenario,indicator,unit = (r[c].strip() for c in ('scenario','indicator','unit'))
        if not all((scenario,indicator,unit)):
            raise ValueError(f'row {i}: missing scenario, indicator or unit')
        n = _number(r['value'])
        key = (scenario, indicator)
        if key in groups:
            raise ValueError(f'row {i}: duplicate scenario + indicator (could hide multiple units) {key}')
        groups[key] = {'value':n,'unit':unit}
    baseline_items = {indicator:v for (sc,indicator),v in groups.items() if sc==baseline}
    if not baseline_items:
        raise ValueError('Baseline scenario not found')
    compared = []
    scenarios = sorted({s for s,_ in groups if s!=baseline})
    for scenario in scenarios:
        for indicator, base in baseline_items.items():
            item = groups.get((scenario,indicator))
            if not item:
                warnings.append(f'{scenario}: no result for indicator {indicator}')
                continue
            if item['unit'] != base['unit']:
                raise ValueError(f'{scenario}/{indicator}: unit mismatch {item["unit"]} vs {base["unit"]}')
            delta = item['value'] - base['value']
            compared.append({'scenario':scenario,'indicator':indicator,'unit':item['unit'],
                             'baseline':base['value'],'alternative':item['value'],
                             'delta':round(delta,10),
                             'improvement_pct_if_lower_is_better':round(100*(base['value']-item['value'])/base['value'],5)
                                 if base['value']>0 else None})
    return {'ok':True, 'file':str(path), 'baseline':baseline, 'comparisons':compared,
            'warnings':warnings,
            'remark':'Only mathematical comparison of externally supplied figures; origin/method of values is not verified.'}
