"""SimaPro Desktop 9.0 adapters. Local preparation only, unless user drives a real GUI session.

Do not mistake a candidate native CSV file for successful import into SimaPro.
"""
from __future__ import annotations
import csv
import hashlib
import io
import json
import math
import os
import re
import tempfile
from collections import defaultdict
from datetime import datetime, timezone
from difflib import SequenceMatcher
from pathlib import Path
from . import core

CATALOG_FIELDS = ('simapro_process_name','reference_unit','geography','library','system_model','version','process_category','source')
MAP_FIELDS = ('process_id','flow_id','flow_name','requested_provider','amount_unit','requested_geography',
              'matched_dataset','matched_unit','matched_geography','library','system_model','version',
              'score','warnings','approved')
NATIVE_SECTIONS = frozenset(('Category type','Process identifier','Type','Process name','Status','Time period',
 'Time Period','Geography','Technology','Representativeness','Multiple output allocation','Substitution allocation',
 'Cut off rules','Capital goods','Boundary with nature','Infrastructure','Date','Record','Generator',
 'Collection method','Data treatment','Verification','Comment','Allocation rules','Literature references',
 'System description','Products','Materials/fuels','Electricity/heat','Avoided products','Resources',
 'Emissions to air','Emissions to water','Emissions to soil','Final waste flows',
 'Non material emission','Non material emissions','Social issues','Economic issues','Waste to treatment',
 'Remaining waste','Separated waste','Input parameters','Calculated parameters'))
TECH_TYPES = {'Materials/fuels','Electricity/heat'}


def _safe(filename: str, parent: bool=False) -> Path:
    return core.safe_path(filename, create_parent=parent)


def _read_csv(filename: str, required):
    p=_safe(filename)
    return core._load_csv(p, tuple(required))


def _write_csv(path, fieldnames, rows):
    with path.open('x', encoding='utf-8-sig', newline='') as file:
        w=csv.DictWriter(file, fieldnames=fieldnames, extrasaction='ignore')
        w.writeheader(); w.writerows(rows)


def list_dataset_candidates(inventory_path: str, catalog_path: str, output_path: str='outputs/dataset_mapping_review.csv', limit: int=3):
    """Deterministic local suggestions; not proof the library is installed or an LCA equivalence assessment."""
    check=core.validate_inventory(inventory_path)
    if not check['ok']:
        return check
    _,lci=_read_csv(inventory_path,core.LCI_COLUMNS)
    _,catalog=_read_csv(catalog_path,CATALOG_FIELDS)
    if not 1 <= limit <= 5: raise ValueError('limit must be from 1 to 5')
    for i,c in enumerate(catalog,2):
        if not c['simapro_process_name'].strip() or not c['reference_unit'].strip():
            raise ValueError(f'Catalog line {i}: missing dataset name or reference unit')
        if not c['source'].strip():
            raise ValueError(f'Catalog line {i}: explicit dataset provenance is required')
    review=[]; unmatched=[]
    for flow in lci:
        if flow['flow_role']!='technosphere_input' or flow['provider_type'].strip().lower()!='background': continue
        query=(flow['provider_ref'] or flow['flow_name']).strip()
        candidates=[]
        for c in catalog:
            unit_ok=c['reference_unit'].strip()==flow['unit'].strip()
            if not unit_ok: continue
            name=c['simapro_process_name'].strip()
            lexical=SequenceMatcher(None, query.lower(),name.lower()).ratio()
            toks=lambda s:set(re.findall(r'[a-z0-9]+',s.lower()))
            a,b=toks(query),toks(name)
            overlap=len(a&b)/len(a|b) if a|b else 0
            geo=c['geography'].strip()
            geo_match=(geo.lower()==flow['geography'].strip().lower())
            score=round(0.6*lexical+0.3*overlap+(0.1 if geo_match else 0),4)
            candidates.append((score,name,c,geo_match))
        candidates.sort(key=lambda x:(-x[0],x[1]))
        if not candidates: unmatched.append(f"{flow['process_id']}:{flow['flow_id']}")
        for score,name,c,gm in candidates[:limit]:
            warnings=[]
            if not gm: warnings.append('GEOGRAPHY_MISMATCH_REVIEW')
            if score<0.6: warnings.append('LOW_TEXT_SIMILARITY')
            warnings.append('NOT_VERIFIED_IN_RUNNING_SIMAPRO')
            review.append(dict(process_id=flow['process_id'],flow_id=flow['flow_id'],flow_name=flow['flow_name'],
                requested_provider=query,amount_unit=flow['unit'],requested_geography=flow['geography'],
                matched_dataset=name,matched_unit=c['reference_unit'],matched_geography=c['geography'],
                library=c['library'],system_model=c['system_model'],version=c['version'],score=score,
                warnings=' | '.join(warnings),approved=''))
    path=_safe(output_path,True)
    if path.exists(): raise FileExistsError(f'Will not overwrite mapping review {path}')
    _write_csv(path,MAP_FIELDS,review)
    return {'ok':True,'candidates':len(review),'unmatched':unmatched,'review_file':str(path),
            'remark':'Suggestions only. Manually set approved=yes on ONE correct dataset per background flow.'}


