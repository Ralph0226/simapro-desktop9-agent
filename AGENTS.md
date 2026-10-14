# Agent operating rules — SimaPro 9.0 ordinary desktop

Use `.agents/skills/simapro-desktop9/SKILL.md` for all SimaPro work. Target SimaPro 9.0 desktop normal license, not COM Developer/API.

Always operate in `SIMAPRO_WORKSPACE`; all MCP paths are relative to that workspace. For actual database writes, the human operator must back up the database, import into an isolated test project, approve exact mappings, check import error logs, and verify process links before considering any LCA results.

Never treat demo data, file generation, SimaPro import, UI clicks and actual SimaPro LCIA as equivalent states. Do not auto-link unknown ecoinvent providers or overwrite original processes.
