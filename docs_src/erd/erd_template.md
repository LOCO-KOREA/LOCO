# ERD · 데이터 설계서

> 근골격계 유해요인조사 보조 앱 · 3단계 스키마 (외부 · 개념 · 내부)

## 문서 정보

| 항목 | 내용 |
|---|---|
| 문서 번호 | ERGO-DD-001 |
| 버전 | v0.1 (초안) |
| 작성일 | 2026-10-12 |
| 작성 | 한정욱 (데이터 담당) |
| 검토 | 김나리 · 유서하 · 정혁 |
| 상태 | 초안. 10/14 설계 1차에서 검토, 10/15 확정 |
| 상위 문서 | 기능정의서 v0.3 (ERGO-FD-001), requirements.md |
| 다음 문서 | API 계약서 (ERGO-API-001) |
| DBMS | SQLite 3.45 (Python 3.11 내장 sqlite3). 서버 없이 PC에 파일 하나 |
| 그림 원본 | `ERD.drawio` (draw.io로 열어 고칠 수 있음) · PNG는 `ERD_그림` 폴더 |
| 멘토 WBS | api-data-design.md의 '엑셀·저장 데이터' 부분 |

### 개정 이력

| 버전 | 날짜 | 바뀐 내용 |
|---|---|---|
| v0.1 | 2026-10-12 | 초안. 3단계 스키마, 데이터 표준, 테이블 {{N_TABLE}}개, 뷰 {{N_VIEW}}개, 인덱스 {{N_INDEX}}개, 트리거 {{N_TRIGGER}}개. SQLite에서 만들어 시험함. API 계약서와 대조해 GPT 뷰(거르기용 번호, 조사의 단위작업 수)와 수정 이력 동작 코드의 뜻을 맞춤 |
| v0.1 | 2026-10-12 | ERD를 그림으로: draw.io 파일 1개(5쪽)와 PNG 5장. 개념 ERD와 5.5절에서 ai_text의 두 부모를 '반드시 하나'로 적었던 것을 '없거나 하나'로 바로잡음 (외래키가 NULL 허용) |
| v0.1.1 | 2026-10-12 | 고시 제2020-12호 원문 대조 (국가법령정보센터 현행 본문): criterion.legal_text의 3호·6호를 원문대로 고침 (띄어쓰기만 다름, 나머지 9개는 일치). 작업 기간 구분 설명을 고시 제2조 표현으로 바꿈. 원문 사본과 시험은 프로젝트의 tests/test_law_text.py |

---

## 1. 이 문서가 정하는 것

- 데이터를 세 층으로 나눠 정한다 (ANSI/SPARC 3단계 스키마).
  - **외부 스키마**: 사용자와 응용 프로그램이 보는 모양. 화면, 엑셀, GPT가 각각 보는 뷰 (7절)
  - **개념 스키마**: 데이터 전체의 논리 구조. 엔티티, 속성, 관계, 무결성 규칙 (5절)
  - **내부 스키마**: 실제로 저장하는 방식. 테이블, 타입, 인덱스, 트리거, 파일 (6절)
- 설계 원칙
  1. **판정의 근거가 남는다.** 같은 입력이면 같은 결과가 나오고, 그 결과가 어떤 값으로 나왔는지 다시 보여 줄 수 있어야 한다 (NFR-004, NFR-005).
  2. **법 기준값은 출처와 함께 저장한다.** 각도 기준은 해설 값이 기본이고, 조사자가 바꾸면 사유가 남는다 (BR-06).
  3. **필요한 것만 저장한다.** 얼굴, 원본 영상, 관절 위치 원자료는 저장하지 않는다 (BR-22, 8절).
  4. **DB가 막을 수 있는 규칙은 DB가 막는다.** 값의 범위, 상태의 조합, 이력 보호는 CHECK, 외래키, 트리거로 건다. 앱 코드에 버그가 있어도 잘못된 데이터가 들어가지 않는다 (9절에서 시험).
  5. **PC 한 대, 파일 하나.** 백업과 이동은 파일 하나를 복사하면 된다.

---

## 2. 3단계 스키마 한눈에 보기

![3단계 스키마](ERD_그림/ERD_0_3단계_스키마.png)

| 층 | 무엇 | 이 프로젝트에서 | 누가 쓰나 |
|---|---|---|---|
| 외부 스키마 | 사용자·응용별로 필요한 부분만 보이는 모양 | 뷰 {{N_VIEW}}개 (조사 목록, 분석 결과, 판정표, 엑셀 시트, GPT 전송, 검증) | 화면, 엑셀 내보내기, GPT 어댑터 |
| 개념 스키마 | 조직 전체의 데이터 논리 구조. 하나만 있다 | 엔티티 {{N_TABLE}}개, 관계, 식별자, 정규화, 무결성 규칙 | 설계자, 모든 기능의 기준 |
| 내부 스키마 | 저장 장치에 어떻게 저장하나 | SQLite 파일, STRICT 테이블, 인덱스, 트리거, 저장 옵션 | DB 엔진 |

**데이터 독립성** (3단계로 나누는 이유)

- **논리적 독립성** (외부 ↔ 개념): 개념 스키마가 바뀌어도 뷰만 고치면 화면과 엑셀 코드는 그대로다. 예: 판정 근거를 `judgment_basis`로 나눠도 화면은 `v_judgment_sheet`만 읽으므로 영향이 없다.
- **물리적 독립성** (개념 ↔ 내부): 저장 방식이 바뀌어도 테이블 구조와 뷰는 그대로다. 예: 인덱스를 더하거나 `WITHOUT ROWID`로 바꿔도 테이블·뷰·앱 코드는 그대로다.

