// Read the stored explanation in sections without rewriting or summarizing its claims.
const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[c]));
const paragraphs = text => String(text ?? '').split(/\n+/).filter(line => line.trim()).map(line => `<p>${esc(line)}</p>`).join('');

function plainPreview(text) {
  const lines = String(text ?? '').trim().split(/\n+/).filter(line => line.trim());
  const first = lines[0] || '';
  const sentences = first.split(/(?<=[.!?。])\s+/);
  const lead = sentences.slice(0, 2).join(' ');
  const excerpt = lead.length > 280 ? lead.slice(0, 280) + '…' : lead;
  const more = lines.length > 1 || excerpt !== first;
  return `<div class="quick-explanation-summary"><h4>설명 미리보기</h4>${paragraphs(excerpt)}</div>${more ? `<details class="quick-explanation-details"><summary>전체 설명 보기</summary><div class="quick-explanation-full">${paragraphs(text)}</div></details>` : ''}`;
}

export function renderQuickExplanation(ai, text) {
  const content = ai.content;
  // Structured content belongs only to the generated text, never to an investigator's edits.
  if (text !== ai.generated_text || !content || typeof content.summary !== 'string') return plainPreview(text);
  const checks = (Array.isArray(content.check_items) ? content.check_items : []).filter(x => typeof x === 'string');
  const criteria = (Array.isArray(content.criteria) ? content.criteria : []).filter(x => Number.isInteger(x?.criterion_no) && x.criterion_no >= 1 && x.criterion_no <= 11 && typeof x.explanation === 'string');
  const options = (Array.isArray(content.improvement_options) ? content.improvement_options : []).filter(x => typeof x?.proposal === 'string');
  const checkList = items => `<ul>${items.map(x => `<li>${esc(x)}</li>`).join('')}</ul>`;
  return `<div class="quick-explanation-summary"><h4>핵심 요약</h4>${paragraphs(content.summary)}</div>
    ${checks.length ? `<div class="quick-explanation-checks"><h4>먼저 확인할 점</h4>${checkList(checks.slice(0, 3))}${checks.length > 3 ? `<details class="quick-explanation-details"><summary>확인할 점 ${checks.length - 3}개 더 보기</summary>${checkList(checks.slice(3))}</details>` : ''}</div>` : ''}
    ${criteria.length ? `<details class="quick-explanation-details"><summary>기준별 설명 ${criteria.length}개 보기</summary><div class="quick-explanation-criteria">${criteria.map(x => `<section><h4>${x.criterion_no}호</h4>${paragraphs(x.explanation)}</section>`).join('')}</div></details>` : ''}
    ${options.length ? `<details class="quick-explanation-details"><summary>개선 검토 선택지 ${options.length}개 보기</summary><ul>${options.map(x => `<li>${esc(x.proposal)}${x.needs_confirmation ? '<small>현장 확인 필요</small>' : ''}</li>`).join('')}</ul></details>` : ''}`;
}
