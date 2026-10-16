/* ui; dependencies are composed by analysis-workspace.js. */
export function createUi(ctx){
 const {host, s, statusNames}=ctx;
const $=selector=>selector==='loco-guide'?document.querySelector(selector):host.element.querySelector(selector), $$=selector=>[...host.element.querySelectorAll(selector)];

const e=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));

const fmt=value=>value===null||value===undefined?'미계산':e(value);

const badge=(value)=>`<span class="badge ${['VALID','COMPLETE','CURRENT','REVIEWED_CURRENT'].includes(value)?'good':['NEEDS_INPUT','INCOMPLETE','ERROR','FAILED'].includes(value)?'error':'warn'}">${e(statusNames[value]||value||'미계산')}</span>`;

const ev=()=>({source:null,text:null,observed_at:null});

function toast(message){host.notify(message);}

async function api(method,params={}){return host.api(method,params);}

function options(values,value){return values.map(item=>{const [key,label]=Array.isArray(item)?item:[item,item];return `<option value="${e(key)}" ${String(value??'')===String(key)?'selected':''}>${e(label)}</option>`;}).join('');}

function field(label,path,value,type='text'){return `<label>${e(label)}<input data-field="${e(path)}" type="${type}" value="${e(value)}" ${type==='number'?'step="any"':''}></label>`;}

function select(label,path,value,values){return `<label>${e(label)}<select data-field="${e(path)}">${options(values,value)}</select></label>`;}

function number(path){const input=$(`[data-field="${path}"]`);return input?.value===''?null:Number(input?.value);}

function text(path){return $(`[data-field="${path}"]`)?.value??'';}

function card(title,body,actions=''){return `<section class="card"><div class="card-head"><h2>${title}</h2><div class="toolbar">${actions}</div></div>${body}</section>`;}

function empty(message,button=''){return `<div class="card empty"><div class="symbol">◇</div><h2>${message}</h2><p>상단 메뉴로 이동하거나 조사와 작업을 선택해 주세요.</p>${button}</div>`;}

function metric(label,value,unit=''){return `<div class="metric"><span class="label">${label}</span><strong>${fmt(value)}<small>${unit}</small></strong></div>`;}

function modal(title,body){$('#overlay-root').innerHTML=`<div class="modal-backdrop"><div class="modal"><h2>${e(title)}</h2>${body}<div class="toolbar"><button data-action="close-modal">닫기</button></div></div></div>`;}

function context(){return `<div class="note">${e(s.survey?.title||'조사 미선택')} ${s.bundle?' / '+e(s.bundle.task.task_name)+' · 입력 r'+s.bundle.task.input_revision:''}</div>`;}

function selectedIds(){return Object.values(s.exportSelections).filter(Boolean).map(Number);}

function comparisonSpecs(){const before=Number(s.comparisonBefore),after=Number(s.comparisonAfter);return before&&after&&before!==after?[{before_analysis_id:before,after_analysis_id:after,note:s.comparisonNote||null}]:[];}

 return {$, e, fmt, badge, ev, toast, api, options, field, select, number, text, card, empty, metric, modal, context, selectedIds, comparisonSpecs, $$};
}
