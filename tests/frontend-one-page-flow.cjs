/* The user is asked for input on ONE page, once:
   - the two-step wizard is gone: work features, conditions, photo questions and the posture checklist are one list of fields;
   - an answer that decides which other fields exist (a work feature, the photo situation) is saved in place and the page grows, no trip through the result screen;
   - "나머지 작업은 모두 안 해요" only fills the blanks; one save finishes everything;
   - the page opens by itself at most once per analysis, and the way back from the result screen is a plain "입력 수정하기" that never asks on its own. */
const assert = require('node:assert/strict');
const path = require('node:path');
const {pathToFileURL} = require('node:url');
const url = name => pathToFileURL(path.join(__dirname, '../frontend', name)).href;

(async () => {
  const {AdaptiveIntake} = await import(url('intake/client.js'));
  const {QuickFlow} = await import(url('quick-flow.js'));
  const {captureWorkspace, workspaceDraftDiffers} = await import(url('quick-workspace-draft.js'));
  const YES_NO = [{value: 'YES', label: '예'}, {value: 'NO', label: '아니오'}];
  const ABSENT = '표시된 남은 작업은 하지 않는다고 직접 확인';
  const contract = {policy: {quick_review_interval: 5, default_condition: 'default', text_limit: 2400, form_prompt_limit: 3, optional_photo_destinations: ['context', 'view', 'manual', 'load', 'load_kg', 'load_link']},
    methods: {session: 'session', turn: 'turn'}, fields: []};
  const COND = 'photo:2';
  const base = (target, condition, extra) => ({target, identity: `${target}@${condition}`, condition, text: target, label: target, group: 'g', ...extra});
  const lift = base('work_type.lift', 'default', {kind: 'choice', choices: YES_NO, destination: {type: 'work_type'}});
  const keyboard = base('work_type.keyboard', 'default', {kind: 'choice', choices: YES_NO, destination: {type: 'work_type'}});
  const days = base('annual_work_days', 'default', {kind: 'number', maximum: 366, destination: {type: 'task'}});
  const mass = base('card.lift.load_mass_kg', 'default', {kind: 'number', destination: {type: 'card'}, gate: 'lift'});
  const context = base('context', 'default', {kind: 'choice', choices: [{value: 'YES', label: '예, 모두 맞아요'}, {value: 'NO', label: '아니오'}], destination: {type: 'context'}});
  const load = base('load', 'default', {kind: 'choice', choices: [{value: 'UNLOADED', label: '없음'}, {value: 'MEASURED', label: '있음'}], destination: {type: 'load'}});
  const seated = base('manual.COMMON.seated', COND, {kind: 'choice', choices: YES_NO, destination: {type: 'manual', scope: 'COMMON', field: 'seated'}, checklist: {group: '다리', order: 0, label: 'seated', yes: 'YES', no: 'NO'}});
  const neck = base('manual.COMMON.neck_base', COND, {kind: 'choice', choices: [{value: 1, label: '똑바로'}, {value: 2, label: '숙임'}], destination: {type: 'manual', scope: 'COMMON', field: 'neck_base'}});
  const user = (identity, value) => ({identity, target: identity.split('@')[0], condition: identity.split('@')[1], state: 'KNOWN', source: 'USER', value});

  // The service stand-in: gates decide which fields exist, exactly as the planner does.
  const service = ({facts = [], reasons = [], photo = true, model = () => []} = {}) => {
    const calls = [];
    let revision = 1;
    const known = identity => facts.find(f => f.identity === identity);
    const rows = () => [lift, keyboard, days, ...(known('work_type.lift@default')?.value === 'YES' ? [mass] : []), ...(photo ? [context, load, ...(known('context@default') ? [seated, neck] : [])] : [])];
    const snapshot = reason => ({contract, task: {task_id: 1, input_revision: revision, created_at: 't0'}, facts: structuredClone(facts), messages: [], questions: [], form_fields: structuredClone(rows()),
      remaining_count: 0, complete: false, reason: reason || null, preview: {score: {total: 2, risk: 'LOW', assumption: 'a'}}, progress: {completed_count: 0, total_count: 1, remaining_count: 1, percent: 0, dynamic: true}});
    const api = async (method, params) => {
      calls.push([method, structuredClone(params)]);
      if (method === 'intake_contract') return contract;
      if (method === 'session') return snapshot();
      for (const a of params.answers) { facts = facts.filter(f => f.identity !== a.target + '@' + a.condition); facts.push({identity: a.target + '@' + a.condition, target: a.target, condition: a.condition, state: 'KNOWN', source: 'USER', value: a.value, quote: a.quote || null}); }
      if (params.text) for (const m of model(params.text)) if (known(m.target + '@' + m.condition)?.source !== 'USER') { facts = facts.filter(f => f.identity !== m.target + '@' + m.condition); facts.push({identity: m.target + '@' + m.condition, target: m.target, condition: m.condition, state: 'KNOWN', source: 'AI', value: m.value}); }
      revision += 1;
      return snapshot(reasons.shift());
    };
    return {api, calls, fact: identity => known(identity), turns: () => calls.filter(([method]) => method === 'turn').map(([, params]) => params)};
  };

  const open = async svc => {
    const notes = [], log = {labels: [], errors: [], renders: 0, finished: 0};
    const intake = new AdaptiveIntake({changed() {}, notify: message => notes.push(message), api: svc.api});
    await intake.open(1);
    Object.assign(intake, {dialogOpen: true, pageShown: true});
    const note = {textContent: '', hidden: true}, controls = [];
    const flow = Object.create(QuickFlow.prototype);
    Object.assign(flow, {intake, busy: false, task: null, preview: null, controls,
      host: {querySelectorAll: selector => selector === '[data-intake-form]' ? controls : [], querySelector: selector => selector === '[data-intake-fill-note]' ? note : null},
      keepDraft() {}, render() { log.renders++; }, async ensureAiOn() {}, async finish() { log.finished++; }, onError(error) { log.errors.push(error.message); }, notify(message) { notes.push(message); },
      async run(label, action) { if (this.busy) return; this.busy = label; log.labels.push(label); try { await action(); } catch (error) { this.onError(error); } finally { this.busy = false; this.render(); } }});
    return {svc, intake, flow, note, log, notes, controls};
  };
  const pick = (flow, identity, value) => flow.input({target: {dataset: {intakeForm: identity}, value, setCustomValidity() {}, reportValidity() {}}});
  const press = (flow, dataset) => flow.click({target: {closest: () => ({dataset, disabled: false})}});
  const results = [];
  const check = async (name, body) => { try { await body(); results.push([name, null]); } catch (error) { results.push([name, String(error.message).split('\n')[0]]); } };
  const ids = fields => fields.map(f => f.identity);

  // 1. One list of fields: no stages, and a stage argument changes nothing.
  await check('one page, no stages', async () => {
    const t = await open(service());
    assert.deepEqual(ids(t.intake.pendingFormFields()), ['work_type.lift@default', 'work_type.keyboard@default', 'annual_work_days@default'], 'work features and conditions together; the photo rows only count when asked for');
    assert.deepEqual(ids(t.intake.pendingFormFields(0)), ids(t.intake.pendingFormFields()), 'the old stage 0 argument is ignored');
    assert.deepEqual(ids(t.intake.pendingFormFields(1)), ids(t.intake.pendingFormFields()), 'and so is stage 1');
    assert.deepEqual(ids(t.intake.pendingFormFields(undefined, {includePhoto: true})), [...ids(t.intake.pendingFormFields()), 'context@default', 'load@default']);
    assert.equal(t.intake.formFields(0).length, 5);
    assert.equal(t.intake.formFields(1).length, 5);
    t.intake.setFormValue('work_type.keyboard@default', 'NO');
    t.intake.setFormValue('annual_work_days@default', 220);
    assert.deepEqual(t.intake.formAnswers(0).map(a => a.target), ['work_type.keyboard', 'annual_work_days'], 'answers of every kind leave in one list, in form order');
    assert.deepEqual(t.intake.formAnswers(1), t.intake.formAnswers());
    assert.equal('formStage' in t.intake, false, 'there is no wizard step to remember');
    assert.equal(t.intake.hasOpenItems(), true);
  });

  // 2. A work feature answered YES brings its conditions onto the same page, saved in place with whatever else was typed.
  await check('work feature YES: its fields appear in place', async () => {
    const svc = service(), t = await open(svc);
    pick(t.flow, 'annual_work_days@default', '220');
    pick(t.flow, 'work_type.keyboard@default', '');
    await t.flow.refreshing;
    assert.equal(svc.turns().length, 0, 'a blank answer and an ordinary field save nothing');
    pick(t.flow, 'work_type.lift@default', 'YES');
    await t.flow.refreshing;
    const turns = svc.turns();
    assert.equal(turns.length, 1);
    assert.deepEqual(turns[0].answers.map(a => [a.target, a.value]), [['work_type.lift', 'YES'], ['work_type.keyboard', null], ['annual_work_days', 220]], 'what was typed rides along, a deliberate "모름" included');
    assert.equal(turns[0].text, '');
    assert.equal(turns[0].plan, false, 'no model call');
    assert.equal(t.intake.dialogOpen, true, 'the page stays open');
    assert.equal(t.log.finished, 0, 'no trip through the result screen');
    assert.equal(t.intake.formAnswers().length, 0, 'saved drafts are gone');
    assert.deepEqual(t.log.labels, ['선택한 작업의 입력칸을 불러오고 있어요…']);
    assert.ok(ids(t.intake.formFields()).includes('card.lift.load_mass_kg@default'), 'the conditions of the chosen work are on the page now');
    assert.equal(t.flow.revealPhotoRows || false, false, 'a work feature has nothing to reveal in the photo rows');
    pick(t.flow, 'work_type.lift@default', 'YES');
    await t.flow.refreshing;
    assert.equal(svc.turns().length, 1, 'saying the same thing again changes nothing');
  });
  await check('a "no" that changes nothing waits for the final save', async () => {
    const svc = service(), t = await open(svc);
    pick(t.flow, 'work_type.keyboard@default', 'NO');
    await t.flow.refreshing;
    assert.equal(svc.turns().length, 0, 'no conditions are on the page for it, so nothing is saved yet');
    assert.equal(t.intake.formValue(keyboard), 'NO', 'the answer is in the form');
    assert.equal(t.intake.changesFields(lift, 'YES'), true);
    assert.equal(t.intake.changesFields(lift, 'NO'), false);
    assert.equal(t.intake.changesFields(days, 220), false, 'an ordinary box never does');
    assert.equal(t.intake.changesFields(context, 'NO'), true, 'the photo situation always does');
  });
  await check('work feature NO after YES: the fields go away', async () => {
    const svc = service({facts: [user('work_type.lift@default', 'YES')]}), t = await open(svc);
    assert.ok(ids(t.intake.formFields()).includes('card.lift.load_mass_kg@default'));
    pick(t.flow, 'work_type.lift@default', 'NO');
    await t.flow.refreshing;
    assert.equal(svc.turns().length, 1);
    assert.equal(svc.turns()[0].answers[0].value, 'NO');
    assert.ok(!ids(t.intake.formFields()).includes('card.lift.load_mass_kg@default'));
  });
  await check('the photo situation still works the same way and a stale save keeps the answer', async () => {
    const svc = service({reasons: ['INPUT_CHANGED']}), t = await open(svc);
    pick(t.flow, 'context@default', 'YES');
    await t.flow.refreshing;
    assert.equal(t.intake.formValues.get('context@default'), 'YES', 'the answer is not lost');
    assert.equal(t.intake.dialogOpen, true);
    assert.ok(t.notes.some(message => /다른 화면에서 바뀐/.test(message)));
    const u = await open(service()), labels = [];
    u.flow.run = async function(label, action) { labels.push(label); this.revealPhotoRows && labels.push('reveal'); await action(); };
    pick(u.flow, 'context@default', 'YES');
    await u.flow.refreshing;
    assert.deepEqual(labels, ['사진 확인 내용을 저장하고 있어요…', 'reveal']);
    assert.ok(ids(u.intake.formFields()).includes('manual.COMMON.seated@photo:2'), 'the checklist row is on the page');
  });

  await check('a gate answer does not send the bulk fills', async () => {
    const svc = service(), t = await open(svc);
    press(t.flow, {quick: 'intake-no-other-work'});
    assert.equal(t.intake.formValue(keyboard), 'NO');
    pick(t.flow, 'work_type.lift@default', 'YES');
    await t.flow.refreshing;
    const sent = svc.turns()[0].answers.map(a => a.target);
    assert.deepEqual(sent, ['work_type.lift'], 'only what the user chose; the "no" for the rest waits for the save, where a typed sentence can still beat it');
    assert.equal(t.intake.formValue(keyboard), 'NO', 'and the box still shows it');
    assert.equal(t.intake.formValues.get('quote:work_type.keyboard@default'), ABSENT);
  });
  await check('the scroll position and open sections survive a gate answer', async () => {
    const svc = service(), t = await open(svc);
    const body = {scrollTop: 300}, sections = [{open: true, querySelector: () => ({textContent: '작업 조건'})}];
    t.flow.host = {querySelectorAll: selector => /details/.test(selector) ? sections : [], querySelector: selector => /intake-dialog-body/.test(selector) ? body : null};
    t.flow.render = () => { body.scrollTop = 0; sections[0].open = false; };
    pick(t.flow, 'work_type.lift@default', 'YES');
    await t.flow.refreshing;
    assert.equal(body.scrollTop, 300, 'the page is where the user left it');
    assert.equal(sections[0].open, true, 'and the section stays open');
  });

  // 3. "나머지 작업은 모두 안 해요" only fills the blanks; it never saves, never leaves the page, never overwrites.
  await check('no other work is fill-only', async () => {
    const svc = service(), t = await open(svc);
    t.controls.push({dataset: {intakeForm: 'work_type.lift@default'}, value: ''}, {dataset: {intakeForm: 'work_type.keyboard@default'}, value: ''}, {dataset: {intakeForm: 'annual_work_days@default'}, value: ''});
    t.intake.setFormValue('work_type.lift@default', 'YES');
    press(t.flow, {quick: 'intake-no-other-work'});
    assert.equal(svc.turns().length, 0, 'nothing is saved by the button');
    assert.equal(t.log.finished, 0);
    assert.equal(t.intake.dialogOpen, true, 'the page stays');
    assert.equal(t.intake.formValue(keyboard), 'NO', 'the blank work feature is "no"');
    assert.equal(t.intake.formValues.get('quote:work_type.keyboard@default'), ABSENT);
    assert.equal(t.intake.formValue(lift), 'YES', 'an answer is never overwritten');
    assert.equal(t.controls[1].value, 'NO', 'the select shows it');
    assert.equal(t.controls[0].value, '', 'and the chosen one is left alone');
    assert.equal(t.controls[2].value, '', 'only work features are touched');
    assert.match(t.note.textContent, /1개 항목을 채웠어요/);
    press(t.flow, {quick: 'intake-no-other-work'});
    assert.match(t.note.textContent, /아직 고르지 않은 작업이 없어요/, 'a second press says there is nothing left');
    // an explicit "don't know" is an answer too
    const u = await open(service());
    u.intake.formValues.set('work_type.keyboard@default', null);
    press(u.flow, {quick: 'intake-no-other-work'});
    assert.equal(u.intake.formValues.get('work_type.keyboard@default'), null, 'a deliberate blank stays blank');
    assert.equal(u.intake.formValue(lift), 'NO', 'the other blank is filled');
    await u.flow.saveIntakeForm();
    const sent = u.svc.turns()[0].answers;
    assert.ok(sent.some(a => a.target === 'work_type.lift' && a.value === 'NO' && a.quote === ABSENT), 'the save sends the fill with its sentence');
  });

  await check('a typed sentence beats "나머지 작업은 모두 안 해요"', async () => {
    const svc = service({model: text => text.includes('들기') ? [{target: 'work_type.lift', condition: 'default', value: 'YES'}] : []}), t = await open(svc);
    press(t.flow, {quick: 'intake-no-other-work'});
    t.intake.text = '들기 작업도 해요.';
    await t.flow.saveIntakeForm();
    const turns = svc.turns();
    assert.equal(turns.length, 2, 'the sentence first, the fills after it');
    assert.equal(turns[0].text, '들기 작업도 해요.');
    assert.ok(!turns[0].answers.some(a => a.quote === ABSENT), 'the first request carries no "does not apply"');
    assert.deepEqual(turns[1].answers.map(a => a.target), ['work_type.keyboard'], 'only the box the sentence left blank');
    assert.equal(turns[1].plan, false);
    assert.deepEqual([svc.fact('work_type.lift@default').value, svc.fact('work_type.lift@default').source], ['YES', 'AI']);
    assert.equal(svc.fact('work_type.keyboard@default').value, 'NO');
  });
  await check('the sentence typed in the page replaces a stale "no" draft', async () => {
    const svc = service({model: text => text.includes('들기') ? [{target: 'work_type.lift', condition: 'default', value: 'YES'}] : []}), t = await open(svc);
    press(t.flow, {quick: 'intake-no-other-work'});
    await t.flow.respondIntake('들기 작업도 해요.', []);
    assert.equal(t.intake.formValues.has('work_type.lift@default'), false, 'the draft "no" for an answered box is dropped');
    assert.equal(t.intake.formValue(lift), 'YES', 'the page shows what the sentence said');
    assert.equal(t.intake.formValue(keyboard), 'NO', 'the other fill waits for the save');
  });

  // 4. One save finishes everything.
  await check('one save: everything in one request, the page closes, the result follows', async () => {
    const svc = service({facts: [user('work_type.lift@default', 'YES'), user('context@default', 'YES')]}), t = await open(svc);
    t.intake.setFormValue('work_type.keyboard@default', 'NO');
    t.intake.setFormValue('annual_work_days@default', 220);
    t.intake.setFormValue('card.lift.load_mass_kg@default', 10);
    t.intake.setFormValue('manual.COMMON.seated@photo:2', 'NO');
    t.intake.setFormValue('manual.COMMON.neck_base@photo:2', 2);
    press(t.flow, {quick: 'intake-form-next'});
    await new Promise(resolve => setTimeout(resolve, 20));
    const turns = svc.turns();
    assert.equal(turns.length, 1, 'one request for the whole page');
    assert.deepEqual(turns[0].answers.map(a => a.target).sort(), ['annual_work_days', 'card.lift.load_mass_kg', 'manual.COMMON.neck_base', 'manual.COMMON.seated', 'work_type.keyboard']);
    assert.equal(t.intake.dialogOpen, false);
    assert.equal(t.log.finished, 1, 'the result is calculated');
    assert.equal(t.intake.formAnswers().length, 0);
    assert.deepEqual(t.log.errors, []);
  });
  await check('no wizard buttons are handled any more', async () => {
    const t = await open(service());
    t.flow.step = 'questions';
    press(t.flow, {quick: 'intake-form-back'});
    assert.equal(t.intake.dialogOpen, true, 'there is no step to go back to');
    assert.equal(typeof t.flow.saveIntakeForm.length, 'number');
  });

  // 5. The page opens by itself at most once.
  await check('the page opens once and never again by itself', async () => {
    const t = await open(service());
    Object.assign(t.intake, {dialogOpen: false, pageShown: false});
    assert.equal(t.intake.openPageOnce(), true, 'something is open and nothing was shown yet');
    assert.equal(t.intake.dialogOpen, true);
    t.intake.dialogOpen = false;
    assert.equal(t.intake.openPageOnce(), false, 'the second time it stays closed');
    assert.equal(t.intake.dialogOpen, false);
    t.intake.reset();
    await t.intake.open(1);
    assert.equal(t.intake.pageShown, false, 'a new analysis starts fresh');
    const empty = await open(service({facts: [user('work_type.lift@default', 'NO'), user('work_type.keyboard@default', 'NO'), user('annual_work_days@default', 220)], photo: false}));
    Object.assign(empty.intake, {dialogOpen: false, pageShown: false});
    assert.equal(empty.intake.hasOpenItems(), false);
    assert.equal(empty.intake.openPageOnce(), false, 'nothing to ask, nothing opens');
  });
  await check('a photo question alone opens the page; a restored draft that showed it does not', async () => {
    const answered = [user('work_type.lift@default', 'NO'), user('work_type.keyboard@default', 'NO'), user('annual_work_days@default', 220)];
    const t = await open(service({facts: answered}));
    assert.deepEqual(ids(t.intake.pendingFormFields()), [], 'nothing else is open');
    assert.equal(t.intake.hasOpenItems(), true, 'the photo situation is');
    Object.assign(t.intake, {dialogOpen: false, pageShown: false});
    t.intake.restorePage(false);
    assert.equal(t.intake.dialogOpen, true, 'a draft that never showed the page may show it');
    t.intake.dialogOpen = false;
    t.intake.restorePage(true);
    assert.equal(t.intake.dialogOpen, false, 'a draft that already showed it does not ask again');
    assert.equal(t.intake.pageShown, true);
    t.intake.state.form_fields = undefined; t.intake.state.questions = [{id: 'q'}];
    t.intake.restorePage(true);
    assert.equal(t.intake.dialogOpen, true, 'the old question list keeps its own rule');
  });
  await check('reopening a draft: the page opens only if it was never shown', async () => {
    for (const [shown, expected] of [[false, true], [true, false], [undefined, true]]) {
      const svc = service();
      const intake = new AdaptiveIntake({changed() {}, notify() {}, api: svc.api});
      const flow = Object.assign(Object.create(QuickFlow.prototype), {intake, drafts: {scope: 's'}, settings: {}, reset() {},
        async api(method, params) {
          if (method === 'get_survey') return {survey_id: 1, created_at: 'sv'};
          if (method === 'get_task') return {task: {task_id: 1, survey_id: 1, created_at: 't0', input_revision: 1, capture: {slots: []}, conditions: {}}, photos: []};
          return svc.api(method, params);
        }});
      await flow.restoreDraft({id: 'd', taskId: 1, surveyId: 1, createdAt: 'sv', taskCreatedAt: 't0', adaptive: true, photos: {}, formValues: [], step: 'questions', pageShown: shown, formStage: 1});
      assert.equal(intake.dialogOpen, expected, `shown=${shown}`);
      assert.equal('formStage' in intake, false, 'an old draft with a wizard step loads without bringing it back');
    }
  });
  await check('finishing leaves the page for good', async () => {
    const t = await open(service());
    Object.assign(t.intake, {dialogOpen: true, pageShown: false});
    t.flow.run = async () => {};
    await QuickFlow.prototype.finish.call(t.flow);
    assert.equal(t.intake.dialogOpen, false);
    assert.equal(t.intake.pageShown, true, 'it is remembered as shown');
  });
  await check('closing, saving and later turns never reopen it', async () => {
    const svc = service({facts: [user('context@default', 'YES')]}), t = await open(svc);
    t.intake.pageShown = false;
    press(t.flow, {quick: 'intake-close'});
    assert.equal(t.intake.dialogOpen, false);
    assert.equal(t.intake.pageShown, true, 'closing is remembered');
    await t.flow.respondIntake('', [{target: 'annual_work_days', condition: 'default', value: 200}]);
    assert.equal(t.intake.dialogOpen, false, 'a turn after closing does not ask again');
    t.intake.setFormValue('work_type.keyboard@default', 'NO');
    pick(t.flow, 'work_type.lift@default', 'YES');
    await t.flow.refreshing;
    assert.equal(t.intake.dialogOpen, false, 'not even a gate answer reopens it');
    await t.flow.finish();
    assert.equal(t.intake.dialogOpen, false);
  });

  // 6. The way back from an unfinished result is plain and the user's own move.
  await check('the result screen offers "입력 수정하기", not a request', async () => {
    const html = QuickFlow.prototype.postureAction.call({intake: {state: {form_fields: []}}});
    assert.match(html, /data-quick="questions"/);
    assert.match(html, />입력 수정하기</);
    assert.doesNotMatch(html, /확정|확인하고|→/, 'it is not a to-do and promises nothing');
    assert.doesNotMatch(html, /class="primary"/, 'and it is not the main button');
    assert.equal(QuickFlow.prototype.postureAction.call({intake: {state: {}}}), '', 'no form, no button');
    const t = await open(service());
    t.intake.dialogOpen = false;
    press(t.flow, {quick: 'questions', revealPhoto: '1'});
    assert.equal(t.intake.dialogOpen, true, 'the user pressed it, so the page opens');
    press(t.flow, {quick: 'intake-close'});
    assert.equal(t.intake.dialogOpen, false);
    await t.flow.respondIntake('', []);
    assert.equal(t.intake.dialogOpen, false);
  });

  // 7. A typed sentence in the page is still sent; the page closes by itself only when nothing is open any more.
  await check('respondIntake: stays while something is open, finishes when nothing is', async () => {
    const open1 = await open(service({facts: [user('work_type.lift@default', 'NO'), user('work_type.keyboard@default', 'NO'), user('annual_work_days@default', 220)]}));
    await open1.flow.respondIntake('', [{target: 'annual_work_days', condition: 'default', value: 200}]);
    assert.equal(open1.log.finished, 0, 'the photo situation is still open: no result yet');
    assert.equal(open1.intake.dialogOpen, true);
    const done = await open(service({facts: [user('work_type.lift@default', 'NO'), user('work_type.keyboard@default', 'NO'), user('annual_work_days@default', 220), user('context@default', 'YES'), user('load@default', 'UNLOADED'),
      user('manual.COMMON.seated@photo:2', 'NO'), user('manual.COMMON.neck_base@photo:2', 1)]}));
    await done.flow.respondIntake('', [{target: 'annual_work_days', condition: 'default', value: 200}]);
    assert.equal(done.log.finished, 1, 'nothing left: the result follows');
    assert.equal(done.intake.dialogOpen, false);
  });

  // 8. The look of the page survives the redraw: scroll position, opened sections, the focused box.
  await check('scroll, open sections and focus are kept across the in-place redraw', async () => {
    const t = await open(service());
    const body = {scrollTop: 240}, sections = [{open: true, querySelector: () => ({textContent: '사진 확인'})}, {open: false, querySelector: () => ({textContent: '자세 체크리스트'})}];
    const focused = {focus() { this.focused = true; }};
    t.flow.host = {querySelectorAll: selector => /details/.test(selector) ? sections : [], querySelector: selector => /intake-dialog-body/.test(selector) ? body : /data-intake-form="annual_work_days@default"/.test(selector) ? focused : null,
      ownerDocument: {activeElement: {dataset: {intakeForm: 'annual_work_days@default'}}}};
    const ui = t.flow.captureDialogUi();
    body.scrollTop = 0; sections[0].open = false; sections[1].open = true;
    t.flow.restoreDialogUi(ui);
    assert.equal(body.scrollTop, 240);
    assert.deepEqual(sections.map(s => s.open), [true, false]);
    assert.equal(focused.focused, true);
    t.flow.host = {querySelectorAll: () => [], querySelector: () => null};
    assert.doesNotThrow(() => t.flow.restoreDialogUi(t.flow.captureDialogUi()), 'a page that is not there is not an error');
  });

  await check('a checkpoint remembers that the page was shown and knows no wizard step', async () => {
    const t = await open(service());
    const flow = Object.assign(Object.create(QuickFlow.prototype), {step: 'provisional', intake: t.intake, photos: {}, drafts: {scope: 's'}});
    t.intake.pageShown = true;
    const shown = captureWorkspace(flow);
    assert.equal(shown.intake.pageShown, true);
    assert.equal('formStage' in shown.intake, false);
    t.intake.pageShown = false;
    assert.equal(captureWorkspace(flow).intake.pageShown, false);
    // an old checkpoint or draft that still carries a wizard step is read without trouble and the step plays no part in "changed"
    const old = {...shown, ui: {intakeText: '', answers: {}, group: 0}, intake: {...shown.intake, formStage: 1, formValues: []}};
    assert.equal(workspaceDraftDiffers(old, {intakeText: '', reply: '', answers: {}, group: 0, formValues: [], photos: {}, formStage: 0}), false, 'a different old step is no difference');
    assert.equal(workspaceDraftDiffers(old, {intakeText: '', reply: '', answers: {}, group: 0, formValues: [['x', 1]], photos: {}}), true, 'a different value still is');
  });

  for (const [name, failure] of results) console.log(failure ? `FAIL ${name}: ${failure}` : `ok   ${name}`);
  if (results.some(([, failure]) => failure)) process.exitCode = 1; else console.log(`PASS one page flow (${results.length} sections)`);
})().catch(error => { console.error(error); process.exitCode = 1; });
