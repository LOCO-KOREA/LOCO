param(
    [string]$PythonPath = 'python',
    [string]$ModelPath = '',
    [string]$DatabasePath = ''
)
# Uses the team's existing Electron launcher with the shared Python service.
# Specify a CPython 3.12 environment with requirements-desktop.txt installed.
# Existing sample data is not copied or merged.
$ErrorActionPreference = 'Stop'
# Resolve explicit relative paths before frontend/start.ps1 changes directory.
if ($PythonPath.Contains('/') -or $PythonPath.Contains('\')) {
    $PythonPath = $ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($PythonPath)
}
if ($ModelPath) {
    $ModelPath = $ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($ModelPath)
}
if ($DatabasePath) {
    $DatabasePath = $ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($DatabasePath)
}
if (-not $DatabasePath) {
    $DatabasePath = Join-Path $PSScriptRoot 'frontend/.local/loco_frontend.db'
}
$serviceEntry = Join-Path $PSScriptRoot 'ergo/service/json_lines.py'
$previousModel = $env:LOCO_MOVENET_MODEL
try {
    if ($ModelPath) { $env:LOCO_MOVENET_MODEL = $ModelPath }
    & (Join-Path $PSScriptRoot 'frontend/start.ps1') `
        -PythonPath $PythonPath -ServiceEntry $serviceEntry -DatabasePath $DatabasePath
} finally {
    $env:LOCO_MOVENET_MODEL = $previousModel
}