**데이터 모델링 단계와의 대응**

| 모델링 단계 | 하는 일 | 이 문서 |
|---|---|---|
| 개념적 모델링 | 주제 영역, 핵심 엔티티, 관계 | 5.1, 5.2 |
| 논리적 모델링 | 속성, 식별자, 관계의 카디널리티, 정규화 | 5.3 ~ 5.7 → 개념 스키마 |
| 물리적 모델링 | 테이블, 타입, 인덱스, 저장 옵션 | 6절 → 내부 스키마 |
| 뷰 설계 | 사용자별 보기 | 7절 → 외부 스키마 |

---

## 3. 데이터 요건 (기능정의서 → 저장할 정보)

| 기능 | 저장할 정보 | 엔티티 | 메모 |
|---|---|---|---|
| F01-01 | 조사개요, 수시 사유 | survey, survey_reason | 수시 사유는 여러 개라 따로 둠 |
| F01-02 | 모든 입력과 결과 (자동 저장) | 전체 | — |
| F01-03 | 다음 정기조사 예정일 | (저장 안 함) | 확정일 + 3년. 파생 속성이라 뷰에서 계산 |
| F02-01 | 단위작업, 작업 기간 구분 | unit_task | — |
| F02-02 | 하루 작업시간과 호별 입력값 | task_input, repetition_input, lift_position_input | 비어 있음(NULL) = '입력 필요' |
| F02-03 | 참여 근로자 | participant | 개인정보 |
| F03-01, F03-03 | 영상 정보, 촬영 동의 | video | 원본은 위치만 |
| F03-04 | 분석 실행과 상태 | analysis_run | 다시 분석하면 새 행 |
| F04-01 | 관절 위치 | (저장 안 함) | 메모리에서만 씀 |
| F04-02 | 얼굴 가린 대표 장면 | key_frame_image | 가린 것만 저장 (DB가 강제) |
| F04-03, F04-04 | 프레임별 각도와 자세 판별 | frame_angle | 기준을 바꿔도 영상 없이 다시 계산 (OI-12) |
| F04-05 | 자세 비율, 하루 노출 시간 | judgment_basis | 판정 시점의 값을 스냅샷으로 |
| F04-06, F04-07 | REBA 사람 입력, 단계별 점수, 대표 장면 | reba_input, reba_result | — |
| F05-01, F05-02 | 호별 판정, 사람 확인 사유 | judgment, judgment_basis, criterion | 단위작업 × 호마다 1행 |
| F05-03 | 경고 기록 | warning | — |
| F05-05, F05-06 | 확정, 수정 이력 | judgment, edit_log | 이력은 추가만 |
| F06-01 | 엑셀 내보내기 기록 | export_log | 시트 내용은 뷰에서 |
| F06-02, F06-03 | GPT 요청과 결과 | ai_text | 보낸 값을 남김 |
| F07-01 ~ F07-03 | 모델, 각도 기준, 설정 | pose_model, threshold_default, survey_threshold, app_setting | GPT 키는 저장 안 함 |

---

## 4. 데이터 표준

### 4.1 명명 규칙

1. 테이블과 컬럼 이름은 영어 소문자와 밑줄(snake_case)로 쓴다. 테이블은 단수 명사다 (예: `survey`, `unit_task`).
2. 컬럼 이름의 끝은 도메인을 나타낸다 (4.2절). 예: `daily_work_h`는 '시간(시)' 도메인
3. 식별자는 `테이블명_id`로 쓴다. 다른 테이블에서도 같은 이름으로 참조한다 (예: `unit_task_id`).
4. 코드 값은 영어 대문자와 밑줄로 쓰고 4.4절 코드 정의서에 등록한다.
5. 약어는 표준 단어(4.3절)에 있는 것만 쓴다.

### 4.2 도메인 정의

| 도메인 | 컬럼 끝 | SQLite 타입 | 규칙 |
|---|---|---|---|
| 식별자 | `_id` | INTEGER | 1부터 자동 증가 (rowid) |
| 번호 | `_no` | INTEGER | 0 이상 (호 번호는 1~11) |
| 코드 | `_cd` | TEXT | 코드 정의서의 값만 (CHECK) |
| 여부 | `_yn` | INTEGER | 0 또는 1. NULL은 '아직 모름' |
| 일시 | `_at` | TEXT | `YYYY-MM-DDTHH:MM:SS` 로컬 시각 |
| 일자 | `_date` | TEXT | `YYYY-MM-DD` (`date()`로 검증) |
| 시간(시) | `_h` | REAL | 0 ~ 24 |
| 시간(초) | `_s` | REAL | 0 이상 |
| 각도 | `_deg` | REAL | 부위별 범위 (-180 ~ 180, 0 ~ 180) |
| 무게 | `_kg` | REAL | 0 이상 |
| 횟수·개수 | `_cnt`, `_per_day`, `_per_min`, `_per_hour` | INTEGER, REAL | 0 이상 |
| 비율 | `_ratio` | REAL | 0 ~ 1 |
| 점수 | `_score` | INTEGER | REBA 단계별 범위 |
| 이름 | `_name` | TEXT | 빈 글자 금지 |
| 글 | `_text`, `_desc`, `_json` | TEXT | JSON은 `json_valid()` 검사 |
| 위치 | `_path` | TEXT | 원본 파일 위치 |
| 이미지 | `_jpeg` | BLOB | 얼굴 가린 JPEG만 |

