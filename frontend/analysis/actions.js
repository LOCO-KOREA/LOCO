/* actions; dependencies are composed by analysis-workspace.js. */
export function createActions(ctx){
 const {host, s, LocoReview, inputLabel, $, e, toast, api, field, select, number, text, modal, selectedIds, comparisonSpecs, $$}=ctx;
 const navigate=(...args)=>ctx.navigate(...args);
 const populateExportChoices=(...args)=>ctx.populateExportChoices(...args);
 const refreshTask=(...args)=>ctx.refreshTask(...args);
 const render=(...args)=>ctx.render(...args);
function editTargets(){const mode=$('#manual-range')?.value||'single';return mode==='selected'?[...s.selectedSlots]:[s.slot];}

function mergeManual(manual,value){const i=manual.findIndex(m=>m.slot_no===value.slot_no&&m.scope===value.scope&&m.field===value.field);if(i<0)manual.push(value);else manual[i]=value;}

async function saveManual(automatic){const t=s.bundle.task;const manual=structuredClone(t.manual);const targets=editTargets();let applied=0;let skipped=0;const source=text('manual-source');const note=text('manual-evidence');for(const no of targets){const slot=t.capture.slots.find(x=>x.slot_no===no);if(!slot?.photo_id||!slot.analysis_target){skipped++;continue;}if(automatic){const old=s.analysis?.snapshot;const consistent=old&&JSON.stringify(old.capture)===JSON.stringify(t.capture)&&JSON.stringify(old.settings.pose_model)===JSON.stringify(s.settings.analysis.pose_model)&&['worker_code','method_description','work_height_cm'].every(k=>old.conditions[k]===t.conditions[k]);if(!consistent){skipped++;continue;}for(const candidate of s.analysis.reba?.slots?.find(x=>x.slot_no===no)?.candidates||[]){if(candidate.proposed_value===null||!$$('[data-auto-candidate]:checked').some(input=>input.dataset.autoCandidate===candidate.scope+'.'+candidate.field))continue;mergeManual(manual,{slot_no:no,photo_id:slot.photo_id,scope:candidate.scope,field:candidate.field,value:candidate.proposed_value,source:'AUTO_ACCEPTED',evidence:{source:'OTHER',text:JSON.stringify({angles:candidate.angles,min_confidence:candidate.min_confidence}),observed_at:new Date().toISOString()}});applied++;}}else for(const input of $$('[data-manual-use]:checked')){const [scope,field]=input.dataset.manualUse.split('.');const raw=$(`[data-manual="${scope}.${field}"]`).value;const value=raw===''?null:field.endsWith('_base')?parseInt(raw,10):raw;mergeManual(manual,{slot_no:no,photo_id:slot.photo_id,scope,field,value,source,evidence:{source,text:[note,field==='neck_base'?((raw==='2_EXTENSION'?'뒤로 젖힘·신전':raw==='2'?'20° 초과 앞굽힘':raw==='1'?'중립·0~20° 앞굽힘':'관찰불가')):''].filter(Boolean).join(' / ')||null,observed_at:new Date().toISOString()}});applied++;}}if(!applied)return toast('저장할 값이 없습니다. 선택한 사진·필드를 확인하세요.');await api('set_manual_values',{task_id:t.task_id,manual});s.analysis=await api('recalculate_reba',{task_id:t.task_id});s.selectedAnalysis=s.analysis.analysis_id;await refreshTask();render();toast(`${applied}개 필드를 저장했습니다.${skipped?' 대상이 아니거나 빈 사진인 '+skipped+'개 행은 건너뛰었습니다.':''}`);}

const actions={
 'open-next-input':async button=>{
  const taskId=Number(button.dataset.task),module=button.dataset.module,path=button.dataset.path;
  if(module==='BURDEN'||path.startsWith('conditions.')||path.startsWith('analysis_scope.')||path.startsWith('criteria.')||path.startsWith('exposures.')){
   await host.onInput({taskId,path:path||`criteria.${button.dataset.criterion}.condition_present`});
  }else if(module==='POSE'||path.startsWith('capture.')||path.startsWith('photos.')||path==='effective_load_kg'||path==='photo_id'||path==='duplicate_photo_id'||path==='observation.load_state'){
   await host.onPhotoInput({taskId,path,slotNo:Number(button.dataset.slot)||null});
  }else if(module==='SURVEY')host.onLeave('S02');
  else if(module==='EXPLANATION'){await navigate('S06');$('.explanation-evidence')?.scrollIntoView({block:'center'});}
  else{if(s.bundle?.task.task_id!==taskId)s.bundle=await api('get_task',{task_id:taskId});await refreshTask();s.slot=Number(button.dataset.slot)||s.bundle.task.capture.slots[0]?.slot_no||1;await navigate('S06');const parts=path.split('.');const key=parts[0]?.toUpperCase()+'.'+parts[1];[...$$('[data-manual]')].find(n=>n.dataset.manual===key)?.focus();}
 },
 'show-basis':async button=>{
  const ai=s.analysis?.ai.find(x=>x.text_id===button.dataset.textId),basis=LocoReview.basis(ai,s.analysis,button.dataset.ref);
  if(!basis)return toast('저장된 설명에서 해당 근거를 찾을 수 없습니다.');
  modal(`${basis.number}호 · 설명 생성 당시 계산 근거`,`${ai.source_current?'':'<p class="note warn">이전 계산 요약에 대한 설명입니다.</p>'}<p>${basis.path?e(inputLabel(basis.path)):e(button.dataset.ref)}</p><table><tbody>${Object.entries(basis.value).map(([key,value])=>`<tr><th>${e({item_code:'참조',value:'입력값',unit:'단위',operator:'비교',threshold:'문턱'}[key]||key)}</th><td>${value===null?'미입력':e(value)}</td></tr>`).join('')}</tbody></table>${basis.path?`<button data-action="open-next-input" data-task="${s.bundle.task.task_id}" data-module="BURDEN" data-path="${e(basis.path)}">현재 입력 항목으로 이동</button>`:''}`);
 },
 'view-history':async b=>{s.selectedAnalysis=Number(b.dataset.id);s.analysis=s.history.find(a=>a.analysis_id===s.selectedAnalysis)||null;render();},
 'capture-guide':async()=>modal('사진·관찰 입력 안내',`<p>사진은 작업 특성에 따라 0장 이상 등록하고, 각 사진을 분석대상으로 쓸지 직접 선택합니다. 순서나 파일명만으로 작업 단계·하중을 추정하지 않습니다.</p><ul class="next-list"><li>대상 사진마다 카메라 좌우, 화면에서 작업자가 향한 방향, 측면 촬영 확인을 기록합니다.</li><li>단일 작업자·전신·통상 작업 여부를 확인하고, 모르는 관찰값은 미확인으로 둡니다.</li><li>관찰 하중은 무하중, 측정값, 미확인을 구분하고 측정 출처를 남깁니다.</li><li>상자 들기도 다른 작업과 같은 일반 작업·가변 사진·조건별 입력을 사용합니다.</li></ul><p>사진의 자세 비율은 하루 노출시간이나 법정 기준 해당 확률이 아닙니다.</p>`),
 'start-analysis':async()=>{if(!s.bundle)return toast('작업을 먼저 선택하세요.');const handle=await api('start_analysis',{task_id:s.bundle.task.task_id});s.selectedAnalysis=handle.analysis_id;await navigate('S05');},
 'cancel-analysis':async()=>{if(s.analysis){await api('cancel_analysis',{analysis_id:s.analysis.analysis_id});toast('취소를 요청했습니다.');}},
 'select-slot':async b=>{s.slot=Number(b.dataset.slot);render();},
 'apply-candidates':async()=>saveManual(true),
 'save-manual':async()=>saveManual(false),
 'recalculate-tags':async()=>{s.analysis=await api('recalculate_tags',{task_id:s.bundle.task.task_id});s.selectedAnalysis=s.analysis.analysis_id;await refreshTask();render();},
 'representative':async b=>{if(!s.analysis)return toast('분석 결과가 없습니다.');s.analysis=await api('select_representative',{analysis_id:s.analysis.analysis_id,slot_no:Number(b.dataset.slot)});render();toast(s.analysis.notes.at(-1)?.message||'대표사진을 저장했습니다.');},
 'calculate-criteria':async()=>{if(!s.bundle)return toast('작업을 선택하세요.');s.analysis=await api('recalculate_judgments',{task_id:s.bundle.task.task_id});s.selectedAnalysis=s.analysis.analysis_id;await navigate('S07');},
 'conclusion':async b=>{const n=Number(b.dataset.number),j=s.analysis?.judgment?.judgments.find(j=>j.criterion_no===n);if(!j)return toast('직접입력으로 초안 재계산을 먼저 실행하세요.');s.editCriterion=n;modal(`${n}호 · 조사자 결론`,`${select('조사자 결론','inv.status',j.investigator.status,[['','미입력·결론 해제'],['APPLICABLE','해당'],['NOT_APPLICABLE','비해당']])}${field('사유','inv.reason',j.investigator.reason)}${field('근거','inv.evidence',j.investigator.evidence.text)}${field('검토자','inv.reviewer',j.investigator.reviewer||s.survey.investigator)}<div class="toolbar"><button class="primary" data-action="save-conclusion">결론 저장</button></div><p class="input-guide">앱 초안의 누락·검토 사유는 유지되며 조사 전체 검토 표시가 해제됩니다.</p>`);},
 'save-conclusion':async()=>{const conclusion={criterion_no:s.editCriterion,status:text('inv.status')||null,reason:text('inv.reason')||null,evidence:{source:'DIRECT_OBSERVATION',text:text('inv.evidence')||null,observed_at:new Date().toISOString()},reviewer:text('inv.reviewer')||null,reviewed_at:new Date().toISOString()};s.analysis=await api('set_investigator_conclusion',{analysis_id:s.analysis.analysis_id,conclusion});s.survey=await api('get_survey',{survey_id:s.survey.survey_id});$('#overlay-root').innerHTML='';render();},
 'review-on':async()=>setReview(true), 'review-off':async()=>setReview(false),
 'refresh-overview':async()=>{await navigate('S08');await populateExportChoices();},
  'export':async()=>{const destination=await window.loco.choose_export_destination();if(!destination)return;const receipt=await api('export_excel',{survey_id:s.survey.survey_id,spec:{destination,analysis_ids:selectedIds(),include_representative:$('#include-representative').checked,comparisons:comparisonSpecs()}});toast('유형별 한글 Excel을 저장했습니다.\n'+receipt.file_path);await navigate('S08');await populateExportChoices();},
 'generate-explanation':async()=>{if(!s.analysis)return toast('분석 결과를 먼저 선택하세요.');const result=await api('generate_ai_text',{analysis_id:s.analysis.analysis_id,purpose:s.aiPurpose||'TASK_EXPLANATION'});s.aiTextId=result.text.text_id;await refreshTask();render();},
 'edit-explanation':async()=>{const ai=(s.analysis?.ai||[]).find(x=>x.text_id===s.aiTextId);if(!ai)return toast('설명 이력을 먼저 선택하세요.');await api('edit_ai_text',{analysis_id:s.analysis.analysis_id,text_id:ai.text_id,text:$('#explanation-text').value});await refreshTask();render();},
 'apply-generated':async()=>applyExplanation(false),'apply-edited':async()=>applyExplanation(true),
 'save-analysis-settings':async()=>{const settings=structuredClone(s.settings);delete settings.gpt_key_present;settings.analysis.pose_model.confidence_min=number('analysis-confidence');for(const key of ['neck_forward_deg','trunk_flex_deg','trunk_extension_deg','upper_arm_raise_deg'])settings.analysis.posture_profile[key]=number('profile-'+key);s.settings=await api('update_settings',{settings});await refreshTask();render();toast('분석 보조 설정을 저장했습니다. 영향을 받는 분석은 다시 계산하세요.');},
 'save-settings':async()=>{s.settings.ui={loco_visible:text('loco_visible')==='YES',loco_mode:text('loco_mode')};await persistSettings();render();toast('로코 설정을 저장했습니다.');},
 'save-gpt-settings':async()=>{s.settings.gpt_enabled=text('gpt_enabled')==='YES';s.settings.gpt_model=text('gpt_model').trim();await persistSettings();render();toast('GPT 설정을 저장했습니다.');},
 'close-modal':async()=>$('#overlay-root').innerHTML=''
};

async function applyExplanation(useEdited){const ai=(s.analysis?.ai||[]).find(x=>x.text_id===s.aiTextId);if(!ai)return toast('설명 이력을 먼저 선택하세요.');await api('apply_ai_text',{analysis_id:s.analysis.analysis_id,text_id:ai.text_id,use_edited:useEdited});await refreshTask();render();}

async function setReview(reviewed){const tasks=await api('list_tasks',{survey_id:s.survey.survey_id});const ids=tasks.map(t=>t.task_id===s.bundle?.task.task_id?s.analysis?.analysis_id:t.latest_analysis_id).filter(Boolean);const review={reviewed,reviewed_analysis_ids:ids,reviewed_metadata_revision:s.survey.metadata_revision,reviewer:text('review-reviewer')||s.survey.investigator||null,reviewed_at:new Date().toISOString(),note:text('review-note')||null};s.survey=await api('set_survey_review',{survey_id:s.survey.survey_id,review});toast('검토 표시를 저장했습니다. 계산 완전성과는 별도입니다.');render();}

async function persistSettings(){const {gpt_key_present,...settings}=s.settings;s.settings=await api('update_settings',{settings});}

function syncGuidePreferences(){
  const widget=$('loco-guide'),ui=s.settings?.ui;
  if(!ui)return;
  widget.setAttribute('visible',String(ui.loco_visible));
  widget.setAttribute('mode',ui.loco_mode);


  if(s.page==='S09'){
    const visible=$('[data-field="loco_visible"]'),mode=$('[data-field="loco_mode"]');
    if(visible)visible.value=ui.loco_visible?'YES':'NO';
    if(mode)mode.value=ui.loco_mode;
  }
}

 return {editTargets, mergeManual, saveManual, actions, applyExplanation, setReview, persistSettings, syncGuidePreferences};
}
