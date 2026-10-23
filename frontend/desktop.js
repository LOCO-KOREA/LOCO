import {DatabaseLocation} from './database-location.js';
import {SurveyEditor} from './survey-editor.js';
import {createDeleteConfirmation} from './delete-confirmation.js';
import {SCREENS, isAnalysisScreen} from './screens.js';
import {TaskWorkspace} from './task-workspace.js';
import {PhotoWorkspace} from './photo-workspace.js';
import {DashboardWorkspace} from './dashboard.js';
import {createSampleSurvey} from './sample-data.js';
import {nextStep, renderNextStep, markDone} from './next-step.js';
import {QuickFlow} from './quick-flow.js';
import {SurveyIntake} from './survey-intake.js';
import {createAnalysisWorkspace} from './analysis-workspace.js';
const $=selector=>document.querySelector(selector);
const confirmDeletion=createDeleteConfirmation(document);
const state={stepDone:[],surveys:[],selected:null,editorId:null,details:new Map(),drafts:new Map(),busy:false,page:'S01'};
const names=SCREENS.map(screen=>screen.name);
const paths=['<rect x="2" y="2" width="5" height="5" rx="1"/><rect x="11" y="2" width="5" height="5" rx="1"/><rect x="2" y="11" width="5" height="5" rx="1"/><rect x="11" y="11" width="5" height="5" rx="1"/>','<rect x="3" y="2" width="12" height="14" rx="2"/><path d="M6 6h6M6 9h6M6 12h4"/>','<path d="m2 5 7-3 7 3-7 3zM2 5v8l7 3 7-3V5M9 8v8"/>','<path d="M2 5h3l2-2h4l2 2h3v10H2z"/><circle cx="9" cy="10" r="3"/>','<path d="M6 2H2v4M12 2h4v4M2 12v4h4M12 16h4v-4"/><circle cx="9" cy="9" r="3"/>','<circle cx="9" cy="3" r="2"/><path d="M9 5v6M4 9l5-3 5 3M9 11l-4 6M9 11l4 6"/>','<path d="m9 1 6 3v5c0 4-6 7-6 7S3 13 3 9V4zM6 8l2 2 4-4"/>','<path d="M4 1h7l4 4v12H4zM11 1v4h4M7 8h5M7 11h5M7 14h3"/>','<circle cx="9" cy="9" r="3"/><path d="M9 1v3M9 14v3M1 9h3M14 9h3M3 3l2 2M13 13l2 2M3 15l2-2M13 5l2-2"/>'];
const esc=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
function notify(text){clearError();$('#toast').textContent=text;$('#toast').hidden=false;clearTimeout(notify.timer);notify.timer=setTimeout(()=>$('#toast').hidden=true,4500);}
function showError(error){clearTimeout(notify.timer);$('#toast').hidden=true;$('#error').textContent=error.message||String(error);$('#error').hidden=false;if($('#survey-editor').open)$('#survey-editor-error').textContent=error.message||String(error);}
function clearError(){$('#error').hidden=true;$('#survey-editor-error').textContent='';}
async function api(method,params={}){if(!window.loco)throw new Error('브라우저 미리보기입니다. 저장·조회는 Electron 앱에서 실행하세요.');const result=await window.loco.call(method,params);if(!result.ok)throw new Error(`${result.error.code}: ${result.error.message}`);return result.value;}
function blank(){return {survey_type:'REGULAR',survey_date:new Date().toLocaleDateString('sv-SE',{timeZone:'Asia/Seoul'}),investigator:'',department:'',process:'',title:'',occasional_reason:''};}
function draft(){const data=Object.fromEntries(new FormData($('#survey-form')));return {survey_type:data.survey_type,survey_date:data.survey_date||null,investigator:data.investigator||'',department:data.department||'',process:data.process||'',title:data.title||'',occasional_reason:data.occasional_reason||null,...intakeUI.collect(data)};}
function remember(){state.drafts.set(state.editorId??'new',draft());}
function fill(data){for(const key of Object.keys(blank())){if(key==='survey_type'){const type=['INITIAL','REGULAR','OCCASIONAL'].includes(data[key])?data[key]:'REGULAR';const radio=$(`#survey-form input[name="survey_type"][value="${type}"]`);if(radio)radio.checked=true;}else $('#survey-form').elements.namedItem(key).value=data[key]??'';}intakeUI.fill(data);$('#form-title').textContent=state.editorId?'조사개요 수정':'조사개요 입력';$('#save-survey').textContent=state.editorId?'조사 저장하고 작업 등록':'조사 만들고 작업 등록';}
function status(s){return s.review_current?'current':s.reviewed?'history':'none';}
function rows(){const keyword=$('#search').value.trim().toLowerCase(),filter=$('#review-filter').value,sign=$('#sort').value==='asc'?1:-1;const list=state.surveys.filter(s=>(filter==='all'||status(s)===filter)&&s.title.toLowerCase().includes(keyword)).sort((a,b)=>sign*((a.survey_date||'').localeCompare(b.survey_date||'')||a.survey_id-b.survey_id));$('#survey-rows').innerHTML=list.map(s=>`<tr data-id="${s.survey_id}" class="${s.survey_id===state.selected?'selected':''}"><td class="row-title"><button class="row-button" data-id="${s.survey_id}"><strong>${esc(s.title||'제목 없는 조사')}</strong></button><small>조사 #${s.survey_id}</small></td><td>${esc(s.survey_date||'미입력')}</td><td>${s.task_count}</td><td><span class="badge ${status(s)}">${s.review_current?'검토 완료':s.reviewed?'이전 결과 검토':'미검토'}</span></td></tr>`).join('')||'<tr><td colspan="4" class="empty">'+(state.surveys.length?'조건에 맞는 조사가 없습니다.':'저장된 조사가 없습니다.<br>상단의 새 조사 버튼으로 첫 조사를 만들어 주세요.')+'</td></tr>';const chosen=state.surveys.find(s=>s.survey_id===state.selected);$('#selection').textContent=chosen?`선택 조사 · ${chosen.title||'제목 없음'} / 조사 #${chosen.survey_id}`:'선택한 조사가 없습니다.';}
async function refresh(){state.surveys=await api('list_surveys');rows();if(state.page==='S01')await dashboardUI.open(state.surveys,state.selected);$('#connection').textContent='';$('#connection').setAttribute('aria-label','연결됨');$('#connection').classList.add('connected');updateNextStep();}
async function selectSurvey(id){if(state.busy)return;remember();const survey=await api('get_survey',{survey_id:id});state.selected=id;state.editorId=id;state.details.set(id,survey);fill(state.drafts.get(id)||survey);rows();clearError();}
function page(id){
  state.page=id;
  if(!isAnalysisScreen(id))analysisUI.suspend();
  $('#analysis-workspace').hidden=!isAnalysisScreen(id);
  $('#dashboard-workspace').hidden=id!=='S01';
  $('#survey-workspace').hidden=id!=='S02';
  $('#task-workspace').hidden=!['S03','S04'].includes(id);
  $('#photo-workspace').hidden=id!=='S05';
  const screen=SCREENS.find(screen=>screen.id===id);
  if(['S01','S02'].includes(id)){
    $('#title').textContent=screen.name;$('.page-title p').textContent=screen.description;
    if(id==='S01')perform(()=>dashboardUI.open(state.surveys,state.selected));
  }
  const icons=[0,1,2,1,3,5,6,7,4,8];
  $('#navigation').innerHTML=SCREENS.filter(screen=>screen.navigation!==false).map((screen,i)=>`<button data-nav="${screen.id}" class="${id===screen.id?'active':''}" ${id===screen.id?'aria-current="page"':''}><svg viewBox="0 0 18 18" fill="none" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${paths[icons[i]]}</svg>${screen.name}<em>${String(i+1).padStart(2,'0')}</em></button>`).join('');
  $('#breadcrumb-mode').textContent='조사 관리';$('#breadcrumb-page').textContent=screen.name;$('loco-guide').setAttribute('page',id);
  markDone($('#navigation'),state.stepDone);updateNextStep();
}
let stepRevision=0;
async function updateNextStep(){
  if(!window.loco)return;
  const revision=++stepRevision;
  try{
    const surveys=await api('list_surveys');
    const survey=surveys.find(item=>item.survey_id===state.selected)||null;
    const tasks=survey?await api('list_tasks',{survey_id:survey.survey_id}):[];
    if(revision!==stepRevision)return;
    const step=nextStep({survey,tasks});
    state.stepDone=step.done;
    renderNextStep($('#next-step'),step,SCREENS);markDone($('#navigation'),state.stepDone);
  }catch{/* the hint is optional; real errors surface from the screen's own calls */}
}
$('#next-step').addEventListener('click',event=>{const id=event.target.closest('[data-next-step]')?.dataset.nextStep;if(id)perform(()=>id==='S02'&&!state.selected?newSurvey():navigateScreen(id));});
async function tasks(screen='info',skipPhotoFlush=false,taskId){
  const selected=taskId??(state.page==='S05'?photoUI.task?.task_id:isAnalysisScreen(state.page)?analysisUI.currentTask(state.selected):undefined);
  if(state.page==='S05'&&!skipPhotoFlush)await photoUI.flush();
  taskUI.remember();
  if(!state.selected){
    if(!window.loco){taskUI.preview();taskUI.screen=screen;taskUI.render();return;}
    return notify('조사를 먼저 선택해 주세요.');
  }
  await taskUI.open(state.selected);
  if(selected&&taskUI.current?.task_id!==selected)await taskUI.load(selected);
  taskUI.screen=screen;taskUI.render();window.scrollTo({top:0});
}
async function photos(taskId){
  if(!window.loco&&!state.selected){page('S05');photoUI.preview();return;}
  if(!state.selected)return notify('조사를 먼저 선택해 주세요.');
  if(state.page==='S05'&&(!taskId||photoUI.task?.task_id===taskId))return;
  if(state.page==='S05')await photoUI.flush();
  const selected=taskId??(isAnalysisScreen(state.page)?analysisUI.currentTask(state.selected):undefined);
  if(taskUI.surveyId!==state.selected||!taskUI.current)await taskUI.open(state.selected);
  if(selected&&taskUI.current?.task_id!==selected)await taskUI.load(selected);
  if(!taskUI.current.task_id||taskUI.isDirty())await taskUI.save();
  await photoUI.open(taskUI.current.task_id);page('S05');window.scrollTo({top:0});
}
async function openAnalysis(id,taskId,analysisId,skipPhotoFlush=false){
  if(id==='S05')return photos(taskId);
  if(['S03','S04'].includes(id))return tasks(id==='S04'?'conditions':'info',skipPhotoFlush,taskId);
  if(state.page==='S05'&&!skipPhotoFlush)await photoUI.flush();
  taskUI.remember();
  if(id!=='S10'&&!state.selected)return notify('조사를 먼저 선택해 주세요.');
  const selectedTask=taskId??(state.page==='S05'?photoUI.task?.task_id:isAnalysisScreen(state.page)?analysisUI.currentTask(state.selected):taskUI.current?.task_id);
  await analysisUI.open({page:id,surveyId:state.selected,taskId:selectedTask,analysisId});
  window.scrollTo({top:0});
}
async function navigateScreen(id,taskId,skipPhotoFlush=false){
  if(['S01','S02'].includes(id)){
    if(state.page==='S05'&&!skipPhotoFlush)await photoUI.flush();
    taskUI.remember();page(id);window.scrollTo({top:0});return;
  }
  return openAnalysis(id,taskId,undefined,skipPhotoFlush);
}
async function startPhotoAnalysis(taskId){
  const {task}=await api('get_task',{task_id:taskId});
  await api('set_analysis_scope',{task_id:taskId,scope:{...task.analysis_scope,pose:true,tags:true,reba:true}});
  const handle=await api('start_analysis',{task_id:taskId});
  await openAnalysis('S09',taskId,handle.analysis_id,true);
}
async function calculateCriteria(taskId){
  const analysis=await api('recalculate_judgments',{task_id:taskId});
  await openAnalysis('S07',taskId,analysis.analysis_id);
}
async function perform(action){try{clearError();await action();}catch(error){showError(error);}}
const intakeUI=new SurveyIntake($('#survey-form'),error=>{if(error)showError(error);else remember();});
const surveyEditor=new SurveyEditor($('#survey-form'),{remember,isBusy:()=>state.busy});
$('#page-top').addEventListener('click',()=>window.scrollTo({top:0,behavior:matchMedia('(prefers-reduced-motion: reduce)').matches?'instant':'smooth'}));
$('#edit-survey').addEventListener('click',()=>{if(!state.selected)return notify('수정할 조사를 선택해 주세요.');clearError();surveyEditor.open();});
$('#survey-form').addEventListener('input',remember);$('#survey-form').addEventListener('change',remember);
$('#survey-form').addEventListener('submit',event=>{event.preventDefault();if(state.busy)return;perform(async()=>{state.busy=true;$('#save-survey').disabled=true;try{const value=draft();remember();const saved=await api(state.editorId?'update_survey':'create_survey',state.editorId?{survey_id:state.editorId,draft:value}:{draft:value});state.selected=saved.survey_id;state.editorId=saved.survey_id;state.details.set(saved.survey_id,saved);state.drafts.delete('new');state.drafts.set(saved.survey_id,value);fill(saved);await refresh();surveyEditor.close(true);notify('조사를 SQLite에 저장했습니다.');await tasks();}finally{state.busy=false;$('#save-survey').disabled=false;}});});
$('#survey-rows').addEventListener('click',event=>{const row=event.target.closest('[data-id]');if(row)perform(async()=>{await selectSurvey(Number(row.dataset.id));if(!state.busy)surveyEditor.open();});});
function newSurvey(){if(state.busy)return;remember();state.editorId=null;state.selected=null;fill(state.drafts.get('new')||blank());rows();page('S02');clearError();surveyEditor.open();}
$('#new-survey').addEventListener('click',newSurvey);
$('#open-survey').addEventListener('click',()=>perform(tasks));
$('#delete-survey').addEventListener('click',()=>{if(!state.selected||state.busy)return notify('삭제할 조사를 선택해 주세요.');perform(async()=>{const id=state.selected;const survey=state.surveys.find(item=>item.survey_id===id);const deleted=await confirmDeletion({title:'조사를 삭제할까요?',message:`조사: ${survey?.title||'제목 없는 조사'} (#${id})\n포함 작업 ${survey?.task_count??'전체'}개와 등록 사진 정보, 분석 이력, 조사자 검토 및 출력 기록이 삭제됩니다.\n원본 사진과 이미 만든 Excel 파일은 삭제하지 않습니다.\n이 작업은 앱에서 되돌릴 수 없습니다.`,remove:()=>api('delete_survey',{survey_id:id})});if(!deleted)return;taskUI.resetSurvey(id);state.drafts.delete(id);state.details.delete(id);state.selected=null;state.editorId=null;fill(blank());page('S01');await refresh();notify('선택 조사를 삭제했습니다. 원본 사진과 Excel은 삭제하지 않습니다.');});});
for(const selector of ['#search','#review-filter','#sort'])$(selector).addEventListener(selector==='#search'?'input':'change',rows);
$('#navigation').addEventListener('click',event=>{const id=event.target.closest('[data-nav]')?.dataset.nav;if(id)perform(()=>navigateScreen(id));});
$('#home').addEventListener('click',()=>perform(async()=>{
  if(document.body.classList.contains('quick-mode')){
    await quickUI.workspaceHome();
    if(quickUI.step==='home'){$('#title').textContent='사진으로 빠른 분석';$('.page-title p').textContent='';}
    return;
  }
  if(state.page==='S05')await photoUI.flush();taskUI.remember();page('S01');window.scrollTo({top:0});
}));
$('#help').addEventListener('click',()=>{$('#dialog-title').textContent='LOCO · 작업 분석 안내';$('#dialog-text').textContent='조사·일반 작업 입력, 11개 기준, 가변 사진·사진별 관찰, 선택 분석, 조사자 검토와 한글 Excel 흐름을 사용합니다. 상자 들기도 같은 작업 기록을 사용합니다.';$('#dialog').showModal();});$('#close-dialog').addEventListener('click',()=>$('#dialog').close());
document.addEventListener('loco-guide-action',event=>{const {action}=event.detail;if(SCREENS.some(s=>s.id===action))perform(()=>navigateScreen(action));else if(action==='calculate')perform(async()=>{if(await taskUI.save())await calculateCriteria(taskUI.current.task_id);});else if(action==='guide'&&state.page==='S05')photoUI.showGuide();else perform(()=>analysisUI.guide(action));});
document.addEventListener('loco-guide-preference-change',event=>perform(()=>analysisUI.preferences(event.detail)));
const taskUI=new TaskWorkspace({api,notify,confirmDeletion,onOpenPhotos:taskId=>photos(taskId),onOpenPage:(id,taskId)=>navigateScreen(id,taskId),onCalculate:calculateCriteria,onScreenChange:screen=>{const id=screen==='conditions'?'S04':'S03';if(state.page!==id)page(id);},onError:showError,onChanged:refresh,onBack:()=>page('S02'),surveyTitle:()=>state.details.get(state.selected)?.title||'',setTitle:(title,description)=>{$('#title').textContent=title;$('.page-title p').textContent=description;}});
const photoUI=new PhotoWorkspace({api,notify,clearError,onError:showError,onBack:()=>tasks('conditions',true),onAnalyze:startPhotoAnalysis,onOpenPage:(id,taskId)=>navigateScreen(id,taskId,true),surveyTitle:()=>state.details.get(state.selected)?.title||'',setTitle:(title,description)=>{$('#title').textContent=title;$('.page-title p').textContent=description;},onSaved:task=>{if(taskUI.current?.task_id===task.task_id){taskUI.current=structuredClone(task);taskUI.saved=structuredClone(task);taskUI.buffers.delete(task.task_id);}}});
const dashboardUI=new DashboardWorkspace({api,onError:showError,onNew:newSurvey,onList:()=>page('S02'),onSample:()=>perform(async()=>{if(state.busy)return;state.busy=true;try{const {survey}=await createSampleSurvey(api);state.selected=survey.survey_id;await refresh();notify('샘플 조사를 만들었습니다. 합성 예시이며 실제 자료가 아닙니다.');}finally{state.busy=false;}}),onOpen:(surveyId,taskId)=>perform(async()=>{await selectSurvey(surveyId);if(taskId){await tasks('conditions',false,taskId);}else page('S02');window.scrollTo({top:0});})});
const analysisUI=createAnalysisWorkspace({element:$('#analysis-workspace'),api,notify,onLeave:id=>navigateScreen(id),onPhotoInput:async({taskId,path,slotNo})=>{await photos(taskId);photoUI.focusInput(path,slotNo);},onInput:async({taskId,path})=>{await tasks();if(taskUI.current?.task_id!==taskId)await taskUI.load(taskId);await taskUI.focusInput(path);},onNavigate:(id,info)=>{page(id);$('#title').textContent=info[0];$('.page-title p').textContent=info[2];}});
const databaseLocation=new DatabaseLocation({element:$('#database-location'),bridge:window.loco,noticeElement:$('#environment')});
databaseLocation.initialize();
document.addEventListener('click',event=>{
  if(event.target.closest('[data-db-retry]')){databaseLocation.initialize();return;}
  if(!event.target.closest('[data-open-database-location]'))return;
  $('#database-settings').showModal();
  databaseLocation.initialize();
});
$('#close-database-settings').addEventListener('click',()=>$('#database-settings').close());
const quickUI=new QuickFlow({host:$('#quick-workspace'),toolbar:$('#quick-toolbar'),api,notify,onError:showError,onScreenChange:label=>{if(document.body.classList.contains('quick-mode')){$('#breadcrumb-mode').textContent='간편 분석';$('#breadcrumb-page').textContent=label;}},onOpenDetail:({surveyId,taskId})=>perform(async()=>{setMode('detail');await refresh();if(surveyId){await selectSurvey(surveyId);await tasks('conditions',false,taskId);}})});
function setMode(mode){
  const quick=mode==='quick';
  document.body.classList.toggle('quick-mode',quick);$('#quick-workspace').hidden=!quick;
  $('#mode-toggle').textContent=quick?'고급 편집':'간편 화면';
  if(quick){$('#title').textContent='사진으로 빠른 분석';$('.page-title p').textContent='';quickUI.open();}
  else{page('S01');if(window.loco)perform(refresh);}
}
$('#mode-toggle').addEventListener('click',()=>setMode(document.body.classList.contains('quick-mode')?'detail':'quick'));
document.addEventListener('keydown',event=>{if(!(event.ctrlKey||event.metaKey)||event.key.toLowerCase()!=='s')return;event.preventDefault();if(document.body.classList.contains('quick-mode')||!['S03','S04'].includes(state.page))return;perform(async()=>{if(await taskUI.save())notify('작업을 저장했어요.');});});
fill(blank());page('S01');rows();setMode('quick');
if(!window.loco&&new URLSearchParams(location.search).get('screen')==='photos'){page('S05');photoUI.preview();}
if(!window.loco&&['task','conditions'].includes(new URLSearchParams(location.search).get('screen'))){taskUI.preview();taskUI.screen=new URLSearchParams(location.search).get('screen')==='conditions'?'conditions':'info';taskUI.render();}
if(!window.loco){$('#connection').textContent='브라우저 미리보기';}else perform(async()=>{await refresh();await analysisUI.initialize();});
