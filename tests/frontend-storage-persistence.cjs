/* Counterexamples for independent local drafts, recovery ownership, acknowledgements and diagnostics. */
const assert=require('node:assert/strict'),path=require('node:path'),{pathToFileURL}=require('node:url');
const url=name=>pathToFileURL(path.join(__dirname,'../frontend',name)).href;
const tick=()=>new Promise(resolve=>setImmediate(resolve));
(async()=>{
 const {LocalDrafts,intakeDraftKey,saveExplanationDraft,readExplanationDraft,clearExplanationDraft}=await import(url('drafts.js'));
 const {AdaptiveIntake}=await import(url('intake/client.js'));
 const {QuickFlow}=await import(url('quick-flow.js'));
 const {renderIntakeHistory}=await import(url('intake/history-view.js'));
 const data=new Map();global.localStorage={getItem:key=>data.get(key)??null,setItem:(key,value)=>data.set(key,value),removeItem:key=>data.delete(key)};
 const drafts=new LocalDrafts({storage:()=>global.localStorage,scope:'database-a'});
 const other=new LocalDrafts({storage:()=>global.localStorage,scope:'database-b'});
 drafts.put('quick','one',{text:'first'});drafts.put('quick','two',{text:'second'});assert.equal(drafts.list('quick').length,2);assert.equal(other.list('quick').length,0);
 assert.equal(drafts.get('quick','toString'),null);data.set(drafts.key('corrupt'),'{broken');assert.equal(drafts.put('corrupt','x',{}),false);assert.equal(data.get(drafts.key('corrupt')),'{broken');
 const original=localStorage.setItem;localStorage.setItem=()=>{throw Error('quota');};assert.equal(drafts.put('quick','third',{}),false);assert.match(drafts.error,/실패/);localStorage.setItem=original;
 let deletes=0;const flow=Object.create(QuickFlow.prototype);Object.assign(flow,{drafts,step:'start',task:null,intakeText:'사진 전 설명',photos:{},intake:{text:''},answers:{},render(){},reset(){Object.assign(this,{task:null,step:'start',intakeText:'',photos:{},intake:{text:'',reset(){}},answers:{},draftId:null});},api(){deletes++;throw Error('must not delete');}});
 flow.keepDraft();const first=flow.draftId;flow.startNew();assert.equal(deletes,0);assert.equal(drafts.get('quick',first).intakeText,'사진 전 설명');
 flow.intakeText='두 번째 설명';flow.keepDraft();assert.notEqual(flow.draftId,first);const second=flow.draftId;
 await flow.restoreDraft(drafts.get('quick',first));assert.equal(flow.intakeText,'사진 전 설명');assert.equal(deletes,0);
 flow.intakeText='';flow.keepDraft();assert.equal(drafts.get('quick',first),null);assert.equal(drafts.get('quick',second).intakeText,'두 번째 설명');
 // Explicit discard updates the list inside the caller's busy scope and removes only its owner.
 drafts.put('quick','db-draft',{id:'db-draft',surveyId:9,createdAt:'survey-owner',taskId:9});let surveys=[{survey_id:9,created_at:'survey-owner'}];
 flow.api=async(method,args)=>{if(method==='list_surveys')return surveys;if(method==='get_survey')return surveys[0];assert.equal(method,'delete_survey');assert.equal(args.survey_id,9);surveys=[];};
 flow.busy=true;await flow.discardDraft('db-draft');assert.equal(flow.step,'home');assert.deepEqual(flow.surveys,[]);assert.equal(drafts.get('quick','db-draft'),null);assert.ok(drafts.get('quick',second));
 drafts.put('quick','orphan',{id:'orphan',surveyId:99,createdAt:'deleted-owner'});await flow.discardDraft('orphan');assert.equal(drafts.get('quick','orphan'),null);
 drafts.put('quick','reused-survey',{id:'reused-survey',surveyId:9,createdAt:'old-survey-owner'});flow.surveys=[{survey_id:9,created_at:'new-survey-owner'}];assert.match(flow.viewHome(),/data-open="9"/,'a bookmark for a deleted owner must not hide the new survey');
 const contract={session_key:'intake_session',methods:{session:'session',turn:'turn'},policy:{autosave_delay_ms:60000},fields:[{target:'daily_work_min',kind:'number',label:'하루 시간',choices:[]}]};
 const identity='daily_work_min@default';let value=480,revision=1,created='owner-a',block=null,fail=false,calls=0;
 const snapshot=()=>({task:{task_id:1,created_at:created,input_revision:revision},contract,facts:[{target:'daily_work_min',condition:'default',identity,value}],questions:[],history:[]});
 const api=async(method,args)=>{if(method==='intake_contract')return contract;if(method==='session')return snapshot();calls++;if(block)await block;if(fail)throw Error('쓰기 실패');if(args.expected_revision!==revision)return {...snapshot(),reason:'INPUT_CHANGED'};value=args.answers[0].value;revision++;return snapshot();};
 const make=()=>new AdaptiveIntake({api,drafts,changed(){},notify(){}});
 let client=make();await client.open(1);client.schedule(identity,420,()=>{});assert.equal(drafts.get('intake',intakeDraftKey(client.state.task)).entries[0][1].value,420);assert.match(client.saveStatus(),/임시 저장/);client.reset();assert.equal(value,480);
 client=make();await client.open(1);assert.equal(value,420);assert.equal(client.pending.size,0);
 for(const number of [0,null]){client.schedule(identity,number,()=>{});client.reset();client=make();await client.open(1);assert.equal(value,number);}
 // External writes must retain both values until the recovered edit is explicitly confirmed.
 client.schedule(identity,300,()=>{});client.reset();value=240;revision++;const before=calls;client=make();await client.open(1);assert.equal(value,240);assert.equal(client.value(identity),300);assert.equal(calls,before);assert.equal(client.pendingConflicts.size,1);await assert.rejects(()=>client.flush());await client.answer(identity,300);assert.equal(value,300);
 // Reused SQLite IDs cannot inherit drafts belonging to a deleted task.
 client.schedule(identity,100,()=>{});client.reset();created='owner-b';client=make();await client.open(1);assert.equal(client.pending.size,0);assert.equal(value,300);
 // A successful older request cannot acknowledge newer typing.
 let release;block=new Promise(resolve=>release=resolve);const old=client.answer(identity,200);await tick();client.schedule(identity,180,()=>{});release();await old;block=null;assert.equal(client.value(identity),180);assert.equal(client.pending.get(identity).base,200);client.reset();client=make();await client.open(1);assert.equal(value,180);
 fail=true;await assert.rejects(()=>client.answer(identity,120));client.reset();client=make();await client.open(1);assert.equal(client.value(identity),120);assert.match(client.saveStatus(),/저장하지 못했어요/);assert.ok(!client.saveStatus().includes('합성 저장'));fail=false;await assert.rejects(()=>client.flush());await client.answer(identity,120);await client.flush();assert.equal(value,120);
 // Removing a field in a future contract must not erase its pending edit.
 client.schedule(identity,90,()=>{});client.reset();contract.fields=[];client=make();await client.open(1);assert.equal(client.pending.size,1);assert.equal(client.pendingConflicts.size,1);client.reset();contract.fields=[{target:'daily_work_min',kind:'number',label:'하루 시간',choices:[]}];
 const analysis={analysis_id:1,created_at:'analysis-owner'},ai={text_id:'one',created_at:'text-owner',purpose:'TASK_EXPLANATION',generated_text:'generated',edited_text:null};
 saveExplanationDraft(analysis,ai,'unsaved',drafts);saveExplanationDraft(analysis,{...ai,text_id:'two'},'other history',drafts);saveExplanationDraft(analysis,{...ai,purpose:'IMPROVEMENT_ADVICE'},'other purpose',drafts);
 assert.equal(readExplanationDraft(analysis,ai,drafts).text,'unsaved');assert.equal(ai.edited_text,null);saveExplanationDraft(analysis,ai,'new typing',drafts);clearExplanationDraft(analysis,ai,'unsaved',drafts);assert.equal(readExplanationDraft(analysis,ai,drafts).text,'new typing');clearExplanationDraft(analysis,ai,'new typing',drafts);assert.equal(readExplanationDraft(analysis,ai,drafts),null);assert.equal(readExplanationDraft({...analysis,created_at:'new owner'},ai,drafts),null);
 const html=renderIntakeHistory({contract,diagnostics:[{target:'daily_work_min',reason:'STALE_QUOTE',quote:'<img src=x onerror=1>'}],history:[{requests:[{phase:'EXTRACT_AND_PLAN',context:{omitted_message_ids:['one']}}],decisions:[]}]});assert.ok(!html.includes('<img'));assert.match(html,/&lt;img/);assert.match(html,/일부 이전 설명/);assert.match(html,/최신 값/);
 console.log('PASS independent drafts, pre-photo recovery, zero/null, external conflicts, reused owners, late acknowledgements, write failures, explanation histories and escaped persistent diagnostics');
})().catch(error=>{console.error(error);process.exitCode=1;});
