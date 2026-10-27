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
| report | 같은 snapshot의 기록 데이터 전용 한글 시트·상태·다음 입력·전후 비교; 법정 서식 완성 증명은 아님 |
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
type SurveyDraft = {survey_type:SurveyType,survey_date:Date,investigator:string,department:string,process:string,title:string,previous_survey_date:Date|null};
type ReviewRecord = {reviewed:boolean,reviewed_analysis_ids:ID[],reviewed_metadata_revision:Count|null,reviewer:string|null,reviewed_at:Timestamp|null,note:string|null};
type ReviewMark = ReviewRecord & {history?: (ReviewRecord & {archived_at:Timestamp,reason:string})[]};
type Survey = SurveyDraft & {survey_id:ID,metadata_revision:Count,review:ReviewMark,created_at:Timestamp,updated_at:Timestamp,survey_type_source:'USER'|'DEFAULT'|'UNKNOWN'};
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

하중은 관찰한 UNLOADED이면 0, MEASURED이면 측정 kg, UNKNOWN이면 null이다. 상태와 측정값의 충돌은 진단한다. 사건명이나 사진 순서로 전체 물체 중량을 적용하지 않는다. 하중을 기준 8~10호의 하루 값에 자동 전사하지 않는다. 목·손목 편위/비틀림·지지·쥐기·충격·활동은 현장 확인값이다. 손목 굽힘·폄은 아래 2D 관측 조건을 만족한 사진 후보와 직접 확인값을 구별한다.

자동 후보는 몸통/무릎/좌우 위팔·아래팔 6개에 공급자가 손 관절을 제공하면 좌우 wrist_base를 추가한다. 일반 편집은 적용할 때 AUTO_ACCEPTED로 저장하며 간편 확인에서는 사진 상황을 확인한 뒤 고품질 후보만 저장하고 질문에서 제외한다. null/경계 후보는 기존값을 덮어쓰지 않는다. 관찰 복사는 사용자가 고른 필드와 사진에만 적용한다. 근거·시각·대상 photo_id를 기록한다. ManualField별 허용 scope·범주·숫자 범위는 기능정의서 §5.1을 따른다.

## 5. 분석 DTO와 상태

