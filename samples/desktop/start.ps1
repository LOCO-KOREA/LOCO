param([string]$PythonPath, [string]$ModelPath)
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
if ($PythonPath) { $env:LOCO_PYTHON = $PythonPath }
elseif (Test-Path -LiteralPath (Join-Path $PSScriptRoot '.venv/Scripts/python.exe')) {
    $env:LOCO_PYTHON = Join-Path $PSScriptRoot '.venv/Scripts/python.exe'
}
if ($ModelPath) { $env:LOCO_MOVENET_MODEL = [System.IO.Path]::GetFullPath($ModelPath) }
if (-not (Test-Path -LiteralPath (Join-Path $PSScriptRoot 'node_modules/electron/dist/electron.exe'))) {
    & npm.cmd install --cache .npm-cache
    if ($LASTEXITCODE -ne 0) { throw 'Electron 의존성 설치에 실패했습니다.' }
}
& npm.cmd start