### 4.3 표준 단어

| 한글 | 영어 | 한글 | 영어 |
|---|---|---|---|
| 조사 | survey | 단위작업 | unit_task |
| 부담작업 기준(호) | criterion | 각도 기준 | threshold |
| 판정 | judgment | 근거 | basis |
| 경고 | warning | 분석 | analysis_run |
| 영상 | video | 프레임 | frame |
| 참여자 | participant | 수정 이력 | edit_log |
| 계산값(초안) | computed | 확정값 | final |
| 확정 | confirm | 하루 | daily |
| 노출 | exposure | 비율 | ratio, share |
| 굽힘 | flex | 젖힘 | ext |
| 비틀림 | twist | 들기 | lift |
| 몸통 | trunk | 허리 | waist |
| 목 | neck | 위팔 | upper_arm |
| 팔꿈치 | elbow | 무릎 | knee |
| 손잡이 | coupling | 하중 | load |
| 대표 장면 | key_frame | 기울기 | tilt |

### 4.4 코드 정의서

| 코드 컬럼 | 값과 뜻 |
|---|---|
| survey.survey_type_cd | REGULAR 정기 · OCCASIONAL 수시 · INITIAL 최초 |
| survey_reason.reason_cd | MSD_CASE 근골격계질환자 발생 · NEW_TASK 부담작업에 해당하는 새 작업·설비 도입 · ENV_CHANGE 업무량·작업공정 등 작업환경 변경 |
| survey.status_cd | DRAFT 작성 중 · CONFIRMED 확정 |
| participant.participant_type_cd | REPRESENTATIVE 근로자 대표 · WORKER 해당 작업 근로자 |
| unit_task.period_type_cd | ONGOING 상시 (단기간작업도 간헐적인 작업도 아님) · SHORT_TERM 단기간작업 (2개월 이내에 종료되는 1회성 작업) · INTERMITTENT 간헐적인 작업 (연간 총 작업일수 60일 이하). 정의는 고시 제2조 제1·2호 |
| repetition_input.body_part_cd | NECK 목 · SHOULDER 어깨 · ELBOW 팔꿈치 · WRIST 손목 · HAND 손 |
| lift_position_input.position_cd | BELOW_KNEE 무릎 아래 · ABOVE_SHOULDER 어깨 위 · ARM_EXTENDED 팔을 뻗은 상태 |
| reba_input.coupling_cd | GOOD 좋음 (+0) · FAIR 보통 (+1) · POOR 나쁨 (+2) · UNACCEPTABLE 받아들일 수 없음 (+3) |
| reba_input.wrist_flex_cd | LE15 0~15° · GT15 15° 초과 |
| reba_input.legs_support_cd | BILATERAL 양발 지지 · UNILATERAL 한 발 지지·불안정 |
| threshold_default.threshold_cd | NECK_FLEX 목 굽힘 · WAIST_FLEX 허리 굽힘 · WAIST_EXT 허리 젖힘 · NECK_TWIST 목 비틀림 · WAIST_TWIST 허리 비틀림 · UPPER_ARM_RAISE 팔꿈치 들기 (위팔) |
| threshold_default.measure_cd | VIDEO 영상으로 잼 · INVESTIGATOR 조사자 판단 |
| criterion.basis_type_cd | VIDEO 영상 · INPUT 입력 · MIXED 영상과 입력 |
| analysis_run.status_cd | RUNNING 분석 중 · DONE 완료 · FAILED 실패 · CANCELED 취소 |
| reba_result.key_frame_by_cd | AUTO 자동 · INVESTIGATOR 조사자가 고름 |
| reba_result.side_cd | L 왼쪽 · R 오른쪽 |
| reba_result.risk_level_cd | NEGLIGIBLE 무시 (1) · LOW 낮음 (2~3) · MEDIUM 보통 (4~7) · HIGH 높음 (8~10) · VERY_HIGH 매우 높음 (11~15) |
| judgment.computed_status_cd | APPLICABLE 해당 · NOT_APPLICABLE 비해당 · NEEDS_REVIEW 사람 확인 · NEEDS_INPUT 입력 필요 |
| judgment.final_status_cd | APPLICABLE 해당 · NOT_APPLICABLE 비해당 |
| judgment.review_reason_cd | JITTER 기준 각도 근처 · INVALID_FRAMES 판별 불가 프레임이 많음 · INTERPRETATION 따로 본 결과와 합친 결과가 다름 · MULTI_PERSON 여러 사람 · LEGS_CUT 다리 잘림 · KNEE_ON_FLOOR 무릎을 바닥에 댄 자세가 있음 |
| judgment.exclusion_cd | SHORT_TERM 단기간작업 · INTERMITTENT 간헐적인 작업 |
| judgment_basis.unit_cd | H 시간 · KG · CNT_DAY 회/일 · CNT_MIN 회/분 · CNT_HOUR 회/시간 · PERSON 명 · RATIO 비율 · DEG 도 · YN 예/아니오 |
| judgment_basis.threshold_source_cd | NOTICE 고시 · MOEL_NOTE 고용노동부 해설 · INVESTIGATOR 조사자 변경 |
| judgment_basis.item_cd | 자세 항목은 threshold_cd 값과 P3_UNION(3호 합산) · SQUAT · KNEELING, 입력 항목은 KEYBOARD_H · REPEAT_{부위} · FINGER_* · ONEHAND_* · LIFT_KG_PER_PERSON · LIFT_CNT · POS_{위치} · FREQ_LIFT_* · IMPACT_*. CHECK 없이 이 목록으로 관리 (항목이 늘 수 있어서) |
| ai_text.purpose_cd | WARNING_ADVICE 경고 조언 · REPORT_SUMMARY 보고서 요약 |
| ai_text.result_cd | OK 정상 · DISABLED 꺼 둠 · NO_WARNING 열린 경고가 없어 부르지 않음 (보고서 요약) · FALLBACK_NO_KEY 키 없음 · FALLBACK_OFFLINE 인터넷 없음 · FALLBACK_TIMEOUT 시간 초과 · FALLBACK_ERROR 오류 · FALLBACK_NUMBER_MISMATCH 보낸 적 없는 숫자 |
| edit_log.target_cd | SURVEY · TASK_INPUT · REBA_INPUT · THRESHOLD · KEY_FRAME · JUDGMENT |
| edit_log.action_cd | SET 값 입력·교체 (사유 선택) · CHANGE 사유가 필요한 변경 (각도 기준, 확정 결과 고치기) · CONFIRM 확정 · UNCONFIRM 확정 해제 · RESET 기본값으로 (언제 무엇을 쓰는지는 API 계약서 2.1절) |
| app_setting.setting_key | POSE_MODEL_ID · GPT_ENABLED · GPT_MODEL · LAST_EXPORT_DIR |