~~~typescript
type ModuleState = 'NOT_REQUESTED'|'NOT_CALCULATED'|'RUNNING'|'COMPLETE'|'INCOMPLETE'|'FAILED'|'CANCELED';
type ModuleStates = {pose:ModuleState,tags:ModuleState,reba:ModuleState,judgment:ModuleState};
type PoseModel = {model_id:string,provider:string,variant:string,name:string,version:string,preprocess_version:string,input_size:Count,point_count:Count,confidence_kind:string,model_path:string,model_sha256:string,confidence_min:Number,detection_min:Number,presence_min:Number};
type PostureProfile = {version:'POSTURE_TECH_V1',neck_forward_deg:Number,trunk_flex_deg:Number,trunk_extension_deg:Number,upper_arm_raise_deg:Number};
type AnalysisSettings = {pose_model:PoseModel,posture_profile:PostureProfile,reba_rule:'REBA_TABLE_2000_V2',burden_rule:'MOEL_2020_12_GENERAL_V2'};
type TaskSnapshot = TaskInput & {task_id:ID,input_revision:Count,photos:PhotoInfo[],settings:AnalysisSettings};
type SlotStatus = 'PENDING'|'VALID'|'INVALID'|'ERROR'|'CANCELED'|'NOT_PROCESSED';
type AngleCode = 'TRUNK_TILT_VERT'|'NECK_TILT_VERT_PROXY'|'NECK_FLEX_TRUNK_PROXY'|'UPPER_ARM_RAISE_VERT'|'UPPER_ARM_FLEX_TRUNK'|'ELBOW_FLEX'|'KNEE_FLEX'|'WRIST_FLEX_2D';
type Keypoint = {point_no:Count,name:string,x_px:Number,y_px:Number,confidence:Number,confidence_kind?:string,visibility?:Number,presence?:Number,z_normalized?:Number};
type Angle = {side:Side,angle_code:AngleCode,value_deg:Number|null,min_confidence:Number|null,diagnostic:string|null,diagnostic_code?:string,measurement?:{policy_version:string,coordinate_space:'ORIGINAL_IMAGE_2D',auto_eligible:boolean,hand_plane_method:string,used_world_coordinates:false,policy:Record<string,string|Number>,[quality:string]:unknown}};
type SlotPoseResult = {slot_no:Count,photo_id:ID|null,status:SlotStatus,diagnostics:Diagnostic[],points:Keypoint[],angles:Angle[],engine?:PoseModel & {actual_model_sha256:string,contract_version:string},world_points?:{point_no:Count,name:string,x_m:Number,y_m:Number,z_m:Number,confidence:Number}[],world_angles?:{side:Side,angle_code:string,label:string,value_deg:Number|null,coordinate_space:string,used_for_reba:false}[],connections?:[string,string][]};
type PoseResult = {status:'RUNNING'|'DONE'|'PARTIAL_REVIEW'|'FAILED'|'CANCELED',valid_count:Count,total_slot_count:Count,terminal_error:string|null,slots:SlotPoseResult[]};
type TagCode = 'NECK_FORWARD_PROXY'|'TRUNK_FLEX'|'TRUNK_EXT'|'UPPER_ARM_RAISE'|'HAND_ABOVE_HEAD'|'ELBOW_ABOVE_SHOULDER'|'ELBOW_BEHIND_TRUNK'|'NECK_TWIST'|'TRUNK_TWIST'|'SQUAT'|'KNEEL';
type SlotTag = {slot_no:Count,tag:TagCode,value:Truth,source:'ANGLE'|'MANUAL'|'UNKNOWN'};
type TagSummary = {tag:TagCode,yes_count:Count,observed_count:Count,valid_pose_count:Count,manual_observed_count:Count,total_slot_count:Count,sample_ratio:Number|null};
type TagResult = {slots:SlotTag[],summary:TagSummary[]};
type ReviewReason = 'COMBINATION_RULE'|'POSTURE_INTERPRETATION'|'BOUNDARY_REVIEW'|'INPUT_CONFLICT';
type RebaCandidate = {slot_no:Count,photo_id:ID|null,scope:'COMMON'|'LEFT'|'RIGHT',field:'trunk_base'|'upper_arm_base'|'lower_arm_base'|'knee_band'|'wrist_base',proposed_value:Count|KneeBand|null,angles:Angle[],min_confidence:Number|null,review_reasons:ReviewReason[],diagnostics:Diagnostic[]};
type Risk = 'NEGLIGIBLE'|'LOW'|'MEDIUM'|'HIGH'|'VERY_HIGH';
type RebaSideScore = {
  side:Side,trunk:Count|null,neck:Count|null,legs:Count|null,table_a:Count|null,load_score:Count|null,score_a:Count|null,
  upper_arm:Count|null,lower_arm:Count|null,wrist:Count|null,table_b:Count|null,coupling_score:Count|null,score_b:Count|null,
  table_c:Count|null,activity_score:Count|null,total:Count|null,risk:Risk|null,missing_fields:string[],review_reasons:ReviewReason[]
};
type RebaScoreSoFar = {total:Count,risk:Risk,selected_side:Side,left:Count,right:Count,assumed:string[],unconfirmed_photo?:string[],assumption:string};
type RebaCurrentScore = {total:Count,risk:Risk,kind:'CONFIRMED'|'WITH_ASSUMPTIONS'|'ASSUMED_REFERENCE',source:'COMPLETE'|'ANSWERS_SO_FAR'|'FIRST_PASS'|'ASSUMED_REFERENCE',slot_no:Count,complete_count:Count,total_slot_count:Count,assumed:string[],assumption:string};
type PhotoMeasurementQuality = {slot_no:Count,photo_id:ID|null,measured_points:Count,total_points:Count,mean_confidence:Number|null,confidence_level:'HIGH'|'MEDIUM'|'LOW'|'MISSING'};
type MeasurementQuality = {measured_points:Count,total_points:Count,mean_confidence:Number|null,confidence_level:'HIGH'|'MEDIUM'|'LOW'|'MISSING',slots:PhotoMeasurementQuality[]};
type RebaSlotResult = {slot_no:Count,photo_id:ID|null,candidates:RebaCandidate[],load_state:LoadState,effective_load_kg:Number|null,status:'COMPLETE'|'INCOMPLETE',left:RebaSideScore,right:RebaSideScore,selected_side:Side|null,total:Count|null,risk:Risk|null,missing_fields:string[],score_so_far?:RebaScoreSoFar,current_score?:RebaCurrentScore};
type RebaSummary = {complete_count:Count,total_slot_count:Count,available_max:Count|null,full_max:Count|null,representative_slot_no:Count|null,selection:'AUTO'|'MANUAL'|null,score_so_far?:RebaScoreSoFar&{slot_no:Count},first_pass?:RebaScoreSoFar&{photo_count:Count,slot_no:Count},current_score?:RebaCurrentScore};
type RebaResult = {status:'COMPLETE'|'INCOMPLETE',slots:RebaSlotResult[],summary:RebaSummary};
type BasisItem = {item_code:string,value:Number|Truth|null,unit:'MIN_DAY'|'KG'|'KG_EQUIV'|'COUNT_DAY'|'COUNT_MIN'|'COUNT_HOUR'|'MONTH'|'COUNT_YEAR'|'BOOLEAN',operator:'GE'|'LE'|'EQ'|'OR'|null,threshold:Number|null,source:string};
type InvestigatorConclusion = {criterion_no:Count,status:FinalStatus|null,reason:string|null,evidence:Evidence,reviewer:string|null,reviewed_at:Timestamp|null};
type Judgment = {criterion_no:Count,computed_status:JudgmentStatus,exclusion:'SHORT_TERM'|'INTERMITTENT'|'BOTH'|null,basis:BasisItem[],missing_fields:string[],review_reasons:ReviewReason[],source:string,investigator:InvestigatorConclusion,effective_status:JudgmentStatus};
type JudgmentResult = {judgments:Judgment[]};
type AnalysisV2 = {
  analysis_id:ID,task_id:ID,input_revision:Count,snapshot:TaskSnapshot,status:JobStatus,
  module_states:ModuleStates,pose:PoseResult|null,slot_tags:SlotTag[],tags:TagSummary[],
  reba:RebaResult|null,judgment:JudgmentResult|null,ai:AiText[],notes:Diagnostic[],measurement_quality?:MeasurementQuality,
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
type ProvisionalRebaInput = {total:Count,risk:string,photo_ids:ID[]};
type NumericSummary = {
  schema_version:'2.0',purpose:AiPurpose,rule_version:string,module_states:ModuleStates,requested_scope:AnalysisScope,
  pose_quality:{target_count:Count,valid_count:Count|null,measured_points:Count,total_points:Count,mean_confidence:Number|null,confidence_level:'HIGH'|'MEDIUM'|'LOW'|'MISSING'},
  reba:{complete_count:Count|null,available_max:Count|null,full_max:Count|null,current_score?:{total:Count,risk:Risk,kind:string,source:string,assumed_count:Count},first_pass?:{total:Count,risk:Risk,assumed_count:Count},score_so_far?:{total:Count,risk:Risk,assumed_count:Count,unconfirmed_photo_count?:Count,load_assumed?:boolean}},
  provisional_reba?:{assumption:string,analysis_currentness:'CURRENT'|'STALE',initial_total:Count,initial_risk:string,initial_photo_count:Count,final_photo_count:Count,same_photo_scope:boolean,final_complete:boolean,final_total:Count|null,final_risk:string|null,comparable:boolean,comparison_status:'COMPARABLE'|'STALE_ANALYSIS'|'FINAL_INCOMPLETE'|'DIFFERENT_PHOTO_SCOPE'|'MULTI_PHOTO_COMPOSITION',score_delta:Count|null},
  posture_results:{photo_ref:string,pose_status:string|null,pose_diagnostic_codes:string[],model:{name:string|null,version:string|null,provider:string|null}|null,landmark_count:Count,measurement_quality?:Omit<PhotoMeasurementQuality,'slot_no'|'photo_id'>,angles:{side:string,angle_code:string,value_deg:Number|null,min_confidence:Number|null,diagnostic:string|null}[],inferred_world_angles:{side:string,angle_code:string,value_deg:Number|null,min_confidence:Number|null,coordinate_space:'INFERRED_WORLD_3D',used_for_reba:false}[],reba_status:string|null,effective_load_kg:Number|null,selected_side:string|null,total:Number|null,risk:string|null,left:object,right:object,missing_fields:string[],candidates:object[]}[],
  tag_counts:TagSummary[],criteria:NumericCriterion[],public_rule_text:string[]
};
type ExplanationContent = {
  summary:string,reba_comparison:string,posture_explanations:{photo_ref:string,explanation:string}[],criteria:{criterion_no:Count,explanation:string,basis_refs:string[]}[],
  check_items:string[],improvement_options:{proposal:string,basis_refs:string[],needs_confirmation:boolean}[]
};
type AiText = {
  text_id:string,is_active:boolean,purpose:AiPurpose,result:'GENERATED'|'FALLBACK'|'DISABLED',
  generated_text:string|null,edited_text:string|null,applied_text:string|null,
  applied_kind:'MODEL'|'INVESTIGATOR'|'FALLBACK'|null,content:ExplanationContent|null,
  input_summary:NumericSummary,provisional_reba_input?:{total:Count,risk:string,photo_count:Count,photo_scope_sha256:string},model:string,reasoning_effort?:string,connection?:AiConnection|null,prompt_version:string,created_at:Timestamp,edited_at:Timestamp|null,applied_at:Timestamp|null,fallback_reason:string|null
};
type AiTextView = {text:AiText,source_current:boolean};
type UiPreferences = {loco_visible:boolean,loco_mode:'normal'|'quiet'};
type AiConnection = {response_id:string|null,model:string,reasoning_effort:string|null,requested_reasoning_effort:string};
type AiSettingsContract = {version:string,fields:{key:string,label:string,kind:'boolean'|'text'|'choice'|'number'|'integer',default:boolean|string|number,env?:string,choices?:{value:string,label:string}[]}[],defaults:Record<string,boolean|string|number>};
type PoseContract = {version:string,models:Record<string,PoseModel>,fields:object[],defaults:PoseModel,landmarks:Record<string,string[]>,connections:Record<string,[string,string][]>,world_angles:object[]};
type Settings = {analysis:AnalysisSettings,gpt_enabled:boolean,gpt_model:string,gpt_reasoning_effort:string,gpt_max_output_tokens:Count,gpt_contract:AiSettingsContract,pose_contract:PoseContract,gpt_key_present:boolean,ui:UiPreferences};
type SettingsUpdate = Omit<Settings,'gpt_key_present'|'gpt_contract'|'pose_contract'>;
~~~

서비스가 저장된 결과로 NumericSummary를 만든다. 간편 흐름이 보낸 1차 REBA 점수는 분석 snapshot에 포함된 사진인지 검증한 뒤, 미확인 자세 항목 부담 없음 가정·최종 REBA 완성도·사진 범위와 함께 선택적으로 요약한다. 사진 ID는 입력 검증에만 쓰고 모델 요약에는 보내지 않는다. 같은 단일 사진 범위에서 최종 전체 점수가 완성되고 분석이 현재 작업 입력과 일치하는 경우에만 차이를 계산한다. 분석이 오래되었으면 analysis_currentness='STALE', comparison_status='STALE_ANALYSIS', comparable=false, score_delta=null을 반환하고 저장된 과거 결과임을 설명한다. 다중 사진을 합친 1차 점수, 범위 불일치 또는 최종 미완성에서도 차이를 만들지 않는다. 익명 사진 참조와 사진별 각도·REBA 구성 결과를 포함해 자세 결과도 설명할 수 있게 한다. 원본 사진·관절 좌표·이름·경로·자유입력 근거·내부 ID·사용자 행 label은 보내지 않는다. 사진 AI의 자연어 관찰은 별도 5단계 화면에서만 검토한다. item_code는 서비스가 만든 비식별 항목 코드이며 basis_refs는 이 코드를 참조한다. rule_version은 고시/REBA/기술프로필 버전을 함께 나타내는 고정 문자열이다. 기술태그를 법적 확정 각도로 표현하지 않는다.

Python의 Responses API와 Structured Outputs 대응 모델을 사용한다. 모든 응답 필드를 required, additionalProperties=false로 정의한다. 1차 점수 입력이 있으면 응답에 reba_comparison 설명을 반드시 포함하며, 입력이 없으면 빈 문자열을 반환한다. 설명 응답에 판정·점수 변경 필드를 두지 않는다. criteria는 1~11호를 각각 한 번 포함한다. 잘못된/중복/누락 호 번호·basis_refs·스키마는 대체 설명으로 처리한다. Responses API의 text.format에 type=json_schema, strict=true와 스키마를 지정한다. 구조 적합이 내용 정확성을 보장하지 않으므로 생성문은 조사자가 편집·적용한다.
[OpenAI 공식 문서](https://developers.openai.com/api/docs/guides/structured-outputs)

입력 정리·후속 질문·설명·사진 관찰은 ergo/ai_config.py의 공통 AI 설정과 프로세스 공유 OpenAI client/HTTP 연결 풀을 쓴다. 모델·추론 강도·출력 토큰은 설정 화면 또는 환경변수로 지정한다. 공통 초기값은 gpt-6-luna / high / 32768토큰(추론 포함, 2026-10-26 소유자 지시로 xhigh에서 낮춤)이며, 저장된 설정이 환경 기본값보다 우선한다. 앱은 AI 요청 한 번을 120초까지만 기다리고, 그때까지 답이 없으면 같은 요청을 다시 보낸다(처음 포함 최대 3번, ergo/ai_config.py의 REQUEST_TIMEOUT_SECONDS·REQUEST_ATTEMPTS, 2026-10-26 소유자 지시). 시간 초과가 아닌 오류와 불완전 응답은 다시 보내지 않고 SDK 자동 재시도는 끈다. 구버전 gpt_timeout_seconds 저장값과 LOCO_AI_TIMEOUT_SECONDS 환경값은 호환을 위해 오류 없이 무시하며 새 Settings/gpt_contract 응답에는 포함하지 않는다. 키 없음/통신 실패/거절/불완전 응답은 FALLBACK과 이유, 설정 비활성은 DISABLED다. 로컬 계산은 유지한다. 키는 Python 환경 OPENAI_API_KEY에서 받고 DB/renderer/배포물에 넣지 않는다. 모델 ID는 설정으로 고정하고 실제 계정에서 접근을 확인한다.

provisional_reba_input은 현재성 재계산용 내부 요약값이며 photo_ids 원문은 보존하지 않고 GPT에 보내지 않는다. ai는 생성 요청별 text_id를 가진 이력 배열이다. 생성은 새 레코드를 추가하며 기존 편집/적용본을 덮어쓰지 않는다. 생성/편집/적용본과 input_summary를 보존한다. 편집·적용은 text_id를 지정한다. 적용하면 같은 목적의 기존 is_active를 false, 대상 is_active를 true로 원자적으로 바꾸고 과거 applied_text는 보존한다. DISABLED 또는 텍스트 없는 레코드는 적용하지 않는다. 실패/비활성은 기존 활성 적용문을 지우지 않는다. 같은 목적의 현재 요약과 레코드의 input_summary를 값 비교하고, 해당 분석이 최신 작업 입력·최신 계산 결과인지 확인해 source_current를 반환한다. 입력 또는 계산이 바뀐 과거 분석에는 source_current=false를 반환하고 REBA 차이를 계산하지 않으며, 생성 후 계산이 바뀌면 이전 결과 설명으로 표시한다.

## 7. 서비스 호출

반환은 Result<T>다. type LegacyAnalysisV13은 §10의 고정 이전 계약에서 가져오는 외부 별칭이며 아래 타입 예시와 함께 해석한다. 현재 코드에 같은 메서드명이 있어도 2.0 계약이 구현됐다는 뜻은 아니다.

| method | params | value |
|---|---|---|
| list_surveys | 없음 | SurveySummary[] |
| create_survey / update_survey | draft / survey_id,draft. 수시조사 사유·작업장 상황·근로자 참여·증상조사 필드(occasional_reason, occasional_cause, workplace_situation, participation, symptom_survey)는 받아도 무시하고 저장하지 않는다(2026-10-27 소유자 지시: REBA 계산과 그 값을 Excel로 주는 것까지만 한다). OCCASIONAL도 사유 없이 저장한다. 옛 행에 남은 값은 읽을 때(get_survey·update_survey 응답·출력 snapshot) 뺀다 | Survey |
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
| preview_photo_file | file_path:string | CropSourcePreview |
| import_cropped_photo | task_id,file_path,source_sha256,crop,task_created_at? | PhotoInfo |
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
| generate_ai_text | analysis_id,purpose?:AiPurpose (기본 TASK_EXPLANATION),provisional_reba?:ProvisionalRebaInput | AiTextView |
| edit_ai_text | analysis_id,text_id,text | AiTextView |
| apply_ai_text | analysis_id,text_id,use_edited:boolean | AiTextView |
| preview_excel | survey_id,analysis_ids:ID[],comparisons:ComparisonSpec[] | ReportOverview |
| export_excel | survey_id,spec:ExportSpec | ExportReceipt |
| preview_pdf | survey_id, spec:{task_ids,analysis_ids,include_representative} | PdfPreview (PDF 바이트의 data URL, page_count, warnings, overview, format:'PDF') |
| export_pdf | survey_id, spec:{task_ids,analysis_ids,include_representative,destination} | PdfExportReceipt (PDF 저장·이력 추가) |
| list_export_logs | survey_id | ExportLogItem[] |
| get_settings / update_settings | 없음 / settings:SettingsUpdate | Settings |
| quick_preview | task_id,views:{LEFT?,FRONT?,RIGHT?:ID} | QuickPreview (저장하지 않음: 사진별 관절·방향 추정, 측면 근측 범주, 정면·후면 기울임 제안, 부담 없음 가정 1차 REBA, 규칙 기반 질문) |
| preview_excel_sheets | survey_id,analysis_ids?,comparisons? (preview_excel과 같은 선택) | ExcelPreview {sheets:[{name,title,lead,tables:[{heading,columns,rows,widths,header?,labels?,label_rows?,label_cells?,merges?,bordered?,heights?,break?,photo?}],notes,tab_color?}]} (저장하지 않음: export_excel이 만드는 시트와 같은 내용. 양식 표는 header·labels·merges 같은 선택 키로 그린다. 대표 사진 이미지만 파일에만 들어간다) |
| quick_interpret | text (1~600자 작업 설명 한 문장) | QuickIntake {items,dropped,reason} (저장하지 않음: 문장을 조사표 칸으로 옮긴 값. 모든 값은 문장 속 근거 구절과 함께 오며 근거가 문장에 없거나 범위를 벗어난 값은 버린다. 문장만 AI에 보내고 별도 스레드로 응답한다) |

| intake_contract | 없음 | AdaptiveIntakeContract {version,session_key,methods,policy,states,sources,ai_states,fields} |
| intake_session | task_id,views? | AdaptiveIntakeState (세션 복원·사진 측정 자동 저장·현재 추가 질문) |
| intake_turn | task_id,text?,answers?,expected_revision?,plan?,focus?,task_created_at? | AdaptiveIntakeState (직접 답변 우선 저장, 선택값은 로컬 후속 계획, 문장 추출·재시도는 AI) |

적응형 입력의 DTO·상태·단위·조건별 연결·저장 의미는 [적응형 추가 확인 계약](adaptive-intake.md)을 따른다. `conditions.intake_session`은 선택 JSON 메타데이터이며 실제 입력은 기존 legal/capture/manual/conditions에도 기록한다. `intake_contract`가 내보내는 변수와 catalogue를 프론트·서비스·AI 응답 schema가 공유한다.

추가 확인 질문은 선택적으로 `paired_question?:AdaptiveIntakeQuestion`을 포함한다(2026-10-23). 현재 누락 후보에 같은 manual 항목의 반대쪽(LEFT/RIGHT)이나 반대쪽 사진 방향(`view_LEFT`/`view_RIGHT`)이 있을 때 서비스가 기존 질문 DTO 형태로 붙이며, KNOWN·USER UNKNOWN인 쪽은 제외한다. 최상위 `questions` 길이 제한 1은 유지한다. 관련 필드 묶음은 `answer_questions?:AdaptiveIntakeQuestion[]`와 `group_title?:string`을 추가하며, member는 중첩 pair/group 없는 기존 질문 DTO다. 몸통·목 6개, 다리 3개, 움직임·힘 4개, 양팔·손목 추가 자세 8개, 작업 특징 최대 9개 범위에서 미확인 항목을 묶는다. `answer_questions`가 있으면 화면은 이 목록을 우선 사용하고 짝 질문을 중복 표시하지 않는다. 좌우 짝 질문은 양쪽 응답을 받은 뒤 `intake_turn.answers`에 두 `{target,condition,value,quote?}`를 함께 보내고 기존 revision 검사를 적용한다. 관련 그룹은 하나 이상 선택한 member만 함께 보내며 선택하지 않은 항목은 answers에 포함하지 않는다. 각 쪽의 UNKNOWN은 독립적이며 미선택 쪽을 0·NO나 반대쪽 값으로 추정하지 않는다.

AdaptiveIntakeState의 `progress={completed_count,total_count,remaining_count,percent,dynamic:true}`는 현재 필요한 추가 확인 항목의 진행률이다. 질문 배열은 한 번에 하나로 제한되므로 그 길이를 전체 질문 수로 사용하지 않는다. 좌우 짝 질문과 관련 항목 그룹도 원래 필드 수로 집계하며 묶음 화면 수로 진행률을 바꾸지 않는다. 남은 40개는 질문 화면 40개를 뜻하지 않는다. 퍼센트·처리/전체/남은 항목은 서버 값으로 표시하고 답변에 따른 대상 변화를 안내한다. USER 모름도 확인 처리에 포함하지만 계산 완성인 `complete`와 구분한다. 상세 집계·구버전 응답 표시는 [적응형 추가 확인 계약](adaptive-intake.md)을 따른다.

AdaptiveIntakeState의 `ai`는 실제 마지막 요청의 상태·응답 모델·요청/응답 추론 강도·실패 사유·시각·응답 ID다. 설정/키 존재와 실제 응답 성공을 구분한다. 이 메타데이터는 내부 진단에 유지하며 사용자 팝업은 모델·추론 강도·연결 성공 상태를 숨기고 처리 중·실패만 일반 안내로 표시한다. 기본 질문 수는 정책 변수로 하나이며, 입력 추출을 반영한 뒤 남은 누락으로 후속 질문을 만든다. 응답 실패 시 저장한 입력/문장을 유지하고 팝업에서 재시도한다. `plan=true`이고 `answers`만 있으며 공백을 제거한 `text`가 비면 외부 AI를 재호출하지 않고 저장 후 다음 질문을 로컬 계획한다. 이 로컬 회차의 ai.status는 NOT_REQUESTED이며 이전 내부 AI 진단과 미처리 문장 초안을 새 성공으로 바꾸거나 삭제하지 않는다. 자유문장 추출과 answers/text 모두 없는 명시적 재시도는 기존 AI 경로를 유지한다.

재계산 요청은 해당 모듈 scope=true의 명시적 요청이다. scope가 바뀌면 revision을 한 번 갱신해 새 분석을 만들고 다른 scope는 유지한다. GPT는 별도 스레드에서 같은 request_id로 응답해 일반 요청 읽기를 막지 않는다.

set_capture는 slot_no/photo_id로 교체를 비교한다. 순서 zip이나 배열 인덱스로 비교하지 않는다. 사진 내용 교체는 새 photo_id이며 해당 관찰/manual을 초기화한다. 카메라 변경은 해당 slot, 작업자/방법/작업 높이 변경은 관련 관찰/manual을 재확인한다. 모델/전처리 변경은 AUTO_ACCEPTED만 해제한다.

같은 사진의 경로 재연결은 update_photo로 manual/observation을 보존한다. 배정된 경로 변경은 revision을 한 번 올리고 동의만 바꾸면 유지한다. 원본 바이트 동일성을 보증하는 기능은 아니다.

delete_photo는 배정 해제·관찰 초기화·대상 manual 제거·PHOTO 삭제를 같은 트랜잭션으로 처리한다. 현재 입력이 바뀐 경우에만 revision을 한 번 올린다. 없는 사진 삭제는 Ack다. 조사자 결론 변경과 전체 reviewed=false도 같은 트랜잭션이다. 대표/설명 편집은 계산 검토 표시를 유지한다.

## 8. 보고서·전후 비교

~~~typescript
type ComparisonSpec = {before_analysis_id:ID,after_analysis_id:ID,note:string|null};
type ExportSpec = {destination:string,analysis_ids:ID[],include_representative:boolean,comparisons:ComparisonSpec[]};
type ReportState = {reviewed:boolean,review_current:boolean,has_incomplete:boolean,has_stale:boolean};
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
type ReportOverview = {report_version:'2.0',state:ReportState,counts:ReportCounts,tasks:ReportTaskOverview[],comparisons:ComparisonOverview[]};
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

출력 시트는 같은 snapshot으로 `plain_sheets`가 만드는 시트 정의 목록이며 Excel 파일과 `preview_excel_sheets` 미리보기가 같은 정의를 쓴다. 모든 조사 유형은 `조사 결과`에 실제 기록한 조사 개요·작업 입력과 계산 가능한 결과만 출력한다. 조사 유형은 사용자가 실제 선택한 경우에만 표시한다. 기본값·UNKNOWN provenance의 기존 조사 유형은 표시하지 않는다. 부담작업·자세·입력값 시트는 실제 기록값이나 분석 결과가 있을 때만 생성하며, 빈 공식 양식·기본 UNKNOWN·미질문 기준·미입력 안내는 출력하지 않는다. 확인사항 시트는 만들지 않고 앱 조사화면의 다음 입력 안내는 유지한다. 사람이 확정한 설명과 선택한 비교 결과는 해당 데이터가 있을 때만 추가한다. 모든 시트는 참고 자료이며 공식 서식의 완성·서명/날인·조사자 검토를 대신한다. 출력 영수증의 sheets에는 실제 생성된 시트를 순서대로 저장한다.

| 시트 | 조건 | 내용 |
|---|---|---|
| 조사 결과 | 항상 | 조사 구분·조사 개요·작업명과 계산 가능한 결과만 포함. 빈 항목과 선택하지 않은 선택지는 생략한다. 수시조사도 별지 양식 형태를 만들지 않는다. |
| 부담작업 해당 여부 | 기록된 기준의 결과가 있을 때 | 답변·입력 이력이 있는 기준 중 계산 결과가 정해진 행만 표시한다. 11개 전체 빈 행렬, 미질문 기준, 미입력 안내는 포함하지 않는다. |
| 자세 분석(REBA) | 자세/REBA/기술태그 데이터가 있을 때 | 사진별 REBA 구성점수, 읽은 각도, 자세 표시 |
| 입력한 값 | 실제 계산 입력·사진 확인·자세 입력 근거가 있을 때 | 입력한 값과 AI가 정리한 입력 사실만 표시한다. 기본 UNKNOWN과 입력되지 않은 기본값은 숨긴다. |
| 확인사항 | 사용하지 않음 | Excel에는 다음 입력·미입력·미질문 안내 시트를 만들지 않는다. 앱 조사화면의 보완 입력 안내는 유지한다. |
| 결과 설명 | 사람이 확정한 설명이 있을 때 | 활성 적용본의 확정 문장·종류·확정 시각. 미확정 생성/편집 초안은 제외 |
| 개선 전후 비교 | 비교를 골랐을 때 | 기준별 변화와 바뀐 입력 |

시트 정의 표는 name, title, lead, tables, notes, tab_color를 사용하며 각 표는 heading, columns, rows, widths와 선택 키 header, labels, label_rows, label_cells, merges, bordered, heights, break, photo를 가질 수 있다. 대표 사진 이미지는 조사자가 포함을 선택하고 실제 대표 사진이 있을 때만 기본 결과 시트의 사진 칸에 들어가며 파일에만 있다. 비교 블록은 정렬 표 밖에 두고 실제 입력 변화와 비교 제한은 비교 시트에 표시한다.

needs_input_count/needs_review_count는 computed_status별 기준 수(작업당 0~11)다. judgment 미계산이면 null이며 조사 집계에 null이 있으면 합계도 null이다. incomplete_reba_count는 요청하고 계산한 REBA의 N−complete_count다. 미계산/미요청은 null로 두고 상태로 구분한다. 요청 대상 0건은 0과 NO_ANALYSIS_TARGET을 함께 표시한다. REBA 조사 합계는 전체 미요청이면 null, 요청 작업 중 미계산이 있으면 null, 나머지는 요청·계산한 작업의 수를 더한다.

has_incomplete는 요청 모듈의 NOT_CALCULATED/RUNNING/INCOMPLETE/FAILED/CANCELED에서 산출하고 NOT_REQUESTED는 제외한다. 분석 없음은 true다. GPT 실패·이전 설명은 앱 상태에 남기며 Excel에는 표시하지 않는다. 사람이 확정한 설명만 결과 설명 시트에 출력한다. has_stale는 선택 분석의 STALE 여부다.

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

## 원본 별지 1 PDF 출력 계약 (2026-10-22 개정안)

사용자 보고서 흐름은 Excel 미리보기·저장을 유지한다. PDF 미리보기·저장은 간편·고급 사용자 화면에 노출하지 않으며, 아래 절은 내부 PDF API에만 적용한다. Excel API와 영수증 계약은 유지한다. 이 절은 PDF에 적용하며, 앞의 Excel 시트 설명은 Excel 출력에만 적용한다. 이 문서는 후보 코드에 대응하는 개정안이며 실제 main 반영·배포 완료 보고가 아니다.

- 선택한 Task 한 건마다 원본 1·2·3쪽 양식을 만든다. 끝에 원본 작성방법을 한 번 붙인다. 기본 페이지 수는 3×선택 작업 수+1이며, 원본 칸을 넘는 긴 작성 내용이 있을 때만 별첨을 붙인다. 별도 하위 단위작업 모델은 추가하지 않는다.
- Task 이름과 method_description을 작업명·작업내용으로 표시하고, 세부 작업을 나누어 입력하지 않은 Task는 전체 작업 한 행으로 평가한다. A/B 면담 점수를 여러 가상 단위작업에 복제하지 않으며, 둘 다 1~5 정수일 때만 곱한다. null은 공란이다.
- task_ids는 비어 있지 않은 중복 없는 양의 정수 목록, analysis_ids는 선택 Task당 최대 하나다. 타 조사/선택 밖 Task 분석은 거부한다. 명시 선택이 없으면 최신 분석, 분석이 없으면 출력 시점 입력을 사용한다. include_representative는 bool이다.
- 분석이 있으면 그 분석 snapshot, 없으면 Task 입력을 읽는다. 과거 분석을 현재 입력으로 바꾸지 않는다. 조사 메타와 Task/분석 선택은 요청 순서대로 snapshot에 고정한 뒤 PDF 생성만 별도 스레드에서 처리한다.
- 원본 칸의 부담작업 호는 조사자 APPLICABLE 결론만 표시한다. 계산 초안·조사자 결론 상세·미확정 상태는 앱에서 구분하며 PDF 별첨으로 나열하지 않는다. 공란을 비해당 확정으로 보지 않는다. worker_code는 실명으로 출력하지 않는다.
- 원본의 작업장 상황 칸은 채우지 않고 비워 둔다(작업장 상황은 더 이상 입력받지 않는다, 2026-10-27 소유자 지시: REBA 계산과 그 값을 Excel로 주는 것까지만 한다). 원본 칸에 대응하는 작성 내용이 칸을 넘을 때만 전체 원문을 별첨에 보존하고 해당 칸에 별첨 참조를 표시한다. 유해요인·발생 원인을 호 번호/GPT로 생성하거나 임의로 분해해 짝짓지 않는다.
- 대표 사진을 요청한 경우 선택 snapshot의 대표 슬롯 사진만 포함한다. 누락·손상은 명시하고 다른 사진으로 대체하지 않는다. 사진 미포함 요청에서는 파일을 읽지 않는다.
- 입력한 노출량·조건 행·수동 관찰값·REBA·적용한 설명·빈 사진 슬롯·내부 식별번호·보완사항은 PDF에 자동 별첨하지 않는다. 경고·완전성 상태는 기존 API 응답과 앱에 유지한다. 원본 서식 칸에 REBA나 AI 설명을 끼워 넣지 않는다. 전후 비교는 기존 화면/Excel 흐름을 유지하며 이번 PDF API는 비교 매개변수를 받지 않는다.
- PDF 미리보기는 파일/이력을 만들지 않는다. 실제 저장은 새 snapshot을 사용하므로 미리보기 뒤 변경된 입력은 실제 영수증이 기준이다. 저장 창 취소는 서비스 저장 요청을 보내지 않는다.
- PdfPreview는 `{report_version:'2.0',format:'PDF',template_version,template_sha256,page_count,task_ids,analysis_ids,warnings,overview,data_url,...ReportState}`다. data_url은 application/pdf base64이다.
- PdfExportReceipt는 미리보기와 같은 메타에서 overview/data_url을 제외하고 `{export_id,file_path,created_at}`을 더한다. 실제 파일 저장 후 기존 EXPORT_LOG에 snapshot_json/receipt_json 새 행을 추가한다. format이 없는 과거 영수증은 Excel로 읽는다. 기존 snapshot과 이력은 재작성하지 않는다.
- PDF 바이트 생성 후 임시 파일을 최종 경로로 교체한다. 생성·쓰기 실패에 성공 이력을 만들지 않는다. 파일 생성 후 로그 실패는 파일 경로를 포함한 DB 오류다. 잘못된 PDF 입력은 기존 입력 오류 경계를 따르고, PDF 생성 실패는 EXPORT_ERROR다.
- 개발용 시스템 글꼴 경로와 Downloads 경로에 의존하지 않는다. 원본 출처 해시·빈 양식·배포 가능한 한글 글꼴을 자산으로 포함한다. 원본 3쪽의 예시는 실제 문자 객체에서 제거하고 작성방법 페이지는 보존한다.

- 지연 PDF 저장은 출력 준비 때의 DB 경로를 유지하며, 이력 추가 트랜잭션에서 조사 생성시각도 함께 비교한다. 대상 조사가 삭제·교체됐다면 다른 조사에 이력을 붙이지 않고 파일 경로와 오류를 알린다. 이 구분은 서버가 부여한 created_at이 조사 수명별로 다르다는 기존 저장정보를 이용한다.


## 등록 전 사진 크롭 (2026-10-22)

간편 화면의 사진 선택/드롭은 원본 등록 전에 사각형 선택 대화상자를 연다. 기존 import_photos와 고급 사진 등록은 유지한다.

- CropSourcePreview = {data_url:string,width_px:Count,height_px:Count,source_sha256:string}. preview_photo_file은 EXIF 보정 RGB 사진을 PNG data URL로 반환하며 DB 행이나 파일을 생성하지 않는다.
- import_cropped_photo의 crop={x,y,width,height}는 EXIF 보정 원본의 정수 픽셀 좌표다. x/y는 0 이상, width/height는 1 이상이며 영역 전체가 사진 안이어야 한다. 원본 바이트 SHA-256이 미리보기 때와 다르면 거부한다. task_created_at을 지정하면 현재 작업 수명과 비교한다.
- 확인 시 현재 DB 파일의 상위 폴더/media/photos 아래 고유 PNG를 저장하고 기존 PHOTO 행의 file_path에 등록한다. 원본은 덮어쓰지 않는다. 원본 경로/해시/크기와 선택 좌표는 기존 notes의 PHOTO_CROP 진단 message에 JSON으로 보존한다. 사진 크기와 분석 좌표는 크롭 이미지 기준이다.
- 메모리 DB는 크롭 파일을 보관할 위치가 없으므로 거부한다. 새 테이블·열·물리 migration은 없다. 원본 EXIF 이외 메타데이터를 새 PNG에 복사하지 않는다.
- DB 경로와 작업 생성시각을 고정해 처리하며 저장 전에 대상 수명을 재확인한다. 등록 실패 시 이번에 만든 파일만 정리한다. 기존 사진·분석 snapshot·출력 이력은 바꾸지 않는다. 수명 비교는 기존 created_at을 사용한다.
- 취소하면 등록·교체·작업 생성 요청을 하지 않는다. 교체는 새 사진의 등록/미리보기 성공 후에만 화면에 반영한다. 지연 응답은 초기화/다른 화면의 사진이나 진행 상태를 덮지 않는다.
- 크롭 파일은 참조 삭제 때 자동 삭제하지 않는다. 과거 snapshot이 계속 참조할 수 있기 때문이다. 백업·다른 PC 이동 시 DB와 media/photos를 함께 보관하며 기존 절대 사진 경로의 재연결 원칙을 따른다.
- MoveNet·REBA와 보고서 사진은 모두 등록된 크롭 파일을 사용한다. 크롭은 사진 입력 영역 선택이며 점수·법령 판정을 직접 변경하지 않는다. 잘못된 좌표/파일/변경된 원본은 기존 FILE_ERROR, DB 오류는 DB_ERROR, 사라진 작업은 NOT_FOUND 경계를 따른다.


간편 추가 확인 정책의 `policy.quick_review_interval=5`는 결과를 먼저 볼 수 있도록 안내하는 화면 간격이다. 질문 후보나 계산 완성을 제한하는 값이 아니며 기존 미확인 필드와 `progress`/`complete` 의미는 유지한다.


## 기본 간편 입력: 묶음 서식 (2026-10-23)

새 서비스 응답의 `form_fields`가 있으면 간단 확인 횟수 제한/개별 질문 대신 작업 특징 → 작업 조건 → 결과의 고정 이동을 사용한다. 첫 화면에 작업 특징을 함께 표시하고 저장 후 해당 작업의 관련 조건을 선택·숫자 서식으로 묶어 표시한다. 관련된 KNOWN 값은 미리 표시하며 변경한 값만 기존 intake_turn.answers로 저장한다. 조건별 identity를 유지하고 서로 다른 중량·횟수를 합치지 않는다. 선택 보완인 사진 자세는 접을 수 있다. 미선택은 NO/0으로 자동 채우지 않으며 미확인 상태로 결과를 생성할 수 있다. 화면 단계 표시는 계산 완성률을 뜻하지 않는다. 결과 이동 후 개별 누락 질문을 자동으로 이어가지 않는다. 추가 설명은 선택 영역에서 AI로 정리할 수 있고 서식 선택·숫자 저장에는 AI 요청을 하지 않는다. 기존 응답의 questions/progress/complete는 호환·실제 계산 상태로 유지한다. form_fields가 없는 과거 초안은 기존 질문 화면으로 읽는다.

### 하루 시간 합산 정정 (2026-10-22)

2026-10-23 추가: 허용 derivations가 있는 AI 답변에는 nullable `calculation={operation,terms:[{quote,minutes}]}`을 schema의 필수 키로 생성한다. 합산하지 않는 답변은 null이며 과거 이 키 없는 응답도 읽는다. 서비스는 원문 위치·피연산자별 분 환산·중복·최종 합계를 검사하고 정규화한 fact.calculation만 저장한다. 저장 객체는 `{operation,unit,terms,value}`이며 복합 단위 하나의 정규화는 `NORMALIZE_STATED_DURATION`이다. 다른 노출에 총시간 합산 권한을 추가하지 않는다. 예시·실패 경계는 [적응형 계약](adaptive-intake.md)을 따른다.

intake_contract.fields[].derivations는 허용 수치 연산을 기술한다. daily_work_min만 SUM_STATED_DURATIONS를 허용하며, 합산 fact의 선택 calculation={operation,unit,terms:[{minutes,quote}],value}에 검증된 근거를 반환한다. AI의 답변 schema는 기존 quote/number를 유지한다. 자세한 근거 검증과 예외는 [적응형 추가 확인 계약](adaptive-intake.md)의 작업별 시간 합산 절을 따른다.


## 입력 저장 감사 7건 정정 (2026-10-23)

intake_session/intake_turn 응답에 diagnostics와 history를 추가한다. messages의 message_id와 회차의 requests[phase,connection.response_id,answers,context]·decisions[proposal_index,request_index,outcome,reason,source_message_ids]를 기존 JSON에 보관한다. INPUT_CHANGED는 늦은 제안의 폐기 표식이 아니다. 같은 작업이면 최신 값에 재조정한 결과와 보존한 제안/진단을 반환한다. 명시한 글자 예산이 없으면 저장된 자연어 전체를 문맥에 포함한다. 상세 DTO·호환·소유권은 [저장 계약](storage-persistence.md)을 따른다.


## 실호출 입력·출력 대조 정정 (2026-10-23)

FOLLOWUP의 answers도 동일한 근거 검증을 거쳐 ACCEPTED/UNCHANGED/REJECTED로 기록한다. 반영 후 질문 후보를 갱신하고 USER 값과 미해결 CONFLICT를 지킨다. 과거 IGNORED/FOLLOWUP_ONLY 회차는 호환 열람하며 재작성하지 않는다. 메서드/매개변수와 물리 DB 스키마는 유지한다. 상세는 [저장·출력 보존 계약](storage-persistence.md)을 따른다.

자연어 단독 turn은 오래된 expected_revision도 최신 상태에 재조정하고 선택 `history[].rebased_from_revision`을 기록한다. 구조화 직접 답변의 저장 경합은 INPUT_CHANGED이며 저장 성공이 아니다. 사진 소유 문맥을 확인할 수 없는 제안은 PHOTO_CONTEXT_CONFIRMATION_REQUIRED로 보관한다. 조회에 따른 파생 별칭/무하중 손잡이의 revision 변화를 제거한다. 기존 요청 매개변수와 여섯 테이블은 유지한다.



## 최신 main 통합과 재질문 방지 (2026-10-23)

최신 main의 Excel 출력·사진 크롭·공통 이동과 당시 2단계 묶음 확인(2026-10-26부터 한 페이지)을 기준으로 MediaPipe 및 저장 보완만 추가한다. 이미 KNOWN인 값과 USER가 모름으로 확인한 항목은 새 질문/질문 묶음에 넣지 않는다. 간편 묶음 서식에서도 기본 추가 입력에서 제외하고 닫힌 ‘이미 확인한 정보 · 수정하기’에서만 수정한다. 조건별 행과 좌우 사진의 identity를 유지하며 한 조건의 답을 다른 조건에 복사하지 않는다. ESTIMATED·CONFLICT 및 새 사진에 연결되지 않은 정보는 확인할 수 있다.

사진과 같은 물건이라고 확인한 유일 중량은 photo_load의 공통 해석으로 계산과 질문에 함께 사용한다. 이 파생값을 새 사실로 저장하거나 조회 revision을 올리지 않는다. 여러 중량, 확인하지 않은 연결, 명시적인 모름·무하중·직접 중량은 구분한다. 자동 저장과 수동 임시 저장이 같은 작업/생성시각을 가리키면 홈의 이어서 하기 카드는 수동 저장 하나로 표시한다. 별도 작업 초안은 보존한다.

사용자에게 보이는 시스템 용어는 frontend/user-language.json을 공통 사전으로 사용한다. 화면의 AI 본문·처리 상태·계산 근거 및 Excel 설명은 같은 뜻의 한국어로 표시한다. 과거 저장된 원문·직접 입력 근거·계산 코드·수치·단위·snapshot은 바꾸지 않는다. 새 AI 설명 지침에도 같은 사전을 제공하며 근거 참조 코드는 유지한다. 묶음 입력에서 미전송한 추가 설명은 다음 단계 저장과 함께 처리하고, 입력 단계와 수정 중 선택값은 초안 복원 대상이다.

검증 범위와 실제 호출 증거는 [최신 main 재질문 점검](verification/2026-10-23-main-no-repeat.md)에 기록한다. 외부 호출 없이 검사한 계약 조합과 실제 모델·앱·DB·Excel 실행은 구분한다.

## 실제 원문 인용과 반 시간 경계 정정 (2026-10-23)

요청/응답 키는 유지한다. 공통 evidence_quote는 공백 정규화 연속 인용 또는 동일 원문에서 순서/위치가 검증된 완전한 문장 인용만 인정한다. fact.quote는 실제 연속 원문, history.requests/decisions.quote는 원본 AI 인용이며 source_message_ids는 같은 규칙으로 결정한다. 숫자 검증은 원본 인용의 값·단위를 유지하고 USER 우선권·지연 응답 재조정 규칙은 바꾸지 않는다. 자세한 허용/거절 경계는 [추가 확인 계약](adaptive-intake.md#원문-문장-인용과-반-시간-경계-2026-10-23)을 따른다.

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

### 명시 총시간과 불필요 계산 메타데이터 (2026-10-23)

원문을 그대로 복사한 단일 확정 하루 총시간과 제안 수치의 단위 환산이 직접 일치하면, AI가 함께 붙인 불필요한 합산 메타데이터 때문에 그 값을 거절하지 않는다. `grounding.DIRECT_TOTAL_POLICY`가 이 우선순위와 부정·불확실 경계를 관리한다. 예: “하루 전체 실제 작업시간은 5시간입니다”의 300분은 직접 저장하며, 별도 작업 피연산자가 인용에 없다는 이유로 재질문하지 않는다. 원 AI 제안의 calculation과 결정·원문 연결은 이력에 그대로 보존하고, fact에는 검증하지 않은 합산 근거를 저장하지 않는다. 틀린 총값·단위·잘린 복합 시간·범위·부정·불확실 총시간은 이 우선 규칙으로 허용하지 않는다. 단일 명시 총시간이 없는 합산은 기존 원문 피연산자·단위·순서·중복·산술 검증을 계속 거친다. DB 스키마·기존 snapshot·USER 우선권은 바꾸지 않는다.

### 실제 사진의 AI 관찰 (2026-10-23)

사용자가 사진 분석을 요청하는 기존 intake_turn 계획 실행에서 등록된 현재 크롭 사진을 실제 Luna 이미지 입력으로 보낸다. 계약은 `ergo.vision.contract`, 서비스는 `service.photo_vision`이며 모델·추론 설정은 기존 ai_config를 공유한다. 사진별 동작·몸통·목·무릎·좌우 팔·좌우 손목·잡은 모습 9개 관찰과 보이지 않거나 모호한 이유를 보존한다. MediaPipe의 수치 각도와 구분한다. `conditions.intake_session.photo_vision` 및 동일 응답 경로에 사진별 원본/전송 JPEG SHA, task/photo 소유권, signature, raw_response, 연결·진단을 저장하고 base64/EXIF를 DB에 넣지 않는다. 여섯 테이블과 과거 snapshot은 유지한다.

등록 이미지/view/소유권·모델/추론/프롬프트·이미지 정책으로 캐시하며 읽기·재시작·직접 선택 답변·plan=false에는 이미지 API를 호출하지 않는다. 변경된 사진의 최초 요청은 사진별 병렬 실행하며 지연 응답을 시간으로 폐기하지 않는다. 다른 사진이나 삭제·교체된 작업에 이전 결과를 적용하지 않는다. 불확실/안 보임은 NO가 아니다. 허용된 분명한 boolean 자세와 4개 작업 특징의 YES만 별도 검증 경로로 source=VISION에 반영할 수 있다. USER(직접 모름 포함), 텍스트 AI, SAVED, 유효한 POSE를 우선한다. 사진에서 무게·힘·시간·횟수·정밀 각도·법정/의학 판정을 만들지 않는다. 상세는 [photo-vision.md](photo-vision.md)를 따른다.

### 사진 등록 세대와 사용자 사진 상황 우선권 (2026-10-23)

`photo_identity.REGISTRATION_KEY`는 새 PHOTO.metadata_json 행에 UUID를 부여하며 update로 교체하지 않는다. 물리 스키마는 유지한다. legacy 행은 경로/소유 ID로 결정되는 토큰을 읽고 조회 중 metadata를 쓰지 않는다. 사진 signature는 [view,photo_id,원본SHA,등록세대]이며 과거 triple을 호환한다. 같은 SQLite ID·파일경로·바이트·view로 재등록해도 이전 이미지 및 텍스트 사진 응답이 새 등록에 적용되지 않는다.

사용자가 context=NO로 사진 상황을 부정하면 raw 관찰과 캐시는 보존하되 VISION 소유 manual/작업특징 입력은 UNKNOWN으로 돌려 실제 투영값도 해제한다. USER·텍스트 AI·SAVED·POSE 소유 값은 건드리지 않는다. context=YES로 직접 정정하면 같은 이미지 관찰을 재사용하며 추가 이미지 API를 호출하지 않는다. 같은 turn의 텍스트 추출 뒤 저장에도 이 우선권을 적용한다.

### 현재 원문이 사진 AI 추정을 정정하는 경우 (2026-10-23)

원문 인용·대상·단위·사진 소유권 검증을 통과한 현재 텍스트 제안은 이전 source=VISION의 KNOWN/CONFLICT 추정보다 우선해 source=AI,state=KNOWN으로 저장한다. 다른 값은 충돌 재질문으로 만들지 않고, 같은 값도 텍스트 근거로 승격하여 사진 삭제 때 명시한 작업 특징이 사라지지 않게 한다. 과거 원문 인용만으로는 이 승격을 하지 않는다. USER(직접 모름 포함), 기존 텍스트 AI/SAVED/유효 POSE 값과 사진 변경·지연 보호는 유지한다. 사진별 manual 정식 조건과 대표 호환 alias는 같은 사진의 AI 근거를 가리키며 원래 사진 관찰 raw/cache는 수정하지 않는다.

context=NO이면 public 사진 관찰은 계속 보관·표시하되 계산·추출용 known_visual_observations는 빈 목록이다. YES로 직접 정정하면 기존 사진 캐시를 다시 사용할 수 있다. 사진과 무관한 직접 설명값은 유지한다.

### 미완성 REBA의 지금까지 기준 점수 (2026-10-26)

`calculate_reba` 결과의 미완성 슬롯에는 선택 필드 `score_so_far`가 붙는다. 지금까지 저장된 자세·답변 값은 그대로 쓰고, 비어 있거나 UNKNOWN인 REBA 입력(OR 규칙으로 제외된 칸은 제외)만 계산에서 부담 없음 선택지로 대신해 얻은 점수다. 대신한 값은 입력으로 저장하지 않으며 분석 snapshot의 manual·observation은 바뀌지 않는다. `assumed`는 대신한 입력 경로(common.*, left.*, right.*)이고 하중 상태가 UNKNOWN이면 하중 없음을 가정하고 `observation.load_state`를 함께 적는다. 물건을 든다고 답했는데 손잡이 상태가 비어 있으면 GOOD을 가정한다.

사진 상황 확인(context)에 사용자가 아직 답하지 않았으면, 분석 snapshot에 담긴 intake 세션에서 같은 사진이 소유한 POSE·MOVENET KNOWN 판독(작업 입력에는 아직 투영되지 않은 값이며 방향·신뢰도·경계 검사를 통과한 값만 KNOWN이다)을 아직 비어 있는 자리에 빌려 쓰고, 그 경로를 `unconfirmed_photo`에 적는다. 이 값은 `assumed`에서 빠지며 입력으로 저장되지 않는다. context가 NO이거나 사용자의 모름이면 빌리지 않고(planner가 같은 항목을 직접 묻는다), YES이면 이미 받아들인 값만 쓴다. 다른 사진이 소유한 값, ESTIMATED 값, 이미 입력된 값은 빌리지도 덮어쓰지도 않으며 intake 세션이 없는 작업에는 빌릴 값이 없다.

2026-10-27 사용자 변경: 등록한 분석대상 사진에는 `summary.current_score`를 항상 제공한다. 기존의 몸통·위팔 누락 등으로 현재 점수를 생략하던 표시 문턱은 폐기한다. 확정 점수는 기존 검증을 유지하며, 필요한 근거가 없거나 입력이 충돌하면 부담 없음 가정을 명시한 `ASSUMED_REFERENCE`로 수치를 제공한다. 실제 입력과 확정 total을 0이나 가정으로 덮어쓰지 않는다. 무사진 작업에는 사진 점수를 만들지 않는다. `summary.score_so_far`와 `summary.first_pass`는 확인 전 점수와 사진 1차 점수를 구분해 보존한다. `current_score`는 완성 사진과 확인 전 점수 중 큰 값을 선택하고, 동점이면 확정 사진을 우선한다.

`NumericSummary.reba.score_so_far`는 total·risk·assumed_count와, 있을 때만 unconfirmed_photo_count·load_assumed를 허용 목록으로 전달한다. AI는 LOCO가 계산한 점수와 가정을 설명하며 점수를 생성하거나 삭제하지 않는다. 화면과 Excel의 주 결과는 `REBA 현재 점수`이며, 확인 전 항목은 점수 옆에 가정 포함으로 표시한다. 확정 계산 total과 별도인 현재 점수를 조사자 결론이나 법적 판정으로 표시하지 않는다.

### 측정 신뢰도와 현재 점수 읽기 투영 (2026-10-27)

`analysis.measurement_quality`는 분석대상 사진별 측정된 관절 수, topology의 전체 관절 수, 관절 신뢰도 평균과 품질 수준을 제공한다. 유한한 좌표·신뢰도를 가진 점 중 snapshot의 confidence_min 이상인 점만 measured_points에 센다. MediaPipe는 33, MoveNet은 17을 분모로 쓰며 없는 관절을 측정한 것으로 채우지 않는다. 검출 비율과 평균 신뢰도가 모두 0.75 이상이면 HIGH, 모두 0.50 이상이면 MEDIUM, 측정점이 남으면 LOW, 측정점이 없으면 MISSING이다. 이 값은 모델 검출 품질이며 REBA 정확도나 질환 확률이 아니다. 점수 옆 품질은 current_score.slot_no와 같은 사진의 값이다.

기존 저장 분석에 현재 점수 필드가 없으면 서비스의 공통 읽기 투영으로 같은 snapshot·pose·사진별 근거에서 계산한다. `project_score_continuity(analysis)`는 원 객체·DB·불변 snapshot을 수정하지 않으며, 화면과 보고서는 같은 `current_score`를 사용한다.

## 자세 체크리스트와 한 번에 채우기 보조 필드 (2026-10-26)

`intake_contract.fields[]`의 manual 항목 중 선택지가 [예, 아니오]인 18개(COMMON `trunk_twisted`·`trunk_side_bent`·`neck_twisted`·`neck_side_bent`·`legs_support`·`seated`·`shock_force`·`static_over_1min`·`small_repeat_over_4min`·`rapid_change_or_unstable`, LEFT/RIGHT `shoulder_raised`·`arm_abducted_or_rotated`·`arm_supported_or_gravity_assisted`·`wrist_deviated_or_twisted`)에는 선택 필드 `checklist:{group:string,order:Count,label:string,yes:string,no:string}`이 붙는다. `yes`/`no`는 해당 항목 `choices`의 값이며(`legs_support`는 UNILATERAL_OR_UNSTABLE/BILATERAL_STABLE) 같은 항목을 담는 `form_fields[]`에도 그대로 실린다. 다른 항목에는 없다. 몸통·목의 네 항목은 `label`/`question`도 칸마다 다른 문구로 바뀌었다. 기준 사진의 manual 질문 후보와 `form_fields[]`에는 정면·후면 사진 판독이 있을 때만 `suggestion?:{value:string,estimated:boolean,quote:string,photo_label:string,reading:string}`이 붙는다(조건과 의미는 [적응형 추가 확인 계약](adaptive-intake.md)의 같은 날짜 절). `suggestion`은 입력값이 아니며 사실·manual 행·REBA 입력을 바꾸지 않는다. `intake_turn.answers[]`의 각 항목은 `{target,condition?,value,quote?}`이며 `quote`는 USER 사실의 근거 문구가 된다(없으면 “직접 입력”). 서식의 체크·채우기는 이 필드로 선택 경위를 보낸다. 요청·응답 메서드와 매개변수는 늘지 않는다. 모델 요청(EXTRACT_AND_PLAN·FOLLOWUP)의 `targets`·`missing`·`asked`에는 `checklist`·`suggestion`을 싣지 않는다.
