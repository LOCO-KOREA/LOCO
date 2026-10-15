# API 계약서

> 문서 ID ERGO-API-001 · 설계 버전 1.5 · 기준일 2026-10-15 · 데모 개발 기준

## 1. 경계·모듈

Windows Electron renderer(UI)→preload→main→로컬 Python Application Service 계약이다. 아래 타입 표기는 설계이며 구현 코드가 아니다. 화면은 HTML/CSS/JavaScript 계열로 작성하고 계산·저장·Excel은 Python이 담당한다. 서비스는 모듈들을 순서대로 호출하고 storage에 저장한다. 계산 모듈은 DB를 직접 읽거나 서로의 내부 함수를 호출하지 않는다. 문서 버전1.5는 로코 공통 안내 위젯과 설정 저장 계약까지 반영하며 TaskSnapshot/ExportSnapshot.schema_version과 report_version은1.3이다. `loco-guide-action`과 `loco-guide-preference-change`는 renderer 내부 이벤트로 Python API 메서드가 아니다. renderer가 화면 동작을 처리하고 설정 이벤트만 `update_settings` 호출로 저장한다.

| 모듈 | 입력→출력 | 책임 |
|---|---|---|
| survey | SurveyDraft/ReviewMark→Survey | 조사·검토 표시 |
| task_input | TaskConditions/LegalInputs/ManualValue→Task | 입력·input_revision·수정 영향 |
| capture | 사진경로/배정→PhotoInfo/CaptureSet/PhotoPreview | 다중사진·15슬롯·촬영 관찰·EXIF 미리보기 |
| pose | PoseRequest→PoseResult, TagRequest→TagResult | 17관절·각도·태그 |
| reba | RebaRequest→RebaResult | 사진별 자동 후보·좌우 점수표 |
| burden | BurdenRequest→JudgmentResult | 직접입력으로11호 초안 |
| explanation | NumericSummary→생성문자열 | 선택 GPT 설명 |
| report | build_overview(snapshot)→ReportOverview, render(snapshot,destination)→RenderedReport | 공통 상태·집계·다음 입력 안내·네 시트 렌더링 |
| storage | 아래 DTO↔SQLite/JSON | 저장·읽기·서비스 삭제 |

expected_version/WriteGuard/승인 토큰/잠금 API/보안검증기는 없다. 미입력·모순·부분분석은 반환 결과의 notes/missing_fields/review_reasons로 표시한다. 저장·분석·초안 내보내기는 이런 상태에서도 사용할 수 있다. 읽을 수 없는 파일·모델·DB·출력 오류는 정상 오류 처리이며 운영 차단정책이 아니다.

### 1.1 Electron·Python 호출 연결

