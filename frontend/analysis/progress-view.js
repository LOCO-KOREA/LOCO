/* Analysis progress stays readable; per-photo diagnostics are available on demand. */
export function createProgressView(ctx){
 const {s, e, badge, card, empty, context}=ctx;
 const moduleNames={pose:'사진 자세',tags:'자세 태그',reba:'REBA',judgment:'11개 기준'};

 function progressPage(){
  if(!s.bundle)return empty('작업을 선택하세요');
  const analysis=s.analysis;
  if(!analysis)return context()+empty('아직 분석 결과가 없습니다','<button class="primary" data-action="start-analysis">분석 시작</button>');
  const slots=analysis.pose?.slots||[];
  const total=analysis.pose?.total_slot_count??slots.length;
  const processed=slots.filter(item=>item.status!=='PENDING').length;
  const percent=total?Math.min(100,processed/total*100):0;
  const rowDiagnostics=slots.filter(item=>(item.diagnostics||[]).length);
  const modules=Object.entries(analysis.module_states||{}).map(([key,value])=>`<li><span>${e(moduleNames[key]||key)}</span> ${badge(value)}</li>`).join('');
  const rows=slots.map(item=>{
   const slot=analysis.snapshot.capture.slots.find(value=>value.slot_no===item.slot_no);
   return `<tr><td>${e(slot?.label||`사진 ${item.slot_no}`)}</td><td>${badge(item.status)}</td><td>${(item.diagnostics||[]).map(diagnostic=>e(diagnostic.message)).join('<br>')||'추가 안내 없음'}</td></tr>`;
  }).join('');
  return context()+card('분석 진행',`<div class="toolbar">${badge(analysis.status)} ${badge(analysis.currentness)}<span class="input-guide">분석 #${analysis.analysis_id}</span></div><div class="progress-track" role="progressbar" aria-label="분석대상 사진 처리" aria-valuemin="0" aria-valuemax="${total}" aria-valuenow="${processed}"><div style="width:${percent}%"></div></div><h3>${processed} / ${total}장 처리</h3><p>사진 처리 상태와 REBA·기준 계산 상태는 다를 수 있습니다.</p><div class="toolbar section-actions"><button data-action="cancel-analysis" ${analysis.status==='RUNNING'?'':'disabled'}>분석 취소 요청</button><button class="primary" data-page="S06">사진 자세·REBA 결과 보기</button></div><details class="progress-details"><summary>요청한 분석 항목 상태 보기</summary><ul class="progress-module-list">${modules||'<li>요청한 분석 항목이 없습니다.</li>'}</ul></details>`)
   +`<details class="progress-details"><summary>사진별 상태와 진단 ${rowDiagnostics.length?`· 안내 ${rowDiagnostics.length}건`:''}</summary><div class="table-wrap"><table><thead><tr><th>사진</th><th>상태</th><th>안내</th></tr></thead><tbody>${rows||`<tr><td colspan="3">${total?'자세 분석을 요청하지 않았습니다.':'분석대상 사진이 없습니다.'}</td></tr>`}</tbody></table></div></details>`;
 }

 return {progressPage};
}
