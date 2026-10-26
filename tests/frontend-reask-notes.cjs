/* A returning question says why it returns, and "improve again" no longer promises that every answer is kept. */
const assert = require('node:assert/strict');
const path = require('node:path');
const {pathToFileURL} = require('node:url');
const url = name => pathToFileURL(path.join(__dirname, '../frontend', name)).href;

(async () => {
  const {AdaptiveIntake} = await import(url('intake/client.js'));
  const {QuickFlow} = await import(url('quick-flow.js'));
  const contract = {policy: {quick_review_interval: 5, default_condition: 'default', text_limit: 2400, form_prompt_limit: 3, optional_photo_destinations: ['context', 'view', 'manual', 'load', 'load_kg', 'load_link']},
    methods: {session: 'session', turn: 'turn'}, fields: []};
  const asked = {target: 'context', identity: 'context@default', condition: 'default', kind: 'choice', label: '사진 확인', text: '사진 확인', group: '사진 확인',
    choices: [{value: 'YES', label: '예'}, {value: 'NO', label: '아니오'}], destination: {type: 'context'}, reason: '결과 계산에 필요한 정보가 아직 없어요.'};
  const form = async (field, facts = []) => {
    const state = {contract, task: {task_id: 1, input_revision: 1}, facts, messages: [], questions: [], form_fields: [field], remaining_count: 1, complete: false,
      progress: {completed_count: 0, total_count: 1, remaining_count: 1, percent: 0, dynamic: true}};
    const intake = new AdaptiveIntake({changed() {}, notify() {}, api: async method => method === 'intake_contract' ? contract : structuredClone(state)});
    await intake.open(1);
    intake.formStage = 1;
    intake.dialogOpen = true;
    return {intake, html: intake.dialog(false)};
  };
  const why = '사진 또는 측정 설정이 바뀌어 이전 확인을 쓸 수 없어요. 다시 확인해 주세요.';
  assert.match((await form({...asked, reask: true, reason: why})).html, new RegExp(why), 'a returning photo question must show why it returns');
  assert.doesNotMatch((await form(asked)).html, /결과 계산에 필요한 정보가 아직 없어요/, 'a first-time question keeps its quiet look');


  // A photo reading the user refused is saved as KNOWN but unused: the form must ask for it, not list it as confirmed.
  const unused = {target: 'manual.COMMON.trunk_base', identity: 'manual.COMMON.trunk_base@photo:2', condition: 'photo:2', kind: 'choice', label: '몸통 굽힘', text: '몸통 굽힘',
    group: '사진 자세', choices: [{value: 3, label: '3단계'}], destination: {type: 'manual', scope: 'COMMON', field: 'trunk_base'}, photo_unused: true,
    reason: '사진 측정값은 쓰지 않기로 해서 직접 확인해 주세요.'};
  const read = [{identity: unused.identity, target: unused.target, state: 'KNOWN', source: 'POSE', value: 3, label: '몸통 굽힘'}];
  const refused = await form(unused, read);
  assert.equal(refused.intake.formHandled(unused), false, 'an unused photo reading is not handled');
  assert.equal(refused.intake.formValue(unused), undefined, 'the unused reading must not be preselected');
  assert.equal(refused.intake.pendingFormFields(1, {includePhoto: true}).length, 1);
  assert.doesNotMatch(refused.html, /data-intake-confirmed/, 'it must not be listed as already confirmed');
  assert.match(refused.html, /사진 측정값은 쓰지 않기로 해서 직접 확인해 주세요/);
  const kept = await form({...unused, photo_unused: undefined}, read);
  assert.equal(kept.intake.formHandled({...unused, photo_unused: undefined}), true, 'the same reading stays confirmed while the photo is in use');

  const flow = Object.create(QuickFlow.prototype), messages = [];
  Object.assign(flow, {result: {analysis_id: 1}, review: {reviewer: '조사자', note: ''}, reopened: false,
    async run(label, action) { await action(); }, notify(message) { messages.push(message); }});
  await flow.improveAgain();
  assert.equal(messages.length, 1);
  assert.doesNotMatch(messages[0], /이전 답변은 그대로 유지돼요/, 'photo-bound answers are not kept, so the promise must not say all answers are');
  assert.match(messages[0], /작업 종류·시간·횟수 답변은 그대로 유지/);
  assert.match(messages[0], /사진 자세 확인은 새 사진 기준으로 다시 물어봐요/);
  console.log('PASS returning photo questions say why they return; refused photo readings are asked, not listed as confirmed; improve-again wording matches what is kept');
})().catch(error => { console.error(error); process.exitCode = 1; });
