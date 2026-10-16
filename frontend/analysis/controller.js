/* controller; dependencies are composed by analysis-workspace.js. */
export function createController(ctx){
 const {host, s, pages, statusNames, $, toast, api, options, field, select, card, modal, selectedIds, comparisonSpecs}=ctx;
 const criteriaPage=(...args)=>ctx.criteriaPage(...args);
 const drawPhoto=(...args)=>ctx.drawPhoto(...args);
 const exportPage=(...args)=>ctx.exportPage(...args);
 const persistSettings=(...args)=>ctx.persistSettings(...args);
 const progressPage=(...args)=>ctx.progressPage(...args);
 const rebaPage=(...args)=>ctx.rebaPage(...args);
 const settingsPage=(...args)=>ctx.settingsPage(...args);
 const syncGuidePreferences=(...args)=>ctx.syncGuidePreferences(...args);
 const {actions}=ctx;
async function refreshTask(){if(!s.bundle)return;s.bundle=await api('get_task',{task_id:s.bundle.task.task_id});s.history=await api('list_analysis_history',{task_id:s.bundle.task.task_id});const chosen=s.history.find(a=>a.analysis_id===s.selectedAnalysis)||s.history.find(a=>a.analysis_id===s.bundle.task.latest_analysis_id);s.analysis=chosen||null;s.selectedAnalysis=s.analysis?.analysis_id??null;s.tasks=await api('list_tasks',{survey_id:s.survey.survey_id});}

async function navigate(page){if(['S01','S02','S03','S04'].includes(page)){host.onLeave(page);return;}clearInterval(s.poll);s.poll=null;s.page=page;
  if(page==='S01')s.surveys=await api('list_surveys');
  if(s.bundle&&['S05','S06','S07'].includes(page))await refreshTask();
  if(page==='S08'&&s.survey){s.tasks=await api('list_tasks',{survey_id:s.survey.survey_id});s.overview=await api('preview_excel',{survey_id:s.survey.survey_id,analysis_ids:selectedIds(),comparisons:comparisonSpecs()});}
  render();if(page==='S05'&&s.analysis?.status==='RUNNING')s.poll=setInterval(pollAnalysis,800);
}

function render(){
  if(!host.active)return;
  host.onNavigate(s.page,pages[s.page]);
  syncGuidePreferences();
  $('#content').innerHTML=(s.survey&&s.page!=='S09'?card('작업 선택',`<div class="toolbar"><select id="task-choice" aria-label="분석할 작업">${options([['','작업 선택'],...s.tasks.map(t=>[t.task_id,t.task_name||'이름 없는 작업'])],s.bundle?.task.task_id)}</select><button data-page="S03">작업 입력으로</button></div>`):'')+({S05:progressPage,S06:rebaPage,S07:criteriaPage,S08:exportPage,S09:settingsPage}[s.page])();
  if(s.page==='S06')drawPhoto();
}

async function pollAnalysis(){if(!s.analysis)return;try{s.analysis=await api('get_analysis',{analysis_id:s.analysis.analysis_id});if(s.page==='S05')render();if(s.analysis.status!=='RUNNING'){clearInterval(s.poll);s.poll=null;toast('분석 요청 처리가 끝났습니다. 사진별 진단과 입력 부족을 확인하세요.');}}catch(error){clearInterval(s.poll);toast(error.message);}}

async function populateExportChoices(){const entries=await Promise.all(s.tasks.map(async task=>({task,history:await api('list_analysis_history',{task_id:task.task_id})})));s.comparisonPool=entries.flatMap(({task,history})=>history.map(a=>({...a,task_name:task.task_name})));for(const {task,history} of entries){const select=$(`[data-export-task="${task.task_id}"]`);if(select?.isConnected)select.innerHTML=options([['','최신 분석 / 미분석'],...history.map(a=>[a.analysis_id,`#${a.analysis_id} · r${a.input_revision} · ${statusNames[a.currentness]}`])],s.exportSelections[task.task_id]||'');}const choices=[['','분석 선택'],...s.comparisonPool.map(a=>[a.analysis_id,`#${a.analysis_id} · ${a.task_name} · r${a.input_revision}`])];for(const id of ['comparison-before','comparison-after']){const select=$(`[data-field="${id}"]`);if(select?.isConnected)select.innerHTML=options(choices,id==='comparison-before'?s.comparisonBefore:s.comparisonAfter);}}

 Object.assign(ctx,{refreshTask, navigate, render, pollAnalysis, populateExportChoices});
host.element.addEventListener('click',async event=>{const button=event.target.closest('[data-page],[data-action]');if(!button)return;try{if(button.dataset.page){await navigate(button.dataset.page);if(s.page==='S08')await populateExportChoices();}else await actions[button.dataset.action]?.(button);}catch(error){toast(error.message);}});
host.element.addEventListener('change',async event=>{const el=event.target;try{if(el.id==='task-choice'&&el.value){s.slot=1;s.selectedSlots.clear();s.bundle=await api('get_task',{task_id:Number(el.value)});s.selectedAnalysis=null;await refreshTask();render();}if(el.id==='history-choice'){s.selectedAnalysis=Number(el.value)||null;s.analysis=s.history.find(a=>a.analysis_id===s.selectedAnalysis)||null;s.aiTextId=null;render();}if(el.dataset.field==='ai-purpose'){s.aiPurpose=el.value;s.aiTextId=null;render();}if(el.dataset.field==='ai-choice'){s.aiTextId=el.value||null;render();}if(el.dataset.field==='comparison-before'){s.comparisonBefore=Number(el.value)||null;await navigate('S08');await populateExportChoices();}if(el.dataset.field==='comparison-after'){s.comparisonAfter=Number(el.value)||null;await navigate('S08');await populateExportChoices();}if(el.dataset.slotAssignment){const capture=structuredClone(s.bundle.task.capture);const slot=capture.slots.find(x=>x.slot_no===Number(el.dataset.slotAssignment));if(slot)slot.photo_id=Number(el.value)||null;await api('set_capture',{task_id:s.bundle.task.task_id,capture});await refreshTask();render();}if(el.dataset.selectSlot){if(el.checked)s.selectedSlots.add(Number(el.dataset.selectSlot));else s.selectedSlots.delete(Number(el.dataset.selectSlot));}if(el.dataset.manual){const check=$(`[data-manual-use="${el.dataset.manual}"]`);if(check)check.checked=true;}if(el.dataset.exportTask){s.exportSelections[el.dataset.exportTask]=Number(el.value)||null;await navigate('S08');await populateExportChoices();}}catch(error){toast(error.message);}});
host.element.addEventListener('input',event=>{if(event.target.dataset.field==='comparison-note')s.comparisonNote=event.target.value;});
document.addEventListener('keydown',event=>{if(host.active&&event.key==='Escape')$('#overlay-root').innerHTML='';});


return {
 currentTask(surveyId){return s.survey?.survey_id===surveyId?s.bundle?.task.task_id:undefined;},
 async open({page,surveyId,taskId,analysisId}){
  this.suspend();host.active=true;
  s.settings=await api('get_settings');
   if(s.survey?.survey_id!==surveyId){s.bundle=null;s.analysis=null;s.selectedAnalysis=null;s.exportSelections={};s.selectedSlots.clear();s.comparisonPool=[];s.comparisonBefore=null;s.comparisonAfter=null;s.comparisonNote='';}
  s.survey=surveyId?await api('get_survey',{survey_id:surveyId}):null;
  s.tasks=surveyId?await api('list_tasks',{survey_id:surveyId}):[];
  const chosen=s.tasks.find(t=>t.task_id===taskId)||s.tasks[0];
  if(chosen){
   if(s.bundle?.task.task_id!==chosen.task_id){s.selectedAnalysis=null;s.slot=1;s.selectedSlots.clear();}
   s.bundle=await api('get_task',{task_id:chosen.task_id});if(analysisId)s.selectedAnalysis=analysisId;await refreshTask();
  }else{s.bundle=null;s.analysis=null;s.selectedAnalysis=null;}
  await navigate(page);if(page==='S08'&&s.survey)await populateExportChoices();
 },
 suspend(){host.active=false;clearInterval(s.poll);s.poll=null;$('#overlay-root').innerHTML='';},
 async guide(action){
  if(action==='guide')await actions['capture-guide']();
  else if(action==='manual')$('.manual-grid')?.scrollIntoView({behavior:'smooth'});
  else if(action==='criterion4')modal('4호 · 조건 합산 해석','<p>개별 조건과 중복을 제외한 하루 노출시간을 함께 확인하세요. 합산 해석이 필요한 경우 추가 검토로 표시합니다.</p>');
  else if(action==='next')$('#next-inputs')?.scrollIntoView({behavior:'smooth'});
 },
 async preferences(detail){
  s.settings=await api('get_settings');
  if('visible'in detail)s.settings.ui.loco_visible=detail.visible;
  if('mode'in detail)s.settings.ui.loco_mode=detail.mode;
  await persistSettings();syncGuidePreferences();
 },
 async initialize(){s.settings=await api('get_settings');syncGuidePreferences();}
};

}