def catalog_from_native_export(native_csv: str, output_csv: str, library: str, version: str,
                              system_model: str, source: str, native_encoding: str='utf-8-sig'):
    """Index reference products from an authorized, local SimaPro CSV export; no online database access."""
    if not all(str(v).strip() for v in (library,version,system_model,source)):
        raise ValueError('Library, version, system model and traceable source are required')
    native=parse_native(native_csv,native_encoding)
    rows=[]
    for block in native['sections']:
        products=block.get('Products',[])
        if not products:continue
        category=block.get('Category type',['material'])[0]
        geography=block.get('Geography',['Unspecified'])[0]
        for line in products:
            parts=next(csv.reader([line],delimiter=';',quotechar='"'))
            if len(parts)<2 or not parts[0].strip() or not parts[1].strip():continue
            rows.append(dict(simapro_process_name=parts[0].strip(),reference_unit=parts[1].strip(),
                geography=geography,library=library,system_model=system_model,version=version,
                process_category=category,source=source))
    if not rows:raise ValueError('No Product reference entries found in native CSV export')
    target=_safe(output_csv,True)
    if target.exists():raise FileExistsError(f'File exists: {target}')
    _write_csv(target,CATALOG_FIELDS,rows)
    return {'ok':True,'indexed_reference_products':len(rows),'catalog':str(target),
        'source_sha256':native['sha256'],
        'note':'Catalog is derived from the authorized subset export. Keep locally; do not publish database content.'}


def mapping_qa(inventory_path: str, mapping_path: str):
    _, flows=_read_csv(inventory_path,core.LCI_COLUMNS)
    _, maps=_read_csv(mapping_path,MAP_FIELDS)
    issues=[]; selected={}
    needed={(r['process_id'],r['flow_id']):r for r in flows if r['flow_role']=='technosphere_input' and r['provider_type'].strip().lower()=='background'}
    for m in maps:
        if m['approved'].strip().lower() not in ('yes','y','true','1'): continue
        k=(m['process_id'],m['flow_id'])
        if k in selected: issues.append(f'duplicate approved mapping for {k}')
        if k not in needed: issues.append(f'approved mapping not in inventory: {k}')
        elif m['matched_unit'].strip()!=needed[k]['unit'].strip(): issues.append(f'unit mismatch for {k}')
        if k in needed:
            flow=needed[k]
            for field,expected in (('flow_name',flow['flow_name']),('requested_provider',flow['provider_ref'] or flow['flow_name']),
                                   ('amount_unit',flow['unit']),('requested_geography',flow['geography'])):
                if m[field].strip()!=expected.strip():
                    issues.append(f'stale mapping {field} for {k}; regenerate and review')
        if not m['matched_dataset'].strip(): issues.append(f'missing dataset name for {k}')
        if not m['library'].strip() or not m['version'].strip() or not m['system_model'].strip():
            issues.append(f'database/library/version/system_model provenance missing for {k}')
        selected[k]=m
    missing=sorted(set(needed)-set(selected))
    issues += [f'background flow needs approved mapping: {k}' for k in missing]
    return {'ok':not issues,'issues':issues,'required':len(needed),'approved':len(selected),'selected':selected}


