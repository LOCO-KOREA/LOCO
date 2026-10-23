param(
    [Parameter(Mandatory=$true)][string]$RepoRoot,
    [Parameter(Mandatory=$true)][string]$SourceDirectory,
    [string]$DestinationDirectory,
    [int]$RemoteDebuggingPort=18875
)
$ErrorActionPreference='Stop'
$taskRepo=(Resolve-Path -LiteralPath $RepoRoot).Path
$taskSource=(Resolve-Path -LiteralPath $SourceDirectory).Path
$taskPython=Join-Path $taskRepo '.venv\Scripts\python.exe'
$taskRevision=(& git -C $taskRepo rev-parse HEAD).Trim()
if($LASTEXITCODE -ne 0){throw '앱 소스 위치를 확인해 주세요.'}
if(-not $DestinationDirectory){$DestinationDirectory=Join-Path $taskRepo ('.local\manual-vision-'+$taskRevision.Substring(0,7)+'-'+(Get-Date -Format 'yyyyMMdd-HHmmss'))}
$taskDestination=[IO.Path]::GetFullPath($DestinationDirectory)
& $taskPython (Join-Path $PSScriptRoot 'prepare_visible_clone.py') $taskSource $taskDestination
if($LASTEXITCODE -ne 0){throw '자료 복사 결과를 확인해 주세요. 기존 앱은 그대로 실행 중입니다.'}
foreach($folder in @('media','profile')){
    $from=Join-Path $taskSource $folder
    $to=Join-Path $taskDestination $folder
    if(Test-Path -LiteralPath $from){
        & robocopy $from $to /E /COPY:DAT /DCOPY:DAT /R:0 /W:0 /XJ /XF LOCK lockfile SingletonLock SingletonCookie DevToolsActivePort /NFL /NDL /NJH /NJS | Out-File -LiteralPath (Join-Path $taskDestination ('copy-'+$folder+'.log')) -Encoding utf8
        if($LASTEXITCODE -ge 8){throw ('복사하지 못한 '+$folder+' 파일을 로그에서 확인해 주세요. 기존 앱과 원본은 유지했습니다.')}
    }
}
$configuration=@{
    repo_root=$taskRepo;source_directory=$taskSource;destination_directory=$taskDestination;
    source_sha=$taskRevision;remote_debugging_port=$RemoteDebuggingPort;
    source_app_stopped=$false;profile_copy_atomic=$false;launch_performed=$false
}
$configuration | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $taskDestination 'launch-config.json') -Encoding utf8
$launch=@'
$ErrorActionPreference='Stop'
$node=(Get-Command node -ErrorAction Stop).Source
& $node (Join-Path $PSScriptRoot 'launch-visible.cjs') (Join-Path $PSScriptRoot 'launch-config.json')
if($LASTEXITCODE -ne 0){throw '새 앱 시작 로그를 확인해 주세요. 기존 앱은 그대로입니다.'}
'@
Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'launch_visible_clone.cjs') -Destination (Join-Path $taskDestination 'launch-visible.cjs')
$launch | Set-Content -LiteralPath (Join-Path $taskDestination 'launch-visible.ps1') -Encoding utf8
Write-Output ('Prepared only; no app launched: '+(Join-Path $taskDestination 'launch-visible.ps1'))
