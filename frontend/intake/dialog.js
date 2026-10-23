import {renderForm} from './form.js';
import {connectionStatus} from './view.js';
import {renderActivity} from './activity.js';
const esc=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const display=(q,value)=>q.choices?.find(c=>String(c.value)===String(value))?.label??`${value}${q.unit?' '+q.unit:''}`;
const count=value=>Number.isSafeInteger(value)&&value>=0;
const choicesFor=q=>q?.kind==='choice'&&Array.isArray(q.choices)&&q.choices.length>0;

function progressPanel(state) {
  const p=state.progress;
  const valid=p&&[p.completed_count,p.total_count,p.remaining_count,p.percent].every(count)
    &&p.total_count===p.completed_count+p.remaining_count&&p.percent<=100
    &&p.percent===(p.total_count?Math.floor(p.completed_count*100/p.total_count):100)
    &&(!count(state.remaining_count)||p.remaining_count===state.remaining_count);
  if(!valid) {
    const remaining=count(state.remaining_count)?`남은 확인 항목 <b>${state.remaining_count}개</b>`:'남은 항목을 확인하고 있어요.';
    return `<section class="intake-progress" aria-label="추가 확인 진행"><div class="intake-progress-heading"><span>추가 확인 진행</span><strong>—</strong></div><p class="intake-progress-counts">${remaining}</p><p class="intake-progress-note">진행률 정보를 확인하고 있어요.</p></section>`;
  }
  const completion=p.remaining_count===0?`<p class="intake-progress-note">추가 질문이 없어요.${state.complete===false?' 입력·검토가 필요한 항목은 결과에서 확인해 주세요.':''}</p>`:'';
  return `<section class="intake-progress" aria-label="추가 확인 진행"><div class="intake-progress-heading"><span>추가 확인 진행</span><strong>${p.percent}%</strong></div>
    <div class="intake-progress-track" role="progressbar" aria-label="추가 확인 진행률" aria-valuemin="0" aria-valuemax="100" aria-valuenow="${p.percent}" aria-valuetext="${p.percent}% · 남은 확인 항목 ${p.remaining_count}개"><span class="intake-progress-fill" style="width:${p.percent}%"></span></div>
    <p class="intake-progress-counts" aria-live="polite"><span>확인한 항목 <b>${p.completed_count}개</b> / 전체 ${p.total_count}개</span><strong>남은 항목 ${p.remaining_count}개</strong></p>
    <p class="intake-progress-note">숫자는 세부 항목 수예요. 관련 항목은 한 화면에서 함께 확인해요. 답변에 따라 필요한 항목 수가 달라질 수 있어요.</p>${completion}</section>`;
}

