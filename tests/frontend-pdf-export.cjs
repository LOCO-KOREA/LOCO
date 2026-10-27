/* Internal PDF helper contracts and user-facing Excel reports; no Electron/native dialog. */
const assert=require('node:assert/strict');
const {pathToFileURL}=require('node:url');
const path=require('node:path');
const deferred=()=>{let resolve;const promise=new Promise(r=>resolve=r);return {promise,resolve};};
(async()=>{
 const load=file=>import(pathToFileURL(path.resolve(__dirname,'../frontend',file)).href);
 const {previewPdf,exportPdf,renderPdfPreview}=await load('pdf-export.js');
 const {QuickFlow}=await load('quick-flow.js');
 const {createExportView}=await load('analysis/export-view.js');
 const {createRebaView}=await load('analysis/reba-view.js');
 const {createExplanationView}=await load('analysis/explanation-view.js');
 const params=()=>({survey_id:1,spec:{task_ids:[2],analysis_ids:[3],include_representative:false}});
 let calls=[];
 assert.equal(await exportPdf((...a)=>calls.push(a),async()=>null,params()),null);
 assert.equal(calls.length,0,'cancel does not send export');
 const dialog=deferred();let choices=0;const original=params();
 const api=async(method,args)=>{calls.push([method,args]);return {file_path:'demo.pdf'};};
 const first=exportPdf(api,()=>{choices++;return dialog.promise;},original);
 const second=exportPdf(api,()=>{throw new Error('second dialog');},params());
 assert.equal(first,second,'duplicate export shares one operation');
 await Promise.resolve();original.spec.task_ids=[999];original.survey_id=9;
 dialog.resolve('demo.pdf');await first;
 assert.equal(choices,1);assert.equal(calls.length,1);
 assert.equal(calls[0][0],'export_pdf');assert.equal(calls[0][1].survey_id,1);
 assert.deepEqual(calls[0][1].spec.task_ids,[2]);
 let count=0;const response=deferred();
 const p1=previewPdf(()=>{count++;return response.promise;},params());
 const p2=previewPdf(()=>{throw new Error('second preview');},params());
 assert.equal(p1,p2);await Promise.resolve();assert.equal(count,1);response.resolve({page_count:4});await p1;
 const html=renderPdfPreview({data_url:'data:application/pdf;base64,JVBERi0=',page_count:4,warnings:['<script>unsafe</script>']});
 assert.match(html,/<iframe/);assert.ok(html.includes('&lt;script&gt;'));assert.ok(!html.includes('<script>'));
 const viewer=html.match(/src="(blob:[^"]+)#view=FitH"/)[1];
 assert.equal(await (await fetch(viewer)).text(),'%PDF-','viewer receives decoded PDF bytes through a Blob URL');
 URL.revokeObjectURL(viewer);
 assert.ok(!renderPdfPreview({data_url:'javascript:alert(1)'}).includes('<iframe'));

 // Visible reports keep the Excel overview, sheet preview, and selected before/after comparison.
 global.window={scrollTo(){},loco:{choose_pdf_destination(){throw new Error('PDF dialog must stay hidden');}}};
 global.localStorage={getItem(){return null;}};
 const comparison={before_analysis_id:2,after_analysis_id:3,note:'before and after'};
 const makeFlow=()=>Object.assign(Object.create(QuickFlow.prototype),{
  survey:{survey_id:1},task:{task_id:2},result:{analysis_id:3},baseline:{analysis_id:2},
  comparison:{spec:comparison},step:'review',busy:false,excelPreview:null,excelTab:9,overview:null,
  review:{reviewer:'',note:''},surveys:[],settings:{},exported:null,
  run:async(_label,action)=>action(),render(){},notify(){},onError(error){throw error;}
 });
 const overview={tasks:[]},sheets={sheets:[{name:'요약',title:'요약',lead:'',tables:[],notes:[]}]};
 const flow=makeFlow(),previewCalls=[];
 flow.api=async(method,args)=>{
  previewCalls.push([method,args]);
  if(method==='preview_excel')return overview;
  if(method==='preview_excel_sheets')return sheets;
  throw new Error('unexpected report API: '+method);
 };
 await flow.openExcel();
 assert.deepEqual(previewCalls.map(([method])=>method),['preview_excel','preview_excel_sheets']);
 for(const [,args] of previewCalls)assert.deepEqual(args,{survey_id:1,analysis_ids:[3],comparisons:[comparison]});
 assert.equal(flow.overview,overview);assert.equal(flow.excelPreview,sheets);
 assert.equal(flow.step,'excel');assert.equal(flow.excelTab,0);
 const exportCalls=[],notifications=[];let excelChoices=0;
 window.loco.choose_export_destination=async()=>{excelChoices++;return 'report.xlsx';};
 flow.api=async(method,args)=>{
  exportCalls.push([method,args]);assert.equal(method,'export_excel','visible save uses the Excel API');
  return {file_path:'report.xlsx'};
 };
 flow.notify=message=>notifications.push(message);
 await flow.exportExcel();
 assert.equal(excelChoices,1);
 assert.deepEqual(exportCalls,[['export_excel',{survey_id:1,spec:{
  destination:'report.xlsx',analysis_ids:[3],include_representative:true,comparisons:[comparison]
 }}]]);
 assert.equal(flow.exported.file_path,'report.xlsx');assert.match(notifications[0],/Excel/);
 window.loco.choose_export_destination=async()=>null;
 await flow.exportExcel();
 assert.equal(exportCalls.length,1,'cancel does not send an Excel export');
 assert.equal(notifications.length,1,'cancel does not announce a saved file');
 const noComparison=makeFlow();noComparison.baseline=null;noComparison.comparison=null;
 const noComparisonCalls=[];
 noComparison.api=async(method,args)=>{noComparisonCalls.push([method,args]);return method==='preview_excel'?overview:sheets;};
 await noComparison.openExcel();
 for(const [,args] of noComparisonCalls)assert.deepEqual(args.comparisons,[],'no comparison stays unrequested');

 // Actual entry-point rendering prevents the retained PDF backend from reappearing in user UI.
 const noPdf=(markup,where)=>assert.doesNotMatch(markup,/\bPDF\b|data-pdf-task|(?:preview|export)-pdf|application\/pdf/i,where+' must not show a PDF entry point');
 Object.assign(flow,{photoStrip:()=>'',rebaPanel:()=>'',resultSummary:()=>'',criteriaRows:()=>'',comparePanel:()=>'',aiPanel:()=>''});
 for(const [name,render] of [['home',()=>flow.viewHome()],['result',()=>flow.viewResult()],['review',()=>flow.viewReview()],['Excel',()=>flow.viewExcel()]])noPdf(render(),name);
 assert.doesNotMatch(flow.viewHome(),/quick-settings|data-setting|data-quick="settings"/,'home keeps user settings hidden');
 assert.match(flow.viewResult(),/data-quick="preview">Excel 미리보기/);
 assert.match(flow.viewReview(),/data-quick="preview">Excel 미리보기/);
 assert.match(flow.viewExcel(),/data-quick="excel">Excel로 저장/);
 assert.match(flow.viewExcel(),/data-quick="excel-tab"/,'Excel sheet tabs remain visible');
 const s={survey:{survey_id:1},tasks:[{task_id:2,task_name:'작업'}],comparisonPool:[],comparisonBefore:null,comparisonAfter:null,comparisonNote:'',
  exportSelections:{},pdfTaskSelections:{},overview:{tasks:[],comparisons:[],counts:{},state:{}}};
 const escape=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
 const advanced=createExportView({s,LocoReview:{comparison:()=>''},inputLabel:x=>x,$:()=>null,e:escape,fmt:String,badge:()=>'',field:()=>'',select:()=>'',
  card:(title,body)=>'<section><h3>'+title+'</h3>'+body+'</section>',empty:String,context:()=>''}).exportPage();
 noPdf(advanced,'advanced export');
 assert.match(advanced,/data-action="export">저장 위치를 선택하고 Excel 저장/);
 assert.match(advanced,/id="include-representative"/,'Excel representative-image choice remains available');
 assert.match(advanced,/실제로 입력하거나 분석한 값/,'primary export copy is data-only');
 assert.doesNotMatch(advanced,/확인사항|다음 입력 안내|입력한 값|쉬운 설명|유형별 한글 Excel/,'advanced export avoids a stale sheet inventory or technical follow-up list');
 assert.match(advanced,/<details class="export-options" data-export-section="analysis"/,'optional analysis selection is progressive');

 const rebaState={selectedSlots:new Set(),history:[],bundle:{task:{capture:{slots:[]},manual:[]}}};
 const rebaContext={s:rebaState,angleNames:{},tagNames:{},sideNames:{},statusNames:{},manualLabels:{},commonFields:[],armFields:[],reasonText:String,candidateValueText:String,manualOptions:()=>[],$:()=>null,e:escape,fmt:value=>value??'미계산',badge:value=>`<b>${value??'미계산'}</b>`,options:()=>'',field:()=>'',select:()=>'',card:(title,body)=>`<section><h2>${title}</h2>${body}</section>`,empty:String,metric:()=>'',context:()=>''};
 const reba=createRebaView(rebaContext);
 const reference={reba:{summary:{current_score:{total:1,risk:'NEGLIGIBLE',kind:'ASSUMED_REFERENCE',slot_no:4,assumed:[],assumption:'자세 측정값이 없어 기준 자세를 가정했습니다.'},score_so_far:null}},measurement_quality:{slots:[{slot_no:4,measured_points:0,total_points:33,mean_confidence:null,confidence_level:'MISSING'}]}};
 const scoreHtml=reba.currentScoreCard(reference);
 assert.match(scoreHtml,/REBA 현재 점수/);assert.match(scoreHtml,/1점/);assert.match(scoreHtml,/참고값/);assert.match(scoreHtml,/0\/33개/);assert.match(scoreHtml,/측정값 없음/);
 const confirmedHtml=reba.currentScoreCard({reba:{summary:{current_score:{total:5,risk:'MEDIUM',kind:'CONFIRMED',slot_no:2}}},measurement_quality:{slots:[{slot_no:2,measured_points:22,total_points:33,mean_confidence:.71,confidence_level:'MEDIUM'}]}});
 assert.match(confirmedHtml,/5점/);assert.match(confirmedHtml,/완성 사진 기준/);assert.match(confirmedHtml,/22\/33개/);assert.match(confirmedHtml,/보통 \(0\.71\)/);
 const assumedHtml=reba.currentScoreCard({reba:{summary:{current_score:{total:4,risk:'MEDIUM',kind:'WITH_ASSUMPTIONS',slot_no:3,assumed:['common.neck_base'],assumption:'미확인 자세를 가정했습니다.'},score_so_far:{slot_no:3,total:4,assumed:['common.neck_base'],assumption:'미확인 자세를 가정했습니다.'}}},measurement_quality:{slots:[{slot_no:3,measured_points:22,total_points:33,mean_confidence:.71,confidence_level:'MEDIUM'}]}});
 assert.match(assumedHtml,/4점/);assert.match(assumedHtml,/확정 전/);assert.match(assumedHtml,/가정한 항목 1개/);assert.match(assumedHtml,/실제 점수는 이 점수보다 높거나 낮을 수 있습니다/);
 const rowAnalysis={snapshot:{schema_version:'2.0',capture:{slots:[{slot_no:4,photo_id:44,label:'사진 4',analysis_target:true}]}},pose:{slots:[{slot_no:4,status:'VALID'}]},reba:{slots:[{slot_no:4,status:'INCOMPLETE',total:null,score_so_far:{total:1},left:{total:null},right:{total:null},missing_fields:[]}],summary:reference.reba.summary},measurement_quality:{slots:[{slot_no:4,measured_points:22,total_points:33,mean_confidence:.71,confidence_level:'MEDIUM'}]}};
 const rowHtml=reba.rebaTableRow(rowAnalysis.snapshot.capture.slots[0],rowAnalysis);
 assert.match(rowHtml,/22\/33/);assert.match(rowHtml,/보통 \(0\.71\)/);assert.match(rowHtml,/1점/,'the per-photo reference score remains numeric');
 const projectedRow=structuredClone(rowAnalysis);
 projectedRow.reba.summary.current_score={total:11,risk:'VERY_HIGH',kind:'WITH_ASSUMPTIONS',slot_no:9};
 projectedRow.reba.slots[0].score_so_far=null;
 projectedRow.reba.slots[0].current_score={total:2,risk:'LOW',kind:'WITH_ASSUMPTIONS',slot_no:4};
 const projectedRowHtml=reba.rebaTableRow(projectedRow.snapshot.capture.slots[0],projectedRow);
 assert.match(projectedRowHtml,/<strong>2점<\/strong><small>확정 전 · 가정 포함/,'a projected per-photo score stays numeric even when raw partial scoring had no anchor');
 assert.doesNotMatch(projectedRowHtml,/11점/,'the task-wide maximum must not be assigned to another photo');
 projectedRow.reba.slots[0].current_score={total:1,risk:'NEGLIGIBLE',kind:'ASSUMED_REFERENCE',slot_no:4};
 const projectedReferenceHtml=reba.rebaTableRow(projectedRow.snapshot.capture.slots[0],projectedRow);
 assert.match(projectedReferenceHtml,/<strong>1점<\/strong><small>참고값/,'reference provenance belongs to the projected photo score');

 const ai={text_id:3,purpose:'TASK_EXPLANATION',result:'GENERATED',created_at:'2026-10-27T00:00:00Z',source_current:true,is_active:false,generated_text:'전체 생성 문장',edited_text:null,content:{summary:'몸통 자세와 점수를 설명합니다.',reba_comparison:'현재 점수 설명',posture_explanations:[],criteria:[],check_items:['사진 자세를 확인하세요.'],improvement_options:[]}};
 const explanationState={analysis:{analysis_id:10,currentness:'CURRENT',ai:[ai]},aiPurpose:'TASK_EXPLANATION',aiTextId:3};
 const explanation=createExplanationView({s:explanationState,LocoReview:{evidence:()=>'<details class="evidence"><summary>세부 근거</summary></details>'},$:()=>null,e:escape,options:()=>'',select:(label,key)=>`<label>${label}<select data-field="${key}"></select></label>`,field:()=>'',drafts:{get:()=>null},card:()=>''}).explanationCard();
 assert.match(explanation,/결과 설명 생성/);assert.match(explanation,/AI 작성 · 확정 전/);assert.match(explanation,/data-field="ai-purpose"/);assert.match(explanation,/AI는 수치와 사진 분석 요약/);assert.match(explanation,/data-explanation-editor/);assert.match(explanation,/AI 작성 문장 확정/);
 assert.doesNotMatch(explanation,/AI 쉬운 설명/);
 console.log('PASS Excel data-only wording, optional advanced choices, numeric per-photo score/coverage/confidence and result explanation provenance/confirmation');
})().catch(error=>{console.error(error);process.exit(1);});
