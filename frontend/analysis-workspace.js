/* S04-S09 integration. S01-S03 remain owned by TaskWorkspace/desktop.js. */
window.createAnalysisWorkspace=function(host){
host.element.innerHTML='<div id="content"></div><div id="overlay-root"></div>';
/* User-facing labels only. Calculation rules and stored DTO codes stay in Python. */
const exposureNames={
  C1_KEYBOARD_FOCUSED:'집중 키보드·마우스 사용',C2_NECK:'목 반복 동작',C2_SHOULDER:'어깨 반복 동작',C2_ELBOW:'팔꿈치 반복 동작',C2_WRIST:'손목 반복 동작',C2_HAND:'손 반복 동작',C3_UNION:'3호 자세의 중복을 제외한 시간',
  C4_NECK_FLEX:'목 앞굽힘',C4_TRUNK_FLEX:'몸통 앞굽힘',C4_TRUNK_EXT:'몸통 뒤로 젖힘',C4_NECK_TWIST:'목 비틀림',C4_TRUNK_TWIST:'몸통 비틀림',C4_UNION:'4호 자세의 중복을 제외한 시간',C5_SQUAT:'쪼그림',C5_KNEEL:'무릎 굽힘',C5_UNION:'5호 자세의 중복을 제외한 시간',C6_QUALIFYING:'한손 집기·힘 조건의 작업',C7_QUALIFYING:'한손 들기·힘 조건의 작업',C10_LIFT:'반복 들기',C11_IMPACT:'손·무릎 반복 충격'
};
const inputNames={box_mass_kg:'상자 전체 중량',shelf_height_cm:'선반 상판 높이',daily_work_min:'하루 실제 작업시간',one_off:'1회성 작업 여부',planned_duration_months:'예정 작업기간',annual_work_days:'연간 작업일수',lift_count_day:'하루 들기 횟수',condition_present:'해당 작업조건 존재',unsupported:'신체·물체가 지지되지 않는 조건',posture_restricted:'자세를 자유롭게 바꾸기 어려운 조건',posture_interpretation_pending:'자세 해석 확인',rows_complete:'하루의 모든 해당 조건 행 기록 여부',pinch_mass_kg:'한손 손가락 집기 중량',pinch_force_kg_equiv:'손가락에 가해지는 힘',single_hand_mass_kg:'한손 들기 중량',grip_force_kg_equiv:'한손 쥐기 힘',below_knee_count_day:'무릎 아래에서 들기',above_shoulder_count_day:'어깨 위에서 들기',extended_arm_count_day:'팔을 뻗어 들기',union_count_day:'중복을 제외한 들기 횟수',lift_rate_min:'작업 중 분당 들기 횟수',impact_rate_hour:'작업 중 시간당 충격 횟수',effective_load_kg:'적용 하중',photo_id:'사진 배정'};
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
  if(field==='value'&&parts.at(-2)==='union')return '적격 행의 중복 제거 합집합 수치';
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

const pages={S01:['조사 목록','SURVEY WORKSPACE','조사를 만들고 현장의 기록을 이어갑니다.'],S02:['조사 개요','SURVEY OVERVIEW','현장과 조사자 정보를 기록합니다. 모르는 항목은 비워둘 수 있습니다.'],S03:['작업·직접입력','TASK & EXPOSURE','작업 종류에 관계없이 같은 11개 기준과 하루 수치를 기록합니다.'],S04:['사진·분석대상','GENERAL STILLS','가변 사진 행에서 분석대상을 선택합니다.'],S05:['분석 진행','LOCAL ANALYSIS','시작 시점의 입력을 기준으로 로컬 분석을 진행합니다.'],S06:['자세·REBA','POSTURE & REBA','각도는 후보입니다. 현장 관찰값과 함께 확인하고 적용하세요.'],S07:['조사자 확인','CRITERIA REVIEW','앱 초안과 조사자의 결론은 별도로 보존됩니다.'],S08:['Excel 보고서','REPORT EXPORT','선택한 분석의 입력과 결과를 같은 보고서에 담습니다.'],S09:['설정','WORKSPACE SETTINGS','분석 규칙과 로코 안내 설정을 확인합니다.']};
const phaseNames=['손 닿기 전','바닥 분리 직후','바닥면 절반 높이','선반 접촉 직전','손 놓은 후'];
const statusNames={CURRENT:'현재 입력 기준',STALE:'이전 입력/분석 기준',NONE:'분석 없음',NEEDS_INPUT:'입력 필요',NEEDS_REVIEW:'추가 검토',APPLICABLE:'해당 초안',NOT_APPLICABLE:'비해당 초안',UNREVIEWED:'미검토',NO_ANALYSIS:'분석 없음',REVIEWED_CURRENT:'조사자 검토완료',REVIEWED_HISTORY:'이전결과 검토',VALID:'유효',INVALID:'확인 필요',ERROR:'오류',PENDING:'대기',CANCELED:'취소',NOT_PROCESSED:'미처리',FINISHED:'요청 처리 완료',RUNNING:'처리 중',FAILED:'분석 실패',COMPLETE:'완전',INCOMPLETE:'입력 필요',DONE:'포즈 완료',PARTIAL_REVIEW:'일부 사진 확인 필요'};
const s={page:'S01',surveys:[],survey:null,tasks:[],bundle:null,analysis:null,selectedAnalysis:null,aiTextId:null,history:[],settings:null,slot:1,previews:new Map(),selectedSlots:new Set(),poll:null,overview:null,exportSelections:{},comparisonPool:[],comparisonBefore:null,comparisonAfter:null,comparisonNote:''};
const $=selector=>selector==='loco-guide'?document.querySelector(selector):host.element.querySelector(selector), $$=selector=>[...host.element.querySelectorAll(selector)];
const e=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const fmt=value=>value===null||value===undefined?'미계산':e(value);
const badge=(value)=>`<span class="badge ${['VALID','COMPLETE','CURRENT','REVIEWED_CURRENT'].includes(value)?'good':['NEEDS_INPUT','INCOMPLETE','ERROR','FAILED'].includes(value)?'error':'warn'}">${e(statusNames[value]||value||'미계산')}</span>`;
const ev=()=>({source:null,text:null,observed_at:null});
function toast(message){host.notify(message);}
async function api(method,params={}){return host.api(method,params);}
function options(values,value){return values.map(item=>{const [key,label]=Array.isArray(item)?item:[item,item];return `<option value="${e(key)}" ${String(value??'')===String(key)?'selected':''}>${e(label)}</option>`;}).join('');}
const truth=[['UNKNOWN','미확인'],['YES','예'],['NO','아니오']];
function field(label,path,value,type='text'){return `<label>${e(label)}<input data-field="${e(path)}" type="${type}" value="${e(value)}" ${type==='number'?'step="any"':''}></label>`;}
function select(label,path,value,values){return `<label>${e(label)}<select data-field="${e(path)}">${options(values,value)}</select></label>`;}
function number(path){const input=$(`[data-field="${path}"]`);return input?.value===''?null:Number(input?.value);}
function text(path){return $(`[data-field="${path}"]`)?.value??'';}
function card(title,body,actions=''){return `<section class="card"><div class="card-head"><h2>${title}</h2><div class="toolbar">${actions}</div></div>${body}</section>`;}
function empty(message,button=''){return `<div class="card empty"><div class="symbol">◇</div><h2>${message}</h2><p>상단 메뉴로 이동하거나 조사와 작업을 선택해 주세요.</p>${button}</div>`;}
function metric(label,value,unit=''){return `<div class="metric"><span class="label">${label}</span><strong>${fmt(value)}<small>${unit}</small></strong></div>`;}
function modal(title,body){$('#overlay-root').innerHTML=`<div class="modal-backdrop"><div class="modal"><h2>${e(title)}</h2>${body}<div class="toolbar"><button data-action="close-modal">닫기</button></div></div></div>`;}
function context(){return `<div class="note">${e(s.survey?.title||'조사 미선택')} ${s.bundle?' / '+e(s.bundle.task.task_name)+' · 입력 r'+s.bundle.task.input_revision:''}</div>`;}
function selectedIds(){return Object.values(s.exportSelections).filter(Boolean).map(Number);}
function comparisonSpecs(){const before=Number(s.comparisonBefore),after=Number(s.comparisonAfter);return before&&after&&before!==after?[{before_analysis_id:before,after_analysis_id:after,note:s.comparisonNote||null}]:[];}
async function refreshTask(){if(!s.bundle)return;s.bundle=await api('get_task',{task_id:s.bundle.task.task_id});s.history=await api('list_analysis_history',{task_id:s.bundle.task.task_id});const chosen=s.history.find(a=>a.analysis_id===s.selectedAnalysis)||s.history.find(a=>a.analysis_id===s.bundle.task.latest_analysis_id);s.analysis=chosen||null;s.selectedAnalysis=s.analysis?.analysis_id??null;s.tasks=await api('list_tasks',{survey_id:s.survey.survey_id});}
async function navigate(page){if(['S01','S02','S03','S04'].includes(page)){host.onLeave(page);return;}clearInterval(s.poll);s.poll=null;s.page=page;
  if(page==='S01')s.surveys=await api('list_surveys');
  if(s.bundle&&['S05','S06','S07'].includes(page))await refreshTask();
  if(page==='S08'&&s.survey){s.tasks=await api('list_tasks',{survey_id:s.survey.survey_id});s.overview=await api('preview_excel',{survey_id:s.survey.survey_id,analysis_ids:selectedIds(),comparisons:comparisonSpecs()});}
  render();if(page==='S05'&&s.analysis?.status==='RUNNING')s.poll=setInterval(pollAnalysis,800);
}
function render(){
  if(!host.active)return;
  host.onNavigate(s.page,pages[s.page]);
  syncGuidePreferences();
  $('#content').innerHTML=(s.survey&&s.page!=='S09'?card('작업 선택',`<div class="toolbar"><select id="task-choice" aria-label="분석할 작업">${options([['','작업 선택'],...s.tasks.map(t=>[t.task_id,t.task_name||'이름 없는 작업'])],s.bundle?.task.task_id)}</select><button data-page="S03">작업 입력으로</button></div>`):'')+({S04:capturePage,S05:progressPage,S06:rebaPage,S07:criteriaPage,S08:exportPage,S09:settingsPage}[s.page])();
  if(s.page==='S04')loadThumbnails();
  if(s.page==='S06')drawPhoto();
}
const criterionTitles=['집중 키보드·마우스','같은 동작 반복','팔·손 위치','목·허리 굽힘·비틀림','쪼그림·무릎 굽힘','한손 손가락 집기·힘','한손 들기·쥐기','25kg 이상 들기','10kg 이상 불리한 위치 들기','4.5kg 이상 반복 들기','손·무릎 반복 충격'];
function capturePage(){if(!s.bundle)return empty('작업을 선택하세요','<button data-page="S03">작업 입력으로</button>');const t=s.bundle.task;return context()+card('촬영 프로토콜',`<p>정측면·수평 렌즈, 15장 위치와 줌 고정. 전신·상자·바닥·선반 상판을 담아 주세요.<br>중간 사진은 상자 <strong>바닥면</strong>이 선반 높이의 절반을 통과하는 순간입니다. 정상 동작을 멈추지 않습니다.</p><div class="grid" style="margin-top:15px">${select('카메라 측면','camera_side',t.capture.camera_side,[['','미입력'],['LEFT','작업자 왼쪽'],['RIGHT','작업자 오른쪽']])}${select('작업자 앞쪽 방향','forward_direction',t.capture.forward_direction,[['','미입력'],['SCREEN_RIGHT','화면 오른쪽'],['SCREEN_LEFT','화면 왼쪽']])}</div><div class="toolbar" style="margin-top:16px"><button data-action="save-camera">카메라 정보 저장</button><button data-action="capture-guide">촬영 안내 자세히</button></div>`)+card('사진 보관함',`<div id="drop-zone"><p>사진을 끌어놓거나 파일 선택으로 등록합니다. 원본은 현재 위치에 유지됩니다.</p><div class="pool">${s.bundle.photos.map(p=>`<div class="photo"><img data-photo="${p.photo_id}" alt="${e(p.file_name)}"><div class="photo-name">${e(p.file_name)}</div><div class="toolbar"><button class="small danger" data-action="delete-photo" data-id="${p.photo_id}">참조 삭제</button></div></div>`).join('')||'<div class="input-guide">등록된 사진이 없습니다.</div>'}</div></div>`,'<button data-action="import-photos">＋ 사진 선택</button>')+Array.from({length:3},(_,cycle)=>`<h3 class="cycle-label">${String(cycle+1).padStart(2,'0')} 회차 <span class="inline-count">NORMAL CYCLE</span></h3><div class="slot-grid">${t.capture.slots.slice(cycle*5,cycle*5+5).map(slot=>`<div class="slot"><div class="thumb">${slot.photo_id?`<img data-photo="${slot.photo_id}" alt="슬롯 ${slot.slot_no} 사진">`:'＋'}<span class="number">${String(slot.slot_no).padStart(2,'0')}</span></div><div class="slot-body"><strong>${phaseNames[(slot.slot_no-1)%5]}</strong><select data-slot-assignment="${slot.slot_no}">${options([['','사진 미배정'],...s.bundle.photos.map(p=>[p.photo_id,p.file_name])],slot.photo_id)}</select><button class="small" data-action="observe-slot" data-slot="${slot.slot_no}">사건·하중 확인</button><div class="input-guide">${e({UNKNOWN:"하중 미확인",UNLOADED:"무하중",FULL_BOX:"상자 전체 중량"}[slot.observation.load_state]||"하중 확인 필요")} · ${slot.observation.phase_verified==='YES'?'사건 확인':'사건 미확인'}</div></div></div>`).join('')}</div>`).join('')+`<div class="toolbar"><button class="primary" data-action="start-analysis">로컬 분석 시작 →</button><span class="input-guide">빈 슬롯이 있어도 실행할 수 있습니다.</span></div>`;}
function progressPage(){if(!s.bundle)return empty('작업을 선택하세요');const a=s.analysis;if(!a)return context()+empty('아직 분석이 없습니다','<button class="primary" data-action="start-analysis">분석 시작</button>');const slots=a.pose?.slots||[];const total=a.pose?.total_slot_count??slots.length;const processed=slots.filter(p=>p.status!=='PENDING').length;const percent=total?Math.min(100,processed/total*100):0;return context()+card('시작 입력 기준으로 분석',`<div class="toolbar">${badge(a.status)} ${badge(a.currentness)} <span class="input-guide">분석 #${a.analysis_id} · 입력 r${a.input_revision}</span></div><div class="progress-track"><div style="width:${percent}%"></div></div><h2>${processed} <span class="inline-count">/ ${total}개 분석대상 사진 처리 · ${total?'대상 있음':'대상 없음'}</span></h2><p>요청 처리 완료와 모듈별 계산 완전성은 별도 상태입니다.</p><div class="grid">${Object.entries(a.module_states||{}).map(([key,value])=>`<div class="sheet"><strong>${e({pose:'MoveNet',tags:'자세 기술태그',reba:'REBA',judgment:'11개 기준'}[key]||key)}</strong><p>${badge(value)}</p></div>`).join('')}</div><div class="toolbar" style="margin-top:20px"><button data-action="cancel-analysis" ${a.status==='RUNNING'?'':'disabled'}>취소 요청</button><button class="primary" data-page="S06">결과 살펴보기 →</button></div>`)+card('사진별 처리 상태',`<table><thead><tr><th>사진 행</th><th>상태</th><th>진단</th></tr></thead><tbody>${slots.map(p=>{const slot=a.snapshot.capture.slots.find(x=>x.slot_no===p.slot_no);return `<tr><td>${e(slot?.label||`사진 ${p.slot_no}`)} · 행 ${p.slot_no}</td><td>${badge(p.status)}</td><td>${(p.diagnostics||[]).map(d=>e(d.message)).join('<br>')}</td></tr>`;}).join('')||`<tr><td colspan="3">${total?'포즈 분석이 요청되지 않았습니다.':'분석대상 사진이 없습니다.'}</td></tr>`}</tbody></table>`);}
const manualLabels={trunk_base:'몸통 기본범주',trunk_twisted:'몸통 비틀림',trunk_side_bent:'몸통 옆굽힘',neck_base:'목 기본범주',neck_twisted:'목 비틀림',neck_side_bent:'목 옆굽힘',legs_support:'다리 지지',seated:'앉은 자세',knee_band:'양쪽 중 큰 무릎 범주',shock_force:'충격·급격한 힘',static_over_1min:'1분 초과 정적 유지',small_repeat_over_4min:'분당 4회 초과 작은 반복',rapid_change_or_unstable:'급격한 변화·불안정',upper_arm_base:'위팔 기본범주',arm_abducted_or_rotated:'팔 벌림·회전',shoulder_raised:'어깨 들림',arm_supported_or_gravity_assisted:'팔 지지·중력 보조',lower_arm_base:'아래팔 기본범주',wrist_base:'손목 기본범주',wrist_deviated_or_twisted:'손목 편위·비틀림',coupling:'손잡이·쥐기',hand_above_head:'머리 위 손',elbow_above_shoulder:'어깨 위 팔꿈치',elbow_behind_trunk:'몸통 뒤 팔꿈치',squat:'쪼그림',kneel:'무릎 접촉'};
const commonFields=['trunk_base','trunk_twisted','trunk_side_bent','neck_base','neck_twisted','neck_side_bent','legs_support','seated','knee_band','shock_force','static_over_1min','small_repeat_over_4min','rapid_change_or_unstable','hand_above_head','elbow_above_shoulder','elbow_behind_trunk','squat','kneel'];
const armFields=['upper_arm_base','arm_abducted_or_rotated','shoulder_raised','arm_supported_or_gravity_assisted','lower_arm_base','wrist_base','wrist_deviated_or_twisted','coupling'];
function manualOptions(field){if(postureOptions[field])return postureOptions[field];if(field==='neck_base')return [['','관찰불가'],['1','중립·0~20° 앞굽힘 (1)'],['2','20° 초과 앞굽힘 (2)'],['2_EXTENSION','뒤로 젖힘·신전 (2)']];if(field.endsWith('_base')){const maximum={trunk_base:4,neck_base:2,upper_arm_base:4,lower_arm_base:2,wrist_base:2}[field];return [['','미확인'],...Array.from({length:maximum},(_,i)=>[i+1,field==='neck_base'?(i===0?'중립·0~20° 앞굽힘 (1)':'20° 초과 앞굽힘 또는 신전 (2)'):`${i+1} 범주`])];}return field==='legs_support'?[['','미확인'],['BILATERAL_STABLE','양발 안정'],['UNILATERAL_OR_UNSTABLE','한발·불안정']]:field==='knee_band'?[['','미확인'],['UNDER_30','30° 미만'],['FROM_30_TO_60','30~60°'],['OVER_60','60° 초과']]:field==='coupling'?[['','미확인'],['GOOD','좋음'],['FAIR','보통'],['POOR','나쁨'],['UNACCEPTABLE','수용 불가'],['NOT_APPLICABLE','물체를 잡지 않음']]:truth;}
function historyPicker(){
  const label=a=>{
    const modelError=a.pose?.slots.some(p=>p.diagnostics.some(d=>d.code==='MODEL_ERROR'));
    return modelError?'모델 연결 오류':!a.pose?'포즈 미요청':`유효 포즈 ${a.pose.valid_count}/${a.pose.total_slot_count??a.pose.slots?.length??0}`;
  };
  return `<div><div class="toolbar"><label for="history-choice">저장된 분석 ${s.history.length}개</label><select id="history-choice">${options([['','분석 선택'],...s.history.map(a=>[a.analysis_id,`#${a.analysis_id} · 입력 r${a.input_revision} · ${statusNames[a.currentness]} · ${label(a)}`])],s.analysis?.analysis_id)}</select>${s.analysis?badge(s.analysis.currentness):''}</div><p class="input-guide">#번호는 저장된 분석 ID입니다. 분석·재계산마다 새 기록이 생기며, 같은 작업의 이전 기록은 이 목록에서 선택할 수 있습니다. 실패한 기록도 보존됩니다.</p><details><summary>이 작업의 전체 분석 이력 보기</summary><div class="table-wrap"><table><thead><tr><th>분석 ID</th><th>입력 버전</th><th>현재성</th><th>포즈 결과</th><th></th></tr></thead><tbody>${s.history.map(a=>`<tr><td>#${a.analysis_id}</td><td>r${a.input_revision}</td><td>${badge(a.currentness)}</td><td>${e(label(a))}</td><td><button class="small" data-action="view-history" data-id="${a.analysis_id}">열기</button></td></tr>`).join('')}</tbody></table></div></details></div>`;
}
function rebaPage(){if(!s.bundle)return empty('작업을 선택하세요');const a=s.analysis;const summary=a?.reba?.summary;const slot=s.bundle.task.capture.slots.find(x=>x.slot_no===s.slot);const targetCount=(a?.snapshot.capture.slots||s.bundle.task.capture.slots).filter(x=>x.analysis_target&&x.photo_id!==null).length;const r=a?.reba?.slots?.find(r=>r.slot_no===s.slot);const ps=a?.pose?.slots?.find(p=>p.slot_no===s.slot);return context()+card('분석 이력',historyPicker())+`<div class="metrics">${metric('유효 포즈',a?.pose?.valid_count,`/ ${a?.pose?.total_slot_count??targetCount}`)}${metric('완전 REBA',summary?.complete_count,`/ ${summary?.total_slot_count??targetCount}`)}${metric('계산된 사진 중 최대',summary?.available_max,'점')}</div><div class="note">대상 ${summary?.total_slot_count??targetCount}개 중 최대: ${fmt(summary?.full_max)} · 대표 사진 행: ${summary?.representative_slot_no??'없음'} · 모델: ${e(a?.snapshot.settings.pose_model.version??'미실행')}<br>목 프록시는 참고값이며 목 REBA 범주를 자동 결정하지 않습니다.</div>`+card('사진별 결과',`<div class="table-wrap reba-results"><table><thead><tr><th>선택</th><th>사진 행</th><th>포즈</th><th>왼쪽</th><th>오른쪽</th><th>전체</th><th>누락</th><th></th></tr></thead><tbody>${s.bundle.task.capture.slots.filter(sl=>sl.analysis_target).map(sl=>rebaTableRow(sl,a)).join('')||'<tr><td colspan="8">분석대상이 없습니다. 사진 화면에서 대상을 선택하세요.</td></tr>'}</tbody></table></div>`)+`<div class="split">${card(`선택 사진 · ${s.slot}번`, '<div class="photo-view"><canvas id="pose-canvas"></canvas><p id="photo-message">사진을 불러오는 중입니다.</p></div>'+`<div class="detail">${e(poseDiagnosticText(ps))}</div><details><summary>좌우 각도 · 원본 픽셀 기준</summary><pre>${e(ps?.angles?.map(x=>`${sideNames[x.side]||"측면"} · ${angleNames[x.angle_code]||"각도"}: ${x.value_deg===null?'미확인':x.value_deg.toFixed(2)+'°'}`).join('\n')||'각도 결과 없음')}</pre></details>`)}${card('자동 후보',r?`${r.candidates.map(c=>`<div class="sheet" style="margin-bottom:10px"><strong>${e(sideNames[c.scope]||"관찰")} · ${e(manualLabels[c.field])}</strong><p>후보 ${e(candidateValueText(c))} · 근거각도 ${e(c.angles.map(x=>x.value_deg===null?"미확인":x.value_deg.toFixed(2)+"°").join(" / ")||"없음")} · 최저 관절 신뢰도 ${c.min_confidence?.toFixed(2)??'없음'}<br>${e(c.review_reasons.map(reasonText).join(', '))}</p></div>`).join('')}<button data-action="apply-candidates">선택 사진에 후보 적용</button>`:'분석 후 사진별 후보를 표시합니다.')}</div>`+card(`현장 관찰 편집 · 현재 사진 ${s.slot}번`, `<div class="grid"><label>편집 범위<select id="manual-range">${options([['single','이 사진'],['selected','체크한 분석대상 사진들']],'single')}</select></label>${select('관찰 출처','manual-source','DIRECT_OBSERVATION',[['DIRECT_OBSERVATION','직접 관찰'],['INTERVIEW','면담']])}${field('근거·목 자세 설명','manual-evidence','')}</div><div class="input-guide">체크한 필드만 선택 사진에 합칩니다. 자동 후보는 각 사진의 자체 각도만 사용합니다.</div>${['COMMON','LEFT','RIGHT'].map(scope=>`<h3 style="margin-top:25px">${scope==='COMMON'?'공통 관찰':scope==='LEFT'?'왼쪽 팔':'오른쪽 팔'}</h3><div class="manual-grid">${(scope==='COMMON'?commonFields:armFields).map(f=>{const value=s.bundle.task.manual.find(m=>m.slot_no===s.slot&&m.scope===scope&&m.field===f)?.value;return `<label><input type="checkbox" data-manual-use="${scope}.${f}">${e(manualLabels[f])}<select data-manual="${scope}.${f}">${options(manualOptions(f),value)}</select></label>`;}).join('')}</div>`).join('')}<div class="divider"></div><div class="toolbar"><button class="primary" data-action="save-manual">선택 필드 저장 · REBA 재계산</button><button data-action="recalculate-tags">태그 재계산</button></div><details><summary>사진 태그 빈도</summary><pre>${e(a?.tags?.map(t=>`${tagNames[t.tag]||"자세 관찰"}: ${t.yes_count}/${t.observed_count} (수동 ${t.manual_observed_count}, 유효포즈 ${t.valid_pose_count}/${t.total_slot_count})`).join('\n')||'미계산')}</pre><p>사진에서 확인한 빈도이며 하루 노출시간으로 환산하지 않습니다.</p></details>`)+explanationCard();}
function rebaTableRow(slot,analysis){
  const result=analysis?.reba?.slots.find(r=>r.slot_no===slot.slot_no);
  const poseResult=analysis?.pose?.slots.find(p=>p.slot_no===slot.slot_no);
  const sourceSlot=analysis?.snapshot.capture.slots.find(s=>s.slot_no===slot.slot_no)||slot;
  const missing=result?.missing_fields||[];
  const name=path=>{
    if(path==='effective_load_kg')return '적용 하중 — 촬영 순간·지지 상태·중량 확인';
    if(path==='photo_id')return '사진 배정';
    const [scope,field]=path.split('.');
    return ({common:'공통',left:'왼쪽',right:'오른쪽'}[scope]||scope)+' · '+(manualLabels[field]||field||path);
  };
  const description=!sourceSlot.photo_id?'<span class="input-guide">사진 미배정 · 사진을 연결한 뒤 관찰값을 입력하세요.</span>':missing.length?`<span class="badge warn">${missing.length}개 항목 입력 필요</span><ul class="missing-fields">${missing.map(path=>`<li>${e(name(path))}</li>`).join('')}</ul>`:'<span class="input-guide">'+(result?'필수 입력 누락 없음':'REBA 미계산')+'</span>';
  return `<tr><td><input type="checkbox" data-select-slot="${slot.slot_no}" ${s.selectedSlots.has(slot.slot_no)?'checked':''}></td><td><button class="small" data-action="select-slot" data-slot="${slot.slot_no}">${e(sourceSlot.label||`사진 행 ${slot.slot_no}`)} · ${slot.slot_no}</button></td><td>${badge(poseResult?.status)}</td><td>${fmt(result?.left?.total)}</td><td>${fmt(result?.right?.total)}</td><td>${fmt(result?.total)}</td><td>${description}</td><td><button class="small" data-action="representative" data-slot="${slot.slot_no}" ${result?.status==='COMPLETE'?'':'disabled'}>대표 선택</button></td></tr>`;
}
function poseDiagnosticText(result){
  if(!result)return '포즈 미계산';
  if(result.diagnostics.length)return result.diagnostics.map(d=>d.message).join('\n');
  return result.status==='VALID'?'포즈 분석 완료 · 관절 신뢰도 기준 충족':statusNames[result.status]||result.status;
}
function explanationCard(){const list=(s.analysis?.ai||[]).filter(a=>a.purpose==='TASK_EXPLANATION'),ai=list.find(a=>a.text_id===s.aiTextId)||list.find(a=>a.is_active)||list.at(-1);if(ai)s.aiTextId=ai.text_id;return card('GPT 설명 · 수치 요약만 전송',`<p>사진·이름·경로·자유입력 근거는 보내지 않습니다. 설명은 계산이나 조사자 결론을 바꿀 수 없습니다.</p><label>설명 이력<select id="ai-choice" data-field="ai-choice">${options([['','설명 이력 선택'],...list.map(x=>[x.text_id,`${x.result} · ${new Date(x.created_at).toLocaleString('ko-KR')}${x.is_active?' · 적용 중':''}`])],ai?.text_id||'')}</select></label>${ai?`<div class="note ${ai.source_current?'':'warn'}">${ai.source_current?'현재 계산과 일치하는 설명':'이전 계산 설명 · 현재 결과와 다름'}${ai.fallback_reason?' · '+e(ai.fallback_reason):''}</div>`:''}<textarea id="explanation-text">${e(ai?.edited_text??ai?.generated_text??'')}</textarea><div class="toolbar"><button data-action="generate-explanation">새 설명 생성</button><button data-action="edit-explanation" ${ai?'':'disabled'}>수정본 저장</button><button data-action="apply-generated" ${ai?'':'disabled'}>생성문 적용</button><button data-action="apply-edited" ${ai?.edited_text?'':'disabled'}>수정문 적용</button></div><div class="detail">적용 출처: ${e(ai?.applied_kind||'없음')}\n${e(ai?.applied_text||'')}</div>`);}
function criteriaPage(){if(!s.bundle)return empty('작업을 선택하세요');const a=s.analysis;const judgments=a?.judgment?.judgments||[];return context()+card('분석 선택',historyPicker(),'<button data-action="calculate-criteria">직접입력으로 초안 재계산</button>')+`<div class="note">조사자 결론을 기록해도 앱 초안의 부족 항목은 유지됩니다. 사진·REBA 없이 직접 입력만으로 계산할 수 있습니다.</div>`+card('11개 기준 검토',`<div class="table-wrap criteria-results"><table><colgroup><col class="criterion-column"><col class="draft-column"><col class="basis-column"><col class="conclusion-column"><col class="effective-column"><col class="action-column"></colgroup><thead><tr><th>기준</th><th>앱 초안</th><th>누락·검토</th><th>조사자 결론</th><th>현재 표시값</th><th>결론 입력</th></tr></thead><tbody>${Array.from({length:11},(_,i)=>{const j=judgments.find(j=>j.criterion_no===i+1);return `<tr><td><strong>${i+1}호</strong><div class="input-guide">${criterionTitles[i]}</div></td><td>${badge(j?.computed_status)}</td><td>${e(j?.missing_fields.map(inputLabel).join(', ')||'')}<br>${e(j?.review_reasons.map(reasonText).join(', ')||'')}<details><summary>전체 비교근거</summary><div class="basis-text">${e(j?.basis.map(basisText).join('\n')||'미계산')}</div></details></td><td>${e(j?.investigator.status==='APPLICABLE'?'해당':j?.investigator.status==='NOT_APPLICABLE'?'비해당':'미입력')}</td><td>${badge(j?.effective_status)}</td><td><button class="small" data-action="conclusion" data-number="${i+1}">결론 기록</button></td></tr>`;}).join('')}</tbody></table></div>`)+card('조사 검토 표시',`<p>계산 완전성 및 법적 승인과 별개인 조사자의 검토 표시입니다.</p><div class="toolbar" style="margin-top:16px"><button data-action="review-on">선택 분석들 검토 완료 표시</button><button data-action="review-off">검토 표시 해제</button><button class="primary" data-page="S08">보고서로 →</button></div>`);}
function exportPage(){if(!s.survey)return empty('조사를 선택하세요');const ov=s.overview;const comparisonOptions=[['','분석 선택'],...s.comparisonPool.map(x=>[x.analysis_id,`#${x.analysis_id} · ${x.task_name} · r${x.input_revision}`])];return context()+card('작업별 분석 선택',`<p>작업마다 분석 하나를 선택합니다. 선택하지 않으면 최신 분석을 쓰며 분석이 없는 작업도 보고서에 남깁니다.</p><div id="export-choices" class="grid" style="margin-top:16px">${s.tasks.map(t=>`<label>${e(t.task_name)}<select data-export-task="${t.task_id}"><option value="">최신 분석 / 미분석</option></select></label>`).join('')}</div>`)+card('개선 전후 분석 비교',`<p>같은 조사 안의 서로 다른 두 분석을 선택합니다. REBA 최대값 차이는 규칙·촬영 표본이 비교 가능한 때만 계산합니다.</p><div class="grid">${select('개선 전 분석','comparison-before',s.comparisonBefore,comparisonOptions)}${select('개선 후 분석','comparison-after',s.comparisonAfter,comparisonOptions)}${field('비교 메모','comparison-note',s.comparisonNote)}</div>${ov?.comparisons.map(c=>`<div class="sheet"><strong>#${c.spec.before_analysis_id} → #${c.spec.after_analysis_id} · REBA 후−전 ${fmt(c.reba_max_delta)}</strong><p>규칙 호환 ${c.rule_compatible?'예':'아니오'} · 표본 호환 ${c.sampling_compatible?'예':'아니오'}</p>${c.notes.map(n=>`<div class="input-guide">${e(n)}</div>`).join('')}</div>`).join('')||'<p class="input-guide">두 분석을 고르면 비교 미리보기를 계산합니다. 기준별 변화는 합산 점수나 개선율로 만들지 않습니다.</p>'}`)+`<div class="metrics">${metric('계산 입력이 부족한 기준',ov?.counts.needs_input_count,'기준')}${metric('추가 검토가 필요한 기준',ov?.counts.needs_review_count,'기준')}${metric('REBA 미완료 사진',ov?.counts.incomplete_reba_count,'사진')}</div>`+card('선택 결과 상태',`<div class="grid">${Object.entries(ov?.state||{}).map(([key,val])=>`<div class="sheet"><strong>${{reviewed:'선택 결과 전체 검토 여부',review_current:'검토 현재성',has_incomplete:'미완전 포함',has_stale:'과거 결과 포함',survey_input_complete:'조사 단계 입력 보완'}[key]}</strong><p>${val?'예':'아니오'}</p></div>`).join('')}</div><div class="table-wrap"><table><thead><tr><th>작업</th><th>분석</th><th>현재성</th><th>검토</th></tr></thead><tbody>${ov?.tasks.map(t=>`<tr><td>${e(t.task_name)}</td><td>${t.analysis_id??'미분석'}</td><td>${badge(t.currentness)}</td><td>${badge(t.review_status)}</td></tr>`).join('')||''}</tbody></table></div>`)+card('유형별 한글 Excel',`<div class="grid">${[['요약','작업별 상태와 첫 입력 안내'],['작업별 결과','입력 근거·사진·MoveNet·태그·REBA·설명'],['확인사항','미완료·진단·전후 비교 제한'],['판정 근거','11개 초안과 별도 조사자 결론'],['별지1 유해요인조사표','질환자 발생 수시조사 시 서식 기반 추가'],['별지2 증상조사표','질환자 발생 수시조사 시 서식 기반 추가']].map(([name,desc])=>`<div class="sheet"><strong>${name}</strong><p>${desc}</p></div>`).join('')}</div><div class="divider"></div><label><input type="checkbox" id="include-representative" checked>대표 사진 이미지 포함</label><div class="toolbar" style="margin-top:20px"><button class="primary" data-action="export">Excel 저장 위치 선택 · 내보내기</button><button data-action="refresh-overview">미리보기 갱신</button></div><p class="input-guide">미완전·미분석·과거 결과도 출력할 수 있습니다. 출력 시점의 자료를 사용합니다.</p>`)+card('다음 입력 안내',`<div id="next-inputs">${ov?.survey_followups?.map(x=>`<div class="note warn">${e(x)}</div>`).join("")||""}${ov?.tasks.map(t=>`<h3>${e(t.task_name)} · 작업 #${t.task_id} / 분석 ${t.analysis_id??'없음'}</h3><ul class="next-list">${t.next_inputs.map(x=>`<li>${e(x.message)}</li>`).join('')}</ul>`).join('')||'<p>등록된 작업이 없습니다.</p>'}</div>`)+`<div class="note warn">작업 분석 보조 보고서. 법정 유해요인조사표·증상조사표의 완성을 뜻하지 않습니다.</div>`;}
function settingsPage(){const x=s.settings;if(!x)return empty('Python 설정을 불러오지 못했습니다');return card('로컬 분석 엔진',`<div class="grid">${Object.entries(x.analysis.pose_model).map(([key,value])=>`<div class="sheet"><strong>${e(key)}</strong><p>${e(value)}</p></div>`).join('')}</div><div class="detail">REBA: ${e(x.analysis.reba_rule)}\n부담작업: ${e(x.analysis.burden_rule)}</div><div class="note warn" style="margin-top:20px">실제 추론은 LOCO_MOVENET_MODEL의 모델 파일과 호환 Python 런타임이 필요합니다. 연결되지 않으면 사진별 MODEL_ERROR로 표시합니다.</div>`)+card('로코 안내',`<div class="grid">${select('로코 표시','loco_visible',x.ui.loco_visible?'YES':'NO',[['YES','표시'],['NO','숨김']])}${select('안내 방식','loco_mode',x.ui.loco_mode,[['normal','일반 모드'],['quiet','조용한 모드']])}</div><div class="toolbar" style="margin-top:20px"><button class="primary" data-action="save-settings">설정 저장</button></div>`)+card('GPT 설명',`<p>GPT는 저장된 판정·점수의 비식별 수치 요약만 받아 설명과 확인 항목을 만듭니다. API 키는 Python 실행환경의 OPENAI_API_KEY에서 읽습니다.</p><div class="grid">${select('GPT 사용','gpt_enabled',x.gpt_enabled?'YES':'NO',[['NO','사용 안 함'],['YES','사용']])}${field('모델 ID','gpt_model',x.gpt_model||'gpt-6-luna')}</div><div class="detail">API 키 ${x.gpt_key_present?'환경에 설정됨':'환경에서 찾지 못함'} · 요청 제한 10초 · 키 값은 화면·DB에 저장하지 않음</div><div class="toolbar" style="margin-top:20px"><button class="primary" data-action="save-gpt-settings">GPT 설정 저장</button></div><div class="note warn">GPT가 기준 해당 여부, REBA 점수, 계산값을 판정하거나 변경하지 않습니다. 생성문은 조사자가 확인한 뒤 적용하세요.</div>`);}
async function loadThumbnails(){for(const img of $$('img[data-photo]')){const photo=s.bundle.photos.find(p=>p.photo_id===Number(img.dataset.photo));if(!photo)continue;try{const preview=await previewPhoto(photo);if(img.isConnected)img.src=preview.data_url;}catch(error){img.alt=error.message;}}}
async function previewPhoto(photo){const key=photo.photo_id+':'+photo.file_path;if(!s.previews.has(key))s.previews.set(key,await api('get_photo_preview',{photo}));return s.previews.get(key);}
// Same visible left/right/torso colors as pose2/utils.py's OpenCV rendering.
// OpenCV uses BGR; Canvas uses RGB, so (147,20,255) becomes #ff1493.
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
async function drawPhoto(){
  // Capture photo and analysis together before waiting for file decoding.
  const selected=s.analysis,slotNo=s.slot;
  const slot=(selected?.snapshot.capture||s.bundle.task.capture).slots.find(s=>s.slot_no===slotNo);
  const photos=selected?.snapshot.photos||s.bundle.photos;
  const photo=slot?photos.find(p=>p.photo_id===slot.photo_id):null;
  const points=selected?.pose?.slots.find(p=>p.slot_no===slotNo)?.points||[];
  const message=$('#photo-message'),canvas=$('#pose-canvas');
  canvas.parentElement.insertAdjacentHTML('afterend','<div class="pose-legend" aria-label="관절 색상 안내"><span><i class="pose-left"></i>작업자 왼쪽</span><span><i class="pose-right"></i>작업자 오른쪽</span><span><i class="pose-center"></i>코·몸통 연결</span><small>화면 좌우가 아닌 신체 기준 · 신뢰도 0.5 이상만 표시</small></div>');
  if(!slot||!photo){message.textContent=slot?'이 사진 행에 사진이 없습니다.':'사진 행을 선택하세요.';canvas.style.display='none';return;}
  try{
    const preview=await previewPhoto(photo);
    if(!canvas.isConnected)return;
    const img=new Image();
    img.onload=()=>{
      if(!canvas.isConnected)return;
      canvas.width=preview.width_px;canvas.height=preview.height_px;
      const ctx=canvas.getContext('2d');ctx.drawImage(img,0,0);
      const visible=point=>point&&point.confidence>=.5&&point.x_px>=0&&point.x_px<canvas.width&&point.y_px>=0&&point.y_px<canvas.height;
      const lookup=Object.fromEntries(points.map(p=>[p.name,p]));
      const lineWidth=Math.max(2,canvas.width/250);
      ctx.lineCap='round';ctx.lineJoin='round';
      for(const [from,to,group] of poseEdges){
        const a=lookup[from],b=lookup[to];
        if(!visible(a)||!visible(b))continue;
        ctx.beginPath();ctx.moveTo(a.x_px,a.y_px);ctx.lineTo(b.x_px,b.y_px);
        ctx.lineWidth=lineWidth+Math.max(1,lineWidth*.3);ctx.strokeStyle='rgba(36,45,65,.45)';ctx.stroke();
        ctx.lineWidth=lineWidth;ctx.strokeStyle=poseColors[group];ctx.stroke();
      }
      for(const point of points){
        if(!visible(point))continue;
        const group=point.name.startsWith('left_')?'left':point.name.startsWith('right_')?'right':'center';
        ctx.fillStyle=poseColors[group];ctx.lineWidth=Math.max(1,lineWidth*.4);ctx.strokeStyle='#242d41';
        ctx.beginPath();ctx.arc(point.x_px,point.y_px,Math.max(3,canvas.width/160),0,Math.PI*2);ctx.fill();ctx.stroke();
      }
      message.style.display='none';
    };
    img.onerror=()=>{if(canvas.isConnected){message.textContent='사진 미리보기를 표시하지 못했습니다.';canvas.style.display='none';}};
    img.src=preview.data_url;
  }catch(error){if(canvas.isConnected){message.textContent=error.message;canvas.style.display='none';}}
}
async function pollAnalysis(){if(!s.analysis)return;try{s.analysis=await api('get_analysis',{analysis_id:s.analysis.analysis_id});if(s.page==='S05')render();if(s.analysis.status!=='RUNNING'){clearInterval(s.poll);s.poll=null;toast('분석 요청 처리가 끝났습니다. 사진별 진단과 입력 부족을 확인하세요.');}}catch(error){clearInterval(s.poll);toast(error.message);}}
function editTargets(){const mode=$('#manual-range')?.value||'single';return mode==='selected'?[...s.selectedSlots]:[s.slot];}
function mergeManual(manual,value){const i=manual.findIndex(m=>m.slot_no===value.slot_no&&m.scope===value.scope&&m.field===value.field);if(i<0)manual.push(value);else manual[i]=value;}
async function saveManual(automatic){const t=s.bundle.task;const manual=structuredClone(t.manual);const targets=editTargets();let applied=0;let skipped=0;const source=text('manual-source');const note=text('manual-evidence');for(const no of targets){const slot=t.capture.slots.find(x=>x.slot_no===no);if(!slot?.photo_id||!slot.analysis_target){skipped++;continue;}if(automatic){const old=s.analysis?.snapshot;const consistent=old&&JSON.stringify(old.capture)===JSON.stringify(t.capture)&&JSON.stringify(old.settings.pose_model)===JSON.stringify(s.settings.analysis.pose_model)&&['worker_code','method_description','work_height_cm'].every(k=>old.conditions[k]===t.conditions[k]);if(!consistent){skipped++;continue;}for(const candidate of s.analysis.reba?.slots?.find(x=>x.slot_no===no)?.candidates||[]){if(candidate.proposed_value===null)continue;mergeManual(manual,{slot_no:no,photo_id:slot.photo_id,scope:candidate.scope,field:candidate.field,value:candidate.proposed_value,source:'AUTO_ACCEPTED',evidence:{source:'OTHER',text:JSON.stringify({angles:candidate.angles,min_confidence:candidate.min_confidence}),observed_at:new Date().toISOString()}});applied++;}}else for(const input of $$('[data-manual-use]:checked')){const [scope,field]=input.dataset.manualUse.split('.');const raw=$(`[data-manual="${scope}.${field}"]`).value;const value=raw===''?null:field.endsWith('_base')?parseInt(raw,10):raw;mergeManual(manual,{slot_no:no,photo_id:slot.photo_id,scope,field,value,source,evidence:{source,text:[note,field==='neck_base'?((raw==='2_EXTENSION'?'뒤로 젖힘·신전':raw==='2'?'20° 초과 앞굽힘':raw==='1'?'중립·0~20° 앞굽힘':'관찰불가')):''].filter(Boolean).join(' / ')||null,observed_at:new Date().toISOString()}});applied++;}}if(!applied)return toast('저장할 값이 없습니다. 선택한 사진·필드를 확인하세요.');await api('set_manual_values',{task_id:t.task_id,manual});s.analysis=await api('recalculate_reba',{task_id:t.task_id});s.selectedAnalysis=s.analysis.analysis_id;await refreshTask();render();toast(`${applied}개 필드를 저장했습니다.${skipped?' 대상이 아니거나 빈 사진인 '+skipped+'개 행은 건너뛰었습니다.':''}`);}
async function importPhotos(paths){if(!paths.length)return;const result=await api('import_photos',{task_id:s.bundle.task.task_id,file_paths:paths});await refreshTask();render();toast(`${result.added.length}장 등록. 슬롯은 아래에서 직접 배정하세요.${result.unreadable.length?'\n읽기 실패: '+result.unreadable.map(x=>x.file_path+': '+x.message).join('\n'):''}`);}
async function populateExportChoices(){const entries=await Promise.all(s.tasks.map(async task=>({task,history:await api('list_analysis_history',{task_id:task.task_id})})));s.comparisonPool=entries.flatMap(({task,history})=>history.map(a=>({...a,task_name:task.task_name})));for(const {task,history} of entries){const select=$(`[data-export-task="${task.task_id}"]`);if(select?.isConnected)select.innerHTML=options([['','최신 분석 / 미분석'],...history.map(a=>[a.analysis_id,`#${a.analysis_id} · r${a.input_revision} · ${statusNames[a.currentness]}`])],s.exportSelections[task.task_id]||'');}const choices=[['','분석 선택'],...s.comparisonPool.map(a=>[a.analysis_id,`#${a.analysis_id} · ${a.task_name} · r${a.input_revision}`])];for(const id of ['comparison-before','comparison-after']){const select=$(`[data-field="${id}"]`);if(select?.isConnected)select.innerHTML=options(choices,id==='comparison-before'?s.comparisonBefore:s.comparisonAfter);}}
const actions={
 'view-history':async b=>{s.selectedAnalysis=Number(b.dataset.id);s.analysis=s.history.find(a=>a.analysis_id===s.selectedAnalysis)||null;render();},
 'save-camera':async()=>{const capture=structuredClone(s.bundle.task.capture);capture.camera_side=text('camera_side')||null;capture.forward_direction=text('forward_direction')||null;await api('set_capture',{task_id:s.bundle.task.task_id,capture});await refreshTask();render();toast('카메라 정보 저장. 변경된 촬영 맥락의 관찰값은 재확인이 필요합니다.');},
 'import-photos':async()=>importPhotos(await window.loco.choose_photo_paths()),
 'delete-photo':async b=>{await api('delete_photo',{photo_id:Number(b.dataset.id)});await refreshTask();render();},
 'observe-slot':async b=>{s.slot=Number(b.dataset.slot);const slot=s.bundle.task.capture.slots[s.slot-1];const o=slot.observation;modal(`${slot.cycle_no}회차 · ${phaseNames[(s.slot-1)%5]}`,`<div class="grid">${select('촬영 순간 확인','obs.phase_verified',o.phase_verified,truth)}${select('실제 하중 상태','obs.load_state',o.load_state,[['UNKNOWN','미확인'],['UNLOADED','무하중'],['FULL_BOX','상자 전체 중량']])}${['single_person','full_frame','camera_fixed','normal_cycle'].map(k=>select({single_person:'한 사람',full_frame:'전신 프레임',camera_fixed:'카메라 고정',normal_cycle:'정상 작업'}[k],'obs.'+k,o[k],truth)).join('')}${field('관찰 근거','obs.evidence',o.evidence.text)}</div><div class="toolbar"><button class="primary" data-action="save-observation">관찰 저장</button></div>`);},
 'save-observation':async()=>{const capture=structuredClone(s.bundle.task.capture);const o=capture.slots[s.slot-1].observation;for(const k of ['phase_verified','load_state','single_person','full_frame','camera_fixed','normal_cycle'])o[k]=text('obs.'+k);o.evidence={source:'DIRECT_OBSERVATION',text:text('obs.evidence')||null,observed_at:new Date().toISOString()};await api('set_capture',{task_id:s.bundle.task.task_id,capture});$('#overlay-root').innerHTML='';await refreshTask();render();},
 'capture-guide':async()=>modal('사진·관찰 입력 안내',`<p>사진은 작업 특성에 따라 0장 이상 등록하고, 각 사진을 분석대상으로 쓸지 직접 선택합니다. 순서나 파일명만으로 작업 단계·하중을 추정하지 않습니다.</p><ul class="next-list"><li>대상 사진마다 카메라 좌우, 화면에서 작업자가 향한 방향, 측면 촬영 확인을 기록합니다.</li><li>단일 작업자·전신·통상 작업 여부를 확인하고, 모르는 관찰값은 미확인으로 둡니다.</li><li>관찰 하중은 무하중, 측정값, 미확인을 구분하고 측정 출처를 남깁니다.</li><li>상자 들기도 다른 작업과 같은 일반 작업·가변 사진·조건별 입력을 사용합니다.</li></ul><p>사진의 자세 비율은 하루 노출시간이나 법정 기준 해당 확률이 아닙니다.</p>`),
 'start-analysis':async()=>{if(!s.bundle)return toast('작업을 먼저 선택하세요.');const handle=await api('start_analysis',{task_id:s.bundle.task.task_id});s.selectedAnalysis=handle.analysis_id;await navigate('S05');},
 'cancel-analysis':async()=>{if(s.analysis){await api('cancel_analysis',{analysis_id:s.analysis.analysis_id});toast('취소를 요청했습니다.');}},
 'select-slot':async b=>{s.slot=Number(b.dataset.slot);render();},
 'apply-candidates':async()=>saveManual(true),
 'save-manual':async()=>saveManual(false),
 'recalculate-tags':async()=>{s.analysis=await api('recalculate_tags',{task_id:s.bundle.task.task_id});s.selectedAnalysis=s.analysis.analysis_id;await refreshTask();render();},
 'representative':async b=>{if(!s.analysis)return toast('분석 결과가 없습니다.');s.analysis=await api('select_representative',{analysis_id:s.analysis.analysis_id,slot_no:Number(b.dataset.slot)});render();toast(s.analysis.notes.at(-1)?.message||'대표사진을 저장했습니다.');},
 'calculate-criteria':async()=>{if(!s.bundle)return toast('작업을 선택하세요.');s.analysis=await api('recalculate_judgments',{task_id:s.bundle.task.task_id});s.selectedAnalysis=s.analysis.analysis_id;await navigate('S07');},
 'conclusion':async b=>{const n=Number(b.dataset.number),j=s.analysis?.judgment?.judgments.find(j=>j.criterion_no===n);if(!j)return toast('직접입력으로 초안 재계산을 먼저 실행하세요.');s.editCriterion=n;modal(`${n}호 · 조사자 결론`,`${select('조사자 결론','inv.status',j.investigator.status,[['','미입력·결론 해제'],['APPLICABLE','해당'],['NOT_APPLICABLE','비해당']])}${field('사유','inv.reason',j.investigator.reason)}${field('근거','inv.evidence',j.investigator.evidence.text)}${field('검토자','inv.reviewer',j.investigator.reviewer||s.survey.investigator)}<div class="toolbar"><button class="primary" data-action="save-conclusion">결론 저장</button></div><p class="input-guide">앱 초안의 누락·검토 사유는 유지되며 조사 전체 검토 표시가 해제됩니다.</p>`);},
 'save-conclusion':async()=>{const conclusion={criterion_no:s.editCriterion,status:text('inv.status')||null,reason:text('inv.reason')||null,evidence:{source:'DIRECT_OBSERVATION',text:text('inv.evidence')||null,observed_at:new Date().toISOString()},reviewer:text('inv.reviewer')||null,reviewed_at:new Date().toISOString()};s.analysis=await api('set_investigator_conclusion',{analysis_id:s.analysis.analysis_id,conclusion});s.survey=await api('get_survey',{survey_id:s.survey.survey_id});$('#overlay-root').innerHTML='';render();},
 'review-on':async()=>setReview(true), 'review-off':async()=>setReview(false),
 'refresh-overview':async()=>{await navigate('S08');await populateExportChoices();},
  'export':async()=>{const destination=await window.loco.choose_export_destination();if(!destination)return;const receipt=await api('export_excel',{survey_id:s.survey.survey_id,spec:{destination,analysis_ids:selectedIds(),include_representative:$('#include-representative').checked,comparisons:comparisonSpecs()}});toast('유형별 한글 Excel을 저장했습니다.\n'+receipt.file_path);await navigate('S08');await populateExportChoices();},
 'generate-explanation':async()=>{if(!s.analysis)return toast('분석 결과를 먼저 선택하세요.');const result=await api('generate_ai_text',{analysis_id:s.analysis.analysis_id,purpose:'TASK_EXPLANATION'});s.aiTextId=result.text.text_id;await refreshTask();render();},
 'edit-explanation':async()=>{const ai=(s.analysis?.ai||[]).find(x=>x.text_id===s.aiTextId);if(!ai)return toast('설명 이력을 먼저 선택하세요.');await api('edit_ai_text',{analysis_id:s.analysis.analysis_id,text_id:ai.text_id,text:$('#explanation-text').value});await refreshTask();render();},
 'apply-generated':async()=>applyExplanation(false),'apply-edited':async()=>applyExplanation(true),
 'save-settings':async()=>{s.settings.ui={loco_visible:text('loco_visible')==='YES',loco_mode:text('loco_mode')};await persistSettings();render();toast('로코 설정을 저장했습니다.');},
 'save-gpt-settings':async()=>{s.settings.gpt_enabled=text('gpt_enabled')==='YES';s.settings.gpt_model=text('gpt_model').trim();await persistSettings();render();toast('GPT 설정을 저장했습니다.');},
 'close-modal':async()=>$('#overlay-root').innerHTML=''
};
async function applyExplanation(useEdited){const ai=(s.analysis?.ai||[]).find(x=>x.text_id===s.aiTextId);if(!ai)return toast('설명 이력을 먼저 선택하세요.');await api('apply_ai_text',{analysis_id:s.analysis.analysis_id,text_id:ai.text_id,use_edited:useEdited});await refreshTask();render();}
async function setReview(reviewed){const tasks=await api('list_tasks',{survey_id:s.survey.survey_id});const ids=tasks.map(t=>t.task_id===s.bundle?.task.task_id?s.analysis?.analysis_id:t.latest_analysis_id).filter(Boolean);const review={reviewed,reviewed_analysis_ids:ids,reviewed_metadata_revision:s.survey.metadata_revision,reviewer:s.survey.investigator||null,reviewed_at:new Date().toISOString(),note:null};s.survey=await api('set_survey_review',{survey_id:s.survey.survey_id,review});toast('검토 표시를 저장했습니다. 계산 완전성과는 별도입니다.');render();}
async function persistSettings(){const {gpt_key_present,...settings}=s.settings;s.settings=await api('update_settings',{settings});}
function syncGuidePreferences(){
  const widget=$('loco-guide'),ui=s.settings?.ui;
  if(!ui)return;
  widget.setAttribute('visible',String(ui.loco_visible));
  widget.setAttribute('mode',ui.loco_mode);
  
  
  if(s.page==='S09'){
    const visible=$('[data-field="loco_visible"]'),mode=$('[data-field="loco_mode"]');
    if(visible)visible.value=ui.loco_visible?'YES':'NO';
    if(mode)mode.value=ui.loco_mode;
  }
}
host.element.addEventListener('click',async event=>{const button=event.target.closest('[data-page],[data-action]');if(!button)return;try{if(button.dataset.page){await navigate(button.dataset.page);if(s.page==='S08')await populateExportChoices();}else await actions[button.dataset.action]?.(button);}catch(error){toast(error.message);}});
host.element.addEventListener('change',async event=>{const el=event.target;try{if(el.id==='task-choice'&&el.value){s.slot=1;s.selectedSlots.clear();s.bundle=await api('get_task',{task_id:Number(el.value)});s.selectedAnalysis=null;await refreshTask();render();}if(el.id==='history-choice'){s.selectedAnalysis=Number(el.value)||null;s.analysis=s.history.find(a=>a.analysis_id===s.selectedAnalysis)||null;s.aiTextId=null;render();}if(el.dataset.field==='ai-choice'){s.aiTextId=el.value||null;render();}if(el.dataset.field==='comparison-before'){s.comparisonBefore=Number(el.value)||null;await navigate('S08');await populateExportChoices();}if(el.dataset.field==='comparison-after'){s.comparisonAfter=Number(el.value)||null;await navigate('S08');await populateExportChoices();}if(el.dataset.slotAssignment){const capture=structuredClone(s.bundle.task.capture);const slot=capture.slots.find(x=>x.slot_no===Number(el.dataset.slotAssignment));if(slot)slot.photo_id=Number(el.value)||null;await api('set_capture',{task_id:s.bundle.task.task_id,capture});await refreshTask();render();}if(el.dataset.selectSlot){if(el.checked)s.selectedSlots.add(Number(el.dataset.selectSlot));else s.selectedSlots.delete(Number(el.dataset.selectSlot));}if(el.dataset.manual){const check=$(`[data-manual-use="${el.dataset.manual}"]`);if(check)check.checked=true;}if(el.dataset.exportTask){s.exportSelections[el.dataset.exportTask]=Number(el.value)||null;await navigate('S08');await populateExportChoices();}}catch(error){toast(error.message);}});
host.element.addEventListener('input',event=>{if(event.target.dataset.field==='comparison-note')s.comparisonNote=event.target.value;});
host.element.addEventListener('dragover',event=>{if(s.page==='S04')event.preventDefault();});
host.element.addEventListener('drop',async event=>{if(s.page!=='S04'||!s.bundle)return;event.preventDefault();const paths=[];for(const file of event.dataTransfer.files){try{const path=window.loco.path_for_file(file);if(path)paths.push(path);else toast(file.name+': 파일 경로를 얻지 못했습니다.');}catch(error){toast(error.message);}}try{await importPhotos(paths);}catch(error){toast(error.message);}});
document.addEventListener('keydown',event=>{if(host.active&&event.key==='Escape')$('#overlay-root').innerHTML='';});


return {
 currentTask(surveyId){return s.survey?.survey_id===surveyId?s.bundle?.task.task_id:undefined;},
 async open({page,surveyId,taskId,analysisId}){
  this.suspend();host.active=true;
  s.settings=await api('get_settings');
   if(s.survey?.survey_id!==surveyId){s.bundle=null;s.analysis=null;s.selectedAnalysis=null;s.exportSelections={};s.selectedSlots.clear();s.comparisonPool=[];s.comparisonBefore=null;s.comparisonAfter=null;s.comparisonNote='';}
  s.survey=surveyId?await api('get_survey',{survey_id:surveyId}):null;
  s.tasks=surveyId?await api('list_tasks',{survey_id:surveyId}):[];
  const chosen=s.tasks.find(t=>t.task_id===taskId)||s.tasks[0];
  if(chosen){
   if(s.bundle?.task.task_id!==chosen.task_id){s.selectedAnalysis=null;s.slot=1;s.selectedSlots.clear();}
   s.bundle=await api('get_task',{task_id:chosen.task_id});if(analysisId)s.selectedAnalysis=analysisId;await refreshTask();
  }else{s.bundle=null;s.analysis=null;s.selectedAnalysis=null;}
  await navigate(page);if(page==='S08'&&s.survey)await populateExportChoices();
 },
 suspend(){host.active=false;clearInterval(s.poll);s.poll=null;$('#overlay-root').innerHTML='';},
 async guide(action){
  if(action==='guide')await actions['capture-guide']();
  else if(action==='manual')$('.manual-grid')?.scrollIntoView({behavior:'smooth'});
  else if(action==='criterion4')modal('4호 · 조건 합산 해석','<p>개별 조건과 중복을 제외한 하루 노출시간을 함께 확인하세요. 합산 해석이 필요한 경우 추가 검토로 표시합니다.</p>');
  else if(action==='next')$('#next-inputs')?.scrollIntoView({behavior:'smooth'});
 },
 async preferences(detail){
  s.settings=await api('get_settings');
  if('visible'in detail)s.settings.ui.loco_visible=detail.visible;
  if('mode'in detail)s.settings.ui.loco_mode=detail.mode;
  await persistSettings();syncGuidePreferences();
 },
 async initialize(){s.settings=await api('get_settings');syncGuidePreferences();}
};
};
