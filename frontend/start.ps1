param(
    [string]$PythonPath = 'python',
    [string]$DatabasePath = ''
)
$ErrorActionPreference = 'Stop'
Push-Location $PSScriptRoot
$previousPython = $env:LOCO_PYTHON
$previousDatabase = $env:LOCO_DB_PATH
$previousElectronMode = $env:ELECTRON_RUN_AS_NODE
try {
    $env:LOCO_PYTHON = $PythonPath
    if ($DatabasePath) { $env:LOCO_DB_PATH = $DatabasePath }
    Remove-Item Env:ELECTRON_RUN_AS_NODE -ErrorAction SilentlyContinue
    & npm.cmd start
    if ($LASTEXITCODE -ne 0) { throw "Electron exited with code $LASTEXITCODE" }
} finally {
    $env:LOCO_PYTHON = $previousPython
    $env:LOCO_DB_PATH = $previousDatabase
    $env:ELECTRON_RUN_AS_NODE = $previousElectronMode
    Pop-Location
}