export function renderDialog(intake,busy) {
  if(!intake.dialogOpen||!intake.state)return '';
  if(Array.isArray(intake.state.form_fields))return renderForm(intake,busy);
  const state=intake.state,q=intake.questions[0];
  if(!busy&&intake.shouldReview?.())return `<dialog class="intake-dialog" data-intake-dialog aria-labelledby="intake-dialog-title"><header class="intake-dialog-header"><div><span class="intake-eyebrow">LOCO · 간단 확인</span><h2 id="intake-dialog-title">결과를 먼저 확인해 볼까요?</h2></div><button type="button" data-quick="intake-close" aria-label="추가 질문 닫기">×</button></header><div class="intake-dialog-body"><article><h3>추가 질문을 끝까지 답하지 않아도 돼요.</h3><p class="quick-note">지금까지 입력한 내용으로 결과를 먼저 확인하세요. 아직 확인하지 않은 값은 입력 필요·미완성으로 남겨 두고, 필요한 부분만 나중에 보완할 수 있어요.</p></article><details class="intake-review-details"><summary>전체 상세 항목 진행 보기</summary>${progressPanel(state)}</details></div><footer class="intake-dialog-footer"><button type="button" data-quick="intake-continue">상세 항목 더 확인</button><button type="button" class="primary" data-quick="next">결과 먼저 보기 →</button></footer></dialog>`;

  const hasAnswerGroup=Array.isArray(q?.answer_questions)&&q.answer_questions.length>0;
  const members=hasAnswerGroup?(intake.answerFields?.(q)||q.answer_questions):[];
  const grouped=hasAnswerGroup&&members.length>0&&members.every(choicesFor);
  const hasChoices=grouped||!hasAnswerGroup&&choicesFor(q),paired=!hasAnswerGroup&&hasChoices&&choicesFor(q.paired_question)?q.paired_question:null;
  const pairReady=paired&&[q,paired].every(field=>intake.pairValues?.has(field.identity));
  const groupReady=grouped&&members.some(field=>intake.pairValues?.has(field.identity));
  const writing=!hasChoices||intake.writingFor===q.identity||Boolean(intake.text.trim());
  const auto=state.facts.filter(f=>f.state==='KNOWN'&&['AI','MOVENET'].includes(f.source)).length;
  const condition=q&&q.condition!==state.contract.policy.default_condition ? `<span class="intake-context">${esc(q.condition)}</span>` : '';
  const coverage=!grouped&&q?.ai_writable===false?state.contract.fields.filter(f=>f.destination?.type==='work_type'&&!state.facts.some(saved=>saved.target===f.target)).map(f=>f.label):[];
  const choice=(field,value,label,inPair=false)=>{
    const selected=inPair&&intake.pairValues?.has(field.identity)&&intake.pairValues.get(field.identity)===value;
    return `<button type="button" data-${inPair?'intake-pair-pick':'intake-pick'}="${esc(field.identity)}" data-value="${esc(value??'')}" ${inPair?`class="${selected?'selected':''}" aria-pressed="${Boolean(selected)}"`:''} ${busy?'disabled':''}>${esc(label)}</button>`;
  };
  const details=(field,inPair=false,inGroup=false)=>{
    const saved=state.facts.find(f=>f.identity===field.identity);
    const estimate=saved?.state==='ESTIMATED'?`<div class="intake-estimate">사진에서 ${esc(display(field,saved.value))}로 측정했어요. ${esc(saved.quote)}${inGroup?'':choice(field,saved.value,'이 사진 측정값이 맞아요',inPair)}</div>`:'';
    const conflict=saved?.state==='CONFLICT'?`<p class="quick-warn">앞선 값 ${esc(display(field,saved.value))}과 새 설명 ${esc(display(field,saved.conflict.value))}이 달라요. 어느 쪽이 맞는지 알려 주세요.</p>`:'';
    return estimate+conflict;
  };
  const replies=(field,inPair=false)=>`<div class="quick-choices intake-quick-replies">${field.choices.map(c=>choice(field,c.value,c.label,inPair)).join('')}${choice(field,null,'모르겠어요',inPair)}</div>`;
  const side=field=>field.destination?.scope==='LEFT'||field.destination?.view==='LEFT'?'왼쪽':'오른쪽';
  const pairedPanel=()=>`<div class="intake-paired-questions">${[q,paired].sort(a=>side(a)==='왼쪽'?-1:1).map(field=>`<fieldset class="intake-side-question" data-intake-pair-question="${esc(field.identity)}"><legend>${side(field)}</legend><p class="quick-note">${esc(field.text)}</p>${details(field,true)}${replies(field,true)}</fieldset>`).join('')}</div><div class="intake-dialog-actions"><button type="button" class="primary" data-quick="intake-pair-save" ${busy||!pairReady?'disabled':''}>선택한 답변 저장</button></div>`;
  const groupPanel=()=>`<p class="quick-note">아는 항목만 선택해도 돼요. 미선택은 그대로 남아요. 모두 답하지 않아도 아래에서 현재 정보로 결과를 볼 수 있어요.</p><div class="intake-group-questions">${members.map(field=>{
    const selected=intake.pairValues?.has(field.identity),value=intake.pairValues?.get(field.identity);
    const options=[`<option value="__unselected__" ${!selected?'selected':''}>선택해 주세요</option>`,
      ...field.choices.map(choice=>`<option value="${esc(choice.value)}" ${selected&&value===choice.value?'selected':''}>${esc(choice.label)}</option>`),
      `<option value="__unknown__" ${selected&&value===null?'selected':''}>모르겠어요</option>`].join('');
    return `<div class="intake-group-item"><label class="intake-group-question"><span>${esc(field.label||field.text)}</span><select data-intake-group-value="${esc(field.identity)}" aria-label="${esc(field.label||field.text)}" ${busy?'disabled':''}>${options}</select></label>${details(field,false,true)}</div>`;
  }).join('')}</div><div class="intake-dialog-actions"><button type="button" class="primary" data-quick="intake-group-save" ${busy||!groupReady?'disabled':''}>선택한 항목 저장</button></div>`;
  const send=()=>`<button type="button" class="primary" data-quick="adaptive-next" ${busy||!intake.text.trim()&&state.ai?.status!=='ERROR'?'disabled':''}>${busy?'답변을 정리하는 중…':state.ai?.status==='ERROR'?'다시 시도':'답변 보내기'}</button>`;
  return `<dialog class="intake-dialog" data-intake-dialog aria-labelledby="intake-dialog-title" aria-busy="${Boolean(busy)}"><header class="intake-dialog-header"><div><span class="intake-eyebrow">LOCO · 추가 확인</span><h2 id="intake-dialog-title">${q?'작업 정보를 확인해요':'추가 질문 확인을 마쳤어요'}</h2></div><button type="button" data-quick="intake-close" aria-label="추가 질문 닫기">×</button></header>
    ${busy?renderActivity(typeof busy==='string'?busy:'답변을 정리하고 있어요',intake.busyElapsedSeconds):''}${progressPanel(state)}<div class="intake-dialog-body">${busy?'':connectionStatus(intake,false)}<p class="intake-auto-note">설명·사진에서 ${auto}개 정보를 자동으로 정리했어요. 이미 아는 것은 다시 묻지 않아요.</p>
    ${q?`<article data-intake-question="${esc(q.identity)}">${condition}<h3>${grouped?esc(q.group_title||'관련된 항목을 함께 확인해 주세요'):paired?'왼쪽과 오른쪽을 함께 확인해 주세요':esc(q.text)}</h3>${grouped?'':`<p class="quick-note">${paired?'양쪽의 값을 각각 선택하고 한 번에 저장해 주세요.':esc(q.reason)}</p>`}${coverage.length?`<p class="intake-auto-note">확인할 특징: ${coverage.map(esc).join(' · ')}</p>`:''}${grouped?groupPanel():paired?pairedPanel():details(q)+(hasChoices?replies(q):'')}</article>`:''}
    ${!writing?`<button type="button" class="intake-write-toggle" data-quick="intake-write" aria-expanded="false" aria-controls="intake-writing" ${busy?'disabled':''}>직접 설명하기</button>`:''}
    <div id="intake-writing" class="intake-writing" ${writing?'':'hidden'}>${writing?`<label class="intake-response-label" for="intake-reply">${q?'답변을 편하게 적어 주세요':'작업 설명을 더해도 돼요'}</label><textarea id="intake-reply" data-intake-reply maxlength="${state.contract.policy.text_limit}" rows="3" ${busy?'disabled':''} placeholder="${esc(q?.reply_example || '작업에 대해 편하게 설명해 주세요.')}">${esc(intake.text)}</textarea>
    <div class="intake-dialog-actions">${send()}${q&&!hasChoices?choice(q,null,'모르겠어요'):''}</div>`:''}</div>
    ${intake.saveError?'<p class="quick-warn">답변을 저장하지 못했어요. 입력한 내용은 유지돼요. 다시 시도해 주세요.</p>':''}
    ${!writing&&state.ai?.status==='ERROR'?`<div class="intake-dialog-actions">${send()}</div>`:''}</div>
    <footer class="intake-dialog-footer"><button type="button" data-quick="intake-close">나중에 확인</button><button type="button" data-quick="next" ${busy?'disabled':''}>현재 정보로 결과 보기 →</button></footer></dialog>`;
}

export function mountDialog(host,busy,focusPair=null) {
  const dialog=host.querySelector?.('[data-intake-dialog]');
  if(!dialog)return;
  if(!dialog.open)dialog.showModal();
  if(!busy) {
    const selected=focusPair&&[...dialog.querySelectorAll('[data-intake-pair-pick][aria-pressed="true"], [data-intake-group-value]')].find(control=>(control.dataset.intakePairPick||control.dataset.intakeGroupValue)===focusPair);
    (selected||dialog.querySelector('[data-intake-reply]')||dialog.querySelector('[data-intake-group-value]:not(:disabled)')||dialog.querySelector('.intake-quick-replies button:not(:disabled)'))?.focus({preventScroll:true});
  }
}
