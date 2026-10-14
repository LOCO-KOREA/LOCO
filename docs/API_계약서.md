# API 계약서

> 문서 ID ERGO-API-001 · 설계 버전 1.2 · 기준일 2026-10-14 · 데모 개발 기준

## 1. 경계·모듈

Windows 로컬 UI→Application Service 계약이다. 아래 타입 표기는 설계이며 구현 코드가 아니다. HTTP 서버를 요구하지 않는다. 서비스는 모듈들을 순서대로 호출하고 storage에 저장한다. 계산 모듈은 DB를 직접 읽거나 서로의 내부 함수를 호출하지 않는다.

| 모듈 | 입력→출력 | 책임 |
|---|---|---|
| survey | SurveyDraft/ReviewMark→Survey | 조사·검토 표시 |
| task_input | TaskConditions/LegalInputs/ManualValue→Task | 입력·input_revision·수정 영향 |
| capture | 사진경로/배정→PhotoInfo/CaptureSet | 다중사진·15슬롯·촬영 관찰 |
| pose | PoseRequest→PoseResult, TagRequest→TagResult | 17관절·각도·태그 |
| reba | RebaRequest→RebaResult | 사진별 좌우 점수표 |
| burden | BurdenRequest→JudgmentResult | 직접입력으로11호 초안 |
| explanation | NumericSummary→생성문자열 | 선택 GPT 설명 |
| report | ExportSnapshot→ReportOverview/Excel 파일 | 공통 요약 집계·다음 입력 안내·네 시트 렌더링 |
| storage | 아래 DTO↔SQLite/JSON | 저장·읽기·서비스 삭제 |

expected_version/WriteGuard/승인 토큰/잠금 API/보안검증기는 없다. 미입력·모순·부분분석은 반환 결과의 notes/missing_fields/review_reasons로 표시한다. 저장·분석·초안 내보내기는 이런 상태에서도 사용할 수 있다. 읽을 수 없는 파일·모델·DB·출력 오류는 정상 오류 처리이며 운영 차단정책이 아니다.

## 2. 공통 타입

ID는 양의 정수, Number는 유한 실수, Count는0이상 정수다. 날짜 YYYY-MM-DD, 시각 UTC ISO8601이며 UI는 Asia/Seoul 표시다. null은 미입력이다. 숫자 범위는 계산 의미를 정의하며 DB CHECK로 강제하지 않는다. 요청은 아래 전체 DTO를 전달하고 부분 수정은 UI가 현재값에 합쳐 저장한다.

```typescript
type ID = number;
type Number = number;
type Count = number;
type Date = string;
type Timestamp = string;
type Truth = 'YES'|'NO'|'UNKNOWN';
type Side = 'LEFT'|'RIGHT';
type Forward = 'SCREEN_LEFT'|'SCREEN_RIGHT';
type Phase = 'CYCLE_START'|'LIFT_OFF'|'MID_LIFT'|'SHELF_APPROACH'|'CYCLE_END';
type LoadState = 'UNLOADED'|'FULL_BOX'|'UNKNOWN';
type RunStatus = 'RUNNING'|'DONE'|'PARTIAL_REVIEW'|'FAILED'|'CANCELED';
type JobStatus = 'RUNNING'|'FINISHED'|'FAILED'|'CANCELED';
type SlotStatus = 'PENDING'|'VALID'|'INVALID'|'ERROR'|'CANCELED'|'NOT_PROCESSED';
type Currentness = 'NONE'|'CURRENT'|'STALE';
type JudgmentStatus = 'APPLICABLE'|'NOT_APPLICABLE'|'NEEDS_INPUT'|'NEEDS_REVIEW';
type FinalStatus = 'APPLICABLE'|'NOT_APPLICABLE';
type Risk = 'NEGLIGIBLE'|'LOW'|'MEDIUM'|'HIGH'|'VERY_HIGH';
type Evidence = {source:'DIRECT_OBSERVATION'|'INTERVIEW'|'DOCUMENT'|'OTHER'|null,text:string|null,observed_at:Timestamp|null};
type Diagnostic = {code:string,message:string,field_path:string|null};
type AppError = {code:'FILE_ERROR'|'MODEL_ERROR'|'DB_ERROR'|'EXPORT_ERROR'|'NOT_FOUND',message:string};
type Result<T> = {ok:true,value:T}|{ok:false,error:AppError};
type Ack = {message:string};
type Coupling = 'GOOD'|'FAIR'|'POOR'|'UNACCEPTABLE'|'NOT_APPLICABLE';
type LegsSupport = 'BILATERAL_STABLE'|'UNILATERAL_OR_UNSTABLE';
type KneeBand = 'UNDER_30'|'FROM_30_TO_60'|'OVER_60';
type ReviewReason = 'COMBINATION_RULE'|'POSTURE_INTERPRETATION'|'BOUNDARY_REVIEW'|'INPUT_CONFLICT';
type AngleCode = 'TRUNK_TILT_VERT'|'NECK_TILT_VERT_PROXY'|'NECK_FLEX_TRUNK_PROXY'|'UPPER_ARM_RAISE_VERT'|'UPPER_ARM_FLEX_TRUNK'|'ELBOW_FLEX'|'KNEE_FLEX';
type TagCode = 'NECK_FORWARD_PROXY'|'TRUNK_FLEX'|'TRUNK_EXT'|'UPPER_ARM_RAISE'|'HAND_ABOVE_HEAD'|'ELBOW_ABOVE_SHOULDER'|'ELBOW_BEHIND_TRUNK'|'NECK_TWIST'|'TRUNK_TWIST'|'SQUAT'|'KNEEL';
type ConditionCode = 'C1_KEYBOARD_FOCUSED'|'C2_NECK'|'C2_SHOULDER'|'C2_ELBOW'|'C2_WRIST'|'C2_HAND'|'C3_UNION'|'C4_NECK_FLEX'|'C4_TRUNK_FLEX'|'C4_TRUNK_EXT'|'C4_NECK_TWIST'|'C4_TRUNK_TWIST'|'C4_UNION'|'C5_SQUAT'|'C5_KNEEL'|'C5_UNION'|'C6_QUALIFYING'|'C7_QUALIFYING'|'C10_LIFT'|'C11_IMPACT';
```

