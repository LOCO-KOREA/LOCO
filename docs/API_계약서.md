# API 계약서

> 문서 ID ERGO-API-001 · 설계 버전 2.0 · 개정일 2026-10-16 · 완성 목표 2026-10-23(Asia/Seoul)
>
> 실행 계약의 기준이다. main e7b0cf1은 설계 출발점이며 현재 구현·실행 증거와 남은 제약은 [검증 대조표](local-verification.md)를 따른다. 문서 존재와 전체 수용을 구분한다.

## 1. 모듈·버전·연결

실행 계약은 `ergo/contracts.py`의 2.0 메서드 목록과 이 문서의 §7을 함께 검증한다. Electron과 개발 실행은 `ergo/service/json_lines.py`만 사용한다. 이전 0.3 Protocol/StubService, 별도 샘플 서버, 이전 프론트 저장 adapter는 실행 경로에서 제거한다. 알 수 없는 메서드·누락 매개변수·이전 DTO 버전은 저장 전에 거부한다. 1.3은 `ergo/legacy/v13.py`의 읽기 adapter와 저장된 snapshot 열람에 한정하며 이전 규칙으로 새 계산을 만들지 않는다.

모든 작업에 동일한 일반 작업 계약을 사용한다. 상자 들기도 조건별 직접입력, 가변 사진, 사진별 촬영조건·관찰 하중으로 처리한다. 신규 작업에는 15슬롯·3회차·5순간·사건별 자동 하중을 사용하지 않는다. 이전 상자 프로토콜은 §10의 호환 읽기에만 남긴다.

Electron renderer → preload → main → Python Application Service → 기능 모듈/storage 순서다. main은 Python 프로세스 하나를 windowsHide=true로 실행한다. UTF-8 JSON Lines와 request_id로 요청·응답을 연결한다. stdout은 응답, stderr는 로그다. 분석/GPT 작업은 백그라운드에서 처리하며 응답 쓰기는 메시지 단위로 직렬화한다. HTTP 서버·통신용 DB를 추가하지 않는다.

| 모듈 | 책임 |
|---|---|
| task_input | 일반 작업·11개 기준·조건별 행·입력 revision |
| capture | 가변 사진·분석대상 선택·사진별 촬영조건·EXIF 미리보기 |
| pose/tags | MoveNet 17관절·각도 후보·사진 기술태그 |
| reba | 관찰 하중·수동 범주·점수표 계산 |
| burden | 직접입력으로 11개 기준 초안·비교근거·누락·모순 |
| explanation | 허용 수치 요약으로 실제 GPT API/로컬 대체 설명 |
| report | 같은 snapshot의 한글 시트(공식 유해요인조사 서식 구성 시트와 보조 시트)·상태·다음 입력·전후 비교 |
| storage | 여섯 테이블의 JSON 매핑·트랜잭션·부분 결과 저장 |

신규 TaskInput/TaskSnapshot/ExportSnapshot.schema_version과 report_version은 '2.0'이다. 물리 테이블은 유지한다. 문서 1.5/저장 1.3/미병합 업무 양식 1.4는 이전 계약이며 기존 행을 일괄 변환하지 않는다.

N02의 읽기 전용 DB 위치 기능은 Electron 전용 IPC다. main은 시작 시 작업 폴더를 기준으로 DB 절대경로를 결정하고 동일 값을 Python의 LOCO_DB_PATH에 전달한다. `get_database_info`는 기존 list_surveys의 성공 응답으로 연결 여부를 확인한다. 실패 시 지정 경로와 connected=false, DB_ERROR 안내를 함께 반환하며 연결 완료로 표시하지 않는다. `copy_database_path`와 `open_database_folder`는 인자로 경로를 받지 않고 같은 worker의 연결을 다시 확인한 뒤 지정 파일 DB에만 수행한다. clipboard·폴더 열기 실패는 FILE_ERROR다. 메모리 DB와 브라우저 미리보기에는 파일 동작이 없다. 위치 확인 조회만 8초로 제한하며 지연 응답이 파일 동작을 재개하지 않는다. 기존 저장·분석 요청의 IPC 처리는 변경하지 않는다. Python dispatch 메서드·DTO·DB 구조에는 변화가 없으며 DB 선택·전환 계약은 후속 범위다.

## 2. 공통 타입

~~~typescript
type ID = number;          // 양의 DB ID
type Number = number;      // 유한 실수
type Count = number;       // 0 이상 정수
type RowID = string;       // 기준 내 조건 행 ID
type Date = string;        // YYYY-MM-DD
type Timestamp = string;   // UTC ISO8601
type Truth = 'YES'|'NO'|'UNKNOWN';
type Side = 'LEFT'|'RIGHT';
type Forward = 'SCREEN_LEFT'|'SCREEN_RIGHT';
type Currentness = 'NONE'|'CURRENT'|'STALE';
type JobStatus = 'RUNNING'|'FINISHED'|'FAILED'|'CANCELED';
type JudgmentStatus = 'APPLICABLE'|'NOT_APPLICABLE'|'NEEDS_INPUT'|'NEEDS_REVIEW';
type FinalStatus = 'APPLICABLE'|'NOT_APPLICABLE';
type Evidence = {source:'DIRECT_OBSERVATION'|'INTERVIEW'|'DOCUMENT'|'OTHER'|null,text:string|null,observed_at:Timestamp|null};
type Diagnostic = {code:string,message:string,field_path:string|null};
type AppError = {code:'FILE_ERROR'|'MODEL_ERROR'|'DB_ERROR'|'EXPORT_ERROR'|'NOT_FOUND'|'API_ERROR',message:string};
type Result<T> = {ok:true,value:T}|{ok:false,error:AppError};
type Ack = {message:string};
type BridgeRequest = {request_id:number,method:string,params:Record<string,unknown>};
type BridgeResponse<T> = {request_id:number,result:Result<T>};
type DatabaseLocationInfo = {
  path:string; storage:'file'|'memory'; connected:boolean; error:AppError|null;
};
type DesktopBridge = {
  call<T>(method:string,params:Record<string,unknown>):Promise<Result<T>>;
  choose_photo_paths():Promise<string[]>;
  path_for_file(file:File):string;
  choose_export_destination():Promise<string|null>;
  get_database_info():Promise<Result<DatabaseLocationInfo>>;
  copy_database_path():Promise<Result<Ack>>;
  open_database_folder():Promise<Result<Ack>>;
};
~~~

null은 미입력이고 실제 0은 숫자 0이다. UI·Excel은 Asia/Seoul로 표시한다. 음수·단위/범위 충돌·중복 ID 및 condition_present=NO와 양수 적격 작업의 모순은 관련 계산 진단이며 부분 입력도 저장·검토·초안 출력할 수 있다. 없는 ID·읽기 실패·DB 실패는 Result.error다. request_id는 저장하지 않는다. 부분 편집은 UI가 현재 전체 DTO에 합쳐 전달한다.

## 3. 조사·작업·11개 기준 입력

### 3.1 일반 작업

