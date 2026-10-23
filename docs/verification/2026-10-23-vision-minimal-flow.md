# Luna 사진 관찰과 최소 질문 실호출 검증

1차 검증 소스는 `f909714f596a69cb1b6a342cb47d2e80ad709c5e`이다. 등록 UUID/context 처리와 명시 텍스트 우선권 수정 이후의 최종 재검증은 아래 별도 절에 기록한다.

숨긴 Electron 창, 실제 Python 서비스·SQLite·MediaPipe Heavy·외부 Luna xhigh를 사용했다. 작업 입력·사진 크롭·확인·Excel 저장은 화면 동작으로 실행했다. 읽기 API와 물리 DB 대조로만 확인하며 미확인 값을 API로 채우지 않았다. 창은 화면 밖에 있고 focusable=false이며 마우스·키보드 입력을 사용하지 않았다.

| 사례 | 처음 제공한 정보 | 추가 팝업/답변 | UI 검사 | DB·Excel 검사 |
|---|---|---:|---:|---:|
| A | 사진 없음, 연간30일, 일회성아님 | 0/0 | 23 | 388 |
| B | 사진1장, 키보드120분·팔들기180분·하루전체300분·연220일·일회성아님 | 1/1 | 41 | 702 |
| C | 실제 측면 사진1장, B의 시간과 겹치는 허리·목·무릎 굽힘180분, 비틀림·쪼그림0분, 지지없음·자세제한없음 | 1/1 | 61 | 802 |

세 사례 모두 실제 Excel 저장까지 도달했고 검사 결함·실행 오류는 0건이다. B/C는 남은 작업 특징을 하지 않는다는 화면 버튼을 각각 한 번 눌렀다. 이미 확인한 항목이 미확인 질문으로 표시되지 않았고 빈 작업 조건 창도 나타나지 않았다. C의 시간·조건은 테스트에서 사용자가 처음부터 선언한 가상 작업 정보이며 사진에서 추정한 값이 아니다. B의 기존 운동 사진·입력은 변경하지 않았다. 이후 다른 사진이 새 작업 특징을 분명하게 보여 주면 추가 노출시간이 필요할 수 있으므로 모든 작업에 0/1회가 보장된다는 뜻은 아니다.

사진 없는 A는 이미지 API 호출0회이다. B/C는 각각 실제 이미지 요청1회와 텍스트 정리2회를 기록했다. 읽기·직접 선택 저장은 추가 이미지 호출을 만들지 않았다. 사진 관찰9개와 모호한 이유를 저장하고 초기 화면과 선택 분석의 결과 화면에 표시했다. 숫자 confidence는 모델 응답/DB에 보존하고 일반 사용자 화면에는 표시하지 않았다.

실제 SDK 전송 이미지의 SHA와 저장된 encoded_sha256, 등록 크롭과 source_sha256, 응답 ID, 원문9관찰과 물리 DB·불변 분석 snapshot의 동일성 및 결과 화면의 동작·허리·무릎 표시를 추가18검사로 대조했다. 모두 일치했다. 원본 사진 파일은 변경하지 않았다. 전체 앱 소스 manifest도 실행 전후 동일했다.

로컬 증거는 `LOCO-luna-vision-20261023/.local/minimal-vision-f909714-r1/`의 `finished.json`, 각 사례 `receipt.json`·`audit.json`·`final-output.xlsx`·화면 PNG, `image-linkage.json`이다. 이미지 관찰의 임상적 정확도나 법정 판단의 타당성을 이 세 사례로 주장하지 않는다.

새 일반 사용자 창 준비는 `scripts/prepare-visible-vision-app.ps1`로 분리했다. 기존 앱을 종료하지 않고 원본 SQLite를 읽기 전용 backup으로 복제하며, 현재 PHOTO 경로만 복사한 파일로 연결하고 과거 분석 snapshot은 그대로 둔다. profile/media를 새 위치에 복사하고 별도 `launch-visible.ps1`를 생성한다. 준비 명령은 앱을 띄우지 않으며 새 창 시작은 호출자가 실행한다. 실행 중인 profile의 파일 복사는 원자적 snapshot이 아니므로 원본 profile도 그대로 보존한다.

## 최종 후속 소스의 A/C 재실행

최종 runtime은 `e8ded39bc2cadd909c9f0c3aef520fdf7a85f610`이다. 등록 UUID/context 처리, 명시 텍스트의 VISION 추정 우선권, 사진이 해당 작업이 아니라고 확인한 경우의 계산 미적용 안내가 통합된 뒤 A/C의 문장·사진을 바꾸지 않고 실제 호출했다. runtime manifest는 시작과 종료가 동일했다.

| 최종 사례 | 추가 팝업/답변 | UI 검사 | DB·Excel 검사 | 결과 |
|---|---:|---:|---:|---|
| A | 0/0 | 23 | 388 | 실제 Excel 저장, 결함0 |
| C | 1/1 | 61 | 802 | 실제 사진9관찰·Heavy33점·Excel 저장, 결함0 |

C는 이미지1회·텍스트2회를 실제 호출했으며 읽기/직접 확인 시 추가 이미지 호출은 없었다. 실제 전송 이미지 SHA, 등록 사진 SHA, 실제 응답 ID와 원문9관찰, 물리 DB·불변 snapshot·결과 화면의 주요3관찰도 추가9검사에서 일치했다. B의 결과는 앞선 f909714 실행의 기록으로만 구분하며 이 최종 runtime에서 재실행했다고 주장하지 않는다. 최종 A/C 증거는 `LOCO-luna-vision-20261023/.local/minimal-vision-e8ded39-final/`의 `finished.json`, 각 사례의 `receipt.json`·`audit.json`·Excel·PNG, `image-linkage.json`에 있다.

복제/시작 스크립트는 가상 DB·사진·profile로 실행해 원본 DB SHA 불변, PHOTO 복사 경로 연결, 기존 ANALYSIS snapshot 불변, profile 복사, 생성한 PowerShell 문법을 확인했다. 이 검사에서 실제 앱 실행은0회였다. 실제 사용자 자료 복제와 새 창 실행은 root가 수행한다.

```powershell
$taskRepo = 'C:\Users\금정산2-PC02\Documents\Codex\2026-10-22\https-github-com-loco-korea-loco\work\LOCO-luna-vision-20261023'
$taskSource = 'C:\Users\금정산2-PC02\Documents\Codex\2026-10-22\https-github-com-loco-korea-loco\work\LOCO-main-latest-review-20261023\.local\manual-updated-c886b8d'
& (Join-Path $taskRepo 'scripts\prepare-visible-vision-app.ps1') -RepoRoot $taskRepo -SourceDirectory $taskSource -RemoteDebuggingPort 18875
# 출력된 새 경로의 launch-visible.ps1를 root가 별도로 실행한다.
```