## 3. 조사·작업·사진 입력

```typescript
type SurveyDraft = {survey_type:'REGULAR'|'OCCASIONAL',survey_date:Date,investigator:string,department:string,process:string,title:string,occasional_reason:string|null};
type ReviewMark = {reviewed:boolean,reviewed_analysis_ids:ID[],reviewed_metadata_revision:Count|null,reviewer:string|null,reviewed_at:Timestamp|null,note:string|null};
type Survey = SurveyDraft & {survey_id:ID,metadata_revision:Count,review:ReviewMark,created_at:Timestamp,updated_at:Timestamp};
type SurveySummary = {survey_id:ID,title:string,survey_date:Date,task_count:Count,reviewed:boolean,review_current:boolean};
type TaskConditions = {worker_code:string,method_description:string,box_mass_kg:Number|null,shelf_height_cm:Number|null,daily_work_min:Number|null,one_off:Truth,planned_duration_months:Number|null,annual_work_days:Count|null,evidence:Evidence};
type Exclusions = {short_term:Truth,intermittent:Truth};
type ExposureInput = {condition_code:ConditionCode,minutes:Number|null,evidence:Evidence};
type CriterionCommon = {condition_present:Truth,evidence:Evidence,posture_interpretation_pending:boolean};
type C1Input = CriterionCommon & {criterion_no:1};
type C2Input = CriterionCommon & {criterion_no:2};
type C3Input = CriterionCommon & {criterion_no:3};
type C4Input = CriterionCommon & {criterion_no:4,unsupported:Truth,posture_restricted:Truth};
type C5Input = CriterionCommon & {criterion_no:5};
type C6Input = CriterionCommon & {criterion_no:6,unsupported:Truth,pinch_mass_kg:Number|null,pinch_force_kg_equiv:Number|null};
type C7Input = CriterionCommon & {criterion_no:7,unsupported:Truth,single_hand_mass_kg:Number|null,grip_force_kg_equiv:Number|null};
type C8Input = CriterionCommon & {criterion_no:8};
type C9Input = CriterionCommon & {criterion_no:9,below_knee_count_day:Count|null,above_shoulder_count_day:Count|null,extended_arm_count_day:Count|null,union_count_day:Count|null,union_evidence:Evidence};
type C10Input = CriterionCommon & {criterion_no:10,lift_rate_min:Number|null};
type C11Input = CriterionCommon & {criterion_no:11,impact_rate_hour:Number|null};
type CriterionInput = C1Input|C2Input|C3Input|C4Input|C5Input|C6Input|C7Input|C8Input|C9Input|C10Input|C11Input;
type LegalInputs = {lift_count_day:Count|null,criteria:CriterionInput[],exposures:ExposureInput[]};
type PhotoInfo = {photo_id:ID,task_id:ID,file_path:string,file_name:string,width_px:Count|null,height_px:Count|null,consent:Truth,notes:Diagnostic[]};
type FileFailure = {file_path:string,message:string};
type ImportReport = {added:PhotoInfo[],unreadable:FileFailure[],notes:Diagnostic[]};
type CaptureObservation = {phase_verified:Truth,load_state:LoadState,single_person:Truth,full_frame:Truth,camera_fixed:Truth,normal_cycle:Truth,evidence:Evidence};
type CaptureSlot = {slot_no:Count,cycle_no:Count,phase:Phase,photo_id:ID|null,observation:CaptureObservation};
type CaptureSet = {protocol:'BOX_LIFT_15_V1',camera_side:Side|null,forward_direction:Forward|null,slots:CaptureSlot[]};
type ManualField = 'trunk_base'|'trunk_twisted'|'trunk_side_bent'|'neck_base'|'neck_twisted'|'neck_side_bent'|'legs_support'|'seated'|'knee_band'|'shock_force'|'upper_arm_base'|'arm_abducted_or_rotated'|'shoulder_raised'|'arm_supported_or_gravity_assisted'|'lower_arm_base'|'wrist_base'|'wrist_deviated_or_twisted'|'coupling'|'static_over_1min'|'small_repeat_over_4min'|'rapid_change_or_unstable'|'hand_above_head'|'elbow_above_shoulder'|'elbow_behind_trunk'|'squat'|'kneel';
type ManualValue = {slot_no:Count,photo_id:ID,scope:'COMMON'|'LEFT'|'RIGHT',field:ManualField,value:Number|Truth|LegsSupport|KneeBand|Coupling|null,source:'AUTO_ACCEPTED'|'DIRECT_OBSERVATION'|'INTERVIEW'|null,evidence:Evidence};
type TaskDraft = {task_kind:'FLOOR_TO_SHELF_BOX_SINGLE_PERSON',task_name:string,conditions:TaskConditions};
type Task = TaskDraft & {task_id:ID,survey_id:ID,worker_count:1,input_revision:Count,legal:LegalInputs,capture:CaptureSet,manual:ManualValue[],latest_analysis_id:ID|null,created_at:Timestamp,updated_at:Timestamp};
type TaskInputBundle = {task:Task,exclusions:Exclusions,photos:PhotoInfo[],settings:AnalysisSettings};
```