~~~typescript
type SurveyType = 'INITIAL'|'REGULAR'|'OCCASIONAL';
type OccasionalCause = 'DISEASE_CASE'|'NEW_TASK_OR_EQUIPMENT'|'WORK_ENVIRONMENT_CHANGE'|'OTHER';
type WorkplaceSituation = {equipment_status:Truth,equipment_notes:string,workload_status:Truth,workload_notes:string,speed_status:Truth,speed_notes:string,work_pattern_status:Truth,work_pattern_notes:string};
type WorkerParticipation = {status:Truth,role:'WORKER_REPRESENTATIVE'|'AFFECTED_WORKER'|'BOTH'|'UNKNOWN',participant_code:string,method:'INTERVIEW'|'MEETING'|'OBSERVATION'|'OTHER'|'UNKNOWN',date:Date|null,notes:string};
type SymptomRegion = {side:'RIGHT'|'LEFT'|'BOTH'|'NONE'|'UNKNOWN',duration:'LT_1_DAY'|'DAY_TO_WEEK'|'WEEK_TO_MONTH'|'MONTH_TO_6_MONTHS'|'GE_6_MONTHS'|'UNKNOWN',severity:'MILD'|'MODERATE'|'SEVERE'|'VERY_SEVERE'|'UNKNOWN',last_week:Truth};
type SymptomResponse = {response_code:string,name:string,age_years:Count|null,sex:'MALE'|'FEMALE'|'UNKNOWN',workplace_tenure_months:Count|null,department:string,job:string,current_work:string,current_work_months:Count|null,daily_work_hours:Count|null,rest_breaks:string,previous_work:string,previous_work_months:Count|null,leisure_activities:string,household_work:string,medical_history:Truth,injury_history:Truth,injury_sites:string[],physical_burden:1|2|3|4|5|null,work_related_symptoms_last_year:Truth,regions:Record<'neck'|'shoulder'|'arm_elbow'|'hand_wrist'|'back'|'leg_foot',SymptomRegion>};
type SymptomSurvey = {method:'QUESTIONNAIRE'|'INTERVIEW'|'OTHER'|'NOT_DONE'|'UNKNOWN',date:Date|null,respondent_count:Count|null,summary:string,responses:SymptomResponse[]};
type SurveyDraft = {survey_type:SurveyType,survey_date:Date,investigator:string,department:string,process:string,title:string,occasional_reason:string|null,occasional_cause:OccasionalCause|null,previous_survey_date:Date|null,workplace_situation:WorkplaceSituation,participation:WorkerParticipation,symptom_survey:SymptomSurvey};
type ReviewRecord = {reviewed:boolean,reviewed_analysis_ids:ID[],reviewed_metadata_revision:Count|null,reviewer:string|null,reviewed_at:Timestamp|null,note:string|null};
type ReviewMark = ReviewRecord & {history?: (ReviewRecord & {archived_at:Timestamp,reason:string})[]};
type Survey = SurveyDraft & {survey_id:ID,metadata_revision:Count,review:ReviewMark,created_at:Timestamp,updated_at:Timestamp};
type SurveySummary = {survey_id:ID,title:string,survey_date:Date,task_count:Count,reviewed:boolean,review_current:boolean};
type InputTemplate = 'GENERAL'|'OFFICE'|'REPETITION'|'POSTURE'|'HAND_FORCE'|'LIFTING'|'IMPACT';
type TaskConditions = {
  worker_code:string,method_description:string,work_posture:string,work_height_cm:Number|null,
  daily_work_min:Number|null,work_intensity:1|2|3|4|5|null,work_frequency:1|2|3|4|5|null,
  hazard_factors:string,hazard_causes:string,improvement_recommendations:string,
  one_off:Truth,planned_duration_months:Number|null,annual_work_days:Count|null,evidence:Evidence
};
type AnalysisScope = {judgment:true,pose:boolean,tags:boolean,reba:boolean};
type TaskDraft = {task_name:string,input_template:InputTemplate,conditions:TaskConditions};
type TaskInput = TaskDraft & {schema_version:'2.0',task_kind:'GENERAL_TASK',worker_count:Count|null,legal:LegalInputs,capture:CaptureSet,manual:ManualValue[],analysis_scope:AnalysisScope,legacy_input:Record<string,unknown>|null};
type Task = TaskInput & {task_id:ID,survey_id:ID,input_revision:Count,latest_analysis_id:ID|null,created_at:Timestamp,updated_at:Timestamp};
type Exclusions = {short_term:Truth,intermittent:Truth};
type TaskInputBundle = {task:Task,source_schema_version:'1.3'|'2.0',exclusions:Exclusions,photos:PhotoInfo[],settings:AnalysisSettings};
~~~

input_template는 질문 순서·도움말만 바꾸고 기준을 자동 NO로 만들지 않는다. 신규 작업의 legacy_input은 null이다. 11개 기준을 UNKNOWN으로 만들고 scope는 judgment만 true, 사진은0건이다. work_height_cm는 작업 높이 기록이며 물체 중량은 기준별 조건 행에 기록한다. 공동 작업의 하중을 worker_count로 나누지 않는다.

### 3.2 기준1~5의 직접시간과 기준6~11의 조건 행

~~~typescript
type ExposureCode =
  'C1_KEYBOARD_FOCUSED'|'C2_NECK'|'C2_SHOULDER'|'C2_ELBOW'|'C2_WRIST'|'C2_HAND'|
  'C3_UNION'|'C4_NECK_FLEX'|'C4_TRUNK_FLEX'|'C4_NECK_TWIST'|'C4_TRUNK_TWIST'|'C4_UNION'|
  'C5_SQUAT'|'C5_KNEEL'|'C5_UNION';
type ExposureInput = {condition_code:ExposureCode,minutes:Number|null,evidence:Evidence};
type CriterionCommon = {condition_present:Truth,evidence:Evidence,posture_interpretation_pending:boolean};
type UnionMeasure = {row_ids:RowID[],value:Number|null,evidence:Evidence};
type RowBase = {row_id:RowID,label:string,evidence:Evidence};
type C1Input = CriterionCommon & {criterion_no:1};
type C2Input = CriterionCommon & {criterion_no:2};
type C3Input = CriterionCommon & {criterion_no:3};
type C4Input = CriterionCommon & {criterion_no:4,unsupported:Truth,posture_restricted:Truth};
type C5Input = CriterionCommon & {criterion_no:5};
type PinchRow = RowBase & {unsupported:Truth,pinch_mass_kg:Number|null,pinch_force_kg_equiv:Number|null,minutes:Number|null};
type HandRow = RowBase & {unsupported:Truth,single_hand_mass_kg:Number|null,grip_force_kg_equiv:Number|null,minutes:Number|null};
type LiftCountRow = RowBase & {load_mass_kg:Number|null,lift_count_day:Count|null};
type PositionCounts = {below_knee_count_day:Count|null,above_shoulder_count_day:Count|null,extended_arm_count_day:Count|null,union_count_day:Count|null};
type PositionRow = RowBase & PositionCounts & {load_mass_kg:Number|null,union_evidence:Evidence};
type LiftRateRow = RowBase & {load_mass_kg:Number|null,lift_rate_min:Number|null,minutes:Number|null};
type ImpactRow = RowBase & {impact_verified:Truth,impact_rate_hour:Number|null,minutes:Number|null};
type RowAggregation = {rows_complete:Truth,union:UnionMeasure};
type C6Input = CriterionCommon & RowAggregation & {criterion_no:6,rows:PinchRow[]};
type C7Input = CriterionCommon & RowAggregation & {criterion_no:7,rows:HandRow[]};
type C8Input = CriterionCommon & RowAggregation & {criterion_no:8,rows:LiftCountRow[]};
type C9Input = CriterionCommon & {criterion_no:9,rows:PositionRow[],rows_complete:Truth,totals:PositionCounts & {row_ids:RowID[],evidence:Evidence}};
type C10Input = CriterionCommon & RowAggregation & {criterion_no:10,rows:LiftRateRow[]};
type C11Input = CriterionCommon & RowAggregation & {criterion_no:11,rows:ImpactRow[]};
type CriterionInput = C1Input|C2Input|C3Input|C4Input|C5Input|C6Input|C7Input|C8Input|C9Input|C10Input|C11Input;
type LegalInputs = {criteria:CriterionInput[],exposures:ExposureInput[]};
~~~

