import {renderActivity} from './activity.js';
import {renderIntakeHistory} from './history-view.js';
const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
export function renderForm(intake,busy) {
  const stage=intake.formStage, fields=intake.formFields(), facts=intake.state.facts;
  const control=f=>{
    const value=intake.formValue(f), saved=facts.find(s=>s.identity===f.identity);
    const attrs=`data-intake-form="${esc(f.identity)}" ${busy?'disabled':''}`;
    const input=f.kind==='choice'?`<select ${attrs}><option value="" ${value==null?'selected':''}>모름 / 미확인</option>${f.choices.map(c=>`<option value="${esc(c.value)}" ${value===c.value?'selected':''}>${esc(c.label)}</option>`).join('')}</select>`:
      `<input ${attrs} type="${f.kind==='number'?'number':'text'}" ${f.kind==='number'?`min="0" step="any" ${f.maximum!=null?`max="${f.maximum}"`:''}`:''} value="${esc(value)}" placeholder="미확인">`;
    const status=saved?.state==='CONFLICT'?'<small class="quick-warn">기존 설명과 다른 값이 있어 확인이 필요해요.</small>':saved?.state==='ESTIMATED'?`<small>사진 추정: ${esc(f.choices?.find(c=>c.value===saved.value)?.label??saved.value)} · 직접 확인해 주세요.</small>`:saved?.source==='AI'&&saved.state==='KNOWN'?'<small>설명에서 자동 정리</small>':'';
    const reason=f.destination.type==='manual'&&f.reason?`<small class="intake-measurement-reason">${esc(f.reason)}</small>`:'';
    return `<div class="intake-group-item"><label class="intake-group-question"><span>${esc(f.label)}${f.unit?` <small>(${esc(f.unit)})</small>`:''}</span>${input}</label>${status}${reason}</div>`;
  };
  const handled=f=>{const saved=facts.find(s=>s.identity===f.identity);return saved?.state==='KNOWN'||saved?.state==='UNKNOWN'&&saved.source==='USER';};
  const pending=fields.filter(f=>!handled(f)), confirmed=fields.filter(handled);
  const optional=f=>(intake.state.contract.policy.optional_photo_destinations||['manual','view']).includes(f.destination.type);
  const core=pending.filter(f=>!optional(f));
  const limit=intake.state.contract.policy.form_prompt_limit||3;
  const prompt=stage===0&&core.length?'설명한 작업 외에 아래 작업도 하나요?':core.length?core.slice(0,limit).map(f=>f.label+(f.unit?` (${f.unit})`:'')).join(' · '):'';
  const groups=new Map();
  for(const field of pending) {const photo=field.photo_label||field.display_condition;const condition=field.condition&&!field.condition.startsWith(intake.state.contract.photo_policy?.condition_prefix||'photo:')&&field.condition!=='default'?field.condition:'';const key=(field.group||'기본 작업 정보')+(photo||condition?' · '+(photo||condition):'');if(!groups.has(key))groups.set(key,[]);groups.get(key).push(field);}
  const sections=[...groups].map(([title,rows])=>{
    const photoOnly=rows.every(optional);
    return photoOnly?`<details class="intake-form-section" data-intake-photo-optional><summary>${esc(title)} · 사진 점수를 더 확인할 때</summary>${rows.map(control).join('')}</details>`:`<section class="intake-form-section"><h3>${esc(title)}</h3>${rows.map(control).join('')}</section>`;
  }).join('');
  const natural=`<section class="intake-form-section" data-intake-natural-answer><h3>${esc(prompt||'설명이 다르거나 더할 내용이 있나요?')}</h3><p>아는 내용을 한 번에 적어 주세요. 설명에서 필요한 값을 정리해요.</p>${stage===0&&core.length?`<ul>${core.map(f=>`<li>${esc(f.label)}</li>`).join('')}</ul>`:''}<textarea data-intake-reply maxlength="${intake.state.contract.policy.text_limit}" placeholder="예: 다른 작업은 없어요. 이 조건은 하루 30분, 1분에 1번 정도예요.">${esc(intake.text)}</textarea><button type="button" data-quick="adaptive-next" ${busy||!intake.text.trim()?'disabled':''}>답변 정리</button>${stage===0&&core.length?`<button type="button" data-quick="intake-no-other-work" ${busy?'disabled':''}>선택하지 않은 나머지 작업은 모두 안 해요</button>`:''}</section>`;
  return `<dialog class="intake-dialog" data-intake-dialog aria-labelledby="intake-dialog-title" aria-busy="${Boolean(busy)}"><header class="intake-dialog-header"><div><span class="intake-eyebrow">LOCO · 작업 정보 확인</span><h2 id="intake-dialog-title">${stage===0?'작업 특징을 함께 확인해 주세요':'해당 작업의 조건을 확인해 주세요'}</h2></div><button type="button" data-quick="intake-close" ${busy?'disabled':''} aria-label="닫기">×</button></header>
    <div class="intake-form-steps" aria-label="입력 단계"><span ${stage===0?'aria-current="step"':''}>1. 작업 특징</span><span ${stage===1?'aria-current="step"':''}>2. 작업 조건</span><span>3. 결과</span></div>
    <div class="intake-form-progress"><span>입력 단계 ${stage+1}/2 · ${stage*50}%</span><div class="intake-progress-track" role="progressbar" aria-label="입력 단계 진행" aria-valuemin="0" aria-valuemax="100" aria-valuenow="${stage*50}"><span class="intake-progress-fill" style="width:${stage*50}%"></span></div><small>단계 이동 기준이며, 계산에 필요한 정보가 모두 채워졌다는 뜻은 아니에요.</small></div>
    ${busy?renderActivity(typeof busy==='string'?busy:'저장하고 있어요',intake.busyElapsedSeconds):''}
    <div class="intake-dialog-body"><p class="intake-auto-note">아직 확인하지 못한 항목만 보여 드려요. 이미 정리한 값은 다시 입력하지 않아도 돼요. 비워 둔 값은 미확인으로 남아요.</p>${natural}<details class="intake-form-section" data-intake-direct-fields><summary>항목을 직접 선택해서 답하기</summary><div data-intake-unanswered>${sections||'<p>추가로 입력할 항목이 없어요. 다음 단계로 이동해 주세요.</p>'}</div></details>${confirmed.length?`<details class="intake-form-section" data-intake-confirmed><summary>이미 확인한 정보 ${confirmed.length}개 · 수정하기</summary>${confirmed.map(control).join('')}</details>`:''}${renderIntakeHistory(intake.state,{details:false})}
    ${intake.saveError?'<p class="quick-warn">저장하지 못했어요. 입력은 유지돼요. 다시 시도해 주세요.</p>':''}</div>
    <footer class="intake-dialog-footer"><button type="button" data-quick="${stage===0?'intake-close':'intake-form-back'}" ${busy?'disabled':''}>${stage===0?'나중에 확인':'이전'}</button><button type="button" class="primary" data-quick="intake-form-next" ${busy?'disabled':''}>${stage===0?'저장하고 작업 조건 확인 →':'저장하고 결과 보기 →'}</button></footer></dialog>`;
}
