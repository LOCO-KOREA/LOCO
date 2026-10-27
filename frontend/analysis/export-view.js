/* Excel output keeps optional analysis choices and comparisons out of the primary action. */
export function createExportView(ctx){
 const {s, LocoReview, inputLabel, $, e, fmt, badge, field, select, card, empty, context}=ctx;

 function exportPage(){
  if(!s.survey)return empty('조사를 선택하세요');
  const ov=s.overview;
  const comparisonOptions=[['','분석 선택'],...s.comparisonPool.map(item=>[item.analysis_id,`#${item.analysis_id} · ${item.task_name} · 입력 r${item.input_revision}`])];
  const taskChoices=s.tasks.map(task=>`<label>${e(task.task_name)}<select data-export-task="${task.task_id}"><option value="">최신 분석 (기본)</option></select></label>`).join('');
  const comparisonList=(ov?.comparisons||[]).map(item=>`<div class="sheet"><strong>#${item.spec.before_analysis_id} → #${item.spec.after_analysis_id} · REBA 변화 ${fmt(item.reba_max_delta)}</strong><p>규칙 호환 ${item.rule_compatible?'예':'아니오'} · 사진 표본 호환 ${item.sampling_compatible?'예':'아니오'}</p>${item.notes.map(note=>`<div class="input-guide">${e(note)}</div>`).join('')}${LocoReview.comparison(item,inputLabel)}</div>`).join('');
  const statusTable=(ov?.tasks||[]).map(task=>`<tr><td>${e(task.task_name)}</td><td>${task.analysis_id??'분석 없음'}</td><td>${badge(task.currentness)}</td><td>${badge(task.review_status)}</td></tr>`).join('');

  return context()+card('Excel로 저장',`<p>실제로 입력하거나 분석한 값과 현재 선택한 결과만 담습니다. 빈 서식이나 입력하지 않은 항목 목록은 만들지 않습니다.</p><div class="toolbar section-actions"><label><input type="checkbox" id="include-representative" checked>대표 사진 이미지 포함</label></div><div class="toolbar section-actions"><button class="primary" data-action="export">저장 위치를 선택하고 Excel 저장</button></div><p class="input-guide">입력 부족·미분석·이전 결과가 있어도 저장할 수 있습니다. 선택한 결과와 실제 생성 시점은 저장 후 표시됩니다.</p>`)
   +`<details class="export-options" data-export-section="analysis"><summary>작업별 분석 선택 · 기본은 최신 결과</summary><p>다른 분석 기록을 선택하지 않으면 작업별 최신 분석을 사용합니다. 분석이 없는 작업은 입력한 작업 정보만 담습니다.</p><div id="export-choices" class="grid">${taskChoices}</div></details>`
   +`<details class="export-options" data-export-section="comparison"><summary>개선 전후 비교 선택</summary><p>같은 조사 안의 서로 다른 두 분석을 비교합니다. 점수 차이는 계산 규칙과 사진 표본이 비교 가능할 때만 표시합니다.</p><div class="grid">${select('개선 전 분석','comparison-before',s.comparisonBefore,comparisonOptions)}${select('개선 후 분석','comparison-after',s.comparisonAfter,comparisonOptions)}${field('비교 메모','comparison-note',s.comparisonNote)}</div>${comparisonList||'<p class="input-guide">두 분석을 고르면 비교 내용을 확인할 수 있습니다.</p>'}</details>`
   +`<details class="export-options"><summary>선택 결과 상태 보기</summary><div class="grid">${Object.entries(ov?.state||{}).filter(([key])=>['reviewed','review_current','has_incomplete','has_stale'].includes(key)).map(([key,value])=>`<div class="sheet"><strong>${{reviewed:'조사자 검토 기록',review_current:'검토 현재성',has_incomplete:'입력 또는 계산 미완료',has_stale:'이전 분석 포함'}[key]}</strong><p>${value?'있음':'없음'}</p></div>`).join('')}</div><div class="table-wrap"><table><thead><tr><th>작업</th><th>선택 분석</th><th>현재성</th><th>검토</th></tr></thead><tbody>${statusTable||'<tr><td colspan="4">등록된 작업이 없습니다.</td></tr>'}</tbody></table></div></details>`;
 }

 return {exportPage};
}
