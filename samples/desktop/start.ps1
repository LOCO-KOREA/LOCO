param([string]$PythonPath = 'python')
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$env:LOCO_PYTHON = $PythonPath
if (-not (Test-Path -LiteralPath (Join-Path $PSScriptRoot 'node_modules/electron/dist/electron.exe'))) {
    & npm.cmd install --cache .npm-cache
    if ($LASTEXITCODE -ne 0) { throw 'Electron 의존성 설치에 실패했습니다.' }
}
& npm.cmd start
