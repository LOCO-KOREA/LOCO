/* "Analyze" shows the first score at once and lets the AI part finish behind it.
   The pose measurement needs no AI, so the user must not stare at a spinner for the minutes the AI takes. While the AI turn is out the run stays locked:
   everything that would send something is disabled, so two requests can never overlap, and a late answer never lands on a screen the user has left. */
const assert = require('node:assert/strict');
const path = require('node:path');
const {pathToFileURL} = require('node:url');
const url = name => pathToFileURL(path.join(__dirname, '../frontend', name)).href;

(async () => {
  const {QuickFlow} = await import(url('quick-flow.js'));
  const {AdaptiveIntake} = await import(url('intake/client.js'));
  const contract = {policy: {quick_review_interval: 5, default_condition: 'default', text_limit: 2400, form_prompt_limit: 3, optional_photo_destinations: ['context', 'view', 'manual', 'load', 'load_kg', 'load_link']},
    methods: {session: 'session', turn: 'turn'}, fields: []};
  const preview = {score: {total: 4, risk: 'MEDIUM', assumption: '확인하지 못한 항목은 부담 없음으로 가정한 점수예요.'}, measured: [], front: [], diagnostics: [], views: {}, questions: []};
  const field = {target: 'work_type.lift', identity: 'work_type.lift@default', condition: 'default', kind: 'choice', label: '들기 작업', text: 't', group: '작업 특징',
    choices: [{value: 'YES', label: '예'}, {value: 'NO', label: '아니오'}], destination: {type: 'work_type'}};
  const snapshot = ({reason = null, withPreview = preview} = {}) => ({contract, task: {task_id: 1, input_revision: 1, created_at: 't0'}, facts: [], messages: [], questions: [], form_fields: [field],
    remaining_count: 1, complete: false, reason, preview: withPreview, progress: {completed_count: 0, total_count: 1, remaining_count: 1, percent: 0, dynamic: true}});
  const photo = {RIGHT: {photo: {photo_id: 17, width_px: 100, height_px: 100}, image: {data_url: 'data:,', width_px: 100, height_px: 100}}};
  const deferred = () => { let resolve, reject; const promise = new Promise((res, rej) => { resolve = res; reject = rej; }); return {promise, resolve, reject}; };
  const until = async (condition, what) => { for (let i = 0; i < 400; i++) { if (condition()) return; await new Promise(resolve => setTimeout(resolve, 5)); } throw new Error('timed out waiting for ' + what); };

  // The service stand-in: `session` is the pose-only state (no AI), `turn` is the slow AI call that the test settles by hand.
  const make = ({photos = photo, openPreview = preview, onAiOn = () => {}} = {}) => {
    const log = {renders: [], errors: [], calls: []}, turn = deferred();
    const intake = new AdaptiveIntake({changed() {}, notify() {}, api: async method => {
      log.calls.push(method);
      if (method === 'intake_contract') return contract;
      if (method === 'session') return snapshot({withPreview: openPreview});
      return turn.promise;
    }});
    const host = {innerHTML: '', querySelectorAll: () => [], querySelector: () => null};
    const flow = Object.create(QuickFlow.prototype);
    Object.assign(flow, {intake, host, busy: false, step: 'start', stale: true, photos, intakeText: '상자를 하루 30번 들어요', task: null, survey: null, preview: null, group: 0, settings: {}, answers: {},
      async ensureTask() { this.task = {task_id: 1, created_at: 't0', input_revision: 1}; },
      async ensureAiOn() { log.calls.push('ai-on'); await onAiOn(intake); },
      keepDraft() {}, notify() {}, onError(error) { log.errors.push(error.message); },
      render() { log.renders.push({step: this.step, busy: this.busy, html: this.step === 'provisional' ? this.viewProvisional() : ''}); }});
    return {flow, intake, log, turn, turns: () => log.calls.filter(call => call === 'turn').length, lastRender: () => log.renders.at(-1)};
  };
  const disabledButtons = html => [...html.matchAll(/<button\b[^>]*data-quick="(photos|questions|next|intake)"[^>]*>/g)].map(match => [match[1], /\bdisabled\b/.test(match[0])]);

  // 1. The first score is on screen, locked, before the AI answers; the dialog opens after it, as it always did.
  {
    const t = make(), done = t.flow.analyze();
    await until(() => t.turns() === 1, 'the AI turn to be sent');
    assert.equal(t.flow.step, 'provisional', 'the first score screen is up while the AI works');
    assert.equal(t.flow.preview.score.total, 4);
    assert.equal(t.flow.task.task_id, 1);
    assert.equal(t.flow.stale, true, 'the analysis is not finished yet');
    assert.equal(t.flow.intake.dialogOpen, false, 'the dialog waits for the answers');
    const early = t.log.renders.find(item => item.step === 'provisional');
    assert.ok(early, 'a provisional render happened before the turn returned');
    assert.match(early.busy, /AI가 사진과 작업 설명을 정리하고 있어요.*1차 점수는 먼저 보여 드려요/, 'the wait is explained in plain words');
    assert.match(early.html, /1차 REBA 점수/);
    assert.match(early.html, />4<\/strong><span>점/, 'the score itself is shown');
    const buttons = disabledButtons(t.lastRender().html);
    assert.deepEqual(buttons.map(([name]) => name).sort(), ['intake', 'next', 'photos', 'photos', 'questions'], 'every control that could send or leave is on the screen');
    assert.ok(buttons.every(([, disabled]) => disabled), 'and every one of them is disabled while the AI works: ' + JSON.stringify(buttons));
    assert.match(t.lastRender().html, /<div inert>/, 'the saved-values list cannot be edited while the AI works');
    await t.flow.analyze();
    assert.equal(t.turns(), 1, 'a second press never starts a second request');
    t.turn.resolve(snapshot());
    await done;
    assert.equal(t.flow.busy, false);
    assert.equal(t.flow.stale, false);
    assert.equal(t.flow.step, 'provisional');
    assert.equal(t.flow.intake.dialogOpen, true, 'the dialog opens when the answers are back');
    assert.deepEqual(disabledButtons(t.lastRender().html).filter(([, disabled]) => disabled), [], 'everything is usable again');
    assert.equal(t.turns(), 1);
    assert.deepEqual(t.log.errors, []);
  }

  // 2. The AI answers with a reason: the first score stays and the dialog opens with the reason, as before.
  {
    const t = make(), done = t.flow.analyze();
    await until(() => t.turns() === 1, 'the AI turn');
    t.turn.resolve(snapshot({reason: 'AI_ERROR'}));
    await done;
    assert.equal(t.flow.step, 'provisional');
    assert.equal(t.flow.intake.state.reason, 'AI_ERROR');
    assert.equal(t.flow.intake.dialogOpen, true, 'the reason is shown in the dialog');
    assert.equal(t.flow.preview.score.total, 4);
  }

  // 3. The AI call throws: the first score is not taken away, the error is shown once, and the way on stays open.
  {
    const t = make(), done = t.flow.analyze();
    await until(() => t.turns() === 1, 'the AI turn');
    t.turn.reject(new Error('연결이 끊겼어요'));
    await done;
    assert.deepEqual(t.log.errors, ['연결이 끊겼어요']);
    assert.equal(t.flow.busy, false);
    assert.equal(t.flow.step, 'provisional', 'the first score stays on screen');
    assert.equal(t.flow.preview.score.total, 4);
    assert.equal(t.flow.stale, true, 'the analysis is still open, so it can be run again');
    assert.equal(t.flow.intake.dialogOpen, false);
    assert.deepEqual(disabledButtons(t.lastRender().html).filter(([, disabled]) => disabled), [], 'the buttons are back, so the user can go on by hand');
  }

  // 4. Without a photo nothing is shown early: there is no pose score and the order is exactly as before.
  {
    const t = make({photos: {}}), done = t.flow.analyze();
    await until(() => t.turns() === 1, 'the AI turn');
    assert.equal(t.flow.step, 'start');
    assert.ok(t.log.renders.every(item => item.step === 'start'), 'no early provisional screen for a sentence alone');
    t.turn.resolve(snapshot());
    await done;
    assert.equal(t.flow.step, 'provisional');
    assert.equal(t.flow.intake.dialogOpen, true);
  }

  // 5. A photo the pose could not score has nothing to show early: the wait stays as it was.
  {
    const t = make({openPreview: {...preview, score: null}}), done = t.flow.analyze();
    await until(() => t.turns() === 1, 'the AI turn');
    assert.equal(t.flow.step, 'start');
    assert.ok(t.log.renders.every(item => item.step === 'start'));
    t.turn.resolve(snapshot());
    await done;
    assert.equal(t.flow.step, 'provisional');
  }

  // 6. Something else takes the screen while the AI works: the late answer neither crashes nor overwrites it.
  {
    const t = make(), done = t.flow.analyze();
    await until(() => t.turns() === 1, 'the AI turn');
    t.intake.reset();
    Object.assign(t.flow, {step: 'start', task: null, preview: null, stale: true});
    t.turn.resolve(snapshot());
    await done;
    assert.equal(t.flow.step, 'start', 'the late answer did not switch the screen');
    assert.equal(t.flow.task, null);
    assert.equal(t.flow.preview, null);
    assert.equal(t.flow.intake.dialogOpen, false);
    assert.equal(t.flow.stale, true);
    assert.deepEqual(t.log.errors, []);
  }

  // 7. Something else takes the screen while the AI switch is made (even a new session is open by then): the sentence is never sent to that other task.
  {
    const t = make({onAiOn: async intake => { intake.reset(); await intake.open(2, {}); }}); // another analysis opens its own session meanwhile
    await Promise.race([t.flow.analyze(), new Promise(resolve => setTimeout(resolve, 300))]); // a regression would leave the sent request unanswered: fail on the count, never hang
    assert.equal(t.turns(), 0, 'no request left for a task nobody is looking at');
    assert.deepEqual(t.log.errors, []);
  }

  console.log('PASS analyze shows the first score at once, locks every sending control while the AI works, keeps the score on failure, ignores late answers and leaves sentence-only analysis as before');
})().catch(error => { console.error(error); process.exitCode = 1; });