작업 생성 시15고정 슬롯, 기준1..11 하나씩,20조건 시간 하나씩을 빈값으로 만든다. 슬롯 순서는 기능정의서 §2. 입력은 부분 상태로 저장할 수 있다. 중량/높이>0, 시간0..1440, months/days/횟수≥0이 계산상 의미 범위다. 범위 밖/모순은 계산 결과에 INPUT_CONFLICT를 표시하며 저장 가드를 만들지 않는다.

short_term/intermittent 파생은 기능정의서 §5. 자세 해석 pending은3/4/5/9에 사용한다. 근거는 권장 입력, 미기입도 저장한다. ManualValue의 scope/범주는 기능정의서 §4 표와 같다. 마지막5개 태그전용 필드는 COMMON/Truth, seated도 Truth. neck_base/wrist_base는 자동 좌표로 생성하지 않는다. 사진 교체 시 해당 슬롯 manual/observation을 비워 둔다. 사진이 없는 슬롯에는 manual을 자동 생성하지 않는다.

자동 후보 수용은trunk_base/upper_arm_base/lower_arm_base/knee_band만AUTO_ACCEPTED로 기록한다. 비틀림/지지/손목/쥐기/충격/활동은 현장 관찰·면담 입력이다. 이 구분은 값의 출처이며 별도 승인/차단 가드를 요구하지 않는다.

## 4. 분석·결과 DTO