def parse_native(path: str, encoding: str='utf-8-sig'):
    """Lightweight, conservative process block reader for template calibration; no full format parser."""
    p=_safe(path)
    data=p.read_bytes()
    if encoding not in ('utf-8-sig','utf-8','cp1252','gbk'):
        raise ValueError('Unsupported native encoding; use the actual export encoding')
    content=data.decode(encoding).replace('\r\n','\n').replace('\r','\n')
    prefix=content[:content.index('\nProcess\n')+1] if '\nProcess\n' in content else ('\n' if content.startswith('Process\n') else '')
    if not prefix: raise ValueError('No Process block at start of line; export one normal process as SimaPro CSV')
    if '{CSV separator: Semicolon}' not in prefix:
        raise ValueError('Only semicolon-delimited authentic SimaPro CSV templates are supported')
    if '{Decimal separator: .}' not in prefix:
        raise ValueError('Only dot-decimal authentic SimaPro CSV templates are supported')
    if not re.search(r'\{SimaPro 9\.0(?:[.}]|\s)',prefix):
        raise ValueError('A SimaPro 9.0 export header is required; another version needs separate calibration')
    blocks=re.findall(r'(?ms)^Process[ \t]*\n(.*?)^End[ \t]*$',content)
    if not blocks: raise ValueError('Cannot extract native Process/End blocks')
    remainder=re.sub(r'(?ms)^Process[ \t]*\n.*?^End[ \t]*$', '', content[len(prefix):])
    if remainder.strip():
        raise ValueError('Only complete Process/End blocks are supported; additional objects or truncated blocks found')
    parsed=[]
    for block in blocks:
        sections={}
        # shortcut: blank lines delimit sections; multiline/extended exports need a calibrated parser.
        for paragraph in re.split(r'\n[ \t]*\n',block.strip('\n')):
            lines=paragraph.splitlines()
            key=lines[0].strip()
            if key not in NATIVE_SECTIONS:
                raise ValueError(f'Unsupported native section or multiline field: {key!r}')
            if key in sections:
                raise ValueError(f'Duplicate native section: {key}')
            sections[key]=lines[1:]
        parsed.append(sections)
    return {'encoding':encoding,'prefix':prefix,'sections':parsed,'path':str(p),
            'sha256':hashlib.sha256(data).hexdigest(),'processes':len(parsed)}


def inspect_native_template(path: str, native_encoding: str='utf-8-sig'):
    n=parse_native(path,native_encoding)
    s=n['sections'][0]
    missing=sorted({'Products','Category type','Materials/fuels'}-set(s))
    return {'ok':not missing,'source':n['path'],'sha256':n['sha256'],'encoding':n['encoding'],
      'total_process_blocks':n['processes'],'first_process_sections':list(s),
      'missing_sections':missing,'note':'Inspect-only; a file generated from this template still needs SimaPro 9.0 import testing.'}


def _native_csv_line(items):
    """SimaPro semi-colon line with conservative RFC4180 quote escaping."""
    out=io.StringIO()
    w=csv.writer(out,delimiter=';',lineterminator='',quoting=csv.QUOTE_ALL)
    w.writerow([str(v) for v in items]);return out.getvalue()+';'


def _safe_cell(s):
    v=str(s).strip()
    if any(c in v for c in ('\n','\r','\x00')): raise ValueError('Native CSV strings cannot contain newline/NUL here')
    return v


def _numeric(s):
    val=core._number(str(s))
    if val<=0: raise ValueError('Positive exchange amounts only in native candidate')
    return format(val,'.12g')


