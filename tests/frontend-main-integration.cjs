const assert=require('node:assert/strict'),path=require('node:path'),{pathToFileURL}=require('node:url');
(async()=>{
 const load=name=>import(pathToFileURL(path.join(__dirname,'../frontend',name)).href);
 const {QuickFlow}=await load('quick-flow.js'),{LocalDrafts}=await load('drafts.js');
 const {writeWorkspaceDraft,readWorkspaceDraft}=await load('quick-workspace-draft.js');
 const data=new Map();global.localStorage={getItem:k=>data.get(k)||null,setItem:(k,v)=>data.set(k,v),removeItem:k=>data.delete(k)};
 const drafts=new LocalDrafts({storage:()=>localStorage,scope:'integration-db'});
 const a={id:'one',surveyId:1,createdAt:'survey-a',taskId:11,taskCreatedAt:'task-a',photos:{},savedAt:'2026-10-23',surveyTitle:'수동 저장과 같은 작업'};
 const b={id:'two',surveyId:2,createdAt:'survey-b',taskId:12,taskCreatedAt:'task-b',photos:{},savedAt:'2026-10-23',surveyTitle:'별도 자동 초안'};
 drafts.put('quick',a.id,a);drafts.put('quick',b.id,b);
 const checkpoint={version:1,step:'review',survey:{id:1,createdAt:'survey-a'},task:{id:11,createdAt:'task-a'}};
 writeWorkspaceDraft(checkpoint);
 const flow=Object.create(QuickFlow.prototype);let loaded=0,deleted=0;
 Object.assign(flow,{drafts,surveys:[{survey_id:1,created_at:'survey-a'},{survey_id:2,created_at:'survey-b'}],settings:{},busy:false,loadHome:async()=>loaded++,api:async()=>{deleted++;throw Error('manual checkpoint must not be deleted');}});
 const home=flow.viewHome();assert.match(home,/data-quick="workspace-resume"/);assert.match(home,/data-draft="two"/);assert.ok(!home.includes('data-draft="one"'));
 await flow.discardDraft('one');assert.equal(deleted,0);assert.equal(loaded,1);assert.deepEqual(readWorkspaceDraft(),checkpoint);assert.equal(drafts.get('quick','one'),null);assert.ok(drafts.get('quick','two'));
 // A new pre-photo analysis must keep both manual checkpoints and independent unsent input.
 Object.assign(flow,{step:'start',task:null,survey:null,photos:{},intakeText:'사진 선택 전에 적은 새 설명',intake:{text:'아직 보내지 않은 문장',reset(){}},answers:{},draftId:'pre-photo',render(){}});
 flow.startNew();assert.equal(deleted,0);assert.equal(drafts.get('quick','pre-photo').intakeText,'사진 선택 전에 적은 새 설명');assert.equal(drafts.get('quick','pre-photo').reply,'아직 보내지 않은 문장');assert.deepEqual(readWorkspaceDraft(),checkpoint);assert.ok(drafts.get('quick','two'));
 writeWorkspaceDraft(null);drafts.put('quick','bare',{id:'bare',intakeText:'사진 전 설명',photos:{},savedAt:'2026-10-23'});
 assert.match(flow.viewHome(),/data-draft="bare"/,'missing parent IDs are not evidence that two drafts are the same');
 console.log('PASS main manual checkpoint ownership, no duplicate automatic card, protected discard and independent pre-photo drafts');
})().catch(error=>{console.error(error);process.exitCode=1;});
