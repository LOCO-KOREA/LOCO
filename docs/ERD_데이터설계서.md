# ERD · 데이터 설계서

> 문서 ID ERGO-DATA-001 · 설계 버전 2.0 · 개정일 2026-10-16 · 완성 목표 2026-10-23(Asia/Seoul)

## 1. 저장 원칙과 논리 관계

SQLite의 기존 여섯 테이블과 JSON TEXT 컬럼을 유지한다. 물리 migration·추가 테이블·trigger·외래키를 도입하지 않는다. API DTO 2.0은 JSON과 조회 조합으로 표현한다. 상자 들기도 같은 GENERAL_TASK·가변 사진 구조다.

~~~mermaid
erDiagram
  SURVEY ||--o{ TASK : contains
  TASK ||--o{ PHOTO : registers
  TASK ||--o{ ANALYSIS : snapshots
  SURVEY ||--o{ EXPORT_LOG : exports
  APP_SETTINGS ||--o{ ANALYSIS : copied_into_snapshot
~~~

선은 서비스가 관리하는 논리 관계이며 실제 FK가 아니다. ANALYSIS에 복사된 설정은 APP_SETTINGS의 변경을 따라가지 않는다. PHOTO는 원본 파일 경로·메타를 저장하고 이미지 바이트는 DB에 넣지 않는다.

## 2. 물리 테이블·컬럼

| 테이블 | 컬럼 | 의미 |
|---|---|---|
| SURVEY | survey_id INTEGER PK, metadata_revision INTEGER, metadata_json TEXT, review_json TEXT, created_at TEXT, updated_at TEXT | 조사 정보·검토 이력 |
| TASK | task_id INTEGER PK, survey_id INTEGER, input_revision INTEGER, latest_analysis_id INTEGER nullable, input_json TEXT, created_at TEXT, updated_at TEXT | 현재 편집 입력·최신 분석 포인터 |
| PHOTO | photo_id INTEGER PK, task_id INTEGER, metadata_json TEXT | 등록 사진 정보 |
| ANALYSIS | analysis_id INTEGER PK, task_id INTEGER, input_revision INTEGER, status TEXT, snapshot_json TEXT, result_json TEXT, created_at TEXT, finished_at TEXT nullable | 분석 시점 입력과 계산/표시 결과 |
| APP_SETTINGS | settings_id INTEGER PK, settings_json TEXT | settings_id=1의 앱 설정 |
| EXPORT_LOG | export_id INTEGER PK, survey_id INTEGER, file_path TEXT, snapshot_json TEXT, receipt_json TEXT, created_at TEXT | 출력 당시 데이터와 영수증 |

ID는 양의 정수, 시각은 UTC ISO8601이다. UI·Excel은 Asia/Seoul로 표시한다. schema_version/report_version/module_states/비교/AI 이력을 위한 새 컬럼을 만들지 않는다. currentness·review_current·설명 현재성은 조회 때 계산한다.

## 3. JSON 매핑

### SURVEY

metadata_json은 SurveyDraft의 최초/정기/수시 유형·수시 사유·이전 조사일, 작업장 상황의 설비/작업량/속도/업무형태 변화, 근로자 참여기록, 증상조사 방법·익명 응답·요약을 저장한다. 응답 이름은 선택사항이며 익명 코드를 권장한다. 건강 관련 정보는 로컬 SQLite와 내보낸 파일에 평문으로 포함될 수 있으므로 파일 접근을 제한해야 한다. review_json은 reviewed, reviewed_analysis_ids, reviewed_metadata_revision, reviewer, reviewed_at, note와 선택적 history다. history는 이전 검토 기록과 archived_at·무효화/변경 사유를 보존하며 기존 history 없는 자료도 읽는다. 메타 변경은 metadata_revision을 올리고 현재 검토 표시를 해제한다.

### TASK.input_json

API의 TaskInput 전체를 저장한다. schema_version='2.0', task_kind='GENERAL_TASK', task_name, input_template, worker_count, conditions, legal, capture, manual, analysis_scope, legacy_input이다.

| JSON 영역 | 내용 |
|---|---|
| conditions | 작업자 코드·방법·자세·작업 높이·하루 시간·강도/빈도 자기평가·유해요인/원인·개선 제안·일회성·예정 개월·연간 일수·근거 |
| legal.criteria | criterion_no 1~11을 각각 한 번; 공통 질적 확인과 기준별 조건 |
| legal.exposures | 1~5호의 ExposureCode 15종 직접시간·근거 |
| 기준 6~11 | 조건별 rows·rows_complete·적격 행 row_ids·중복 제거 union 또는 9호 totals |
| capture | GENERAL_STILLS_V1, 가변 slots의 안정적 slot_no·photo_id·분석대상·촬영조건·관찰 하중 |
| manual | slot_no/photo_id/scope/field/value/source/evidence |
| analysis_scope | judgment=true, pose/tags/reba 선택 |
| legacy_input | 신규 null; 이전 TASK.input_json 원문 전체를 변환하지 않은 보존본 |

6/7/10/11호 union.value의 단위는 min/day, 8호는 count/day, 9호 totals는 위치별/합집합 count/day다. 서로 다른 조건 행의 중량·횟수·시간을 분리해 보존한다. 15종 시간에 6/7/10/11호 시간을 중복 저장하지 않는다.

### PHOTO.metadata_json

PhotoInfo 중 ID와 task_id를 제외한 file_path, file_name, width_px, height_px, consent, notes다. 사진 등록과 분석대상 배정은 별개다. 하나의 등록 photo_id를 여러 슬롯에 중복 배정하면 중복 관찰로 진단한다. 파일 내용 동일성은 경로만으로 증명하지 않는다.

### ANALYSIS.snapshot_json

TaskSnapshot 전체를 깊은 복사한다. TaskInput 2.0과 task_id, input_revision, photos, AnalysisSettings를 포함한다. 촬영 프로토콜·관찰 하중·수동값·규칙·모델/전처리 버전·기술태그 숫자 설정까지 고정한다. 원본 이미지 바이트는 복사하지 않는다.

입력·설정이 바뀌어도 snapshot을 수정하지 않는다. 파일이 사라져도 저장한 좌표·계산 결과는 읽을 수 있으나 원본 사진 재추론·이미지 재출력은 불가능할 수 있다. 이 한계를 결과/출력에 표시한다.

### ANALYSIS.result_json

2.0에서는 module_states, pose, slot_tags, tags, reba, judgment, ai, notes를 저장한다. 분석 ID·task_id·revision·status·시각은 컬럼과 snapshot에서 조합한다.

| 구역 | 보존할 내용 |
|---|---|
| pose | 대상 N의 사진별 상태·17관절·각도·진단 |
| tags | 사진별 기술태그와 yes/observed 수·표본 비율 |
| reba | 후보·관찰 하중·좌우 구성점수·누락·사진 총점·집계·대표 선택 |
| judgment | 11개 계산 초안·비교값·누락·해석·출처·별도 조사자 결론 |
| ai | 생성별 text_id·목적·is_active·생성/편집/적용본·content·입력 NumericSummary·모델/프롬프트 버전·시각·대체 이유 |
| module_states/notes | 요청별 상태와 계산/파일/설명 진단 |

결과가 없으면 null 또는 계약상 빈 배열로 표현하고 미요청/미계산 상태를 함께 저장한다. empty 배열 자체를 계산 완료로 해석하지 않는다. API 키·원본 사진·좌표의 GPT 전송용 복사본은 저장하지 않는다. GPT에 보낸 NumericSummary에는 자유입력 근거·이름·내부 ID·사용자 행 label도 없다. ai 배열은 생성마다 추가하며 편집/적용은 text_id로 지정한다. 같은 목적에서 적용된 활성 레코드만 is_active=true다. 이전 적용문과 그 입력 요약을 함께 보존한다.

계산 완료와 AI 편집은 서로 소유한 JSON 키만 바꾼다. 오래된 전체 result_json으로 다른 결과를 덮어쓰지 않는다. judgment의 조사자 결론과 reba의 대표 선택처럼 같은 하위 객체를 공유하는 경우에도 기존 값을 트랜잭션 안에서 다시 읽어 해당 경로만 갱신한다.

### APP_SETTINGS.settings_json

analysis 설정, gpt_enabled, gpt_model, ui{loco_visible,loco_mode}를 저장한다. gpt_key_present는 Python 환경에서 파생하며 키 자체는 DB에 저장하지 않는다. ui 기본값은 true/normal이다. 분석 설정은 snapshot에 복사하고 이후 변경을 소급하지 않는다.

### EXPORT_LOG

snapshot_json은 ExportSnapshot 2.0 전체다. survey, 모든 현존 tasks, 작업별 선택 analyses, unanalysed_task_ids, include_representative, comparison_specs, comparison_analyses, exported_at, schema_version/report_version을 담는다.

비교 대상은 같은 조사의 서로 다른 분석이며 일반 출력의 “한 작업 한 분석” 선택과 별도로 복사한다. 같은 작업의 과거/현재 비교에서도 두 snapshot이 빠지지 않는다. 출력 파일을 나중에 삭제해도 로그의 수치 근거는 남으며 파일 존재를 보증하지 않는다.

receipt_json은 report_version, sheets, reviewed, review_current, has_incomplete, has_stale, survey_input_complete다. 나머지 ExportReceipt의 ID·경로·시각은 컬럼에서 구성한다. 미리보기는 파일과 EXPORT_LOG를 만들지 않는다. 출력 시점 snapshot을 기준으로 공식 서식 구성 시트와 보조 시트를 만들고 증상조사표는 익명 응답이 있을 때만 추가한다.

## 4. 불변성·현재성·트랜잭션

- 시작 시 TASK 입력·PHOTO 메타·설정을 읽어 ANALYSIS snapshot을 만들고 latest_analysis_id를 설정한다.
- input_revision 변경은 한 사용자 입력 저장에서 한 번이다. 조사 메타 변경은 별도 metadata_revision이다.
- CURRENT는 현재 task revision과 분석 revision, latest_analysis_id가 모두 일치할 때다. 과거 분석 완료가 최신 포인터를 되돌리지 않는다.
- 검토 현재성은 선택 분석 ID 집합·metadata_revision·CURRENT에 묶인다. 결론 변경과 전체 reviewed=false는 원자적으로 저장한다.
- 같은 사진 경로 재연결은 관찰·수동값을 보존한다. 다른 photo_id 교체는 해당 값만 제거한다.
- 사진 삭제는 배정 해제·관찰/수동값 제거·PHOTO 삭제를 함께 처리하고 현재 입력이 바뀐 경우 revision을 한 번 올린다.
- 조사/작업 삭제는 서비스가 관련 행을 함께 지운다. 원본 사진 파일은 삭제하지 않는다. 지연 완료는 삭제된 ANALYSIS를 다시 만들지 않는다.

## 5. 1.3 호환 읽기

schema_version이 1.3인 기존 TASK·ANALYSIS·EXPORT_LOG를 일괄 재작성하지 않는다. 구체 타입은 API 계약서 §10과 legacy-compatibility.md의 읽기 계약을 따른다. 과거 15슬롯·회차·사건 하중은 당시 의미로 읽고 이전 형식임을 표시한다.

get_task는 메모리상 편집 DTO 2.0과 source_schema_version을 반환한다. 사진·알려진 수동값을 보존하고 사건명은 역사적 사진 label로 남긴다. 기존 중량/시간의 관련값은 조건 행으로 옮기되 새로운 망라성·측면 확인·실제 사진 하중을 추정하지 않는다. 이전 TASK.input_json 전체는 legacy_input에 보존한다. C4_TRUNK_EXT는 새 법령 입력에 포함하지 않는다. 사진 비율 등 환산값은 새 직접수치에 null을 넣고 이전 원문·변환 출처·진단으로 남겨 재확인한다.

명시 저장 때 TASK.input_json만 2.0으로 바꾸고 revision을 올린다. 새 분석·출력은 2.0이며 과거 분석/출력 snapshot은 불변이다. 새 분석에 과거 조사자 결론·AI 적용문·검토를 자동 승계하지 않는다.

## 6. 확인할 데이터 반례

혼합 중량 행의 분리, null/0, row_ids 누락/중복, 0개 사진 상태, 같은 사진 재연결, 새 사진 교체, 계산 중 AI 편집, 삭제 후 늦은 완료, 과거 분석을 포함한 전후 출력, 과거 1.3 열람 후 취소가 원본을 변경하지 않는지 확인한다. 물리 스키마가 같다는 사실만으로 데이터 호환 완료를 주장하지 않는다.

## TASK 선택 JSON 확장 (2026-10-22)

`TASK.input_json.conditions.intake_session`은 선택 보조 JSON이며 기존 여섯 테이블과 컬럼은 바꾸지 않는다. 값/단위/대상 조건/출처/근거/상태와 질문 문맥을 저장한다. 실제 값은 기존 legal·capture·manual·conditions에 함께 반영한다. 세부 DTO는 [적응형 계약](adaptive-intake.md)을 따른다. 이전 자료에는 이 키가 없어도 된다.

`intake_session.last_ai`는 실제 마지막 요청의 상태·모델·응답 ID·진단을 담는 선택 객체다. 이전 자료에는 없을 수 있으며 설정 존재와 응답 성공을 구분한다. 인증정보는 포함하지 않는다.

AI 입력 정리·후속 질문·설명 생성은 공통 설정 계약(`ergo/ai_config.py`, API 계약서 §6)을 공유한다. 모델·추론 강도·요청 시간·토큰 한도는 변수이며, 두 설정 화면도 서버 필드 정의로 렌더링한다. APP_SETTINGS의 기존 JSON에 저장하며 테이블·이전 분석 snapshot은 추가/변경하지 않는다.

## MediaPipe 자세 엔진 개정 (2026-10-22)

자세 엔진·설정·출력의 현행 계약은 [자세 엔진 계약](pose-engine.md)을 따른다. MoveNet 고정 입력/관절/해시 표기는 이전 엔진에 해당한다. 기본 엔진은 MediaPipe Heavy(33점), Full은 비교/선택 가능하며 과거 MoveNet snapshot의 의미는 보존한다. 설정과 프론트는 공통 registry를 소비하고 REBA/11개 계산은 기존 규칙을 유지한다. world_points/3D 분절각은 별도 추정 후보이며 점수에 자동 혼합하지 않는다.

### PDF 출력 영수증 JSON (2026-10-22 개정안)

기존 EXPORT_LOG 테이블을 그대로 쓴다. receipt_json에 format:'PDF', template_version, template_sha256, page_count, task_ids, analysis_ids, warnings와 기존 상태 필드를 저장한다. snapshot_json에는 선택한 Task/분석과 출력 시점 조사 메타를 저장한다. format이 없는 기존 영수증은 Excel이며 기존 sheets 필드는 보존한다. PDF 영수증은 페이지를 sheets라고 저장하지 않는다. 새 테이블·열·trigger·물리 migration 없이 새 출력 행만 추가한다.

PDF 이력은 같은 저장 트랜잭션에서 대상 조사 존재·created_at을 확인한 뒤 추가한다. 기존 Excel 호출의 동작/저장 행은 변경하지 않는다. 서버 생성시각의 수명별 구분을 이용하며 물리 migration은 없다.

### 하루 시간 합산 정정 (2026-10-22)

2026-10-23: 같은 선택 JSON fact.calculation에 검증한 피연산자 원문·분 값·합계를 저장한다. 복합 단위 정규화 근거의 operation은 `NORMALIZE_STATED_DURATION`이다. 실제 사용자 원문은 기존 messages에 유지하며 기존 여섯 테이블·컬럼과 과거 분석/출력 snapshot은 재작성하지 않는다. AI 응답 객체와 정규화한 저장 객체의 구분은 [적응형 계약](adaptive-intake.md)을 따른다.

intake fact의 선택 calculation 객체에 연산·단위·피연산 원문과 분 값·합계를 저장한다. 기존 TASK.input_json과 불변 snapshot JSON의 확장이며 여섯 테이블은 유지한다. 자세한 근거 검증과 예외는 [적응형 추가 확인 계약](adaptive-intake.md)의 작업별 시간 합산 절을 따른다.


## 입력 저장 감사 7건 정정 (2026-10-23)

기존 TASK.input_json.conditions.intake_session의 messages에 선택 message_id, turns에 회차별 requests/decisions/decision_history를 추가한다. 응답의 history/diagnostics는 같은 JSON에서 계산한다. 새 테이블·열·물리 migration 없이 과거 snapshot을 보존한다. 저장 전 초안은 DB 경로와 레코드 생성시각으로 구분한 Electron localStorage에 따로 보관한다. JSON 상세는 [저장 계약](storage-persistence.md)을 따른다.


## 실호출 입력·출력 대조 정정 (2026-10-23)

AI 응답 answers의 target/condition/number/text/quote와 DB TaskInput은 바깥 형태가 다르지만, 공통 catalogue destination으로 연결한다. 기존 facts/messages/turns 및 TaskInput→AnalysisSnapshot→ExportSnapshot의 JSON 값·조건·단위·출처 보존을 검증한다. 여섯 테이블·물리 스키마와 과거 snapshot은 바꾸지 않는다. 상세는 [저장·출력 보존 계약](storage-persistence.md)을 따른다.
### 실호출 조회·경합 정정

기존 TASK JSON의 intake_session.turns에 선택 rebased_from_revision과 사진 문맥 확인 진단을 보존한다. 파생 별칭과 무하중 손잡이 근거는 읽을 때 재생성하지 않는다. DB·분석·출력의 공통 TaskInput을 실제 JSON과 Excel 셀로 대조한다. 테이블·열·migration 추가는 없다. [저장 계약](storage-persistence.md) 참조.


2026-10-23 최신 main 통합: 중복 질문·용어 표시 수정은 기존 여섯 테이블/JSON 계약을 사용하며 물리 스키마 변경이 없다. 사진 하중 별칭은 계산 시 공통 해석하고 조회로 fact/revision을 만들지 않는다. 과거 분석·출력 snapshot과 사용자 원문은 보존한다. [점검 기록](verification/2026-10-23-main-no-repeat.md) 참조.

## 실제 원문 인용과 반 시간 경계 정정 (2026-10-23)

물리 스키마는 바꾸지 않는다. 기존 intake facts.quote에는 검증된 실제 연속 원문을, requests.answers.quote와 decisions.quote에는 원본 모델 인용을 보존한다. source_message_ids도 동일한 문장 검증으로 원래 메시지와 연결한다. 과거 행·snapshot을 재작성하지 않는다. 자세한 허용/거절 경계는 [추가 확인 계약](adaptive-intake.md#원문-문장-인용과-반-시간-경계-2026-10-23)을 따른다.

## 명시적 모름 표현 보존 정정 (2026-10-23)

자연어의 명시적 모름은 grounding.UNKNOWN_POLICY/unknown_evidence에서 공통 검증한다. "모릅니다"·"몰라요"·"알 수 없어요"·"미확인/확인 불가" 등은 UNKNOWN으로 보존하며 부정문이나 무관한 표현은 모름 근거로 사용하지 않는다. 숫자 0·무하중·NO를 대신 넣지 않는다. 원본 제안/출처, USER 우선권, 지연 재조정, 기존 snapshot은 보존한다. 자세한 표현과 반례는 [모름 표현 검증](verification/2026-10-23-unknown-evidence.md)을 따른다.


## 추가 질문 최소화 (2026-10-23)

계산기가 이미 완료한 범위의 작업 특징은 후보와 묶음 서식 모두에서 제외한다. 원래 미확인 값을 NO로 저장하지 않는다. 작업 설명을 먼저 보이는 답변 칸에서 한 번에 정리하고, 개별 수정은 접힌 영역에서 제공한다. 화면에 열거된 남은 작업 특징은 사용자가 명시적으로 한 번 확인하여 NO로 저장할 수 있다. 먼저 작성 중 설명과 직접 선택을 저장하며 새로 알려진 YES, 이전 USER 모름, 이미 확인된 값은 일괄 확인으로 덮지 않는다.

공통 intake POLICY.optional_photo_destinations는 사진 점수를 더 보완할 때의 항목을 정의하고 form_prompt_limit은 한 자연어 안내에 나열할 항목 수를 정의한다. 사진의 미확정 보완 항목만 남으면 기본 팝업을 강제하지 않고, 사용자가 선택해 더 확인할 수 있다. 해당 값은 미확인으로 보존하고 REBA 미완성/현재 정보 출력의 기존 의미를 유지한다. 작업 정보가 충분하거나 사용자가 모른다고 확인한 뒤에는 빈 단계를 건너뛴다. 미전송 설명/직접 수정은 결과 이동 전에 저장한다.

회귀는 test_question_minimization.py와 frontend-question-minimization.cjs에서 계산 완료 시 9개→0개, 남은 특징 한 번 확인, USER 모름/직접 YES 보호, 미전송 설명 우선 처리와 실패 보존을 검사한다. 실제 질문 수는 저장 필드 수 또는 접힌 사진 보완 수와 구분하여 사용자 답변 동작으로 검증한다.

## 질문 전 원문 교차확인 (2026-10-23)

새 자연어를 저장한 회차는 질문을 보여 주기 전에 FOLLOWUP 원문 교차확인을 한 번 수행한다. 다른 유효 질문이 있어도 앞선 제안·거절사유·현재 사실·원문 당시 사진 범위를 대조하여 빠진 명시 사실을 추가한다. 조회/중복 읽기, 직접 선택 답변만의 저장, plan=false에는 추가 호출하지 않는다. 기존 원문 검증·USER 우선권·지연 재조정·불변 snapshot을 유지하며 만료 조건을 추가하지 않는다. 상세 계약은 [원문 교차확인](verification/2026-10-23-source-coverage.md)을 따른다.


## 사진별 관측값 소유권 (2026-10-23)

사진 자세 값은 같은 원본 사진·신체 부위에만 적용한다. `manual.<scope>.<field>@photo:<photo_id>`가 정식 식별자이며 `photo_id`, 사진 방향, 원래 각도·신뢰도·측정 정책·엔진 근거를 함께 보존한다. 대표가 아닌 사진에서 읽은 값도 저장하지만 대표 사진의 빈 자세를 대신 채우지 않는다. 같은 사진에서 이미 확인한 값과 직접 모름으로 남긴 값은 다시 묻지 않는다. 남은 질문·묶음 서식에는 ‘왼쪽에서 찍은 사진 · 오른팔’처럼 사진 방향과 신체 부위를 표시하고 내부 식별자는 노출하지 않는다.

기존 `@default` 자세 값은 당시 대표 사진에만 연결하는 호환 별칭이다. 이미 저장된 사진별 USER 값·모름을 옛 자동 추정 별칭으로 덮지 않는다. 사진 교체·삭제 시 다른 사진의 사용자 값과 원문·시각을 보존하고 제거된 사진 값은 현재 계산에 투영하지 않는다. 동일 원본·모델 설정·근거를 반복 조회하거나 재시작하면 저장 JSON·revision·근거 시각은 변하지 않는다.

정면·후면의 몸통·목 기울임과 팔 벌림 관측은 원래 사진·신체 좌우별로 보존한다. 한쪽 팔의 최대 각도를 양팔에 복사하지 않으며 확실한 양성 측정만 자동 변환한다. 낮은 신뢰도·점수 경계·손 가림·손바닥 방향 불명확은 확인 대상으로 남긴다. 참고용 목 각도와 추정 3D 좌표는 기존 REBA 확정값으로 승격하지 않는다. 하루 시간·하중 추정, 대표 사진 선택, 양팔 REBA 완성·최댓값 계산은 유지한다.

기존 여섯 테이블과 TaskInput 2.0을 유지한다. `TASK.conditions.intake_session`의 선택 `photo_observations`와 fact 소유권·근거 메타데이터로 저장하며 물리 migration은 없다. 분석·출력 snapshot은 불변이고 Excel 입력 근거는 각 행의 실제 사진 식별자로 조회한다. 같은 범주값인 두 사진도 각자의 각도·인용을 유지한다. 세부 계약과 검증 한계는 [사진별 검증](verification/2026-10-23-photo-ownership.md)을 따른다.
