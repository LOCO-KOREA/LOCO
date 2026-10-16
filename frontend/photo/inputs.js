export const inputs={
esc(v){return String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));},
emptyObservation(){return {load_state:'UNKNOWN',measured_load_kg:null,single_person:'UNKNOWN',full_frame:'UNKNOWN',normal_work:'UNKNOWN',evidence:{source:null,text:null,observed_at:null}};},
run(action){this.pending=this.pending.then(()=>{this.clearError();return action();}).catch(error=>this.onError(error));return this.pending;},
async flush(){await this.pending;if(this.task?.task_id)await this.save();},
async open(taskId){const bundle=await this.api('get_task',{task_id:taskId});if(this.task?.task_id!==taskId){this.selected=1;this.failures=[];this.previews.clear();}this.task=bundle.task;this.capture=structuredClone(bundle.task.capture);this.photos=bundle.photos;this.render();},
focusInput(path,slotNo){
  this.selected=this.capture.slots.find(s=>s.slot_no===slotNo)?.slot_no??this.capture.slots[0]?.slot_no;
  this.render();
  let field=String(path||'').split('.').at(-1);
  if(field==='photo_id'||field==='duplicate_photo_id'){this.host.querySelector(`[data-assign-slot="${this.selected}"]`)?.focus();return;}
  if(field==='file_path'){this.showDetails();this.dialog.querySelector('#photo-path')?.focus();return;}
  if(field==='effective_load_kg')field=this.slot()?.observation.load_state==='MEASURED'?'measured_load_kg':'load_state';
  if(field==='observation')field='single_person';
  const node=[...this.host.querySelectorAll('[data-photo-field]')].find(n=>n.dataset.photoField===field)||this.host.querySelector('[data-target-slot]')||this.host.querySelector('[data-photo-action="import"]');
  node?.scrollIntoView({block:'center'});node?.focus();
 },
preview(){this.task={task_id:null,task_name:'',capture:{protocol:'GENERAL_STILLS_V1',slots:[]}};this.capture=structuredClone(this.task.capture);this.photos=[];this.render();},
dirty(){return JSON.stringify(this.capture)!==JSON.stringify(this.task.capture);},
status(){const node=this.host.querySelector('[data-photo-status]');if(node)node.textContent=!this.task.task_id?'화면 미리보기':this.dirty()?'● 저장 전 변경 사항':'● 저장됨';},
slot(){return this.capture.slots.find(s=>s.slot_no===this.selected)||null;},
photo(id){return this.photos.find(p=>p.photo_id===id);},
async save(){if(!this.task?.task_id)throw Error('조사와 작업을 저장한 뒤 사진을 사용할 수 있습니다.');if(!this.dirty())return;const sent=structuredClone(this.capture);const task=await this.api('set_capture',{task_id:this.task.task_id,capture:sent});if(JSON.stringify(this.capture)===JSON.stringify(sent))this.capture=structuredClone(task.capture);this.task=task;this.onSaved(task);this.status();},
async assign(no,id){const s=this.capture.slots.find(x=>x.slot_no===no);this.selected=no;if(s.photo_id!==id){s.photo_id=id;s.side_view_verified='UNKNOWN';s.observation=this.emptyObservation();if(!id)s.analysis_target=false;}this.render();if(this.task.task_id)await this.save();},
async choosePhotos(){if(!window.loco)throw Error('사진 선택은 Electron 앱에서 사용할 수 있습니다.');const paths=await window.loco.choose_photo_paths();if(paths.length)await this.importPaths(paths);},
async importPaths(paths){if(!this.task?.task_id)throw Error('작업을 먼저 저장한 뒤 사진을 등록하세요.');const report=await this.api('import_photos',{task_id:this.task.task_id,file_paths:paths});this.photos.push(...report.added);this.failures=report.unreadable.map(x=>`${x.file_path}: ${x.message}`);this.render();if(this.dialog.open)this.showCandidates(this.assignTarget);this.notify(`${report.added.length}장 등록했습니다. 분석 행에 직접 배정하세요.`);},
async remove(id){await this.save();await this.api('delete_photo',{photo_id:id});const b=await this.api('get_task',{task_id:this.task.task_id});this.task=b.task;this.capture=structuredClone(b.task.capture);this.photos=b.photos;this.onSaved(b.task);this.previews.delete(id);this.render();if(this.dialog.open)this.showCandidates(this.assignTarget);this.notify('사진 등록을 삭제했습니다. 원본 파일은 유지됩니다.');}
};