신규 입력은 criterion_no 1~11 각 1건과 ExposureCode 15건을 초기화한다. 기준 6~11의 rows는 빈 배열, rows_complete는 UNKNOWN이다. union/totals 객체는 유지하고 row_ids는 빈 배열, 측정값은 null, 근거는 빈 값으로 초기화한다. 이전 20종 시간 중 C6/C7/C10/C11은 조건 행·union으로 옮긴다. C4_TRUNK_EXT는 새 법령 입력에서 제외하고 이전 원문에 보존한다. 법문에 없는 젖힘을 4호의 자동 조건으로 추가하지 않는다.

- row_id는 기준 안에서 안정적이며 배열 순서와 다르다. 동일 물리 이벤트를 중복 합산하지 않는다.
- rows_complete=YES는 해당 기준의 하루 조건 행을 모두 기록했다는 관찰이다.
- union.value는 적격 조건 행의 중복 제거 직접값이다. 6/7/10/11호는 min/day, 8호는 count/day다. 9호 totals는 적격 중량의 위치별/합집합 count/day다.
- row_ids는 집계 대상을 명시한다. 부적격 행을 포함하면 모순, 적격 여부가 모르는 행을 포함하면 누락을 반환한다. 모르는 행을 0으로 제외하지 않는다.
- 완전한 단일 적격 행은 그 행의 값 자체가 union이다. 여러 행을 자동 합산하지 않는다.
- 한 행만으로 확실히 기준 이상이면 다른 행의 무관한 누락을 요구하지 않는다. 미달 결론에는 필요한 행의 망라성과 중복 제거값이 확인되어야 한다.
- 4/5/9호 자세 결합 해석은 기능정의서 §3의 COMBINATION_RULE을 따른다.

## 4. 가변 사진과 관찰값

~~~typescript
type LoadState = 'UNLOADED'|'MEASURED'|'UNKNOWN';
type PhotoInfo = {photo_id:ID,task_id:ID,file_path:string,file_name:string,width_px:Count|null,height_px:Count|null,consent:Truth,notes:Diagnostic[]};
type PhotoPreview = {photo_id:ID,data_url:string,width_px:Count,height_px:Count};
type ImportReport = {added:PhotoInfo[],unreadable:{file_path:string,message:string}[],notes:Diagnostic[]};
type CaptureObservation = {load_state:LoadState,measured_load_kg:Number|null,single_person:Truth,full_frame:Truth,normal_work:Truth,evidence:Evidence};
type CaptureSlot = {
  slot_no:Count,photo_id:ID|null,label:string,analysis_target:boolean,
  camera_side:Side|null,forward_direction:Forward|null,side_view_verified:Truth,
  observation:CaptureObservation
};
type CaptureSet = {protocol:'GENERAL_STILLS_V1',slots:CaptureSlot[]};
type Coupling = 'GOOD'|'FAIR'|'POOR'|'UNACCEPTABLE'|'NOT_APPLICABLE';
type LegsSupport = 'BILATERAL_STABLE'|'UNILATERAL_OR_UNSTABLE';
type KneeBand = 'UNDER_30'|'FROM_30_TO_60'|'OVER_60';
type ManualField =
  'trunk_base'|'trunk_twisted'|'trunk_side_bent'|'neck_base'|'neck_twisted'|'neck_side_bent'|
  'legs_support'|'seated'|'knee_band'|'shock_force'|'upper_arm_base'|'arm_abducted_or_rotated'|
  'shoulder_raised'|'arm_supported_or_gravity_assisted'|'lower_arm_base'|'wrist_base'|
  'wrist_deviated_or_twisted'|'coupling'|'static_over_1min'|'small_repeat_over_4min'|
  'rapid_change_or_unstable'|'hand_above_head'|'elbow_above_shoulder'|'elbow_behind_trunk'|'squat'|'kneel';
type ManualValue = {
  slot_no:Count,photo_id:ID,scope:'COMMON'|'LEFT'|'RIGHT',field:ManualField,
  value:Number|Truth|LegsSupport|KneeBand|Coupling|null,
  source:'AUTO_ACCEPTED'|'DIRECT_OBSERVATION'|'INTERVIEW'|null,evidence:Evidence
};
~~~

사진은 0..N건이며 분석대상으로 선택한 slot만 pose/tags/reba에 사용한다. 등록만으로 자동 배정·자동 분석하지 않는다. slot_no는 안정적 ID이며 다른 행 삭제 시 재번호를 붙이지 않는다. 일반 작업과 상자 들기에 동일 계약을 쓴다. 같은 photo_id를 여러 분석 행에 중복 배정하면 진단하고 중복 표본을 완성 결과로 계산하지 않는다.

하중은 관찰한 UNLOADED이면 0, MEASURED이면 측정 kg, UNKNOWN이면 null이다. 상태와 측정값의 충돌은 진단한다. 사건명이나 사진 순서로 전체 물체 중량을 적용하지 않는다. 하중을 기준 8~10호의 하루 값에 자동 전사하지 않는다. 목·손목·비틀림·지지·쥐기·충격·활동은 현장 확인값이다.

자동 후보는 몸통/무릎/좌우 위팔·아래팔 6개이며 적용할 때만 AUTO_ACCEPTED 수동값으로 저장한다. null 후보는 기존값을 덮어쓰지 않는다. 관찰 복사는 사용자가 고른 필드와 사진에만 적용한다. 근거·시각·대상 photo_id를 기록한다. ManualField별 허용 scope·범주·숫자 범위는 기능정의서 §5.1을 따른다.

## 5. 분석 DTO와 상태