---

## 5. 개념 스키마

### 5.1 주제 영역

| 주제 영역 | 엔티티 | 설명 |
|---|---|---|
| 기준 정보 | criterion, threshold_default, pose_model | 법의 11개 호, 해설의 각도, 모델 목록. 앱과 함께 배포 |
| 조사 | survey, survey_reason, participant, survey_threshold | 조사 한 건과 그 조사에만 적용하는 값 |
| 작업과 입력 | unit_task, task_input, repetition_input, lift_position_input, reba_input | 단위작업과 조사자가 넣는 값 |
| 영상과 분석 | video, analysis_run, frame_angle, reba_result, key_frame_image | 영상 분석 결과 |
| 판정과 경고 | judgment, judgment_basis, warning, ai_text | 11개 호 판정, 근거, 경고, AI 문장 |
| 이력과 설정 | edit_log, export_log, app_setting, schema_version | 감사 기록, 설정, 스키마 버전 |

### 5.2 개념 ERD (엔티티와 관계)

![개념 ERD](ERD_그림/ERD_1_개념.png)

- 표기: IE 표기법 (까마귀발). 선 끝 `‖` 반드시 하나 · `o|` 없거나 하나 · `o<` 없거나 여럿. 실선은 식별 관계 (부모의 키가 자식의 PK에 들어감), 점선은 비식별 관계.
- 그림의 관계와 카디널리티는 스키마(부록 A)의 외래키에서 자동으로 만든다. 5.5절 표와도 자동으로 대조한다.
- 원본: `ERD.drawio` (draw.io에서 열어 고칠 수 있음. 부록 C)

### 5.3 논리·물리 ERD (컬럼 전체)

테이블마다 모든 컬럼과 타입을 보인다. 타입 뒤 `?`는 NULL 허용, 밑줄은 기본키다. 다른 그림에 있는 테이블은 회색 점선 상자에 기본키만 보인다. 컬럼 설명은 6.2절 테이블 정의서에 있다.

**① 기준 정보 · 조사 · 작업과 입력**

![논리 ERD 1](ERD_그림/ERD_2_조사_작업.png)

**② 영상과 분석**

![논리 ERD 2](ERD_그림/ERD_3_영상_분석.png)

**③ 판정과 경고 · 이력과 설정**

![논리 ERD 3](ERD_그림/ERD_4_판정_이력.png)

### 5.4 엔티티 정의

