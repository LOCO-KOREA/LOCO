import {connectionStatus} from './view.js';
const esc=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const display=(q,value)=>q.choices?.find(c=>String(c.value)===String(value))?.label??`${value}${q.unit?' '+q.unit:''}`;

export function renderDialog(intake,busy) {
  if(!intake.dialogOpen||!intake.state)return '';
  const state=intake.state,q=intake.questions[0],saved=state.facts.find(f=>f.identity===q?.identity);
  const auto=state.facts.filter(f=>f.state==='KNOWN'&&['AI','POSE','MOVENET'].includes(f.source)).length;
  const condition=q&&q.condition!==state.contract.policy.default_condition ? `<span class="intake-context">${esc(q.condition)}</span>` : '';
  const coverage=q?.ai_writable===false?state.contract.fields.filter(f=>f.destination?.type==='work_type'&&!state.facts.some(saved=>saved.target===f.target)).map(f=>f.label):[];
  const choice=(value,label)=>`<button type="button" data-intake-pick="${esc(q.identity)}" data-value="${esc(value??'')}" ${busy?'disabled':''}>${esc(label)}</button>`;
  const estimate=saved?.state==='ESTIMATED'?`<div class="intake-estimate">사진에서 ${esc(display(q,saved.value))}로 측정했어요. ${esc(saved.quote)}${choice(saved.value,'이 사진 측정값이 맞아요')}</div>`:'';
  const conflict=saved?.state==='CONFLICT'?`<p class="quick-warn">앞선 값 ${esc(display(q,saved.value))}과 새 설명 ${esc(display(q,saved.conflict.value))}이 달라요. 어느 쪽이 맞는지 알려 주세요.</p>`:'';
  return `<dialog class="intake-dialog" data-intake-dialog aria-labelledby="intake-dialog-title"><header><div><span class="intake-eyebrow">LOCO AI · 추가 확인</span><h2 id="intake-dialog-title">${q?'이것만 알려 주세요':'정리한 내용으로 결과를 볼 수 있어요'}</h2></div><button type="button" data-quick="intake-close" aria-label="추가 질문 닫기">×</button></header>
    ${connectionStatus(intake,busy)}<p class="intake-auto-note">설명·사진에서 ${auto}개 정보를 자동으로 정리했어요. 이미 아는 것은 다시 묻지 않아요.</p>
    ${q?`<article data-intake-question="${esc(q.identity)}">${condition}<h3>${esc(q.text)}</h3><p class="quick-note">${esc(q.reason)}</p>${coverage.length?`<p class="intake-auto-note">확인할 특징: ${coverage.map(esc).join(' · ')}</p>`:''}${estimate}${conflict}<div class="quick-choices intake-quick-replies">${q.kind==='choice'?q.choices.map(c=>choice(c.value,c.label)).join(''):''}</div></article>`:''}
    <label class="intake-response-label" for="intake-reply">${q?'답변을 편하게 적어 주세요':'작업 설명을 더해도 돼요'}</label><textarea id="intake-reply" data-intake-reply maxlength="${state.contract.policy.text_limit}" rows="3" ${busy?'disabled':''} placeholder="${esc(q?.reply_example || '작업에 대해 편하게 설명해 주세요.')}">${esc(intake.text)}</textarea>
    ${intake.saveError?`<p class="quick-warn">${esc(intake.saveError)}</p>`:''}
    <div class="intake-dialog-actions"><button type="button" class="primary" data-quick="adaptive-next" ${busy||!intake.text.trim()&&state.ai?.status!=='ERROR'?'disabled':''}>${busy?'AI가 정리하는 중…':state.ai?.status==='ERROR'?'AI 다시 연결하고 정리':'답변 보내기'}</button>${q?choice(null,'모르겠어요'):''}</div>
    <footer><button type="button" data-quick="intake-close">나중에 확인</button><button type="button" data-quick="next" ${busy?'disabled':''}>현재 정보로 결과 보기 →</button></footer></dialog>`;
}

export function mountDialog(host,busy) {
  const dialog=host.querySelector?.('[data-intake-dialog]');
  if(!dialog)return;
  if(!dialog.open)dialog.showModal();
  if(!busy)dialog.querySelector('[data-intake-reply]')?.focus({preventScroll:true});
}
