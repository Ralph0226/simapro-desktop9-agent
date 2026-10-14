$ErrorActionPreference = 'Stop'
Set-Location (Join-Path $PSScriptRoot '..')
$env:SIMAPRO_WORKSPACE = (Get-Location).Path
if (-not (Test-Path '.\.venv\Scripts\python.exe')) { Write-Error 'Create venv first (see README.md)' }
& '.\.venv\Scripts\python.exe' -m unittest discover -s tests -v
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
& '.\.venv\Scripts\python.exe' '.\scripts\mcp_smoke.py'
exit $LASTEXITCODE
