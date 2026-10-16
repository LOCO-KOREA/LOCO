/* Workspace composition; rendering, input state and events are independent modules. */
import {definitions} from './task/definitions.js';
import {defaults} from './task/defaults.js';
import {inputs} from './task/inputs.js';
import {views} from './task/views.js';
import {events} from './task/events.js';
export class TaskWorkspace {
 constructor(options){Object.assign(this,options);this.host=document.querySelector('#task-workspace');this.items=[];this.current=null;this.saved=null;this.surveyId=null;this.screen='info';this.criterion=1;this.buffers=new Map();this.saving=false;this.host.addEventListener('click',e=>this.click(e));this.host.addEventListener('input',e=>this.input(e));this.host.addEventListener('change',e=>this.input(e));this.host.addEventListener('submit',e=>{e.preventDefault();this.run(()=>this.save());});}
}
Object.assign(TaskWorkspace,definitions);
Object.assign(TaskWorkspace.prototype,defaults, inputs, views, events);
