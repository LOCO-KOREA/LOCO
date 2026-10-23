/* Opt-in external OpenAI account check, with the actual Electron/Python/SQLite/model stack. */
const {_electron}=require('../frontend/node_modules/playwright');
const fs=require('node:fs/promises'),path=require('node:path'),assert=require('node:assert/strict');
const root=path.resolve(__dirname,'..'),directory=process.env.LOCO_VERIFY_DIR||path.join(root,'.local',`adaptive-live-${Date.now()}`);
const text='20kg 상자를 하루 30번 옮기는 작업입니다. 하루 전체 작업시간은 8시간이고 연 220일 하며 일회성 작업은 아닙니다. 사진은 한 사람의 전신이 나온 평소 작업 모습입니다. 사진에서도 이 20kg 상자를 들고 있고 양손으로 잡기 좋은 손잡이가 있습니다.';
let app,page; const receipt={kind:'external OpenAI account + real Electron/Python/SQLite/pose engine; synthetic work statement and public photo',checks:[],errors:[]};
async function api(method,params={}){const r=await page.evaluate(async p=>window.loco.call(p.method,p.params),{method,params});assert.equal(r.ok,true,JSON.stringify(r.error));return r.value;}
// Choice questions start with quick replies; these scenarios explicitly use free-text fallback.
async function fillIntakeReply(text) {
  const dialog = page.locator('[data-intake-dialog][open]');
  await dialog.waitFor();
  const write = dialog.locator('[data-quick="intake-write"]');
  if (await write.count()) await write.click();
  await dialog.locator('[data-intake-reply]').fill(text);
}
async function main(){
 if(process.env.LOCO_LIVE_AI!=='1'||!process.env.OPENAI_API_KEY||!process.env.LOCO_LIVE_MODEL)throw Error('Use explicit LOCO_LIVE_AI=1, OPENAI_API_KEY and LOCO_LIVE_MODEL for this external test.');
 await fs.mkdir(directory,{recursive:true});
 const env={...process.env,LOCO_HIDDEN:'1',LOCO_DB_PATH:path.join(directory,'loco.db'),LOCO_PYTHON:process.env.LOCO_PYTHON||path.join(root,'.venv/Scripts/python.exe'),LOCO_MOVENET_MODEL:path.join(root,'models/movenet_lightning.tflite')};
 delete env.ELECTRON_RUN_AS_NODE;delete env.OPENAI_BASE_URL;
 app=await _electron.launch({executablePath:require('../frontend/node_modules/electron'),args:[`--user-data-dir=${path.join(directory,'profile')}`,path.join(root,'frontend')],cwd:root,env});
 page=await app.firstWindow();page.setDefaultTimeout(60000);page.on('pageerror',error=>receipt.errors.push(error.message));
 await page.locator('#connection.connected').waitFor();
 const settings=await api('get_settings');delete settings.gpt_key_present;settings.gpt_enabled=true;settings.gpt_model=process.env.LOCO_LIVE_MODEL;await api('update_settings',{settings});
 await page.locator('[data-quick="new"]').click();
 await app.evaluate(({dialog},photo)=>{dialog.showOpenDialog=async()=>({canceled:false,filePaths:[photo]});},path.join(root,'.local/fixtures/tensorflow-movenet-example.jpeg'));
 await page.locator('[data-choose="RIGHT"]').click();await page.locator('.quick-slot.filled').waitFor();
 await page.locator('[data-quick-intake]').fill(text);const started=Date.now();await page.locator('[data-quick="analyze"]').click();
 await page.locator('[data-intake-dialog][open]').waitFor();receipt.elapsed_ms=Date.now()-started;
 const survey=(await api('list_surveys'))[0],task=(await api('list_tasks',{survey_id:survey.survey_id}))[0];
 const facts=Object.values(task.conditions.intake_session.facts);
 assert.ok(facts.some(f=>f.source==='AI'),'real model must contribute grounded facts');
 assert.equal(task.conditions.daily_work_min,480);assert.equal(task.conditions.annual_work_days,220);
 const rows=task.legal.criteria[7].rows;
 assert.ok(rows.some(r=>r.load_mass_kg===20&&r.lift_count_day===30),'weight/count must remain paired');
 assert.equal(await page.locator('[data-intake-dialog] input[type="number"]').count(),0);
 assert.equal(await page.locator('[data-intake-question^="card.lift.load_mass_kg@"]').count(),0);
 assert.equal(await page.locator('[data-intake-question^="card.lift.lift_count_day@"]').count(),0);
 assert.equal(await page.locator('[data-intake-question^="daily_work_min@"]').count(),0);
  assert.equal(await page.locator('[data-intake-question^="context@"]').count(),0,'explicit photo context must not be asked again');
  assert.equal(await page.locator('[data-intake-question^="one_off@"]').count(),0,'explicit one-off answer must not be asked again');
  assert.equal(await page.locator('[data-intake-question^="task_name@"]').count(),0,'work title must not interrupt an already-described task');
 receipt.checks.push('actual OpenAI extracts and saves the stated values through the UI without reasking them');
 receipt.model=process.env.LOCO_LIVE_MODEL;receipt.task_id=task.task_id;receipt.ai_fact_count=facts.filter(f=>f.source==='AI').length;
 receipt.photo_point_count=null; // verified below from the actual saved preview endpoint
 const session=await api('intake_session',{task_id:task.task_id});
 assert.equal(session.ai.status,'CONNECTED');assert.equal(session.ai.model,settings.gpt_model);assert.ok(session.ai.response_id?.startsWith('resp_'),'actual success is recorded by the service, independently of hidden connection labels');
 assert.ok(!(await page.locator('[data-intake-dialog]').innerText()).includes(settings.gpt_model),'model details must stay out of the user dialog');
 receipt.photo_point_count=session.preview.views.RIGHT.points.length;assert.equal(receipt.photo_point_count,(await api('get_settings')).analysis.pose_model.point_count);
 receipt.reason=session.reason;receipt.questions=session.questions.map(q=>({target:q.target,text:q.text}));
  await fillIntakeReply('이 20kg 상자를 1분에 1번씩 하루 30분 들어 올려요. 지금 말한 20kg 조건이 이 작업의 모든 조건입니다.');
  await page.locator('[data-quick="adaptive-next"]').click();
  await page.waitForFunction(()=>!document.querySelector('#quick-workspace .quick-busy'));
  await page.waitForFunction(()=>!document.querySelector('[data-quick="adaptive-next"]')?.disabled);
  const followup=(await api('get_task',{task_id:task.task_id})).task;
  assert.ok(followup.legal.criteria[9].rows.some(r=>r.load_mass_kg===20&&r.lift_rate_min===1&&r.minutes===30),'natural follow-up must attach rate and duration to the same 20kg condition');
  const next=await api('intake_session',{task_id:task.task_id});
  assert.ok(!next.questions.some(q=>q.target==='card.lift.lift_rate_min'||q.target==='card.lift.minutes'));
  receipt.checks.push('a second actual AI turn fills rate and duration for the existing condition and stops asking them');
 await page.screenshot({path:path.join(directory,'live-followup.png'),fullPage:true});
 await page.locator('[data-intake-dialog] [data-quick="next"]').click();await page.locator('[data-quick="review"]').waitFor();
 const result=await api('get_task_result',{task_id:task.task_id});assert.equal(result.analysis.judgment.judgments.length,11);
 receipt.analysis_id=result.analysis.analysis_id;receipt.checks.push('actual account/model workflow reaches real analysis with preserved incomplete fields');
 assert.deepEqual(receipt.errors,[]);console.log(JSON.stringify({checks:receipt.checks,elapsed_ms:receipt.elapsed_ms,ai_fact_count:receipt.ai_fact_count,questions:receipt.questions}));
 await fs.writeFile(path.join(directory,'receipt.json'),JSON.stringify(receipt,null,2),'utf8');
}
main().catch(async error=>{console.error(error.message);receipt.errors.push(error.message);await fs.mkdir(directory,{recursive:true});await fs.writeFile(path.join(directory,'receipt.json'),JSON.stringify(receipt,null,2),'utf8');process.exitCode=1;}).finally(async()=>{await app?.close().catch(()=>{});});