def build_native_import_candidate(inventory_path: str, mapping_path: str, template_path: str,
                                  output_path: str='outputs/simapro9_import_CANDIDATE.csv',
                                  process_suffix: str='', native_encoding: str='utf-8-sig'):
    """Generate semicolon SimaPro CSV from an authentic, local 9.0 process export template.

    Requires manual import and verification. Rejects elementary/waste flows rather than inventing compartments.
    """
    check=core.validate_inventory(inventory_path)
    if not check['ok']:return check
    q=mapping_qa(inventory_path,mapping_path)
    if not q['ok']:return {'ok':False,'errors':q['issues'],'where':'mapping approval'}
    template=parse_native(template_path,native_encoding)
    selected=template['sections'][0]
    for req in ('Products','Category type','Materials/fuels'):
        if req not in selected: raise ValueError(f'Authentic template missing section {req}')
    if template['processes']!=1:
        raise ValueError('Template must contain exactly one freshly exported simple foreground process')
    if selected.get('Category type') not in (['material'],['energy']):
        raise ValueError('Only material or energy process template supported, not waste-treatment templates')
    if selected.get('Type')!=['Unit process']:
        raise ValueError('Template must be a Unit process; do not inherit a system process')
    # Prevent silently transporting environmental flows / extra products / specialized metadata
    # from the original template into an unrelated newly generated model.
    dangerous=('Avoided products','Waste to treatment','Resources','Emissions to air','Emissions to water',
               'Emissions to soil','Final waste flows','Waste treatment','Remaining waste','Separated waste',
               'Input parameters','Calculated parameters','Social issues','Economic issues',
               'Non material emission','Non material emissions')
    carry=[k for k in dangerous if selected.get(k)]
    if carry:raise ValueError('Template is not a blank simple process: nonempty sections '+', '.join(carry))
    if len(selected.get('Products',[]))!=1:
        raise ValueError('Template must contain one reference product; avoid multifunctional templates')
    _,rows=_read_csv(inventory_path,core.LCI_COLUMNS)
    groups=defaultdict(list)
    for r in rows:
        if r['flow_role'] not in ('reference_output','technosphere_input'):
            raise ValueError(f"Unsupported role {r['flow_role']} for native candidate: {r['flow_id']}. Handle emissions/waste using separately verified SimaPro 9.0 template before import.")
        groups[r['process_id']].append(r)
    for pid,group in groups.items():
        num=sum(r['flow_role']=='reference_output' for r in group)
        if num!=1:raise ValueError(f'Process {pid}: exactly one reference product required, got {num}')
    references={pid:next(r for r in group if r['flow_role']=='reference_output') for pid,group in groups.items()}
    for group in groups.values():
        for r in group:
            if r['flow_role']=='technosphere_input' and r['provider_type'].strip().lower()=='foreground':
                provider=references.get(r['provider_ref'].strip())
                if provider and provider['unit']!=r['unit']:
                    raise ValueError(f"Foreground unit mismatch {r['flow_id']} -> {r['provider_ref']}")
    suffix=_safe_cell(process_suffix)
    if suffix and not re.fullmatch(r'[a-zA-Z0-9_-]{1,24}',suffix):
        raise ValueError('process_suffix should be 1-24 ASCII letters, digits, hyphens, underscores')
    product_names={}
    for pid,group in groups.items():
        output=next(r for r in group if r['flow_role']=='reference_output')
        product_names[pid]=_safe_cell(output['flow_name']+(' ['+suffix+']' if suffix else ''))
    if len(set(product_names.values()))!=len(product_names):
        raise ValueError('Reference product names must be unique to prevent ambiguous foreground links')
    out_lines=[template['prefix'].rstrip('\n')]
    for pid,group in sorted(groups.items()):
        s={k:list(v) for k,v in selected.items()}
        for key in ('Status','Time period','Time Period','Technology','Representativeness','Multiple output allocation',
                    'Substitution allocation','Cut off rules','Capital goods','Boundary with nature','Infrastructure',
                    'Date','Record','Generator','Collection method','Data treatment','Verification',
                    'Allocation rules','Literature references','System description'):
            if key in s:s[key]=[]
        out=next(r for r in group if r['flow_role']=='reference_output')
        product=product_names[pid]
        s['Category type']=['material']
        s['Products']=[_native_csv_line([product,_safe_cell(out['unit']),_numeric(out['amount']),'100','not defined','AgentForeground',''])]
        # Do not reuse template identifiers; local candidate name is stable but an import must still test it.
        if 'Process identifier' in s:
            s['Process identifier']=['Agent'+hashlib.sha1((pid+suffix).encode()).hexdigest()[:18]]
        if 'Process name' in s: s['Process name']=[_safe_cell(group[0]['process_name']+(' '+suffix if suffix else ''))]
        if 'Geography' in s: s['Geography']=[_safe_cell(out['geography'] or 'Unspecified')]
        if 'Comment' in s: s['Comment']=['Prepared by Agent; source inventory: '+_safe_cell(Path(inventory_path).name)+'; import validation required']
        for sec in ('Materials/fuels','Electricity/heat','Avoided products','Waste to treatment','Resources',
                    'Emissions to air','Emissions to water','Emissions to soil','Final waste flows'):
            if sec in s: s[sec]=[]
        all_inputs=[]
        for r in group:
            if r['flow_role']!='technosphere_input': continue
            typ=r['provider_type'].strip().lower()
            if typ=='foreground':
                ref=r['provider_ref'].strip()
                if ref not in product_names: raise ValueError(f'Unknown foreground provider: {ref}')
                name=product_names[ref]
            elif typ=='background':
                name=q['selected'][(pid,r['flow_id'])]['matched_dataset'].strip()
            else: raise ValueError(f'Unsupported provider_type for {r["flow_id"]}')
            all_inputs.append((name,r['unit'],r['amount']))
        if 'Materials/fuels' not in s:
            raise ValueError('Materials/fuels section required in source template')
        s['Materials/fuels']=[_native_csv_line([_safe_cell(name),_safe_cell(unit),_numeric(amount),'Undefined','0','0','0',''])
                               for name,unit,amount in all_inputs]
        out_lines.extend(['Process',''])
        for key,section in s.items():
            out_lines.append(key);out_lines.extend(section);out_lines.append('')
        out_lines.extend(['End',''])
    candidate='\n'.join(out_lines).rstrip()+'\n'
    # Exact encoding must be verified with original 9.0 import; do not silently replace unsupported chars.
    candidate.encode(template['encoding'])
    path=_safe(output_path,True)
    manifest=path.with_suffix('.manifest.json')
    if path.exists() or manifest.exists(): raise FileExistsError(f'Output or manifest already exists: {path}')
    with path.open('xb') as fp:
        fp.write(candidate.replace('\n','\r\n').encode(template['encoding']))
    provenance={'candidate_file':str(path),'created_utc':datetime.now(timezone.utc).isoformat(),
        'status':'GENERATED_NOT_IMPORTED_NOT_CALCULATED','software_target':'SimaPro 9.0 desktop',
        'inventory_sha256':core.validate_inventory(inventory_path)['sha256'],
        'mapping_sha256':hashlib.sha256(_safe(mapping_path).read_bytes()).hexdigest(),
        'template_sha256':template['sha256'],'process_suffix':suffix,
        'candidate_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
        'process_count':len(groups),'warnings':['Only simple material processes with technosphere inputs',
            'Review imported outputs, links, units and process identifier; do not replace existing processes',
            'This is a candidate derived from a user-authenticated CSV template, not an official generator']}
    with manifest.open('x',encoding='utf-8') as fp:
        fp.write(json.dumps(provenance,ensure_ascii=False,indent=2))
    return {'ok':True,'file':str(path),'manifest':str(manifest), 'process_count':len(groups),
            'status':provenance['status'],'sha256':provenance['candidate_sha256'],
            'next':'Import manually into a NEW test project with linking mode reviewed; verify each process, then calculate manually.'}


