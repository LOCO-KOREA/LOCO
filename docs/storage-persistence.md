# AI 입력·초안·처리 이력 저장 계약 · 2026-10-23

사용자가 보낸 문장과 저장 전 수정문은 구분하여 보존한다. 경과 시간이나 응답 도착 순서만으로 버리지 않는다. 새 분석 시작은 기존 조사 삭제가 아니다. 삭제는 선택한 기록의 명시적 삭제 동작으로만 수행한다. 운영 승인이나 배포 차단 기능을 추가하지 않는다.

## 저장 위치와 소유권

| 자료 | 저장 위치 | 확인 기준 |
|---|---|---|
| 보낸 원문·직접 답변 | SQLite `TASK.input_json.conditions.intake_session.messages` | 원문과 새 메시지별 `message_id` |
| 정리된 사실 | 같은 JSON의 `facts`, 기존 conditions/legal/capture/manual | 항목·조건·단위·출처·근거, USER 우선권 |
| AI 제안과 판단 | 같은 JSON의 `turns` | 회차 ID → 요청 phase/response_id → proposal_index/request_index → 결정 |
| 보내기 전 작업 설명·팝업 답변 | `frontend/drafts.js`의 DB별 `quick` 초안 | 초안 UUID, 조사/작업 ID와 생성시각 |
| 자동 저장 대기 중 직접 편집 | 같은 모듈의 `intake` 초안 | 작업 ID+생성시각, base/value/version |
| 아직 저장·적용하지 않은 설명 수정문 | 같은 모듈의 `explanation` 초안 | 분석 ID+생성시각, purpose, text_id+생성시각 |

LocalDrafts 키는 `DRAFT_POLICY.prefix`와 열린 DB 경로 및 종류로 구성한다. `get_database_info`로 현재 DB 범위를 확인한다. 임시 저장은 이 PC의 Electron 프로필 localStorage이며 다른 PC로 DB만 복사하면 함께 이동하지 않는다. SQLite에 저장된 값과 분석/출력 snapshot이 정본이다. 저장 실패/공간 부족/손상은 표시하며 손상된 bucket을 새 빈 객체로 덮지 않는다. v1 단일 초안은 호환해서 읽되 새 초안은 여러 건을 독립 보관한다. 보존 기간에 따른 삭제는 없다.

## 늦은 응답과 원문 문맥

`ergo/intake/history.py`는 순수 회차·문맥 모듈이다. 구조화한 수정 메시지와 자연어 문장을 먼저 분리한다. 기본 `POLICY.history_context_chars=None`은 저장된 모든 자연어 원문을 문맥에 포함한다. 한 항목을 추출했다고 같은 문장의 나머지 정보까지 처리 완료로 판단하지 않는다. 최근 회수나 경과 시간으로 원문을 만료시키지 않는다. 운영에서 명시적으로 글자 예산을 지정한 경우 요청별 포함/미포함 메시지 ID를 기록하고 미포함 안내를 표시하며, 원문은 삭제하지 않는다. 공급자의 요청 실패도 원문을 지우지 않는다.

네트워크 대기 중 DB 잠금을 유지하지 않는다. revision이 바뀐 동안 도착한 응답도 `RECONCILED` 회차로 현재 작업에 다시 병합한다. 비충돌 새 정보는 저장하고, 최신 직접 값·모름·수정된 값을 지키며 충돌 제안과 근거를 남긴다. 과거의 UNKNOWN 제안은 최신 확인값을 비우지 못한다. 과거 결정이 있으면 `decision_history`에 보존하고 현재 결정과 구별한다. 삭제·재생성된 다른 작업에 응답을 붙이거나 삭제 행을 복원하지 않는다. 시간 제한으로 제안을 폐기하는 유효기간은 없다.

## 회차·진단 DTO

응답의 `history`는 기존 JSON `turns`의 사본, `diagnostics`는 아직 해결하지 않은 미반영 항목이다. `dropped`는 현재 회차의 호환 진단으로 유지한다. 회차는 `{turn_id,message_id,created_at,decided_at,input_revision,status,focus,requests,decisions,decision_history?}`다. 새 상태는 SAVED/REQUESTING/COMPLETE/ERROR/RECONCILED이며 이전 진단을 옮긴 LEGACY 회차도 읽는다.

