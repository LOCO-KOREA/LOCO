/* The order things are saved in, and the one dialog that follows the photo question:
   - "확인 끝" says "does not apply" only for boxes nobody answered, so it goes out after the typed sentence and never overrides what the sentence says;
   - answering the photo situation in the open dialog saves it right there and the checklist appears in the same dialog;
   - the note under the form expires as soon as the user edits or leaves. */
const assert = require('node:assert/strict');
const path = require('node:path');
const {pathToFileURL} = require('node:url');
const url = name => pathToFileURL(path.join(__dirname, '../frontend', name)).href;

(async () => {
  const client = await import(url('intake/client.js'));
  const {AdaptiveIntake} = client;
  const {QuickFlow} = await import(url('quick-flow.js'));
  const CONFIRM = '자세 체크리스트에서 체크하지 않은 항목을 해당 없음으로 직접 확인';
  const YES_NO = [{value: 'YES', label: '예'}, {value: 'NO', label: '아니오'}];
  const contract = {policy: {quick_review_interval: 5, default_condition: 'default', text_limit: 2400, form_prompt_limit: 3, optional_photo_destinations: ['context', 'view', 'manual', 'load', 'load_kg', 'load_link']},
    methods: {session: 'session', turn: 'turn'}, fields: []};
  const COND = 'photo:2';
  const ITEMS = [['trunk_twisted', 0], ['trunk_side_bent', 1], ['neck_twisted', 2], ['neck_side_bent', 3], ['shoulder_raised', 4, 'ARM'], ['arm_abducted_or_rotated', 5, 'ARM'], ['arm_supported_or_gravity_assisted', 6, 'ARM'],
    ['wrist_deviated_or_twisted', 7, 'ARM'], ['seated', 8], ['shock_force', 9], ['static_over_1min', 10], ['small_repeat_over_4min', 11], ['rapid_change_or_unstable', 12]];
  const flags = ITEMS.flatMap(([field, order, kind]) => (kind === 'ARM' ? ['LEFT', 'RIGHT'] : ['COMMON']).map(scope => ({target: `manual.${scope}.${field}`, identity: `manual.${scope}.${field}@${COND}`, condition: COND,
    kind: 'choice', label: field, text: field, group: '사진 자세 보완', photo_label: '오른쪽에서 찍은 사진', choices: YES_NO, destination: {type: 'manual', scope, field},
    checklist: {group: '몸통·목', order, label: field, yes: 'YES', no: 'NO'}})));
  const neck = {target: 'manual.COMMON.neck_base', identity: `manual.COMMON.neck_base@${COND}`, condition: COND, kind: 'choice', label: 'neck_base', text: 'neck_base', group: '사진 자세 보완', photo_label: '오른쪽에서 찍은 사진',
    choices: [{value: 1, label: '똑바로'}, {value: 2, label: '숙임'}], destination: {type: 'manual', scope: 'COMMON', field: 'neck_base'}};
  const context = {target: 'context', identity: 'context@default', condition: 'default', kind: 'choice', label: '올린 사진이 모두 한 사람의 전신이 나온 평소 작업 모습인가요?', text: 'context', group: '사진 확인',
    choices: [{value: 'YES', label: '예, 모두 맞아요'}, {value: 'NO', label: '아니오'}], destination: {type: 'context'}};
  const load = {target: 'load', identity: 'load@default', condition: 'default', kind: 'choice', label: '이 순간 손에 든 물건이 있나요?', text: 'load', group: '사진 확인',
    choices: [{value: 'UNLOADED', label: '없음'}, {value: 'MEASURED', label: '있음'}], destination: {type: 'load'}};
  const by = (scope, field) => `manual.${scope}.${field}@${COND}`;
  const user = (identity, value) => ({identity, target: identity.split('@')[0], condition: identity.split('@')[1], state: 'KNOWN', source: 'USER', value});

  // A small stand-in for the service with the two rules these tests depend on: an answer of the user wins over a model value in the same request,
  // and the photo rows exist only once the photo situation is answered (a refused photo is described by hand, so its rows come back too).
  const service = ({facts = [], model = () => [], reasons = []} = {}) => {
    const calls = [];
    let revision = 1;
    const known = identity => facts.find(f => f.identity === identity);
    const rows = () => known('context@default') ? [context, load, ...flags, neck] : [context, load];
    const snapshot = reason => ({contract, task: {task_id: 1, input_revision: revision, created_at: 't0'}, facts: structuredClone(facts), messages: [], questions: [], form_fields: structuredClone(rows()),
      remaining_count: 0, complete: false, reason: reason || null, preview: {}, progress: {completed_count: 0, total_count: 1, remaining_count: 1, percent: 0, dynamic: true}});
    const put = (identity, fact) => { facts = facts.filter(f => f.identity !== identity); facts.push({identity, target: identity.split('@')[0], condition: identity.split('@')[1], state: 'KNOWN', ...fact}); };
    const api = async (method, params) => {
      calls.push([method, structuredClone(params)]);
      if (method === 'intake_contract') return contract;
      if (method === 'session') return snapshot();
      for (const a of params.answers) put(a.target + '@' + a.condition, {source: 'USER', value: a.value, quote: a.quote || null});
      if (params.text) for (const m of model(params.text)) if (known(m.target + '@' + m.condition)?.source !== 'USER') put(m.target + '@' + m.condition, {source: 'AI', value: m.value});
      revision += 1;
      return snapshot(reasons.shift());
    };
    return {api, calls, fact: identity => known(identity), turns: () => calls.filter(([method]) => method === 'turn').map(([, params]) => params)};
  };

  const open = async svc => {
    const notes = [], log = {labels: [], reveal: [], errors: [], renders: 0, finished: 0};
    const intake = new AdaptiveIntake({changed() {}, notify: message => notes.push(message), api: svc.api});
    await intake.open(1);
    Object.assign(intake, {dialogOpen: true, pageShown: true, photoEditor: true});
    const note = {textContent: '', hidden: true}, flow = Object.create(QuickFlow.prototype);
    Object.assign(flow, {intake, busy: false, task: null, preview: null, host: {querySelectorAll: () => [], querySelector: selector => selector === '[data-intake-fill-note]' ? note : null},
      keepDraft() {}, render() { log.renders++; }, async ensureAiOn() {}, async finish() { log.finished++; }, onError(error) { log.errors.push(error.message); }, notify(message) { notes.push(message); },
      async run(label, action) { if (this.busy) return; this.busy = label; log.labels.push(label); log.reveal.push(Boolean(this.revealPhotoRows)); try { await action(); } catch (error) { this.onError(error); } finally { this.busy = false; } }});
    return {svc, intake, flow, note, log, notes};
  };
  const pick = (flow, identity, value) => flow.input({target: {dataset: {intakeForm: identity}, value, setCustomValidity() {}, reportValidity() {}}});
  const tick = (flow, identity, checked) => flow.input({target: {dataset: {intakeFlag: identity}, checked}});
  const press = (flow, dataset) => flow.click({target: {closest: () => ({dataset, disabled: false})}});
  const SENTENCE = '허리를 계속 비틀어서 작업해요.';
  const model = text => text.includes('비틀') ? [{target: 'manual.COMMON.trunk_twisted', condition: COND, value: 'YES'}] : [];
  const photoAnswered = [user('context@default', 'YES'), user('load@default', 'UNLOADED')];
  const results = [];
  const check = async (name, body) => { try { await body(); results.push([name, null]); } catch (error) { results.push([name, String(error.message).split('\n')[0]]); } };

  // 1. [P1] "확인 끝" and a typed sentence: the sentence is saved first, the confirmation only fills what is still blank.
  await check('sentence first, confirmation after', async () => {
    const svc = service({facts: photoAnswered, model}), t = await open(svc);
    t.flow.fillIntakeForm({kind: 'confirm', condition: COND});
    t.intake.setFormValue(by('COMMON', 'neck_base'), 2);
    t.intake.text = SENTENCE;
    await t.flow.saveIntakeForm();
    const turns = svc.turns();
    assert.equal(turns.length, 2, 'one request for the sentence, one for the confirmation');
    assert.equal(turns[0].text, SENTENCE);
    assert.deepEqual(turns[0].answers.map(a => a.target), ['manual.COMMON.neck_base'], 'only what the user chose themselves travels with the sentence');
    assert.equal(turns[1].text, '');
    assert.equal(turns[1].plan, false, 'the confirmation never calls the model');
    assert.equal(turns[1].answers.length, flags.length - 1, 'every blank box, and not the one the sentence answered');
    assert.ok(turns[1].answers.every(a => a.quote === CONFIRM && a.value === 'NO'));
    assert.ok(!turns[1].answers.some(a => a.target === 'manual.COMMON.trunk_twisted'));
    const trunk = svc.fact(by('COMMON', 'trunk_twisted'));
    assert.deepEqual([trunk.value, trunk.source], ['YES', 'AI'], 'the sentence wins over "does not apply"');
    assert.equal(svc.fact(by('COMMON', 'seated')).value, 'NO', 'the rest is confirmed');
    assert.equal(t.intake.formAnswers().length, 0, 'saved drafts are gone');
    assert.equal(t.log.finished, 1);
  });
  await check('without a sentence: one request, same order', async () => {
    const svc = service({facts: photoAnswered}), t = await open(svc);
    t.flow.fillIntakeForm({kind: 'confirm', condition: COND});
    t.intake.setFormValue(by('COMMON', 'neck_base'), 2);
    tick(t.flow, by('COMMON', 'seated'), true);
    await t.flow.saveIntakeForm();
    const turns = svc.turns();
    assert.equal(turns.length, 1, 'no sentence, one request');
    assert.deepEqual(turns[0].answers.map(a => a.target), [...flags.map(f => f.target), 'manual.COMMON.neck_base'], 'the form order');
    assert.equal(turns[0].answers.find(a => a.target === 'manual.COMMON.seated').value, 'YES', 'the tick is kept');
    assert.equal(svc.fact(by('COMMON', 'seated')).value, 'YES');
    assert.equal(svc.fact(by('COMMON', 'static_over_1min')).value, 'NO');
  });
  await check('a confirmation for a box answered meanwhile is not sent', async () => {
    const svc = service({facts: photoAnswered}), t = await open(svc);
    t.flow.fillIntakeForm({kind: 'confirm', condition: COND});
    // Somebody else (another screen, the photo, the model) answers one box after the press.
    t.intake.state.facts.push({identity: by('COMMON', 'seated'), target: 'manual.COMMON.seated', condition: COND, state: 'KNOWN', source: 'AI', value: 'YES'});
    await t.flow.saveIntakeForm();
    assert.ok(!svc.turns().some(turn => turn.answers.some(a => a.target === 'manual.COMMON.seated')), 'the answered box keeps its value');
    assert.equal(svc.turns()[0].answers.length, flags.length - 1);
  });

  // 2. [P1 variant] "확인 끝", then "답변 정리": the model's value shows and stays; the next save does not send the old "does not apply".
  await check('confirm then sentence only', async () => {
    const svc = service({facts: photoAnswered, model}), t = await open(svc);
    t.flow.fillIntakeForm({kind: 'confirm', condition: COND});
    t.intake.text = SENTENCE;
    await t.flow.respondIntake();
    const trunkField = flags.find(f => f.identity === by('COMMON', 'trunk_twisted'));
    assert.equal(t.intake.formValues.has(by('COMMON', 'trunk_twisted')), false, 'the draft "does not apply" for an answered box is dropped');
    assert.equal(t.intake.formValue(trunkField), 'YES', 'the form shows the model value');
    assert.equal(t.intake.formAnswers().length, flags.length - 1, 'the other confirmations are still waiting for the save');
    t.intake.setFormValue(by('COMMON', 'neck_base'), 2);
    await t.flow.saveIntakeForm();
    assert.ok(!svc.turns().some(turn => turn.answers.some(a => a.target === 'manual.COMMON.trunk_twisted')), 'no request ever carried a "does not apply" for the box the sentence answered');
    const trunk = svc.fact(by('COMMON', 'trunk_twisted'));
    assert.deepEqual([trunk.value, trunk.source], ['YES', 'AI']);
  });

  // 3. An explicit context edit refreshes stored data without turning all posture metadata into new questions.
  await check('photo situation YES: current posture data remains read-only', async () => {
    const svc = service(), t = await open(svc);
    assert.doesNotMatch(t.intake.dialog(false), /intake-checklist"|data-intake-flag/, 'before the answer there is no checklist');
    pick(t.flow, 'load@default', 'UNLOADED');
    pick(t.flow, 'context@default', '');
    await t.flow.refreshing;
    assert.equal(svc.turns().length, 0, 'a blank answer and a different question do not save anything');
    pick(t.flow, 'context@default', 'YES');
    await t.flow.refreshing;
    const turns = svc.turns();
    assert.equal(turns.length, 1);
    assert.deepEqual(turns[0].answers.map(a => a.target).sort(), ['context', 'load'], 'what was typed so far is saved with it');
    assert.equal(turns[0].text, '');
    assert.equal(turns[0].plan, false, 'no model call');
    assert.equal(t.intake.dialogOpen, true, 'the dialog stays open');
    assert.equal(t.log.finished, 0, 'no trip through the result screen');
    assert.equal(t.intake.formAnswers().length, 0, 'saved drafts are gone');
    assert.deepEqual(t.log.labels, ['사진 확인 내용을 저장하고 있어요…'], 'busy while saving');
    assert.deepEqual(t.log.reveal, [true], 'the photo rows are shown opened while it saves');
    assert.equal(t.flow.revealPhotoRows, false, 'and only that once');
    const html = t.intake.dialog(false);
    assert.equal((html.match(/data-intake-data=/g)||[]).length,flags.length+3,'context, load and every posture value remain accessible');
    assert.doesNotMatch(html,/data-intake-flag=|data-intake-form=|data-fill-kind=/,'refreshing context does not demand 18 posture answers');
    assert.match(html,/목 굽힘/);assert.match(html,/미확인/,'an unobserved angle remains a data state');
    pick(t.flow, 'context@default', 'YES');
    await t.flow.refreshing;
    assert.equal(svc.turns().length, 1, 'saying the same thing again changes nothing');
    assert.equal(t.intake.formAnswers().length, 0);
  });
  await check('photo situation NO: what the service returns is shown', async () => {
    const svc = service(), t = await open(svc);
    pick(t.flow, 'context@default', 'NO');
    await t.flow.refreshing;
    assert.equal(svc.turns().length, 1);
    assert.equal(svc.turns()[0].answers[0].value, 'NO');
    assert.equal((t.intake.dialog(false).match(/data-intake-data=/g)||[]).length,flags.length+3,'the refused photo retains its explicit correction data');
    assert.doesNotMatch(t.intake.dialog(false),/data-intake-flag=|data-intake-form=/,'refusing photo use does not create forced posture questions');
    assert.equal(t.log.errors.length, 0);
  });
  await check('a stale save keeps the answer and says why', async () => {
    const svc = service({reasons: ['INPUT_CHANGED']}), t = await open(svc);
    pick(t.flow, 'context@default', 'YES');
    await t.flow.refreshing;
    assert.equal(t.intake.formValues.get('context@default'), 'YES', 'the answer is not lost');
    assert.equal(t.intake.dialogOpen, true);
    assert.ok(t.notes.some(message => /다른 화면에서 바뀐/.test(message)), 'the reason reaches the user');
    assert.equal(t.flow.revealPhotoRows, false);
  });
  await check('any other reason is shown, not swallowed', async () => {
    const svc = service({reasons: ['API_ERROR']}), t = await open(svc);
    pick(t.flow, 'context@default', 'YES');
    await t.flow.refreshing;
    assert.equal(t.intake.formValues.get('context@default'), 'YES');
    assert.equal(t.log.errors.length, 1);
    assert.ok(t.log.errors[0].length > 5);
  });
  await check('only the dialog photo rows are opened, and only when the posture button asked', async () => {
    const t = await open(service());
    const sections = [{open: false}, {open: false}];
    t.flow.host = {querySelectorAll: selector => /data-intake-direct-fields/.test(selector) && /data-intake-photo-optional/.test(selector) ? sections : []};
    t.flow.openPhotoRows();
    assert.deepEqual(sections.map(s => s.open), [true, true]);
    assert.match(QuickFlow.prototype.postureAction.call({intake: {state: {form_fields: []}}}), /data-reveal-photo="1"/, 'the posture button asks for the rows to be shown');
    const u = await open(service({facts: photoAnswered}));
    u.flow.revealPhotoRows = false;
    press(u.flow, {quick: 'questions', revealPhoto: '1'});
    assert.equal(u.flow.revealPhotoRows, true);
    press(u.flow, {quick: 'questions'});
    assert.equal(u.flow.revealPhotoRows, false, 'the plain "부족한 부분만 확인" button does not');
    u.flow.revealPhotoRows = true;
    press(u.flow, {quick: 'intake-close'});
    assert.equal(u.flow.revealPhotoRows, false, 'closing forgets it');
  });

  // 4. [P3] The note under the form is only true until the user changes something or leaves.
  await check('the note expires', async () => {
    const svc = service({facts: photoAnswered}), t = await open(svc);
    t.flow.fillIntakeForm({kind: 'confirm', condition: COND});
    assert.match(t.note.textContent, new RegExp(`${flags.length}개 항목을 채웠어요`));
    assert.equal(t.note.hidden, false);
    tick(t.flow, by('COMMON', 'seated'), true);
    assert.equal(t.intake.fillNote, '', 'a tick ends the note');
    assert.equal(t.note.textContent, '');
    assert.equal(t.note.hidden, true);
    t.flow.setFillNote('x');
    tick(t.flow, by('COMMON', 'seated'), false);
    assert.equal(t.intake.fillNote, '', 'so does an untick');
    t.flow.setFillNote('x');
    pick(t.flow, by('COMMON', 'neck_base'), '2');
    assert.equal(t.intake.fillNote, '', 'and an edit of an ordinary box');
    for (const dataset of [{quick: 'intake-close'}, {quick: 'questions'}]) {
      t.flow.setFillNote('x');
      press(t.flow, dataset);
      assert.equal(t.intake.fillNote, '', `${dataset.quick} ends the note`);
    }
  });

  // 5. The sentence that marks a bulk confirmation is the one the confirm button writes.
  await check('one confirmation sentence', async () => {
    assert.equal(client.CHECKLIST_CONFIRM_QUOTE, CONFIRM);
    const t = await open(service({facts: photoAnswered}));
    const plan = t.intake.fillPlan({kind: 'confirm', condition: COND});
    assert.ok(plan.length > 0 && plan.every(item => item.quote === client.CHECKLIST_CONFIRM_QUOTE));
  });

  for (const [name, failure] of results) console.log(failure ? `FAIL ${name}: ${failure}` : `ok   ${name}`);
  if (results.some(([, failure]) => failure)) process.exitCode = 1; else console.log(`PASS checklist flow (${results.length} sections)`);
})().catch(error => { console.error(error); process.exitCode = 1; });
