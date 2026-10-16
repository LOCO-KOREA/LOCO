/* Async analysis UI regressions against the actual repository modules.
 * Uses fake DOM nodes, local in-memory API doubles and fake timers only.
 * No Electron, native file picker, external API, filesystem fixtures or DB is
 * started. A failed assertion exits nonzero; this is not real renderer E2E. */
const assert=require('node:assert/strict');
const path=require('node:path');
const {pathToFileURL}=require('node:url');
const deferred=()=>{let resolve,reject;const promise=new Promise((a,b)=>{resolve=a;reject=b;});return {promise,resolve,reject};};
const tick=()=>new Promise(resolve=>setImmediate(resolve));
class Timers{
 constructor(){this.next=1;this.entries=new Map();this.cleared=[];}
 setTimeout(fn){const id=this.next++;this.entries.set(id,fn);return id;}
 clearTimeout(id){this.entries.delete(id);this.cleared.push(id);}
}
function node(dataset={}){
 const attrs=new Map();return {dataset,disabled:false,isConnected:true,innerHTML:'',value:'',checked:false,
 hasAttribute(name){return attrs.has(name)||name==='data-request-busy'&&this.dataset.requestBusy!==undefined;},
 setAttribute(name,value){attrs.set(name,value);},removeAttribute(name){attrs.delete(name);},focus(){},scrollIntoView(){}};
}
async function fixture(){
 const base=path.join(__dirname,'..','frontend','analysis');
 const [{createAnalysisState},{createActions},{createController}]=await Promise.all(['state','actions','controller'].map(name=>import(pathToFileURL(path.join(base,name+'.js')).href)));
 const timers=new Timers();global.clearInterval=id=>timers.clearTimeout(id);global.setInterval=fn=>timers.setTimeout(fn);
 global.document={addEventListener(){},querySelector(){return node();}};
 global.window={loco:{choose_export_destination:async()=>'/fake/report.xlsx'}};
 const events={},buttons=['start-analysis','generate-explanation','save-manual','apply-candidates','cancel-analysis'].map(action=>node({action}));
 const element={addEventListener(name,fn){events[name]=fn;},querySelectorAll(){return buttons;}};
 const nodes=new Map();const $=key=>{if(!nodes.has(key))nodes.set(key,node());return nodes.get(key);};
 const settings={analysis:{pose_model:{confidence_min:.5},posture_profile:{}},ui:{loco_visible:true,loco_mode:'normal'},gpt_enabled:false,gpt_model:''};
 const surveys={1:{survey_id:1,title:'A survey',investigator:'tester',metadata_revision:1},2:{survey_id:2,title:'B survey',investigator:'tester',metadata_revision:1}};
 const bundles={},histories={};
 for(const id of [1,2]){
  const task={task_id:id,survey_id:1,task_name:'task'+id,input_revision:1,latest_analysis_id:id*11,manual:[],conditions:{worker_code:'worker',method_description:'work',work_height_cm:1},capture:{slots:[{slot_no:1,photo_id:id,analysis_target:true}]},analysis_scope:{judgment:true,pose:true,tags:true,reba:true}};
  bundles[id]={task,photos:[],settings:settings.analysis};
  histories[id]=[{analysis_id:id*11,task_id:id,input_revision:1,status:'FINISHED',snapshot:{capture:structuredClone(task.capture),conditions:structuredClone(task.conditions),settings:settings.analysis},pose:null,reba:null,judgment:{judgments:[{criterion_no:1,investigator:{status:null,evidence:{text:''}}}]},ai:[{text_id:'old'+id,purpose:'TASK_EXPLANATION',generated_text:'old',edited_text:'edit'}],notes:[]}];
 }
 const calls=[],hooks={};let renders=0;
 async function api(method,params={}){
  calls.push({method,params:structuredClone(params)});
  if(hooks[method])return hooks[method](params);
  if(method==='get_settings'||method==='update_settings')return structuredClone(settings);
  if(method==='get_survey')return structuredClone(surveys[params.survey_id]);
  if(method==='list_tasks')return Object.values(bundles).map(b=>structuredClone(b.task));
  if(method==='get_task')return structuredClone(bundles[params.task_id]);
  if(method==='list_analysis_history')return structuredClone(histories[params.task_id]);
  if(method==='get_analysis')return structuredClone(Object.values(histories).flat().find(a=>a.analysis_id===params.analysis_id));
  if(method==='preview_excel')return {};
  if(method==='set_survey_review')return structuredClone(surveys[params.survey_id]);
  if(method==='set_manual_values'||method==='set_capture'||method==='cancel_analysis')return {message:'ok'};
  if(method==='edit_ai_text'||method==='apply_ai_text')return {};
  if(method==='export_excel')return {file_path:params.spec.destination};
  throw Error('Unhandled test double: '+method);
 }
 const host={element,active:true,api,notify(message){messages.push(message);},onNavigate(){renders++;},onLeave(){host.active=false;},onInput:async()=>{},onPhotoInput:async()=>{}};
 const messages=[],s=createAnalysisState();
 Object.assign(s,{page:'S06',survey:structuredClone(surveys[1]),tasks:Object.values(bundles).map(b=>b.task),bundle:structuredClone(bundles[1]),analysis:structuredClone(histories[1][0]),selectedAnalysis:11,aiTextId:'old1',settings:structuredClone(settings),slot:1,exportSelections:{1:11},comparisonBefore:11,comparisonAfter:22,comparisonNote:'original'});
 const ctx={host,s,$,$$:selector=>selector==='[data-manual-use]:checked'?[{dataset:{manualUse:'COMMON.trunk_base'}}]:selector==='[data-auto-candidate]:checked'?[{dataset:{autoCandidate:'COMMON.trunk_base'}}]:[],api,toast:m=>messages.push(m),pages:{S05:['progress'],S06:['reba'],S07:['criteria'],S08:['export'],S09:['settings']},statusNames:{},options:()=>'',card:()=>'',modal:()=>{},field:()=>'',select:()=>'',e:String,number:()=>.5,text:key=>$(key).value||'',inputLabel:String,LocoReview:{basis:()=>null},selectedIds:()=>Object.values(s.exportSelections).filter(Boolean),comparisonSpecs:()=>[{before_analysis_id:s.comparisonBefore,after_analysis_id:s.comparisonAfter,note:s.comparisonNote}],timers,
  progressPage:()=>'',rebaPage:()=>'',criteriaPage:()=>'',exportPage:()=>'',settingsPage:()=>'',drawPhoto:()=>{}};
 $('[data-manual="COMMON.trunk_base"]').value='2';$('#include-representative').checked=true;
 Object.assign(ctx,createActions(ctx));const workspace=createController(ctx);
 const choose=async id=>events.change({target:{id:'task-choice',value:String(id),dataset:{}}});
 const changeAI=async(field,value)=>events.change({target:{id:'',value,dataset:{field}}});
 const input=()=>events.input({target:{id:'explanation-text',value:'unsaved next draft',dataset:{}}});
 return {s,ctx,workspace,api,calls,hooks,host,events,$,buttons,timers,messages,bundles,histories,surveys,choose,changeAI,input,renders:()=>renders};
}
const cases=[];
function test(name,run){cases.push({name,run});}