요청은 `{phase,reason,connection,answers,questions,context}`다. 인증키는 저장하지 않는다. connection에는 실제 모델·추론 강도·응답 ID와 상태만 허용한다. EXTRACT_AND_PLAN과 FOLLOWUP 응답은 각각 보관한다. FOLLOWUP에서 발견한 새 제안도 같은 원문·단위·USER 우선 검증을 거쳐 반영/미반영 결정을 남긴다. 질문 단계라는 이유로 버리지 않는다. 반영 뒤 누락 후보를 다시 계산하여 이미 해결한 항목을 묻지 않는다. 같은 회차의 반복 제안으로 기존 CONFLICT를 해소하지 않으며 새 사용자 진술/직접 선택으로 확인한다. 과거 IGNORED/FOLLOWUP_ONLY 이력은 당시 처리 결과로 그대로 읽는다.

결정은 `{target,condition,proposal_index,request_index?,quote?,proposed_value?,outcome,reason,source_message_ids}`다. outcome은 ACCEPTED/UNCHANGED/REJECTED/USER_SAVED/IGNORED다. 미반영 사유는 숫자·단위 근거 불일치, 원문 부재, 최신 값 보존, 직접 값 우선, 충돌 등을 구분한다. 빈 후속 응답은 이전 미반영 진단을 지우지 않는다. 이후 해당 항목을 직접 고치거나 검증된 값으로 해결하면 활성 안내만 해소하며 이전 회차는 보존한다. 늦게 처리한 회차의 진단은 결정 순서에 따라 갱신한다.

## 저장 전 편집과 화면

숫자 입력은 입력 이벤트에서 먼저 로컬에 기록하고, 서버의 `autosave_delay_ms` 정책에 따라 SQLite에 저장한다. 화면은 로컬 임시 저장/서버 저장 중/저장 완료/실패를 구분한다. 재실행 시 같은 작업에서 DB 값이 base와 같으면 복구를 저장하고, 이미 value이면 성공 확인 후 대기 항목을 지운다. DB 값이 둘 다 아니면 임시값과 최신값을 함께 남겨 명시적으로 확인한다. 더 오래된 요청의 성공 응답으로 새로 입력한 수정문을 지우지 않는다. 제거된 항목의 대기값도 자동 폐기하지 않고 확인 대상으로 보존한다.

간편 설명과 고급 설명은 목적·이력별 수정문을 보관한다. 고급의 ‘수정본 저장’은 DB의 edited_text만 바꾸고 ‘저장한 수정문 적용’은 저장본을 적용한다. 간편의 ‘수정문 적용’은 수정본 저장 후 적용한다. 그 사이 새로 타이핑한 내용은 성공한 구문과 다르면 유지한다. 분석의 계산 snapshot은 설명 저장/적용으로 바뀌지 않는다.

## 범위와 검증

AUD-01/02/03/05/06/07/08의 회귀 기준은 `tests/test_intake_persistence.py`, `tests/frontend-storage-persistence.cjs`, `tests/storage-persistence-e2e.cjs`다. 기존 AUD-04 표현/시간 근거 정정은 유지한다. 실스택 시험은 별도 DB/프로필과 화면 밖·초점 불가 Electron을 사용한다. 루프백 모델 응답 검증과 실제 외부 Luna/xhigh 검증은 따로 기록하고 실제 Excel 셀과 SQLite 출력 snapshot도 대조한다.

이번 작업은 `feat/mediapipe-heavy`의 저장 수정이다. 최신 origin/main을 기준으로 통합할 때 Excel 기본 출력·사진 크롭·질문 묶음/진행률·수동 임시 저장/이어쓰기를 유지한다. 자동 미완성 초안과 수동 화면 임시 저장은 구별하며 동일 작업의 중복 카드는 숨긴다. 저장 계약에 필요한 변경만 추가하며 화면을 이전 feature 버전으로 교체하지 않는다. 통합 검증의 근거는 별도 기록한다. PR·push·main 병합·배포는 이번 검증의 완료 상태에 포함하지 않는다.


## 출력 값과 근거 (실호출 10회 후 정정)

`ergo/report/input_trace.py`는 선택된 snapshot의 공통 catalogue와 fact를 기준으로 출력 항목별 출처와 근거를 찾는다. 조건 행 전체의 대표 근거를 각 중량·횟수·시간에 복제하지 않는다. 값·조건·사진 소유권이 맞지 않거나 input_revision과 projected_revision이 다르면 과거 메타데이터로 새 값을 설명하지 않고 기존 입력 근거로 돌아간다. 과거 snapshot/DB 행은 재작성하지 않는다.

