// Read the stored explanation in sections without rewriting or summarizing its claims.
import {userText} from './user-language.js';
const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[c]));
const paragraphs = text => String(text ?? '').split(/\n+/).filter(line => line.trim()).map(line => `<p>${esc(userText(line))}</p>`).join('');
function basisLinks(references) {
  const numbers = [...new Set((Array.isArray(references) ? references : []).map(ref => {
    const match = typeof ref === 'string' ? /^C(0[1-9]|1[01])-B\d+$/.exec(ref) : null;
    return match ? Number(match[1]) : null;
  }).filter(Number.isInteger))];
  return numbers.length ? `<div class="quick-explanation-evidence">${numbers.map(number => `<button type="button" data-evidence-criterion="${number}">계산 근거 ${number}호 확인</button>`).join('')}</div>` : '';
}

function plainPreview(text) {
  return `<div class="quick-explanation-summary"><h4>결과 설명</h4>${paragraphs(text)}</div>`;
}

export function renderQuickExplanation(ai, text) {
  const content = ai.content;
  // Structured content belongs only to the generated text, never to an investigator's edits.
  if (text !== ai.generated_text || !content || typeof content.summary !== 'string') {
    const preview = plainPreview(text);
    const rebaEvidence = text === ai.generated_text && ai.input_summary?.provisional_reba
      ? '<button type="button" data-evidence-posture="true">사진별 자세·REBA 결과 확인</button>' : '';
    return preview + rebaEvidence;
  }
  const checks = (Array.isArray(content.check_items) ? content.check_items : []).filter(x => typeof x === 'string');
  const criteria = (Array.isArray(content.criteria) ? content.criteria : []).filter(x => Number.isInteger(x?.criterion_no) && x.criterion_no >= 1 && x.criterion_no <= 11 && typeof x.explanation === 'string');
  const options = (Array.isArray(content.improvement_options) ? content.improvement_options : []).filter(x => typeof x?.proposal === 'string');
  const posture = (Array.isArray(content.posture_explanations) ? content.posture_explanations : []).filter(x => typeof x?.photo_ref === 'string' && typeof x?.explanation === 'string');
  const checkList = items => `<ul>${items.map(x => `<li>${esc(userText(x))}</li>`).join('')}</ul>`;
  const rebaComparison = typeof content.reba_comparison === 'string' ? content.reba_comparison.trim() : '';
  return `<div class="quick-explanation-summary"><h4>한눈에 보기</h4>${paragraphs(content.summary)}</div>
    ${rebaComparison ? `<details class="quick-explanation-details"><summary>첫 사진 점수와 현재 REBA 설명 보기</summary><section class="quick-explanation-reba">${paragraphs(rebaComparison)}<button type="button" data-evidence-posture="true">자세·REBA 근거 보기</button></section></details>` : ''}
    ${posture.length ? `<details class="quick-explanation-details"><summary>사진별 설명 ${posture.length}개 보기</summary><section class="quick-explanation-posture">${posture.map(item=>{const photo=/^사진 ([1-9]\d*)$/.exec(item.photo_ref);return `<article><strong>${esc(item.photo_ref)}</strong>${paragraphs(item.explanation)}${photo ? `<button type="button" data-evidence-photo="${Number(photo[1])}">이 사진의 자세·REBA 근거 보기</button>` : ''}</article>`;}).join('')}</section></details>` : ''}
    ${checks.length ? `<details class="quick-explanation-details"><summary>확인할 점 ${checks.length}개 보기</summary><section class="quick-explanation-checks">${checkList(checks)}<button type="button" data-evidence-criteria="true">기준별 계산 근거 보기</button><button type="button" data-evidence-posture="true">사진별 자세·REBA 근거 보기</button></section></details>` : ''}
    ${criteria.length ? `<details class="quick-explanation-details"><summary>기준별 설명 ${criteria.length}개 보기</summary><div class="quick-explanation-criteria">${criteria.map(x => `<section><h4>${x.criterion_no}호</h4>${paragraphs(x.explanation)}${basisLinks(x.basis_refs)}</section>`).join('')}</div></details>` : ''}
    ${options.length ? `<details class="quick-explanation-details"><summary>개선 검토 선택지 ${options.length}개 보기</summary><ul>${options.map(x => `<li>${esc(userText(x.proposal))}${x.needs_confirmation ? '<small>현장 확인 필요</small>' : ''}${basisLinks(x.basis_refs)}</li>`).join('')}</ul></details>` : ''}`;
}