~~~typescript
type ModuleState = 'NOT_REQUESTED'|'NOT_CALCULATED'|'RUNNING'|'COMPLETE'|'INCOMPLETE'|'FAILED'|'CANCELED';
type ModuleStates = {pose:ModuleState,tags:ModuleState,reba:ModuleState,judgment:ModuleState};
type PoseModel = {model_id:string,provider:string,variant:string,name:string,version:string,preprocess_version:string,input_size:Count,point_count:Count,confidence_kind:string,model_path:string,model_sha256:string,confidence_min:Number,detection_min:Number,presence_min:Number};
type PostureProfile = {version:'POSTURE_TECH_V1',neck_forward_deg:Number,trunk_flex_deg:Number,trunk_extension_deg:Number,upper_arm_raise_deg:Number};
type AnalysisSettings = {pose_model:PoseModel,posture_profile:PostureProfile,reba_rule:'REBA_TABLE_2000_V2',burden_rule:'MOEL_2020_12_GENERAL_V2'};
type TaskSnapshot = TaskInput & {task_id:ID,input_revision:Count,photos:PhotoInfo[],settings:AnalysisSettings};
type SlotStatus = 'PENDING'|'VALID'|'INVALID'|'ERROR'|'CANCELED'|'NOT_PROCESSED';
type AngleCode = 'TRUNK_TILT_VERT'|'NECK_TILT_VERT_PROXY'|'NECK_FLEX_TRUNK_PROXY'|'UPPER_ARM_RAISE_VERT'|'UPPER_ARM_FLEX_TRUNK'|'ELBOW_FLEX'|'KNEE_FLEX';
type Keypoint = {point_no:Count,name:string,x_px:Number,y_px:Number,confidence:Number,confidence_kind?:string,visibility?:Number,presence?:Number,z_normalized?:Number};
type Angle = {side:Side,angle_code:AngleCode,value_deg:Number|null,min_confidence:Number|null,diagnostic:string|null};
type SlotPoseResult = {slot_no:Count,photo_id:ID|null,status:SlotStatus,diagnostics:Diagnostic[],points:Keypoint[],angles:Angle[],engine?:PoseModel & {actual_model_sha256:string,contract_version:string},world_points?:{point_no:Count,name:string,x_m:Number,y_m:Number,z_m:Number,confidence:Number}[],world_angles?:{side:Side,angle_code:string,label:string,value_deg:Number|null,coordinate_space:string,used_for_reba:false}[],connections?:[string,string][]};
type PoseResult = {status:'RUNNING'|'DONE'|'PARTIAL_REVIEW'|'FAILED'|'CANCELED',valid_count:Count,total_slot_count:Count,terminal_error:string|null,slots:SlotPoseResult[]};
type TagCode = 'NECK_FORWARD_PROXY'|'TRUNK_FLEX'|'TRUNK_EXT'|'UPPER_ARM_RAISE'|'HAND_ABOVE_HEAD'|'ELBOW_ABOVE_SHOULDER'|'ELBOW_BEHIND_TRUNK'|'NECK_TWIST'|'TRUNK_TWIST'|'SQUAT'|'KNEEL';
type SlotTag = {slot_no:Count,tag:TagCode,value:Truth,source:'ANGLE'|'MANUAL'|'UNKNOWN'};
type TagSummary = {tag:TagCode,yes_count:Count,observed_count:Count,valid_pose_count:Count,manual_observed_count:Count,total_slot_count:Count,sample_ratio:Number|null};
type TagResult = {slots:SlotTag[],summary:TagSummary[]};
type ReviewReason = 'COMBINATION_RULE'|'POSTURE_INTERPRETATION'|'BOUNDARY_REVIEW'|'INPUT_CONFLICT';
type RebaCandidate = {slot_no:Count,photo_id:ID|null,scope:'COMMON'|'LEFT'|'RIGHT',field:'trunk_base'|'upper_arm_base'|'lower_arm_base'|'knee_band',proposed_value:Count|KneeBand|null,angles:Angle[],min_confidence:Number|null,review_reasons:ReviewReason[],diagnostics:Diagnostic[]};
type Risk = 'NEGLIGIBLE'|'LOW'|'MEDIUM'|'HIGH'|'VERY_HIGH';
type RebaSideScore = {
  side:Side,trunk:Count|null,neck:Count|null,legs:Count|null,table_a:Count|null,load_score:Count|null,score_a:Count|null,
  upper_arm:Count|null,lower_arm:Count|null,wrist:Count|null,table_b:Count|null,coupling_score:Count|null,score_b:Count|null,
  table_c:Count|null,activity_score:Count|null,total:Count|null,risk:Risk|null,missing_fields:string[],review_reasons:ReviewReason[]
};
type RebaSlotResult = {slot_no:Count,photo_id:ID|null,candidates:RebaCandidate[],load_state:LoadState,effective_load_kg:Number|null,status:'COMPLETE'|'INCOMPLETE',left:RebaSideScore,right:RebaSideScore,selected_side:Side|null,total:Count|null,risk:Risk|null,missing_fields:string[]};
type RebaSummary = {complete_count:Count,total_slot_count:Count,available_max:Count|null,full_max:Count|null,representative_slot_no:Count|null,selection:'AUTO'|'MANUAL'|null};
type RebaResult = {status:'COMPLETE'|'INCOMPLETE',slots:RebaSlotResult[],summary:RebaSummary};
type BasisItem = {item_code:string,value:Number|Truth|null,unit:'MIN_DAY'|'KG'|'KG_EQUIV'|'COUNT_DAY'|'COUNT_MIN'|'COUNT_HOUR'|'MONTH'|'COUNT_YEAR'|'BOOLEAN',operator:'GE'|'LE'|'EQ'|'OR'|null,threshold:Number|null,source:string};
type InvestigatorConclusion = {criterion_no:Count,status:FinalStatus|null,reason:string|null,evidence:Evidence,reviewer:string|null,reviewed_at:Timestamp|null};
type Judgment = {criterion_no:Count,computed_status:JudgmentStatus,exclusion:'SHORT_TERM'|'INTERMITTENT'|'BOTH'|null,basis:BasisItem[],missing_fields:string[],review_reasons:ReviewReason[],source:string,investigator:InvestigatorConclusion,effective_status:JudgmentStatus};
type JudgmentResult = {judgments:Judgment[]};
type AnalysisV2 = {
  analysis_id:ID,task_id:ID,input_revision:Count,snapshot:TaskSnapshot,status:JobStatus,
  module_states:ModuleStates,pose:PoseResult|null,slot_tags:SlotTag[],tags:TagSummary[],
  reba:RebaResult|null,judgment:JudgmentResult|null,ai:AiText[],notes:Diagnostic[],
  created_at:Timestamp,finished_at:Timestamp|null,currentness:Currentness
};
type RunHandle = {analysis_id:ID,task_id:ID,status:JobStatus};
type Warning = {criterion_no:Count,from:'COMPUTED'|'INVESTIGATOR',message:string};
type Analysis = AnalysisV2 | LegacyAnalysisV13; // §10의 이전 계약에서 가져오는 별칭
type TaskResult = {task:Task,currentness:Currentness,analysis:Analysis|null,warnings:Warning[],review_current:boolean};
~~~

Analysis는 AnalysisV2 또는 §10의 이전 Analysis 읽기 타입에 별칭을 붙인 LegacyAnalysisV13이다. 실행 FINISHED는 요청 처리 종료이며 계산 완전성·조사자 검토와 별개다.