| 엔티티 | 한글명 | 정의 | 식별자 (종류) | 생기는 때 |
|---|---|---|---|---|
| criterion | 부담작업 기준 | 고시 제3조의 1~11호 | criterion_no (본질 식별자: 법의 호 번호) | 앱 설치 때 |
| threshold_default | 각도 기준 기본값 | 해설이 정한 자세 각도 | threshold_cd (본질 식별자) | 앱 설치 때 |
| pose_model | 관절 모델 | 쓸 수 있는 관절 모델 | model_id (인조) | 앱 설치 때 |
| survey | 조사 | 유해요인조사 한 건 | survey_id (인조) | 조사를 만들 때 |
| survey_reason | 수시조사 사유 | 수시조사의 사유 하나 | survey_id + reason_cd (복합, 식별 관계) | 사유를 고를 때 |
| participant | 참여 근로자 | 면담 참여자 한 명 | participant_id (인조) | 참여자를 넣을 때 |
| survey_threshold | 조사별 각도 기준 변경 | 한 조사에서 바꾼 각도 하나 | survey_id + threshold_cd (복합, 식별 관계) | 조사자가 각도를 바꿀 때 |
| unit_task | 단위작업 | 판정 단위가 되는 작업 | unit_task_id (인조) | 단위작업을 등록할 때 |
| task_input | 작업 정보 입력 | 단위작업의 입력값 묶음 | unit_task_id (1:1 식별 관계) | 처음 입력할 때 |
| repetition_input | 부위별 반복 시간 | 2호 부위 하나의 반복 시간 | unit_task_id + body_part_cd (복합) | 부위 시간을 넣을 때 |
| lift_position_input | 위치별 들기 | 9호 위치 하나의 횟수와 무게 | unit_task_id + position_cd (복합) | 위치별 값을 넣을 때 |
| reba_input | REBA 사람 입력 | 영상으로 못 재는 REBA 항목 | unit_task_id (1:1 식별 관계) | 처음 입력할 때 |
| video | 영상 | 단위작업에 붙인 영상 파일 하나 | video_id (인조) | 영상을 고를 때 |
| analysis_run | 분석 실행 | 영상 하나를 모델 하나로 분석한 한 번 | run_id (인조) | 분석을 시작할 때 |
| frame_angle | 프레임별 각도 | 분석의 프레임 하나 | run_id + frame_no (복합, 식별 관계) | 분석이 끝날 때 |
| reba_result | REBA 결과 | 분석의 대표 장면 REBA | run_id (1:1 식별 관계) | 분석이 끝날 때 |
| key_frame_image | 대표 장면 이미지 | 얼굴 가린 대표 장면 | run_id (1:1 식별 관계) | 대표 장면이 정해질 때 |
| judgment | 판정 | 단위작업의 호 하나에 대한 판정 | judgment_id (인조), 대체키 unit_task_id + criterion_no | 판정을 계산할 때 |
| judgment_basis | 판정 근거 | 판정에 쓴 값 하나 | basis_id (인조), 대체키 judgment_id + item_cd | 판정을 계산할 때 |
| warning | 경고 | 띄운 경고 하나 | warning_id (인조) | '해당' 초안이 생길 때 |
| ai_text | AI 문장 | GPT 요청 한 번 | ai_text_id (인조) | 문장을 요청할 때 |
| edit_log | 수정 이력 | 바뀐 일 하나 | log_id (인조) | 값이 바뀔 때 |
| export_log | 엑셀 내보내기 기록 | 엑셀 파일 하나 | export_id (인조) | 엑셀을 만들 때 |
| app_setting | 앱 설정 | 설정 하나 | setting_key (본질) | 설정을 바꿀 때 |
| schema_version | 스키마 버전 | 스키마 변경 한 번 | version_no | 설치·업그레이드 때 |

### 5.5 관계 정의

| 부모 | 자식 | 카디널리티 | 관계 | 부모를 지우면 |
|---|---|---|---|---|
| survey | unit_task, survey_reason, participant, survey_threshold, edit_log, export_log | 1 : 0..N | 비식별 (survey_reason, survey_threshold는 식별) | 함께 지움 (CASCADE) |
| survey | ai_text (요약) | 0..1 : 0..N | 비식별, 선택 (AI 문장은 경고나 조사 중 하나에만 딸림, CHECK로 강제) | 함께 지움 |
| threshold_default | survey_threshold | 1 : 0..N | 식별 | 지울 수 없음 (기준 정보) |
| criterion | threshold_default, judgment, warning | 1 : 0..N | 비식별 | 지울 수 없음 (기준 정보) |
| unit_task | task_input, reba_input | 1 : 0..1 | 식별 (1:1) | 함께 지움 |
| unit_task | repetition_input, lift_position_input | 1 : 0..N | 식별 | 함께 지움 |
| unit_task | video, analysis_run, judgment, warning | 1 : 0..N | 비식별 | 함께 지움 |
| video | analysis_run | 1 : 0..N | 비식별 | 분석이 남아 있으면 영상만 지울 수 없음 (증거 보호) |
| pose_model | analysis_run | 1 : 0..N | 비식별 | 지울 수 없음 |
| analysis_run | frame_angle | 1 : 0..N | 식별 | 함께 지움 |
| analysis_run | reba_result | 1 : 0..1 | 식별 (1:1) | 함께 지움 |
| reba_result | key_frame_image | 1 : 0..1 | 식별 (1:1) | 함께 지움 |
| analysis_run | judgment | 0..1 : 0..N | 비식별, 선택 (입력만 쓰는 호는 분석이 없음) | 판정이 남아 있으면 지울 수 없음 |
| judgment | judgment_basis | 1 : 0..N | 비식별 | 함께 지움 |
| judgment | warning | 0..1 : 0..N | 비식별, 선택 | 경고의 연결만 끊음 (SET NULL) |
| warning | ai_text (조언) | 0..1 : 0..N | 비식별, 선택 (위와 같음) | 함께 지움 |

### 5.6 정규화 검토

| 단계 | 검토 | 이 설계에서 |
|---|---|---|
| 1정규형 | 한 칸에 값 하나, 반복 그룹 없음 | 수시 사유(여러 개) → survey_reason. 2호 부위별 시간 → repetition_input. 9호 위치별 횟수 → lift_position_input |
| 2정규형 | 복합키의 일부에만 딸린 속성 없음 | frame_angle의 각도는 (run_id, frame_no) 전체에 딸림. survey_threshold의 값·사유는 (survey_id, threshold_cd) 전체에 딸림 |
| 3정규형 | 키가 아닌 속성끼리의 이행 종속 없음 | 호의 이름·법 문구는 criterion에만. 모델 이름·버전은 pose_model에만. 조사자 이름은 survey에만 |

**의도적 반정규화** (이유가 있어 계산 결과를 저장한 곳)

