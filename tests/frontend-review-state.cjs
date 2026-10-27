const assert=require('node:assert/strict');
(async()=>{
 const {QuickFlow}=await import('../frontend/quick-flow.js');
 let panel=null,html='';
 const host={querySelector:selector=>selector==='#quick-criteria-review'?panel:null,querySelectorAll:()=>[],
  set innerHTML(value){html=value;const attrs=/<details\b([^>]*\bid="quick-criteria-review"[^>]*)>/.exec(value)?.[1];panel=attrs==null?null:{open:/\bopen\b/.test(attrs)};},get innerHTML(){return html;}};
 const task={task_id:3,created_at:'task-owner',input_revision:1,latest_analysis_id:9};
 const makeResult=(receipt=false)=>({analysis_id:9,input_revision:1,currentness:'CURRENT',status:'FINISHED',
  judgment:{judgments:Array.from({length:11},(_,index)=>({criterion_no:index+1,computed_status:'NEEDS_INPUT',investigator:{status:null}}))},
  ...(receipt?{confirmation_current:true,criterion_review:{conclusions:[{criterion_no:1,status:'APPLICABLE'}]}}:{})});
 const result=makeResult();let finish,fail;const calls=[],errors=[];
 const flow=Object.assign(Object.create(QuickFlow.prototype),{host,step:'review',survey:{survey_id:7,created_at:'survey-owner',review:{}},task,result,
  review:{reviewer:'검토자',note:''},intake:{dialogOpen:false,dialog:()=>'',mount:()=>{},reset:()=>{}},
  photoStrip:()=>'',photoVisionPanel:()=>'',rebaPanel:()=>'',aiPanel:()=>'',keepDraft:()=>{},
  onError:error=>errors.push(error),api:async(method,params)=>{calls.push({method,params});
   if(method==='get_task_result')return {task:{...task},analysis:result};
   if(method==='get_task')return {task:{...task}};
   if(method==='confirm_criterion_review')return new Promise((resolve,reject)=>{finish=()=>resolve({...result,...makeResult(true)});fail=()=>reject(Error('controlled save failure'));});
   throw Error(method);
  }});
 flow.render();
 assert.equal(panel.open,false);
 // This is the same delegated path used by an actual criterion button.
 const option=(number,status)=>({target:{closest:()=>({disabled:false,dataset:{concl:String(number),status}})}});
 panel.open=true;flow.click(option(1,'APPLICABLE'));
 assert.equal(panel.open,true,'choosing a status must preserve the open review disclosure');
 assert.equal(calls.length,0,'choosing a status is a local draft, not an immediate save');
 assert.equal(flow.criterionReviewDraft().touched.has(1),true);

 const saving=flow.confirmCriterionReview();await new Promise(setImmediate);
 assert.equal(panel.open,true,'the panel stays open while one batch is saving');
 assert.equal(calls.filter(call=>call.method==='confirm_criterion_review').length,1,'the explicit confirmation makes one write');
 finish();await saving;
 assert.equal(panel.open,true,'successful confirmation keeps the panel open for review');
 assert.equal(errors.length,0);

 flow.click(option(2,'NOT_APPLICABLE'));const failed=flow.confirmCriterionReview();await new Promise(setImmediate);
 fail();await failed;assert.equal(errors.length,1,'a failed batch is reported');
 assert.equal(panel.open,true,'a failed confirmation keeps the panel open');

 panel.open=false;flow.render();assert.equal(panel.open,false,'a user close remains closed');
 panel.open=true;flow.reset();flow.step='review';flow.task={...task,task_id:4};flow.result=makeResult();flow.render();
 assert.equal(panel.open,false,'a different analysis does not inherit the prior panel state');

 const excel=Object.assign(Object.create(QuickFlow.prototype),{excelPreviewPanel:()=>'<p>저장한 결론 미리보기</p>',
  checklistPanel:()=>{throw Error('Excel must not ask the review questions again');},comparePanel:()=>'',comparison:null,exported:null}).viewExcel();
 assert.match(excel,/저장한 결론 미리보기/);assert.match(excel,/data-quick="excel"/);
 assert.doesNotMatch(excel,/Excel 만들기 전 확인|입력하러 가기|입력 필요 기준/);

 const proposal=makeResult();proposal.ai=[{purpose:'TASK_EXPLANATION',result:'GENERATED',source_current:true,text_id:'ai-current'}];
 proposal.criteria_proposals=Array.from({length:11},(_,index)=>({criterion_no:index+1,proposed_status:'UNDETERMINED',reason:'근거',basis_refs:[],source_text_id:'ai-current',source_current:true}));
 Object.assign(flow,{task:{...task},survey:{survey_id:7,created_at:'survey-owner',review:{}},result:proposal,step:'review',criteriaProposalSeen:new Set(),criteriaReviewOpen:false});
 flow.render();assert.equal(panel.open,true,'a new typed response opens the human review section');
 assert.equal((html.match(/data-concl="\d+"/g)||[]).length,33,'all eleven criteria and three choices are visible together');
 panel.open=false;flow.click(option(2,'APPLICABLE'));
 assert.equal(panel.open,false,'after the user closes it, selecting an option does not reopen it');
 console.log('PASS delegated choice click, no per-row write, batch confirm, disclosure state and all eleven AI proposals visible');
})().catch(error=>{console.error(error);process.exitCode=1;});
