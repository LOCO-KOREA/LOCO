/* User-facing labels only. Calculation rules and stored DTO codes stay in Python. */
const exposureNames={
  C1_KEYBOARD_FOCUSED:'집중 키보드·마우스 사용',C2_NECK:'목 반복 동작',C2_SHOULDER:'어깨 반복 동작',C2_ELBOW:'팔꿈치 반복 동작',C2_WRIST:'손목 반복 동작',C2_HAND:'손 반복 동작',C3_UNION:'3호 자세의 중복을 제외한 시간',
  C4_NECK_FLEX:'목 앞굽힘',C4_TRUNK_FLEX:'몸통 앞굽힘',C4_TRUNK_EXT:'몸통 뒤로 젖힘',C4_NECK_TWIST:'목 비틀림',C4_TRUNK_TWIST:'몸통 비틀림',C4_UNION:'4호 자세의 중복을 제외한 시간',C5_SQUAT:'쪼그림',C5_KNEEL:'무릎 굽힘',C5_UNION:'5호 자세의 중복을 제외한 시간',C6_QUALIFYING:'한손 집기·힘 조건의 작업',C7_QUALIFYING:'한손 들기·힘 조건의 작업',C10_LIFT:'반복 들기',C11_IMPACT:'손·무릎 반복 충격'
};
const inputNames={box_mass_kg:'상자 전체 중량',shelf_height_cm:'선반 상판 높이',daily_work_min:'하루 실제 작업시간',one_off:'1회성 작업 여부',planned_duration_months:'예정 작업기간',annual_work_days:'연간 작업일수',lift_count_day:'하루 들기 횟수',condition_present:'해당 작업조건 존재',unsupported:'신체·물체가 지지되지 않는 조건',posture_restricted:'자세를 자유롭게 바꾸기 어려운 조건',posture_interpretation_pending:'자세 해석 확인',pinch_mass_kg:'한손 손가락 집기 중량',pinch_force_kg_equiv:'손가락에 가해지는 힘',single_hand_mass_kg:'한손 들기 중량',grip_force_kg_equiv:'한손 쥐기 힘',below_knee_count_day:'무릎 아래에서 들기',above_shoulder_count_day:'어깨 위에서 들기',extended_arm_count_day:'팔을 뻗어 들기',union_count_day:'중복을 제외한 들기 횟수',lift_rate_min:'작업 중 분당 들기 횟수',impact_rate_hour:'작업 중 시간당 충격 횟수',effective_load_kg:'적용 하중',photo_id:'사진 배정'};
const angleNames={TRUNK_TILT_VERT:'몸통 앞굽힘·뒤로 젖힘',NECK_TILT_VERT_PROXY:'목 기울기 참고값',NECK_FLEX_TRUNK_PROXY:'몸통 대비 목 기울기 참고값',UPPER_ARM_RAISE_VERT:'수직 기준 위팔 올림',UPPER_ARM_FLEX_TRUNK:'몸통 기준 위팔 굽힘',ELBOW_FLEX:'팔꿈치 굽힘',KNEE_FLEX:'무릎 굽힘'};
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
  const exposure=parts.find(p=>exposureNames[p]);
  if(exposure)return exposureNames[exposure]+' 시간';
  const field=parts.at(-1);
  const name=inputNames[field]||(typeof manualLabels!=='undefined'?manualLabels[field]:null)||'확인할 입력 항목';
  const scope={common:'공통',left:'왼쪽',right:'오른쪽'}[parts[0]];
  return scope?scope+' · '+name:name;
}
function reasonText(reason){return reasonNames[reason]||'추가 확인 필요';}
function valueText(value){return value===null||value===undefined?'미입력':({YES:'예',NO:'아니오',UNKNOWN:'미확인'}[value]??String(value));}
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
