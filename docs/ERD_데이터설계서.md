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

metadata_json은 SurveyDraft의 최초/정기/수시 유형·수시 사유·이전 조사일, 작업장 상황의 설비/작업량/속도/업무형태 변화, 근로자 참여기록, 증상조사 방법·익명 응답·요약을 저장한다. 응답 이름은 선택사항이며 익명 코드를 권장한다. 건강 관련 정보는 로컬 SQLite와 내보낸 파일에 평문으로 포함될 수 있으므로 파일 접근을 제한해야 한다. review_json은 reviewed, reviewed_analysis_ids, reviewed_metadata_revision, reviewer, reviewed_at, note다. 메타 변경은 metadata_revision을 올리고 현재 검토 표시를 해제한다.

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

receipt_json은 report_version, sheets, reviewed, review_current, has_incomplete, has_stale, survey_input_complete다. 나머지 ExportReceipt의 ID·경로·시각은 컬럼에서 구성한다. 미리보기는 파일과 EXPORT_LOG를 만들지 않는다. 출력 시점 snapshot을 기준으로 기본 4시트를 만들고 질환자 발생에 따른 수시조사에 별지 1·2 기반 시트를 조건부로 추가한다.

## 4. 불변성·현재성·트랜잭션

- 시작 시 TASK 입력·PHOTO 메타·설정을 읽어 ANALYSIS snapshot을 만들고 latest_analysis_id를 설정한다.
- input_revision 변경은 한 사용자 입력 저장에서 한 번이다. 조사 메타 변경은 별도 metadata_revision이다.
- CURRENT는 현재 task revision과 분석 revision, latest_analysis_id가 모두 일치할 때다. 과거 분석 완료가 최신 포인터를 되돌리지 않는다.
- 검토 현재성은 선택 분석 ID 집합·metadata_revision·CURRENT에 묶인다. 결론 변경과 전체 reviewed=false는 원자적으로 저장한다.
- 같은 사진 경로 재연결은 관찰·수동값을 보존한다. 다른 photo_id 교체는 해당 값만 제거한다.
- 사진 삭제는 배정 해제·관찰/수동값 제거·PHOTO 삭제를 함께 처리하고 현재 입력이 바뀐 경우 revision을 한 번 올린다.
- 조사/작업 삭제는 서비스가 관련 행을 함께 지운다. 원본 사진 파일은 삭제하지 않는다. 지연 완료는 삭제된 ANALYSIS를 다시 만들지 않는다.

## 5. 1.3 호환 읽기

schema_version이 1.3인 기존 TASK·ANALYSIS·EXPORT_LOG를 일괄 재작성하지 않는다. 구체 타입은 API 계약서의 고정 이전 계약을 따른다. 과거 15슬롯·회차·사건 하중은 당시 의미로 읽고 이전 형식임을 표시한다.

get_task는 메모리상 편집 DTO 2.0과 source_schema_version을 반환한다. 사진·알려진 수동값을 보존하고 사건명은 역사적 사진 label로 남긴다. 기존 중량/시간의 관련값은 조건 행으로 옮기되 새로운 망라성·측면 확인·실제 사진 하중을 추정하지 않는다. 이전 TASK.input_json 전체는 legacy_input에 보존한다. C4_TRUNK_EXT는 새 법령 입력에 포함하지 않는다. 사진 비율 등 환산값은 새 직접수치에 null을 넣고 이전 원문·변환 출처·진단으로 남겨 재확인한다.

명시 저장 때 TASK.input_json만 2.0으로 바꾸고 revision을 올린다. 새 분석·출력은 2.0이며 과거 분석/출력 snapshot은 불변이다. 새 분석에 과거 조사자 결론·AI 적용문·검토를 자동 승계하지 않는다.

## 6. 확인할 데이터 반례

혼합 중량 행의 분리, null/0, row_ids 누락/중복, 0개 사진 상태, 같은 사진 재연결, 새 사진 교체, 계산 중 AI 편집, 삭제 후 늦은 완료, 과거 분석을 포함한 전후 출력, 과거 1.3 열람 후 취소가 원본을 변경하지 않는지 확인한다. 물리 스키마가 같다는 사실만으로 데이터 호환 완료를 주장하지 않는다.
