const assert=require('node:assert/strict');
(async()=>{
 const {QuickFlow}=await import('../frontend/quick-flow.js');
 const {captureWorkspace,workspaceDraftDiffers}=await import('../frontend/quick-workspace-draft.js');
 const calls=[],survey={survey_id:1,created_at:'owner',title:'기존 제목',department:'포장팀',survey_type:'REGULAR'};
 const flow=Object.assign(Object.create(QuickFlow.prototype),{survey,analysisTitle:'  상자 운반  ',api:async(method,args)=>{calls.push({method,args});return method==='get_survey'?survey:{...survey,...args.draft};}});
 await flow.saveAnalysisTitle();assert.equal(flow.survey.title,'상자 운반');assert.equal(calls[1].args.draft.department,'포장팀');
 flow.analysisTitle='';await flow.saveAnalysisTitle();assert.equal(flow.survey.title,'','clearing the optional title is saved');
 flow.api=async()=>({...survey,created_at:'replacement'});await assert.rejects(()=>flow.saveAnalysisTitle(),/변경/);
 const start=Object.assign(Object.create(QuickFlow.prototype),{photos:{},analysisTitle:'<제목>',intakeText:'설명',intake:{},busy:false});
 const html=start.viewStart();assert.ok(html.indexOf('quick-slots')<html.indexOf('data-quick-title'));assert.ok(html.indexOf('data-quick-title')<html.indexOf('data-quick-intake'));assert.match(html,/value="&lt;제목&gt;"/);
 const checkpoint=captureWorkspace({...start,step:'start',draftId:'one'});assert.equal(checkpoint.ui.analysisTitle,'<제목>');
 assert.equal(workspaceDraftDiffers(checkpoint,{analysisTitle:'다른 제목',intakeText:'설명'}),true,'title differences preserve distinct draft versions');
 const drafts=[];Object.assign(start,{step:'start',intakeText:'',draftId:'one',draftOwnerId:'one',drafts:{scope:'test',put(_type,_id,value){drafts.push(value);return false;}}});start.keepDraft();assert.equal(drafts[0].analysisTitle,'<제목>','a title-only draft is retained');
 console.log('PASS analysis title placement, escaping, metadata preservation, clear, owner replacement and title-only drafts');
})().catch(error=>{console.error(error);process.exitCode=1;});
