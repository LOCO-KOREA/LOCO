/* Actual candidate modules, deferred API replies; no Electron/native dialog. */
const assert=require('node:assert/strict');
const {pathToFileURL}=require('node:url');
const path=require('node:path');
const deferred=()=>{let resolve;const promise=new Promise(r=>resolve=r);return {promise,resolve};};
(async()=>{
 const {previewPdf,exportPdf,renderPdfPreview}=await import(pathToFileURL(path.resolve(__dirname,'../frontend/pdf-export.js')).href);
 const {QuickFlow}=await import(pathToFileURL(path.resolve(__dirname,'../frontend/quick-flow.js')).href);
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
 const flow=Object.create(QuickFlow.prototype);const late=deferred();
 Object.assign(flow,{survey:{survey_id:1},task:{task_id:2},result:{analysis_id:3},step:'review',busy:false,pdfPreview:null,
  render(){},onError(error){throw error;},api:()=>late.promise});
 const opening=flow.openExcel();await Promise.resolve();flow.task={task_id:99};flow.step='start';flow.busy='newer request';
 late.resolve({data_url:'data:application/pdf;base64,JVBERi0=',overview:{tasks:[]}});await opening;
 assert.equal(flow.step,'start');assert.equal(flow.pdfPreview,null);assert.equal(flow.busy,'newer request');
 const saveDialog=deferred();global.window={loco:{choose_pdf_destination:()=>saveDialog.promise}};
 const exportCalls=[];const saving=Object.create(QuickFlow.prototype);
 Object.assign(saving,{survey:{survey_id:1},task:{task_id:2},result:{analysis_id:3},step:'excel',busy:false,
  render(){},notify(){throw new Error('stale notification');},onError(e){throw e;},
  api:async(method,args)=>{exportCalls.push([method,args]);return {file_path:'original.pdf'};}});
 const save=saving.exportExcel();await Promise.resolve();saving.task={task_id:88};saving.step='start';
 saveDialog.resolve('original.pdf');await save;
 assert.equal(exportCalls.length,1);assert.deepEqual(exportCalls[0][1].spec.task_ids,[2]);assert.equal(saving.exported,undefined);
 console.log('PASS PDF cancel, duplicate suppression, frozen targets, viewer escaping, late-response and busy ownership');
})().catch(error=>{console.error(error);process.exit(1);});