scope=false는 NOT_REQUESTED, scope=true이며 결과가 없으면 NOT_CALCULATED다. 요청한 pose의 대상 0건은 FAILED, 요청한 reba/tags의 대상 0건은 INCOMPLETE와 NO_ANALYSIS_TARGET 진단이다. 빈 배열을 완성으로 처리하지 않는다. judgment는 11개 초안에 입력/검토 필요가 없으면 COMPLETE, 있으면 INCOMPLETE다. pose/tags/reba의 완전성 판정은 기능정의서 §6을 따른다. scope는 서로 독립적이다. pose 없이 reba를 요청하면 확인된 수동값으로 평가하고, tags는 직접 관찰 태그만 사용한다. 의존 기능을 조용히 자동 요청하지 않는다.

CURRENT는 input_revision과 latest_analysis_id가 모두 일치할 때다. 시작 때 최신 포인터를 설정하며 늦은 완료가 되돌리지 않는다. 재계산은 새 snapshot/행을 만들고 RUNNING 결과를 재사용하지 않는다. 의존 비교와 입력 변경의 영향은 기능정의서 §6을 따른다.

## 6. GPT와 설정

~~~typescript
type AiPurpose = 'TASK_EXPLANATION'|'IMPROVEMENT_ADVICE';
type NumericCriterion = {
  criterion_no:Count,computed_status:JudgmentStatus|null,investigator_status:FinalStatus|null,
  effective_status:JudgmentStatus|null,effective_source:'COMPUTED'|'INVESTIGATOR'|null,
  exclusion:'SHORT_TERM'|'INTERMITTENT'|'BOTH'|null,missing_fields:string[],review_reasons:ReviewReason[],
  basis:Omit<BasisItem,'source'>[]
};
type NumericSummary = {
  schema_version:'2.0',purpose:AiPurpose,rule_version:string,module_states:ModuleStates,requested_scope:AnalysisScope,
  pose_quality:{target_count:Count,valid_count:Count|null},
  reba:{complete_count:Count|null,available_max:Count|null,full_max:Count|null},
  tag_counts:TagSummary[],criteria:NumericCriterion[],public_rule_text:string[]
};
type ExplanationContent = {
  summary:string,criteria:{criterion_no:Count,explanation:string,basis_refs:string[]}[],
  check_items:string[],improvement_options:{proposal:string,basis_refs:string[],needs_confirmation:boolean}[]
};
type AiText = {
  text_id:string,is_active:boolean,purpose:AiPurpose,result:'GENERATED'|'FALLBACK'|'DISABLED',
  generated_text:string|null,edited_text:string|null,applied_text:string|null,
  applied_kind:'MODEL'|'INVESTIGATOR'|'FALLBACK'|null,content:ExplanationContent|null,
  input_summary:NumericSummary,model:string,reasoning_effort?:string,connection?:AiConnection|null,prompt_version:string,created_at:Timestamp,edited_at:Timestamp|null,applied_at:Timestamp|null,fallback_reason:string|null
};
type AiTextView = {text:AiText,source_current:boolean};
type UiPreferences = {loco_visible:boolean,loco_mode:'normal'|'quiet'};
type AiConnection = {response_id:string|null,model:string,reasoning_effort:string|null,requested_reasoning_effort:string};
type AiSettingsContract = {version:string,fields:{key:string,label:string,kind:'boolean'|'text'|'choice'|'number'|'integer',default:boolean|string|number,env?:string,choices?:{value:string,label:string}[]}[],defaults:Record<string,boolean|string|number>};
type PoseContract = {version:string,models:Record<string,PoseModel>,fields:object[],defaults:PoseModel,landmarks:Record<string,string[]>,connections:Record<string,[string,string][]>,world_angles:object[]};
type Settings = {analysis:AnalysisSettings,gpt_enabled:boolean,gpt_model:string,gpt_reasoning_effort:string,gpt_timeout_seconds:number,gpt_max_output_tokens:Count,gpt_contract:AiSettingsContract,pose_contract:PoseContract,gpt_key_present:boolean,ui:UiPreferences};
type SettingsUpdate = Omit<Settings,'gpt_key_present'|'gpt_contract'|'pose_contract'>;
~~~

서비스가 저장된 결과로 NumericSummary를 만든다. 원본 사진·좌표·이름·경로·자유입력 근거·내부 ID·사용자 행 label을 보내지 않는다. item_code는 서비스가 만든 비식별 항목 코드이며 basis_refs는 이 코드를 참조한다. rule_version은 고시/REBA/기술프로필 버전을 함께 나타내는 고정 문자열이다. 기술태그를 법적 확정 각도로 표현하지 않는다.

