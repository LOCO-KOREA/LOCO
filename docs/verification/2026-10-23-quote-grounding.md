# 실제 Luna 인용·시간 어휘 거절 정정

기준 HEAD는 `d98ad3f5afec904c1edb875e1266467241a8a5ce`이며 별도 `fix/quote-grounding-20261023` 작업 복사본에서 수정했다. 새 외부 AI 호출·Electron UI 조작·공유 DB 변경·PR·push·main 병합은 이 검증에 포함하지 않는다. 최신 main의 Excel/사진 크롭 코드는 변경하지 않았다.

## 확인한 실제 결함

| 기록된 실제 호출 | 원래 제안과 거절 | 정정 결과 |
| --- | --- | --- |
| `live-field-cases-20261023/08-zero-and-absent` | `UNLOADED`의 원문 두 문장 사이에 사진 설명이 있어 `QUOTE_NOT_IN_TEXT` | 같은 메시지의 완전한 문장·순서·별도 위치를 검증하고 실제 연속 근거를 저장한다. 원래 AI 인용/결정과 source_message_ids를 보존한다. |
| `live-posture-cases-20261023/11-preparation-posture` | 정확한 “각각 하루 3시간 반복” → 180분을 제안했으나 lexer가 “3시간 반”을 210분으로 읽어 거절 | `반` 뒤의 단어 경계를 검사하여 손목/손 각각 180분을 저장한다. |

원시 응답 중 테스트에 필요한 합성 시나리오 원문과 첫 AI 제안은 `tests/fixtures/intake-recorded-grounding-20261023.json`에 보관한다. 현재/과거 문맥과 USER·사진 소유권, 지연 재조정 계약은 유지한다. 중간 문장에서 새 수치나 모름 근거를 끌어오지 않는다.

## 수행한 검증

- 새 회귀 `tests/test_intake_evidence.py`: 정확/공백 인용, 떨어진 완전 문장, 소수점, 마지막 미종결 문장, 역순·재사용·의역·부정 삭제·부분 문장·메시지 간 합성 거절, 숫자/단위 근거, 중간 문맥, USER/과거/지연/사진 소유권을 검사한다.
- “한 시간 반이에요/동안”, “1시간반씩”, “2시간반을”, 반 시간 수량의 일부 인용을 검사한다. “반복/반대/반드시/반품/반도체/반응”은 30분을 추가하지 않는다.
- 기록된 실제 응답 두 건을 실제 Python 서비스와 격리 SQLite에서 재생했다. 08은 무하중·원래 제안·canonical 사실 근거·출처 메시지·재질문 제외·DB 재시작·동일 경로 반복 조회·분석 snapshot·Excel 셀을 대조했다. USER 변경 후 과거 snapshot 불변도 검사했다. 11은 손목/손 180분·노출 projection·출처를 대조했다.
- 별도 지속 산출물 `.local/recorded-grounding-replay-20261023/receipt.json`과 각 시나리오 `loco.db`, `01-first-replay.json`, `02-restored.json`, `03-analysis.json`, `04-excel-cells.json`, `report.xlsx`를 남겼다. 11의 Excel `입력한 값` 시트에서 두 항목 모두 `180 분/일`임을 확인했다. 사진 추론만 빈 preview/소유 합성 PNG로 통제했으며 새 AI 호출로 보고하지 않는다.
- 공식 MoveNet/MediaPipe Heavy·Full 모델과 공개 사진 fixture를 준비한 전체 Python 시험: **347개, 모두 통과, skip 0**. 로그는 `.local/quote-grounding-python-suite-with-models.log`다. 로그의 start 실패/잘못된 입력 traceback은 해당 실패 경로를 주입한 시험이며 최종 판정은 `OK`다.

## 경계

수치 검증은 모델이 실제로 인용한 숫자·단위와 허용 연산을 검사한다. 작업별 의미 배분 전체를 일반적으로 보증하지 않으며 최종 실제 호출·앱 E2E는 통합 후보에서 별도로 다시 수행한다.

독립 audit의 07 DB를 다른 작업 경로로 복제하면 동일 모델 SHA라도 현재 모델 fingerprint에 절대 경로가 포함되어 한 번 재측정될 수 있다. 이때 POSE fact.updated_at·manual evidence.observed_at·입력 revision이 바뀔 수 있다. 같은 경로의 단순 재조회 변이와 구분하며 이번 정정에서 fingerprint 계약/호환은 바꾸지 않는다. USER 값과 기존 snapshot은 바꾸지 않는다.