```typescript
type PoseModel = {name:string,version:string,preprocess_version:string,input_size:192,point_count:17,confidence_min:0.5};
type PostureProfile = {version:'POSTURE_TECH_V1',neck_forward_deg:Number,trunk_flex_deg:Number,trunk_extension_deg:Number,upper_arm_raise_deg:Number};
type AnalysisSettings = {pose_model:PoseModel,posture_profile:PostureProfile,reba_rule:'REBA_TABLE_2000_V1',burden_rule:'MOEL_2020_12_V1'};
type TaskSnapshot = {schema_version:'1.2',task_id:ID,input_revision:Count,task_name:string,conditions:TaskConditions,legal:LegalInputs,capture:CaptureSet,manual:ManualValue[],photos:PhotoInfo[],settings:AnalysisSettings};
type Keypoint = {point_no:Count,name:string,x_px:Number,y_px:Number,confidence:Number};
type Angle = {side:Side,angle_code:AngleCode,value_deg:Number|null,min_confidence:Number|null,diagnostic:string|null};
type SlotPoseResult = {slot_no:Count,photo_id:ID|null,status:SlotStatus,diagnostics:Diagnostic[],points:Keypoint[],angles:Angle[]};
type PoseResult = {status:RunStatus,valid_count:Count,total_slot_count:15,terminal_error:string|null,slots:SlotPoseResult[]};
type PoseRequest = {snapshot:TaskSnapshot};
type TagRequest = {pose:PoseResult|null,snapshot:TaskSnapshot};
type SlotTag = {slot_no:Count,tag:TagCode,value:Truth,source:'ANGLE'|'MANUAL'|'UNKNOWN'};
type TagSummary = {tag:TagCode,yes_count:Count,observed_count:Count,valid_pose_count:Count,manual_observed_count:Count,total_slot_count:15,sample_ratio:Number|null};
type TagResult = {slots:SlotTag[],summary:TagSummary[]};
type RebaSideScore = {side:Side,trunk:Count|null,neck:Count|null,legs:Count|null,table_a:Count|null,load_score:Count|null,score_a:Count|null,upper_arm:Count|null,lower_arm:Count|null,wrist:Count|null,table_b:Count|null,coupling_score:Count|null,score_b:Count|null,table_c:Count|null,activity_score:Count|null,total:Count|null,risk:Risk|null,missing_fields:string[],review_reasons:ReviewReason[]};
type RebaSlotResult = {slot_no:Count,photo_id:ID|null,load_state:LoadState,effective_load_kg:Number|null,status:'COMPLETE'|'INCOMPLETE',left:RebaSideScore,right:RebaSideScore,selected_side:Side|null,total:Count|null,risk:Risk|null,missing_fields:string[]};
type RebaSummary = {complete_count:Count,total_slot_count:15,available_max:Count|null,full_max:Count|null,representative_slot_no:Count|null,selection:'AUTO'|'MANUAL'|null};
type RebaResult = {status:'COMPLETE'|'INCOMPLETE',slots:RebaSlotResult[],summary:RebaSummary};
type RebaRequest = {pose:PoseResult|null,snapshot:TaskSnapshot};
type BasisItem = {item_code:string,value:Number|Truth|null,unit:'MIN_DAY'|'KG'|'KG_EQUIV'|'COUNT_DAY'|'COUNT_MIN'|'COUNT_HOUR'|'BOOLEAN',operator:'GE'|'LE'|'EQ'|'OR'|null,threshold:Number|null,source:string};
type InvestigatorConclusion = {criterion_no:Count,status:FinalStatus|null,reason:string|null,evidence:Evidence,reviewer:string|null,reviewed_at:Timestamp|null};
type Judgment = {criterion_no:Count,computed_status:JudgmentStatus,exclusion:'SHORT_TERM'|'INTERMITTENT'|'BOTH'|null,basis:BasisItem[],missing_fields:string[],review_reasons:ReviewReason[],source:string,investigator:InvestigatorConclusion,effective_status:JudgmentStatus};
type JudgmentResult = {judgments:Judgment[]};
type BurdenRequest = {conditions:TaskConditions,legal:LegalInputs,rule_version:'MOEL_2020_12_V1'};
type Warning = {criterion_no:Count,from:'COMPUTED'|'INVESTIGATOR',message:string};
type Analysis = {analysis_id:ID,task_id:ID,input_revision:Count,snapshot:TaskSnapshot,status:JobStatus,pose:PoseResult|null,slot_tags:SlotTag[],tags:TagSummary[],reba:RebaResult|null,judgment:JudgmentResult|null,ai:AiText[],notes:Diagnostic[],created_at:Timestamp,finished_at:Timestamp|null,currentness:Currentness};
type RunHandle = {analysis_id:ID,task_id:ID,status:JobStatus};
type TaskResult = {task:Task,currentness:Currentness,analysis:Analysis|null,warnings:Warning[],review_current:boolean};
```

Analysis.input_revision=현재TASK.input_revision이고 latest_analysis_id가 해당 행이면 CURRENT, 이전이면 STALE, 결과 없음 NONE. currentness/review_current는 저장 부울을 신뢰하지 않고 조회에서 계산한다. 포즈 완료와 REBA/고시 완전성은 독립이다. PoseResult.slots/RebaResult.slots는15개, JudgmentResult.judgments는11개다. 추론한 슬롯 points17개·angles좌우×7개, 미처리 슬롯은 빈 배열이다. 읽을 수 없는 사진은 슬롯 ERROR, 빈 슬롯은 INVALID/MISSING_PHOTO.

JobStatus FINISHED는 요청한 모듈 처리 완료이고 PoseResult의 DONE과 다르다. 포즈가 FAILED여도 고시/수동REBA 결과를 반환한 작업은 FINISHED일 수 있다. 조사 review_current는 reviewed=true, 검토 당시 metadata_revision 일치, 현존 작업별 최신CURRENT 분석ID 목록 일치일 때 true다. set_survey_review에서 서비스가 현재 metadata_revision을 기록한다. 이는 검토표시 계산이며 버튼을 차단하지 않는다.

REBA total/risk는 모든 인자가 확인됐을 때만 존재한다. 양쪽 중 미완전이면 selected_side/전체 total/risk null. RebaResult.status COMPLETE는15슬롯 모두COMPLETE일 때이고 그 외INCOMPLETE다. full_max도15개완전일 때만 존재한다. 기술태그 입력은 POSTURE_TECH_V1이고 REBA/고시 기준을 바꾸지 않는다. 수동 관찰이 없는 태그 UNKNOWN은 observed_count에서 제외한다.