하루 전체 시간·연간 일수·일회성, 노출 0, 직접 모름/NO, 모든 조건 행 기록 여부도 입력한 값 시트에서 구별한다. AI 제안 DTO와 TaskInput의 바깥 구조는 서로 다르다. DB→분석→출력의 공통 TaskInput 필드와 target→destination→값/단위/조건→Excel cell 매핑의 일치로 보존성을 검증하며, schema_version 문자열만 같다고 통과시키지 않는다. 원문/응답/단계별 실제 DB/선택 snapshot/셀 기록을 갖춘 10회 시험과 수정 후 검증은 별도 증거로 보존한다.

## 조회와 경합 중 제출한 답변

이미 projection이 만든 별칭은 조회 때 새 사용자 fact로 만들지 않는다. 물건 없음에서 파생한 손잡이 `NOT_APPLICABLE`의 근거 시각도 근거가 된 fact 시각으로 고정한다. 조회만으로 값·근거·revision이 달라지지 않는다. 최초 작업명은 소수점(예: 12.5kg)을 문장 끝으로 자르지 않는다.

자연어만 제출한 요청의 expected_revision이 오래됐어도 원문을 먼저 보관하고 최신 상태에서 AI 정리를 진행한다. `rebased_from_revision`은 당시 클라이언트 revision을 회차에 남긴다. 최신 USER 값과 기존 확정값을 보호한다. 구조화한 직접 수정은 경합 시 `INPUT_CHANGED`로 응답하여 화면의 임시 수정값을 유지하며, 저장하지 않은 값을 성공으로 응답하지 않는다. 최초 자연어 저장의 낙관적 경합은 현재 소유 작업에서 재시도하며 원문을 중복 저장하지 않는다.

이미 전송한 AI 응답이 늦게 도착했을 때 사진 선택이 같으면 사진 제안도 정상 재검증한다. 사진 선택이 바뀌었거나 오래된 클라이언트의 사진 소유 문맥을 확인할 수 없으면 새 사진에 자동 연결하지 않는다. 원문·제안·`PHOTO_CONTEXT_CONFIRMATION_REQUIRED` 진단은 보관하고 전역 시간·일수 등 비충돌 값은 저장한다. 수명/사진 소유권 확인이며 시간 경과에 따른 폐기 규칙은 없다.


## 최신 main 통합과 재질문 방지 (2026-10-23)

최신 main의 Excel 출력·사진 크롭·공통 이동과 2단계 묶음 확인을 기준으로 MediaPipe 및 저장 보완만 추가한다. 이미 KNOWN인 값과 USER가 모름으로 확인한 항목은 새 질문/질문 묶음에 넣지 않는다. 간편 묶음 서식에서도 기본 추가 입력에서 제외하고 닫힌 ‘이미 확인한 정보 · 수정하기’에서만 수정한다. 조건별 행과 좌우 사진의 identity를 유지하며 한 조건의 답을 다른 조건에 복사하지 않는다. ESTIMATED·CONFLICT 및 새 사진에 연결되지 않은 정보는 확인할 수 있다.

사진과 같은 물건이라고 확인한 유일 중량은 photo_load의 공통 해석으로 계산과 질문에 함께 사용한다. 이 파생값을 새 사실로 저장하거나 조회 revision을 올리지 않는다. 여러 중량, 확인하지 않은 연결, 명시적인 모름·무하중·직접 중량은 구분한다. 자동 저장과 수동 임시 저장이 같은 작업을 가리키면 홈의 이어서 하기 카드는 하나로 묶으며, 내용이 다른 자동 보관본은 같은 카드 안에서 따로 연다. 별도 작업 초안은 보존한다.

사용자에게 보이는 시스템 용어는 frontend/user-language.json을 공통 사전으로 사용한다. 화면의 AI 본문·처리 상태·계산 근거 및 Excel 설명은 같은 뜻의 한국어로 표시한다. 과거 저장된 원문·직접 입력 근거·계산 코드·수치·단위·snapshot은 바꾸지 않는다. 새 AI 설명 지침에도 같은 사전을 제공하며 근거 참조 코드는 유지한다. 묶음 입력에서 미전송한 추가 설명은 다음 단계 저장과 함께 처리하고, 입력 단계와 수정 중 선택값은 초안 복원 대상이다.

검증 범위와 실제 호출 증거는 [최신 main 재질문 점검](verification/2026-10-23-main-no-repeat.md)에 기록한다. 외부 호출 없이 검사한 계약 조합과 실제 모델·앱·DB·Excel 실행은 구분한다.

## 수동 저장 시점과 자동 보관의 독립 복원

