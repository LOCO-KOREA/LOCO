/* Ten independently recorded external-AI E2E journeys. Application code stays frozen until all finish. */
const {_electron}=require('../frontend/node_modules/playwright');
const fs=require('node:fs/promises'),path=require('node:path'),{execFileSync}=require('node:child_process');
const root=path.resolve(__dirname,'..'),python=path.join(root,'.venv/Scripts/python.exe');
const selected=process.env.LOCO_CASE_IDS?.split(',');
const cases=require('./live_output_cases.json').filter(test=>!selected||selected.includes(test.id)).map(test=>process.env.LOCO_CONFIRM_UNLOADED==='1'&&test.id==='08-zero-and-absent'?{...test,statement:test.statement+' 손으로 밀거나 당기는 힘도 전혀 없어요.',expected:{...test.expected,load:'UNLOADED'},oracle_note:'Focused verification explicitly excludes both held load and pushing/pulling force; original ten-run text is preserved.'}:test);
const directory=process.env.LOCO_CAMPAIGN_DIR||path.join(root,'.local',`live-output-ten-${Date.now()}`);
const baseline=execFileSync('git',['rev-parse','HEAD'],{cwd:root,encoding:'utf8'}).trim();
const equal=(a,b)=>JSON.stringify(a)===JSON.stringify(b),pause=()=>new Promise(r=>setTimeout(r,100));
async function run(test){
 const dir=path.join(directory,test.id);await fs.mkdir(dir,{recursive:true});await fs.writeFile(path.join(dir,'case.json'),JSON.stringify(test,null,2));
 const receipt={id:test.id,baseline,checks:[],defects:[],errors:[],exports:[],stages:[],native_input:false};let app,page,taskId,surveyId,initialAnalysis,finalAnalysis;
 const save=()=>fs.writeFile(path.join(dir,'receipt.json'),JSON.stringify(receipt,null,2));
 const event=async(action,data={})=>fs.appendFile(path.join(dir,'actions.jsonl'),JSON.stringify({sequence:receipt.stages.length,action,...data})+'\n');
 const check=(name,expected,actual)=>{const row={name,expected,actual,pass:equal(expected,actual)};receipt.checks.push(row);if(!row.pass)receipt.defects.push(row);};
 async function api(method,params={}){const r=await page.evaluate(async p=>window.loco.call(p.method,p.params),{method,params});if(!r.ok)throw Error(method+': '+JSON.stringify(r.error));return r.value;}
 async function idle(){await page.waitForFunction(()=>!document.querySelector('#quick-workspace .quick-busy'),{},{timeout:0});}
 async function state(stage){
  const session=await api('intake_session',{task_id:taskId});const bundle=await api('get_task',{task_id:taskId});
  await fs.writeFile(path.join(dir,stage+'.json'),JSON.stringify({stage,session,bundle},null,2));receipt.stages.push(stage);
  execFileSync(python,['tests/live_output_audit.py','capture',dir,stage],{cwd:root,env:{...process.env,PYTHONIOENCODING:'utf-8'}});
  const handled=new Set(session.facts.filter(f=>f.state==='KNOWN'||f.state==='UNKNOWN'&&f.source==='USER').map(f=>f.identity));const asked=[];for(const q of session.questions||[])asked.push(q,...(q.answer_questions||[]),...(q.paired_question?[q.paired_question]:[]));check(stage+': no handled identity is asked again',[],asked.filter(q=>handled.has(q.identity)).map(q=>q.identity));const shown=await page.locator('[data-intake-dialog][open] [data-intake-unanswered] [data-intake-form]').evaluateAll(nodes=>nodes.map(n=>n.dataset.intakeForm));check(stage+': no handled identity is shown as missing',[],shown.filter(id=>handled.has(id)));await save();return session;
 }
 function checkExpected(session,values,stage){for(const [target,expected] of Object.entries(values||{})){
  const facts=session.facts.filter(f=>f.target===target);let actual=Array.isArray(expected)?facts.map(f=>f.value).sort((a,b)=>a-b):facts[0]?.value;
  const wanted=Array.isArray(expected)?[...expected].sort((a,b)=>a-b):expected;check(stage+': '+target,wanted,actual??(expected===null&&facts.length?null:'MISSING'));
 }}
 async function launch(){
  const env={...process.env,LOCO_HIDDEN:'1',LOCO_DB_PATH:path.join(dir,'loco.db'),LOCO_PYTHON:python,LOCO_LIVE_TRACE:path.join(dir,'openai.jsonl'),PYTHONPATH:path.join(root,'tests/live_trace')+(process.env.PYTHONPATH?path.delimiter+process.env.PYTHONPATH:'')};delete env.ELECTRON_RUN_AS_NODE;delete env.OPENAI_BASE_URL;
  app=await _electron.launch({executablePath:require('../frontend/node_modules/electron'),args:[`--user-data-dir=${path.join(dir,'profile')}`,path.join(root,'frontend')],cwd:root,env});page=await app.firstWindow();page.setDefaultTimeout(30000);page.on('pageerror',error=>receipt.errors.push(error.message));await page.locator('#connection.connected').waitFor();
  const runtime=await app.evaluate(({BrowserWindow})=>{const w=BrowserWindow.getAllWindows()[0];return {bounds:w.getBounds(),focusable:w.isFocusable()};});check('window cannot take native focus',false,runtime.focusable);check('window is offscreen',true,runtime.bounds.x<=-10000);receipt.runtime=runtime;
 }
 async function actualTurn(text,stage){const before=await api('intake_session',{task_id:taskId});await event('natural-language-input',{text,stage});if(!await page.locator('[data-intake-reply]').isVisible()){if(await page.locator('[data-quick="intake-write"]').count())await page.locator('[data-quick="intake-write"]').click();else await page.locator('[data-intake-reply]').evaluate(el=>el.closest('details').open=true);}await page.locator('[data-intake-reply]').fill(text);await page.locator('[data-quick="adaptive-next"]').click();await idle();const s=await state(stage);check(stage+': new message stored',true,s.messages.some(m=>m.text===text&&!before.messages.some(old=>old.message_id===m.message_id)));check(stage+': new actual AI response',true,Boolean(s.ai.response_id)&&s.ai.response_id!==before.ai.response_id);check(stage+': actual AI connection','CONNECTED',s.ai.status);check(stage+': actual model','gpt-6-luna',s.ai.model);check(stage+': actual effort','xhigh',s.ai.reasoning_effort);return s;}
 async function completedAnalysis(handle){let value;do{value=await api('get_analysis',{analysis_id:handle.analysis_id});if(value.status==='RUNNING')await pause();}while(value.status==='RUNNING');return value;}
 async function exportViaApi(analysis,label){const destination=path.join(dir,label+'.xlsx');const preview=await api('preview_excel_sheets',{survey_id:surveyId,analysis_ids:[analysis.analysis_id]});await fs.writeFile(path.join(dir,label+'-preview.json'),JSON.stringify(preview,null,2));const result=await api('export_excel',{survey_id:surveyId,spec:{destination,analysis_ids:[analysis.analysis_id],include_representative:false,comparisons:[]}});receipt.exports.push({label,analysis_id:analysis.analysis_id,...result});await save();}
 async function cropPhoto(){
  const file=path.join(root,'.local/fixtures/tensorflow-movenet-example.jpeg'),source=await api('preview_photo_file',{file_path:file});
  const originalHash=require('node:crypto').createHash('sha256').update(await fs.readFile(file)).digest('hex');
  await event('photo-crop-input',{file,source_sha256:originalHash,width_px:source.width_px,height_px:source.height_px,start:[0.01,0.01],end:[0.99,0.99]});
  await app.evaluate(({dialog},file)=>{dialog.showOpenDialog=async()=>({canceled:false,filePaths:[file]});},file);
  await page.locator('[data-choose="RIGHT"]').click();await page.locator('[data-photo-crop]').waitFor();await page.waitForFunction(()=>document.querySelector('[data-photo-crop] [data-confirm]')?.disabled===false);
  const box=await page.locator('[data-photo-crop] canvas').boundingBox();await page.mouse.move(box.x+box.width*0.01,box.y+box.height*0.01);await page.mouse.down();await page.mouse.move(box.x+box.width*0.99,box.y+box.height*0.99,{steps:5});await page.mouse.up();await page.locator('[data-photo-crop] [data-confirm]').click();await page.locator('.quick-slot.filled').waitFor();
  const survey=(await api('list_surveys'))[0],task=(await api('list_tasks',{survey_id:survey.survey_id}))[0],photo=(await api('get_task',{task_id:task.task_id})).photos[0],provenance=JSON.parse(photo.notes.find(n=>n.code==='PHOTO_CROP').message);
  check('source file remains unchanged',originalHash,require('node:crypto').createHash('sha256').update(await fs.readFile(file)).digest('hex'));
  check('crop registers a distinct PNG',true,photo.file_path!==file&&photo.file_path.endsWith('.png'));check('nontrivial crop dimensions',true,photo.width_px<source.width_px&&photo.height_px<source.height_px);check('crop dimensions match provenance',[photo.width_px,photo.height_px],[provenance.crop.width,provenance.crop.height]);
  receipt.crop={photo_id:photo.photo_id,file_path:photo.file_path,width_px:photo.width_px,height_px:photo.height_px,provenance};await save();
 }
 try{
  await event('declared-test-inputs',{test,baseline});await launch();
  const settings=await api('get_settings');delete settings.gpt_key_present;settings.gpt_enabled=true;settings.gpt_model='gpt-6-luna';settings.gpt_reasoning_effort='xhigh';await api('update_settings',{settings});receipt.model=settings.gpt_model;receipt.pose_model=settings.analysis.pose_model.model_id;
  await page.locator('[data-quick="new"]').click();await event('initial-description',{text:test.statement});await page.locator('[data-quick-intake]').fill(test.statement);
  await cropPhoto();check('quick settings remain hidden',0,await page.locator('.quick-settings').count());
  surveyId=(await api('list_surveys'))[0].survey_id;taskId=(await api('list_tasks',{survey_id:surveyId}))[0].task_id;receipt.task_id=taskId;receipt.survey_id=surveyId;await state('00-before-ai');
  await page.locator('[data-quick="analyze"]').click();await idle();await page.locator('[data-intake-dialog][open]').waitFor();const first=await state('01-first-ai');checkExpected(first,test.expected,'initial extraction');check('initial actual AI','CONNECTED',first.ai.status);
  if(test.id==='06-decimal-load'&&first.facts.find(f=>f.target==='task_name')?.source==='SAVED')check('automatic title keeps the decimal number',true,first.task.task_name.startsWith('12.5'));
  await page.screenshot({path:path.join(dir,'initial.png'),fullPage:true});
  const second=await actualTurn(test.followup,'02-followup-ai');checkExpected(second,{...test.expected,...test.after_followup},'after followup');
  const repeated=await state('02a-repeated-read');check('repeated read keeps revision',second.task.input_revision,repeated.task.input_revision);check('repeated read keeps manual evidence',second.task.manual,repeated.task.manual);
  initialAnalysis=await completedAnalysis(await api('start_analysis',{task_id:taskId}));check('initial analysis finished','FINISHED',initialAnalysis.status);receipt.initial_analysis_id=initialAnalysis.analysis_id;await exportViaApi(initialAnalysis,'initial-ai-values');await state('03-initial-export');
  await page.locator('[data-intake-dialog] [data-quick="intake-close"]').first().click();await page.locator('.intake-summary > details:first-child > summary').click();
  for(const [target,value] of Object.entries(test.edits)){
   const session=await api('intake_session',{task_id:taskId});const fact=session.facts.find(f=>f.target===target);await event('direct-user-correction',{target,value});
   if(fact&&await page.locator(`[data-intake-edit="${fact.identity}"]`).count()){
    await page.locator(`[data-intake-edit="${fact.identity}"]`).click();await page.locator(`[data-intake-value="${fact.identity}"]`).fill(value===null?'':String(value));await page.locator('.quick-steps').click();
    // Wait for the UI's actual write acknowledgement, without an elapsed-time acceptance rule.
    await page.waitForFunction(()=>{const node=document.querySelector('.intake-save');return node&&node.textContent.includes('입력과 출처를 이 작업에 저장했어요.');},{},{timeout:0});
   }else{receipt.defects.push({name:'missing initial fact has no summary editor',target});await api('intake_turn',{task_id:taskId,answers:[{target,value}],plan:false});await page.reload();await page.locator('#connection.connected').waitFor();await page.locator('[data-quick="resume"]').click();await idle();await page.locator('[data-intake-dialog] [data-quick="intake-close"]').first().click();await page.locator('.intake-summary > details:first-child > summary').click();}
  }
  const direct=await state('04-direct-edits');checkExpected(direct,test.edits,'direct UI edits');for(const target of Object.keys(test.edits))check('direct owner '+target,'USER',direct.facts.find(f=>f.target===target)?.source);
  await app.close();await launch();await page.locator(`[data-quick="resume"]`).click();await idle();await page.locator('[data-intake-dialog][open]').waitFor();checkExpected(await state('05-restarted'),test.edits,'restart');
  const retained=await actualTurn('처음 설명은 그대로 보관해 주세요. 처음 설명에 있는 시간과 일수보다 지금 직접 수정해서 저장한 값을 우선해 주세요. 추가 작업은 없습니다.','06-after-correction-ai');checkExpected(retained,test.edits,'AI after direct correction');
  if(await page.locator('[data-quick="intake-form-next"]').count()){await page.locator('[data-quick="intake-form-next"]').click();await idle();await page.locator('[data-quick="intake-form-next"]').click();}else await page.locator('[data-intake-dialog] [data-quick="next"]').click();await idle();await page.locator('[data-quick="review"]').waitFor();finalAnalysis=(await api('get_task_result',{task_id:taskId})).analysis;receipt.final_analysis_id=finalAnalysis.analysis_id;await state('07-final-analysis');
  check('final analysis finished','FINISHED',finalAnalysis.status);check('Heavy 33 points',33,finalAnalysis.pose?.slots[0]?.points?.length);
  await page.locator('[data-quick="review"]').click();await event('generate-explanation');await page.locator('[data-quick="gen-ai"]').click();await idle();check('explanation uses ordinary user language',false,/NEEDS_INPUT|NOT_APPLICABLE|\bUNKNOWN\b|\bYES\b|\bNO\b/.test(await page.locator('#quick-workspace').innerText()));let ai=(await api('get_analysis',{analysis_id:finalAnalysis.analysis_id})).ai.at(-1);check('actual explanation generated','GENERATED',ai.result);receipt.explanation=ai;
  const edited=(ai.generated_text||'')+'\n검토 메모: '+test.id+'에서 직접 확인한 저장값을 사용했습니다.';await event('direct-explanation-edit',{text:edited,text_id:ai.text_id});await page.locator('[data-ai-editor] summary').click();await page.locator('[data-aidraft]').fill(edited);await page.locator('[data-quick="apply-edited"]').click();await idle();await state('08-applied-explanation');
  const frozen=(await api('get_analysis',{analysis_id:initialAnalysis.analysis_id})).snapshot;check('old initial snapshot remains unchanged',initialAnalysis.snapshot,frozen);
  await page.locator('[data-quick="preview"]').click();await page.locator('.quick-excel-page .quick-sheet').first().waitFor();check('main Excel preview remains the user output',true,(await page.locator('.quick-excel-page').innerText()).includes('Excel로 저장'));check('no PDF preview is introduced',0,await page.locator('iframe').count());await page.locator('[data-quick="detail"]').click();await page.locator('[data-nav="S08"]').click();await page.locator('[data-action="export"]').waitFor();
  const destination=path.join(dir,'final-output.xlsx');await fs.writeFile(path.join(dir,'final-output-preview.json'),JSON.stringify(await api('preview_excel_sheets',{survey_id:surveyId,analysis_ids:[finalAnalysis.analysis_id]}),null,2));await app.evaluate(({dialog},file)=>{dialog.showSaveDialog=async()=>({canceled:false,filePath:file});},destination);
  await event('final-export-via-ui',{analysis_id:finalAnalysis.analysis_id,destination});await page.locator('[data-action="export"]').click();await page.waitForFunction(()=>document.querySelector('[data-action="export"]')?.disabled===false,{},{timeout:0});const logs=await api('list_export_logs',{survey_id:surveyId});receipt.exports.push({label:'final-output',analysis_id:finalAnalysis.analysis_id,...logs.at(-1)});await state('09-final-output');await page.screenshot({path:path.join(dir,'final.png'),fullPage:true});
  await exportViaApi(initialAnalysis,'old-analysis-after-correction');await state('10-old-analysis-export');
  await app.close();await launch();const restored=await api('get_analysis',{analysis_id:finalAnalysis.analysis_id});check('final snapshot survives restart',finalAnalysis.snapshot,restored.snapshot);check('applied text survives restart',edited,restored.ai.find(a=>a.text_id===ai.text_id)?.applied_text);await state('11-final-restart');receipt.completed=true;
 }catch(error){receipt.errors.push(error.stack);await page?.screenshot({path:path.join(dir,'error.png'),fullPage:true}).catch(()=>{});}
 finally{await app?.close().catch(()=>{});await save();try{execFileSync(python,['tests/live_output_audit.py','verify',dir],{cwd:root,env:{...process.env,PYTHONIOENCODING:'utf-8'}});receipt.audit_defect_count=JSON.parse(await fs.readFile(path.join(dir,'audit.json'),'utf8')).defects.length;await save();}catch(error){receipt.audit_error=error.message;await save();}console.log(JSON.stringify({id:test.id,completed:Boolean(receipt.completed),checks:receipt.checks.length,defects:receipt.defects.length,errors:receipt.errors.length}));}
 return receipt;
}
(async()=>{
 if(!cases.length)throw Error('No matching test cases selected.');
 if(!process.env.OPENAI_API_KEY||process.env.LOCO_LIVE_AI!=='1')throw Error('Explicit live E2E requires LOCO_LIVE_AI=1 and the existing API key.');
 await fs.mkdir(directory,{recursive:true});await fs.writeFile(path.join(directory,'campaign.json'),JSON.stringify({baseline,cases,scope:'actual external Luna/xhigh, isolated DB/profile, hidden Electron, transparent SDK recording',source_frozen_for_campaign:true},null,2));
 const sourceFiles=execFileSync('git',['ls-files','--cached','--others','--exclude-standard','ergo','frontend'],{cwd:root,encoding:'utf8'}).trim().split(/\r?\n/).filter(Boolean);
 const sourceHashes={};for(const file of sourceFiles)sourceHashes[file]=require('node:crypto').createHash('sha256').update(await fs.readFile(path.join(root,file))).digest('hex');
 await fs.writeFile(path.join(directory,'application-source-manifest.json'),JSON.stringify({baseline,files:sourceHashes},null,2));
 execFileSync(python,['-c','import json,sys;from ergo.intake.contract import public_contract,response_schema;from pathlib import Path;Path(sys.argv[1]).write_text(json.dumps(dict(public=public_contract(),response_schema=response_schema()),ensure_ascii=False,indent=2),encoding="utf-8")',path.join(directory,'baseline-intake-contract.json')],{cwd:root,env:{...process.env,PYTHONIOENCODING:'utf-8'}});
 const results=[];let cursor=0;async function worker(){while(cursor<cases.length){const test=cases[cursor++];results.push(await run(test));await fs.writeFile(path.join(directory,'progress.json'),JSON.stringify(results.map(r=>({id:r.id,completed:r.completed,defects:r.defects,errors:r.errors})),null,2));}}
 await Promise.all([worker(),worker()]);await fs.writeFile(path.join(directory,'finished.json'),JSON.stringify({baseline,attempted:results.length,completed:results.filter(r=>r.completed).length,results},null,2));console.log('CAMPAIGN_FINISHED '+directory);if(results.some(r=>!r.completed||r.defects.length||r.errors.length||r.audit_error||r.audit_defect_count))process.exitCode=1;
})().catch(error=>{console.error(error.stack);process.exitCode=1;});