TagResult.slots는15슬롯×11태그, summary는11태그다. 서비스는 slots를Analysis.slot_tags, summary를Analysis.tags에 저장한다. 미계산 태그는 둘 다빈배열, 계산했다면 관측불가도UNKNOWN 항목을 남긴다. manual_observed_count는 source=MANUAL인 YES/NO수다. S06의 사진별 태그는 slot_tags에서 읽으며 UI가 같은 분류를 다시 구현하지 않는다. PostureProfile 기본값은20/20/−20/45°이며 실제 설정값은 snapshot에 보존한다.

## 5. 서비스 호출

반환은 모두 Result<T>다. actor/expected_version/guard 인자는 두지 않는다. 검토자 입력은 SurveyDraft/ReviewMark/InvestigatorConclusion의 실제 필드로 기록한다. 설정의 분석모델/태그프로필이 바뀌면 해당 설정을 쓰는 작업 input_revision을 올리고 재계산 필요를 표시한다.

| method | params | value | 화면 |
|---|---|---|---|
| list_surveys | 없음 | SurveySummary[] | S01 |
| get_survey | survey_id:ID | Survey | S02 |
| create_survey | draft:SurveyDraft | Survey | S02 |
| update_survey | survey_id:ID,draft:SurveyDraft | Survey | S02 |
| delete_survey | survey_id:ID | Ack | S01 |
| list_tasks | survey_id:ID | Task[] | S03 |
| create_task | survey_id:ID,draft:TaskDraft | Task | S03 |
| get_task | task_id:ID | TaskInputBundle | S03 |
| rename_task | task_id:ID,task_name:string | Task | S03 |
| set_task_conditions | task_id:ID,conditions:TaskConditions | Task | S03 |
| set_legal_inputs | task_id:ID,legal:LegalInputs | Task | S03/S07 |
| delete_task | task_id:ID | Ack | S03 |
| import_photos | task_id:ID,file_paths:string[] | ImportReport | S04 |
| update_photo | photo_id:ID,file_path:string,consent:Truth | PhotoInfo | S04 |
| delete_photo | photo_id:ID | Ack | S04 |
| set_capture | task_id:ID,capture:CaptureSet | Task | S04 |
| start_analysis | task_id:ID | RunHandle | S05 |
| get_analysis | analysis_id:ID | Analysis | S05 |
| cancel_analysis | analysis_id:ID | RunHandle | S05 |
| set_manual_values | task_id:ID,manual:ManualValue[] | Task | S06 |
| recalculate_reba | task_id:ID | Analysis | S06 |
| recalculate_judgments | task_id:ID | Analysis | S07 |
| recalculate_tags | task_id:ID | Analysis | S06/S09 |
| get_task_result | task_id:ID | TaskResult | S06/S07 |
| list_analysis_history | task_id:ID | Analysis[] | S06 |
| select_representative | analysis_id:ID,slot_no:Count | Analysis | S06 |
| set_investigator_conclusion | analysis_id:ID,conclusion:InvestigatorConclusion | Analysis | S07 |
| set_survey_review | survey_id:ID,review:ReviewMark | Survey | S07 |
| generate_ai_text | analysis_id:ID,purpose:AiPurpose | AiText | S06/S07 |
| edit_ai_text | analysis_id:ID,purpose:AiPurpose,text:string | AiText | S06/S07 |
| apply_ai_text | analysis_id:ID,purpose:AiPurpose,use_edited:boolean | AiText | S06/S07 |
| preview_excel | survey_id:ID,analysis_ids:ID[] | ReportOverview | S08 |
| export_excel | survey_id:ID,spec:ExportSpec | ExportReceipt | S08 |
| get_settings | 없음 | Settings | S09 |
| update_settings | settings:Settings | Settings | S09 |

set_manual_values는 현재15배정에 대한 전체 목록 교체다. start_analysis는 snapshot을 만들고 pose/tag/reba/burden을 수행한다. 재계산 명령은 요청 모듈만 실행해 새 ANALYSIS행을 만들고 다른 모듈은 관련 입력이 같은 기존 출력만 복사한다. 다른 모듈의 입력도 바뀌었다면 그 출력은 null(태그는 빈 배열)과 재계산 안내를 반환한다. 과거 계산을 현재로 복사하지 않는다. recalculate_judgments는 pose 없이도 실행 가능하다. 취소는 요청 후 get_analysis로 처리 상태를 읽는다. 이미 끝난 분석이면 같은 상태를 반환한다.

update_photo는 같은 원본 경로 재연결/동의 기록이다. 내용이 다른 사진은 새 등록 후 set_capture로 교체한다. delete_photo는 현재배정을 비우고 history snapshot의 메타/수치를 남긴다. 역사이미지는 파일이 없으면 표시하지 않는다. snapshot은 원본 바이트를 고정하지 않으며 외부에서 원본을 바꾸는 자동감지는 데모에 없다.

