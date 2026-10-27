# 시연 준비 - 발표 10분 전에 한 번 실행한다.
# 시연용 새 DB(.local\demo.db)를 만들고 AI 설정을 넣은 뒤 키·사진·AI 연결을 점검한다. 키 값은 화면에 찍지 않고 어디에도 저장하지 않는다.
#   .\prepare-demo.ps1                     게이트웨이 키(사용자 환경 변수 AI_GATEWAY_API_KEY)로 openai/gpt-6-luna
#   .\prepare-demo.ps1 -Model gpt-6-luna   OpenAI 키(환경 변수 OPENAI_API_KEY)를 직접 쓸 때
#   .\prepare-demo.ps1 -SkipAiCheck        AI 연결 시험(아주 작은 요청 1번)을 건너뛴다
param(
    [string]$Model = 'openai/gpt-6-luna',
    [string]$DatabasePath = '',
    [switch]$SkipAiCheck
)
$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path $PSScriptRoot '..\..\..')).Path
if (-not $DatabasePath) { $DatabasePath = Join-Path $root '.local\demo.db' }
$python = Join-Path $root '.venv\Scripts\python.exe'
$script:ready = $true
function Check([string]$label, [bool]$good, [string]$hint) {
    if ($good) { Write-Host ('[OK] ' + $label) }
    else { Write-Host ('[!!] ' + $label + '  ->  ' + $hint) -ForegroundColor Yellow; $script:ready = $false }
}

Check 'Python 3.12 가상환경(.venv)' (Test-Path $python) '저장소 README의 "설치와 실행"을 먼저 따라 하세요'
Check 'Electron 설치(frontend\node_modules)' (Test-Path (Join-Path $root 'frontend\node_modules\electron')) 'npm.cmd --prefix frontend ci'
Check '자세 모델(models\pose_landmarker_heavy.task)' (Test-Path (Join-Path $root 'models\pose_landmarker_heavy.task')) '.\.venv\Scripts\python.exe scripts\download_pose_models.py'
Check '시연 사진(demo\photos)' (Test-Path -LiteralPath (Join-Path $PSScriptRoot 'photos\01-키보드작업(CC0).jpg')) 'demo\photos 폴더를 통째로 복사해 두세요'

$source = 'OPENAI_API_KEY'
$key = $env:OPENAI_API_KEY
if (-not $key) { $key = [Environment]::GetEnvironmentVariable('AI_GATEWAY_API_KEY', 'User'); $source = 'AI_GATEWAY_API_KEY(사용자 환경 변수)' }
Check ('AI 키 있음 - ' + $source) ([bool]$key) '키가 없으면 AI 정리 없이 첫 점수까지만 보입니다(플랜 B)'
if (-not $script:ready -and -not (Test-Path $python)) { Write-Host '먼저 위 항목을 해결한 뒤 다시 실행하세요.' -ForegroundColor Yellow; exit 1 }

# 시연용 새 DB + AI 설정(켜짐, 모델, 추론 강도 high). 키는 설정에 저장되지 않는다.
if (Test-Path -LiteralPath $DatabasePath) { Remove-Item -LiteralPath $DatabasePath -Force }
New-Item -ItemType Directory -Force (Split-Path $DatabasePath) | Out-Null
$seed = @'
import sys
from ergo.service.application import create_service
db, model = sys.argv[1], sys.argv[2]
ctx = create_service(db)
settings = ctx.dispatch('get_settings', {})
settings.pop('gpt_key_present', None)
settings.update(gpt_enabled=True, gpt_model=model, gpt_reasoning_effort='high')
ctx.dispatch('update_settings', dict(settings=settings))
print('saved: model=%s effort=high' % model)
'@
Push-Location $root
try { $seed | & $python -X utf8 - $DatabasePath $Model } finally { Pop-Location }
Write-Host ('[OK] 시연용 DB 새로 만듦: ' + $DatabasePath)

if (-not $SkipAiCheck -and $key) {
    $previous = @{ key = $env:OPENAI_API_KEY; url = $env:OPENAI_BASE_URL }
    try {
        $env:OPENAI_API_KEY = $key
        if (-not $previous.url -and $source -like 'AI_GATEWAY*') { $env:OPENAI_BASE_URL = 'https://ai-gateway.vercel.sh/v1' }
        $probe = @'
import os, sys, time
from ergo.gpt.client_pool import create_response
start = time.time()
try:
    create_response(os.environ['OPENAI_API_KEY'], model=sys.argv[1], input='Reply with: ok', max_output_tokens=64, reasoning=dict(effort='low'))
    print('OK %.1f' % (time.time() - start))
except Exception as error:
    print('FAIL %s %s' % (type(error).__name__, str(error)[:160]))
'@
        Push-Location $root
        try { $answer = ($probe | & $python -X utf8 - $Model | Select-Object -Last 1) } finally { Pop-Location }
    } finally {
        if ($null -eq $previous.key) { Remove-Item Env:OPENAI_API_KEY -ErrorAction SilentlyContinue } else { $env:OPENAI_API_KEY = $previous.key }
        if ($null -eq $previous.url) { Remove-Item Env:OPENAI_BASE_URL -ErrorAction SilentlyContinue } else { $env:OPENAI_BASE_URL = $previous.url }
    }
    if ($answer -like 'OK*') { Write-Host ('[OK] AI 연결 시험 통과 (' + $answer.Substring(3).Trim() + '초)') }
    else { Write-Host ('[!!] AI 연결 시험 실패: ' + $answer + '  ->  네트워크·키·모델 이름(-Model)을 확인하세요. 안 되면 플랜 B로 갑니다.') -ForegroundColor Yellow; $script:ready = $false }
}

if ($script:ready) { Write-Host "`n준비 끝. 시연은 .\start-demo.ps1 로 시작하세요." -ForegroundColor Green }
else { Write-Host "`n[!!] 표시된 항목을 확인한 뒤 다시 실행하세요." -ForegroundColor Yellow }
