const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const vm=require('node:vm');
async function main(){
 const {SCREENS,isAnalysisScreen}=await import('../frontend/screens.js');
 assert.deepEqual(SCREENS.map(s=>s.id),Array.from({length:10},(_,i)=>'S'+String(i+1).padStart(2,'0')));
 assert.equal(SCREENS.find(s=>s.id==='S04').editor,'conditions');
 assert.equal(SCREENS.find(s=>s.id==='S05').view,'photo');
 assert.equal(isAnalysisScreen('S09'),true);assert.equal(isAnalysisScreen('S10'),true);assert.equal(isAnalysisScreen('S04'),false);
 const {createController}=await import('../frontend/analysis/controller.js');
 const {createAnalysisState}=await import('../frontend/analysis/state.js');
 global.document={addEventListener(){}};
 const {SCREEN_INFO}=await import('../frontend/screens.js');
 const nodes={'#content':{innerHTML:''},'#overlay-root':{innerHTML:''}};
 const visited=[];
 const host={element:{addEventListener(){},querySelectorAll(){return [];}},active:true,onNavigate(id){visited.push(id);},async onLeave(id){await Promise.resolve();visited.push('leave:'+id);}};
 const s=createAnalysisState();
 const ctx={host,s,pages:SCREEN_INFO,$:key=>nodes[key],api:async method=>{assert.equal(method,'get_settings');return {};},actions:{},toast(message){throw Error(message);},syncGuidePreferences(){},progressPage:()=>'<p>progress view</p>',settingsPage:()=>'<p>settings view</p>'};
 const controller=createController(ctx);
 await controller.open({page:'S09',surveyId:null});assert.match(nodes['#content'].innerHTML,/progress view/);
 await controller.open({page:'S10',surveyId:null});assert.match(nodes['#content'].innerHTML,/settings view/);
 await controller.open({page:'S04',surveyId:null});assert.equal(visited.at(-1),'leave:S04');
 await controller.open({page:'S05',surveyId:null});assert.equal(visited.at(-1),'leave:S05');
 const {events}=await import('../frontend/task/events.js');
 const {inputs}=await import('../frontend/task/inputs.js');
 // A delayed read still supplies data, but cannot render over the user's newer page.
 for(const stillOwnsPage of [false,true]){
  let release,started;const pending=new Promise(resolve=>release=resolve),loading=new Promise(resolve=>started=resolve),renders=[];let current=true;
  const workspace={...inputs,current:null,saved:null,items:[],surveyId:null,buffers:new Map(),remember(){},api:async method=>{if(method==='list_tasks')return [{task_id:7}];started();return pending;},render(){renders.push(this.screen);}};
  const opening=workspace.open(2,{shouldRender:()=>current});
  await loading;current=stillOwnsPage;if(!current)workspace.current={task_id:99,task_name:'사용자가 새로 연 작업'};
  release({task:{task_id:7,task_name:'늦게 도착해도 보관되는 작업'}});const result=await opening;
  assert.equal(result.task_name,'늦게 도착해도 보관되는 작업');
  assert.equal(workspace.current.task_id,stillOwnsPage?7:99);assert.equal(renders.length,stillOwnsPage?2:0);
 }
 const calls=[];
 const editor={current:{task_id:7},saving:false,run(action){this.pending=action();},async save(){calls.push('save');return true;},async onCalculate(id){calls.push('calculate:'+id);},async onOpenPhotos(){throw Error('Direct input must not require photos');}};
 events.click.call(editor,{target:{closest:()=>({dataset:{do:'calculate'}})}});await editor.pending;
 assert.deepEqual(calls,['save','calculate:7']);
 editor.save=async()=>false;
 events.click.call(editor,{target:{closest:()=>({dataset:{do:'calculate'}})}});await editor.pending;
 assert.deepEqual(calls,['save','calculate:7']);
 const guide=fs.readFileSync(path.join(__dirname,'../docs/ui/loco-guide.js'),'utf8');
 const start=guide.indexOf('const PET_GUIDES'),end=guide.indexOf('const PET_ANSWERS');
 const guides=vm.runInNewContext(guide.slice(start,end)+';PET_GUIDES');
 for(const screen of SCREENS)assert.ok(guides[screen.id],screen.id+' missing guide');
 assert.equal(guides.S05.action,'guide');assert.equal(guides.S09.action,'S06');assert.equal(guides.S10.action,'quiet');
 assert.doesNotMatch(guides.S05.message,/바닥면|15장|3회/);
 console.log('PASS ten documented screens, progress/settings dispatch, awaited editor/photo navigation, direct-input save-before-calculate, and guide alignment');
}
main().catch(error=>{console.error(error);process.exitCode=1;});