조건/고시/배정/수동값/작업명/배정사진 경로·관찰 저장은 input_revision 증가, 현재/과거 표시를 갱신한다. 미배정 후보사진 등록/삭제는 계산 입력을 바꾸지 않는다. 조사자 결론/대표/설명/검토는 해당 분석의 표시값을 수정하며 계산 입력 revision을 올리지 않는다. 새 분석행에는 조사자 결론/설명/검토를 자동 승계하지 않는다. 조사 메타는 metadata_revision만 증가한다. 작업명 변경 시 계산은 재사용할 수 있지만 새 표시snapshot이 필요하다.

같은 분석의 조사자 결론을 변경/해제하면SURVEY.review.reviewed=false로 갱신한다. 대표사진/설명문만 바꾸면 계산검토 표시는 유지한다. 검토는 조작 가능한 표시이며 변경/미완전 때문에 기능을 막지 않는다.

카메라/작업자/방법/높이 변경은 전체 사건확인·manual을 비워 두고 모델/전처리 변경은 AUTO_ACCEPTED 값만 비운다. 직접 관찰이 같은 사진에 남아 있으면 그대로 사용할 수 있다. 하중은phase_verified와사건별load_state를 사용하며 미확인/불일치는 해당 effective_load_kg null이다. select_representative에 미완전 슬롯을 고르면 기존대표/없음을 유지하고 notes로 알린다. 사진 미리보기는 점수대표 선택과 별개다. 삭제된 작업/분석을 늦은 완료응답으로 다시 생성하지 않는다.

## 6. GPT·설정

```typescript
type AiPurpose = 'TASK_EXPLANATION'|'IMPROVEMENT_ADVICE';
type NumericBasis = {item_code:string,value:Number|Truth|null,unit:string,operator:string|null,threshold:Number|null};
type NumericCriterion = {criterion_no:Count,effective_status:JudgmentStatus,basis:NumericBasis[]};
type NumericSummary = {purpose:AiPurpose,complete_reba_count:Count,total_slot_count:15,available_max:Count|null,full_max:Count|null,tag_counts:TagSummary[],criteria:NumericCriterion[]};
type AiText = {purpose:AiPurpose,result:'GENERATED'|'FALLBACK'|'DISABLED',generated_text:string|null,edited_text:string|null,applied_text:string|null,applied_kind:'MODEL'|'INVESTIGATOR'|'FALLBACK'|null,model:string,prompt_version:string,created_at:Timestamp};
type Settings = {analysis:AnalysisSettings,gpt_enabled:boolean,gpt_model:string,gpt_key_present:boolean};
```

NumericSummary는 서비스가 계산결과에서 구성한다. BasisItem.source·근거·이름·사진·경로·좌표·내부 ID는 없다. 공개 기준 설명은 내장 문구다. explanation 모듈은 이 DTO로 문장을 요청하며 별도 보안 가드/수치검증기/승인 흐름은 없다. 키는 OPENAI_API_KEY 실행환경을 읽고 Settings에는 존재 여부만 반환한다. gpt_key_present는 읽기전용 파생값이다.

timeout10초/요청실패/키없음은 고정 설명 FALLBACK, 비활성은 DISABLED. 로컬 계산을 실패로 바꾸지 않는다. 각 분석에 purpose별1개 AiText를 저장하며 생성본/수정본/적용본은 별도 필드다. 이전 결과의 설명을 새 결과에 자동 적용하지 않는다.

## 7. Excel

### 7.1 출력·미리보기 DTO

```typescript
type ExportSpec = {destination:string,analysis_ids:ID[],include_representative:boolean};
type ExportSnapshot = {schema_version:'1.2',report_version:'1.2',survey:Survey,tasks:Task[],analyses:Analysis[],unanalysed_task_ids:ID[],exported_at:Timestamp};
type ReportCounts = {needs_input_count:Count|null,needs_review_count:Count|null,incomplete_reba_count:Count|null};
type NextInputItem = {module:'ANALYSIS'|'REBA'|'BURDEN',kind:'NOT_CALCULATED'|'MISSING_INPUT'|'REVIEW_REQUIRED',slot_no:Count|null,criterion_no:Count|null,field_paths:string[],reason_codes:string[],message:string};
type ReportTaskOverview = {task_id:ID,task_name:string,analysis_id:ID|null,input_revision:Count,currentness:Currentness,counts:ReportCounts,next_inputs:NextInputItem[]};
type ReportOverview = {report_version:'1.2',counts:ReportCounts,tasks:ReportTaskOverview[]};
type ExportReceipt = {export_id:ID,file_path:string,sheets:string[],reviewed:boolean,has_incomplete:boolean,has_stale:boolean,created_at:Timestamp};
```

