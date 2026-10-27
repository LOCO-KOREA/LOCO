const assert=require('node:assert/strict');
(async()=>{
 const {QuickFlow}=await import('../frontend/quick-flow.js');
 let panel=null,html='';
 const host={querySelector:selector=>selector==='#quick-criteria-review'?panel:null,querySelectorAll:()=>[],
   set innerHTML(value){html=value;const attrs=/<details\b([^>]*id="quick-criteria-review"[^>]*)>/.exec(value)?.[1];panel=attrs==null?null:{open:/\bopen\b/.test(attrs)};},get innerHTML(){return html;}};
 const errors=[];let finish;
 const result={analysis_id:9,currentness:'CURRENT',judgment:{judgments:[{criterion_no:1,computed_status:'NEEDS_INPUT',investigator:null}]}};
 const flow=Object.assign(Object.create(QuickFlow.prototype),{host,step:'review',survey:{review:{}},task:{task_id:3},result,
   review:{reviewer:'',note:''},intake:{dialogOpen:false,dialog:()=>'',mount:()=>{},reset:()=>{}},
   photoStrip:()=>'',photoVisionPanel:()=>'',rebaPanel:()=>'',aiPanel:()=>'',criteriaRows:()=>'',keepDraft:()=>{},
   onError:error=>errors.push(error),api:()=>new Promise(resolve=>{finish=()=>resolve(result);})});
 flow.render();assert.equal(panel.open,false);
 panel.open=true;
 const saving=flow.conclude(1,'APPLICABLE');
 const openWhileSaving=panel.open;
 finish();await saving;
 assert.equal(openWhileSaving,true,'starting a save must not collapse the open review');
 assert.equal(panel.open,true,'successful save must keep it open for the next selection');
 flow.api=async()=>{throw Error('controlled save failure');};
 await flow.conclude(1,'NOT_APPLICABLE');
 assert.equal(errors.length,1);assert.equal(panel.open,true,'failed saves must also keep the user position');
 panel.open=false;flow.render();assert.equal(panel.open,false,'only the user closes the review');
 panel.open=true;flow.viewStart=()=>'';flow.reset();flow.render();
 flow.step='review';flow.task={task_id:4};flow.result=result;flow.render();
 assert.equal(panel.open,false,'a different task must not inherit the old open state');
 const excel=Object.assign(Object.create(QuickFlow.prototype),{excelPreviewPanel:()=>'<p>저장한 결론 미리보기</p>',
   checklistPanel:()=>{throw Error('Excel must not ask the review questions again');},comparePanel:()=>'',comparison:null,exported:null}).viewExcel();
 assert.match(excel,/저장한 결론 미리보기/);assert.match(excel,/data-quick="excel"/);
 assert.doesNotMatch(excel,/Excel 만들기 전 확인|입력하러 가기|입력 필요 기준/);
 console.log('PASS review remains open through async save/error; manual close/reset respected; Excel does not repeat completed review');
})().catch(error=>{console.error(error);process.exitCode=1;});
