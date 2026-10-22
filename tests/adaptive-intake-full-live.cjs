/* External OpenAI and actual Electron/Python/SQLite/MoveNet/Excel; no OS input. */
const {_electron}=require('../frontend/node_modules/playwright');
const fs=require('node:fs/promises'),path=require('node:path'),assert=require('node:assert/strict');
const root=path.resolve(__dirname,'..'),directory=process.env.LOCO_VERIFY_DIR||path.join(root,'.local',`full-live-e2e-${Date.now()}`);
const text='20kg 상자를 하루 30번 옮기는 합성 작업입니다. 하루 전체 작업시간은 8시간이고 연 220일 하며 일회성 작업은 아닙니다. 사진은 한 사람의 전신이 나온 평소 작업 모습입니다. 사진에서도 이 20kg 상자를 들고 있고 양손으로 잡기 좋은 손잡이가 있습니다.';
let app,page;
const receipt={kind:'actual external OpenAI + offscreen Electron/Python/SQLite/MoveNet/Excel; synthetic statement/public photo',checks:[],errors:[],runtime:[]};
const pass=name=>{receipt.checks.push(name);console.log('PASS '+name);};
async function api(method,params={}){const r=await page.evaluate(async p=>window.loco.call(p.method,p.params),{method,params});assert.equal(r.ok,true,JSON.stringify(r.error));return r.value;}
async function poll(read,predicate){const end=Date.now()+60000;while(Date.now()<end){const value=await read();if(predicate(value))return value;await new Promise(resolve=>setTimeout(resolve,100));}throw Error('State did not settle within 60 seconds');}
async function idle(){await page.waitForFunction(()=>!document.querySelector('#quick-workspace .quick-busy'));}
async function shot(name){await page.screenshot({path:path.join(directory,name+'.png'),fullPage:true});}
async function launch(){
 const env={...process.env,LOCO_HIDDEN:'1',LOCO_DB_PATH:path.join(directory,'loco.db'),LOCO_PYTHON:path.join(root,'.venv/Scripts/python.exe'),LOCO_MOVENET_MODEL:path.join(root,'models/movenet_lightning.tflite')};
 delete env.ELECTRON_RUN_AS_NODE;delete env.OPENAI_BASE_URL;
 app=await _electron.launch({executablePath:require('../frontend/node_modules/electron'),args:[`--user-data-dir=${path.join(directory,'profile')}`,path.join(root,'frontend')],cwd:root,env});
 page=await app.firstWindow();page.setDefaultTimeout(60000);page.on('pageerror',error=>receipt.errors.push(error.message));
 await page.locator('#connection.connected').waitFor();
 const runtime=await app.evaluate(({BrowserWindow})=>{const w=BrowserWindow.getAllWindows()[0];return {pid:process.pid,bounds:w.getBounds(),focusable:w.isFocusable()};});
 assert.ok(runtime.bounds.x<=-10000);assert.equal(runtime.focusable,false);receipt.runtime.push(runtime);
}
async function main(){
 if(process.env.LOCO_LIVE_AI!=='1'||!process.env.OPENAI_API_KEY||!process.env.LOCO_LIVE_MODEL)throw Error('Set LOCO_LIVE_AI=1, OPENAI_API_KEY and LOCO_LIVE_MODEL for this external test.');
 await fs.mkdir(directory,{recursive:true});await launch();
 const settings=await api('get_settings');delete settings.gpt_key_present;settings.gpt_enabled=true;settings.gpt_model=process.env.LOCO_LIVE_MODEL;await api('update_settings',{settings});
 await page.locator('[data-quick="new"]').click();
 // Native file dialogs alone are automated; actual image bytes and the actual output writer are used.
 await app.evaluate(({dialog},photo)=>{dialog.showOpenDialog=async()=>({canceled:false,filePaths:[photo]});},path.join(root,'.local/fixtures/tensorflow-movenet-example.jpeg'));
 await page.locator('[data-choose="RIGHT"]').click();await page.locator('.quick-slot.filled').waitFor();
 await page.locator('[data-quick-intake]').fill(text);const started=Date.now();await page.locator('[data-quick="analyze"]').click();
 await page.locator('[data-intake-dialog][open]').waitFor();receipt.elapsed_ms=Date.now()-started;
 const survey=(await api('list_surveys'))[0],task=(await api('list_tasks',{survey_id:survey.survey_id}))[0],contract=await api('intake_contract'),meta=contract.session_key;
 const facts=Object.values(task.conditions[meta].facts);
 assert.ok(facts.some(f=>f.source==='AI'));assert.equal(task.conditions.daily_work_min,480);assert.equal(task.conditions.annual_work_days,220);
 assert.ok(task.legal.criteria[7].rows.some(r=>r.load_mass_kg===20&&r.lift_count_day===30));
 assert.equal(await page.locator('[data-intake-dialog] input[type="number"]').count(),0);
 assert.equal(await page.locator('[data-intake-dialog] [data-intake-question]').count(),1);
 await page.locator('[data-intake-dialog] [data-ai-state="CONNECTED"]').waitFor();
 for(const target of ['card.lift.load_mass_kg','card.lift.lift_count_day','daily_work_min','context','one_off','task_name'])assert.equal(await page.locator(`[data-intake-question^="${target}@"]`).count(),0,target+' must not be reasked');
 assert.ok(await page.locator('[data-intake-question]').count()<=contract.policy.question_limit);
 let next=await api(contract.methods.session,{task_id:task.task_id});assert.equal(next.preview.views.RIGHT.points.length,17);
 assert.equal(next.ai.status,'CONNECTED');assert.ok(next.ai.response_id?.startsWith('resp_'));receipt.connection=next.ai;
 pass('actual AI and MoveNet save stated values; the UI asks only missing fields');
 receipt.model=process.env.LOCO_LIVE_MODEL;receipt.task_id=task.task_id;receipt.survey_id=survey.survey_id;receipt.ai_fact_count=facts.filter(f=>f.source==='AI').length;
 receipt.initial_questions=next.questions.map(q=>({target:q.target,text:q.text}));await shot('01-followup');
 await page.locator('[data-intake-reply]').fill('이 20kg 상자를 1분에 1번씩 하루 30분 들어 올려요. 지금 말한 20kg 조건이 이 작업의 모든 조건입니다.');
 await page.locator('[data-quick="adaptive-next"]').click();await idle();
 const followup=(await api('get_task',{task_id:task.task_id})).task;
 assert.ok(followup.legal.criteria[9].rows.some(r=>r.load_mass_kg===20&&r.lift_rate_min===1&&r.minutes===30));
 next=await api(contract.methods.session,{task_id:task.task_id});assert.ok(!next.questions.some(q=>q.target==='card.lift.lift_rate_min'||q.target==='card.lift.minutes'));
 pass('second actual AI turn fills rate and duration on the same 20kg condition');
 await page.keyboard.press('Escape');await page.locator('[data-intake-dialog]').waitFor({state:'detached'});
 await page.locator('.intake-summary summary').click();
 const durationIdentity=next.facts.find(f=>f.target==='daily_work_min').identity;
 await page.locator(`[data-intake-edit="${durationIdentity}"]`).click();await page.locator(`[data-intake-value="${durationIdentity}"]`).fill('420');await page.locator('.quick-steps').click();
 await poll(()=>api('get_task',{task_id:task.task_id}),r=>r.task.conditions.daily_work_min===420&&r.task.conditions[meta].facts[durationIdentity].source==='USER');
 pass('UI editing autosaves 420 minutes with USER ownership');
 next=await api(contract.methods.session,{task_id:task.task_id});
 const declined=next.questions[0];assert.ok(declined);
 await page.locator('[data-quick="questions"]').click();await page.locator('[data-intake-dialog][open]').waitFor();
 await page.locator(`[data-intake-pick="${declined.identity}"][data-value=""]`).click();await idle();
 await poll(()=>api('get_task',{task_id:task.task_id}),r=>r.task.conditions[meta].facts[declined.identity]?.source==='USER'&&r.task.conditions[meta].facts[declined.identity].value===null);
 receipt.declined_identity=declined.identity;
 await app.close();await launch();await page.locator('[data-quick="resume"]').click();await page.locator('[data-intake-dialog][open]').waitFor();
 const restored=(await api('get_task',{task_id:task.task_id})).task;
 assert.equal(restored.conditions.daily_work_min,420);assert.equal(restored.conditions[meta].facts[declined.identity].value,null);assert.equal(await page.locator(`[data-intake-question="${declined.identity}"]`).count(),0);
 pass('real app restart restores the direct correction and does not reask the declined unknown');
 await page.locator('[data-intake-reply]').fill('처음 설명에서는 하루 전체 작업시간이 8시간이라고 말했습니다. 지금 저장된 직접 수정값을 유지해 주세요.');
 await page.locator('[data-quick="adaptive-next"]').click();await idle();
 const retained=(await api('get_task',{task_id:task.task_id})).task;
 assert.equal(retained.conditions.daily_work_min,420);assert.equal(retained.conditions[meta].facts[durationIdentity].source,'USER');assert.equal(await page.locator(`[data-intake-question="${declined.identity}"]`).count(),0);
 await shot('02-restored');pass('third actual AI turn preserves USER input and the declined unknown');
 await page.locator('[data-intake-dialog] [data-quick="next"]').click();await page.locator('[data-quick="review"]').waitFor();
 const analysis=(await api('get_task_result',{task_id:task.task_id})).analysis;
 assert.equal(analysis.judgment.judgments.length,11);assert.equal(analysis.snapshot.conditions.daily_work_min,420);assert.ok(analysis.snapshot.legal.criteria[7].rows.some(r=>r.load_mass_kg===20&&r.lift_count_day===30));
 assert.ok(analysis.pose.slots.some(p=>p.points.length===17));assert.ok(analysis.judgment.judgments.some(j=>j.computed_status==='NEEDS_INPUT'));
 const snapshot=JSON.stringify(analysis.snapshot),judgment=JSON.stringify(analysis.judgment),reba=JSON.stringify(analysis.reba);
 receipt.analysis_id=analysis.analysis_id;await shot('03-result');pass('incomplete inputs still produce a real 11-criterion result with the corrected snapshot');
 await page.locator('[data-quick="review"]').click();await page.locator('[data-quick="gen-ai"]').click();await idle();
 const generated=(await api('get_analysis',{analysis_id:analysis.analysis_id})).ai.at(-1);
 receipt.explanation={result:generated.result,fallback_reason:generated.fallback_reason,purpose:generated.purpose};assert.equal(generated.result,'GENERATED',JSON.stringify(receipt.explanation));
 await page.locator('[data-quick="apply-ai"]').click();await idle();
 let stored=await api('get_analysis',{analysis_id:analysis.analysis_id});assert.ok(stored.ai.some(a=>a.text_id===generated.text_id&&a.is_active&&a.applied_text===generated.generated_text));
 assert.equal(JSON.stringify(stored.snapshot),snapshot);assert.equal(JSON.stringify(stored.judgment),judgment);assert.equal(JSON.stringify(stored.reba),reba);
 await page.locator('[data-rev="reviewer"]').fill('합성 E2E 검토자');await page.locator('[data-rev="note"]').fill('숨김 창 실스택 검증');await page.locator('[data-quick="reviewed"]').click();await idle();
 assert.equal((await api('get_survey',{survey_id:survey.survey_id})).review.reviewed,true);await shot('04-review');pass('actual AI explanation applies and review saves without changing the calculation snapshot');
 await page.locator('[data-quick="preview"]').click();await page.locator('.quick-tabs [role="tab"]').first().waitFor();
 const workbook=path.join(directory,'actual-live-report.xlsx');await app.evaluate(({dialog},file)=>{dialog.showSaveDialog=async()=>({canceled:false,filePath:file});},workbook);
 await page.locator('[data-quick="excel"]').click();await page.locator('.quick-ok').filter({hasText:'저장한 파일:'}).waitFor();assert.ok((await fs.stat(workbook)).size>1000);
 const logs=await api('list_export_logs',{survey_id:survey.survey_id});assert.equal(logs.length,1);receipt.workbook=workbook;
 await shot('05-excel');pass('UI preview and real Excel writer produce a workbook and an export snapshot');
 await app.close();await launch();await page.locator(`[data-open="${survey.survey_id}"]`).click();await page.locator('[data-quick="review"]').waitFor();
 stored=(await api('get_task_result',{task_id:task.task_id})).analysis;assert.equal(stored.analysis_id,analysis.analysis_id);assert.equal(JSON.stringify(stored.snapshot),snapshot);assert.equal(JSON.stringify(stored.judgment),judgment);assert.ok(stored.ai.some(a=>a.is_active&&a.text_id===generated.text_id));
 assert.equal((await api('get_survey',{survey_id:survey.survey_id})).review.reviewed,true);await page.locator('[data-quick="review"]').click();await page.locator('[data-quick="unreview"]').waitFor();await shot('06-reopened');
 pass('second restart reopens the result, applied AI text and saved review');assert.deepEqual(receipt.errors,[]);receipt.completed_at=new Date().toISOString();
}
main().catch(async error=>{console.error(error.stack);receipt.errors.push(error.message);await shot('failure').catch(()=>{});process.exitCode=1;}).finally(async()=>{await fs.mkdir(directory,{recursive:true});await fs.writeFile(path.join(directory,'receipt.json'),JSON.stringify(receipt,null,2),'utf8');console.log('Evidence: '+directory);await app?.close().catch(()=>{});});