def prepare_batch_scenarios(inventory_path: str, mapping_path: str, template_path: str,
                            process_id: str, flow_id: str, multipliers: list[float],
                            output_dir: str='outputs/native_scenario_batch', native_encoding: str='utf-8-sig'):
    """Build unique, auditable native *candidates*; does not import or calculate anything."""
    folder=_safe(output_dir,True)
    if folder.exists():raise FileExistsError('Batch destination exists; choose a new directory')
    if not 1<=len(multipliers)<=20:raise ValueError('1..20 multipliers required')
    if len(set(multipliers))!=len(multipliers):raise ValueError('Scenario multipliers must be unique')
    # Require prerequisite mapping and template to be valid before creating any files.
    if not mapping_qa(inventory_path,mapping_path)['ok']:raise ValueError('Unapproved background mapping')
    info=inspect_native_template(template_path,native_encoding)
    if not info['ok']:raise ValueError('Native template missing required sections')
    made=[]
    # Publish only a complete batch; staging contains only files created by this invocation.
    with tempfile.TemporaryDirectory(prefix='simapro-batch-',dir=folder.parent) as temporary:
        staging=Path(temporary)
        staged_rel=staging.relative_to(core.workspace())
        altered=core.create_scenario_inventories(inventory_path,process_id,flow_id,multipliers,str(staged_rel/'inventories'))
        if not altered['ok']:return altered
        for index,item in enumerate(altered['created'],1):
            code=f'S{index:02d}'
            rel=str(staged_rel/f'{code}_CANDIDATE.csv')
            lci_rel=str(Path(item['file']).relative_to(core.workspace()))
            build=build_native_import_candidate(lci_rel,mapping_path,template_path,rel,process_suffix=code,native_encoding=native_encoding)
            if not build['ok']:return build
            final_candidate=folder/Path(build['file']).name
            manifest=Path(build['manifest'])
            data=json.loads(manifest.read_text(encoding='utf-8'))
            data['candidate_file']=str(final_candidate)
            manifest.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
            made.append({'suffix':code,'multiplier':item['multiplier'],'inventory':str(folder/'inventories'/Path(item['file']).name),
                         'import_candidate':str(final_candidate),'manifest':str(folder/manifest.name)})
        staging.rename(folder)
    return {'ok':True,'scenarios':made,'status':'FILES_GENERATED_NOT_IMPORTED_NOT_CALCULATED'}


