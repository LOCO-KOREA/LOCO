const assert=require('node:assert/strict');
(async()=>{
 const {QuickFlow}=await import('../frontend/quick-flow.js');
 const task={task_id:3,created_at:'owner',input_revision:1,latest_analysis_id:9};
 const makeAnalysis=(id=9,revision=1,{proposals=true,currentness='CURRENT',status='FINISHED'}={})=>{
  const result={analysis_id:id,input_revision:revision,status,currentness,judgment:{judgments:Array.from({length:11},(_,index)=>({criterion_no:index+1,computed_status:'NEEDS_INPUT',investigator:{status:null}}))}};
  if(proposals){result.ai=[{purpose:'TASK_EXPLANATION',result:'GENERATED',source_current:true,text_id:'ai-1'}];result.criteria_proposals=Array.from({length:11},(_,index)=>({criterion_no:index+1,proposed_status:index===0?'APPLICABLE':'UNDETERMINED',reason:'근거 설명',basis_refs:[],source_text_id:'ai-1',source_current:true,conflicts_with_computed:false}));}
  return result;
 };
 function flow({current=makeAnalysis(),saved=current,fresh=task,recalculated=null,running=null,confirmResult=null}={}){
  const calls=[],errors=[],notices=[];
  const value=Object.assign(Object.create(QuickFlow.prototype),{task:{...task},survey:{created_at:'survey'},result:current,review:{reviewer:'검토자',note:''},busy:false,criteriaConfirming:false,host:{},render:()=>{},notify:message=>notices.push(message),onError:error=>errors.push(error),
   api:async(method,params)=>{calls.push({method,params});
    if(method==='get_task_result')return {task:{...fresh},analysis:saved};
    if(method==='get_task')return {task:{...fresh}};
    if(method==='recalculate_judgments')return recalculated;
    if(method==='start_analysis')return {analysis_id:running.analysis_id};
    if(method==='get_analysis')return running||saved;
    if(method==='confirm_criterion_review')return confirmResult||{...saved,confirmation_current:true};
    throw Error(method);
   }});
  value.run=async(_label,action)=>{try{await action();}catch(error){value.onError(error);}};
  return {value,calls,errors,notices};
 }

 let fixture=flow();
 assert.equal(fixture.value.criterionReviewDraft().choices.size,11,'a current typed response preselects every legal criterion');
 assert.equal(fixture.value.criterionReviewDraft().choices.get(1).status,'APPLICABLE');
 assert.equal(fixture.value.criterionReviewDraft().choices.get(2).status,'UNDETERMINED');
 fixture.value.conclude(1,'NOT_APPLICABLE');
 assert.equal(fixture.calls.length,0,'changing one choice is local and must not persist');
 assert.match(fixture.value.criteriaRows(true),/AI 제안: 해당/);
 await fixture.value.confirmCriterionReview();
 assert.equal(fixture.calls.filter(call=>call.method==='confirm_criterion_review').length,1,'one explicit action makes one batch write');
 const batch=fixture.calls.find(call=>call.method==='confirm_criterion_review').params;
 assert.equal(batch.analysis_id,9);assert.equal(batch.expected_input_revision,1);assert.equal(batch.source_text_id,'ai-1');
 assert.equal(batch.conclusions.length,11);assert.equal(batch.conclusions[0].status,'NOT_APPLICABLE');
 assert.equal(batch.conclusions[1].status,'UNDETERMINED');assert.equal(fixture.errors.length,0);

 const linked=makeAnalysis();linked.confirmation_current=true;
 linked.criterion_review={source_text_id:'ai-1',conclusions:Array.from({length:11},(_,index)=>({criterion_no:index+1,status:index===0?'APPLICABLE':'UNDETERMINED'}))};
 linked.ai[0]={...linked.ai[0],source_current:false,confirmation_current:true};
 linked.criteria_proposals=linked.criteria_proposals.map(item=>({...item,source_current:false,confirmation_current:true}));
 fixture=flow({current:linked});
 assert.equal(fixture.value.currentCriterionProposals().length,11,'the source AI proposals remain current through the matching human-review receipt');
 assert.equal(fixture.value.criterionReviewDraft().choices.get(1).origin,'CONFIRMED');
 assert.match(fixture.value.criteriaRows(true),/AI 제안: 해당/,'the AI rationale stays visible after the human conclusion is saved');
 const unlinked=structuredClone(linked);unlinked.confirmation_current=false;
 fixture=flow({current:unlinked});assert.equal(fixture.value.currentCriterionProposals().length,0,'an AI receipt flag without the current analysis receipt cannot keep stale proposals visible');
 const held=structuredClone(linked);held.criterion_review.conclusions[1].status='UNDETERMINED';
 fixture=flow({current:held});assert.match(fixture.value.criteriaRows(true),/data-concl="2"[^>]*data-status="CLEAR"/,'a saved hold can be explicitly cleared even without a prior binary investigator conclusion');
 fixture.value.conclude(2,'CLEAR');await fixture.value.confirmCriterionReview();
 assert.equal(fixture.calls.find(call=>call.method==='confirm_criterion_review').params.conclusions.find(item=>item.criterion_no===2).status,null,
  'clearing a saved hold sends the explicit null disposition instead of silently preserving it');

 fixture=flow({current:makeAnalysis(9,1,{proposals:false})});
 assert.equal(fixture.value.criterionReviewDraft().choices.size,0,'no AI proposal or existing human decision must not impersonate a hold answer');
 assert.match(fixture.value.criterionReviewFooter(),/확정할 선택이 없어요/);
 assert.match(fixture.value.criterionReviewFooter(),/data-quick="confirm-criteria" disabled/);
 fixture.value.conclude(3,'APPLICABLE');
 assert.equal(fixture.calls.length,0,'manual selection also stays local until confirmation');
 await fixture.value.confirmCriterionReview();
 assert.deepEqual(fixture.calls.find(call=>call.method==='confirm_criterion_review').params.conclusions,[{criterion_no:3,status:'APPLICABLE'}],
  'AI-free manual confirmation writes only the selected criterion');

 const stale=makeAnalysis(9,1,{currentness:'STALE'}),next=makeAnalysis(10,2);
 fixture=flow({current:stale,saved:stale,recalculated:next,fresh:{...task,input_revision:2,latest_analysis_id:10}});
 fixture.value.conclude(4,'NOT_APPLICABLE');await fixture.value.confirmCriterionReview();
 assert(fixture.calls.some(call=>call.method==='recalculate_judgments'));
 assert(!fixture.calls.some(call=>call.method==='confirm_criterion_review'),'selection from an old analysis never reaches the new analysis');
 assert.equal(fixture.errors.length,1);

 fixture=flow({current:makeAnalysis(9,1,{proposals:false}),fresh:{...task,input_revision:2,latest_analysis_id:10},saved:makeAnalysis(10,2,{proposals:false})});
 fixture.value.conclude(2,'APPLICABLE');await fixture.value.confirmCriterionReview();
 assert(!fixture.calls.some(call=>call.method==='confirm_criterion_review'),'a revision change between selection and save is rejected');
 assert.equal(fixture.errors.length,1);

 fixture=flow();fixture.value.busy='AI 응답을 기다리고 있어요';fixture.value.conclude(1,'NOT_APPLICABLE');
 await fixture.value.confirmCriterionReview();
 assert.equal(fixture.calls.length,0);assert.match(fixture.notices[0],/진행 중인 작업/);
 assert.match(fixture.value.criteriaRows(true),/data-status="APPLICABLE"/);
 console.log('PASS AI proposal preselection, no fake hold, one batch write, AI-free manual mode, stale/revision/busy protection');
})().catch(error=>{console.error(error);process.exitCode=1;});
