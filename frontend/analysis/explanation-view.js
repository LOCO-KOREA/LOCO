import {userText} from '../user-language.js';
import {inputPlaceholder} from '../input-placeholders.js';
import {localDrafts,readExplanationDraft} from '../drafts.js';

/* The selected analysis explains results; only an explicit investigator confirmation is exportable. */
export function createExplanationView(ctx){
 const {s, LocoReview, $, e, options, field, select, card}=ctx;

 function structuredPreview(ai){
  const content=ai?.content;
  if(!content)return `<p class="explanation-summary">${e(userText(ai?.generated_text||'아직 생성된 결과 설명이 없습니다.'))}</p>`;
  const posture=content.posture_explanations||[];
  return `<section class="explanation-reading"><h3>핵심 설명</h3><p class="explanation-summary">${e(userText(content.summary||''))}</p>${content.reba_comparison?`<p><strong>REBA 점수 설명</strong><br>${e(userText(content.reba_comparison))}</p>`:''}${content.check_items?.length?`<h3>확인할 항목</h3><ul>${content.check_items.map(item=>`<li>${e(userText(item))}</li>`).join('')}</ul>`:''}${posture.length?`<details><summary>사진별 자세 설명 ${posture.length}건</summary>${posture.map(item=>`<article><h4>${e(userText(item.photo_ref))}</h4><p>${e(userText(item.explanation))}</p></article>`).join('')}</details>`:''}${LocoReview.evidence(ai)}<details><summary>생성 원문 전체 보기</summary><div class="explanation-full-text">${e(userText(ai.generated_text||''))}</div></details></section>`;
 }

 function explanationCard(){
  const list=(s.analysis?.ai||[]).filter(item=>item.purpose===(s.aiPurpose||'TASK_EXPLANATION'));
  const ai=list.find(item=>item.text_id===s.aiTextId)||list.find(item=>item.is_active)||list.at(-1);
  if(ai)s.aiTextId=ai.text_id;
  const drafts=ctx.drafts||localDrafts(),draft=readExplanationDraft(s.analysis,ai,drafts);
  const current=Boolean(ai?.source_current&&s.analysis?.currentness==='CURRENT');
  const applied=Boolean(ai?.is_active&&ai?.applied_text);
  const source=ai?.applied_kind==='EDITED'?'조사자 수정':ai?.result==='FALLBACK'?'로컬 대체 설명':'AI 작성';
  const confirmation=applied?'확정본': '확정 전 · Excel에 포함되지 않음';
  const status=ai?`<div class="note ${current?'':'warn'}"><strong>${e(source)} · ${e(confirmation)}</strong><br>${current?'현재 분석과 일치합니다.':`이전 분석 결과입니다${ai.fallback_reason?' · '+e(userText(ai.fallback_reason)):''}.`} ${applied&&current?'확정 문장이 Excel에 포함됩니다.':'확정하고 현재 분석과 일치할 때만 Excel에 포함됩니다.'}</div>`:'';
  const reading=applied
   ? `<section class="applied-explanation"><h3>확정 문장</h3><div class="explanation-full-text">${e(userText(ai.applied_text))}</div>${ai.content?`<details><summary>AI 생성 근거 설명 보기</summary>${structuredPreview(ai)}</details>`:''}</section>`
   : structuredPreview(ai);
  const purpose=select('설명 종류','ai-purpose',s.aiPurpose||'TASK_EXPLANATION',[
   ['TASK_EXPLANATION','자세·REBA·조사 결과'],['IMPROVEMENT_ADVICE','개선 검토 선택지']
  ]);
  const history=list.length?`<details class="explanation-history"><summary>이전 결과 설명 ${list.length}건</summary><label>결과 설명 기록<select id="ai-choice" data-field="ai-choice">${options([['','기록 선택'],...list.map(item=>[item.text_id,`${userText(item.result)} · ${new Date(item.created_at).toLocaleString('ko-KR')}${item.is_active?' · 확정본':''}`])],ai?.text_id||'')}</select></label></details>`:'';
  const editor=ai?`<details class="explanation-editor" data-explanation-editor><summary>${applied?'확정 문장 수정':'문장 수정·확정'}</summary><p>문장을 저장한 뒤 ‘수정한 문장 확정’을 눌러야 결과와 Excel에 반영됩니다.</p>${draft?'<p class="input-guide" data-explanation-draft>저장하지 않은 수정문을 이 PC에서 복원했습니다.</p>':''}${drafts.error?`<p role="alert">${e(drafts.error)}</p>`:''}<textarea id="explanation-text" placeholder="${e(inputPlaceholder('', 'textarea', s.aiPurpose==='IMPROVEMENT_ADVICE'?'analysis.improvement':'analysis.explanation'))}">${e(draft?.text??ai.edited_text??userText(ai.generated_text??''))}</textarea><p data-explanation-draft-status role="alert" ${drafts.error?'':'hidden'}>${e(drafts.error)}</p><div class="toolbar"><button data-action="edit-explanation">수정문 저장</button><button data-action="apply-edited" ${ai.edited_text?'':'disabled'}>수정한 문장 확정</button></div></details>`:'';
  return `<p>AI는 수치와 사진 분석 요약을 읽기 쉬운 문장으로 설명합니다. 점수와 조사자 결론은 바꾸지 않습니다. 이름·사진 원본·파일 경로·자유 입력 근거는 전송하지 않습니다.</p><div class="explanation-form">${purpose}${history}${status}${reading}<div class="toolbar"><button data-action="generate-explanation">결과 설명 생성</button>${ai?`<button data-action="apply-generated" ${ai.is_active&&ai.applied_kind==='GENERATED'?'disabled':''}>AI 작성 문장 확정</button>`:''}</div>${editor}</div>`;
 }

 return {explanationCard};
}