for(const page of ['S06','S09'])test('first open from S01 reaches '+page,async h=>{
 h.s.page='S01';h.s.survey=null;h.s.bundle=null;h.s.analysis=null;h.s.selectedAnalysis=null;
 await h.workspace.open({page,surveyId:1,taskId:1});
 assert.equal(h.s.page,page);assert.equal(h.s.bundle.task.task_id,1);assert.ok(h.renders()>0);
});

test('same AI generation double click is one request',async h=>{
 const d=deferred();h.hooks.generate_ai_text=()=>d.promise;
 const p=h.ctx.actions['generate-explanation'](),q=h.ctx.actions['generate-explanation']();await tick();
 const count=h.calls.filter(x=>x.method==='generate_ai_text').length;
 d.resolve({text:{text_id:'new1'}});await Promise.all([p,q]);assert.equal(count,1);
});
test('late A AI response cannot select text on B',async h=>{
 const d=deferred();h.hooks.generate_ai_text=()=>d.promise;
 const p=h.ctx.actions['generate-explanation']();await h.choose(2);const before=h.renders(),messages=h.messages.length;
 d.resolve({text:{text_id:'generated-for-A'}});await p;
 assert.equal(h.s.bundle.task.task_id,2);assert.notEqual(h.s.aiTextId,'generated-for-A');assert.equal(h.renders(),before);assert.equal(h.messages.length,messages);
});
test('AI purpose and explicit history choice outrank old generation',async h=>{
 const d=deferred();h.hooks.generate_ai_text=()=>d.promise;
 const p=h.ctx.actions['generate-explanation']();await h.changeAI('ai-purpose','IMPROVEMENT_ADVICE');await h.changeAI('ai-choice','chosen-other');
 const before=h.renders();d.resolve({text:{text_id:'generated-for-old-purpose'}});await p;
 assert.equal(h.s.aiTextId,'chosen-other');assert.equal(h.renders(),before);
});
test('A to B to A does not revive an old start navigation',async h=>{
 const d=deferred();h.hooks.start_analysis=()=>d.promise;
 const p=h.ctx.actions['start-analysis']();await h.choose(2);await h.choose(1);const before=h.renders();
 d.resolve({analysis_id:101,task_id:1,status:'RUNNING'});await p;
 assert.equal(h.s.page,'S06');assert.equal(h.renders(),before);
});
test('refreshTask commits captured task only if still selected',async h=>{
 const d=deferred();let first=true;
 h.hooks.get_task=params=>{if(params.task_id===1&&first){first=false;return d.promise;}return structuredClone(h.bundles[params.task_id]);};
 const p=h.ctx.refreshTask();await h.choose(2);d.resolve(structuredClone(h.bundles[1]));await p;
 assert.equal(h.s.bundle.task.task_id,2);assert.equal(h.s.analysis.task_id,2);
});
test('poll requests are single flight',async h=>{
 const d=deferred();h.s.page='S05';h.s.analysis.status='RUNNING';h.hooks.get_analysis=()=>d.promise;
 h.ctx.startPoll?.();const p=h.ctx.pollAnalysis(),q=h.ctx.pollAnalysis();await tick();
 const count=h.calls.filter(x=>x.method==='get_analysis').length;
 d.resolve({...structuredClone(h.histories[1][0]),status:'FINISHED'});await Promise.all([p,q]);assert.equal(count,1);
});
test('old poll completion cannot stop new task poll or overwrite it',async h=>{
 const d=deferred();h.s.page='S05';h.s.analysis.status='RUNNING';h.histories[2][0].status='RUNNING';
 h.hooks.get_analysis=()=>d.promise;h.ctx.startPoll?.();const p=h.ctx.pollAnalysis();await h.choose(2);
 const owner=h.s.pollOwner,timer=h.s.poll;d.resolve({...structuredClone(h.histories[1][0]),status:'FINISHED'});await p;
 assert.equal(h.s.analysis.task_id,2);
 {assert.equal(h.s.pollOwner,owner);assert.equal(h.s.poll,timer);assert.ok(h.timers.entries.has(timer));}
});
test('manual save and candidate apply share one write group',async h=>{
 const d=deferred();h.hooks.set_manual_values=()=>d.promise;
 h.s.analysis.reba={slots:[{slot_no:1,candidates:[{scope:'COMMON',field:'trunk_base',proposed_value:2,angles:[],min_confidence:.9}]}]};
 const p=h.ctx.actions['save-manual']();const q=h.ctx.actions['apply-candidates']();await tick();
 const count=h.calls.filter(x=>x.method==='set_manual_values').length;
 h.hooks.recalculate_reba=()=>structuredClone(h.histories[1][0]);d.resolve({});await Promise.all([p,q]);assert.equal(count,1);
});
test('unsaved explanation edits suppress old generation refresh',async h=>{
 const d=deferred();h.hooks.generate_ai_text=()=>d.promise;
 const p=h.ctx.actions['generate-explanation']();h.input();const before=h.renders();
 d.resolve({text:{text_id:'generated'}});await p;assert.equal(h.renders(),before);
});
test('unsaved next manual draft survives earlier manual save completion',async h=>{
 const d=deferred();h.hooks.set_manual_values=()=>d.promise;h.hooks.recalculate_reba=()=>structuredClone(h.histories[1][0]);
 const p=h.ctx.actions['save-manual']();h.events.input({target:{id:'',dataset:{manual:'COMMON.trunk_base'},value:'3'}});const before=h.renders();
 d.resolve({});await p;assert.equal(h.renders(),before);assert.equal(h.calls.find(x=>x.method==='set_manual_values').params.manual[0].value,2);
});
test('render auto-selected AI does not falsely stale a generation request',async h=>{
 const d=deferred();h.hooks.generate_ai_text=()=>d.promise;h.s.aiTextId=null;
 h.ctx.rebaPage=()=>{if(!h.s.aiTextId)h.s.aiTextId='old1';return '';};
 const p=h.ctx.actions['generate-explanation']();h.ctx.render();d.resolve({text:{text_id:'new-auto'}});await p;assert.equal(h.s.aiTextId,'new-auto');
});
test('late A error is not shown on B',async h=>{
 const d=deferred();h.hooks.select_representative=()=>d.promise;
 const p=h.ctx.actions.representative({dataset:{slot:'1'}});await h.choose(2);const count=h.messages.length;
 d.reject(Error('A-only failure'));try{await p;}catch(error){h.messages.push(error.message);}assert.equal(h.messages.length,count);
});
test('newest refresh wins within the same task',async h=>{
 const d=deferred();let first=true;h.hooks.get_task=()=>{if(first){first=false;return d.promise;}const x=structuredClone(h.bundles[1]);x.task.task_name='newer';return x;};
 const old=h.ctx.refreshTask();await h.ctx.refreshTask();d.resolve(structuredClone(h.bundles[1]));await old;assert.equal(h.s.bundle.task.task_name,'newer');
});
test('AI explicit selection survives a delayed representative save',async h=>{
 const d=deferred();h.hooks.select_representative=()=>d.promise;
 const p=h.ctx.actions.representative({dataset:{slot:'1'}});await h.changeAI('ai-choice','chosen-other');const count=h.renders();
 d.resolve(structuredClone(h.histories[1][0]));await p;assert.equal(h.renders(),count);assert.equal(h.s.aiTextId,'chosen-other');
});
test('failure releases only the matching write and allows retry',async h=>{
 let count=0;h.hooks.generate_ai_text=()=>{count++;if(count===1)return Promise.reject(Error('injected'));return {text:{text_id:'retry'}};};
 try{await h.ctx.actions['generate-explanation']();}catch{}
 await h.ctx.actions['generate-explanation']();assert.equal(count,2);assert.equal(h.s.aiTextId,'retry');
});
test('export captures survey and selection before native dialog awaits',async h=>{
 const d=deferred();window.loco.choose_export_destination=()=>d.promise;
 const p=h.ctx.actions.export();await h.choose(2);h.s.survey=structuredClone(h.surveys[2]);h.s.exportSelections={2:22};h.s.comparisonNote='changed';
 d.resolve('/fake/new.xlsx');await p;
 const request=h.calls.find(x=>x.method==='export_excel').params;assert.equal(request.survey_id,1);assert.deepEqual(request.spec.analysis_ids,[11]);assert.equal(request.spec.comparisons[0].note,'original');
});
test('representative late response preserves B selection',async h=>{
 const d=deferred();h.hooks.select_representative=()=>d.promise;
 const p=h.ctx.actions.representative({dataset:{slot:'1'}});await h.choose(2);const before=h.renders();
 d.resolve(structuredClone(h.histories[1][0]));await p;assert.equal(h.s.analysis.task_id,2);assert.equal(h.renders(),before);
});
test('task load blocks old visible writes but still accepts cancellation',async h=>{
 const d=deferred();h.hooks.get_task=params=>params.task_id===2?d.promise:structuredClone(h.bundles[1]);
 const p=h.choose(2);await tick();const before=h.calls.filter(x=>x.method==='select_representative').length;
 h.hooks.select_representative=()=>structuredClone(h.histories[1][0]);
 await h.ctx.actions.representative({dataset:{slot:'1'}});await h.ctx.actions['cancel-analysis']();
 const after=h.calls.filter(x=>x.method==='select_representative').length;
 d.resolve(structuredClone(h.bundles[2]));await p;
 assert.equal(after,before);assert.ok(h.calls.some(x=>x.method==='cancel_analysis'&&x.params.analysis_id===11));
});
test('RUNNING start remains owned across handle and view round trip',async h=>{
 h.hooks.start_analysis=()=>{const result={...structuredClone(h.histories[1][0]),analysis_id:101,status:'RUNNING'};h.histories[1].unshift(result);h.bundles[1].task.latest_analysis_id=101;return {analysis_id:101,task_id:1,status:'RUNNING'};};
 await h.ctx.actions['start-analysis']();await h.choose(2);await h.choose(1);await h.ctx.actions['start-analysis']();
 assert.equal(h.calls.filter(x=>x.method==='start_analysis').length,1);
});
test('open failure clears only its own loading marker and allows retry',async h=>{
 let first=true;h.hooks.get_settings=()=>{if(first){first=false;return Promise.reject(Error('settings failed'));}return structuredClone(h.s.settings);};
 try{await h.workspace.open({page:'S06',surveyId:1,taskId:2});}catch{}
 assert.equal(h.s.pendingSelection,null);
 await h.workspace.open({page:'S06',surveyId:1,taskId:2});assert.equal(h.s.bundle.task.task_id,2);
 h.hooks.select_representative=()=>structuredClone(h.histories[2][0]);
 await h.ctx.actions.representative({dataset:{slot:'1'}});assert.ok(h.calls.some(x=>x.method==='select_representative'&&x.params.analysis_id===22));
});
test('old failed open does not clear a newer open loading marker',async h=>{
 const old=deferred(),next=deferred();let call=0;h.hooks.get_settings=()=>++call===1?old.promise:next.promise;
 const p=h.workspace.open({page:'S06',surveyId:1,taskId:1}).catch(()=>{});
 const q=h.workspace.open({page:'S06',surveyId:1,taskId:2});await tick();
 const marker=h.s.pendingSelection;old.reject(Error('old failed'));await p;
 {assert.equal(h.s.pendingSelection,marker);assert.equal(marker.taskId,2);}
 next.resolve(structuredClone(h.s.settings));await q;assert.equal(h.s.bundle.task.task_id,2);
});
for(const first of ['tags','judgments'])test('latest accepted creation wins completion order '+first,async h=>{
 const a=deferred(),b=deferred();
 function result(id){const r={...structuredClone(h.histories[1][0]),analysis_id:id};h.histories[1].unshift(r);h.bundles[1].task.latest_analysis_id=id;return r;}
 let tagResult,judgmentResult;
 h.hooks.recalculate_tags=()=>{tagResult=result(101);return a.promise;};h.hooks.recalculate_judgments=()=>{judgmentResult=result(102);return b.promise;};
 const p=h.ctx.actions['recalculate-tags'](),q=h.ctx.actions['calculate-criteria']();await tick();
 if(first==='tags'){a.resolve(tagResult);await p;b.resolve(judgmentResult);await q;}
 else{b.resolve(judgmentResult);await q;a.resolve(tagResult);await p;}
 assert.equal(h.s.selectedAnalysis,102);assert.equal(h.s.page,'S07');
});

(async()=>{
 const results=[];
 for(const item of cases){
  const h=await fixture();let error=null;
  try{await item.run(h);}catch(e){error=e.stack;}
  results.push({name:item.name,passed:!error,error});
 }
 console.log(JSON.stringify({passed:results.filter(x=>x.passed).length,total:cases.length},null,2));
 for(const row of results.filter(x=>!x.passed))console.error(row.name+'\n'+row.error);
 process.exitCode=results.some(x=>!x.passed)?1:0;
})().catch(error=>{console.error(error);process.exitCode=1;});
