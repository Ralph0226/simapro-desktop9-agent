param([switch]$GuiDependencies, [switch]$RegisterCodex)
$ErrorActionPreference = 'Stop'
$repoDir = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
$pythonExe = Join-Path $repoDir '.venv\Scripts\python.exe'
Push-Location $repoDir
try {
    if (-not (Test-Path -LiteralPath $pythonExe)) {
        & py -3.12 -m venv .venv
        if ($LASTEXITCODE -ne 0) { throw 'Python 3.12 is required for this Windows setup.' }
    }
    & $pythonExe -m pip install -r mcp_server\requirements.txt
    if ($LASTEXITCODE -ne 0) { throw 'MCP dependency installation failed.' }
    if ($GuiDependencies) {
        & $pythonExe -m pip install -r mcp_server\requirements-windows-gui.txt
        if ($LASTEXITCODE -ne 0) { throw 'GUI dependency installation failed.' }
    }
    & $pythonExe -m unittest discover -s tests -v
    if ($LASTEXITCODE -ne 0) { throw 'Local tests failed; Codex registration was not attempted.' }
    & $pythonExe scripts\mcp_smoke.py
    if ($LASTEXITCODE -ne 0) { throw 'MCP protocol test failed; Codex registration was not attempted.' }
    if ($RegisterCodex) {
        $profileDir = [Environment]::GetFolderPath('UserProfile')
        $skillDir = Join-Path $profileDir '.agents\skills\simapro-desktop9'
        if (Test-Path -LiteralPath $skillDir) { throw "Skill already exists: $skillDir. Review it before replacing." }
        $codexDir = if ($env:CODEX_HOME) { $env:CODEX_HOME } else { Join-Path $profileDir '.codex' }
        $configFile = Join-Path $codexDir 'config.toml'
        & $pythonExe -c "import sys,tomllib; from pathlib import Path; p=Path(sys.argv[1]); c=tomllib.loads(p.read_text(encoding='utf-8')) if p.exists() else {}; sys.exit(1 if 'simapro9' in c.get('mcp_servers',{}) else 0)" $configFile
        if ($LASTEXITCODE -ne 0) { throw 'simapro9 is already configured; inspect it before replacement.' }
        New-Item -ItemType Directory -Path (Join-Path $repoDir 'local-evidence') -Force | Out-Null
        if (Test-Path -LiteralPath $configFile) {
            $backupFile = Join-Path $repoDir ('local-evidence\codex-config-' + (Get-Date -Format 'yyyyMMdd-HHmmss') + '.bak')
            Copy-Item -LiteralPath $configFile -Destination $backupFile
        }
        & codex mcp add simapro9 --env "SIMAPRO_WORKSPACE=$repoDir" --env 'SIMAPRO_GUI_ENABLED=0' -- $pythonExe (Join-Path $repoDir 'mcp_server\server.py')
        if ($LASTEXITCODE -ne 0) { throw 'Codex MCP registration failed.' }
        New-Item -ItemType Directory -Path (Split-Path $skillDir -Parent) -Force | Out-Null
        Copy-Item -LiteralPath (Join-Path $repoDir '.agents\skills\simapro-desktop9') -Destination $skillDir -Recurse
        Write-Output "Skill installed: $skillDir"
        Write-Output 'MCP simapro9 registered. Restart Codex or open a new chat. GUI input remains disabled.'
    }
} finally { Pop-Location }
