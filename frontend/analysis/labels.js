import {userText} from '../user-language.js';
/* Display labels and input options. Domain calculations stay in Python. */
const exposureNames={
  C1_KEYBOARD_FOCUSED:'집중 키보드·마우스 사용',C2_NECK:'목 반복 동작',C2_SHOULDER:'어깨 반복 동작',C2_ELBOW:'팔꿈치 반복 동작',C2_WRIST:'손목 반복 동작',C2_HAND:'손 반복 동작',C3_UNION:'3호 자세의 중복을 제외한 시간',
  C4_NECK_FLEX:'목 앞굽힘',C4_TRUNK_FLEX:'몸통 앞굽힘',C4_TRUNK_EXT:'몸통 뒤로 젖힘',C4_NECK_TWIST:'목 비틀림',C4_TRUNK_TWIST:'몸통 비틀림',C4_UNION:'4호 자세의 중복을 제외한 시간',C5_SQUAT:'쪼그림',C5_KNEEL:'무릎 굽힘',C5_UNION:'5호 자세의 중복을 제외한 시간',C6_QUALIFYING:'한손 집기·힘 조건의 작업',C7_QUALIFYING:'한손 들기·힘 조건의 작업',C10_LIFT:'반복 들기',C11_IMPACT:'손·무릎 반복 충격'
};

const inputNames={box_mass_kg:'상자 전체 중량',shelf_height_cm:'선반 상판 높이',daily_work_min:'하루 실제 작업시간',one_off:'1회성 작업 여부',planned_duration_months:'예정 작업기간',annual_work_days:'연간 작업일수',lift_count_day:'하루 들기 횟수',condition_present:'해당 작업조건 존재',unsupported:'신체·물체가 지지되지 않는 조건',posture_restricted:'자세를 자유롭게 바꾸기 어려운 조건',posture_interpretation_pending:'자세 해석 확인',rows_complete:'하루의 모든 해당 조건 행 기록 여부',pinch_mass_kg:'한손 손가락 집기 중량',pinch_force_kg_equiv:'손가락에 가해지는 힘',single_hand_mass_kg:'한손 들기 중량',grip_force_kg_equiv:'한손 쥐기 힘',below_knee_count_day:'무릎 아래에서 들기',above_shoulder_count_day:'어깨 위에서 들기',extended_arm_count_day:'팔을 뻗어 들기',union_count_day:'중복을 제외한 들기 횟수',lift_rate_min:'작업 중 분당 들기 횟수',impact_rate_hour:'작업 중 시간당 충격 횟수',effective_load_kg:'적용 하중',photo_id:'사진 배정'};

const angleNames={TRUNK_TILT_VERT:'몸통 앞굽힘·뒤로 젖힘',NECK_TILT_VERT_PROXY:'목 기울기 참고값',NECK_FLEX_TRUNK_PROXY:'몸통 대비 목 기울기 참고값',UPPER_ARM_RAISE_VERT:'수직 기준 위팔 올림',UPPER_ARM_FLEX_TRUNK:'몸통 기준 위팔 굽힘',ELBOW_FLEX:'팔꿈치 굽힘',KNEE_FLEX:'무릎 굽힘',WRIST_FLEX_2D:'손목 굽힘·폄(사진 평면)'};

const tagNames={NECK_FORWARD_PROXY:'목 앞기울임 참고',TRUNK_FLEX:'몸통 앞굽힘',TRUNK_EXT:'몸통 뒤로 젖힘',UPPER_ARM_RAISE:'위팔 올림',HAND_ABOVE_HEAD:'머리 위 손',ELBOW_ABOVE_SHOULDER:'어깨 위 팔꿈치',ELBOW_BEHIND_TRUNK:'몸통 뒤 팔꿈치',NECK_TWIST:'목 비틀림',TRUNK_TWIST:'몸통 비틀림',SQUAT:'쪼그림',KNEEL:'무릎 접촉'};

const sideNames={COMMON:'공통',LEFT:'왼쪽',RIGHT:'오른쪽'};

