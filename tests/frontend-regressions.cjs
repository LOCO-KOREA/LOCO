const fs=require('node:fs');
const vm=require('node:vm');
const assert=require('node:assert/strict');
const path=require('node:path');
let ReviewTaskWorkspace;
const clone=value=>structuredClone(value);
function setup(){
 const ui=Object.create(ReviewTaskWorkspace.prototype);
 Object.assign(ui,{surveyId:1,buffers:new Map(),saving:false,host:{classList:{add(){},remove(){}},querySelectorAll(){return [];}},render(){},async onChanged(){},notify(){}});
 const task={...ui.blank(),task_id:1,survey_id:1,input_revision:0};
 let db=clone(task),writes=0;
 ui.current=clone(task);ui.saved=clone(task);ui.items=[clone(task)];
 ui.api=async(method,p)=>{
  if(method==='get_task')return {task:clone(db)};
  if(method==='list_tasks')return [clone(db)];
  if(method==='save_task_input'){
   assert.equal(p.expected_revision,db.input_revision);writes++;
   db={...db,...clone(p.input),input_revision:db.input_revision+1};return clone(db);
  }
  throw Error(method);
 };
 return {ui,get:()=>db,set:value=>{db=value;},writes:()=>writes};
}
async function main(){
 ({TaskWorkspace:ReviewTaskWorkspace}=await import('../frontend/task-workspace.js'));
 await Promise.all(['photo-workspace','survey-intake','analysis-workspace','dashboard'].map(name=>import('../frontend/'+name+'.js')));
 console.log('PASS all workspace ES modules load without global constructor dependencies');
 const state=setup(),ui=state.ui;
 ui.current.conditions.hazard_factors='unsaved interview note';ui.remember();
 const current=clone(state.get());
 current.capture.slots=[{slot_no:7,photo_id:12,analysis_target:true,label:'new photo',observation:{load_state:'UNLOADED'}}];
 current.manual=[{slot_no:7,photo_id:12,scope:'COMMON',field:'trunk_base',value:2}];
 current.input_revision++;state.set(current);
 await ui.open(1);assert.deepEqual(ui.current.manual,current.manual);assert.deepEqual(ui.current.capture,current.capture);
 assert.equal(ui.current.conditions.hazard_factors,'unsaved interview note');
 await ui.save();assert.deepEqual(state.get().manual,current.manual);assert.deepEqual(state.get().capture,current.capture);
 assert.equal(state.get().conditions.hazard_factors,'unsaved interview note');
 console.log('PASS editor rebase preserves unsaved owned fields and newer photo/manual data');

 const concurrent=setup();concurrent.ui.current.task_name='local edit';
 concurrent.set({...concurrent.get(),task_name:'other editor',input_revision:1});
 await assert.rejects(()=>concurrent.ui.save(),/다른 화면/);assert.equal(concurrent.writes(),0);
 console.log('PASS conflicting edits are rejected before overwriting another editor');

 const original=clone(ui.current.legal);
 for(const template of Object.keys(ReviewTaskWorkspace.templateOrder)){
  ui.current.input_template=template;const order=ui.orderedCriteria();assert.equal(order.length,11);
  assert.deepEqual([...order].sort((a,b)=>a-b),Array.from({length:11},(_,i)=>i+1));
  assert.deepEqual(ui.current.legal,original);
 }
 assert.equal(ReviewTaskWorkspace.templateOrder.LIFTING[0],8);
 assert.equal(ReviewTaskWorkspace.templateOrder.OFFICE[0],1);
 console.log('PASS each template reorders all eleven questions without changing legal facts');
}
main().catch(error=>{console.error(error);process.exitCode=1;});
