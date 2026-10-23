import {renderActivity} from './activity.js';
const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
export function renderForm(intake,busy) {
  const stage=intake.formStage, fields=intake.formFields(), facts=intake.state.facts;
  const control=f=>{
    const value=intake.formValue(f), saved=facts.find(s=>s.identity===f.identity);
    const attrs=`data-intake-form="${esc(f.identity)}" ${busy?'disabled':''}`;
    const input=f.kind==='choice'?`<select ${attrs}><option value="" ${value==null?'selected':''}>모름 / 미확인</option>${f.choices.map(c=>`<option value="${esc(c.value)}" ${value===c.value?'selected':''}>${esc(c.label)}</option>`).join('')}</select>`:
      `<input ${attrs} type="${f.kind==='number'?'number':'text'}" ${f.kind==='number'?`min="0" step="any" ${f.maximum!=null?`max="${f.maximum}"`:''}`:''} value="${esc(value)}" placeholder="미확인">`;
    const status=saved?.state==='CONFLICT'?'<small class="quick-warn">기존 설명과 다른 값이 있어 확인이 필요해요.</small>':saved?.state==='ESTIMATED'?`<small>사진 추정: ${esc(f.choices?.find(c=>c.value===saved.value)?.label??saved.value)} · 직접 확인해 주세요.</small>`:saved?.source==='AI'&&saved.state==='KNOWN'?'<small>설명에서 자동 정리</small>':'';
    return `<div class="intake-group-item"><label class="intake-group-question"><span>${esc(f.label)}${f.unit?` <small>(${esc(f.unit)})</small>`:''}</span>${input}</label>${status}</div>`;
  };
  const groups=new Map();
  for(const field of fields) {const key=(field.group||'기본 작업 정보')+(field.condition!=='default'?' · '+field.condition:'');if(!groups.has(key))groups.set(key,[]);groups.get(key).push(field);}
  const sections=[...groups].map(([title,rows])=>{
    const optional=rows.every(f=>['manual','view'].includes(f.destination.type));
    return optional?`<details class="intake-form-section"><summary>${esc(title)} · 선택 보완</summary>${rows.map(control).join('')}</details>`:`<section class="intake-form-section"><h3>${esc(title)}</h3>${rows.map(control).join('')}</section>`;
  }).join('');
  return `<dialog class="intake-dialog" data-intake-dialog aria-labelledby="intake-dialog-title" aria-busy="${Boolean(busy)}"><header class="intake-dialog-header"><div><span class="intake-eyebrow">LOCO · 작업 정보 확인</span><h2 id="intake-dialog-title">${stage===0?'작업 특징을 함께 확인해 주세요':'해당 작업의 조건을 확인해 주세요'}</h2></div><button type="button" data-quick="intake-close" ${busy?'disabled':''} aria-label="닫기">×</button></header>
    <div class="intake-form-steps" aria-label="입력 단계"><span ${stage===0?'aria-current="step"':''}>1. 작업 특징</span><span ${stage===1?'aria-current="step"':''}>2. 작업 조건</span><span>3. 결과</span></div>
    <div class="intake-form-progress"><span>입력 단계 ${stage+1}/2 · ${stage*50}%</span><div class="intake-progress-track" role="progressbar" aria-label="입력 단계 진행" aria-valuemin="0" aria-valuemax="100" aria-valuenow="${stage*50}"><span class="intake-progress-fill" style="width:${stage*50}%"></span></div><small>단계 이동 기준이며, 계산에 필요한 정보가 모두 채워졌다는 뜻은 아니에요.</small></div>
    ${busy?renderActivity(typeof busy==='string'?busy:'저장하고 있어요',intake.busyElapsedSeconds):''}
    <div class="intake-dialog-body"><p class="intake-auto-note">설명에서 정리한 값은 미리 채웠어요. 아는 항목만 확인하거나 고치세요. 비워 둔 값은 미확인으로 남아요.</p>${sections||'<p>추가로 입력할 작업 조건이 없어요. 결과를 확인해 주세요.</p>'}
    <details class="intake-form-section" ${intake.text?'open':''}><summary>설명이 다르거나 더할 내용이 있나요?</summary><textarea data-intake-reply maxlength="${intake.state.contract.policy.text_limit}" placeholder="추가 설명을 적어 주세요">${esc(intake.text)}</textarea><button type="button" data-quick="adaptive-next" ${busy||!intake.text.trim()?'disabled':''}>설명에서 정보 정리</button></details>
    ${intake.saveError?'<p class="quick-warn">저장하지 못했어요. 입력은 유지돼요. 다시 시도해 주세요.</p>':''}</div>
    <footer class="intake-dialog-footer"><button type="button" data-quick="${stage===0?'intake-close':'intake-form-back'}" ${busy?'disabled':''}>${stage===0?'나중에 확인':'이전'}</button><button type="button" class="primary" data-quick="intake-form-next" ${busy?'disabled':''}>${stage===0?'저장하고 작업 조건 확인 →':'저장하고 결과 보기 →'}</button></footer></dialog>`;
}