`quick-workspace-draft.js`가 소유권과 내용 비교 계약을 담당한다. 새 수동 checkpoint는 기존 version 1 구조에 선택 필드 `scope`(DB 경로), `draftId`(논리 초안 UUID)를 추가한다. 자동 quick 초안은 `id`(보관본 UUID), `ownerId`(논리 초안 UUID), `taskRevision`을 보관한다. 기존 version 1은 계속 읽으며 SQLite 여섯 테이블과 TaskInput/분석/Excel snapshot 형식은 바꾸지 않는다.

양쪽 모두 DB 작업이 있는 자료는 DB 범위와 조사·작업 ID 및 각각의 생성시각으로 같은 소유자인지 확인한다. 숫자 ID만 같거나 양쪽 ID가 없는 것은 같은 초안이라는 근거가 아니다. 사진 등록 전에는 UUID로 확인하므로 여러 미전송 설명이 모두 목록에 남으며, 첫 사진으로 DB 작업이 생겨도 같은 UUID의 이전 보관본을 연결할 수 있다. 새 checkpoint는 다른 DB의 복사본에 연결하지 않는다. DB 범위가 없는 과거 자료는 기존 조사·작업 생성시각 확인을 유지한다. `list_surveys`는 생성시각이 없는 요약 응답이므로 홈에서 보관본이 가리키는 조사만 별도 조회하여 생성시각을 확인한다. 확인하지 못한 소유권으로 다른 최근 기록을 숨기지 않는다.

수동 저장은 그 시점의 화면·원문·선택값을 복원한다. 수동 저장 이후에도 자동 보관을 계속한다. 수동 화면을 여는 render가 이후 미전송 내용을 덮지 않도록 같은 내용의 보관본은 재사용하고 다른 내용이면 별도 UUID로 자동 보관한다. 홈에서는 같은 소유자의 보관본을 한 카드 안에서 선택하며, 수동 저장 버튼의 ‘이어서 하기’는 계속 수동 저장 시점으로 돌아간다. 자동 보관 경로는 현재 DB 작업을 읽으므로 같은 원문이라도 카드 안에서 항상 접근할 수 있다. 수동 저장 후 DB 입력이 달라져 수동 화면을 열지 못하는 경우에도 자동 보관 내용은 열 수 있다. 텍스트·답변·서식 단계/선택값·사진·직접 값의 0/null을 비교하며, 내용 비교가 불가능한 자료를 같다고 간주하지 않는다. 다른 작업이나 DB의 초안을 지우지 않으며 명시적으로 카드의 ‘버리기’를 누르면 그 카드에 묶인 같은 소유자 보관본만 정리한다. 아무것도 작성하지 않은 새 분석에서 홈으로 돌아가도 이전의 의미 있는 수동 저장을 빈 화면으로 대체하지 않는다.

회귀 기준은 `tests/frontend-main-integration.cjs`의 사진 전 원문, 다른 DB/재사용 ID, 실제 render 이후 자동 보관 보존, 정확한 수동 복원, 같은 카드 내 다른 보관본 접근이다. `tests/storage-persistence-e2e.cjs`는 실제 화면 밖 Electron→Python→SQLite→MediaPipe→Excel을 사용하고 모델 HTTP만 결정된 루프백 응답으로 대체한다. 따라서 이 저장 회귀의 통과는 외부 Luna 호출의 정확성 증거와 구별한다.

## 비연속 원문 인용 보존 (2026-10-23)

같은 메시지의 완전한 문장들을 순서대로 복사한 인용은 공통 evidence_quote로 검증한다. fact.quote는 첫 문장부터 마지막 문장까지의 실제 연속 원문을 보존하고, 원래 모델 인용은 requests.answers.quote/decisions.quote에 그대로 남긴다. source_message_ids도 같은 규칙으로 찾는다. 중간 문장의 수치/모름을 원래 제안의 근거로 확장하지 않으며 USER 우선권·지연 응답 재조정·불변 snapshot은 유지한다. 반 시간 lexer는 “3시간 반복”을 210분으로 바꾸지 않는다. 물리 저장 구조와 메서드 키는 바꾸지 않는다.

과거 자동 초안에 `photos`와 intake session의 `views`가 모두 없으면 capture slot의 방향 코드 또는 한국어 사진 이름을 공통 `VIEWS`/`VIEW_LABEL`로 복원한다. 정면·후면 사진을 `UNKNOWN`/오른쪽으로 바꾸지 않고, 이름에 방향이 없으면 유효한 camera_side를 사용한다.
