import {renderActivity} from './activity.js';
import {renderIntakeHistory} from './history-view.js';
const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const POSTURE={neck_base:'목 굽힘',trunk_base:'몸통 굽힘',legs_base:'다리 지지',knee_flexion:'무릎 굽힘',upper_arm_base:'위팔 들림',lower_arm_base:'팔꿈치 굽힘',wrist_base:'손목 굽힘',coupling:'손잡이·잡는 상태',trunk_twisted:'몸통 비틀림',trunk_side_bent:'몸통 옆 기울임',neck_twisted:'목 비틀림',neck_side_bent:'목 옆 기울임',shoulder_raised:'어깨 들림',arm_abducted_or_rotated:'위팔 벌림·돌림',arm_supported_or_gravity_assisted:'팔 받침·기댐',wrist_deviated_or_twisted:'손목 비틀림·옆 꺾임',legs_support:'다리 지지',seated:'앉은 자세',shock_force:'충격·갑작스러운 힘',static_over_1min:'1분 이상 자세 유지',small_repeat_over_4min:'작은 동작 반복',rapid_change_or_unstable:'급격한 자세 변화·불안정'};
const LABELS={context:'사진 사용 상황',load:'물건·힘 상태',load_kg:'물건 무게',load_link:'사진 물건과 입력 중량의 연결',daily_work_min:'하루 전체 작업시간',annual_work_days:'연간 작업일수',planned_duration_months:'작업 예정 기간',one_off:'일회성 작업',task_name:'작업명',other_work:'다른 작업 특징'};
const SOURCE={USER:'직접 입력',AI:'설명에서 정리',POSE:'MediaPipe 측정',MOVENET:'MoveNet 측정',VISION:'AI 사진 관찰',SAVED:'저장된 입력'};
export function dataLabel(field) {
  const d=field.destination||{},side=d.scope==='LEFT'?'왼쪽 ':d.scope==='RIGHT'?'오른쪽 ':'';
  if(d.type==='manual')return side+(POSTURE[d.field]||field.checklist?.label||field.label?.replace(/\s*어떤가요\?|\s*얼마나.*$/g,'')||'자세 항목');
  return LABELS[field.target]||field.label?.replace(/인가요\?$|하나요\?$|\?$/g,'')||'작업 정보';
}
/** Form descriptors are editable data, not the planner's question queue. */
export function renderForm(intake,busy) {
  const fields=intake.formFields(),facts=intake.state.facts||[];
  const row=f=>{
    const saved=facts.find(s=>s.identity===f.identity),draft=intake.formValues.has(f.identity),value=draft?intake.formValues.get(f.identity):saved?.value;
    const editing=intake.dataEditing?.has(f.identity),label=dataLabel(f);
    const display=value==null?(saved?.state==='UNKNOWN'&&saved.source==='USER'?'모름':'미확인'):(f.choices?.find(c=>String(c.value)===String(value))?.label??String(value))+(f.unit?' '+f.unit:'');
    const source=draft?'수정 중':SOURCE[saved?.source]||'측정·입력 근거 없음';
    const state=saved?.state==='ESTIMATED'?' · 추정값':saved?.state==='CONFLICT'?' · 값 불일치':saved?.state==='UNKNOWN'&&saved.source==='USER'?' · 모름으로 저장':'';
    const applied=f.photo_unused?' · 사진 사용 안 함':!draft&&f.destination?.type==='manual'&&value!=null&&['KNOWN','ESTIMATED'].includes(saved?.state)?' · 현재 점수에 반영':'';
    const attrs=`data-intake-form="${esc(f.identity)}" aria-label="${esc(label)}" ${busy?'disabled':''}`;
    const control=!editing?'':f.kind==='choice'?`<select ${attrs}><option value="" ${value==null?'selected':''}>모름 / 미확인</option>${(f.choices||[]).map(c=>`<option value="${esc(c.value)}" ${value===c.value?'selected':''}>${esc(c.label)}</option>`).join('')}</select>`:`<input ${attrs} type="${f.kind==='number'?'number':'text'}" ${f.kind==='number'?`min="0" step="any" ${f.maximum!=null?`max="${f.maximum}"`:''}`:''} value="${esc(value)}" placeholder="미확인">`;
    return `<div class="intake-data-row" data-intake-data="${esc(f.identity)}"><div><strong>${esc(label)}${f.unit?` <small>(${esc(f.unit)})</small>`:''}</strong><span class="intake-data-value">${esc(display)}</span><small class="intake-data-source">${esc(source+state+applied)}</small>${saved?.quote?`<small class="intake-data-evidence">${esc(saved.quote)}</small>`:''}</div>${editing?control:`<button type="button" data-intake-edit-field="${esc(f.identity)}" aria-label="${esc(label)} 수정" ${busy?'disabled':''}>수정</button>`}</div>`;
  };
  const groups=new Map();
  for(const field of fields) {
    const photo=['context','view','manual','load','load_kg','load_link'].includes(field.destination?.type);
    const title=photo?(field.photo_label||field.display_condition||'사진 분석값'):'작업·조사 정보';
    if(!groups.has(title))groups.set(title,{photo,fields:[]});
    groups.get(title).fields.push(field);
  }
  const sections=[...groups].map(([title,group])=>`<details class="intake-form-section" data-intake-section="${group.photo?'measurements':'conditions'}" ${group.photo?'data-intake-photo-optional open':''}><summary>${esc(title)} · 현재 값 ${group.fields.length}개</summary>${group.fields.map(row).join('')}</details>`).join('');
  return `<dialog class="intake-dialog" data-intake-dialog aria-labelledby="intake-dialog-title" aria-busy="${Boolean(busy)}"><header class="intake-dialog-header"><div><span class="intake-eyebrow">LOCO · 분석값 확인·수정</span><h2 id="intake-dialog-title">현재 분석에 사용한 정보</h2></div><button type="button" data-quick="intake-close" aria-label="닫기" ${busy?'disabled':''}>×</button></header>${busy?renderActivity(typeof busy==='string'?busy:'저장하고 있어요',intake.busyElapsedSeconds):''}<div class="intake-dialog-body"><p class="intake-section-lead">측정값과 입력값은 이미 반영했어요. 미확인은 그대로 유지하며, 바꿀 항목의 ‘수정’을 누르면 편집할 수 있어요.</p>${sections||'<p>저장된 분석값이 없어요.</p>'}<details class="intake-form-section intake-history-section"><summary>이전 입력 기록 보기</summary>${renderIntakeHistory(intake.state,{details:false})}</details>${intake.saveError?'<p class="quick-warn">저장하지 못했어요. 수정한 값은 유지돼요.</p>':''}</div><footer class="intake-dialog-footer"><button type="button" data-quick="intake-close" ${busy?'disabled':''}>닫기</button><button type="button" class="primary" data-quick="intake-form-next" ${busy?'disabled':''}>수정한 값 저장</button></footer></dialog>`;
}
