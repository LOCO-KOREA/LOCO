# 실제 12사례 최종 독립 대조 · 2026-10-23

검증 대상 앱 내용은 c886b8d와 동일한 160개 ergo/frontend 파일이다. 최초 A의 기록 HEAD는 de0ea9b, B는 c886b8d, 재시도는 tests/docs 후속 HEAD였으므로 HEAD 표기만으로 같은 소스라고 가정하지 않았다. 네 캠페인의 전체 파일 목록·SHA256을 현재 디스크와 최종 Git 내용에 독립 대조했다. 시작/종료 14개 검사는 불일치 0이며 공통 manifest 해시는 `5b5ee91d4f3edaec2edd55e04cf1cdb069f861812cc91970335ae6bc44b01829`다. 150개는 Git blob과 raw byte가 같고, 10개는 Git LF를 CRLF로 직렬화한 것과 정확히 같다. 다른 byte 차이는 없다. 런타임 의존성·모델 파일은 이 160개 manifest와 구분한다.

원본 캠페인 ROOT `.local/live-final-integrated-a-20261023`의 01/02/03과 B의 07/08/09, `.local/live-final-retry-a-20261023`의 04/05/06과 retry-b의 10/11/12를 최종 완료 증거로 선택했다. 최초 04/06/11은 디스크 여유 0 기간에 worker 종료가 관측됐지만 원인은 확정하지 않았다. 05는 직접 Errno28, 10은 빈 receipt, 12는 미시작이다. 이 시도를 통과로 세지 않고 선택표에 보존했다. 통제된 test trace writer ENOSPC는 실제 dispatch 전 worker를 종료시킬 수 있음을 재현했으나 과거 세 worker 종료의 원인이라는 주장은 아니다.

| 독립 대조 | 실제 결과 |
|---|---|
| 완성된 실제 UI/DB/Excel/재시작 사례 | 12/12, UI 오류·불일치 0 |
| 최초 원문에서 명시한 선언값 | 115개, 원문/물리 DB 보조검사 포함 158개 모두 통과 |
| 전체 물리 DB·선택 불변 snapshot·실제 Excel 셀 | 30,176개 모두 통과 |
| 최초/후속/직접수정/재시작의 확장 원장 | 1,626개 모두 통과 |
| 무게·횟수 조건 결합, 사진 하중 연결·명시적 모름 | 114개 모두 통과 |
| 종료 physical DB backup과 마지막 checkpoint | TASK JSON/revision, ANALYSIS, EXPORT_LOG 36개 모두 통과 |
| 실제 SDK 요청·응답·오류 | 84/84/0, gpt-6-luna와 xhigh 일치 |
| native 마우스·키보드 | 사용하지 않음 |

원본 JSON/JSONL/XLSX는 읽기 전용으로 조회했다. 독립 감사는 별도 폴더에 작은 결과 JSON과 최종 SQLite read-only backup만 작성했다. 이미 보관한 원본을 수정하지 않았다. 디스크 부족 때 중복 IPC copy 하나는 원본 SHA256 일치를 확인한 뒤 단일 파일로 정리했고, 기존 독립 보관본 439개 파일은 NTFS 압축 전후 SHA256이 같았다.

지속 증거는 `LOCO-per-photo-intake-20261023/.local/integrated-final-readonly-audit-20261023-final/`의 `independent-summary.json`, `physical-db-audit.json`, `external-call-audit.json`, `attempt-selection.json`과 각 사례별 감사다. 종료 소스 대조는 `.local/integrated-final-source-end-20261023/application-source-audit.json`이다. 재현 도구는 `tests/audit_application_manifest.py`, `tests/audit_integrated_campaigns.py`, 통제된 trace 장애 도구는 `tests/trace_storage_failure_replay.py`다.

이 결과는 선언한 115개 기대값과 선택한 12개 조합의 보존·출력 증거다. 가능한 모든 자연어·사진 조합의 정확성을 보증하지 않는다. 이후 최신 main UI 병합의 별도 실제 UI 사례, 새 Luna 사진 관찰 기능, Excel의 개발용 출처 접두사 표시는 각각 후속 소스와 별도 검증으로 보고해야 한다. 이 12개를 후속 사진 vision 기능의 E2E 통과로 세지 않는다.