RESULT_IMPORT_FIELDS=('scenario','indicator','value','unit','method','database','system_model','functional_unit','source_file','result_stage')
RESULT_STAGES={'characterization','damage_assessment','normalization','weighting','single_score'}
PROVENANCE_FIELDS=('unit','method','database','system_model','functional_unit','result_stage')


def _validate_result_rows(rows):
    if not rows:raise ValueError('No result rows')
    seen=set()
    for i,r in enumerate(rows,2):
        if not all(r[k].strip() for k in RESULT_IMPORT_FIELDS if k!='value'):
            raise ValueError(f'row {i}: nonempty result provenance required')
        if r['result_stage'] not in RESULT_STAGES:
            raise ValueError(f'row {i}: invalid result_stage')
        core._number(r['value'])
        key=(r['scenario'],r['indicator'])
        if key in seen:raise ValueError(f'Duplicate scenario and indicator: {key}')
        seen.add(key)

def normalize_lcia_export(file_path: str, output_path: str, scenario: str, method: str,
                          database: str, system_model: str, functional_unit: str,
                          indicator_column: str, value_column: str, unit_column: str,
                          delimiter: str=',', encoding: str='utf-8-sig', result_stage: str=''):
    """User-calibrated tabular SimaPro export. Never silently guesses table layout or runs LCIA."""
    if delimiter not in (',',';','\t'): raise ValueError('delimiter must be comma, semicolon or tab')
    if len({indicator_column,value_column,unit_column})!=3:
        raise ValueError('Indicator, value and unit columns must be distinct')
    if encoding not in ('utf-8','utf-8-sig','cp1252','gbk'):raise ValueError('Unsupported encoding')
    required=[scenario,method,database,system_model,functional_unit,result_stage]
    if not all(str(z).strip() for z in required):raise ValueError('Missing LCIA provenance: scenario/method/database/system model/FU')
    src=_safe(file_path)
    with src.open('r',encoding=encoding,newline='') as fp:
        reader=csv.DictReader(fp,delimiter=delimiter)
        if not reader.fieldnames or len(set(reader.fieldnames))!=len(reader.fieldnames) or not set((indicator_column,value_column,unit_column)) <= set(reader.fieldnames):
            raise ValueError(f'Required result columns absent. Found: {reader.fieldnames}')
        rows=[]
        for i,r in enumerate(reader,2):
            if None in r or any(v is None for v in r.values()):
                raise ValueError(f'row {i}: result cells do not match header')
            if not r[indicator_column].strip():raise ValueError(f'row {i}: indicator is empty')
            value=core._number(r[value_column]);unit=(r[unit_column] or '').strip()
            if not unit:raise ValueError(f'Empty unit at row {i}')
            rows.append(dict(scenario=scenario,indicator=r[indicator_column].strip(),value=value,unit=unit,
                 method=method,database=database,system_model=system_model,functional_unit=functional_unit,
                 source_file=str(src),result_stage=result_stage))
    _validate_result_rows(rows)
    path=_safe(output_path,True)
    if path.exists():raise FileExistsError(f'File exists: {path}')
    _write_csv(path,RESULT_IMPORT_FIELDS,rows)
    return {'ok':True,'rows':len(rows),'file':str(path),'source_sha256':hashlib.sha256(src.read_bytes()).hexdigest(),
            'claim':'Normalized reported figures only, not an Agent-performed SimaPro calculation.'}


