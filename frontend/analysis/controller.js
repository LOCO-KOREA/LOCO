import {mountPoseSettings} from '../pose-settings.js';
/* Controller: responses belong to the selection that started their request. */
export function createController(ctx){
 const {host,s,pages,statusNames,$,toast,api,options,card,modal}=ctx;
 const {actions}=ctx;
 const timers=ctx.timers||globalThis;

 function token({analysis=false,ai=false,edit=false}={}){
  return {epoch:s.viewEpoch,surveyId:s.survey?.survey_id??null,taskId:s.bundle?.task.task_id??null,
   analysisId:analysis?(s.analysis?.analysis_id??null):undefined,aiEpoch:ai?s.aiEpoch:undefined,editEpoch:edit?s.editEpoch:undefined};
 }
 function current(t){
  return host.active&&!s.pendingSelection&&t.epoch===s.viewEpoch&&t.surveyId===(s.survey?.survey_id??null)&&
   t.taskId===(s.bundle?.task.task_id??null)&&
   (t.analysisId===undefined||t.analysisId===(s.analysis?.analysis_id??null))&&
   (t.aiEpoch===undefined||t.aiEpoch===s.aiEpoch)&&
   (t.editEpoch===undefined||t.editEpoch===s.editEpoch)&&
   (t.analysisIntent===undefined||t.analysisIntent===s.analysisIntent);
 }
 function stopPoll(){
  if(s.pollOwner)s.pollOwner.stopped=true;
  if(s.poll!==null)timers.clearTimeout(s.poll);
  s.poll=null;s.pollOwner=null;
 }
 function invalidate(){s.viewEpoch++;s.readSequence++;s.exportSequence++;stopPoll();s.modalContext=null;s.pendingSelection=null;}
 function settleJobs(taskId,history,observed=s.runningJobs.get(taskId)){
  const id=s.runningJobs.get(taskId);
  if(id!==undefined&&id===observed){const a=history.find(x=>x.analysis_id===id);if(!a||a.status!=='RUNNING')s.runningJobs.delete(taskId);}
 }
 function actionKey(action){
  const task=s.bundle?.task.task_id,analysis=s.analysis?.analysis_id;
  if(['save-manual','apply-candidates'].includes(action))return `task:${task}:manual`;
  if(action==='start-analysis')return `task:${task}:start`;
  if(action==='cancel-analysis')return `analysis:${analysis}:cancel`;
  if(action==='recalculate-tags')return `task:${task}:tags`;
  if(action==='calculate-criteria')return `task:${task}:judgments`;
  if(action==='representative')return `analysis:${analysis}:representative`;
  if(action==='save-conclusion')return `analysis:${s.modalContext?.analysisId??analysis}:conclusion:${s.editCriterion}`;
  if(action==='generate-explanation')return `analysis:${analysis}:generate:${s.aiPurpose||'TASK_EXPLANATION'}`;
  if(action==='edit-explanation')return `analysis:${analysis}:edit:${s.aiTextId}`;
  if(['apply-generated','apply-edited'].includes(action))return `analysis:${analysis}:apply:${s.aiTextId}`;
  if(['review-on','review-off'].includes(action))return `survey:${s.survey?.survey_id}:review`;
  if(action==='export')return `survey:${s.survey?.survey_id}:export`;
  if(['save-settings','save-gpt-settings','save-analysis-settings'].includes(action))return 'settings:update';
  return null;
 }
 function syncBusy(){
  for(const button of host.element.querySelectorAll('[data-action]')){
   const key=actionKey(button.dataset.action);
   const busy=key&&s.pendingWrites.has(key)||button.dataset.action==='start-analysis'&&s.runningJobs.has(s.bundle?.task.task_id)||s.pendingSelection&&key&&!key.endsWith(':cancel');
   if(busy){if(!button.hasAttribute('data-request-busy'))button.dataset.requestWasDisabled=String(button.disabled);button.dataset.requestBusy='true';button.disabled=true;button.setAttribute('aria-busy','true');}
   else if(button.hasAttribute('data-request-busy')){button.disabled=button.dataset.requestWasDisabled==='true';delete button.dataset.requestBusy;delete button.dataset.requestWasDisabled;button.removeAttribute('aria-busy');}
  }
 }
 async function write(key,t,work){
  if(s.pendingSelection&&!key.endsWith(':cancel')){toast('선택한 작업을 불러오는 중입니다.');return;}
  if(s.pendingWrites.has(key)){if(current(t))toast('같은 대상의 요청을 처리하고 있습니다.');return;}
  const owner={};s.pendingWrites.set(key,owner);syncBusy();
  try{return await work();}
  catch(error){if(current(t))toast(error.message);return undefined;}
  finally{if(s.pendingWrites.get(key)===owner)s.pendingWrites.delete(key);syncBusy();}
 }
 async function refreshTask(t=token(),{selection=s.selectedAnalysis}={}){
  if(t.taskId===null||t.surveyId===null)return false;
  const sequence=++s.readSequence,observedJob=s.runningJobs.get(t.taskId);
  const [bundle,history,tasks]=await Promise.all([
   api('get_task',{task_id:t.taskId}),api('list_analysis_history',{task_id:t.taskId}),api('list_tasks',{survey_id:t.surveyId})
  ]);
  // Job ownership outlives navigation; only matching job IDs are retired.
  settleJobs(t.taskId,history,observedJob);
  if(!current(t)||sequence!==s.readSequence)return false;
  const chosen=history.find(a=>a.analysis_id===selection)||history.find(a=>a.analysis_id===bundle.task.latest_analysis_id);
  s.bundle=bundle;s.history=history;s.tasks=tasks;s.analysis=chosen||null;s.selectedAnalysis=chosen?.analysis_id??null;
  syncBusy();return true;
 }
 async function navigate(page,{refresh=true}={}){
  invalidate();
  if(['S01','S02','S03','S04','S05'].includes(page)){await host.onLeave(page);return false;}
  s.page=page;const t=token();
  try{
  if(refresh&&s.bundle&&['S09','S06','S07'].includes(page)){if(!await refreshTask(t))return false;}
  if(page==='S08'&&s.survey){
   const surveyId=t.surveyId,ids=[...ctx.selectedIds()],comparisons=structuredClone(ctx.comparisonSpecs());
   const [tasks,overview]=await Promise.all([api('list_tasks',{survey_id:surveyId}),api('preview_excel',{survey_id:surveyId,analysis_ids:ids,comparisons})]);
   if(!current(t))return false;s.tasks=tasks;s.overview=overview;
  }
  if(!current(t))return false;render();startPoll();return true;
  }catch(error){if(current(t))toast(error.message);return false;}
 }
 function render(){
  if(!host.active)return;
  host.onNavigate(s.page,pages[s.page]);ctx.syncGuidePreferences();
  $('#content').innerHTML=(s.survey&&s.page!=='S10'?card('작업 선택',`<div class="toolbar"><select id="task-choice" aria-label="분석할 작업">${options([['','작업 선택'],...s.tasks.map(t=>[t.task_id,t.task_name||'이름 없는 작업'])],s.bundle?.task.task_id)}</select><button data-page="S03">작업 입력으로</button></div>`):'')+({S09:ctx.progressPage,S06:ctx.rebaPage,S07:ctx.criteriaPage,S08:ctx.exportPage,S10:ctx.settingsPage}[s.page])();
  mountPoseSettings(host.element,s.settings,'data-pose-field');
  if(s.page==='S06')ctx.drawPhoto();syncBusy();
 }
 function startPoll(){
  stopPoll();if(s.page!=='S09'||s.analysis?.status!=='RUNNING'||!host.active)return;
  const owner={token:token({analysis:true}),analysisId:s.analysis.analysis_id,stopped:false,inFlight:false};s.pollOwner=owner;
  s.poll=timers.setTimeout(()=>pollAnalysis(owner),800);
 }
 async function pollAnalysis(owner=s.pollOwner){
  if(!owner||owner.stopped||owner!==s.pollOwner||owner.inFlight||!current(owner.token))return;
  owner.inFlight=true;
  try{
   const result=await api('get_analysis',{analysis_id:owner.analysisId});
   if(result.status!=='RUNNING'&&s.runningJobs.get(result.task_id)===result.analysis_id)s.runningJobs.delete(result.task_id);
   if(owner.stopped||owner!==s.pollOwner||!current(owner.token))return;
   s.analysis=result;render();
   if(result.status!=='RUNNING'){stopPoll();toast('분석 요청 처리가 끝났습니다. 사진별 진단과 입력 부족을 확인하세요.');}
  }catch(error){if(!owner.stopped&&owner===s.pollOwner&&current(owner.token)){stopPoll();toast(error.message);}}
  finally{owner.inFlight=false;if(!owner.stopped&&owner===s.pollOwner&&current(owner.token))s.poll=timers.setTimeout(()=>pollAnalysis(owner),800);}
 }
 async function populateExportChoices(){
  const t=token(),sequence=++s.exportSequence,tasks=[...s.tasks];
  const entries=await Promise.all(tasks.map(async task=>({task,history:await api('list_analysis_history',{task_id:task.task_id})})));
  if(!current(t)||sequence!==s.exportSequence)return false;
  s.comparisonPool=entries.flatMap(({task,history})=>history.map(a=>({...a,task_name:task.task_name})));
  for(const {task,history} of entries){const select=$(`[data-export-task="${task.task_id}"]`);if(select?.isConnected)select.innerHTML=options([['','최신 분석 / 미분석'],...history.map(a=>[a.analysis_id,`#${a.analysis_id} · r${a.input_revision} · ${statusNames[a.currentness]}`])],s.exportSelections[task.task_id]||'');}
  const choices=[['','분석 선택'],...s.comparisonPool.map(a=>[a.analysis_id,`#${a.analysis_id} · ${a.task_name} · r${a.input_revision}`])];
  for(const id of ['comparison-before','comparison-after']){const select=$(`[data-field="${id}"]`);if(select?.isConnected)select.innerHTML=options(choices,id==='comparison-before'?s.comparisonBefore:s.comparisonAfter);}return true;
 }
 function selectHistory(id){invalidate();s.selectedAnalysis=id;s.analysis=s.history.find(a=>a.analysis_id===id)||null;s.aiTextId=null;s.aiEpoch++;render();startPoll();}
 async function chooseTask(taskId){
  invalidate();s.slot=1;s.selectedSlots.clear();s.selectedAnalysis=null;s.aiTextId=null;s.aiEpoch++;
  const epoch=s.viewEpoch,surveyId=s.survey?.survey_id;s.pendingSelection={epoch,taskId};syncBusy();
  try{
   const observedJob=s.runningJobs.get(taskId);
   const [bundle,history,tasks]=await Promise.all([api('get_task',{task_id:taskId}),api('list_analysis_history',{task_id:taskId}),api('list_tasks',{survey_id:surveyId})]);
   if(!host.active||epoch!==s.viewEpoch||surveyId!==s.survey?.survey_id)return false;
   s.bundle=bundle;s.history=history;s.tasks=tasks;s.analysis=history.find(a=>a.analysis_id===bundle.task.latest_analysis_id)||null;s.selectedAnalysis=s.analysis?.analysis_id??null;
   settleJobs(taskId,history,observedJob);s.pendingSelection=null;render();startPoll();return true;
  }catch(error){if(host.active&&epoch===s.viewEpoch){s.pendingSelection=null;render();toast(error.message);}return false;}
 }
 Object.assign(ctx,{token,current,invalidate,write,actionKey,syncBusy,refreshTask,navigate,render,pollAnalysis,populateExportChoices,selectHistory,chooseTask,startPoll});
 host.element.addEventListener('click',async event=>{
  const button=event.target.closest('[data-page],[data-action]');if(!button||button.disabled)return;
  const t=token();try{if(button.dataset.page){if(await navigate(button.dataset.page)&&s.page==='S08')await populateExportChoices();}else await actions[button.dataset.action]?.(button);}catch(error){if(current(t))toast(error.message);}
 });
 host.element.addEventListener('change',async event=>{
  const el=event.target,t=token();try{
   if(el.id==='task-choice'&&el.value){await chooseTask(Number(el.value));return;}
   if(el.id==='history-choice'){selectHistory(Number(el.value)||null);return;}
   if(el.dataset.field==='ai-purpose'||el.dataset.field==='ai-choice'){s.aiEpoch++;if(el.dataset.field==='ai-purpose'){s.aiPurpose=el.value;s.aiTextId=null;}else s.aiTextId=el.value||null;render();return;}
   if(el.dataset.field==='comparison-before'||el.dataset.field==='comparison-after'){if(el.dataset.field==='comparison-before')s.comparisonBefore=Number(el.value)||null;else s.comparisonAfter=Number(el.value)||null;if(await navigate('S08'))await populateExportChoices();return;}
   if(el.dataset.slotAssignment){const capture=structuredClone(s.bundle.task.capture),taskId=t.taskId;const slot=capture.slots.find(x=>x.slot_no===Number(el.dataset.slotAssignment));if(slot)slot.photo_id=Number(el.value)||null;await write(`task:${taskId}:capture`,t,async()=>{await api('set_capture',{task_id:taskId,capture});if(current(t)&&await refreshTask(t))render();});}
   if(el.dataset.selectSlot){s.editEpoch++;if(el.checked)s.selectedSlots.add(Number(el.dataset.selectSlot));else s.selectedSlots.delete(Number(el.dataset.selectSlot));}
   if(el.dataset.manual){s.editEpoch++;const check=$(`[data-manual-use="${el.dataset.manual}"]`);if(check)check.checked=true;}
   if(el.dataset.manualUse!==undefined)s.editEpoch++;
   if(el.dataset.exportTask){s.exportSelections[el.dataset.exportTask]=Number(el.value)||null;if(await navigate('S08'))await populateExportChoices();}
  }catch(error){if(current(t))toast(error.message);}
 });
 host.element.addEventListener('input',event=>{const el=event.target;if(el.dataset.field==='comparison-note')s.comparisonNote=el.value;if(el.dataset.field||el.dataset.manual||el.id==='explanation-text')s.editEpoch++;});
 document.addEventListener('keydown',event=>{if(host.active&&event.key==='Escape'){$('#overlay-root').innerHTML='';s.modalContext=null;}});
 return {
  currentTask(surveyId){return s.survey?.survey_id===surveyId?s.bundle?.task.task_id:undefined;},
  async open({page,surveyId,taskId,analysisId}){
   this.suspend();host.active=true;const epoch=s.viewEpoch;s.pendingSelection={epoch,taskId:taskId??null};syncBusy();
   try{
    const [settings,survey,tasks]=await Promise.all([api('get_settings'),surveyId?api('get_survey',{survey_id:surveyId}):null,surveyId?api('list_tasks',{survey_id:surveyId}):[]]);
    if(!host.active||epoch!==s.viewEpoch)return false;
    const chosen=tasks.find(t=>t.task_id===taskId)||tasks[0];
    const observedJob=chosen?s.runningJobs.get(chosen.task_id):undefined;
    const [bundle,history]=chosen?await Promise.all([api('get_task',{task_id:chosen.task_id}),api('list_analysis_history',{task_id:chosen.task_id})]):[null,[]];
    if(!host.active||epoch!==s.viewEpoch)return false;
    if(s.survey?.survey_id!==surveyId){s.bundle=null;s.analysis=null;s.selectedAnalysis=null;s.exportSelections={};s.selectedSlots.clear();s.comparisonPool=[];s.comparisonBefore=null;s.comparisonAfter=null;s.comparisonNote='';}
    if(s.bundle?.task.task_id!==chosen?.task_id){s.selectedAnalysis=null;s.slot=1;s.selectedSlots.clear();s.aiTextId=null;s.aiEpoch++;}
    s.settings=settings;s.survey=survey;s.tasks=tasks;s.bundle=bundle;s.history=history;
    if(analysisId)s.selectedAnalysis=analysisId;
    s.analysis=history.find(a=>a.analysis_id===s.selectedAnalysis)||history.find(a=>a.analysis_id===bundle?.task.latest_analysis_id)||null;s.selectedAnalysis=s.analysis?.analysis_id??null;
    if(chosen)settleJobs(chosen.task_id,history,observedJob);s.pendingSelection=null;
    // Remove A's controls; only navigate may render the destination page.
    $('#content').innerHTML='';
    if(!await navigate(page,{refresh:false}))return false;if(page==='S08'&&s.survey)await populateExportChoices();return true;
   }catch(error){if(host.active&&epoch===s.viewEpoch)throw error;return false;}
   finally{
    if(s.pendingSelection?.epoch===epoch){s.pendingSelection=null;syncBusy();}
   }
  },
  suspend(){invalidate();host.active=false;$('#overlay-root').innerHTML='';},
  async guide(action){if(action==='guide')await actions['capture-guide']();else if(action==='manual')$('.manual-grid')?.scrollIntoView({behavior:'smooth'});else if(action==='criterion4')modal('4호 · 조건 합산 해석','<p>개별 조건과 중복을 제외한 하루 노출시간을 함께 확인하세요. 합산 해석이 필요한 경우 추가 검토로 표시합니다.</p>');else if(action==='next')$('#next-inputs')?.scrollIntoView({behavior:'smooth'});},
  async preferences(detail){const t=token(),saved=await api('get_settings');if('visible'in detail)saved.ui.loco_visible=detail.visible;if('mode'in detail)saved.ui.loco_mode=detail.mode;await ctx.persistSettings(saved,t);if(current(t))ctx.syncGuidePreferences();},
  async initialize(){const epoch=s.viewEpoch,saved=await api('get_settings');if(epoch===s.viewEpoch){s.settings=saved;ctx.syncGuidePreferences();}}
 };
}
