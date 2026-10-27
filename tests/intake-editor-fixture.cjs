const assert=require('node:assert/strict');
const YES_NO=[{value:'YES',label:'예'},{value:'NO',label:'아니오'}];
const policy={quick_review_interval:5,default_condition:'default',text_limit:2400,optional_photo_destinations:['context','view','manual','load','load_kg','load_link']};
const field=(target,type,extra={})=>({identity:target+'@default',target,condition:'default',kind:'choice',label:target,text:target,choices:YES_NO,destination:{type},pending_input:true,...extra});
const pose=(scope,name,condition='photo:2',extra={})=>field(`manual.${scope}.${name}`,'manual',{identity:`manual.${scope}.${name}@${condition}`,condition,label:`${scope} 자세를 얼마나 드나요?`,photo_label:condition==='photo:2'?'오른쪽에서 찍은 사진':'다른 사진',destination:{type:'manual',scope,field:name},...extra});
const number=(target,unit='분',extra={})=>field(target,'criterion',{kind:'number',choices:[],unit,...extra});
const fact=(f,value,state='KNOWN',source='USER',extra={})=>({identity:f.identity,target:f.target,condition:f.condition,value,state,source,...extra});
async function setup(rows,facts=[],questions=[]) {
 const {AdaptiveIntake}=await import('../frontend/intake/client.js');
 const {QuickFlow}=await import('../frontend/quick-flow.js');
 const calls=[],contract={policy,fields:rows,methods:{session:'session',turn:'turn'}};
 const state={task:{task_id:1,input_revision:1,created_at:'t0'},contract,facts:structuredClone(facts),questions,form_fields:rows,messages:[],complete:false,preview:{}};
 const intake=new AdaptiveIntake({changed(){},notify(){},api:async(method,params)=>{calls.push({method,params});throw Error('Unexpected network/service request');}});
 intake.state=state;intake.questions=intake.questionQueue(state);intake.dialogOpen=true;
 const flow=Object.create(QuickFlow.prototype),log={finished:0,drafts:0};
 Object.assign(flow,{intake,host:{querySelector(){return null;},querySelectorAll(){return [];}},busy:false,keepDraft(){log.drafts++;},async run(_,fn){await fn();},async finish(){log.finished++;}});
 return {intake,flow,calls,log,state,defaultHtml:()=>{intake.photoEditor=false;return intake.dialog(false);},editor:()=>{intake.photoEditor=true;return intake.dialog(false);}};
}
const count=(html,attribute)=>(html.match(new RegExp(attribute+'=','g'))||[]).length;
const dataRow=(html,identity)=>html.split(`data-intake-data="${identity}"`)[1]?.split('class="intake-data-row"')[0]||'';
const noImplicitControls=html=>{assert.equal(count(html,'data-intake-form'),0);assert.doesNotMatch(html,/data-intake-flag=|data-fill-kind=|해당하는 자세에 체크|직접 확인해 주세요|맞나요\?/);};
function edit(flow,f,raw){flow.input({target:{dataset:{intakeForm:f.identity},value:raw,setCustomValidity(){},reportValidity(){throw Error('Invalid value');}}});}
module.exports={assert,YES_NO,policy,field,pose,number,fact,setup,count,dataRow,noImplicitControls,edit};
