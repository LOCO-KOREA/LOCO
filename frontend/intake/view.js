const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const SOURCE = {USER:'직접 입력',AI:'작업 설명',POSE:'사진 측정',MOVENET:'사진 측정',SAVED:'저장된 입력'};
const conditionLabel = (condition, state) => condition && !condition.startsWith(state.contract.photo_policy?.condition_prefix||'photo:') && condition !== state.contract.policy.default_condition ? ` · ${esc(condition)}` : '';
function display(field, value) {
  if (value == null) return '모름';
  return field?.choices?.find(c => String(c.value) === String(value))?.label ?? `${value}${field?.unit ? ' '+field.unit : ''}`;
}
export function connectionStatus(intake, busy=false) {
  // Model identifiers, reasoning options and provider errors are internal details.
  if (!busy && intake.state?.ai?.status !== 'ERROR') return '';
  const status = busy ? 'REQUESTING' : 'ERROR';
  const label = busy ? '답변을 정리하고 있어요' : '답변 정리를 완료하지 못했어요. 선택지로 답하거나 다시 시도해 주세요.';
  return `<p class="intake-ai-status" data-ai-state="${status}" role="status">${label}</p>`;
}
function editor(intake, field, identity) {
  const value = intake.value(identity), state = intake.state;
  if (field.kind === 'choice') return `<div class="quick-choices">${[...field.choices,{value:null,label:'모름'}].map(c => `<button type="button" data-intake-choice="${esc(identity)}" data-value="${esc(c.value ?? '')}" class="${value === c.value ? 'selected' : ''}">${esc(c.label)}</button>`).join('')}</div>`;
  return `<label class="intake-value"><input aria-label="${esc(field.label)}" ${field.kind === 'number' ? `type="number" min="0" ${field.maximum == null ? '' : `max="${field.maximum}"`} step="any"` : 'type="text" maxlength="80"'} data-intake-value="${esc(identity)}" value="${esc(value ?? '')}"><span>${esc(field.unit)}</span></label><button type="button" data-intake-choice="${esc(identity)}" data-value="">모름으로 남기기</button>`;
}
export function renderSummary(intake) {
  const state = intake.state; if (!state) return '';
  const visible=state.facts.filter(f=>!f.alias_of&&f.photo_active!==false);
  const known = visible.filter(f => f.state === 'KNOWN'), issues = visible.filter(f => f.state !== 'KNOWN');
  const row = fact => {
    const field = state.contract.fields.find(f => f.target === fact.target);
    return `<li><div><strong>${esc(fact.label)}${conditionLabel(fact.condition,state)}</strong><span>${esc(display(field,fact.value))}</span><small>${esc(SOURCE[fact.source] || fact.source)}${fact.quote ? ' · '+esc(fact.quote) : ''}${fact.state === 'CONFLICT' ? ' · 다른 값이 있어 확인 필요' : ''}</small></div><button type="button" data-intake-edit="${esc(fact.identity)}">수정</button>${intake.editing === fact.identity ? `<div class="intake-edit">${editor(intake,field,fact.identity)}</div>` : ''}</li>`;
  };
  return `<section class="intake-summary"><details${intake.editing ? ' open' : ''}><summary>자동으로 정리한 정보 ${known.length}개 · 저장된 값 보기·수정</summary><ul>${known.map(row).join('')}</ul>${issues.length ? `<h4>모름·확인 필요 ${issues.length}개</h4><ul>${issues.map(row).join('')}</ul>` : ''}${known.length ? '' : '<p>사진 측정이나 작업 설명에서 파악한 값이 여기에 저장돼요.</p>'}</details>${renderIntakeHistory(state)}<p class="intake-save" role="status">${esc(intake.saveError?'입력을 저장하지 못했어요. 입력한 내용은 유지되니 다시 시도해 주세요.':intake.saveStatus?.()||(intake.saving?'입력을 저장하고 있어요…':'입력과 출처를 이 작업에 저장했어요.'))}</p></section>`;
}
export function renderQuestions(intake, busy) {
  const state = intake.state; if (!state) return '';
  return `<section class="panel intake-followup"><h2>AI가 작업 정보를 정리했어요</h2>${connectionStatus(intake,busy)}<p>설명과 사진에서 파악한 정보는 저장했어요. 부족한 부분만 팝업에서 물어볼게요.</p><div class="quick-nav"><button type="button" class="intake-back" data-quick="workspace-back" ${busy || intake.saving ? 'disabled' : ''}>뒤로 가기</button><button type="button" class="primary" data-quick="questions" ${busy ? 'disabled' : ''}>${state.questions.length ? 'AI 추가 질문 열기' : '정리한 내용 확인'}</button><button type="button" data-quick="next" ${busy ? 'disabled' : ''}>현재 정보로 결과 보기</button></div></section>`;
}
import {renderIntakeHistory} from './history-view.js';