const postureOptions={
  trunk_base:[['','미확인'],[1,'수직 자세 (1)'],[2,'0° 초과~20° 앞굽힘·뒤로 젖힘 (2)'],[3,'20° 초과~60° 앞굽힘 또는 20° 초과 뒤로 젖힘 (3)'],[4,'60° 초과 앞굽힘 (4)']],
  upper_arm_base:[['','미확인'],[1,'뒤로 20°~앞으로 20° (1)'],[2,'뒤로 20° 초과 또는 앞으로 20° 초과~45° (2)'],[3,'앞으로 45° 초과~90° (3)'],[4,'앞으로 90° 초과 (4)']],
  lower_arm_base:[['','미확인'],[1,'팔꿈치 굽힘 60~100° (1)'],[2,'팔꿈치 굽힘 60° 미만 또는 100° 초과 (2)']],
  wrist_base:[['','미확인'],[1,'손목 굽힘·젖힘 15° 이내 (1)'],[2,'손목 굽힘·젖힘 15° 초과 (2)']]
};

const reasonNames={COMBINATION_RULE:'여러 조건을 합산하는 해석 확인 필요',POSTURE_INTERPRETATION:'자세 정의·해석 확인 필요',BOUNDARY_REVIEW:'점수 경계 ±5° 이내 · 자세 재확인',INPUT_CONFLICT:'입력값 사이의 모순 또는 범위 확인 필요'};

function inputLabel(path){
  const parts=String(path).split('.');
  if(parts[0]==='analysis_scope')return ({pose:'사진 자세 분석 사용',tags:'자세 기술태그 사용',reba:'REBA 사용',judgment:'11개 기준 사용'}[parts[1]]||'분석 범위');
  const exposure=parts.find(p=>exposureNames[p]);
  if(exposure)return exposureNames[exposure]+' 시간';
  const field=parts.at(-1);
  if(parts[0]==='manual')return `사진 행 ${parts[1]} · ${sideNames[parts[2]]||''} · ${manualLabels[parts[3]]||parts[3]} · ${{value:'확인값',source:'출처',observed_at:'관찰 시각',text:'근거'}[field]||field}`;
  if(parts[0]==='capture')return `사진 행 ${parts[2]||''} · ${{photo_id:'배정 사진',label:'표시명',camera_side:'카메라 위치',forward_direction:'작업자 전방',side_view_verified:'측면 확인',load_state:'하중 상태',measured_load_kg:'측정 중량',single_person:'단일 작업자',full_frame:'전신 확인',normal_work:'통상 작업',analysis_target:'분석 대상'}[field]||field}`;
  if(parts[0]==='settings')return '분석 설정 · '+({confidence_min:'관절 신뢰도 문턱',neck_forward_deg:'목 기울기 보조 문턱',trunk_flex_deg:'몸통 앞굽힘 기술 문턱',trunk_extension_deg:'몸통 뒤로 젖힘 기술 문턱',upper_arm_raise_deg:'위팔 올림 기술 문턱',version:'버전',preprocess_version:'전처리 버전'}[field]||field);

  if(field==='value'&&parts.at(-2)==='union')return '적격 행의 중복 제거 합집합 수치';
  const name=({load_mass_kg:'물체 중량',measured_load_kg:'사진에서 관찰한 하중',impact_verified:'실제 충격 확인',minutes:'하루 노출시간',worker_code:'작업자 코드',method_description:'작업 방법',work_posture:'작업 자세',work_height_cm:'작업 높이',worker_count:'작업자 수',row_ids:'집계 대상 조건 행'}[field]||inputNames[field]||(typeof manualLabels!=='undefined'?manualLabels[field]:null)||'확인할 입력 항목');
  const index=parts.indexOf('criteria');
  if(index>=0&&/^\d+$/.test(parts[index+1]))return `${Number(parts[index+1])+(parts[0]==='legal'?1:0)}호 · ${name}`;
  const scope={common:'공통',left:'왼쪽',right:'오른쪽'}[parts[0]];
  return scope?scope+' · '+name:name;
}

