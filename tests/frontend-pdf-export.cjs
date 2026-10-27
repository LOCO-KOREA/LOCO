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
 const advanced=createExportView({s,LocoReview:{comparison:()=>'',nextInput:()=>''},inputLabel:x=>x,$:()=>null,e:String,fmt:String,badge:()=>'',field:()=>'',select:()=>'',metric:()=>'',
  card:(title,body)=>'<section><h3>'+title+'</h3>'+body+'</section>',empty:String,context:()=>''}).exportPage();
 noPdf(advanced,'advanced export');
 assert.match(advanced,/data-action="export">Excel 저장 위치 선택/);
 assert.match(advanced,/id="include-representative"/,'Excel representative-image choice remains available');
 console.log('PASS internal PDF helpers; visible Excel preview/save/comparison/cancel and no PDF entry points');
})().catch(error=>{console.error(error);process.exit(1);});
