import {userText} from '../user-language.js';
const esc=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const REASONS={UNIT_OR_NUMBER_NOT_GROUNDED:'원문의 숫자·단위·계산 근거를 확인하지 못했어요.',
 QUOTE_NOT_IN_TEXT:'해당 근거를 저장된 원문에서 찾지 못했어요.',STALE_QUOTE:'예전 설명이 최신 값을 덮지 않도록 유지했어요.',
 USER_VALUE_KEPT:'직접 확인한 값을 그대로 유지했어요.',CONFLICT:'앞서 저장한 값과 달라 확인이 필요해요.',
 BAD_VALUE:'입력 가능한 값의 형식이나 범위를 벗어났어요.',EMPTY_VALUE:'반영할 값이 없었어요.',
 UNKNOWN_TARGET:'지원하는 입력 항목에 연결하지 못했어요.',BAD_CONDITION:'작업 조건을 연결하지 못했어요.',
 EXPLICIT_FIELD_SELECTION_REQUIRED:'이 항목은 직접 선택해 확인해 주세요.',PHOTO_CONTEXT_CONFIRMATION_REQUIRED:'사진 선택이 바뀌었을 수 있어요. 보관한 설명이 현재 사진에 해당하는지 확인해 주세요.',FOLLOWUP_ONLY:'추가 질문 응답의 값은 입력으로 반영하지 않았어요.'};
const label=(state,target)=>state.contract.fields.find(field=>field.target===target)?.label||'입력 정보';
const proposal=(state,item)=>{if(!Object.hasOwn(item,'proposed_value'))return '';const saved=state.facts?.find(f=>f.target===item.target&&f.condition===(item.condition||state.contract.policy?.default_condition||'default'));return `<small>AI 제안: ${esc(userText(item.proposed_value??'모름'))} · 저장값: ${esc(userText(saved?.value??'미확정'))}</small>`;};
export function renderIntakeHistory(state,{details=true}={}){
 if(!state)return '';
 const rejected=state.diagnostics??state.dropped??[];
 const turns=state.history||[];
 const notice=(rejected.length?`<section class="intake-diagnostics" data-intake-diagnostics role="status"><h4>반영되지 않은 정보 ${rejected.length}개</h4><ul>${rejected.map(item=>`<li><strong>${esc(label(state,item.target))}</strong> · ${esc(REASONS[item.reason]||'입력 근거를 다시 확인해 주세요.')}${proposal(state,item)}${item.quote?`<small>근거: ${esc(item.quote)}</small>`:''}</li>`).join('')}</ul><p>원문은 보관했어요. 추가 설명이나 직접 수정으로 보완할 수 있어요.</p></section>`:'')+
  (turns.some(turn=>turn.requests?.some(request=>request.context?.omitted_message_ids?.length))?'<p class="intake-history-note">일부 이전 설명은 이번 정리 범위에 포함되지 않았어요. 원문은 보관돼요.</p>':'');
 if(!details)return notice;
 const changes=turns.flatMap(turn=>(turn.decisions||[]).filter(item=>item.outcome==='ACCEPTED'||item.outcome==='USER_SAVED'));
 if(!changes.length)return notice;
 const history=changes.reverse().map(item=>`<li><strong>${esc(label(state,item.target))}</strong><span>${item.outcome==='USER_SAVED'?'직접 입력':'설명·사진에서 반영'}</span>${item.quote?`<small>${esc(item.quote)}</small>`:''}</li>`).join('');
 return notice+`<details class="intake-history" data-intake-history><summary>반영된 입력 내역 보기</summary><ul>${history}</ul></details>`;
}
