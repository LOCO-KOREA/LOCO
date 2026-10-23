/* Actual Electron -> preload -> Python -> SQLite/MoveNet/Excel. Only OpenAI HTTP and file dialogs use fixtures. */
const {_electron} = require('../frontend/node_modules/playwright');
const fs = require('node:fs/promises'), path = require('node:path'), http = require('node:http'), assert = require('node:assert/strict');
const root = path.resolve(__dirname, '..');
const directory = process.env.LOCO_VERIFY_DIR || path.join(root, '.local', `adaptive-${Date.now()}`);
const sample = path.join(root, '.local/fixtures/tensorflow-movenet-example.jpeg');
let application, page, mode = 'normal', turn = 0;
const receipt = {kind: 'real Electron/Python/SQLite/MoveNet/Excel; OpenAI loopback HTTP fixture', checks: [], errors: [], requests: []};
const mark = text => {receipt.checks.push(text); console.log('PASS '+text);};
const entry = '20kg 상자를 하루 30번 옮기고 키보드를 4시간 사용해요. 하루 전체 작업은 8시간, 연 220일이며 일회성은 아니에요. 사진은 한 사람의 전신이 나온 평소 작업 모습이에요.';
const value = (target, number, text, quote, condition = 'default') => ({target, number, text, quote, condition});
const question = (target, text) => ({target, condition: 'default', text, reason: '입력된 정보만으로 확인할 수 없는 사실이에요.'});
const server = http.createServer(async (request, response) => {
  let body = ''; for await (const part of request) body += part;
  const parsed = JSON.parse(body), payload = JSON.parse(parsed.input[1].content);
  assert.equal(parsed.text.format.name, 'loco_adaptive_intake'); assert.equal(parsed.text.format.strict, true);
  assert.ok(!body.includes('data:image'), 'no photo bytes go to OpenAI');
  receipt.requests.push({text: payload.text, known: payload.known.length, missing: payload.missing.length});
  if (mode === 'failure') {response.writeHead(503, {'content-type':'application/json'}); response.end(JSON.stringify({error:{message:'synthetic failure'}})); return;}
  let result;
  if (payload.text === entry) result = {answers: [
    value('task_name', null, '합성 상자 이동·키보드 작업', '상자를 하루 30번 옮기고 키보드를'),
    value('card.lift.load_mass_kg', 20, null, '20kg'), value('card.lift.lift_count_day', 30, null, '하루 30번'),
    value('card.keyboard.C1_KEYBOARD_FOCUSED', 240, null, '키보드를 4시간'),
    value('daily_work_min', 480, null, '하루 전체 작업은 8시간'), value('annual_work_days', 220, null, '연 220일'),
    value('one_off', null, 'NO', '일회성은 아니에요'), value('context', null, 'YES', '사진은 한 사람의 전신이 나온 평소 작업 모습이에요')],
    questions: [question('load_link', '사진에서도 같은 20kg 상자를 들고 있나요?'), question('card.lift.load_mass_kg', '다시 무게를 알려 주세요'), question('manual.COMMON.static_over_1min','같은 자세를 1분 넘게 유지하나요?')]};
  else if (payload.text.includes('사진도')) result = {answers: [
    value('load_link',null,'YES','사진도 같은 20kg 상자예요'),
    value('manual.LEFT.coupling',null,'GOOD','양손으로 잡기 좋은 손잡이가 있어요'),
    value('manual.RIGHT.coupling',null,'GOOD','양손으로 잡기 좋은 손잡이가 있어요')],
    questions:[question('manual.COMMON.static_over_1min','다시 자세 유지 시간을 알려 주세요'),question('card.lift.load_mass_kg','무게가 얼마죠?')]};
  else result = {answers:[],questions:[]};
  turn++;
  response.writeHead(200,{'content-type':'application/json'});
  response.end(JSON.stringify({id:'resp_adaptive_'+turn,object:'response',created_at:1,status:'completed',model:'fixture',output:[{id:'msg_'+turn,type:'message',status:'completed',role:'assistant',content:[{type:'output_text',text:JSON.stringify(result),annotations:[]}]}]}));
});
async function api(method, params = {}) {
  const result = await page.evaluate(async p => window.loco.call(p.method,p.params), {method,params});
  assert.equal(result.ok, true, JSON.stringify(result.error)); return result.value;
}
async function launch() {
  const env = {...process.env, LOCO_HIDDEN:'1', LOCO_PYTHON:process.env.LOCO_PYTHON||path.join(root,'.venv/Scripts/python.exe'),
    LOCO_DB_PATH:path.join(directory,'loco.db'), LOCO_MOVENET_MODEL:path.join(root,'models/movenet_lightning.tflite'),
    OPENAI_API_KEY:'local-protocol-fixture-only', OPENAI_BASE_URL:`http://127.0.0.1:${server.address().port}/v1/`};
  delete env.ELECTRON_RUN_AS_NODE;
  application = await _electron.launch({executablePath:require('../frontend/node_modules/electron'),args:[`--user-data-dir=${path.join(directory,'profile')}`,path.join(root,'frontend')],cwd:root,env});
  page = await application.firstWindow(); page.setDefaultTimeout(25000);
  page.on('pageerror', error => receipt.errors.push(error.message));
  await page.locator('#connection.connected').waitFor();
}
// Choice questions start with quick replies; these scenarios explicitly use free-text fallback.
async function fillIntakeReply(text) {
  const dialog = page.locator('[data-intake-dialog][open]');
  await dialog.waitFor();
  const write = dialog.locator('[data-quick="intake-write"]');
  if (await write.count()) await write.click();
  await dialog.locator('[data-intake-reply]').fill(text);
}
async function main() {
  await fs.mkdir(directory,{recursive:true}); await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve)); await launch();
  const settings=await api('get_settings'); delete settings.gpt_key_present; settings.gpt_enabled=true; settings.gpt_model='fixture'; await api('update_settings',{settings});
  await page.locator('[data-quick="new"]').click();
  await application.evaluate(({dialog}, photo)=>{dialog.showOpenDialog=async()=>({canceled:false,filePaths:[photo]});},sample);
  await page.locator('[data-choose="RIGHT"]').click();
  await page.locator('.quick-slot.filled').waitFor();
  await page.locator('[data-quick-intake]').fill(entry);
  await page.locator('[data-quick="analyze"]').click();
  await page.locator('[data-intake-dialog][open]').waitFor();
  const survey=(await api('list_surveys'))[0], task=(await api('list_tasks',{survey_id:survey.survey_id}))[0];
  receipt.taskId=task.task_id; receipt.surveyId=survey.survey_id;
  const connected=await api('intake_session',{task_id:task.task_id});assert.equal(connected.ai.status,'CONNECTED');assert.ok(connected.ai.response_id?.startsWith('resp_'));
  assert.equal(task.conditions.daily_work_min,480);
  assert.equal(task.legal.criteria[7].rows[0].load_mass_kg,20);
  assert.equal(task.legal.criteria[7].rows[0].lift_count_day,30);
  assert.equal(task.legal.exposures.find(e=>e.condition_code==='C1_KEYBOARD_FOCUSED').minutes,240);
  assert.ok(task.conditions.intake_session.facts['manual.COMMON.trunk_base@default']);
  mark('photo and explanation are saved in real SQLite before opening follow-up questions');
  assert.equal(await page.locator('[data-intake-dialog] input[type="number"]').count(),0);
  assert.equal(await page.locator('[data-intake-question^="card.lift.load_mass_kg@"], [data-intake-group-value^="card.lift.load_mass_kg@"], [data-intake-pair-pick^="card.lift.load_mass_kg@"]').count(),0);
  assert.equal(await page.locator('[data-intake-question^="card.lift.lift_count_day@"], [data-intake-group-value^="card.lift.lift_count_day@"], [data-intake-pair-pick^="card.lift.lift_count_day@"]').count(),0);
  assert.equal(await page.locator('[data-intake-question^="daily_work_min@"], [data-intake-group-value^="daily_work_min@"], [data-intake-pair-pick^="daily_work_min@"]').count(),0);
  assert.ok(await page.locator('[data-intake-question]').count()<=3);
  mark('only missing fields are shown; known values inside a partially filled card are not asked again');
  await fillIntakeReply('사진도 같은 20kg 상자예요. 양손으로 잡기 좋은 손잡이가 있어요.');
  await page.locator('[data-quick="adaptive-next"]').click();
  await page.locator('[data-intake-question="manual.COMMON.static_over_1min@default"]').waitFor();
  const staticGroup=page.locator('[data-intake-group-value="manual.COMMON.static_over_1min@default"]');
  if(await staticGroup.count()){
    await staticGroup.selectOption('__unknown__');await page.locator('[data-quick="intake-group-save"]').click();
  }else await page.locator('[data-intake-pick="manual.COMMON.static_over_1min@default"][data-value=""]').click();
  await page.locator('[data-intake-question="manual.COMMON.static_over_1min@default"]').waitFor({state:'detached'});
  assert.equal(await page.locator('[data-intake-question^="manual.LEFT.coupling@"], [data-intake-group-value^="manual.LEFT.coupling@"], [data-intake-pair-pick^="manual.LEFT.coupling@"]').count(),0);
  assert.equal(await page.locator('[data-intake-question^="manual.RIGHT.coupling@"], [data-intake-group-value^="manual.RIGHT.coupling@"], [data-intake-pair-pick^="manual.RIGHT.coupling@"]').count(),0);
  const saved=(await api('get_task',{task_id:task.task_id})).task;
  assert.equal(saved.capture.slots[0].observation.measured_load_kg,20);
  assert.equal(saved.manual.find(m=>m.scope==='LEFT'&&m.field==='coupling').value,'GOOD');
  mark('natural follow-up reuses the known task weight only after photo linkage and saves coupling without another question');
  await page.screenshot({path:path.join(directory,'01-followup.png'),fullPage:true});
  await application.close(); await launch();
  await page.locator('[data-quick="resume"]').click(); await page.locator('.intake-followup').waitFor();
  const restored=(await api('get_task',{task_id:task.task_id})).task;
  assert.equal(restored.conditions.intake_session.facts['manual.COMMON.static_over_1min@default'].value,null);
  assert.equal(await page.locator('[data-intake-question="manual.COMMON.static_over_1min@default"]').count(),0);
  mark('restart restores persisted values, source evidence and declined unknowns');
  mode='failure'; await fillIntakeReply('다음 질문을 다시 확인해 주세요.'); await page.locator('[data-quick="adaptive-next"]').click();
  await page.locator('[data-intake-dialog]').getByText('답변 정리를 완료하지 못했어요.',{exact:false}).waitFor();
  assert.equal(await page.locator('[data-intake-dialog] [data-quick="next"]').isEnabled(),true);
  mark('AI failure keeps the workflow and current-result button available');
  await page.locator('[data-intake-dialog] [data-quick="next"]').click(); await page.locator('[data-quick="review"]').waitFor();
  const result=await api('get_task_result',{task_id:task.task_id});
  assert.equal(result.analysis.judgment.judgments.length,11);
  assert.equal(result.analysis.snapshot.legal.criteria[7].rows[0].load_mass_kg,20);
  assert.equal(result.analysis.snapshot.legal.criteria[0].condition_present,'YES');
  assert.equal(result.analysis.snapshot.legal.criteria[1].condition_present,'UNKNOWN');
  mark('current information produces a real analysis without converting unmentioned work into false');
  await page.locator('[data-quick="preview"]').click(); await page.locator('.quick-tabs [role="tab"]').first().waitFor();
  const destination=path.join(directory,'adaptive-report.xlsx');
  await application.evaluate(({dialog},file)=>{dialog.showSaveDialog=async()=>({canceled:false,filePath:file});},destination);
  await page.locator('[data-quick="excel"]').click();
  await page.locator('.quick-ok').filter({hasText:'저장한 파일:'}).waitFor();
  assert.ok((await fs.stat(destination)).size>1000);
  const logs=await api('list_export_logs',{survey_id:survey.survey_id}); assert.equal(logs.length,1);
  receipt.analysisId=result.analysis.analysis_id; receipt.workbook=destination;
  mark('preview and Excel export use the saved real analysis and record an export snapshot');
  assert.deepEqual(receipt.errors,[]);
  await fs.writeFile(path.join(directory,'receipt.json'),JSON.stringify(receipt,null,2),'utf8');
  console.log('Evidence: '+directory);
}
main().catch(async error=>{console.error(error);receipt.errors.push(error.message);await fs.mkdir(directory,{recursive:true});await fs.writeFile(path.join(directory,'receipt.json'),JSON.stringify(receipt,null,2),'utf8');process.exitCode=1;}).finally(async()=>{await application?.close().catch(()=>{});server.closeAllConnections();await new Promise(resolve=>server.close(resolve));});