| 어디 | 무엇을 저장 | 이유 |
|---|---|---|
| judgment_basis | 자세 비율, 하루 노출 시간, 비교한 기준값 | 판정 시점의 근거를 그대로 남기기 위해 (재현성, 감사). 나중에 기준이 바뀌어도 확정 당시 값이 남는다 |
| judgment.basis_text, source_text | 근거·출처 문장 | 화면과 엑셀에 같은 문장을 보이기 위해 |
| reba_result | REBA 단계별 점수 | 점수가 어떻게 나왔는지 보여 주기 위해. 합계 규칙은 CHECK로 묶어 서로 어긋나지 않게 함 |
| analysis_run.invalid_ratio | 판별 불가 비율 | 사람 확인 판단에 바로 쓰기 위해 |

파생 속성이지만 **저장하지 않는 것**: 다음 정기조사 예정일 (확정일 + 3년, v_survey_list에서 계산), 조사별로 실제 쓰는 각도 (v_effective_threshold에서 계산)

### 5.7 무결성 제약

| 종류 | 무엇을 지키나 | 어떻게 | 기능정의서 |
|---|---|---|---|
| 개체 무결성 | 모든 행은 식별된다 | 모든 테이블에 PK. 복합키 테이블은 WITHOUT ROWID | — |
| 참조 무결성 | 없는 조사·작업·분석을 가리키지 않는다 | 외래키 + 삭제 규칙 (5.5절). 연결마다 `PRAGMA foreign_keys = ON` | — |
| 도메인 무결성 | 값의 범위와 코드 | CHECK: 하루 작업시간 0~24, REBA 1~15, 코드 목록, 날짜 형식, JSON 형식 | F02-02 처리 규칙 2 |
| 상태 무결성 | 상태와 값의 조합 | 확정 = 확정 시각 있음. '입력 필요'는 확정 불가. '사람 확인'과 초안과 다른 확정은 사유 필수 | 3.2절, EX-14, EX-15 |
| 계산 무결성 | 점수 합계 | 점수 A = 표 A + 하중, 점수 B = 표 B + 손잡이, REBA = 표 C + 활동, 위험 단계 = 점수 구간 | F04-06 |
| 업무 규칙 (트리거) | 행 하나로는 못 거는 규칙 | 수시조사에만 사유 · 동의한 영상만 분석 · 같은 작업의 영상·분석만 · 수정 이력은 고치거나 지울 수 없음 | F03-03, F05-06 |
| 개인정보 | 얼굴은 저장하지 않음 | key_frame_image.masked_yn = 1만 허용 | BR-22 |

표 A·B·C의 조회 값(어떤 각도 점수 조합이 몇 점인지)은 DB가 확인하지 않는다. 분석 엔진이 계산하고 워크시트 예시로 시험한다 (AC-18).

---

## 6. 내부 스키마

### 6.1 저장 구조

| 항목 | 정한 것 | 이유 |
|---|---|---|
| 파일 | `%LOCALAPPDATA%\ergo-assist\ergo_assist.db` 하나 | 설치형 PC 프로그램. 사용자 폴더라 관리자 권한이 필요 없음 |
| 연결 설정 | `PRAGMA foreign_keys = ON` (연결마다), `PRAGMA journal_mode = WAL` (파일 만들 때), `PRAGMA busy_timeout = 3000` | SQLite는 외래키가 기본으로 꺼져 있음. WAL은 분석 중 화면이 읽어도 막히지 않고 갑자기 꺼져도 안전함 |
| STRICT 테이블 | 모든 테이블 | SQLite는 원래 타입을 느슨하게 받음. STRICT면 'abc'를 REAL 칸에 넣을 수 없음 |
| WITHOUT ROWID | 복합키 테이블 (survey_reason, survey_threshold, repetition_input, lift_position_input, frame_angle), 문자 PK 테이블 (threshold_default, app_setting) | PK 순서로 바로 저장해 조회가 빠르고 공간이 적음 |
| 이미지 | 대표 장면 JPEG를 BLOB로 DB에 저장 | 백업·이동이 파일 하나로 끝남 (결정 D-02) |
| 시각 | 로컬 시각 ISO 문자열 | SQLite에 날짜 타입이 없음. 문자열이라도 정렬이 시간순과 같음 |

### 6.2 테이블 정의서

{{TABLE_DEFS}}

### 6.3 인덱스

외래키 열에는 인덱스를 둔다 (부모를 지울 때 자식을 빨리 찾으려고). 복합 UNIQUE의 첫 열은 그 UNIQUE 인덱스가 대신하므로 따로 두지 않는다 (예: unit_task.survey_id는 UNIQUE(survey_id, task_name)이 대신함).

{{INDEXES}}

**실행 계획으로 확인** (`EXPLAIN QUERY PLAN`)

{{PLANS}}

### 6.4 트리거

{{TRIGGERS}}

### 6.5 용량 추정

- 30초 영상 1건(900프레임)의 분석 데이터가 파일에서 차지하는 크기: **약 {{RUN_KB}} KB** (실측: 900프레임을 넣고 VACUUM 전후 파일 크기 비교)
- 대표 장면 JPEG 1장: 수십 KB (해상도에 따라)
- 조사 1건 (단위작업 10개, 각 30초 영상): 수 MB 수준. 한 PC에 수백 건을 저장해도 문제없음

### 6.6 백업 · 보존 · 삭제