function reasonText(reason){return reasonNames[reason]||'추가 확인 필요';}

function valueText(value){return value===null||value===undefined?'미입력':({YES:'예',NO:'아니오',UNKNOWN:'미확인'}[value]??userText(String(value)));}

function basisText(basis){
  const units={MIN_DAY:'분/일',KG:'kg',KG_EQUIV:'kg 상당',COUNT_DAY:'회/일',COUNT_MIN:'회/분',COUNT_HOUR:'회/시간',MONTH:'개월',COUNT_YEAR:'일/년',BOOLEAN:''};
  const unit=units[basis.unit]??'';
  const value=valueText(basis.value)+(basis.value!==null&&basis.value!==undefined&&unit?' '+unit:'');
  let text=inputLabel(basis.item_code)+': '+value;
  if(basis.threshold!==null&&basis.threshold!==undefined){
    const operator={GE:'이상',LE:'이하',EQ:'일치',OR:'중 하나'}[basis.operator]||'';
    text+=' / 기준 '+basis.threshold+(unit?' '+unit:'')+' '+operator;
    if(typeof basis.value==='number'){
      const met=basis.operator==='GE'?basis.value>=basis.threshold:basis.operator==='LE'?basis.value<=basis.threshold:basis.operator==='EQ'?basis.value===basis.threshold:null;
      if(met!==null)text+=' — '+(met?'수치 기준 충족':'수치 기준 미충족');
    }
  }
  const source={DIRECT_INPUT:'사용자 입력',DIRECT_OBSERVATION:'직접 관찰',INTERVIEW:'면담',DOCUMENT:'문서',OTHER:'기타',MOEL_2020_12_V1:'고시 제2020-12호'}[basis.source]||'저장된 근거';
  return text+' (출처: '+source+')';
}

function candidateValueText(candidate){
  if(candidate.proposed_value===null)return '미확인';
  if(candidate.field==='knee_band')return {UNDER_30:'무릎 굽힘 30° 미만',FROM_30_TO_60:'무릎 굽힘 30~60°',OVER_60:'무릎 굽힘 60° 초과'}[candidate.proposed_value]||'범주 확인 필요';
  return candidate.proposed_value+' 범주';
}

import {SCREEN_INFO as pages} from '../screens.js';

const statusNames={CURRENT:'현재 입력 기준',STALE:'이전 입력/분석 기준',NONE:'분석 없음',NEEDS_INPUT:'입력 필요',NEEDS_REVIEW:'추가 검토',APPLICABLE:'해당 초안',NOT_APPLICABLE:'비해당 초안',UNREVIEWED:'미검토',NO_ANALYSIS:'분석 없음',REVIEWED_CURRENT:'조사자 검토완료',REVIEWED_HISTORY:'이전결과 검토',VALID:'유효',INVALID:'확인 필요',ERROR:'오류',PENDING:'대기',CANCELED:'취소',NOT_PROCESSED:'미처리',FINISHED:'요청 처리 완료',RUNNING:'처리 중',FAILED:'분석 실패',COMPLETE:'완전',INCOMPLETE:'입력 필요',DONE:'포즈 완료',PARTIAL_REVIEW:'일부 사진 확인 필요'};

const truth=[['UNKNOWN','미확인'],['YES','예'],['NO','아니오']];

const criterionTitles=['집중 키보드·마우스','같은 동작 반복','팔·손 위치','목·허리 굽힘·비틀림','쪼그림·무릎 굽힘','한손 손가락 집기·힘','한손 들기·쥐기','25kg 이상 들기','10kg 이상 불리한 위치 들기','4.5kg 이상 반복 들기','손·무릎 반복 충격'];

