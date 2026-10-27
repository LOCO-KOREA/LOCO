/* Investigator review stays separate from computed judgments and AI explanations. */
export function createCriteriaView(ctx){
 const {s, criterionTitles, inputLabel, reasonText, basisText, $, e, badge, field, card, empty, context}=ctx;
 const historyPicker=(...args)=>ctx.historyPicker(...args);
 const investigatorLabel=status=>status==='APPLICABLE'?'해당':status==='NOT_APPLICABLE'?'비해당':'결론 미입력';

 function criterionCard(number, judgment){
  const j=judgment;
  const conclusion=investigatorLabel(j?.investigator?.status);
  const missing=j?.missing_fields||[], reasons=j?.review_reasons||[], basis=j?.basis||[];
  const details=missing.length||reasons.length||basis.length
   ? `<details class="criterion-details"><summary>계산 근거와 확인할 내용 보기</summary>${missing.length?`<h4>입력이 필요한 항목</h4><ul>${missing.map(path=>`<li>${e(inputLabel(path))}</li>`).join('')}</ul>`:''}${reasons.length?`<h4>추가 확인</h4><ul>${reasons.map(reason=>`<li>${e(reasonText(reason))}</li>`).join('')}</ul>`:''}${basis.length?`<h4>계산에 사용한 값</h4><ul>${basis.map(item=>`<li>${e(basisText(item))}</li>`).join('')}</ul>`:''}</details>`
   : '<p class="input-guide">표시할 계산 근거가 없습니다.</p>';
  return `<article class="criterion-review-card"><div class="criterion-review-heading"><div><h3>${number}호 · ${e(criterionTitles[number-1])}</h3><div class="criterion-review-status"><span>앱 계산</span>${badge(j?.computed_status)}<span>조사자 결론</span><strong>${e(conclusion)}</strong><span>현재 표시</span>${badge(j?.effective_status)}</div></div><button class="small" data-action="conclusion" data-number="${number}">${j?.investigator?.status?'결론 수정':'결론 입력'}</button></div>${j?.investigator?.reason?`<p class="criterion-review-reason">조사자 사유: ${e(j.investigator.reason)}</p>`:''}${details}</article>`;
 }

 function criteriaPage(){
  if(!s.bundle)return empty('작업을 선택하세요');
  const a=s.analysis, judgments=a?.judgment?.judgments||[];
  const review=s.survey?.review||{};
  const history=(review.history||[]).map(mark=>`<article class="review-history-item"><p>${e(mark.reviewer||'검토자 미기록')} · ${e(mark.reviewed_at||'시각 미기록')} · 분석 ${(mark.reviewed_analysis_ids||[]).join(', ')}</p><p>${e(mark.note||'')} · ${e({TASK_INPUT_CHANGED:'작업 입력 변경',METADATA_CHANGED:'조사 정보 변경',CONCLUSION_CHANGED:'조사자 결론 변경',ANALYSIS_SETTINGS_CHANGED:'분석 설정 변경',REVIEW_CHANGED:'검토 변경'}[mark.reason]||mark.reason)}</p></article>`).join('');
  return context()
   + card('11개 기준 검토', `<p>앱 계산은 초안이고 조사자 결론은 별도로 기록됩니다. 입력 부족과 추가 확인 내용은 결론을 저장해도 유지됩니다.</p><div class="criterion-review-list">${Array.from({length:11},(_,i)=>criterionCard(i+1,judgments.find(j=>j.criterion_no===i+1))).join('')}</div>`)
   + `<details class="analysis-tools"><summary>분석 이력과 초안 재계산</summary>${historyPicker()}<button data-action="calculate-criteria">현재 입력으로 초안 다시 계산</button></details>`
   + card('결과 설명', ctx.explanationCard())
   + card('조사 전체 검토', `<p>이 표시는 선택한 분석과 조사 정보를 확인했다는 기록입니다. 계산 완성이나 법적 승인과는 별개입니다.</p><div class="grid">${field('검토자','review-reviewer',review.reviewer||s.survey?.investigator||'')}${field('검토 메모','review-note',review.note||'')}</div><details><summary>이전 검토 기록 ${((review.history)||[]).length}건</summary>${history||'<p>이전 검토 기록이 없습니다.</p>'}</details><div class="toolbar section-actions"><button data-action="review-on">선택한 결과 검토 완료 표시</button><button data-action="review-off">검토 표시 해제</button><button class="primary" data-page="S08">Excel 출력으로</button></div>`);
 }

 return {criteriaPage};
}
