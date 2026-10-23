import {definitions as TaskWorkspace} from './definitions.js';
export const inputs={
key(){return this.current?.task_id??`new:${this.surveyId}`;},
remember(){if(this.current){this.buffers.set(this.key(),structuredClone(this.current));(this.bufferBases??=new Map()).set(this.key(),structuredClone(this.saved));}},
resetSurvey(id){for(const [key,value]of this.buffers)if(key===`new:${id}`||value.survey_id===id)this.buffers.delete(key);if(this.surveyId===id){this.current=null;this.saved=null;this.items=[];this.surveyId=null;}},
async open(surveyId,{shouldRender=()=>true}={}){this.remember();const changed=this.surveyId!==surveyId;this.surveyId=surveyId;const items=await this.api('list_tasks',{survey_id:surveyId});if(!shouldRender())return items;this.items=items;const selected=changed?null:this.items.find(t=>t.task_id===this.current?.task_id);let loaded;if(selected||this.items.length)loaded=await this.load((selected||this.items[0]).task_id,false,{shouldRender});else{this.current=this.buffers.get(`new:${surveyId}`)||this.blank();this.saved=null;}if(!shouldRender())return loaded;this.screen='info';this.render();return this.current;},
preview(){this.surveyId=null;this.current=this.blank();this.saved=null;this.render();},
async load(id,remember=true,{shouldRender=()=>true}={}){
  if(remember)this.remember();
  const bundle=await this.api('get_task',{task_id:id}),buffer=this.buffers.get(id),base=this.bufferBases?.get(id);
  if(!shouldRender())return bundle.task;
  this.saved=bundle.task;this.current=structuredClone(bundle.task);
  if(buffer)for(const key of TaskWorkspace.editableKeys){
   if(!base||JSON.stringify(buffer[key])!==JSON.stringify(base[key]))this.current[key]=structuredClone(buffer[key]);
  }
  this.render();return this.current;
 },
write(path,value){const keys=path.split('.');let target=this.current;for(const key of keys.slice(0,-1))target=target[key];target[keys.at(-1)]=value;},
input(event){const node=event.target;if(node.dataset.aggregate){if(event.type!=='change')return;const [n]=node.dataset.aggregate.split(':').map(Number);const aggregate=n===9?this.current.legal.criteria[n-1].totals:this.current.legal.criteria[n-1].union;const ids=new Set(aggregate.row_ids);if(node.checked)ids.add(node.value);else ids.delete(node.value);aggregate.row_ids=[...ids];this.remember();this.dirtyStatus();return;}const path=node.dataset.path;if(!path)return;let value=node.type==='checkbox'?node.checked:node.type==='number'?(node.value===''?null:Number(node.value)):node.value;if(path.endsWith('.source'))value=value||null;if(path.endsWith('.observed_at'))value=value?new Date(value).toISOString():null;if(path.endsWith('.text'))value=value||null;this.write(path,value);this.remember();this.dirtyStatus();},
dirtyStatus(){const node=this.host.querySelector('#task-save-status');if(node)node.textContent=this.isDirty()?'● 저장 전 변경 사항':'● 저장됨';},
isDirty(){return !this.saved||['task_name','input_template','worker_count','conditions','legal','analysis_scope'].some(k=>JSON.stringify(this.current?.[k])!==JSON.stringify(this.saved[k]));},
async save(){
  if(this.saving)return false;if(!this.surveyId)throw Error('조사를 먼저 저장하거나 선택해 주세요.');
  this.saving=true;this.host.classList.add('task-host-busy');for(const control of this.host.querySelectorAll('input,select,textarea,button'))control.disabled=true;
  try{
   const desired=structuredClone(this.current);let saved;
   if(!desired.task_id){
    saved=await this.api('create_task',{survey_id:this.surveyId,draft:desired});
    this.buffers.delete(`new:${this.surveyId}`);this.bufferBases?.delete(`new:${this.surveyId}`);
   }else{
    const fresh=(await this.api('get_task',{task_id:desired.task_id})).task;
    const input=structuredClone(fresh);let changed=fresh.source_schema_version==='1.3';
    for(const key of TaskWorkspace.editableKeys){
     if(this.saved&&JSON.stringify(desired[key])===JSON.stringify(this.saved[key]))continue;
     if(this.saved&&JSON.stringify(fresh[key])!==JSON.stringify(this.saved[key])&&JSON.stringify(fresh[key])!==JSON.stringify(desired[key]))throw Error('다른 화면에서 같은 작업 항목이 변경되었습니다. 최신 작업을 다시 열어 확인하세요.');
     input[key]=structuredClone(desired[key]);changed=changed||JSON.stringify(input[key])!==JSON.stringify(fresh[key]);
    }
    saved=changed?await this.api('save_task_input',{task_id:desired.task_id,input,expected_revision:fresh.input_revision}):fresh;
   }
   this.buffers.delete(saved.task_id);this.bufferBases?.delete(saved.task_id);this.saved=saved;this.current=structuredClone(saved);
   this.items=await this.api('list_tasks',{survey_id:this.surveyId});await this.onChanged();this.render();this.notify('일반 작업과 11개 기준 입력을 저장했습니다.');return true;
  }catch(error){this.remember();throw error;}
  finally{this.saving=false;this.host.classList.remove('task-host-busy');for(const control of this.host.querySelectorAll('input,select,textarea,button'))control.disabled=false;}
 },
addRow(i){const id=crypto.randomUUID();const row={row_id:id,label:`조건 ${this.current.legal.criteria[i-1].rows.length+1}`,evidence:this.evidence()};const keys={6:['unsupported','UNKNOWN','pinch_mass_kg',null,'pinch_force_kg_equiv',null,'minutes',null],7:['unsupported','UNKNOWN','single_hand_mass_kg',null,'grip_force_kg_equiv',null,'minutes',null],8:['load_mass_kg',null,'lift_count_day',null],9:['load_mass_kg',null,'below_knee_count_day',null,'above_shoulder_count_day',null,'extended_arm_count_day',null,'union_count_day',null,'union_evidence',this.evidence()],10:['load_mass_kg',null,'lift_rate_min',null,'minutes',null],11:['impact_verified','UNKNOWN','impact_rate_hour',null,'minutes',null]}[i];for(let n=0;n<keys.length;n+=2)row[keys[n]]=keys[n+1];this.current.legal.criteria[i-1].rows.push(row);},
orderedCriteria(){return TaskWorkspace.templateOrder[this.current.input_template]||TaskWorkspace.templateOrder.GENERAL;},
async focusInput(path){
  const match=path.match(/criteria\.(\d+)|exposures\.(C(\d+)_\w+)/);
  if(match)this.criterion=Number(match[1]||match[3]);this.screen=(path.startsWith('conditions.')||path.startsWith('analysis_scope.'))?'info':'conditions';this.render();
  let targetPath=path.startsWith('legal.')?path:'legal.'+path;
  if(path.startsWith('conditions.')||path.startsWith('analysis_scope.'))targetPath=path;
  if(match?.[2]){
   const index=this.current.legal.exposures.findIndex(x=>x.condition_code===match[2]);
   targetPath=`legal.exposures.${index}.minutes`;
  }else if(match?.[1]){
   const index=Number(match[1])-1;targetPath=targetPath.replace(`criteria.${match[1]}.`,`criteria.${index}.`);
   const row=path.match(/\.rows\.([^.]+)\./);
   if(row){const ri=this.current.legal.criteria[index].rows.findIndex(x=>x.row_id===row[1]);targetPath=targetPath.replace(`.rows.${row[1]}.`,`.rows.${ri}.`);}
  }
  const input=[...this.host.querySelectorAll('[data-path]')].find(x=>x.dataset.path===targetPath);
  const aggregate=this.host.querySelector(`[data-aggregate="${this.criterion}:${this.criterion===9?'totals':'union'}"]`);
  const node=input||aggregate||this.host.querySelector('.criterion-detail');node?.scrollIntoView({behavior:'smooth',block:'center'});input?.focus();
 }
};