def combine_normalized_lcia(result_files: list[str], output_csv: str):
    """Merge multi-scenario normalized result files; reject duplicates and inconsistent global provenance."""
    if not 2<=len(result_files)<=50:raise ValueError('2..50 normalized files required')
    all_rows=[];seen=set();checks=[];base=None;units={}
    for filename in result_files:
        _,rows=_read_csv(filename,RESULT_IMPORT_FIELDS)
        _validate_result_rows(rows)
        for r in rows:
            key=(r['scenario'].strip(),r['indicator'].strip())
            if not all(key):raise ValueError(f'Empty scenario or indicator: {filename}')
            if key in seen:raise ValueError(f'Duplicate scenario and indicator: {key}')
            seen.add(key)
            if key[1] in units and units[key[1]]!=r['unit'].strip():
                raise ValueError(f'Incomparable units for {key[1]}')
            units[key[1]]=r['unit'].strip()
            provenance=tuple(r[k].strip() for k in PROVENANCE_FIELDS if k!='unit')
            if base is None:base=provenance
            elif provenance!=base:raise ValueError(f'Incomparable method/database/system_model/FU for {key}')
            all_rows.append(r)
        checks.append({'file':filename,'sha256':hashlib.sha256(_safe(filename).read_bytes()).hexdigest()})
    path=_safe(output_csv,True)
    if path.exists():raise FileExistsError(f'File exists: {path}')
    _write_csv(path,RESULT_IMPORT_FIELDS,all_rows)
    return {'ok':True,'file':str(path),'rows':len(all_rows),'inputs':checks,
            'note':'Combined user-supplied LCIA records; no SimaPro engine calculation occurred.'}


def compare_verified_results(file_path: str,baseline: str):
    _,rows=_read_csv(file_path,RESULT_IMPORT_FIELDS)
    _validate_result_rows(rows)
    seen={};bl={}
    for i,r in enumerate(rows,2):
        k=(r['scenario'],r['indicator'])
        if k in seen:raise ValueError(f'Duplicate indicator in one scenario on row {i}')
        seen[k]=r
        if r['scenario']==baseline: bl[r['indicator']]=r
    if not bl:raise ValueError('Baseline not found')
    comparison=[];warnings=[]
    for (scenario,indicator),r in sorted(seen.items()):
        if scenario==baseline:continue
        b=bl.get(indicator)
        if not b: warnings.append(f'{scenario}/{indicator}: not present in baseline');continue
        for field in PROVENANCE_FIELDS:
            if r[field].strip()!=b[field].strip():
                raise ValueError(f'INCOMPARABLE {scenario}/{indicator}: {field} differs between scenarios')
        v=core._number(r['value']);vb=core._number(b['value'])
        comparison.append({'scenario':scenario,'indicator':indicator,'unit':r['unit'],
                           'baseline':vb,'alternative':v,'delta':v-vb,
                           'relative_change_pct':(100*(v-vb)/abs(vb) if vb!=0 else None),
                           'lower_is_better_pct':(100*(vb-v)/vb if vb>0 else None)})
    for scenario in {s for s,_ in seen if s!=baseline}:
        for indicator in set(bl)-{i for s,i in seen if s==scenario}:
            warnings.append(f'{scenario}: missing baseline indicator {indicator}')
    return {'ok':True,'compared':comparison,'warnings':warnings,
            'evidence':'Direct comparison of user-supplied figures, with method and FU metadata matched.'}


def automation_checklist():
    return {'environment':'Windows, SimaPro 9.0 desktop, ordinary license',
      'workflow':[ 'Back up SimaPro database and create a NEW disposable test project',
        'Export one harmless blank/simple process in original SimaPro CSV, semicolon, decimal dot',
        'Prepare canonical foreground CSV and local catalog of licensed reference product names',
        'Generate mapping candidates; confirm exact unit/geography/system model; set approved=yes',
        'Create import candidate using version-matched native CSV template',
        'Import with File > Import into TEST project; review duplicate handling and object linking',
        'Confirm quantities, units, supplier links, mass/energy logic and model tree',
        'Select functional unit and installed LCIA method in SimaPro; calculate using native software',
        'Copy result table (Ctrl+C) into CSV/TSV, archive screenshot and native project',
        'Normalize explicit columns and compare after validating same FU/method/database version'],
       'disallowed_assumption':'Excel dynamic linking, COM and Excel scenario-import are not ordinary desktop features'}
