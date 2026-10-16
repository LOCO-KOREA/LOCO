/* Workspace composition; rendering, input state and events are independent modules. */
import {inputs} from './photo/inputs.js';
import {views} from './photo/views.js';
import {events} from './photo/events.js';
import {details} from './photo/details.js';
export class PhotoWorkspace {
 constructor(options){Object.assign(this,options);this.host=document.querySelector('#photo-workspace');this.task=null;this.photos=[];this.capture=null;this.selected=1;this.previews=new Map();this.pending=Promise.resolve();this.failures=[];this.dialog=document.createElement('dialog');this.dialog.className='photo-dialog';document.body.append(this.dialog);this.host.addEventListener('click',e=>this.click(e));this.host.addEventListener('change',e=>this.change(e));this.dialog.addEventListener('click',e=>this.click(e));for(const target of [this.host,this.dialog]){target.addEventListener('dragover',e=>e.preventDefault());target.addEventListener('drop',e=>{e.preventDefault();const paths=[],missing=[];for(const file of e.dataTransfer.files){try{const path=window.loco?.path_for_file(file);if(path)paths.push(path);else missing.push(file.name);}catch{missing.push(file.name);}}this.run(async()=>{if(paths.length)await this.importPaths(paths);if(missing.length){this.failures.push(...missing.map(name=>`${name}: 경로를 읽지 못했습니다. 사진 추가 버튼을 이용하세요.`));this.render();}});});}}
}
Object.assign(PhotoWorkspace.prototype,inputs, views, events, details);
