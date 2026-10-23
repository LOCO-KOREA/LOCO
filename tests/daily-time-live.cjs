/* Reported two-duration input -> actual AI -> restart -> calculation -> Excel. No OS input. */
const {_electron}=require('../frontend/node_modules/playwright');
const fs=require('node:fs/promises'),path=require('node:path'),assert=require('node:assert/strict');
const root=path.resolve(__dirname,'..'),directory=process.env.LOCO_VERIFY_DIR||path.join(root,'.local',`daily-time-live-${Date.now()}`);
const statement='손을 이미지대로 높이 드는 걸 한 2시간 하고 키보드 작업 6시간 해.';
const receipt={kind:'actual AI, offscreen Electron/Python/SQLite/MediaPipe/Excel; reported duration pattern and public photo',checks:[],errors:[]};
let app,page,budget=420000;
const pass=text=>{receipt.checks.push(text);console.log('PASS '+text);};
async function api(method,params={}){const r=await page.evaluate(async p=>window.loco.call(p.method,p.params),{method,params});assert.equal(r.ok,true,JSON.stringify(r.error));return r.value;}
async function poll(read,test){const end=Date.now()+budget;while(Date.now()<end){const v=await read();if(test(v))return v;await new Promise(r=>setTimeout(r,100));}throw Error('State did not settle');}
async function launch(){
 const env={...process.env,LOCO_HIDDEN:'1',LOCO_DB_PATH:path.join(directory,'loco.db'),LOCO_PYTHON:path.join(root,'.venv/Scripts/python.exe')};delete env.ELECTRON_RUN_AS_NODE;delete env.OPENAI_BASE_URL;
 app=await _electron.launch({executablePath:require('../frontend/node_modules/electron'),args:[`--user-data-dir=${path.join(directory,'profile')}`,path.join(root,'frontend')],cwd:root,env});
 page=await app.firstWindow();page.setDefaultTimeout(budget);page.on('pageerror',e=>receipt.errors.push(e.message));await page.locator('#connection.connected').waitFor();
 const runtime=await app.evaluate(({BrowserWindow})=>{const w=BrowserWindow.getAllWindows()[0];return {pid:process.pid,bounds:w.getBounds(),focusable:w.isFocusable()};});assert.ok(runtime.bounds.x<=-10000);assert.equal(runtime.focusable,false);
}
(async()=>{
 if(process.env.LOCO_LIVE_AI!=='1'||!process.env.OPENAI_API_KEY)throw Error('Actual AI test requires LOCO_LIVE_AI=1 and OPENAI_API_KEY.');
 await fs.mkdir(directory,{recursive:true});await launch();
 const settings=await api('get_settings');settings.gpt_enabled=true;settings.gpt_model=process.env.LOCO_LIVE_MODEL||settings.gpt_model;settings.gpt_reasoning_effort=process.env.LOCO_LIVE_REASONING_EFFORT??settings.gpt_reasoning_effort;
 settings.analysis.pose_model={...settings.pose_contract.models[process.env.LOCO_LIVE_POSE_MODEL||settings.analysis.pose_model.model_id]};budget=(2*settings.gpt_timeout_seconds+60)*1000;
 delete settings.gpt_key_present;delete settings.gpt_contract;delete settings.pose_contract;await api('update_settings',{settings});
 await page.locator('[data-quick="new"]').click();await app.evaluate(({dialog},file)=>{dialog.showOpenDialog=async()=>({canceled:false,filePaths:[file]});},path.join(root,'.local/fixtures/tensorflow-movenet-example.jpeg'));
 await page.locator('[data-choose="RIGHT"]').click();await page.locator('.quick-slot.filled').waitFor();await page.locator('[data-quick-intake]').fill(statement);await page.locator('[data-quick="analyze"]').click();await page.locator('[data-intake-dialog][open]').waitFor();
 const survey=(await api('list_surveys'))[0],task=(await api('list_tasks',{survey_id:survey.survey_id}))[0];const state=await api('intake_session',{task_id:task.task_id});
 assert.equal(state.ai.status,'CONNECTED');assert.equal(state.ai.model,settings.gpt_model);assert.equal(state.ai.reasoning_effort,settings.gpt_reasoning_effort);assert.ok(state.ai.response_id);
 assert.equal(state.task.conditions.daily_work_min,480,JSON.stringify(state.dropped));
 const value=target=>state.facts.find(f=>f.target===target);
 assert.equal(value('card.arm_over.C3_UNION').value,120);assert.equal(value('card.keyboard.C1_KEYBOARD_FOCUSED').value,360);
 const total=value('daily_work_min');assert.equal(total.source,'AI');assert.deepEqual(total.calculation.terms.map(t=>t.minutes),[120,360]);receipt.total=total;receipt.ai=state.ai;receipt.survey_id=survey.survey_id;receipt.task_id=task.task_id;
 pass('actual AI saves 120 and 360 minutes separately and their grounded 480-minute daily total');
 assert.equal(await page.locator('[data-intake-question^="daily_work_min@"]:visible').count(),0);await page.screenshot({path:path.join(directory,'01-no-repeat.png'),fullPage:true});pass('dialog does not ask the daily time already supplied as two work periods');
 await app.close();await launch();await page.locator('[data-quick="resume"]').click();await page.locator('[data-intake-dialog][open]').waitFor();
 const restored=await api('intake_session',{task_id:task.task_id});assert.equal(restored.task.conditions.daily_work_min,480);assert.deepEqual(restored.facts.find(f=>f.target==='daily_work_min').calculation,total.calculation);assert.equal(await page.locator('[data-intake-question^="daily_work_min@"]:visible').count(),0);pass('restart retains the total, calculation evidence and absence of the duplicate question');
 await page.locator('[data-intake-dialog] [data-quick="next"]').click();await page.locator('[data-quick="review"]').waitFor();const analysis=(await api('get_task_result',{task_id:task.task_id})).analysis;assert.equal(analysis.snapshot.conditions.daily_work_min,480);assert.equal(analysis.judgment.judgments.length,11);receipt.analysis_id=analysis.analysis_id;pass('real rule result snapshot uses 480 minutes while retaining the two exposure durations');
 await page.locator('[data-quick="review"]').click();await page.locator('[data-quick="preview"]').click();await page.locator('iframe[title="유해요인조사표 PDF 미리보기"]').waitFor();await page.locator('[data-quick="detail"]').click();await page.locator('.task-context').waitFor();await page.locator('[data-nav="S08"]').click();await page.locator('[data-action="export"]').waitFor();
 const workbook=path.join(directory,'daily-time-report.xlsx');await app.evaluate(({dialog},file)=>{dialog.showSaveDialog=async()=>({canceled:false,filePath:file});},workbook);await page.locator('[data-action="export"]').click();await poll(()=>api('list_export_logs',{survey_id:survey.survey_id}),logs=>logs.some(x=>x.file_path===workbook));assert.ok((await fs.stat(workbook)).size>1000);receipt.workbook=workbook;pass('latest PDF preview and retained advanced Excel UI export the actual workbook and immutable log');
 assert.deepEqual(receipt.errors,[]);receipt.completed_at=new Date().toISOString();
})().catch(async error=>{console.error(error.stack);receipt.errors.push(error.message);await page?.screenshot({path:path.join(directory,'failure.png'),fullPage:true}).catch(()=>{});process.exitCode=1;}).finally(async()=>{await fs.mkdir(directory,{recursive:true});await fs.writeFile(path.join(directory,'receipt.json'),JSON.stringify(receipt,null,2),'utf8');console.log('Evidence: '+directory);await app?.close().catch(()=>{});});
