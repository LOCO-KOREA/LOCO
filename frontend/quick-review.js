const esc=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const ANGLE={TRUNK_TILT_VERT:'몸통 기울기',NECK_TILT_VERT_PROXY:'목 기울기 참고값',NECK_FLEX_TRUNK_PROXY:'몸통 대비 목 기울기 참고값',UPPER_ARM_RAISE_VERT:'위팔 올림',UPPER_ARM_FLEX_TRUNK:'몸통 기준 위팔 굽힘',ELBOW_FLEX:'팔꿈치 굽힘',KNEE_FLEX:'무릎 굽힘',WRIST_FLEX_2D:'손목 굽힘·폄',ELBOW_FLEX_3D:'팔꿈치 굽힘',KNEE_FLEX_3D:'무릎 굽힘'};
const POINT={nose:'코',eye_inner:'눈 안쪽',eye:'눈',eye_outer:'눈 바깥',ear:'귀',mouth_left:'입 왼쪽',mouth_right:'입 오른쪽',shoulder:'어깨',elbow:'팔꿈치',wrist:'손목',pinky:'새끼손가락',index:'검지',thumb:'엄지',hip:'엉덩관절',knee:'무릎',ankle:'발목',heel:'뒤꿈치',foot_index:'발끝'};
const SIDE={LEFT:'왼쪽',RIGHT:'오른쪽',COMMON:'공통'};
const FIELD={trunk_base:'몸통 기본 자세',trunk_twisted:'몸통 비틀림',trunk_side_bent:'몸통 옆 기울임',neck_base:'목 기본 자세',neck_twisted:'목 비틀림',neck_side_bent:'목 옆 기울임',legs_support:'다리 지지',seated:'앉은 자세',knee_band:'무릎 굽힘',shock_force:'충격·급격한 힘',static_over_1min:'1분 초과 유지',small_repeat_over_4min:'작은 동작 반복',rapid_change_or_unstable:'급격한 변화·불안정',upper_arm_base:'위팔 기본 자세',arm_abducted_or_rotated:'팔 벌림·회전',shoulder_raised:'어깨 들림',arm_supported_or_gravity_assisted:'팔 지지·중력 보조',lower_arm_base:'아래팔 기본 자세',wrist_base:'손목 기본 자세',wrist_deviated_or_twisted:'손목 편위·비틀림',coupling:'손잡이·쥐기',effective_load_kg:'적용 하중',photo_id:'배정 사진'};
const REASON={INPUT_CONFLICT:'입력값을 다시 확인해 주세요',BOUNDARY_REVIEW:'점수 경계에 가까워 자세를 다시 확인해 주세요',CAPTURE_CONTEXT_UNCONFIRMED:'사진 방향·전신·통상 작업 여부를 확인해 주세요',MISSING_ANGLE:'필요한 각도를 측정하지 못했어요'};
const TAG={NECK_FORWARD_PROXY:'목 앞기울임 참고',TRUNK_FLEX:'몸통 앞굽힘',TRUNK_EXT:'몸통 뒤로 젖힘',UPPER_ARM_RAISE:'위팔 올림',HAND_ABOVE_HEAD:'머리 위 손',ELBOW_ABOVE_SHOULDER:'어깨 위 팔꿈치',ELBOW_BEHIND_TRUNK:'몸통 뒤 팔꿈치',NECK_TWIST:'목 비틀림',TRUNK_TWIST:'몸통 비틀림',SQUAT:'쪼그림',KNEEL:'무릎 접촉'};
const STATUS={VALID:'각도 측정 완료',INVALID:'측정 불가',ERROR:'처리 오류',PENDING:'처리 대기',CANCELED:'처리 취소',NOT_PROCESSED:'미처리',COMPLETE:'계산 완료',INCOMPLETE:'입력 또는 확인 필요',NOT_REQUESTED:'분석하지 않음',RUNNING:'분석 중',FAILED:'분석 실패',FINISHED:'처리 완료',PARTIAL:'일부 결과 확인 필요'};
const RISK={NEGLIGIBLE:'무시 가능',LOW:'낮음',MEDIUM:'보통',HIGH:'높음',VERY_HIGH:'매우 높음'};
const QUALITY={HIGH:'높음',MEDIUM:'보통',LOW:'낮음',MISSING:'측정 전'};
const POSTURE_CHOICE={trunk_base:{1:'똑바로',2:'20° 이내 굽힘',3:'20~60° 굽힘',4:'60° 초과 굽힘'},neck_base:{1:'20° 이내 숙임',2:'20° 초과 숙임','2_EXTENSION':'뒤로 젖힘'},upper_arm_base:{1:'몸 옆 20° 이내',2:'20~45°',3:'45~90°',4:'90° 초과'},lower_arm_base:{1:'60~100°',2:'60° 미만·100° 초과'},wrist_base:{1:'15° 이내',2:'15° 초과'},knee_band:{UNDER_30:'30° 미만',FROM_30_TO_60:'30~60°',OVER_60:'60° 초과'},coupling:{GOOD:'좋음',FAIR:'보통',POOR:'나쁨',UNACCEPTABLE:'매우 나쁨'}};
const VISION_VALUE={neck_base:{NECK_UP_TO_20:1,NECK_OVER_20:2,NECK_EXTENSION:'2_EXTENSION'},upper_arm_base:{UPPER_NEUTRAL:1,UPPER_EXTENSION:2,UPPER_20_45:2,UPPER_45_90:3,UPPER_OVER_90:4},lower_arm_base:{ELBOW_60_100:1,ELBOW_OUTSIDE_60_100:2},wrist_base:{WRIST_UP_TO_15:1,WRIST_OVER_15:2},coupling:{GOOD:'GOOD',FAIR:'FAIR',POOR:'POOR',UNACCEPTABLE:'UNACCEPTABLE'}};
const REBA_FIELDS=[['trunk','몸통'],['neck','목'],['legs','다리'],['table_a','표 A'],['load_score','하중 가산'],['score_a','A 점수'],['upper_arm','위팔'],['lower_arm','아래팔'],['wrist','손목'],['table_b','표 B'],['coupling_score','손잡이 가산'],['score_b','B 점수'],['table_c','표 C'],['activity_score','활동 가산'],['total','합계']];
const fmt=(value,digits=1)=>typeof value==='number'&&Number.isFinite(value)?Number(value.toFixed(digits)).toString():'—';
const cell=value=>value==null||value===''?'—':esc(value);
const missingName=value=>{const match=/^(common|left|right)\.(.+)$/.exec(String(value||''));if(match)return SIDE[match[1].toUpperCase()]+' · '+(FIELD[match[2]]||'자세 항목');if(value==='duplicate_photo_id')return '같은 사진이 여러 행에 배정됨';if(value==='observation.load_state')return '사진에서 본 하중 상태';return FIELD[value]||'확인할 자세 항목';};
const reasonName=value=>REASON[value]||'추가 확인 필요';
const table=(headers,rows,cls='')=>`<div class="quick-review-table-wrap"><table class="quick-table ${cls}"><thead><tr>${headers.map(x=>`<th>${esc(x)}</th>`).join('')}</tr></thead><tbody>${rows.length?rows.map(row=>`<tr>${row.map(x=>`<td>${x}</td>`).join('')}</tr>`).join(''):`<tr><td colspan="${headers.length}">결과가 없어요.</td></tr>`}</tbody></table></div>`;
const pointName=name=>{let value=String(name||'관절'),side='';for(const key of ['left_','right_'])if(value.startsWith(key)){side=key==='left_'?'왼쪽 ': '오른쪽 ';value=value.slice(key.length);break;}const match=Object.keys(POINT).sort((a,b)=>b.length-a.length).find(key=>value===key||value.startsWith(key+'_'));return esc(side+(POINT[match]||value));};
function pointsTable(points,space){if(!Array.isArray(points)||!points.length)return '';const world=space==='world';const keys=world?['x_m','y_m','z_m']:['x_px','y_px','z_normalized'];const labels=world?['X (m)','Y (m)','Z (m)']:['X (px)','Y (px)','깊이'];return `<details class="quick-review-technical"><summary>관절 좌표 전체 ${points.length}개 보기 · ${world?'3D 추정 좌표':'사진 픽셀 좌표'}</summary>${table(['관절',...labels,'신뢰도'],points.map(point=>[pointName(point.name),...keys.map(key=>fmt(point[key],3)),fmt(point.confidence,3)]))}</details>`;}
export function renderMeasurementQuality(quality,{compact=false}={}){
  if(!quality)return `<p class="quick-measurement-quality is-unknown">자세 측정 신뢰도 정보 없음</p>`;
  const measured=Number.isInteger(quality.measured_points)&&quality.measured_points>=0?quality.measured_points:null;
  const total=Number.isInteger(quality.total_points)&&quality.total_points>0?quality.total_points:null;
  const confidence=typeof quality.mean_confidence==='number'&&Number.isFinite(quality.mean_confidence)?`${Math.round(quality.mean_confidence*100)}%`:null;
  const level=QUALITY[quality.confidence_level]||'미확인';
  const className=String(quality.confidence_level||'unknown').toLowerCase();
  const count=measured!==null&&total!==null?`측정된 관절 ${measured}/${total}개`:'관절 측정 수 미확인';
  const tag=compact?'span':'div';
  return `<${tag} class="quick-measurement-quality ${compact?'compact':''}" aria-label="${esc(count)} · 측정 신뢰도 ${esc(level)}${confidence?` ${confidence}`:''}"><span>${esc(count)}</span><span class="quick-quality-badge ${className}">신뢰도 ${esc(level)}</span>${confidence?`<span>평균 ${esc(confidence)}</span>`:''}</${tag}>`;
}
function storedAnglePrecision(value){
  // Match Python round(value,1), including exact binary quarter-degree ties.
  if(Number.isInteger(value*4)&&!Number.isInteger(value*2)){
    const lower=Math.floor(value*10);return (lower%2===0?lower:lower+1)/10;
  }
  return Number(value.toFixed(1));
}
function worldAngleUsed(result,angle){
  const current=result?.current_score||result?.score_so_far||{};
  return current.kind!=='CONFIRMED'&&Number.isFinite(angle.value_deg)&&(angle.coordinate_space??'INFERRED_WORLD_3D')==='INFERRED_WORLD_3D'&&(current.measurement_refs||[]).some(item=>(item.angles||[]).some(ref=>ref.coordinate_space==='INFERRED_WORLD_3D'&&ref.used_for_reba===true&&ref.side===angle.side&&ref.angle_code===angle.angle_code&&Number.isFinite(ref.value_deg)&&(ref.value_deg===angle.value_deg||ref.value_deg===storedAnglePrecision(angle.value_deg))));
}
function angleTable(angles,{world=false,result=null}={}){const values=Array.isArray(angles)?angles:[];return table(['쪽','각도','결과','관절 신뢰도','설명'],values.map(a=>[cell(SIDE[a.side]||a.side),cell(ANGLE[a.angle_code]||a.label||a.angle_code),a.value_deg==null?'측정 불가':`${fmt(a.value_deg)}°`,a.min_confidence==null?'—':`${fmt(a.min_confidence*100)}%`,cell([a.diagnostic,world?`단안 사진의 3D 추정 · ${worldAngleUsed(result,a)?'현재 REBA 초안에 사용':'현재 REBA에 사용하지 않음'}`:''].filter(Boolean).join(' · '))]));}
function rebaTable(result){if(!result)return '<p class="quick-note">REBA를 계산하지 않았어요.</p>';const rows=['left','right'].map(side=>{const item=result[side]||{};return [side==='left'?'왼쪽':'오른쪽',...REBA_FIELDS.map(([key])=>cell(item[key])),cell(RISK[item.risk]||item.risk),cell((item.missing_fields||[]).map(missingName).join(', ')),cell((item.review_reasons||[]).map(reasonName).join(', '))];});return `${table(['쪽',...REBA_FIELDS.map(([,label])=>label),'위험도','필요한 입력','확인 사유'],rows)}<p class="quick-note">사진 결과 ${esc(STATUS[result.status]||result.status||'미계산')} · ${result.total==null?'양쪽 결과가 완성되지 않아 합계 없음':`높은 쪽 ${fmt(result.total,0)}점 · ${esc(RISK[result.risk]||result.risk||'')}`} · 적용 하중 ${result.effective_load_kg==null?'미확인':`${fmt(result.effective_load_kg,2)}kg`}</p>`;}
function candidatesTable(candidates){if(!Array.isArray(candidates)||!candidates.length)return '';return `<details class="quick-review-technical"><summary>MediaPipe 자세 범주 후보 ${candidates.length}개</summary>${table(['범위','항목','후보','근거 각도','최저 신뢰도','확인할 점'],candidates.map(item=>[cell(SIDE[item.scope]||item.scope),cell(FIELD[item.field]||'자세 항목'),cell(item.proposed_value),cell((item.angles||[]).map(a=>`${SIDE[a.side]||''} ${ANGLE[a.angle_code]||a.angle_code}: ${a.value_deg==null?'측정 불가':fmt(a.value_deg)+'°'}`).join(' · ')),item.min_confidence==null?'—':`${fmt(item.min_confidence*100)}%`,cell((item.review_reasons||[]).map(reasonName).join(', '))]))}</details>`;}
function ownedMeasurement(rows,slot){
  const candidates=rows.filter(item=>item&&item.slot_no===slot.slot_no),exact=candidates.filter(item=>item.photo_id===slot.photo_id);
  if(exact.length===1)return {row:exact[0],mismatch:false};
  if(!exact.length&&candidates.length===1&&candidates[0].photo_id==null)return {row:candidates[0],mismatch:false};
  return {row:null,mismatch:candidates.length>0};
}
function estimatedPhotoInputs(snapshot,slot){
  const session=snapshot.conditions?.intake_session||{},facts=Object.values(session.facts||{}),assigned=(snapshot.capture?.slots||[]).filter(item=>item.photo_id===slot.photo_id);
  if(snapshot.input_revision!==session.projected_revision||assigned.length!==1||assigned[0].slot_no!==slot.slot_no)return [];
  const owned=item=>{const owner=String(item.condition||'').startsWith('photo:')?Number(String(item.condition).slice(6)):item.photo_id;return owner===slot.photo_id&&(item.photo_id??owner)===owner&&item.photo_active!==false;};
  const parts=item=>/^manual\.(COMMON|LEFT|RIGHT)\.(\w+)$/.exec(item.target||'');
  const blocked=new Set((snapshot.manual||[]).filter(item=>item.slot_no===slot.slot_no&&item.photo_id===slot.photo_id&&item.value!=null&&item.value!=='UNKNOWN').map(item=>`${item.scope}.${item.field}`));
  for(const item of facts){const p=parts(item);if(p&&!item.alias_of&&owned(item)&&['USER','AI','SAVED'].includes(item.source)&&['KNOWN','UNKNOWN','CONFLICT'].includes(item.state))blocked.add(`${p[1]}.${p[2]}`);}
  const groups=new Map();
  for(const item of facts){
    const p=parts(item);if(!p||item.alias_of||!owned(item)||item.state!=='ESTIMATED'||item.reask||!['POSE','MOVENET','VISION'].includes(item.source))continue;
    const scope=p[1],field=p[2],key=`${scope}.${field}`;
    if(blocked.has(key)||!POSTURE_CHOICE[field]||!Object.hasOwn(POSTURE_CHOICE[field],item.value))continue;
    const proof=item.source==='VISION'?item.vision_proof||{}:item.photo_proof||{};
    const valid=item.source==='VISION'?proof.scope===scope&&proof.field===field&&proof.status==='OBSERVED'&&VISION_VALUE[field]?.[proof.value]===item.value&&Number.isFinite(proof.confidence)&&proof.confidence>=.5&&proof.confidence<=1:
      proof.scope===scope&&proof.field===field&&proof.photo_id===slot.photo_id&&(proof.angles||[]).some(angle=>Number.isFinite(angle.value_deg));
    if(!valid)continue;
    if(!groups.has(key))groups.set(key,[]);groups.get(key).push({...item,scope,field});
  }
  return [...groups.values()].filter(items=>items.length===1).map(items=>items[0]);
}
function estimatedInputsTable(snapshot,slot,result){
  const items=estimatedPhotoInputs(snapshot,slot);if(!items.length)return '';
  const current=result?.current_score||result?.score_so_far||{},refs=current.kind==='CONFIRMED'?[]:current.measurement_refs||[];
  return `<h4>사진에서 추정한 자세 · 사람 확인 전</h4>${table(['범위','항목','추정 범주','출처','사진 관찰 확신도','현재 점수 사용','근거'],items.map(item=>{
    const method=item.measurement_method||item.photo_proof?.measurement_method,used=refs.some(ref=>ref.scope===item.scope&&ref.field===item.field&&ref.value===item.value&&ref.measurement_method===method);
    return [cell(SIDE[item.scope]),cell(FIELD[item.field]),cell(POSTURE_CHOICE[item.field][item.value]),item.source==='VISION'?'AI 사진 추정':'사진 자동 측정 추정',Number.isFinite(item.vision_confidence)?`${fmt(item.vision_confidence*100)}%`:'—',used?'현재 REBA 초안에 사용':'현재 REBA에 사용하지 않음',cell(item.vision_proof?.evidence||item.measurement_reason||item.quote)];
  }))}`;
}
export function renderPostureReview(analysis){
  const snapshot=analysis?.snapshot||{},slots=(snapshot.capture?.slots||[]).filter(slot=>(slot.analysis_target??snapshot.schema_version==='1.3')&&slot.photo_id!=null),pose=analysis?.pose||{},reba=analysis?.reba||{},poses=pose.slots||[],rebAs=reba.slots||[],state=analysis?.module_states||{};
  const summary=reba.summary||{},targetCount=pose.total_slot_count??slots.length,valid=pose.valid_count,complete=summary.complete_count;
  const header=`<p class="quick-note">사진별 각도와 좌우 REBA 구성을 확인할 수 있어요. 3D 추정각은 현재 점수에 사용했는지 함께 표시해요. 사람이 확인한 자세와 사진 추정값을 구분해 주세요.</p><p class="quick-posture-summary">분석 사진 ${esc(targetCount)}장 · 자세 측정 ${valid==null?'미확인':`${esc(valid)}/${esc(targetCount)}`} · REBA 계산 ${complete==null?'미확인':`${esc(complete)}/${esc(summary.total_slot_count??targetCount)}`}</p>`;
  if(!slots.length)return `<section id="quick-posture-review" tabindex="-1" class="panel quick-posture-review" data-posture-review><h3>MediaPipe 자세·REBA 결과</h3>${header}<p class="quick-note">분석대상 사진이 없어 사진별 자세 결과가 없어요. 자세 분석 상태: ${esc(STATUS[state.pose]||state.pose||'결과 없음')}.</p></section>`;
  const qualityRows=analysis?.measurement_quality?.slots||[];
  const cards=slots.map((slot,index)=>{const poseResult=ownedMeasurement(poses,slot),rebaResult=ownedMeasurement(rebAs,slot),qualityResult=ownedMeasurement(qualityRows,slot),p=poseResult.row,r=rebaResult.row,quality=qualityResult.row,label=slot.label||`사진 ${index+1}`,engine=p?.engine||{};const diag=(p?.diagnostics||[]).map(d=>d.message).filter(Boolean);if(poseResult.mismatch||rebaResult.mismatch||qualityResult.mismatch)diag.push('사진 연결 정보가 맞지 않아 해당 측정값을 표시하지 않았어요.');const name=engine.name||engine.model_id||engine.provider;const details=table(['자세 모델','관절 수','상태'],[[cell(name?`${name}${engine.version?` · ${engine.version}`:''}`:'자세 모델 정보 없음'),p?.points?.length?`${esc(p.points.length)}개 관절`: '관절 정보 없음',cell(STATUS[p?.status]||p?.status||STATUS[state.pose]||state.pose||'결과 없음')]]);
    const current=!rebaResult.mismatch&&summary.current_score?.slot_no===slot.slot_no?summary.current_score:null;
    const photoScore=r?.current_score||current||(r?.score_so_far?{...r.score_so_far,kind:'WITH_ASSUMPTIONS'}:r?.total!=null?{total:r.total,risk:r.risk,kind:'CONFIRMED'}:null);
    const scoreText=photoScore?`REBA ${esc(photoScore.total)}점 · ${esc(RISK[photoScore.risk]||photoScore.risk||'')}${photoScore.kind==='ASSUMED_REFERENCE'?' · 참고값':photoScore.kind==='WITH_ASSUMPTIONS'?' · 가정 포함':''}`:'REBA 점수 미산출';
    return `<details id="quick-posture-photo-${index+1}" tabindex="-1" class="quick-review-photo"><summary><span class="quick-photo-review-title">${esc(label)} · ${esc(STATUS[p?.status]||p?.status||'측정 결과 확인')}</span><strong class="quick-photo-review-score">${scoreText}</strong>${renderMeasurementQuality(quality,{compact:true})}<span class="quick-photo-review-more">자세·REBA 근거 보기</span></summary>${photoScore?.assumption?`<p class="quick-note">${esc(photoScore.assumption)}</p>`:''}${details}${diag.length?`<p class="quick-warn">${diag.map(esc).join(' · ')}</p>`:''}${estimatedInputsTable(snapshot,slot,r)}<h4>사진에서 측정한 2D 각도</h4>${angleTable(p?.angles)}<h4>3D 분절각 추정값</h4>${angleTable(p?.world_angles,{world:true,result:r})}<h4>좌우 REBA 전체 구성</h4>${rebaTable(r)}${candidatesTable(r?.candidates)}${pointsTable(p?.points,'image')}${pointsTable(p?.world_points,'world')}</details>`;
  }).join('');
  return `<section id="quick-posture-review" tabindex="-1" class="panel quick-posture-review" data-posture-review><h3>사진별 자세·REBA 상세</h3>${header}${cards}${(analysis.tags||[]).some(item=>item.observed_count)?`<details class="quick-review-technical"><summary>자세 기술태그 관찰</summary><ul>${(analysis.tags||[]).filter(item=>item.observed_count).map(item=>`<li>${esc(TAG[item.tag]||'자세 표시')} · ${esc(item.yes_count)} / ${esc(item.observed_count)}장 관찰</li>`).join('')}</ul><p class="quick-note">전체 분석 사진 표본의 관찰이며 하루 노출시간이 아니에요.</p></details>`:''}<details class="quick-review-technical"><summary>측정 신뢰도 기준 보기</summary><p>측정 관절 수는 MediaPipe 전체 33개 또는 MoveNet 전체 17개 중 신뢰도 기준을 통과한 수예요. 신뢰도 등급은 측정 범위와 평균 신뢰도를 함께 반영해요. 낮은 점수나 측정 없음은 실제 자세가 없다는 뜻이 아니에요.</p></details></section>`;
}