- **백업**: 엑셀을 내보낼 때 DB 파일을 같은 폴더에 함께 복사하는 기능을 둔다 (SQLite 온라인 백업 API). 파일 하나라 USB로 옮길 수 있다.
- **보존**: 지침 11절의 보존 기간(새 조사가 끝날 때까지, 신상정보가 있으면 5년, 개선계획은 해당 설비가 있는 동안)을 화면과 엑셀에 안내한다. 자동으로 지우지는 않는다.
- **삭제**: 조사를 지우면 그 조사의 모든 데이터와 수정 이력이 함께 지워진다. 수정 이력을 한 줄씩 지우는 것은 막는다 (9절 P7, M06).

### 6.7 스키마 변경 (마이그레이션)

1. 스키마를 바꾸면 `schema_version`에 한 줄을 넣고 `PRAGMA user_version`을 같은 번호로 올린다.
2. 앱이 시작할 때 `user_version`을 보고 필요한 변경 SQL을 순서대로 실행한다.
3. 변경 전에 DB 파일을 백업한다.

---

## 7. 외부 스키마

### 7.1 뷰 목록

| 뷰 | 사용자·응용 | 쓰는 곳 | 보여 주는 것 | 감추는 것 |
|---|---|---|---|---|
| v_survey_list | 조사자 | S01 조사 목록 | 조사, 작업 수, 남은 초안 수, 다음 정기조사 예정일 | 판정 세부 |
| v_task_result | 조사자, 엑셀 | S06 분석 결과, 엑셀 '작업별 결과' | 현재 분석, REBA, 모델, 열린 경고 수 | 과거 분석 |
| v_judgment_sheet | 조사자, 엑셀 | S07 판정, 엑셀 '판정 초안' | 호별 상태(초안·확정), 근거, 출처, 확정자 | 계산 중간값 |
| v_excel_summary | 엑셀 | 엑셀 '요약' | 단위작업별 해당 호, 초안 수, REBA | — |
| v_warning_log | 엑셀 | 엑셀 '경고 기록' | 경고, 근거, AI 문장 결과 | 보낸 요청 원문 |
| v_edit_log | 조사자 | S07 수정 이력 | 누가·언제·무엇을·왜 | — |
| v_effective_threshold | 판정 엔진, 조사자 | S09 설정, 판정 계산 | 조사별로 실제 쓰는 각도와 출처 (해설 / 조사자 변경) | — |
| v_gpt_payload | GPT 어댑터 | F06-02 | 호, 기준 요약, 고시 원문(공개 법령), 하루 작업시간, 비율, 노출 시간, REBA, 조사의 단위작업 수. 거르기·묶기용 번호 (보내지 않음) | **이름, 조사·부서·작업명, 파일 위치, 자유 입력 글** (BR-21, AC-30) |
| v_posture_exposure_check | 검증 담당 | 시험 | 저장된 각도로 다시 계산한 비율과 노출 시간 | — (판정에는 쓰지 않음) |

**응용별 규칙**

1. 화면과 엑셀은 뷰로 읽고, 쓰기는 API 계약서의 서비스 함수로만 한다.
2. GPT 어댑터는 `v_gpt_payload`만 읽는다. 다른 테이블을 읽는 코드는 리뷰에서 막는다. `warning_id`·`survey_id`·`unit_task_id`는 거르고 묶는 데만 쓰고 GPT에 보내지 않는다 (API 계약서 6.2절).
3. `v_posture_exposure_check`는 분석 엔진(Python)의 계산을 SQL로 따로 계산해 대조하는 시험용이다. 두 계산이 같으면 엔진을 믿을 근거가 된다 (9절 P1·P2).

### 7.2 뷰 정의

```sql
{{VIEW_SQL}}
```

---

## 8. 개인정보 분류

| 데이터 | 분류 | 저장 | 처리 |
|---|---|---|---|
| 조사자 이름 (survey.investigator_name, confirmed_by, actor_name, changed_by) | 개인정보 | 저장 | 화면과 엑셀에 보임. GPT에 보내지 않음 |
| 참여 근로자 표시 이름 | 개인정보 | 저장 | 실명 대신 '근로자 A' 권장. GPT에 보내지 않음 |
| 근로자 얼굴 | 개인정보 (영상) | **저장하지 않음** | 대표 장면은 가린 것만 (masked_yn = 1 강제) |
| 원본 영상 | 개인정보 | **복사하지 않음** | 위치(file_path)만 저장 |
| 관절 위치 원자료 | 신체 정보 | **저장하지 않음** | 각도와 자세 판별 결과만 저장 |
| 작업명, 작업 내용 (자유 입력) | 개인정보가 섞일 수 있음 | 저장 | GPT에 보내지 않음 (OI-05) |
| 건강 정보 | 민감정보 | 지금은 없음 | 증상조사(FR-032)를 넣으면 민감정보라 따로 설계 (OI-04) |
| GPT API 키 | 비밀 | **DB에 저장하지 않음** | 저장 위치는 API 계약서에서 정함 |

---

## 9. 검증 결과

제약은 '있다'가 아니라 '잡는다'로 증명한다. 정상 데이터가 들어가는지(P)와, 잘못된 데이터를 일부러 넣어 DB가 막는지(M)를 시험했다.

{{TESTS}}

---

## 10. 예시 쿼리 (업무 질의 겸 SQLD 연습)

같은 시험 데이터에서 실행한 결과다.

{{QUERIES}}

---

## 11. 추적표 (기능 → 데이터)

