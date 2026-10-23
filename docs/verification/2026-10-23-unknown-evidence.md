# 명시적 모름 표현의 실제 응답 거절 정정

독립 `fix/quote-grounding-20261023`의 인용/시간 정정 `9e1dced` 위에서 수행한 보완이다. 실행 중인 root `696f457` 실호출 소스는 변경하지 않았다. 새 외부 AI 호출·PR·push·main 병합·마우스/키보드 조작은 수행하지 않았다.

실제 07 원문 “사진 물건과 두 중량의 연결은 모릅니다.”에 Luna는 EXTRACT_AND_PLAN/FOLLOWUP 모두 `load_link=UNKNOWN`을 제안했다. 원문 인용은 정확했으나 기존 `모르|모름|알 수 없|미확인` 정규식이 “모릅니다”를 찾지 못하여 `EMPTY_VALUE`로 거절했다. 선택형 load_link의 별도 제한이 원인은 아니다.

`grounding.UNKNOWN_POLICY`와 순수 함수 `unknown_evidence`로 명시적 모름의 한국어 표현을 모듈화했다. “모릅니다/모르겠습니다/몰라요/모름으로 기록”, “알 수 없음/알지 못함”, “미확인/미측정/확인 불가”, “기억이 안 남” 등을 읽는다. 국소 부정 경계를 두어 “모르지 않아요”, “알 수 없는 건 아닙니다”, “미확인 항목은 없어요”와 무관한 긍정 사실을 모름으로 저장하지 않는다. “방안 모릅니다”의 안은 부정어가 아니므로 단어 경계도 구분한다. 원래 AI 인용에 표현이 있어야 하며 복원된 중간 문장에서 근거를 빌리지 않는다.

유효한 모름은 기존 계약대로 `value=null,state=UNKNOWN,source=USER,origin=AI`로 저장한다. 물건 무게 0, 작업 없음, 무하중을 뜻하지 않는다. USER 우선권·과거 원문 stale 처리·사진 소유권·늦은 응답 재조정·과거 snapshot 불변성과 여섯 테이블/API 키는 유지한다. 모든 한국어 의미 해석이나 모델의 대상 배분을 일반 보증하지 않는다.

검증한 기록의 UNKNOWN 인용에는 07 “모릅니다”(수리), 09 “모르겠어요”(기존 정상), “양손 손잡이는 잡기 좋아요”(명시 모름 근거가 없어 거절 유지)가 있었다. 기록에 없는 표현은 회귀 시험의 합성 문장으로 구분한다.

- `tests/test_intake_unknown.py`의 7개 시험에서 긍정 29표현, 부정/무관 29표현과 인용 부재·중간 문맥·CURRENT/PRIOR·USER·늦은 응답·사진 소유권을 검증했다. “모르겠다는 뜻은 아니에요/미확인이라는 뜻은 아닙니다”처럼 어미·명사화 부정을 조합한 반례도 거절한다. 모름과 0을 구분하며 같은 연결 질문을 재질문하지 않는다.
- 실제 07 기록의 두 원래 응답은 `tests/fixtures/intake-recorded-unknown-20261023.json`에 보존했다. 실제 서비스와 격리 SQLite 재생에서 첫 제안은 ACCEPTED, 같은 후속 제안은 UNCHANGED가 되었고 원래 답변/response_id/출처 메시지 이력을 보존했다.
- 5kg·30kg 조건을 각각 유지하고 사진 하중은 UNKNOWN/None으로 남았다. DB 재시작·동일 경로 반복 조회에서 값/이력/revision이 유지되며 USER 편집 후 이전 분석 snapshot은 불변이다.
- 지속 산출물 `.local/recorded-unknown-replay-20261023/receipt.json`, `loco.db`, `01-first-replay.json`, `02-restored.json`, `03-analysis.json`, `04-excel-cells.json`, `report.xlsx`를 남겼다. Excel `입력한 값`의 사진 하중은 “모름”이며 0으로 대체하지 않는다. 사진만 소유 합성 PNG/빈 preview로 통제했으며 새 Luna 호출이 아니다.
- 공식 MoveNet/MediaPipe Heavy·Full 모델·공개 사진을 포함한 전체 Python 시험 **354개, skip 0, OK**. 로그는 `.local/unknown-evidence-python-suite.log`다. 마지막 표현 경계 보완 후 입력 관련 회귀도 별도 실행했다.

최종 통합 소스의 새 실제 Luna 호출은 root 캠페인에서 별도 수행한다. 원시 응답 재생을 새 실호출로 보고하지 않는다.
