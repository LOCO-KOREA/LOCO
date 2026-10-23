# 실호출 입력·DB·출력 대조 실행

`tests/live_output_ten.cjs`는 실제 Electron/Python/별도 SQLite/MediaPipe Heavy/외부 AI/Excel 경로를 시험한다. 사용자 화면과 입력 장치를 조작하지 않는다. 별도 프로필과 화면 밖·초점 불가 창을 회차마다 확인한다. 파일 선택·저장 dialog만 시험용 경로를 반환한다.

PowerShell에서 기존 API 키가 환경에 설정되어 있어야 한다. 키를 명령문·로그에 넣지 않는다. Python 가상환경과 `frontend/node_modules`, `.local/fixtures/tensorflow-movenet-example.jpeg`가 준비된 저장소 루트에서 실행한다.

```powershell
$env:LOCO_LIVE_AI='1'
$env:LOCO_CAMPAIGN_DIR=Join-Path (Get-Location) '.local/my-live-output-run'
node tests/live_output_ten.cjs
```

기본은 서로 다른 10종이다. 특정 반례의 재검증에는 `LOCO_CASE_IDS='06-decimal-load,08-zero-and-absent'`를 지정한다. 회차별 출력 경로를 재사용하지 않는다. 진행 중 앱 코드를 고치지 않고 `finished.json`의 전체 완료와 source manifest를 확인한 뒤 수정한다. SDK 외부 호출은 실제 사용량을 발생시킨다.

무하중 집중 시험의 `LOCO_CONFIRM_UNLOADED='1'`은 선택한 08의 시험 문장에 미는/당기는 힘도 없다고 명시하고 load=UNLOADED를 기대한다. 원래 10회의 문장은 고치지 않으며 새 case.json과 원장에 변경한 입력을 먼저 남긴다. 반복 조회의 revision/수동 관찰 근거 동일성도 검사한다.

입력은 넣기 전에 `actions.jsonl`에 기록한다. `openai.jsonl`은 SDK 원요청/원응답의 투명 기록이며 HTTP 응답을 대체하지 않는다. `ipc.jsonl`은 실제 JSON Lines 요청/응답이다. 동일한 회차에 새 텍스트가 저장되고 새 실제 AI 응답 ID를 받았는지도 검사한다. 저장 전/추가 답변/분석/직접 수정/재시작/설명 적용/Excel/과거 분석 출력/최종 재시작의 실제 SQL 행과 schema를 캡처한다.

`tests/live_output_audit.py verify <case-directory>`는 물리 DB·AI strict schema·공통 입력 경로·실제 XLSX 셀을 독립 대조한다. 변환 함수를 호출해서 그 함수의 정답을 재생산하지 않는다. 오라클 자체의 잘못된 타입·단위·셀·계산 피연산자 반례는 `test_live_output_audit.py`로 검증한다. 선언한 입력 기대와 실제 제출한 자연어의 저장도 검사하여, 저장된 값만 정확하게 출력하는 시험으로 끝내지 않는다.

`tests/replay_output_snapshots.py <campaign> <new-directory>`는 캡처한 과거 불변 출력 snapshot을 새 파일로 다시 렌더링한다. 실제 AI/UI 재실행이나 누락 정보 복구의 증거가 아니다. 원 snapshot·DB·기존 Excel은 고치지 않는다.

`tests/build_live_output_evidence.py`는 이번 검증의 지정 캠페인들로 최종 원장/CSV/보고서/일관된 DB backup/ZIP을 만든다. 최초 실패와 수정 중 실패도 보존한다. 마지막 통과 10종이 서로 다른 수정 단계의 근거라면 그 사실을 명시한다. origin/main 통합·배포·현장 정확도의 증거로 확대하지 않는다.

반례 시험은 `test_live_output_findings.py`다. 시간 합산의 부정 표현/실제 중복, FOLLOWUP 새 값과 CONFLICT, 값별 근거, 0/모름/NO/완전성, 조회 안정성, 저장 경합과 원문 보존, 소수 작업명을 확인한다. 서비스 계약과 물리 스키마는 [저장 계약](storage-persistence.md)을 따른다.