Python의 Responses API와 Structured Outputs 대응 모델을 사용한다. 모든 응답 필드를 required, additionalProperties=false로 정의한다. 설명 응답에 판정·점수 변경 필드를 두지 않는다. criteria는 1~11호를 각각 한 번 포함한다. 잘못된/중복/누락 호 번호·basis_refs·스키마는 대체 설명으로 처리한다. Responses API의 text.format에 type=json_schema, strict=true와 스키마를 지정한다. 구조 적합이 내용 정확성을 보장하지 않으므로 생성문은 조사자가 편집·적용한다.
[OpenAI 공식 문서](https://developers.openai.com/api/docs/guides/structured-outputs)

입력 정리·후속 질문·설명은 `ergo/ai_config.py`의 공통 AI 설정을 쓴다. 모델·추론 강도·요청 시간·출력 토큰은 설정 화면 또는 환경변수로 지정한다. 공통 초기값은 gpt-6-luna / xhigh / 180초 / 32768토큰(추론 포함)이며, 저장된 설정이 환경 기본값보다 우선한다. SDK 자동 재시도는 끈다. 키 없음/통신 실패/거절/불완전 응답은 FALLBACK과 이유, 설정 비활성은 DISABLED다. 로컬 계산은 유지한다. 키는 Python 환경 OPENAI_API_KEY에서 받고 DB/renderer/배포물에 넣지 않는다. 모델 ID는 설정으로 고정하고 실제 계정에서 접근을 확인한다.

ai는 생성 요청별 text_id를 가진 이력 배열이다. 생성은 새 레코드를 추가하며 기존 편집/적용본을 덮어쓰지 않는다. 생성/편집/적용본과 input_summary를 보존한다. 편집·적용은 text_id를 지정한다. 적용하면 같은 목적의 기존 is_active를 false, 대상 is_active를 true로 원자적으로 바꾸고 과거 applied_text는 보존한다. DISABLED 또는 텍스트 없는 레코드는 적용하지 않는다. 실패/비활성은 기존 활성 적용문을 지우지 않는다. 같은 목적의 현재 요약과 레코드의 input_summary를 값 비교해 source_current를 반환한다. 생성 후 계산이 바뀌면 이전 결과 설명으로 표시한다.

## 7. 서비스 호출

반환은 Result<T>다. type LegacyAnalysisV13은 §10의 고정 이전 계약에서 가져오는 외부 별칭이며 아래 타입 예시와 함께 해석한다. 현재 코드에 같은 메서드명이 있어도 2.0 계약이 구현됐다는 뜻은 아니다.

| method | params | value |
|---|---|---|
| list_surveys | 없음 | SurveySummary[] |
| create_survey / update_survey | draft / survey_id,draft. OCCASIONAL은 occasional_cause 필수 | Survey |
| get_survey / delete_survey | survey_id | Survey / Ack |
| set_survey_review | survey_id,review | Survey |
| list_tasks | survey_id | Task[] |
| create_task | survey_id,draft:TaskDraft | Task |
| save_task_input | task_id,input:TaskInput,expected_revision?:Count | Task |
| get_task / delete_task | task_id | TaskInputBundle / Ack |
| rename_task | task_id,task_name | Task |
| set_task_conditions | task_id,conditions:TaskConditions | Task |
| set_task_profile | task_id,input_template,worker_count | Task |
| set_legal_inputs | task_id,legal:LegalInputs | Task |
| set_analysis_scope | task_id,scope:AnalysisScope | Task |
| import_photos | task_id,file_paths:string[] | ImportReport |
| get_photo_preview | photo:PhotoInfo | PhotoPreview |
| update_photo | photo_id,file_path,consent:Truth | PhotoInfo |
| delete_photo | photo_id | Ack |
| set_capture | task_id,capture:CaptureSet | Task |
| set_manual_values | task_id,manual:ManualValue[] | Task |
| start_analysis | task_id | RunHandle |
| get_analysis / cancel_analysis | analysis_id | Analysis / RunHandle |
| recalculate_reba / recalculate_judgments / recalculate_tags | task_id | AnalysisV2 |
| list_analysis_history | task_id | Analysis[] |
| get_task_result | task_id | TaskResult |
| select_representative | analysis_id,slot_no | Analysis |
| set_investigator_conclusion | analysis_id,conclusion:InvestigatorConclusion | Analysis |
| generate_ai_text | analysis_id,purpose?:AiPurpose (기본 TASK_EXPLANATION) | AiTextView |
| edit_ai_text | analysis_id,text_id,text | AiTextView |
| apply_ai_text | analysis_id,text_id,use_edited:boolean | AiTextView |
| preview_excel | survey_id,analysis_ids:ID[],comparisons:ComparisonSpec[] | ReportOverview |
| export_excel | survey_id,spec:ExportSpec | ExportReceipt |
| list_export_logs | survey_id | ExportLogItem[] |
| get_settings / update_settings | 없음 / settings:SettingsUpdate | Settings |
| quick_preview | task_id,views:{LEFT?,FRONT?,RIGHT?:ID} | QuickPreview (저장하지 않음: 사진별 관절·방향 추정, 측면 근측 범주, 정면·후면 기울임 제안, 부담 없음 가정 1차 REBA, 규칙 기반 질문) |
| preview_excel_sheets | survey_id,analysis_ids?,comparisons? (preview_excel과 같은 선택) | ExcelPreview {sheets:[{name,title,lead,tables:[{heading,columns,rows,widths,header?,labels?,label_rows?,label_cells?,merges?,bordered?,heights?,break?,photo?}],notes,tab_color?}]} (저장하지 않음: export_excel이 만드는 시트와 같은 내용. 양식 표는 header·labels·merges 같은 선택 키로 그린다. 대표 사진 이미지만 파일에만 들어간다) |
| quick_interpret | text (1~600자 작업 설명 한 문장) | QuickIntake {items,dropped,reason} (저장하지 않음: 문장을 조사표 칸으로 옮긴 값. 모든 값은 문장 속 근거 구절과 함께 오며 근거가 문장에 없거나 범위를 벗어난 값은 버린다. 문장만 AI에 보내고 별도 스레드로 응답한다) |

| intake_contract | 없음 | AdaptiveIntakeContract {version,session_key,methods,policy,states,sources,ai_states,fields} |
| intake_session | task_id,views? | AdaptiveIntakeState (세션 복원·사진 측정 자동 저장·현재 추가 질문) |
| intake_turn | task_id,text?,answers?,expected_revision?,plan?,focus?,task_created_at? | AdaptiveIntakeState (직접 답변 우선 저장, AI 추출·추가 질문, 실패 대체) |

적응형 입력의 DTO·상태·단위·조건별 연결·저장 의미는 [적응형 추가 확인 계약](adaptive-intake.md)을 따른다. `conditions.intake_session`은 선택 JSON 메타데이터이며 실제 입력은 기존 legal/capture/manual/conditions에도 기록한다. `intake_contract`가 내보내는 변수와 catalogue를 프론트·서비스·AI 응답 schema가 공유한다.

AdaptiveIntakeState의 `ai`는 실제 마지막 요청의 상태·응답 모델·요청/응답 추론 강도·실패 사유·시각·응답 ID다. 설정/키 존재와 실제 응답 성공을 구분한다. 기본 질문 수는 정책 변수로 하나이며, 입력 추출을 반영한 뒤 남은 누락으로 후속 질문을 만든다. 응답 실패 시 저장한 입력/문장을 유지하고 팝업에서 재시도한다.

재계산 요청은 해당 모듈 scope=true의 명시적 요청이다. scope가 바뀌면 revision을 한 번 갱신해 새 분석을 만들고 다른 scope는 유지한다. GPT는 별도 스레드에서 같은 request_id로 응답해 일반 요청 읽기를 막지 않는다.

set_capture는 slot_no/photo_id로 교체를 비교한다. 순서 zip이나 배열 인덱스로 비교하지 않는다. 사진 내용 교체는 새 photo_id이며 해당 관찰/manual을 초기화한다. 카메라 변경은 해당 slot, 작업자/방법/작업 높이 변경은 관련 관찰/manual을 재확인한다. 모델/전처리 변경은 AUTO_ACCEPTED만 해제한다.

같은 사진의 경로 재연결은 update_photo로 manual/observation을 보존한다. 배정된 경로 변경은 revision을 한 번 올리고 동의만 바꾸면 유지한다. 원본 바이트 동일성을 보증하는 기능은 아니다.

delete_photo는 배정 해제·관찰 초기화·대상 manual 제거·PHOTO 삭제를 같은 트랜잭션으로 처리한다. 현재 입력이 바뀐 경우에만 revision을 한 번 올린다. 없는 사진 삭제는 Ack다. 조사자 결론 변경과 전체 reviewed=false도 같은 트랜잭션이다. 대표/설명 편집은 계산 검토 표시를 유지한다.

## 8. 보고서·전후 비교

~~~typescript
type ComparisonSpec = {before_analysis_id:ID,after_analysis_id:ID,note:string|null};
type ExportSpec = {destination:string,analysis_ids:ID[],include_representative:boolean,comparisons:ComparisonSpec[]};
type ReportState = {reviewed:boolean,review_current:boolean,has_incomplete:boolean,has_stale:boolean,survey_input_complete:boolean};
type ReportCounts = {needs_input_count:Count|null,needs_review_count:Count|null,incomplete_reba_count:Count|null};
type NextInputItem = {module:'ANALYSIS'|'POSE'|'TAGS'|'REBA'|'BURDEN'|'EXPLANATION',kind:'NOT_CALCULATED'|'MISSING_INPUT'|'REVIEW_REQUIRED',slot_no:Count|null,criterion_no:Count|null,field_paths:string[],reason_codes:string[],message:string};
type ReportTaskOverview = {
  task_id:ID,task_name:string,analysis_id:ID|null,input_revision:Count,source_schema_version:'1.3'|'2.0',
  currentness:Currentness,module_states:ModuleStates|null,state:ReportState,
  review_status:'NO_ANALYSIS'|'UNREVIEWED'|'REVIEWED_CURRENT'|'REVIEWED_HISTORY',
  counts:ReportCounts,next_inputs:NextInputItem[]
};
type ComparisonOverview = {
  spec:ComparisonSpec,before_task_id:ID,after_task_id:ID,rule_compatible:boolean,sampling_compatible:boolean,
  reba_max_delta:Number|null,criteria:{criterion_no:Count,before_computed_status:JudgmentStatus|null,before_investigator_status:FinalStatus|null,before_status:JudgmentStatus|null,after_computed_status:JudgmentStatus|null,after_investigator_status:FinalStatus|null,after_status:JudgmentStatus|null}[],
  condition_changes:{field_path:string,before:unknown,after:unknown}[],notes:string[]
};
type ReportOverview = {report_version:'2.0',state:ReportState,counts:ReportCounts,tasks:ReportTaskOverview[],comparisons:ComparisonOverview[],survey_followups:string[]};
type ExportSnapshot = {
  schema_version:'2.0',report_version:'2.0',survey:Survey,tasks:Task[],analyses:Analysis[],unanalysed_task_ids:ID[],
  include_representative:boolean,comparison_specs:ComparisonSpec[],comparison_analyses:Analysis[],exported_at:Timestamp
};
type RenderedReport = {file_path:string,sheets:string[],overview:ReportOverview};
type ExportReceipt = ReportState & {export_id:ID,file_path:string,sheets:string[],created_at:Timestamp,report_version:'2.0'};
type ExportLogItem = {export_id:ID,survey_id:ID,file_path:string,receipt:ExportReceipt,created_at:Timestamp};
~~~

일반표는 현존 모든 task를 포함한다. 분석을 명시 선택하지 않은 작업은 최신 분석 또는 미분석으로 표시한다. 선택 ID는 해당 작업 소속이어야 하며 한 작업에서 두 개를 일반표에 선택하면 오류다. 비교는 같은 survey의 서로 다른 두 분석이다. 비교용 앞뒤 분석은 일반표의 한 작업 한 분석 선택과 별도로 comparison_analyses에 모두 복사한다. 과거 자료도 비교하되 재계산하지 않는다.

REBA 규칙·프로토콜·대상 수·전체 완성을 비교해 호환될 때만 full_max의 후−전을 reba_max_delta로 제공한다. 그 밖에는 null과 이유다. rule_compatible은 고시/REBA 규칙이 모두 같을 때 true다. REBA 차이에는 REBA 규칙 호환성과 sampling_compatible을 사용하고, 고시 버전 차이는 호별 비교 제한으로 별도 표시한다. sampling_compatible은 같은 프로토콜·동일한 양의 대상 수·양쪽 전 대상 REBA 완성이다. 조건 차이·사진 대표성 한계를 표시하며 질환/산재 감소의 증명으로 표현하지 않는다.

출력 시트는 같은 snapshot으로 `plain_sheets`가 만드는 시트 정의 목록이며 Excel 파일과 `preview_excel_sheets` 미리보기가 같은 정의를 쓴다. 공식 서식 구성 시트가 앞에 오고 보조 시트가 뒤에 온다. 서식 구성의 근거는 고용노동부고시 제2020-12호 별지 제1·2호서식과 한국산업안전보건공단 KOSHA GUIDE E-G-1-2025다. 출력 영수증의 sheets에는 실제 생성된 시트를 순서대로 저장한다. 이 시트는 입력 자료 기반 참고 자료이며 누락·원본 서식 대조·서명/날인·조사자 검토를 대신하지 않는다. 셀은 일반인이 읽는 말로 쓰고 저장 코드·내부 경로는 쓰지 않는다(저장 값은 출력 snapshot에 그대로 있다). 앱에 입력란이 없는 서식 칸(근로자명, 증상조사표의 빈도·조치 문항 등)은 비워 둔다.

| 시트 | 조건 | 내용 |
|---|---|---|
| 유해요인조사표 | 항상 | 별지 제1호서식 구성. 가 조사 개요(조사 구분·수시조사 사유 ☑/☐, 조사 일시·조사자·조사부서명·작업공정명·작업명, 이전 조사일, 근로자 참여), 나 작업장 상황(설비·작업량·작업속도·업무형태의 변경 여부와 주요 변경 내용), 다 작업조건(1단계 작업명·작업내용, 2단계 작업강도 A·작업빈도 B 척도와 작업별 부담작업(호)·A×B, 3단계 근로자명·대표 사진·유해요인별 발생 원인, 3-1 REBA 결과와 표준 판정 문구는 점수가 있을 때), 라 결과 요약(작업별 부담작업·자세 점수·더 입력할 것·결과 기준·검토 상태, 증상조사 요약, 조사자 종합 의견 빈 칸) |
| 부담작업 해당 여부 | 항상 | 11개 호마다 법정 기준 문구, 입력한 값과 기준을 견준 표(○/X), 최종 판단, 조사자 결론·더 필요한 입력·확인할 점 |
| 체크리스트 | 항상 | 작업 × 11개 호 매트릭스(○ 해당, X 해당하지 않음, 입력 필요, 검토 필요)와 호별 기준 한 줄 |
| 증상조사표 | 익명 응답이 있을 때 | 별지 제2호서식 구성. 응답마다 기본 정보 표와 6개 부위 × (구체적 부위·통증 기간·아픈 정도·지난 1주일) 표 |
| 자세 분석(REBA) | 항상 | 사진별 REBA 구성점수, 읽은 각도, 자세 표시 |
| 입력한 값 | 항상 | 계산에 쓴 값과 입력 방법·메모 |
| 확인사항 | 항상 | 더 입력하거나 확인할 사항 |
| 쉬운 설명 | 적용한 설명이 있을 때 | 적용한 AI·조사자 설명 |
| 개선 전후 비교 | 비교를 골랐을 때 | 기준별 변화와 바뀐 입력 |

시트 정의 `{name,title,lead,tables,notes,tab_color?}`의 표는 `{heading,columns,rows,widths}`와 선택 키 `header`(False면 헤더 행 없음), `labels`·`label_rows`·`label_cells`(양식의 칸 이름 칸), `merges`([첫 행,첫 열,끝 행,끝 열]), `bordered`, `heights`, `break`(앞에서 쪽 나눔), `photo`({task_id,row}, 대표 사진을 넣을 칸)를 가질 수 있다. 대표 사진 이미지는 `유해요인조사표` 3단계 사진 칸에만 들어가며 파일에만 있다. 비교 블록은 정렬 표 밖에 두고 조건 차이/비교 제한은 확인사항에도 표시한다.

needs_input_count/needs_review_count는 computed_status별 기준 수(작업당 0~11)다. judgment 미계산이면 null이며 조사 집계에 null이 있으면 합계도 null이다. incomplete_reba_count는 요청하고 계산한 REBA의 N−complete_count다. 미계산/미요청은 null로 두고 상태로 구분한다. 요청 대상 0건은 0과 NO_ANALYSIS_TARGET을 함께 표시한다. REBA 조사 합계는 전체 미요청이면 null, 요청 작업 중 미계산이 있으면 null, 나머지는 요청·계산한 작업의 수를 더한다.

has_incomplete는 요청 모듈의 NOT_CALCULATED/RUNNING/INCOMPLETE/FAILED/CANCELED에서 산출하고 NOT_REQUESTED는 제외한다. 분석 없음은 true다. GPT 실패/이전 설명은 확인사항이며 계산 완전성을 바꾸지 않는다. has_stale는 선택 분석의 STALE 여부다.

reviewed는 선택 ID가 검토 목록에 있고 reviewed=true일 때다. review_current는 여기에 metadata_revision 일치와 CURRENT까지 만족할 때다. 조사 전체 reviewed/review_current는 작업이 1건 이상이고 모두 true일 때, incomplete/stale는 하나라도 true일 때다. 작업 0건이면 네 값 모두 false다.

report.build_overview(snapshot)의 같은 집계/안내를 UI·Excel·receipt에서 사용한다. 미리보기는 파일/로그를 만들지 않고 실제 출력은 호출 시점 snapshot을 사용한다. 안내는 누락/진단/검토 사유에서 사진 label·좌우·기준 번호를 붙여 생성하며 GPT를 사용하지 않는다. 긴 근거는 생략하지 않고 행을 분리한다. Excel 문자열은 수식이 아닌 문자열로 쓰며 숫자/날짜는 해당 형식을 사용한다.

## 9. 오류·저장 경계

파일/DB/API 실행 실패와 없는 ID는 AppError, 사진 불량은 slot 진단, 입력 부족/모순은 missing_fields/review_reasons다. GPT 외부 실패는 원칙적으로 FALLBACK을 반환하고 저장까지 실패하면 DB_ERROR다.

입력 부족이어도 저장·검토·초안 출력을 계속한다. 계산 null과 실행 오류를 구분한다. 계산 저장은 계산 경로만, 표시 편집은 해당 경로만 갱신한다. 서로 다른 스레드가 오래된 result_json 전체를 덮어쓰지 않는다. 늦은 완료로 삭제된 행을 재생성하지 않는다.

## 10. 1.3 호환·현재 구현

LegacyTaskV13/LegacyAnalysisV13/LegacyExportSnapshotV13은 [기존 자료 읽기 계약](legacy-compatibility.md)의 읽기 전용 JSON 별칭이다. 이전 실행 서버나 가짜 Protocol을 호출하지 않는다. 저장된 1.3 snapshot의 15슬롯·회차·순간·사건 하중·당시 규칙은 그대로 읽고 과거 의미로 표시한다. 새 일반 프로토콜의 결과로 라벨을 바꾸지 않는다.

get_task/list_tasks는 메모리상 2.0 편집 DTO로 읽고 get_task는 source_schema_version을 함께 반환한다. 기존 사진과 알려진 수동값을 보존하고 사건명은 사진 label의 역사 정보로 남긴다. 기존 중량·조건·20종 시간의 관련값은 조건 행/union으로 옮긴다. 이전 TASK.input_json 전체를 legacy_input에 복사해 변환하지 않은 원문도 보존한다. 사진 비율 등 환산값은 새 직접수치에 null을 넣고 이전 원문과 재확인 진단으로 남긴다. 새 측면 확인·행 망라성·일반 사진 실제 하중은 UNKNOWN/null로 둔다. 과거 사진 하중을 새 측정값으로 추측하지 않는다.

명시 저장 때에만 TASK 입력을 2.0으로 쓰고 revision을 한 번 올린다. 새 분석은 2.0이며 과거 조사자 결론·설명·검토를 자동 승계하지 않는다. 과거 분석 열람/출력은 legacy adapter와 당시 버전을 사용한다. 호환되지 않는 비교는 null과 이유다. 물리 DB 일괄 migration은 하지 않는다.

검토 출발점 e7b0cf1의 main은 일반 조건 행·가변 사진·module_states·실제 GPT API·전후 비교·한글 4시트를 구현하지 않았다. 코드 수정과 독립 검증은 10/23 개발 범위이며 문서 수정만으로 완료 처리하지 않는다.


로컬 구현 보완: save_task_input의 expected_revision을 지정하면 최신 revision과 다를 때 저장하지 않고 최신 입력 재확인을 안내한다. 작업 편집기는 조건·법령·분석 범위 등 자신이 편집하는 필드만 최신 DTO에 합치며 사진·수동값은 해당 화면의 최신값을 보존한다. 검토 기록의 history는 JSON에 추가 보존하며 물리 migration은 없다. 자세한 실행·검증 증거는 local-verification.md를 따른다.

모듈 구성과 의존 방향은 [모듈 지도](module-map.md)를 따른다. 설정 화면에서 관절 신뢰도와 기술각도를 명시 저장하면 관련 2.0 작업 revision이 한 번 증가한다. 계산 규칙/공식 모델 식별값은 구현과 다른 문자열로 바꿀 수 없다. 설명 목적은 생성·현재성·활성 적용을 각각 분리한다.

전후 비교의 condition_changes는 작업 조건·분석 범위·법령 입력뿐 아니라 사진 배정/관찰, 수동 확인값, 분석 설정의 차이를 포함한다. 같은 프로토콜·양의 대상 수·양쪽 전체 완성·호환 REBA 규칙일 때만 후−전 점수 차이를 표시한다. 수동값/관찰/설정 변경을 생략해 동일 조건의 효과로 오인하게 하지 않는다.

AI 설정 필드·기본값·환경변수·선택값의 단일 계약은 `get_settings.gpt_contract={version,fields,defaults}`다. `gpt_contract`와 `gpt_key_present`는 읽기 메타데이터로 DB에 저장하지 않는다. 이전 설정의 누락 필드는 공통 기본값으로 읽고 기존 명시값과 분석 snapshot은 보존한다. 실제 응답 메타데이터는 입력 session.last_ai 및 설명 connection에 저장한다. 설정 변경 후 이전 호출을 새 설정의 연결 성공으로 표시하지 않는다.

## MediaPipe 자세 엔진 개정 (2026-10-22)

자세 엔진·설정·출력의 현행 계약은 [자세 엔진 계약](pose-engine.md)을 따른다. MoveNet 고정 입력/관절/해시 표기는 이전 엔진에 해당한다. 기본 엔진은 MediaPipe Heavy(33점), Full은 비교/선택 가능하며 과거 MoveNet snapshot의 의미는 보존한다. 설정과 프론트는 공통 registry를 소비하고 REBA/11개 계산은 기존 규칙을 유지한다. world_points/3D 분절각은 별도 추정 후보이며 점수에 자동 혼합하지 않는다.