const manualLabels={trunk_base:'몸통 기본범주',trunk_twisted:'몸통 비틀림',trunk_side_bent:'몸통 옆굽힘',neck_base:'목 기본범주',neck_twisted:'목 비틀림',neck_side_bent:'목 옆굽힘',legs_support:'다리 지지',seated:'앉은 자세',knee_band:'양쪽 중 큰 무릎 범주',shock_force:'충격·급격한 힘',static_over_1min:'1분 초과 정적 유지',small_repeat_over_4min:'분당 4회 초과 작은 반복',rapid_change_or_unstable:'급격한 변화·불안정',upper_arm_base:'위팔 기본범주',arm_abducted_or_rotated:'팔 벌림·회전',shoulder_raised:'어깨 들림',arm_supported_or_gravity_assisted:'팔 지지·중력 보조',lower_arm_base:'아래팔 기본범주',wrist_base:'손목 기본범주',wrist_deviated_or_twisted:'손목 편위·비틀림',coupling:'손잡이·쥐기',hand_above_head:'머리 위 손',elbow_above_shoulder:'어깨 위 팔꿈치',elbow_behind_trunk:'몸통 뒤 팔꿈치',squat:'쪼그림',kneel:'무릎 접촉'};

const commonFields=['trunk_base','trunk_twisted','trunk_side_bent','neck_base','neck_twisted','neck_side_bent','legs_support','seated','knee_band','shock_force','static_over_1min','small_repeat_over_4min','rapid_change_or_unstable','hand_above_head','elbow_above_shoulder','elbow_behind_trunk','squat','kneel'];

const armFields=['upper_arm_base','arm_abducted_or_rotated','shoulder_raised','arm_supported_or_gravity_assisted','lower_arm_base','wrist_base','wrist_deviated_or_twisted','coupling'];

function manualOptions(field){if(postureOptions[field])return postureOptions[field];if(field==='neck_base')return [['','관찰불가'],['1','중립·0~20° 앞굽힘 (1)'],['2','20° 초과 앞굽힘 (2)'],['2_EXTENSION','뒤로 젖힘·신전 (2)']];if(field.endsWith('_base')){const maximum={trunk_base:4,neck_base:2,upper_arm_base:4,lower_arm_base:2,wrist_base:2}[field];return [['','미확인'],...Array.from({length:maximum},(_,i)=>[i+1,field==='neck_base'?(i===0?'중립·0~20° 앞굽힘 (1)':'20° 초과 앞굽힘 또는 신전 (2)'):`${i+1} 범주`])];}return field==='legs_support'?[['','미확인'],['BILATERAL_STABLE','양발 안정'],['UNILATERAL_OR_UNSTABLE','한발·불안정']]:field==='knee_band'?[['','미확인'],['UNDER_30','30° 미만'],['FROM_30_TO_60','30~60°'],['OVER_60','60° 초과']]:field==='coupling'?[['','미확인'],['GOOD','좋음'],['FAIR','보통'],['POOR','나쁨'],['UNACCEPTABLE','수용 불가'],['NOT_APPLICABLE','물체를 잡지 않음']]:truth;}

const poseColors={left:'#ff1493',right:'#00ffff',center:'#ffff00'};

const poseEdges=[
  ['nose','left_eye','left'],['left_eye','left_ear','left'],['nose','left_shoulder','left'],
  ['nose','right_eye','right'],['right_eye','right_ear','right'],['nose','right_shoulder','right'],
  ['left_shoulder','left_elbow','left'],['left_elbow','left_wrist','left'],
  ['right_shoulder','right_elbow','right'],['right_elbow','right_wrist','right'],
  ['left_shoulder','right_shoulder','center'],['left_shoulder','left_hip','left'],
  ['right_shoulder','right_hip','right'],['left_hip','right_hip','center'],
  ['left_hip','left_knee','left'],['left_knee','left_ankle','left'],
  ['right_hip','right_knee','right'],['right_knee','right_ankle','right']
];

export {exposureNames, inputNames, angleNames, tagNames, sideNames, postureOptions, reasonNames, pages, statusNames, truth, criterionTitles, manualLabels, commonFields, armFields, poseColors, poseEdges, inputLabel, reasonText, valueText, basisText, candidateValueText, manualOptions};