분석 선택은 작업별 한 행이다. 명령 시 현존 모든 task를 포함하고 선택하지 않은 작업은 최신분석 또는 미분석15/11빈행을 넣는다. 과거/미완전 분석도 내보낸다. 동일작업을 두 번 선택하면 UI에서 한 행을 고르는 선택 화면을 제공한다. 보고서에 서로 다른 모듈 결과를 임의로 조합하지 않고 선택한 ANALYSIS의 snapshot을 쓴다. 분석없는 작업은 현재 입력을 쓴다.

| sheet | 정확한 열(순서 고정) |
|---|---|
| SUMMARY | task_id,task_name,analysis_id,input_revision,survey_id,survey_title,survey_date,investigator,department,process,currentness,reviewed,review_current,valid_pose_count,complete_reba_count,available_max,full_max,representative_slot_no,applicable_criteria,needs_input_count,needs_review_count,incomplete_reba_count,next_inputs,notes,applied_explanation,report_notice |
| TASK_INPUTS | task_id,analysis_id,input_revision,input_group,item_code,value,unit,source,evidence_text,observed_at |
| PHOTO_REBA | task_id,analysis_id,slot_no,cycle_no,phase,pose_status,load_state,effective_load_kg,left_total,right_total,selected_side,total,risk,missing_fields,diagnostics,image |
| CRITERIA | task_id,analysis_id,criterion_no,computed_status,investigator_status,effective_status,exclusion,comparison_values,source,evidence_text,review_reasons,missing_fields,investigator_reason,reviewer,reviewed_at,warning |

PHOTO_REBA 작업당15행, CRITERIA 작업당11행. TASK_INPUTS는 조건/20시간/11기준입력/15배정관찰/수동값/모델·규칙버전을 행으로 펼친다. image열은 대표 상세블록 참조/이미지 생략 사유를 쓰며 실제 사진은 표 밖의 고정 블록에 넣는다. report_notice는 기능정의서 §9 고정 문구다. 미계산 값은 빈칸이며 초안/조사자결론/현재성/완전성/검토를 각각 표시한다.

선택분석이 있으면 task_name/조건/수동값/사진배정은Analysis.snapshot에서 읽는다. ExportSnapshot.tasks는 현재 작업목록·현재성 비교에 사용한다. 분석없는 작업만Task의 현재입력을 출력한다. 누락 설명은SUMMARY.notes, 관절·각도는TASK_INPUTS의 input_group=RESULT_POSE, 태그/사진별관찰은RESULT_TAG, REBA구성점수는RESULT_REBA로 펼친다. angle은unit=DEG,관절좌표는PX,confidence는RATIO로 쓴다. NumericSummary.tag_counts는Analysis.tags를 사용한다. SUMMARY.applied_explanation은TASK_EXPLANATION의 적용문이고 개선문은TASK_INPUTS의 input_group=EXPLANATION에 기록한다.

### 7.2 미리보기·집계·다음 입력

preview_excel과 export_excel은 같은 분석 선택 규칙으로 ExportSnapshot을 구성하고 report의 같은 파생값 구성 함수를 사용한다. preview_excel은 ReportOverview만 반환하며 파일/EXPORT_LOG를 만들지 않는다. export_excel은 호출 시점의 새 snapshot으로 파일을 쓰고 성공 로그를 저장한다. 미리보기 후 입력이 바뀌면 실제 출력 시점의 상태를 사용한다. 미리보기 일치 가드/승인 절차는 없다. 내부 미리보기 snapshot의 exported_at을 실제 파일 출력 시각으로 안내하지 않는다.

ReportTaskOverview의 작업명/input_revision은 선택 분석 snapshot, 분석이 없으면 현재 Task에서 읽는다. currentness는 ExportSnapshot.tasks의 현재 입력과 선택 analysis_id를 비교한다. ReportOverview/ReportCounts/NextInputItem은 파생값이며 Task/Analysis에 저장하지 않는다. 집계 규칙은 기능정의서 §9.2다. 조사 합계는 해당 결과가 모든 작업에 있을 때만 합산하고, 없는 작업이 있으면 해당 항목만 null이다.

NextInputItem은 미분석이면 ANALYSIS/NOT_CALCULATED 한 항목, 분석은 있으나 reba/judgment가 null이면 각각 REBA/BURDEN의 NOT_CALCULATED를 만든다. 결과가 있으면 슬롯별 누락과 기준별 누락/검토 사유를 모두 만든다. 같은 module/slot_no/criterion_no/kind는 한 항목으로 묶고 field_paths/reason_codes의 중복을 제거한다. 좌우 REBA 경로는 left./right.를 유지하고 공통 누락은 두 번 표시하지 않는다. field_paths는 원래 누락 경로, reason_codes는 원래 검토 사유이며 둘 다 빈 배열일 수 있다. message는 내장된 항목명과 회차·phase·좌우·기준 번호로 생성한다. 미분석/미계산 안내→슬롯1..15→기준1..11 순서이며 같은 대상의 MISSING_INPUT을 REVIEW_REQUIRED보다 먼저 표시한다. GPT/새 경고 이력은 사용하지 않는다.

