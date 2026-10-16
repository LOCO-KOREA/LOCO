/* Rendering for review navigation. All calculations remain in Python. */
export const LocoReview={
 escape(value){return String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));},
 nextInput(item,taskId){
  const e=this.escape;
  return `<button type="button" class="input-link" data-action="open-next-input" data-task="${taskId}" data-module="${e(item.module)}" data-slot="${item.slot_no??''}" data-criterion="${item.criterion_no??''}" data-path="${e(item.field_paths?.[0]||'')}">${e(item.message)}</button>`;
 },
 comparison(model,label){
  const e=this.escape,fmt=value=>value===null||value===undefined?'미입력 / 미계산':typeof value==='boolean'?(value?'예':'아니오'):typeof value==='object'?JSON.stringify(value):({YES:'예',NO:'아니오',UNKNOWN:'모름'}[value]||String(value));
  const status=value=>({APPLICABLE:'해당',NOT_APPLICABLE:'비해당',NEEDS_INPUT:'입력 필요',NEEDS_REVIEW:'검토 필요'}[value]||'미입력 / 미계산');
  return `<div class="comparison-detail"><h3>기준별 전후 결과</h3><div class="table-wrap"><table><thead><tr><th rowspan="2">기준</th><th colspan="3">개선 전 #${model.spec.before_analysis_id}</th><th colspan="3">개선 후 #${model.spec.after_analysis_id}</th></tr><tr><th>계산</th><th>조사자</th><th>유효 결과</th><th>계산</th><th>조사자</th><th>유효 결과</th></tr></thead><tbody>${model.criteria.map(row=>`<tr><th>${row.criterion_no}호</th>${['before_computed_status','before_investigator_status','before_status','after_computed_status','after_investigator_status','after_status'].map(key=>`<td>${status(row[key])}</td>`).join('')}</tr>`).join('')}</tbody></table></div><details class="comparison-inputs"><summary>입력 조건 차이 ${model.condition_changes.length}개 보기</summary><div class="table-wrap"><table><thead><tr><th>항목</th><th>개선 전</th><th>개선 후</th></tr></thead><tbody>${model.condition_changes.map(row=>`<tr><th>${e(label(row.field_path))}</th><td>${e(fmt(row.before))}</td><td>${e(fmt(row.after))}</td></tr>`).join('')||'<tr><td colspan="3">입력 조건 차이가 없습니다.</td></tr>'}</tbody></table></div></details>${model.spec.note?`<p>비교 메모: ${e(model.spec.note)}</p>`:''}</div>`;
 },
 evidence(ai){
  if(!ai?.content)return '';
  const e=this.escape,links=refs=>(refs||[]).map(ref=>{const match=/^C(\d+)-B(\d+)$/.exec(ref);return `<button type="button" class="basis-link" data-action="show-basis" data-ref="${e(ref)}" data-text-id="${e(ai.text_id)}">${match?`${Number(match[1])}호 계산 근거 ${Number(match[2])}`:'계산 근거 확인'}</button>`;}).join(' ');
  return `<details class="explanation-evidence"><summary>기준별 설명과 연결된 계산 근거</summary>${ai.content.criteria.map(item=>`<article><h3>${item.criterion_no}호</h3><p>${e(item.explanation)}</p>${links(item.basis_refs)}</article>`).join('')}<h3>현장 확인이 필요한 개선 선택지</h3>${ai.content.improvement_options.map(item=>`<article><p>${e(item.proposal)}</p>${links(item.basis_refs)}<small>현장 적용 가능성과 효과를 조사자가 확인해야 합니다.</small></article>`).join('')}</details>`;
 },
 basis(ai,analysis,ref){
  const match=/^C(\d{2})-B(\d{2})$/.exec(ref);if(!match)return null;
  const number=Number(match[1]),index=Number(match[2])-1;
  const summary=ai?.input_summary?.criteria?.find(x=>x.criterion_no===number);
  const value=summary?.basis?.find(x=>x.item_code===ref);if(!value)return null;
  const source=analysis?.judgment?.judgments?.find(x=>x.criterion_no===number)?.basis?.[index];
  return {number,value,path:source?.item_code||null};
 }
};