| 기능 | 테이블 | 뷰 |
|---|---|---|
| F01-01 조사 만들기 | survey, survey_reason | v_survey_list |
| F01-02 저장·목록 | (전체) | v_survey_list |
| F01-03 다음 정기조사 예정일 | survey | v_survey_list |
| F02-01 단위작업 등록 | unit_task | v_task_result |
| F02-02 작업 정보 입력 | task_input, repetition_input, lift_position_input | — |
| F02-03 참여 근로자 | participant | — |
| F03-01 ~ F03-03 영상·동의 | video | — |
| F03-04 분석 실행 | analysis_run | v_task_result |
| F04-02 얼굴 모자이크 | key_frame_image | — |
| F04-03 ~ F04-05 각도·자세·노출 | frame_angle, judgment_basis | v_posture_exposure_check |
| F04-06, F04-07 REBA·대표 장면 | reba_input, reba_result, key_frame_image | v_task_result |
| F05-01, F05-02 판정·확신도 | judgment, judgment_basis, criterion | v_judgment_sheet |
| F05-03 경고 | warning | v_warning_log, v_gpt_payload |
| F05-04 다시 계산 | frame_angle, task_input, survey_threshold | v_effective_threshold |
| F05-05 확정 | judgment | v_judgment_sheet |
| F05-06 수정 이력 | edit_log | v_edit_log |
| F06-01 엑셀 | export_log | v_excel_summary, v_task_result, v_warning_log, v_judgment_sheet |
| F06-02, F06-03 GPT | ai_text | v_gpt_payload |
| F07-01 모델 | pose_model, app_setting | — |
| F07-02 각도 기준 | threshold_default, survey_threshold | v_effective_threshold |
| F07-03 GPT 설정 | app_setting | — |

---

## 12. 설계 결정과 미결 사항

### 12.1 결정

| ID | 결정 | 다른 선택지 | 이유 |
|---|---|---|---|
| D-01 | 프레임별 각도를 저장한다 (기능정의서 OI-12) | 요약만 저장 | 각도 기준을 바꿔도 영상 없이 다시 계산하고, 같은 결과를 증명할 수 있다. 30초 영상에 약 {{RUN_KB}} KB |
| D-02 | 대표 장면 이미지는 DB에 BLOB로 | 이미지 파일을 폴더에 따로 | 파일 하나로 백업·이동. 얼굴 가림을 DB가 강제할 수 있음 |
| D-03 | 판정은 현재 값 1행, 바뀐 내역은 수정 이력에 | 판정 버전 테이블 | 화면과 엑셀은 현재 값만 쓰고, 감사는 이력으로 충분 |
| D-04 | 코드는 CHECK 목록으로 | 공통 코드 테이블 | 코드가 적고 거의 안 바뀜. DB가 바로 막음. 바뀌면 마이그레이션 |
| D-05 | 단위작업을 지워도 수정 이력은 남긴다 | 함께 지움 | 누가 무엇을 지웠는지 남기기 위해. 조사 전체를 지울 때만 함께 지움 |
| D-06 | GPT 키는 DB에 두지 않는다 | 설정 테이블에 저장 | DB 파일을 복사해도 키가 새지 않게 |
| D-07 | 조사별 각도 변경은 survey_threshold에, 기본값은 threshold_default에 | 설정 하나로 | 변경이 다른 조사로 퍼지지 않게 (F07-02 처리 규칙 1) |
| D-08 | 관절 위치 원자료는 저장하지 않는다 | 저장 | 데이터 최소화. 기술 파라미터(TP-04~06)를 바꾸면 다시 분석해야 하는 대가가 있음 |

### 12.2 미결 사항이 바뀌면 생기는 스키마 변경

| 기능정의서 미결 | 이렇게 정해지면 | 스키마 변경 |
|---|---|---|
| OI-01 4·5·9호를 합쳐 보기로 | 판정 계산만 바뀜 | 없음 (judgment_basis 항목만 추가) |
| OI-03 2호·7~10호를 영상으로도 잼 | 영상 참고값 저장 | frame_angle에 동작 판별 열 추가 |
| OI-04 증상설문조사를 넣음 | 근로자 응답 저장 | 증상조사 테이블 추가 (민감정보 설계 필요) |
| OI-06 분석 구간 지정 | 구간 저장 | analysis_run에 start_frame_no, end_frame_no 추가 |
| OI-07 정면 영상 추가 | 영상 방향 구분 | video에 view_cd (측면·정면) 추가 |
| OI-08 분석할 사람 선택 | 고른 사람 저장 | analysis_run에 person_index 추가 |

---

## 부록 A. DDL (schema_v1.sql)

```sql
{{DDL}}
```

## 부록 B. 기준 정보 초기 데이터 (seed_v1.sql)

```sql
{{SEED}}
```

## 부록 C. 그림 원본

`ERD.drawio` 한 파일에 5쪽이 있다. 스키마(부록 A)에서 자동으로 만들고, draw.io에서 열어 고칠 수 있다.

| 쪽 | 그림 | 이 문서 |
|---|---|---|
| 0 | 3단계 스키마 | 2절 |
| 1 | 개념 ERD | 5.2절 |
| 2 | 논리·물리 ERD ① 기준 정보 · 조사 · 작업과 입력 | 5.3절 |
| 3 | 논리·물리 ERD ② 영상과 분석 | 5.3절 |
| 4 | 논리·물리 ERD ③ 판정과 경고 · 이력과 설정 | 5.3절 |
