const assert=require('node:assert/strict'),path=require('node:path'),{pathToFileURL}=require('node:url');
(async()=>{
 const load=name=>import(pathToFileURL(path.join(__dirname,'../frontend',name)).href);
 const {QuickFlow}=await load('quick-flow.js'),{LocalDrafts}=await load('drafts.js');
 const {writeWorkspaceDraft,readWorkspaceDraft,captureWorkspace,workspaceMatchesDraft,workspaceTargetAvailable,loadWorkspace,clearWorkspaceDraftForSurvey}=await load('quick-workspace-draft.js');
 const data=new Map();global.localStorage={getItem:k=>data.get(k)||null,setItem:(k,v)=>data.set(k,v),removeItem:k=>data.delete(k)};
 const drafts=new LocalDrafts({storage:()=>localStorage,scope:'integration-db'});
 const a={id:'one',surveyId:1,createdAt:'survey-a',taskId:11,taskCreatedAt:'task-a',photos:{},savedAt:'2026-10-23',surveyTitle:'수동 저장과 같은 작업'};
 const b={id:'two',surveyId:2,createdAt:'survey-b',taskId:12,taskCreatedAt:'task-b',photos:{},savedAt:'2026-10-23',surveyTitle:'별도 자동 초안'};
 drafts.put('quick',a.id,a);drafts.put('quick',b.id,b);
 const checkpoint={version:1,step:'review',survey:{id:1,createdAt:'survey-a'},task:{id:11,createdAt:'task-a'},ui:{},intake:{}};
 writeWorkspaceDraft(checkpoint);
 const flow=Object.create(QuickFlow.prototype);let loaded=0,deleted=0;
 Object.assign(flow,{drafts,surveys:[{survey_id:1,created_at:'survey-a'},{survey_id:2,created_at:'survey-b'}],settings:{},busy:false,loadHome:async()=>loaded++,api:async()=>{deleted++;throw Error('manual checkpoint must not be deleted');}});
 const home=flow.viewHome();assert.match(home,/data-quick="workspace-resume"/);assert.match(home,/data-draft="two"/);assert.match(home,/data-draft="one"/);assert.equal((home.match(/<section class="panel quick-draft"/g)||[]).length,2,'the matching automatic action lives inside the manual card');
 await flow.discardDraft('one');assert.equal(deleted,0);assert.equal(loaded,1);assert.deepEqual(readWorkspaceDraft(),checkpoint);assert.equal(drafts.get('quick','one'),null);assert.ok(drafts.get('quick','two'));
 // A new pre-photo analysis must keep both manual checkpoints and independent unsent input.
 Object.assign(flow,{step:'start',task:null,survey:null,photos:{},intakeText:'사진 선택 전에 적은 새 설명',intake:{text:'아직 보내지 않은 문장',reset(){}},answers:{},draftId:'pre-photo',render(){}});
 flow.startNew();assert.equal(deleted,0);assert.equal(drafts.get('quick','pre-photo').intakeText,'사진 선택 전에 적은 새 설명');assert.equal(drafts.get('quick','pre-photo').reply,'아직 보내지 않은 문장');assert.deepEqual(readWorkspaceDraft(),checkpoint);assert.ok(drafts.get('quick','two'));
 writeWorkspaceDraft(null);drafts.put('quick','bare',{id:'bare',intakeText:'사진 전 설명',photos:{},savedAt:'2026-10-23'});
 assert.match(flow.viewHome(),/data-draft="bare"/,'missing parent IDs are not evidence that two drafts are the same');
 writeWorkspaceDraft(checkpoint);flow.step='start';flow.intakeText='';flow.intake.text='';flow.task=null;flow.photos={};flow.notify=()=>{};
 assert.equal(await flow.saveWorkspace(),true);assert.deepEqual(readWorkspaceDraft(),checkpoint,'an untouched new screen keeps the previous meaningful checkpoint');
 // Reused numeric IDs, cloned databases and independent parentless drafts do not own each other.
 const owned={...checkpoint,scope:drafts.scope};
 assert.equal(workspaceMatchesDraft(owned,a,drafts.scope),true);
 for(const changed of [{...a,taskCreatedAt:'reused-task'},{...a,createdAt:'reused-survey'},{...a,scope:'cloned-db'}])assert.equal(workspaceMatchesDraft(owned,changed,drafts.scope),false);
 assert.equal(workspaceMatchesDraft({version:1,step:'start'}, {id:'bare'},drafts.scope),false);
 assert.equal(workspaceMatchesDraft({draftId:'parentless',scope:drafts.scope},{id:'branch',ownerId:'parentless',scope:drafts.scope},drafts.scope),true);
 assert.equal(workspaceMatchesDraft({draftId:'parentless',scope:drafts.scope},{...a,id:'branch',ownerId:'parentless',scope:drafts.scope},drafts.scope),true,'UUID ownership survives the first photo creating DB parents');
 assert.equal(workspaceMatchesDraft({draftId:'other'},{id:'bare'},drafts.scope),false);
 assert.equal(await workspaceTargetAvailable({...owned,scope:'cloned-db'},async()=>{throw Error('must not read clone');},drafts.scope),false);
 await assert.rejects(loadWorkspace({...owned,scope:'cloned-db'},async()=>{throw Error('must not read clone');},drafts.scope),/다른 저장 파일/);
 writeWorkspaceDraft({...owned,scope:'cloned-db'});
 assert.equal(clearWorkspaceDraftForSurvey({survey_id:1,created_at:'survey-a'},localStorage,drafts.scope),false);
 assert.ok(readWorkspaceDraft(),'deletion in clone never erases original manual checkpoint');
 await assert.rejects(flow.restoreDraft({...a,scope:'cloned-db'}),/다른 저장 파일/);

 // A real render calls keepDraft. Reopening the manual snapshot must not clobber later unsent text.
 for(const hasTask of [false,true]){
  data.clear();const errors=[];
  const owner=Object.create(QuickFlow.prototype);
  const survey=hasTask?{survey_id:1,created_at:'survey-a'}:null,task=hasTask?{task_id:11,survey_id:1,created_at:'task-a',input_revision:4,capture:{slots:[]}}:null;
  Object.assign(owner,{drafts,step:'start',busy:false,survey,task,photos:{},answers:{zero:0,unknown:null},intakeText:'수동 저장 시점의 원문',draftId:'manual-owner',settings:{},
   render(){this.keepDraft();},notify(){},onError:error=>errors.push(error.message),
   intake:{text:'수동 저장 시점의 답변',state:null,values:new Map(),pairValues:new Map(),formStage:0,formValues:new Map([['weight',0]]),hasSession(){return false;},async flush(){},reset(){this.state=null;this.text='';this.values=new Map();this.pairValues=new Map();this.formValues=new Map();}},
   api:async method=>{if(method==='get_survey')return survey;if(method==='get_task')return {task,photos:[]};throw Error('unexpected '+method);}});
  owner.keepDraft();await owner.saveWorkspace();
  owner.intakeText='수동 저장 뒤 아직 보내지 않은 원문';owner.intake.text='수동 저장 뒤 아직 보내지 않은 답변';owner.intake.formStage=1;owner.intake.formValues.set('weight',20);owner.keepDraft();
  const later=drafts.get('quick','manual-owner');
  assert.equal(later.intakeText,'수동 저장 뒤 아직 보내지 않은 원문');assert.equal(later.formValues[0][1],20);
  owner.step='home';owner.surveys=hasTask?[survey]:[];
  assert.equal((owner.viewHome().match(/<section class="panel quick-draft"/g)||[]).length,1,'one owner has one visible card');
  assert.match(owner.viewHome(),/data-draft="manual-owner"/,'later automatic input remains reachable inside manual card');
  await owner.resumeWorkspace();assert.deepEqual(errors,[]);
  assert.equal(owner.intakeText,'수동 저장 시점의 원문');assert.equal(owner.intake.text,'수동 저장 시점의 답변');assert.equal(owner.intake.formValues.get('weight'),0);assert.deepEqual(owner.answers,{zero:0,unknown:null});
  assert.deepEqual(drafts.get('quick','manual-owner'),later,'restoration render preserves later automatic version verbatim');
  const restoredId=owner.draftId;assert.notEqual(restoredId,later.id);
  owner.step='home';await owner.resumeWorkspace();assert.equal(owner.draftId,restoredId,'reopening an unchanged checkpoint reuses its own automatic version');
  await owner.resumeDraft(later.id);assert.equal(owner.intakeText,later.intakeText);assert.equal(owner.intake.text,later.reply);
  owner.step='home';assert.equal((owner.viewHome().match(/<section class="panel quick-draft"/g)||[]).length,1);
  assert.equal(captureWorkspace(owner).draftId,'manual-owner','parentless branches keep a stable owner');
  writeWorkspaceDraft(null);assert.equal((owner.viewHome().match(/<section class="panel quick-draft"/g)||[]).length,1,'automatic variants also share one card after another checkpoint replaces this one');
  if(!hasTask){owner.loadHome=async()=>{};await owner.discardDraft(later.id);assert.equal(drafts.list('quick').length,0,'explicit discard owns all variants in that one card');}
 }
 data.clear();drafts.put('quick',a.id,{...a,scope:drafts.scope});
 const summaryFlow=Object.create(QuickFlow.prototype),identityCalls=[];
 Object.assign(summaryFlow,{drafts,step:'home',busy:false,render(){},onError:error=>{throw error;},intake:{loadContract:async()=>{}},api:async(method,args)=>{
  identityCalls.push([method,args]);if(method==='list_surveys')return [{survey_id:1,title:'same numeric ID'}];if(method==='get_survey')return {survey_id:1,created_at:'reused-survey'};if(method==='get_settings')return {};throw Error(method);
 }});
 await summaryFlow.loadHome();assert.match(summaryFlow.viewHome(),/data-open="1"/,'the actual summary DTO has no created_at, so read the parent before hiding reused IDs');
 assert.ok(identityCalls.some(([method])=>method==='get_survey'));
 console.log('PASS main manual checkpoint ownership, pre-photo visibility, clone/reused-ID boundaries, exact manual restore, later unsent versions and one owner card');
})().catch(error=>{console.error(error);process.exitCode=1;});
