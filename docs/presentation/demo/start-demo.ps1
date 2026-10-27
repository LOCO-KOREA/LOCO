# 시연 시작 - 시연용 DB(.local\demo.db)로 앱을 연다. 먼저 .\prepare-demo.ps1 을 한 번 실행해 둔다.
# AI 키는 이 창의 환경 변수로만 앱에 넘기고 어디에도 저장하지 않는다. 앱을 닫으면 이 창으로 돌아온다.
#   .\start-demo.ps1              앱을 연다
#   .\start-demo.ps1 -DryRun      무엇을 열지만 보여 주고 열지는 않는다
param(
    [string]$DatabasePath = '',
    [switch]$DryRun,
    [switch]$Hidden
)
$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path $PSScriptRoot '..\..\..')).Path
if (-not $DatabasePath) { $DatabasePath = Join-Path $root '.local\demo.db' }
$python = Join-Path $root '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $DatabasePath)) { throw '시연용 DB가 없습니다. 먼저 .\prepare-demo.ps1 을 실행하세요.' }

$previous = @{ key = $env:OPENAI_API_KEY; url = $env:OPENAI_BASE_URL; hidden = $env:LOCO_HIDDEN }
try {
    $mode = 'AI 키: 이 창의 OPENAI_API_KEY 사용'
    if (-not $env:OPENAI_API_KEY) {
        $gateway = [Environment]::GetEnvironmentVariable('AI_GATEWAY_API_KEY', 'User')
        if ($gateway) {
            $env:OPENAI_API_KEY = $gateway
            if (-not $env:OPENAI_BASE_URL) { $env:OPENAI_BASE_URL = 'https://ai-gateway.vercel.sh/v1' }
            $mode = 'AI 키: 사용자 환경 변수 AI_GATEWAY_API_KEY를 이 창에서만 사용(게이트웨이)'
        } else { $mode = 'AI 키 없음: AI 정리는 꺼진 채로 시작합니다(첫 점수까지만 - 플랜 B)' }
    }
    if ($Hidden) { $env:LOCO_HIDDEN = '1' }
    Write-Host ('DB: ' + $DatabasePath); Write-Host $mode
    if ($DryRun) { Write-Host '(DryRun: 앱을 열지 않았습니다)'; return }
    & (Join-Path $root 'run-integrated.ps1') -PythonPath $python -DatabasePath $DatabasePath
} finally {
    if ($null -eq $previous.key) { Remove-Item Env:OPENAI_API_KEY -ErrorAction SilentlyContinue } else { $env:OPENAI_API_KEY = $previous.key }
    if ($null -eq $previous.url) { Remove-Item Env:OPENAI_BASE_URL -ErrorAction SilentlyContinue } else { $env:OPENAI_BASE_URL = $previous.url }
    if ($null -eq $previous.hidden) { Remove-Item Env:LOCO_HIDDEN -ErrorAction SilentlyContinue } else { $env:LOCO_HIDDEN = $previous.hidden }
}