renderer는 preload의 window.loco.call(method,params)을 호출한다. preload는 ipcRenderer.invoke의 loco:call 채널로 main에 전달하고 main은 Python 프로세스 stdin으로 아래 요청 한 줄을 보낸다. Python은 기존 §5 서비스 메서드를 호출하고 stdout으로 응답 한 줄을 돌려준다. 구조는 [Electron 프로세스 문서](https://www.electronjs.org/docs/latest/tutorial/process-model)와 [IPC 문서](https://www.electronjs.org/docs/latest/tutorial/ipc)를 따른다.

```typescript
type BridgeRequest = {request_id:number,method:string,params:Record<string,unknown>};
type BridgeResponse<T> = {request_id:number,result:Result<T>};
type DesktopBridge = {
  call<T>(method:string,params:Record<string,unknown>):Promise<Result<T>>;
  choose_photo_paths():Promise<string[]>;
  path_for_file(file:File):string;
  choose_export_destination():Promise<string|null>;
};
```

request_id는 main이 요청마다 붙이는 통신용 정수이며 같은 ID의 응답을 해당 Promise에 연결한다. 분석ID/input_revision/승인 토큰이 아니며 DB에 저장하지 않는다. params의 키/반환 Result<T>는 §5의 계약과 같다. JSON은 UTF-8이며 한 메시지마다 줄바꿈 한 개로 구분하고 stdout 조각을 줄 단위로 모아 읽는다. 줄 안의 문자열 줄바꿈은 JSON 이스케이프를 사용한다. Python 전송부는 완료 응답을 한 메시지씩 stdout에 써서 동시에 끝난 작업의 메시지가 섞이지 않게 한다. stdout은 응답 전용, Python 로그는stderr로 보낸다. HTTP 서버/별도 이벤트 버스/통신용 DB 테이블은 없다.

main은 앱 시작 시 Node child_process.spawn으로 로컬 Python 실행파일과 서비스 진입파일을 별도 인자로 전달해 프로세스 하나를 실행한다. Windows 콘솔창은 windowsHide=true로 숨기고 stdin/stdout은UTF-8로 맞춘다. Python 출력은 버퍼에 남지 않게 메시지마다 flush한다. 앱 종료 시 자식 프로세스도 종료한다. 개발 실행 설정에 Python 실행파일/진입파일 위치를 두며 APP_SETTINGS에는 추가하지 않는다. Python 서비스는 장시간 분석을 백그라운드에서 실행하고 요청 읽기/진행 조회/취소 처리를 계속한다. 호출별 request_id로 응답을 연결하며 응답 순서를 요청 순서로 가정하지 않는다. 계산 실패는 기존 Result.error/슬롯 진단으로, 프로세스 시작 실패·중단·통신 실패는 해당 call의 Promise 오류로 표시한다. 별도 재시작 정책/동시실행 차단/승인 절차를 만들지 않는다. [Node 자식 프로세스 문서](https://nodejs.org/api/child_process.html)

choose_photo_paths는 main의 dialog.showOpenDialog(openFile,multiSelections) 결과 filePaths를 반환한다. 사용자가 취소하면 빈 배열이다. 끌어놓기의 path_for_file은 preload의 webUtils.getPathForFile을 사용하고, 경로 없는 항목은 해당 사진 안내로 표시한다. choose_export_destination는 main의 dialog.showSaveDialog에서 선택한 Excel 경로 또는 취소null을 반환한다. 이 세 함수는 데스크톱 파일 연결이며 Python 서비스/DB 메서드가 아니다. [Electron dialog](https://www.electronjs.org/docs/latest/api/dialog), [webUtils](https://www.electronjs.org/docs/latest/api/web-utils)

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
type PhotoPreview = {photo_id:ID,data_url:string,width_px:Count,height_px:Count};
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

PhotoPreview는 capture가 원본을 읽어 EXIF 방향을 적용한 이미지 data URL과 그 픽셀 크기를 반환하는 조회 DTO다. 미리보기는 원본을 저장/복사하거나 TASK/ANALYSIS/PHOTO JSON에 추가하지 않는다. pose 좌표와 같은 EXIF 적용 후 원본 크기이며 화면 표시 축소 시 UI가 표시 크기 비율로 좌표를 맞춘다. get_photo_preview의 PhotoInfo는 현재 사진목록 또는 선택 분석 snapshot.photos에서 전달하므로 PHOTO행이 삭제된 과거 사진도 원본 경로가 존재하면 표시할 수 있다. 원본을 못 읽으면 FILE_ERROR와 화면 안내를 반환하고 저장된 수치/다른 사진은 유지한다.

short_term/intermittent 파생은 기능정의서 §5. 자세 해석 pending은3/4/5/9에 사용한다. 근거는 권장 입력, 미기입도 저장한다. ManualValue의 scope/범주는 기능정의서 §4 표와 같다. 마지막5개 태그전용 필드는 COMMON/Truth, seated도 Truth. neck_base/wrist_base는 자동 좌표로 생성하지 않는다. 사진 교체 시 해당 슬롯 manual/observation을 비워 둔다. 사진이 없는 슬롯에는 manual을 자동 생성하지 않는다.

자동 후보 ‘값 적용’은trunk_base/upper_arm_base/lower_arm_base/knee_band만AUTO_ACCEPTED로 기록한다. 목은 중립/0..20° 굴곡1, >20° 굴곡/모든 신전2, 관찰불가null이며 수동 선택한다. 선택한 목 자세문구는 ManualValue.evidence.text에 기존 근거와 함께 기록한다. neck_base=2만으로 굴곡/신전을 구별하지 않는다. 비틀림/지지/손목/쥐기/충격/활동은 현장 관찰·면담 입력이다. 이 구분은 값의 출처이며 별도 승인/차단 가드를 요구하지 않는다.

burden의 결과 우선순위는 기능정의서 §5.1의 확인된 제외→해당 기준 입력모순→확실한FALSE→결론에 필요한 누락→미결정 해석→해당이다. 제외/확실한FALSE로 끝난 기준의 missing_fields/review_reasons는 비우며 무관한 누락은 원자료/notes로 남긴다. 모든 기준에 제외/일일시간 입력을 일괄 요구하지 않는다.

## 4. 분석·결과 DTO

```typescript
type PoseModel = {name:string,version:string,preprocess_version:string,input_size:192,point_count:17,confidence_min:0.5};
type PostureProfile = {version:'POSTURE_TECH_V1',neck_forward_deg:Number,trunk_flex_deg:Number,trunk_extension_deg:Number,upper_arm_raise_deg:Number};
type AnalysisSettings = {pose_model:PoseModel,posture_profile:PostureProfile,reba_rule:'REBA_TABLE_2000_V2',burden_rule:'MOEL_2020_12_V1'};
type TaskSnapshot = {schema_version:'1.3',task_id:ID,input_revision:Count,task_name:string,conditions:TaskConditions,legal:LegalInputs,capture:CaptureSet,manual:ManualValue[],photos:PhotoInfo[],settings:AnalysisSettings};
type Keypoint = {point_no:Count,name:string,x_px:Number,y_px:Number,confidence:Number};
type Angle = {side:Side,angle_code:AngleCode,value_deg:Number|null,min_confidence:Number|null,diagnostic:string|null};
type SlotPoseResult = {slot_no:Count,photo_id:ID|null,status:SlotStatus,diagnostics:Diagnostic[],points:Keypoint[],angles:Angle[]};
type PoseResult = {status:RunStatus,valid_count:Count,total_slot_count:15,terminal_error:string|null,slots:SlotPoseResult[]};
type PoseRequest = {snapshot:TaskSnapshot};
type TagRequest = {pose:PoseResult|null,snapshot:TaskSnapshot};
type SlotTag = {slot_no:Count,tag:TagCode,value:Truth,source:'ANGLE'|'MANUAL'|'UNKNOWN'};
type TagSummary = {tag:TagCode,yes_count:Count,observed_count:Count,valid_pose_count:Count,manual_observed_count:Count,total_slot_count:15,sample_ratio:Number|null};
type TagResult = {slots:SlotTag[],summary:TagSummary[]};
type CandidateField = 'trunk_base'|'upper_arm_base'|'lower_arm_base'|'knee_band';
type RebaCandidate = {slot_no:Count,photo_id:ID|null,scope:'COMMON'|'LEFT'|'RIGHT',field:CandidateField,proposed_value:Count|KneeBand|null,angles:Angle[],min_confidence:Number|null,review_reasons:ReviewReason[],diagnostics:Diagnostic[]};
type RebaSideScore = {side:Side,trunk:Count|null,neck:Count|null,legs:Count|null,table_a:Count|null,load_score:Count|null,score_a:Count|null,upper_arm:Count|null,lower_arm:Count|null,wrist:Count|null,table_b:Count|null,coupling_score:Count|null,score_b:Count|null,table_c:Count|null,activity_score:Count|null,total:Count|null,risk:Risk|null,missing_fields:string[],review_reasons:ReviewReason[]};
type RebaSlotResult = {slot_no:Count,photo_id:ID|null,candidates:RebaCandidate[],load_state:LoadState,effective_load_kg:Number|null,status:'COMPLETE'|'INCOMPLETE',left:RebaSideScore,right:RebaSideScore,selected_side:Side|null,total:Count|null,risk:Risk|null,missing_fields:string[]};
type RebaSummary = {complete_count:Count,total_slot_count:15,available_max:Count|null,full_max:Count|null,representative_slot_no:Count|null,selection:'AUTO'|'MANUAL'|null};
type RebaResult = {status:'COMPLETE'|'INCOMPLETE',slots:RebaSlotResult[],summary:RebaSummary};
type RebaRequest = {pose:PoseResult|null,snapshot:TaskSnapshot};
type BasisItem = {item_code:string,value:Number|Truth|null,unit:'MIN_DAY'|'KG'|'KG_EQUIV'|'COUNT_DAY'|'COUNT_MIN'|'COUNT_HOUR'|'MONTH'|'COUNT_YEAR'|'BOOLEAN',operator:'GE'|'LE'|'EQ'|'OR'|null,threshold:Number|null,source:string};
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

JobStatus FINISHED는 요청한 모듈 처리 완료이고 PoseResult의 DONE과 다르다. 포즈가 FAILED여도 고시/수동REBA 결과를 반환한 작업은 FINISHED일 수 있다. SurveySummary.reviewed는 SURVEY.review.reviewed를 표시한다. SurveySummary.review_current는 작업이1개 이상이고 reviewed=true, 검토 metadata_revision 일치, 현존 모든 작업에 최신CURRENT 분석이 있으며 그ID들이 모두 검토목록에 포함될 때true다. 다른 과거ID가 목록에 더 있어도 이를 바꾸지 않는다. TaskResult.review_current는 그 작업의 최신 분석에 대해 같은 포함/metadata/CURRENT 조건을 적용한다. set_survey_review에서 서비스가 현재 metadata_revision을 기록한다. 이는 검토표시 계산이며 버튼을 차단하지 않는다.

REBA total/risk는 모든 인자가 확인됐을 때만 존재한다. 양쪽 중 미완전이면 selected_side/전체 total/risk null. RebaResult.status COMPLETE는15슬롯 모두COMPLETE일 때이고 그 외INCOMPLETE다. full_max도15개완전일 때만 존재한다. 기술태그 입력은 POSTURE_TECH_V1이고 REBA/고시 기준을 바꾸지 않는다. 수동 관찰이 없는 태그 UNKNOWN은 observed_count에서 제외한다.

각 슬롯 candidates는 COMMON.trunk_base/COMMON.knee_band/LEFT.upper_arm_base/LEFT.lower_arm_base/RIGHT.upper_arm_base/RIGHT.lower_arm_base의6개다. 몸통은 camera_side의 TRUNK_TILT_VERT, 팔은 해당 측 UPPER_ARM_FLEX_TRUNK/ELBOW_FLEX, 무릎은 양쪽 KNEE_FLEX의 큰 값을 사용한다. 필요한 각도가 부족하면 proposed_value/min_confidence=null과 진단을 반환한다. angles는 참조한 Angle을 그대로 담으며 무릎은 양쪽 값 모두 필요하다. 범주·confidence·경계 사유는 기능정의서 §4.2에서 정한 대로 reba가 만든다. 후보 반환은 다른 필수 수동값의 입력과 무관하다. candidate의 slot_no/photo_id는 부모 슬롯과 같다. 적용하지 않은 후보를 점수 인자로 사용하지 않는다.

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
| get_photo_preview | photo:PhotoInfo | PhotoPreview | S04/S06 |
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
| update_settings | settings:SettingsUpdate | Settings | S09 |

set_manual_values는 현재15배정에 대한 전체 목록 교체다. S06의 선택사진 공통 편집/같은순간3회차 편집/사진별 편집은 UI가 현재 manual에 (slot_no,scope,field)로 합친 전체 배열을 보낸다. 대상의 현재 photo_id를 쓰고 선택하지 않은 값은 보존한다. 같은순간 그룹은1/6/11,2/7/12,3/8/13,4/9/14,5/10/15다. 자동 일괄 적용은 대상별 자신의 candidate를 사용하며 evidence.source=OTHER, text=근거 각도·측·최저confidence, observed_at=적용시각, ManualValue.source=AUTO_ACCEPTED다. 직접 관찰 복사는 사용자가 고른 필드/대상에만 기존 관찰 출처와 근거를 기록한다. 후보의 사진·카메라·작업맥락·모델/전처리 입력이 현재와 다르면 그 후보는null/재계산 안내로 취급한다. null 후보는 기존 수동값을 덮어쓰지 않고 자동 생성도 하지 않으며, 빈사진 슬롯도 manual을 만들지 않는다. 다른 값은 계속 저장한다. 별도 bulk/template 서비스나 DB 테이블은 없다.

start_analysis는 snapshot을 만들고 pose/tag/reba/burden을 수행한다. 재계산 명령은 요청 모듈만 실행해 새 ANALYSIS행을 만들고 다른 모듈은 관련 입력이 같은 기존 출력만 복사한다. 다른 모듈의 입력도 바뀌었다면 그 출력은 null(태그는 빈 배열)과 재계산 안내를 반환한다. 과거 계산을 현재로 복사하지 않는다. recalculate_judgments는 pose 없이도 실행 가능하다. 취소는 요청 후 get_analysis로 처리 상태를 읽는다. 이미 끝난 분석이면 같은 상태를 반환한다.

update_photo는 같은 원본 경로 재연결/동의 기록이다. 내용이 다른 사진은 새 등록 후 set_capture로 교체한다. delete_photo는 대상 photo_id가 배정된 모든 현재 슬롯을 photo_id=null로 바꾸고 observation을 phase_verified/load_state/single_person/full_frame/camera_fixed/normal_cycle='UNKNOWN', evidence={source:null,text:null,observed_at:null}로 초기화하며, TASK.manual에서 해당 photo_id의 항목을 제거한다. 이 변경이 있으면 input_revision을 한 번 증가시키고 updated_at을 갱신한 뒤 PHOTO행을 삭제한다. 미배정 사진이고 참조 manual도 없으면 PHOTO행만 삭제해 input_revision은 바꾸지 않는다. 이미 존재하지 않는 photo_id 삭제는 데이터 변경 없이 Ack를 반환한다. ANALYSIS snapshot의 메타/수치는 남기며 역사이미지는 원본 파일이 없으면 표시하지 않는다. snapshot은 원본 바이트를 고정하지 않으며 외부에서 원본을 바꾸는 자동감지는 데모에 없다.

조건/고시/배정/수동값/작업명/배정사진 경로·관찰 저장은 input_revision 증가, 현재/과거 표시를 갱신한다. delete_photo가 현재 배정 또는 manual 값을 비우면 input_revision을 한 번 증가시킨다. 미배정 후보사진 등록/삭제는 계산 입력을 바꾸지 않는다. 조사자 결론/대표/설명/검토는 해당 분석의 표시값을 수정하며 계산 입력 revision을 올리지 않는다. 새 분석행에는 조사자 결론/설명/검토를 자동 승계하지 않는다. 조사 메타는 metadata_revision만 증가한다. 작업명 변경 시 계산은 재사용할 수 있지만 새 표시snapshot이 필요하다.

같은 분석의 조사자 결론을 변경/해제하면SURVEY.review.reviewed=false로 갱신한다. 대표사진/설명문만 바꾸면 계산검토 표시는 유지한다. 검토는 조작 가능한 표시이며 변경/미완전 때문에 기능을 막지 않는다.

카메라/작업자/방법/높이 변경은 전체 사건확인·manual을 비워 두고 모델/전처리 변경은 AUTO_ACCEPTED 값만 비운다. 직접 관찰이 같은 사진에 남아 있으면 그대로 사용할 수 있다. 하중은phase_verified와사건별load_state를 사용하며 미확인/불일치는 해당 effective_load_kg null이다. select_representative에 미완전 슬롯을 고르면 기존대표/없음을 유지하고 notes로 알린다. 사진 미리보기는 점수대표 선택과 별개다. 삭제된 작업/분석을 늦은 완료응답으로 다시 생성하지 않는다.

## 6. GPT·설정

```typescript
type AiPurpose = 'TASK_EXPLANATION'|'IMPROVEMENT_ADVICE';
type NumericBasis = {item_code:string,value:Number|Truth|null,unit:BasisItem['unit'],operator:BasisItem['operator'],threshold:Number|null};
type NumericCriterion = {criterion_no:Count,computed_status:JudgmentStatus|null,investigator_status:FinalStatus|null,effective_status:JudgmentStatus|null,effective_source:'COMPUTED'|'INVESTIGATOR'|null,exclusion:'SHORT_TERM'|'INTERMITTENT'|'BOTH'|null,missing_fields:string[],missing_count:Count|null,review_reasons:ReviewReason[],basis:NumericBasis[]};
type NumericSummary = {purpose:AiPurpose,reba_status:'NOT_CALCULATED'|'INCOMPLETE'|'COMPLETE',judgment_status:'NOT_CALCULATED'|'CALCULATED',complete_reba_count:Count|null,total_slot_count:15,available_max:Count|null,full_max:Count|null,tag_counts:TagSummary[],criteria:NumericCriterion[]};
type AiText = {purpose:AiPurpose,result:'GENERATED'|'FALLBACK'|'DISABLED',generated_text:string|null,edited_text:string|null,applied_text:string|null,applied_kind:'MODEL'|'INVESTIGATOR'|'FALLBACK'|null,model:string,prompt_version:string,created_at:Timestamp};
type UiPreferences = {loco_visible:boolean,loco_mode:'normal'|'quiet'};
type Settings = {analysis:AnalysisSettings,gpt_enabled:boolean,gpt_model:string,gpt_key_present:boolean,ui:UiPreferences};
type SettingsUpdate = {analysis:AnalysisSettings,gpt_enabled:boolean,gpt_model:string,ui:UiPreferences};
```

NumericSummary는 서비스가 계산결과에서 구성한다. BasisItem.source·근거·이름·사진·경로·좌표·내부 ID는 없다. 공개 기준 설명은 내장 문구다. explanation 모듈은 이 DTO로 문장을 요청하며 별도 보안 가드/수치검증기/승인 흐름은 없다. 키는 OPENAI_API_KEY 실행환경을 읽고 Settings에는 존재 여부만 반환한다. gpt_key_present는 읽기전용 파생값이므로 SettingsUpdate에는 없다. update_settings는 변경 가능한 분석 설정·GPT 옵션·UI 선호 전체를 SettingsUpdate로 받고 Settings 응답을 돌려준다. ui.loco_visible 기본값은true, ui.loco_mode 기본값은normal이며 UI 설정은 `AnalysisSettings`/`TaskSnapshot`에 넣지 않고 분석 계산 입력으로 취급하지 않는다.

reba=null이면 reba_status=NOT_CALCULATED, complete_reba_count/available_max/full_max=null이다. 계산 결과가 있으면 실제 status/complete_count를 옮기며 계산한0개와 미계산을 구분한다. judgment=null이면 judgment_status=NOT_CALCULATED, criteria는1..11의 자리를 유지하되 각 상태/effective_source/exclusion/missing_count=null, missing_fields/review_reasons/basis=[]다. 계산 결과가 있으면 CALCULATED이며 초안/조사자/effective 상태를 각각 옮긴다. effective_source는 investigator.status가 있으면INVESTIGATOR, 없으면COMPUTED다. missing_count는 중복 제거한 missing_fields 수다. missing_fields/item_code는 문서의 입력 필드·조건 코드이며 파일 경로나 자유입력 근거가 아니다.

설명은 ‘초안 NEEDS_INPUT + 조사자 APPLICABLE’을 조사자의 별도 결론으로 표현하고 계산이 완전해졌다고 쓰지 않는다. 제외된 기준은 제외사유, NEEDS_REVIEW는 실제 review_reasons, 미계산 모듈은 미계산이라고 설명한다. DTO의 숫자/상태를 바꾸거나 누락값을 추정하지 않는다. 생성문은 제안이며 조사자가 편집/적용한다.

timeout10초/요청실패/키없음은 고정 설명 FALLBACK, 비활성은 DISABLED. 로컬 계산을 실패로 바꾸지 않는다. 각 분석에 purpose별1개 AiText를 저장하며 생성본/수정본/적용본은 별도 필드다. 이전 결과의 설명을 새 결과에 자동 적용하지 않는다.

## 7. Excel

### 7.1 출력·미리보기 DTO

```typescript
type ExportSpec = {destination:string,analysis_ids:ID[],include_representative:boolean};
type ExportSnapshot = {schema_version:'1.3',report_version:'1.3',survey:Survey,tasks:Task[],analyses:Analysis[],unanalysed_task_ids:ID[],include_representative:boolean,exported_at:Timestamp};
type ReportCounts = {needs_input_count:Count|null,needs_review_count:Count|null,incomplete_reba_count:Count|null};
type NextInputItem = {module:'ANALYSIS'|'POSE'|'REBA'|'BURDEN',kind:'NOT_CALCULATED'|'MISSING_INPUT'|'REVIEW_REQUIRED',slot_no:Count|null,criterion_no:Count|null,field_paths:string[],reason_codes:string[],message:string};
type ReportState = {reviewed:boolean,review_current:boolean,has_incomplete:boolean,has_stale:boolean};
type ReportReviewStatus = 'NO_ANALYSIS'|'UNREVIEWED'|'REVIEWED_CURRENT'|'REVIEWED_HISTORY';
type ReportTaskOverview = {task_id:ID,task_name:string,analysis_id:ID|null,input_revision:Count,currentness:Currentness,state:ReportState,review_status:ReportReviewStatus,counts:ReportCounts,next_inputs:NextInputItem[]};
type ReportOverview = {report_version:'1.3',state:ReportState,counts:ReportCounts,tasks:ReportTaskOverview[]};
type RenderedReport = {file_path:string,sheets:string[],overview:ReportOverview};
type ExportReceipt = ReportState & {export_id:ID,file_path:string,sheets:string[],created_at:Timestamp};
```

분석 선택은 작업별 한 행이다. 명령 시 현존 모든 task를 포함하고 선택하지 않은 작업은 최신분석 또는 미분석15/11빈행을 넣는다. 과거/미완전 분석도 내보낸다. 동일작업을 두 번 선택하면 UI에서 한 행을 고르는 선택 화면을 제공한다. 보고서에 서로 다른 모듈 결과를 임의로 조합하지 않고 선택한 ANALYSIS의 snapshot을 쓴다. 분석없는 작업은 현재 입력을 쓴다.

| sheet | 정확한 열(순서 고정) |
|---|---|
| SUMMARY | task_id,task_name,analysis_id,currentness,review_status,valid_pose_count,complete_reba_count,available_max,full_max,applicable_criteria,needs_input_count,needs_review_count,incomplete_reba_count,next_inputs |
| TASK_INPUTS | task_id,analysis_id,input_revision,input_group,item_code,value,unit,source,evidence_text,observed_at |
| PHOTO_REBA | task_id,analysis_id,slot_no,cycle_no,phase,pose_status,load_state,effective_load_kg,left_total,right_total,selected_side,total,risk,missing_fields,diagnostics,image |
| CRITERIA | task_id,analysis_id,criterion_no,computed_status,investigator_status,effective_status,exclusion,comparison_values,source,evidence_text,review_reasons,missing_fields,investigator_reason,reviewer,reviewed_at,warning |

SUMMARY의 작업표는 위14열이다. survey_id/title/survey_date/investigator/department/process는 표 위 조사 개요에 한 번 표시한다. input_revision은 TASK_INPUTS 식별 열, representative_slot_no는 PHOTO_REBA 대표블록에 표시한다. notes와 TASK_EXPLANATION의 applied_explanation/applied_kind는 SUMMARY 표 아래 작업ID/분석ID가 붙은 상세영역, report_notice는 아래 고정 안내영역에 표시한다. 열을 줄여도 이 정보는 생략하지 않는다.

PHOTO_REBA 작업당15행, CRITERIA 작업당11행. TASK_INPUTS는 조건/20시간/11기준입력/15배정관찰/수동값/모델·규칙버전을 행으로 펼친다. image열은 대표 상세블록 참조/이미지 생략 사유를 쓰며 실제 사진은 표 밖의 고정 블록에 넣는다. 고정 안내는 기능정의서 §9의 문구다. 미계산 값은 빈칸이며 초안/조사자결론/현재성/완전성/검토를 각각 표시한다.

선택분석이 있으면 task_name/조건/수동값/사진배정은Analysis.snapshot에서 읽는다. ExportSnapshot.tasks는 현재 작업목록·현재성 비교에 사용한다. 분석없는 작업만Task의 현재입력을 출력한다. 누락 설명은SUMMARY 아래 상세영역, 관절·각도는TASK_INPUTS의 input_group=RESULT_POSE, 태그/사진별관찰은RESULT_TAG, REBA구성점수/후보는RESULT_REBA로 펼친다. angle은unit=DEG,관절좌표는PX,confidence는RATIO로 쓴다. NumericSummary.tag_counts는Analysis.tags를 사용한다. SUMMARY 아래 적용 설명은TASK_EXPLANATION의 적용문이며 생성/수정/적용본과 개선문은TASK_INPUTS의 input_group=EXPLANATION에 각각 기록한다.

### 7.2 미리보기·집계·다음 입력

preview_excel과 export_excel은 같은 분석 선택 규칙으로 ExportSnapshot을 구성하고 report.build_overview(snapshot)의 같은 상태/집계 함수를 사용한다. preview_excel의 내부 snapshot은 include_representative=true이며 이 옵션은 상태/집계에 영향을 주지 않는다. 미리보기는 ReportOverview만 반환하며 파일/EXPORT_LOG를 만들지 않는다. export_excel은 호출 시점의 새 snapshot에 spec.include_representative를 복사하고 report.render(snapshot,spec.destination)을 호출한다. render는 snapshot.include_representative로 이미지 여부를 결정하고 build_overview의 결과를 RenderedReport.overview로 돌려준다. 서비스는 overview.state를 ExportReceipt에 옮겨 성공 로그를 저장한다. 미리보기 후 입력이 바뀌면 실제 출력 시점의 상태를 사용한다. 미리보기 일치 가드/승인 절차는 없다. 내부 미리보기 snapshot의 exported_at을 실제 파일 출력 시각으로 안내하지 않는다.

ReportTaskOverview의 작업명/input_revision은 선택 분석 snapshot, 분석이 없으면 현재 Task에서 읽는다. currentness는 ExportSnapshot.tasks의 현재 입력과 선택 analysis_id를 비교한다. ReportOverview/ReportCounts/NextInputItem은 파생값이며 Task/Analysis에 저장하지 않는다. 집계 규칙은 기능정의서 §9.2다. 조사 합계는 해당 결과가 모든 작업에 있을 때만 합산하고, 없는 작업이 있으면 해당 항목만 null이다.

ReportState는 기능정의서 §9.2의 선택 분석 규칙을 사용한다. 작업 reviewed는 선택 analysis_id가 존재하고 survey.review.reviewed=true이며 reviewed_analysis_ids에 그ID가 있을 때true다. review_current는 여기에 검토 metadata_revision 일치와 currentness=CURRENT까지 만족할 때true다. review_status는 분석없음NO_ANALYSIS, reviewed=false면UNREVIEWED, review_current=true면REVIEWED_CURRENT, 나머지reviewed=true면REVIEWED_HISTORY다. 검토한A2 대신A1을 선택했는데 A1이 목록에 없다면 UNREVIEWED다. TaskResult/SurveySummary의 최신분석 검토표시를 과거 선택 분석에 그대로 복사하지 않는다.

작업 has_incomplete는 선택 분석이 없거나, 분석의 pose=null/valid_count<15, reba=null/status=INCOMPLETE, judgment=null/초안computed_status에NEEDS_INPUT 또는NEEDS_REVIEW 중 하나라도 있을 때true다. report.build_overview가 원래 결과를 직접 읽어 산출하며 별도 미완전 사유 분류/배열을 만들지 않는다. 실패/취소는 원래 실행상태와 슬롯 진단으로 표시한다. 이 값은 조사자 결론/검토와 독립이며 저장·분석·검토·출력 허가 조건으로 사용하지 않는다. has_stale는 선택 분석 currentness=STALE일 때만true며 NONE은 미분석이다. 조사 ReportOverview.state의 reviewed/review_current는 작업이1개 이상이고 모든 작업의 해당 값이true일 때true, has_incomplete/has_stale는 하나라도true일 때true다. 작업0개면 네 값 모두false다. Excel/UI/ExportReceipt는 이 동일 파생값을 사용하고 receipt_json에 네 부울을 기록한다.

NextInputItem은 미분석이면 ANALYSIS/NOT_CALCULATED 한 항목, 분석은 있으나 pose/reba/judgment가 null이면 각각 POSE/REBA/BURDEN의 NOT_CALCULATED를 만든다. 포즈 결과의 VALID가 아닌 슬롯은 POSE/REVIEW_REQUIRED로 진단코드/field_path와 회차·순간에 맞는 사진 연결/촬영 확인/재분석 안내를 만든다. 수동REBA가 완전해도 포즈 진단은 남긴다. REBA와 고시 결과가 있으면 슬롯별 누락과 기준별 누락/검토 사유를 모두 만든다. 같은 module/slot_no/criterion_no/kind는 한 항목으로 묶고 field_paths/reason_codes의 중복을 제거한다. 좌우 REBA 경로는 left./right.를 유지하고 공통 누락은 두 번 표시하지 않는다. field_paths는 원래 누락/진단 경로, reason_codes는 원래 검토사유/진단코드이며 둘 다 빈 배열일 수 있다. message는 내장된 항목명과 회차·phase·좌우·기준 번호로 생성한다. 미분석/미계산 안내→슬롯1..15→기준1..11 순서이며 같은 대상의 MISSING_INPUT을 REVIEW_REQUIRED보다 먼저, 같은종류에서는POSE/REBA/BURDEN 순서로 표시한다. GPT/새 경고 이력은 사용하지 않는다.

안내는 새 미완전 사유 코드로 변환하지 않는다. 분석/모듈 결과 없음은 null과 선택 여부에 맞는 고정 문구, 포즈는 기존 diagnostics[].message, REBA는 missing_fields와 좌우 review_reasons, 고시는 computed_status/missing_fields/review_reasons를 사용한다. 예: ‘포즈 분석을 아직 수행하지 않았습니다’, ‘2회차 선반 접촉 직전: 오른쪽 손목 범주 입력 필요’, ‘4호: 조건 합산 해석 검토 필요’. UI와 Excel은 동일한 next_inputs[].message를 표시한다. has_incomplete를 안내 항목 수로 계산하지 않으며 원래 결과 상태에서 직접 산출한다.

SUMMARY의 세 count열은 ReportTaskOverview.counts, next_inputs는 next_inputs[].message를 모두 줄바꿈해 표시한다. applicable_criteria는 effective_status=APPLICABLE의 번호와 출처(COMPUTED/INVESTIGATOR)를 함께 적고 확정 목록으로 표현하지 않는다. 적용 설명에는 applied_kind도 표시한다. 고정 요약영역은 ReportOverview.counts와 state의 네 부울을 화면설계서 문구로 표시한다. 기존 결과 상태/진단/누락에서 만든 작업별 안내는 아래 식별자 붙은 상세영역에도 표시한다. null숫자는 빈칸과 사유, 실제0은 숫자0이다. 미분석의 판정/REBA 수치를 추측해 채우지 않는다.

### 7.3 식별정보·상세블록·서식

각 시트 제목영역에 ExportSnapshot.report_version/schema_version/exported_at과 survey_id를 표시한다. SUMMARY 작업표에는 task_id/analysis_id, TASK_INPUTS 식별 열에는 해당 input_revision, input_group=SETTINGS에는 snapshot.settings의 모델/전처리/태그/REBA/고시 버전을 넣는다. TASK_INPUTS.item_code는 슬롯/좌우/관절/태그/필드를 구별하는 경로다. RESULT_POSE/RESULT_TAG/RESULT_REBA의 슬롯별 값에는 슬롯번호와 COMMON/LEFT/RIGHT를 경로에 포함한다. 후보는RESULT_REBA에 slots.{slot_no}.candidates.{scope}.{field}.{property}라는 출력용 항목코드로 제안값/근거각도/최저confidence/사유를 펼친다. 예: slots.8.candidates.COMMON.trunk_base.proposed_value. 이 번호는 slot_no이며 배열의0기반 인덱스가 아니다. 집계 태그는 태그코드/필드로 구별한다. 모든 세부값은 같은 선택 분석에서 읽는다.

PHOTO_REBA의 image열은 선택 대표 행에 ‘대표 상세블록 참조’ 또는 ‘이미지 제외/원본을 읽을 수 없음’을 표시하고 나머지는 빈칸이다. 실제 이미지는 표 밖의 고정 대표 상세블록에 한 번 넣는다. include_representative=false이면 이미지만 생략하고 식별자/수치는 표시한다. 대표가 없으면 그 사유를 표시하며 임의 사진을 대표로 대체하지 않는다.

대표 블록 식별자는 task_id/analysis_id/slot_no/cycle_no/phase와 snapshot.capture.slots의 photo_id다. 하중/좌우total/selected_side/total/risk와 선택측 RebaSideScore의 trunk/neck/legs/upper_arm/lower_arm/wrist/table_a/load_score/score_a/table_b/coupling_score/score_b/table_c/activity_score/missing_fields를 표시한다. 선택측이 null이면 구성점수를 임의측으로 채우지 않고 누락을 표시한다. SUMMARY의 available_max/full_max와 대표 total은 각각 이름 붙여 표시한다.

CRITERIA.comparison_values는 Judgment.basis의 모든 BasisItem을 item_code/value/unit/operator/threshold/source 순서로 한 줄씩 표시한다. basis가 없으면 ‘비교근거 없음’이다. CRITERIA.source/evidence_text는 앱의 기준 출처/해당 기준 직접입력 Evidence, investigator_reason은 조사자 사유와 그 Evidence의 source/text/observed_at을 구분해 줄바꿈한다. 조사자 근거가 계산 근거를 대체하지 않는다. TASK_INPUTS에는 조건/노출/조사자 근거를 각각 행으로 펼친다. RESULT_TAG에는 각 TagSummary의 yes_count/observed_count/valid_pose_count/manual_observed_count/total_slot_count/sample_ratio를 모두 출력한다. sample_ratio는 RATIO, 시간은 MIN_DAY이며 사진 비율에서 파생한 시간행은 없다.

시각은 UTC 저장값을 Asia/Seoul로 변환해 Excel 날짜/시각 타입으로 쓴다. 날짜 yyyy-mm-dd, 시각 yyyy-mm-dd hh:mm, 비율0.0%, 실수0.00, 수/호/점수는 정수 표시다. ID/코드/상태/근거는 식별 가능한 글자로 쓴다. 상세 서식·필터·고정 위치·상태 문구는 화면설계서 S08을 따른다. report는 저장 결과와 파생 집계를 표시하며 Excel 수식으로 REBA/법 판정을 재계산하지 않는다.

## 8. 오류와 안내

AppError는 파일/모델/DB/Excel의 실행 오류와 없는 ID만 표현한다. 슬롯별 MISSING_PHOTO/UNREADABLE_FILE/LOW_CONFIDENCE/MISSING_CAMERA는 diagnostics, 계산의 누락/모순은 missing_fields/review_reasons다.15슬롯 미완성·수동입력 누락·미확인 근거·중복사진·동의 미기입 때문에 전체 기능을 차단하지 않는다.

구 `ergo/contracts.py`와 기존 시험은 이전 프로토타입 계약이다. 새 모듈 API의 구현으로 간주하지 않는다. 이 문서를 자동 생성하거나 새 테스트/가드로 강제하지 않는다.
