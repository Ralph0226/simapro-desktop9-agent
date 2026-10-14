"""Exercise the actual stdio server, without touching a SimaPro database."""
import asyncio
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


async def main():
    root=Path(__file__).resolve().parents[1]
    scratch=root/'local-evidence'
    scratch.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(dir=scratch) as tmp:
        shutil.copy(root/'examples/desktop9_simple_lci_DEMO.csv',Path(tmp)/'lci.csv')
        params=StdioServerParameters(command=sys.executable,args=[str(root/'mcp_server/server.py')],
            env={**os.environ,'SIMAPRO_WORKSPACE':tmp,'SIMAPRO_GUI_ENABLED':'0'})
        async with stdio_client(params) as (read,write):
            async with ClientSession(read,write) as session:
                await session.initialize()
                listed=await session.list_tools()
                names={t.name for t in listed.tools}
                assert len(names)==15,names
                normalize=next(t for t in listed.tools if t.name=='normalize_exported_lcia')
                assert 'result_stage' in normalize.inputSchema['required']
                workflow=await session.call_tool('simapro9_workflow',{})
                assert not workflow.isError
                valid=await session.call_tool('validate_lci',{'file_path':'lci.csv'})
                assert json.loads(valid.content[0].text)['ok']
                invalid=await session.call_tool('validate_lci',{'file_path':'../outside.csv'})
                assert not json.loads(invalid.content[0].text)['ok']
                disabled=await session.call_tool('gui_single_step',{'action':'screenshot'})
                assert not json.loads(disabled.content[0].text)['ok']
                print(json.dumps({'ok':True,'transport':'stdio','tools':sorted(names),
                                  'checked':['initialize','list_tools','LCI validation','path rejection','GUI disabled']},indent=2))


if __name__=='__main__':
    asyncio.run(main())
