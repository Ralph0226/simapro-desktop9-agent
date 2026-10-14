"""SimaPro Desktop 9.0 ordinary-license LCA tools, MCP stdio server."""
from __future__ import annotations
from pathlib import Path
import sys
# Support both direct launching through Codex and module-style Python imports.
if __package__ in ('',None):
    sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from mcp.server.fastmcp import FastMCP
from mcp_server import core, desktop9, gui9

mcp=FastMCP('simapro-desktop9')

def protect(fn,*args,**kwargs):
    try:return fn(*args,**kwargs)
    except (ValueError,FileNotFoundError,FileExistsError,PermissionError,RuntimeError,OSError,UnicodeError,KeyError) as exc:
        return {'ok':False,'error':str(exc)}

@mcp.tool()
def simapro9_workflow() -> dict:
    """Version-specific read-only checklist; NO COM/API in ordinary SimaPro 9.0."""
    return desktop9.automation_checklist()

@mcp.tool()
def validate_lci(file_path: str) -> dict:
    """Validate canonical inventory rows; no SimaPro model edits."""
    return protect(core.validate_inventory,file_path)

@mcp.tool()
def summarize_lci(file_path: str) -> dict:
    """Summarize canonical foreground inventory; does not calculate LCIA."""
    return protect(core.inventory_summary,file_path)

@mcp.tool()
def suggest_background_links(inventory_csv: str,licensed_catalog_csv: str,
                             output_csv: str='outputs/dataset_mapping_review.csv',limit: int=3) -> dict:
    """Suggest local background datasets for EACH flow; manual verification and approved=yes required."""
    return protect(desktop9.list_dataset_candidates,inventory_csv,licensed_catalog_csv,output_csv,limit)

@mcp.tool()
def build_local_background_catalog(native_csv:str,output_csv:str,library:str,version:str,
              system_model:str,source:str,native_encoding:str='utf-8-sig')->dict:
    """Index reference products from a user-authorized subset of local native CSV exports."""
    return protect(desktop9.catalog_from_native_export,native_csv,output_csv,library,version,system_model,source,native_encoding)

@mcp.tool()
def inspect_native_csv_template(native_csv: str,native_encoding:str='utf-8-sig')->dict:
    """Read one authentic 9.0 native semicolon/dot process CSV; inspect only."""
    return protect(desktop9.inspect_native_template,native_csv,native_encoding)

@mcp.tool()
def prepare_simapro9_import(inventory_csv: str,approved_mapping_csv: str,authentic_template_csv: str,
                       candidate_csv: str='outputs/simapro9_import_CANDIDATE.csv',scenario_suffix: str='',native_encoding:str='utf-8-sig')->dict:
    """Prepare native CSV CANDIDATE using real exported process template; does not import/run."""
    return protect(desktop9.build_native_import_candidate,inventory_csv,approved_mapping_csv,
                   authentic_template_csv,candidate_csv,scenario_suffix,native_encoding)

@mcp.tool()
def create_lci_scenarios(file_path: str,process_id: str,flow_id: str,multipliers:list[float],
                         output_dir: str='outputs/scenarios')->dict:
    """Generate local parameter perturbations for distinct process imports; no LCIA run."""
    return protect(core.create_scenario_inventories,file_path,process_id,flow_id,multipliers,output_dir)

@mcp.tool()
def prepare_scenario_import_batch(inventory_csv:str,approved_mapping_csv:str,authentic_template_csv:str,
                        process_id:str,flow_id:str,multipliers:list[float],
                        output_dir:str='outputs/native_scenario_batch',native_encoding:str='utf-8-sig')->dict:
    """Create multiple versioned local LCI and native import candidates, not SimaPro calculations."""
    return protect(desktop9.prepare_batch_scenarios,inventory_csv,approved_mapping_csv,authentic_template_csv,
                   process_id,flow_id,multipliers,output_dir,native_encoding)


@mcp.tool()
def normalize_exported_lcia(file_path:str,output_csv:str,scenario:str,method:str,database:str,
     system_model:str,functional_unit:str,indicator_column:str,value_column:str,unit_column:str,
     result_stage:str,delimiter:str=',',encoding:str='utf-8-sig')->dict:
    """Normalize an actual user-provided result table exported/copied from SimaPro into a provenance-rich CSV."""
    return protect(desktop9.normalize_lcia_export,file_path,output_csv,scenario,method,database,
         system_model,functional_unit,indicator_column,value_column,unit_column,delimiter,encoding,result_stage)

@mcp.tool()
def combine_normalized_lcia_files(result_files:list[str],output_csv:str='outputs/lcia_combined.csv')->dict:
    """Merge normalized scenario exports and audit exact FU/method/database/system-model metadata."""
    return protect(desktop9.combine_normalized_lcia,result_files,output_csv)


@mcp.tool()
def compare_provenance_checked_lcia(file_path:str,baseline:str='baseline')->dict:
    """Reject comparisons with mismatched method, FU, units, database and system model."""
    return protect(desktop9.compare_verified_results,file_path,baseline)

@mcp.tool()
def capture_copied_result_table(output_tsv:str='outputs/lcia_clipboard_raw.tsv')->dict:
    """Read a text table manually copied from a visible SimaPro results window (origin unverified)."""
    return protect(gui9.capture_results_clipboard,output_tsv)


@mcp.tool()
def gui_inspect(max_controls:int=100)->dict:
    """Read-only inspect SimaPro Win32 controls on user desktop. Requires Windows pywinauto."""
    return protect(gui9.inspect_gui,max_controls)

@mcp.tool()
def gui_single_step(action:str,control_text:str='',key_sequence:str='',expected_window:str='',approval_token:str='')->dict:
    """Guarded ONE GUI click/type/screenshot; requires local enable, explicit per-action approval, and audit screenshots."""
    return protect(gui9.gui_step,action,control_text,key_sequence,expected_window,approval_token)

if __name__=='__main__':mcp.run(transport='stdio')
