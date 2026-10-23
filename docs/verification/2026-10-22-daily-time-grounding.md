# 이미 답한 하루 총시간 재질문 수정

2026-10-22, `feat/mediapipe-heavy`, 수정 전 커밋 `5632588`. 새 PR을 생성하거나 닫힌 PR #26을 다시 열지 않는다.

## 원인과 변경

현재 앱의 읽기 전용 DB 확인에서 “손을 이미지대로 높이 드는 걸 한 2시간 하고 키보드 작업 6시간 해.”라는 저장 진술과 각각 120분/360분인 AI 사실을 확인했다. 하루 전체 시간은 null이었고 last_dropped에는 daily_work_min의 UNIT_OR_NUMBER_NOT_GROUNDED가 있었다. 검증기는 단일 시간 수치와 단위 변환만 검사해서 원문에 직접 나오지 않은 480분의 합산 근거를 인정하지 못했다. 같은 문장을 사용한 회귀 시험도 수정 전에 None != 480으로 실패했다.

공통 필드 계약의 derivations에서 하루 총시간에만 SUM_STATED_DURATIONS를 허용한다. 숫자 검증은 순수 모듈 ergo/intake/grounding.py로 분리했고, AI가 실제 원문으로 제안한 각 시간의 분 환산·합계를 독립 검증한다. 같은 quote에서 120+360=480이 확인되면 각 작업별 노출을 유지하면서 conditions.daily_work_min=480으로 투영한다. 선택 calculation 객체에 연산·각 피연산 원문·분 값·합계를 남긴다. 원문에 없는 숫자나 연산을 검증기가 직접 추출해 사실로 만들지 않는다.

겹침·포함·동시 작업·휴식·범위·다른 주기·부분 일정은 단순 합산에서 제외한다. 다른 노출 필드에는 합산 권한을 주지 않았고, 직접 입력/모름·최신 값 우선순위와 불변 분석 snapshot도 유지한다. 규칙 계산·REBA나 여섯 DB 테이블은 변경하지 않았다.

## 실제 검증

- 새 회귀 4개: 제보 문장의 480분 저장/중복 질문 제거/재시작, 복합 단위·잘못된 합계, 겹침/휴식/범위/다른 주기/부분 일정/다른 필드 예외, 과거 진술 복구와 USER 값 보존. 전체 Python 249개 통과.
- 실제 Luna/xhigh, 화면 밖·초점 불가 Electron, Python, SQLite, MediaPipe, Excel을 연결한 `.local/daily-time-final-live/receipt.json` 5개 통과, errors=[]. 실제 응답 ID/모델/effort를 확인했다. 120·360·480 저장, 총시간 재질문 없음, 앱 재시작, 실제 계산 snapshot, PDF 미리보기를 거친 기존 고급 Excel 저장을 검증했다.
- `tests/verify_local_artifacts.py .local/daily-time-final-live 1` 통과. 실제 DB의 여섯 테이블, 계산/출력 snapshot, workbook을 독립 대조했다. 출력 “입력한 값” 시트에는 하루 전체 480분/일, 키보드 360분/일, 손·팔 들기 120분/일이 각각 존재한다.
- 실제 workbook을 artifact_tool로 읽기 전용 import/inspect/render하여 위 세 값을 다시 확인했다. 검사 과정에서 workbook을 재저장하지 않았다.
- frontend 회귀 14개와 build 통과. API audit 구현/문서 48개·renderer 41개 일치.
- 최초 live 검증은 고급 화면 전환 후 정보 화면 전용 task_name 필드를 기다리는 시험 선택자가 잘못되어 중단했다. 작업 조건 화면의 준비 상태를 기다리도록 수정하고 새 DB/프로필에서 5개 전체를 다시 통과했다.

## 현재 열린 작업 반영

기존 feature 앱 DB의 일관된 백업 `.local/mediapipe-demo/before-daily-time-fix.db`와 작성 중 값을 보존했다. 새 코드로 이 앱만 재시작한 뒤, 빈 재시도 요청으로 저장된 과거 사용자 진술을 실제 AI에 다시 처리했다. SQL 직접 수정이나 합성 답변 삽입 없이 기존 intake_turn의 revision 검사를 거쳐 480분 및 계산 근거를 저장했다. 실제 연결은 gpt-6-luna/xhigh CONNECTED이며, 현재 화면과 응답 질문 목록에서 daily_work_min 재질문이 없는 것을 확인했다.

작성 중 작업에는 아직 분석 결과가 없을 수 있으므로 해당 UI 복원은 실제 preview를 사용했다. 검증 보조 도구가 분석 결과를 가정해 null 참조한 뒤 이를 구분하여 표시를 완료했다. 존재하지 않는 분석을 만들거나 완료로 표시하지 않았다. 앱 PID 23132는 showInactive로 표시됐고 표시 당시 focused=false다. OS 마우스·키보드를 사용하지 않았으며 원래 main 앱/DB는 수정하지 않았다.
