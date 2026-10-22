const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const SOURCE = {USER:'직접 입력',AI:'작업 설명',MOVENET:'사진 측정',SAVED:'저장된 입력'};
const REASON = {DISABLED:'AI가 꺼져 있어 남은 항목을 직접 입력할 수 있어요.',NO_API_KEY:'AI 키가 없어 남은 항목을 직접 입력할 수 있어요.',TIMEOUT:'AI 응답이 늦어 직접 입력할 수 있는 질문을 보여 드려요.',API_ERROR:'AI 연결을 확인하지 못했어요. 입력한 정보는 유지돼요.',INVALID_STRUCTURED_CONTENT:'AI 응답을 읽지 못했어요. 남은 항목을 직접 입력할 수 있어요.'};
const conditionLabel = (condition, state) => condition && condition !== state.contract.policy.default_condition ? ` · ${esc(condition)}` : '';
function display(field, value) {
  if (value == null) return '모름';
  return field?.choices?.find(c => String(c.value) === String(value))?.label ?? `${value}${field?.unit ? ' '+field.unit : ''}`;
}
function editor(intake, field, identity) {
  const value = intake.value(identity), state = intake.state;
  if (field.kind === 'choice') return `<div class="quick-choices">${[...field.choices,{value:null,label:'모름'}].map(c => `<button type="button" data-intake-choice="${esc(identity)}" data-value="${esc(c.value ?? '')}" class="${value === c.value ? 'selected' : ''}">${esc(c.label)}</button>`).join('')}</div>`;
  return `<label class="intake-value"><input aria-label="${esc(field.label)}" ${field.kind === 'number' ? `type="number" min="0" ${field.maximum == null ? '' : `max="${field.maximum}"`} step="any"` : 'type="text" maxlength="80"'} data-intake-value="${esc(identity)}" value="${esc(value ?? '')}"><span>${esc(field.unit)}</span></label><button type="button" data-intake-choice="${esc(identity)}" data-value="">모름으로 남기기</button>`;
}
export function renderSummary(intake) {
  const state = intake.state; if (!state) return '';
  const known = state.facts.filter(f => f.state === 'KNOWN'), issues = state.facts.filter(f => f.state !== 'KNOWN');
  const row = fact => {
    const field = state.contract.fields.find(f => f.target === fact.target);
    return `<li><div><strong>${esc(fact.label)}${conditionLabel(fact.condition,state)}</strong><span>${esc(display(field,fact.value))}</span><small>${esc(SOURCE[fact.source] || fact.source)}${fact.quote ? ' · '+esc(fact.quote) : ''}${fact.state === 'CONFLICT' ? ' · 다른 값이 있어 확인 필요' : ''}</small></div><button type="button" data-intake-edit="${esc(fact.identity)}">수정</button>${intake.editing === fact.identity ? `<div class="intake-edit">${editor(intake,field,fact.identity)}</div>` : ''}</li>`;
  };
  return `<section class="intake-summary"><details><summary>자동으로 정리한 정보 ${known.length}개 · 저장된 값 보기·수정</summary><ul>${known.map(row).join('')}</ul>${issues.length ? `<h4>모름·확인 필요 ${issues.length}개</h4><ul>${issues.map(row).join('')}</ul>` : ''}${known.length ? '' : '<p>사진 측정이나 작업 설명에서 파악한 값이 여기에 저장돼요.</p>'}</details><p class="intake-save" role="status">${intake.saveError ? esc(intake.saveError) : intake.saving ? '입력을 저장하고 있어요…' : '입력과 출처를 이 작업에 저장했어요.'}</p></section>`;
}
export function renderQuestions(intake, busy) {
  const state = intake.state; if (!state) return '';
  const fields = intake.questions.map(q => {
    const saved = state.facts.find(f => f.identity === q.identity);
    const conflict = saved?.state === 'CONFLICT' ? `<p class="quick-warn">앞선 값: ${esc(display(q,saved.value))} · 새 설명: ${esc(display(q,saved.conflict.value))}<br>${esc(saved.conflict.quote)}</p>` : saved?.state === 'ESTIMATED' ? `<p class="quick-note">사진 추정: ${esc(display(q,saved.value))} · ${esc(saved.quote)}</p><button type="button" data-intake-choice="${esc(q.identity)}" data-value="${esc(saved.value)}">이 사진 추정값 사용</button>` : '';
    return `<article class="intake-question" data-intake-question="${esc(q.identity)}"><h3>${esc(q.text)}${conditionLabel(q.condition,state)}</h3><p class="quick-note">${esc(q.reason)}</p>${saved ? `<small class="intake-answer-state">${saved.state === 'KNOWN' ? '답변 저장됨' : saved.state === 'UNKNOWN' ? '모름으로 저장됨' : '서로 다른 값 확인'}</small>` : ''}${conflict}${editor(intake,q,q.identity)}</article>`;
  }).join('');
  const reason = state.reason && state.reason !== 'INPUT_CHANGED' ? `<p class="quick-note">${esc(REASON[state.reason] || 'AI 연결을 쓰지 못했어요. 아래 항목으로 계속 진행할 수 있어요.')}</p>` : '';
  return `<section class="panel intake-followup"><div class="intake-heading"><h2>${state.questions.length ? '이 부분만 더 알려 주세요' : state.complete ? '결과를 볼 준비가 됐어요' : '현재 정보로 결과를 볼 수 있어요'}</h2><span>남은 입력 ${state.remaining_count}개</span></div><p class="quick-note">이미 파악한 값은 다시 묻지 않아요. 모르는 항목은 모름으로 남겨도 돼요.</p>${reason}${fields}
    <div class="intake-reply"><label for="intake-reply">말로 한 번에 답해도 돼요</label><textarea id="intake-reply" data-intake-reply maxlength="${state.contract.policy.text_limit}" rows="3" placeholder="예: 사진도 같은 20kg 상자예요. 손잡이가 있고 양손으로 잡아요.">${esc(intake.text)}</textarea><button type="button" class="primary" data-quick="adaptive-next" ${busy ? 'disabled' : ''}>${intake.text.trim() ? '답변 정리하고 다음 확인' : '다음 확인 보기'}</button></div>
    <div class="quick-nav"><button type="button" data-quick="photos">사진·작업 설명으로</button><button type="button" class="primary" data-quick="next" ${busy ? 'disabled' : ''}>현재 정보로 결과 보기 →</button></div></section>`;
}