SUMMARY의 세 count열은 ReportTaskOverview.counts, next_inputs는 next_inputs[].message를 모두 줄바꿈해 표시한다. applicable_criteria는 effective_status=APPLICABLE의 번호와 출처(COMPUTED/INVESTIGATOR)를 함께 적고 확정 목록으로 표현하지 않는다. 적용 설명에는 applied_kind도 표시한다. 조사 전체 집계는 고정 요약영역의 ReportOverview.counts를 사용한다. null숫자는 빈칸과 사유, 실제0은 숫자0이다. 미분석의 판정/REBA 수치를 추측해 채우지 않는다.

### 7.3 식별정보·상세블록·서식

각 시트 제목영역에 ExportSnapshot.report_version/schema_version/exported_at과 survey_id를 표시한다. SUMMARY 작업표에는 task_id/analysis_id/input_revision, TASK_INPUTS의 input_group=SETTINGS에는 snapshot.settings의 모델/전처리/태그/REBA/고시 버전을 넣는다. TASK_INPUTS.item_code는 슬롯/좌우/관절/태그/필드를 구별하는 경로다. RESULT_POSE/RESULT_TAG/RESULT_REBA의 슬롯별 값에는 슬롯번호와 COMMON/LEFT/RIGHT를 경로에 포함한다. 집계 태그는 태그코드/필드로 구별한다. 모든 세부값은 같은 선택 분석에서 읽는다.

PHOTO_REBA의 image열은 선택 대표 행에 ‘대표 상세블록 참조’ 또는 ‘이미지 제외/원본을 읽을 수 없음’을 표시하고 나머지는 빈칸이다. 실제 이미지는 표 밖의 고정 대표 상세블록에 한 번 넣는다. include_representative=false이면 이미지만 생략하고 식별자/수치는 표시한다. 대표가 없으면 그 사유를 표시하며 임의 사진을 대표로 대체하지 않는다.

대표 블록 식별자는 task_id/analysis_id/slot_no/cycle_no/phase와 snapshot.capture.slots의 photo_id다. 하중/좌우total/selected_side/total/risk와 선택측 RebaSideScore의 trunk/neck/legs/upper_arm/lower_arm/wrist/table_a/load_score/score_a/table_b/coupling_score/score_b/table_c/activity_score/missing_fields를 표시한다. 선택측이 null이면 구성점수를 임의측으로 채우지 않고 누락을 표시한다. SUMMARY의 available_max/full_max와 대표 total은 각각 이름 붙여 표시한다.

CRITERIA.comparison_values는 Judgment.basis의 모든 BasisItem을 item_code/value/unit/operator/threshold/source 순서로 한 줄씩 표시한다. basis가 없으면 ‘비교근거 없음’이다. CRITERIA.source/evidence_text는 앱의 기준 출처/해당 기준 직접입력 Evidence, investigator_reason은 조사자 사유와 그 Evidence의 source/text/observed_at을 구분해 줄바꿈한다. 조사자 근거가 계산 근거를 대체하지 않는다. TASK_INPUTS에는 조건/노출/조사자 근거를 각각 행으로 펼친다. RESULT_TAG에는 각 TagSummary의 yes_count/observed_count/valid_pose_count/manual_observed_count/total_slot_count/sample_ratio를 모두 출력한다. sample_ratio는 RATIO, 시간은 MIN_DAY이며 사진 비율에서 파생한 시간행은 없다.

시각은 UTC 저장값을 Asia/Seoul로 변환해 Excel 날짜/시각 타입으로 쓴다. 날짜 yyyy-mm-dd, 시각 yyyy-mm-dd hh:mm, 비율0.0%, 실수0.00, 수/호/점수는 정수 표시다. ID/코드/상태/근거는 식별 가능한 글자로 쓴다. 상세 서식·필터·고정 위치·상태 문구는 화면설계서 S08을 따른다. report는 저장 결과와 파생 집계를 표시하며 Excel 수식으로 REBA/법 판정을 재계산하지 않는다.

## 8. 오류와 안내

AppError는 파일/모델/DB/Excel의 실행 오류와 없는 ID만 표현한다. 슬롯별 MISSING_PHOTO/UNREADABLE_FILE/LOW_CONFIDENCE/MISSING_CAMERA는 diagnostics, 계산의 누락/모순은 missing_fields/review_reasons다.15슬롯 미완성·수동입력 누락·미확인 근거·중복사진·동의 미기입 때문에 전체 기능을 차단하지 않는다.

구 `ergo/contracts.py`와 기존 시험은 이전 프로토타입 계약이다. 새 모듈 API의 구현으로 간주하지 않는다. 이 문서를 자동 생성하거나 새 테스트/가드로 강제하지 않는다.
