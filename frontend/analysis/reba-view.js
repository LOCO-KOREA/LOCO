/* Photo posture, REBA score and investigator-entered observations. */
export function createRebaView(ctx){
 const {s, angleNames, tagNames, sideNames, statusNames, manualLabels, commonFields, armFields, reasonText, candidateValueText, manualOptions, $, e, fmt, badge, options, field, select, card, empty, metric, context}=ctx;

 function historyPicker(){
  const label=a=>{
   const modelError=a.pose?.slots?.some(p=>p.diagnostics?.some(d=>d.code==='MODEL_ERROR'));
   return modelError?'사진 분석 모델 연결 오류':!a.pose?'사진 분석 미요청':`유효한 사진 ${a.pose.valid_count}/${a.pose.total_slot_count??a.pose.slots?.length??0}`;
  };
  return `<div><div class="toolbar"><label for="history-choice">저장된 분석 ${s.history.length}개</label><select id="history-choice">${options([['','분석 선택'],...s.history.map(a=>[a.analysis_id,`#${a.analysis_id} · ${statusNames[a.currentness]||a.currentness} · ${label(a)}`])],s.analysis?.analysis_id)}</select>${s.analysis?badge(s.analysis.currentness):''}</div><details><summary>이전 분석 기록 보기</summary><div class="table-wrap"><table><thead><tr><th>분석</th><th>입력 상태</th><th>현재성</th><th>사진 처리</th><th></th></tr></thead><tbody>${s.history.map(a=>`<tr><td>#${a.analysis_id}</td><td>${e(a.input_revision)}</td><td>${badge(a.currentness)}</td><td>${e(label(a))}</td><td><button class="small" data-action="view-history" data-id="${a.analysis_id}">열기</button></td></tr>`).join('')}</tbody></table></div></details></div>`;
 }

 function currentScoreCard(analysis){
  const summary=analysis?.reba?.summary;
  const score=summary?.current_score||(summary?.score_so_far?{...summary.score_so_far,kind:'WITH_ASSUMPTIONS'}:null);
  if(!score)return '';
  const details=score.kind!=='CONFIRMED'
   ? (summary?.score_so_far?.slot_no===score.slot_no?summary.score_so_far:null)||(analysis?.reba?.slots||[]).find(x=>x.slot_no===score.slot_no)?.score_so_far||score
   : null;
  const quality=(analysis?.measurement_quality?.slots||[]).find(item=>item.slot_no===score.slot_no);
  const riskName={NEGLIGIBLE:'무시 가능',LOW:'낮음',MEDIUM:'보통',HIGH:'높음',VERY_HIGH:'매우 높음'}[score.risk]||'위험도 미확인';
  const confidenceName={HIGH:'높음',MEDIUM:'보통',LOW:'낮음',MISSING:'측정값 없음'}[quality?.confidence_level]||'미확인';
  const assumedCount=details?.assumed_count??details?.assumed?.length??score.assumed?.length;
  const photoCount=details?.unconfirmed_photo_count??details?.unconfirmed_photo?.length;
  const assumed=score.kind!=='CONFIRMED';
  const label=score.kind==='ASSUMED_REFERENCE'?'참고값 · 자세 측정값 없음':assumed?'확정 전 · 일부 값을 가정':'완성 사진 기준';
  const caution=assumed
   ? `<p>${score.kind==='ASSUMED_REFERENCE'?'사용 가능한 자세 측정값이 없어 기준 자세를 가정한 참고 점수입니다.':'확정 점수가 아니며 실제 점수는 더 높을 수 있습니다.'}${Number.isFinite(assumedCount)&&assumedCount>0?` 가정한 항목 ${assumedCount}개.`:''}${photoCount?` 사진에서 읽었지만 확인하지 않은 값 ${photoCount}개가 포함됐습니다.`:''}${score.assumption?` ${e(score.assumption)}`:''}</p>`
   : `<p>완성 사진 ${score.slot_no??'—'}번 기준입니다. 다른 분석대상 사진이 미완성이면 전체 최대 점수는 아직 달라질 수 있습니다.</p>`;
  const measurement=quality?`<p>현재 점수 사진의 측정 랜드마크 ${quality.measured_points}/${quality.total_points}개 · 신뢰도 ${e(confidenceName)}${Number.isFinite(quality.mean_confidence)?` (${quality.mean_confidence.toFixed(2)})`:''}</p>`:'';
  const title=analysis?.currentness==='STALE'?'선택한 과거 분석의 REBA 점수':'REBA 현재 점수';
  return card(title,`<div class="current-score"><strong>${score.total}점</strong><span>${e(riskName)} · ${e(label)}</span></div>${measurement}${caution}`);
 }

 function rebaPage(){
  if(!s.bundle)return empty('작업을 선택하세요');
  const a=s.analysis,summary=a?.reba?.summary,slots=a?.snapshot.capture.slots||s.bundle.task.capture.slots;
  const targets=slots.filter(x=>(x.analysis_target??a?.snapshot.schema_version==='1.3')&&x.photo_id!==null).length;
  const targetRows=slots.filter(slot=>(slot.analysis_target??a?.snapshot.schema_version==='1.3')&&slot.photo_id!==null);
  const excludedRows=slots.filter(slot=>slot.photo_id!==null&&!(slot.analysis_target??a?.snapshot.schema_version==='1.3'));
  const result=a?.reba?.slots?.find(x=>x.slot_no===s.slot);
  const pose=a?.pose?.slots?.find(x=>x.slot_no===s.slot);
  const selected=s.bundle.task.capture.slots.find(x=>x.slot_no===s.slot);
  const metadata=`대상 사진 ${summary?.total_slot_count??targets}장 · 완성 REBA ${summary?.complete_count??0}장 · 계산 가능한 사진 중 최대 ${fmt(summary?.available_max)}점`;
  const manual=s.bundle.task.manual||[];
  const groups=[['COMMON','공통 관찰',commonFields],['LEFT','왼쪽 팔 관찰',armFields],['RIGHT','오른쪽 팔 관찰',armFields]];
  return context()+card('분석 선택',historyPicker())
   +currentScoreCard(a)
   +`<div class="metrics">${metric('유효한 사진 자세',a?.pose?.valid_count,`/ ${a?.pose?.total_slot_count??targets}`)}${metric('완성 REBA',summary?.complete_count,`/ ${summary?.total_slot_count??targets}`)}${metric('계산 가능한 사진 중 최대',summary?.available_max,'점')}</div>`
   +`<details class="analysis-details"><summary>분석 범위와 모델 정보</summary><p>${e(metadata)} · 전체 대상 최대 ${fmt(summary?.full_max)}점 · 대표 사진 ${summary?.representative_slot_no??'없음'} · 모델 ${e(a?.snapshot.settings.pose_model.version??'미실행')}</p><p>목 프록시는 참고값이며 목 REBA 범주를 자동 결정하지 않습니다.</p></details>`
   +card('분석대상 사진별 REBA 결과',`<div class="table-wrap reba-results"><table><thead><tr><th>사진</th><th>자세 분석</th><th>측정 랜드마크</th><th>왼쪽</th><th>오른쪽</th><th>REBA 점수</th><th>확인할 항목</th><th></th></tr></thead><tbody>${targetRows.map(slot=>rebaTableRow(slot,a)).join('')||'<tr><td colspan="8">분석대상 사진이 없습니다. 사진 화면에서 분석할 사진을 선택하세요.</td></tr>'}</tbody></table></div>${excludedRows.length?`<details class="excluded-photo-list"><summary>분석대상에서 제외한 사진 ${excludedRows.length}장</summary><ul>${excludedRows.map(slot=>`<li>${e(slot.label||`사진 ${slot.slot_no}`)} · 분석대상 아님 · REBA 미계산</li>`).join('')}</ul></details>`:''}`)
   +`<div class="split">${card(`선택 사진 · ${s.slot}번`, `<div class="photo-view"><canvas id="pose-canvas"></canvas><p id="photo-message">사진을 불러오는 중입니다.</p></div><div class="detail">${e(poseDiagnosticText(pose))}</div><details><summary>사진에서 읽은 각도 보기</summary><pre>${e(pose?.angles?.map(x=>`${sideNames[x.side]||'측면'} · ${angleNames[x.angle_code]||'각도'}: ${x.value_deg===null?'미확인':x.value_deg.toFixed(2)+'°'}`).join('\n')||'각도 결과 없음')}</pre></details>`)}${card('사진에서 읽은 자세 후보',result?`<details class="candidate-details"><summary>확인할 자동 후보 ${result.candidates.length}개</summary>${result.candidates.map(c=>`<div class="sheet candidate-row"><label><input type="checkbox" data-auto-candidate="${c.scope}.${c.field}" ${c.proposed_value===null?'disabled':''}> ${e(sideNames[c.scope]||'공통')} · ${e(manualLabels[c.field])}</label><p>후보 ${e(candidateValueText(c))} · 각도 ${e(c.angles.map(x=>x.value_deg===null?'미확인':x.value_deg.toFixed(1)+'°').join(' / ')||'없음')} · 신뢰도 ${c.min_confidence?.toFixed(2)??'없음'}<br>${e(c.review_reasons.map(reasonText).join(', '))}</p></div>`).join('')}<div class="toolbar section-actions"><button data-action="apply-candidates">체크한 후보 적용</button></div></details>`:'분석 후 사진에서 읽은 후보를 표시합니다.')}</div>`
   +card(`현장 관찰값 수정 · 사진 ${s.slot}번`, `<p>확인한 항목만 체크하고 저장하세요. 자동으로 읽은 값은 직접 확인한 뒤 선택해야 반영됩니다.</p><div class="grid">${select('수정 범위','manual-range','single',[['single','이 사진만'],['selected','체크한 분석대상 사진']])}${select('관찰 출처','manual-source','DIRECT_OBSERVATION',[['DIRECT_OBSERVATION','직접 관찰'],['INTERVIEW','면담']])}${field('관찰 근거','manual-evidence','')}</div><div class="manual-groups">${groups.map(([scope,title,fields])=>{const saved=manual.filter(x=>x.slot_no===s.slot&&x.scope===scope&&x.value!==null).length;return `<details class="manual-group" ${saved?'open':''}><summary>${title} · 입력 ${saved}/${fields.length}</summary><div class="manual-grid">${fields.map(name=>{const value=manual.find(x=>x.slot_no===s.slot&&x.scope===scope&&x.field===name)?.value;return `<label><input type="checkbox" data-manual-use="${scope}.${name}">${e(manualLabels[name])}<select data-manual="${scope}.${name}">${options(manualOptions(name),value)}</select></label>`;}).join('')}</div></details>`;}).join('')}</div><div class="toolbar section-actions"><button class="primary" data-action="save-manual">선택한 값 저장 · REBA 다시 계산</button><button data-action="recalculate-tags">사진 자세 태그 다시 계산</button></div><details><summary>사진에서 확인한 태그 빈도</summary><pre>${e(a?.tags?.map(t=>`${tagNames[t.tag]||'자세 관찰'}: ${t.yes_count}/${t.observed_count} (수동 ${t.manual_observed_count}, 유효 포즈 ${t.valid_pose_count}/${t.total_slot_count})`).join('\n')||'미계산')}</pre><p>사진 표본의 관찰 빈도이며 하루 노출시간으로 바꾸지 않습니다.</p></details>`);
 }

 function rebaTableRow(slot,analysis){
  const result=analysis?.reba?.slots.find(r=>r.slot_no===slot.slot_no);
  const poseResult=analysis?.pose?.slots.find(p=>p.slot_no===slot.slot_no);
  const sourceSlot=analysis?.snapshot.capture.slots.find(x=>x.slot_no===slot.slot_no)||slot;
  const quality=(analysis?.measurement_quality?.slots||[]).find(item=>item.slot_no===slot.slot_no);
  const target=slot.analysis_target??analysis?.snapshot.schema_version==='1.3';
  const missing=result?.missing_fields||[];
  const name=path=>{
   if(path==='effective_load_kg')return '적용 하중 · 촬영 순간·지지 상태·중량';
   if(path==='photo_id')return '사진 배정';
   const [scope,field]=path.split('.');
   return ({common:'공통',left:'왼쪽',right:'오른쪽'}[scope]||scope)+' · '+(manualLabels[field]||field||path);
  };
  const current=result?.current_score?.total??result?.total??result?.score_so_far?.total;
  const scoreKind=result?.current_score?.kind||(result?.score_so_far?'WITH_ASSUMPTIONS':null);
  const score=!target?'<span class="input-guide">분석 제외</span>':current===null||current===undefined?'미계산':`<strong>${fmt(current)}점</strong><small>${scoreKind==='ASSUMED_REFERENCE'?'참고값':scoreKind==='WITH_ASSUMPTIONS'?'확정 전 · 가정 포함':'완성'}</small>`;
  const confidenceName={HIGH:'높음',MEDIUM:'보통',LOW:'낮음',MISSING:'측정값 없음'}[quality?.confidence_level]||'미확인';
  const measurement=quality?`${quality.measured_points}/${quality.total_points} · ${e(confidenceName)}${Number.isFinite(quality.mean_confidence)?` (${quality.mean_confidence.toFixed(2)})`:''}`:'미측정';
  const description=!target?'<span class="input-guide">분석 대상에서 제외됨</span>':missing.length?`<details><summary>${missing.length}개 확인 필요</summary><ul class="missing-fields">${missing.map(path=>`<li>${e(name(path))}</li>`).join('')}</ul></details>`:'<span class="input-guide">누락 없음</span>';
  return `<tr><td><input type="checkbox" data-select-slot="${slot.slot_no}" ${s.selectedSlots.has(slot.slot_no)?'checked':''}><button class="small" data-action="select-slot" data-slot="${slot.slot_no}">${e(sourceSlot.label||`사진 ${slot.slot_no}`)}</button></td><td>${target?badge(poseResult?.status):'분석 제외'}</td><td>${e(measurement)}</td><td>${fmt(result?.left?.total)}</td><td>${fmt(result?.right?.total)}</td><td>${score}</td><td>${description}</td><td><button class="small" data-action="representative" data-slot="${slot.slot_no}" ${result?.status==='COMPLETE'?'':'disabled'}>대표 사진으로 선택</button></td></tr>`;
 }

 function poseDiagnosticText(result){
  if(!result)return '자세 분석 전';
  if(result.diagnostics.length)return result.diagnostics.map(d=>d.message).join('\n');
  return result.status==='VALID'?'사진 자세 분석 완료 · 관절 신뢰도 기준 충족':statusNames[result.status]||result.status;
 }

 return {historyPicker,rebaPage,rebaTableRow,poseDiagnosticText,currentScoreCard};
}
