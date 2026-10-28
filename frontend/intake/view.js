import {renderPhotoVision,photoVisionForTask} from './photo-vision.js';
import {renderIntakeHistory} from './history-view.js';
const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
export function connectionStatus(intake, busy=false) {
  // Model identifiers, reasoning options and provider errors are internal details.
  if (!busy && intake.state?.ai?.status !== 'ERROR') return '';
  const status = busy ? 'REQUESTING' : 'ERROR';
  const label = busy ? '답변을 정리하고 있어요' : '답변 정리를 완료하지 못했어요. 선택지로 답하거나 다시 시도해 주세요.';
  return `<p class="intake-ai-status" data-ai-state="${status}" role="status">${label}</p>`;
}
export function renderSummary(intake) {
  const state = intake.state; if (!state) return '';
  const vision=state.photo_vision??photoVisionForTask(state.task,state.contract);
  return `<section class="intake-summary">${renderPhotoVision(vision,state.contract)}${renderIntakeHistory(state)}<p class="intake-save" role="status">${esc(intake.saveError?'입력을 저장하지 못했어요. 입력한 내용은 유지되니 다시 시도해 주세요.':intake.saveStatus?.()||(intake.saving?'입력을 저장하고 있어요…':'입력과 출처를 이 작업에 저장했어요.'))}</p></section>`;
}
export function renderQuestions(intake, busy) {
  const state = intake.state; if (!state) return '';
  return `<section class="panel intake-followup"><h2>AI가 작업 정보를 정리했어요</h2>${connectionStatus(intake,busy)}<p>설명과 사진에서 파악한 정보는 저장했어요. 부족한 부분만 팝업에서 물어볼게요.</p><div class="quick-nav"><button type="button" class="intake-back" data-quick="workspace-back" ${busy || intake.saving ? 'disabled' : ''}>← 뒤로 가기</button><button type="button" data-quick="questions" ${busy ? 'disabled' : ''}>${state.questions.length ? 'AI 추가 질문 열기' : '정리한 내용 확인'}</button><button type="button" class="primary" data-quick="next" ${busy ? 'disabled' : ''}>현재 정보로 결과 보기</button></div></section>`;
}
