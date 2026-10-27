/* The form's copy helpers (same-as-other-side, front-photo suggestion) only set boxes; the user still saves, and every filled value says how it was chosen. */
const assert = require('node:assert/strict');
const path = require('node:path');
const {pathToFileURL} = require('node:url');
const url = name => pathToFileURL(path.join(__dirname, '../frontend', name)).href;

(async () => {
  const {AdaptiveIntake} = await import(url('intake/client.js'));
  const {QuickFlow} = await import(url('quick-flow.js'));
  const YES_NO = [{value: 'YES', label: '예'}, {value: 'NO', label: '아니오'}];
  const contract = {policy: {quick_review_interval: 5, default_condition: 'default', text_limit: 2400, form_prompt_limit: 3, optional_photo_destinations: ['context', 'view', 'manual', 'load', 'load_kg', 'load_link']},
    methods: {session: 'session', turn: 'turn'}, fields: []};
  const MIRROR_QUOTE = '왼쪽은 오른쪽과 같다고 직접 선택 (선택한 때의 값)';
  const SUGGEST_QUOTE = '정면·후면 사진에서 읽은 값(12.3°)을 확인해 직접 선택';
  const row = (scope, field, choices, extra = {}, condition = 'photo:2') => ({target: `manual.${scope}.${field}`, identity: `manual.${scope}.${field}@${condition}`, condition, kind: 'choice',
    label: `${scope} ${field}`, text: field, group: '사진 자세 보완', photo_label: '오른쪽에서 찍은 사진', choices, destination: {type: 'manual', scope, field}, ...extra});
  const LEVELS = [{value: 1, label: '낮음'}, {value: 2, label: '높음'}];
  const wrist = (scope, extra, condition) => row(scope, 'wrist_base', LEVELS, extra, condition);
  const suggested = row('COMMON', 'trunk_side_bent', YES_NO, {suggestion: {value: 'YES', estimated: false, quote: '12.3°', photo_label: '정면·후면 사진', reading: '몸통이 옆으로 기울어 보여요'}});
  const unsure = row('COMMON', 'neck_side_bent', YES_NO, {suggestion: {value: 'YES', estimated: true, quote: '9.1°', photo_label: '정면·후면 사진', reading: '목이 옆으로 기울어 보여요'}});
  const fields = [wrist('LEFT'), wrist('RIGHT'), row('LEFT', 'upper_arm_base', LEVELS), row('RIGHT', 'upper_arm_base', LEVELS), row('LEFT', 'lower_arm_base', LEVELS), row('RIGHT', 'lower_arm_base', LEVELS), suggested, unsure];
  const [leftWrist, rightWrist, leftUpper, rightUpper, leftLower, rightLower] = fields;
  const facts = [{identity: rightWrist.identity, target: rightWrist.target, state: 'KNOWN', source: 'POSE', value: 2},
    {identity: rightUpper.identity, target: rightUpper.target, state: 'ESTIMATED', source: 'POSE', value: 2}];
  const calls = [];

  // A tiny stand-in for the page, built from the HTML the form really renders, so the buttons' data attributes drive the handlers.
  const camel = text => text.replace(/-([a-z])/g, (_, letter) => letter.toUpperCase());
  const parseTag = tag => ({dataset: Object.fromEntries([...tag.matchAll(/ data-([a-z-]+)="([^"]*)"/g)].map(m => [camel(m[1]), m[2]])),
    disabled: / disabled(?=[\s>])/.test(tag), hidden: / hidden(?=[\s>])/.test(tag), title: (tag.match(/ title="([^"]*)"/) || [])[1] || ''});
  const open = async (rows = fields, saved = facts) => {
    const state = {contract, task: {task_id: 1, input_revision: 1}, facts: saved, messages: [], questions: [], form_fields: rows, remaining_count: rows.length, complete: false,
      progress: {completed_count: 0, total_count: rows.length, remaining_count: rows.length, percent: 0, dynamic: true}};
    const intake = new AdaptiveIntake({changed() {}, notify() {}, api: async (method, params) => { calls.push([method, params]); return method === 'intake_contract' ? contract : structuredClone(state); }});
    await intake.open(1);
    intake.formStage = 1;
    intake.dialogOpen = true;
    const html = intake.dialog(false);
    const controls = rows.map(f => ({dataset: {intakeForm: f.identity}, value: ''}));
    const buttons = [...html.matchAll(/<button[^>]*data-quick="intake-fill"[^>]*>/g)].map(m => parseTag(m[0]));
    const lines = [...html.matchAll(/<small class="intake-suggestion"[^>]*>/g)].map(m => parseTag(m[0]));
    const note = {...parseTag(html.match(/<p class="intake-fill-note"[^>]*>/)[0]), textContent: ''};
    const drafts = {saved: 0}, flow = Object.create(QuickFlow.prototype);
    const host = {querySelectorAll: selector => selector === '[data-intake-form]' ? controls : selector === '[data-quick="intake-fill"]' ? buttons : selector === '[data-suggestion-for]' ? lines : [],
      querySelector: selector => selector === '[data-intake-fill-note]' ? note : null};
    Object.assign(flow, {intake, host, keepDraft() { drafts.saved++; }, async run(label, action) { await action(); }, async finish() { drafts.finished = true; }});
    const button = (kind, extra = {}) => buttons.find(b => b.dataset.fillKind === kind && Object.entries(extra).every(([name, value]) => b.dataset[name] === value));
    return {intake, flow, controls, buttons, lines, note, drafts, html, button};
  };
  const press = (flow, button) => flow.click({target: {closest: () => button}});
  const edit = (flow, identity, value) => flow.input({target: {dataset: {intakeForm: identity}, value, setCustomValidity() {}, reportValidity() {}}});
  const quoteOf = (intake, identity) => intake.formAnswers(1).find(a => a.target + '@' + a.condition === identity)?.quote;

  // 1. What the section shows: a titled box with only the copy buttons that apply; one with nothing to copy yet is dimmed and says why.
  const a = await open();
  const section = a.html.match(/<details class="intake-form-section" data-intake-section="angles" data-intake-photo-optional>[\s\S]*?<\/details>/)[0];
  assert.match(section, /<strong>한 번에 채우기<\/strong>/);
  assert.match(section, /왼쪽 팔·손목은 오른쪽과 같아요/);
  assert.match(section, /오른쪽 팔·손목은 왼쪽과 같아요/);
  assert.match(section, /저장해야 반영돼요/, 'the box says a click only fills the boxes');
  assert.doesNotMatch(section, /모두 해당 없음/, 'the old motion-only button is folded into the checklist');
  assert.match(section, /정면·후면 사진에서 몸통이 옆으로 기울어 보여요 \(12\.3°\)\. 맞나요\?/);
  assert.match(section, /정면·후면 사진에서 목이 옆으로 기울어 보여요, 확신은 낮아요 \(9\.1°\)\. 맞나요\?/, 'an estimate says it is unsure');
  assert.equal(a.button('mirror', {fillSide: 'LEFT'}).disabled, false, 'the measured right wrist can be copied');
  assert.equal(a.button('mirror', {fillSide: 'RIGHT'}).disabled, true, 'nothing on the left to copy yet');
  assert.equal(a.button('mirror', {fillSide: 'RIGHT'}).title, '왼쪽 값을 먼저 정해 주세요.');
  assert.match(a.html, /<footer class="intake-dialog-footer"><p class="intake-fill-note" data-intake-fill-note role="status" hidden><\/p>/, 'the message has a place inside the dialog');
  assert.doesNotMatch((await open([leftUpper], [])).html, /같아요/, 'a side whose other half is not on the form has nothing to copy from');

  // 2. The buttons follow the boxes while the user types: the left side, once filled, makes the right-from-left copy possible.
  edit(a.flow, leftLower.identity, '1');
  assert.equal(a.button('mirror', {fillSide: 'RIGHT'}).disabled, false);
  assert.equal(a.button('mirror', {fillSide: 'RIGHT'}).title, '');
  // Taking the draft value away (as an unticked box does). Picking the blank option instead is the user's explicit "don't know", which a copy no longer overwrites (see frontend-checklist-panel.cjs).
  a.intake.clearFormValue(leftLower.identity); a.flow.syncFills();
  assert.equal(a.button('mirror', {fillSide: 'RIGHT'}).disabled, true, 'and clearing it switches the button off again');
  // 3. The suggestion line disappears once the box is answered, and comes back when it is cleared.
  const line = a.lines.find(l => l.dataset.suggestionFor === suggested.identity);
  assert.equal(line.hidden, false);
  edit(a.flow, suggested.identity, 'NO');
  assert.equal(line.hidden, true, 'an answered row no longer shows the suggestion');
  assert.match(a.intake.dialog(false), new RegExp(`data-suggestion-for="${suggested.identity}" hidden`), 'an answered row stays hidden when the form is drawn again');
  edit(a.flow, suggested.identity, '');
  assert.equal(line.hidden, false);

  // 4. Same as the other side: copies answered values (typed or saved), never estimates, never over an answer; the quote says it was the value at that time.
  edit(a.flow, rightLower.identity, '2');
  const before = a.drafts.saved;
  press(a.flow, a.button('mirror', {fillSide: 'LEFT'}));
  assert.equal(a.drafts.saved, before + 1, 'a fill is kept in the unsent form draft');
  assert.equal(a.intake.formValue(leftWrist), 2, 'a saved right value is copied');
  assert.equal(quoteOf(a.intake, leftWrist.identity), MIRROR_QUOTE);
  assert.equal(a.intake.formValue(leftLower), 2, 'a typed right value is copied');
  assert.equal(a.intake.formValue(leftUpper), 2, 'the user may explicitly copy the available estimated reading');
  assert.equal(quoteOf(a.intake,leftUpper.identity),MIRROR_QUOTE,'copying still records the explicit human action');
  assert.equal(a.intake.formValue(rightLower), 2, 'the right side itself was not touched');
  assert.equal(quoteOf(a.intake, rightLower.identity), undefined);
  assert.match(a.note.textContent, /3개 항목을 채웠어요\. 저장하면 반영돼요/, 'the message is shown inside the dialog');
  assert.equal(a.note.hidden, false);
  assert.equal(a.intake.fillNote, a.note.textContent);
  assert.equal(a.controls.find(c => c.dataset.intakeForm === leftWrist.identity).value, '2', 'the visible box follows the fill');
  // A box that carries a photo estimate is the user's decision: neither side fills it.
  edit(a.flow, leftUpper.identity, '1');
  press(a.flow, a.button('mirror', {fillSide: 'RIGHT'}));
  assert.equal(a.intake.formValue(rightUpper), 2, 'an existing photo estimate is preserved and is not replaced by a copy');
  edit(a.flow, leftUpper.identity, '');
  // 5. Changing a filled box makes it the user's own answer again.
  edit(a.flow, leftWrist.identity, '1');
  assert.equal(a.intake.formValue(leftWrist), 1);
  assert.equal(quoteOf(a.intake, leftWrist.identity), undefined, 'an edited value no longer claims to come from the shortcut');

  // 6. Suggestion: one click, with the reading in the quote; an estimate is called an estimate; never over an answer.
  press(a.flow, a.button('suggest', {fillIdentity: suggested.identity}));
  assert.equal(a.intake.formValue(suggested), 'YES');
  assert.equal(quoteOf(a.intake, suggested.identity), SUGGEST_QUOTE);
  press(a.flow, a.button('suggest', {fillIdentity: unsure.identity}));
  assert.equal(quoteOf(a.intake, unsure.identity), '정면·후면 사진에서 추정한 값(9.1°)을 확인해 직접 선택');
  const b = await open();
  edit(b.flow, suggested.identity, 'NO');
  b.flow.fillIntakeForm({kind: 'suggest', identity: suggested.identity});
  assert.equal(b.intake.formValue(suggested), 'NO', 'the user said no; the suggestion cannot say yes for them');
  assert.match(b.note.textContent, /채울 수 있는 값이 없어요/);

  // 7. Nothing is saved by a click; the answers go out with their quotes when the user saves, and no draft key is left behind.
  assert.equal(calls.filter(([method]) => method === 'turn').length, 0, 'no save happened');
  const kept = new Map([...a.intake.formValues]);
  await a.flow.saveIntakeForm();
  const sent = calls.filter(([method]) => method === 'turn').at(-1)[1].answers;
  assert.equal(sent.find(x => x.target === 'manual.COMMON.trunk_side_bent').quote, SUGGEST_QUOTE);
  assert.equal(sent.find(x => x.target === 'manual.COMMON.neck_side_bent').quote.includes('추정한'), true);
  assert.equal(sent.find(x => x.target === 'manual.RIGHT.lower_arm_base').quote, undefined, 'a plain answer carries no quote');
  assert.ok(sent.every(x => !String(x.target).startsWith('quote:')), 'the draft key never leaves the client');
  assert.equal(a.intake.formValues.size, 0, 'saving leaves neither values nor quotes behind');
  assert.equal(a.intake.fillNote, '');
  assert.equal(a.drafts.finished, true);
  a.intake.formValues = kept;
  assert.equal(quoteOf(a.intake, suggested.identity), SUGGEST_QUOTE, 'a restored draft still knows how each value was chosen');
  a.intake.clearFormValue(suggested.identity);
  assert.equal(a.intake.formValues.has(suggested.identity) || a.intake.formValues.has('quote:' + suggested.identity), false);

  // 8. A box waiting for a decision about a conflict, or already saved as the user's own "don't know", is never decided by a shortcut.
  const saved = [...facts,
    {identity: leftLower.identity, target: leftLower.target, state: 'CONFLICT', source: 'AI', value: 1, conflict: {value: 2}},
    {identity: leftUpper.identity, target: leftUpper.target, state: 'UNKNOWN', source: 'USER', value: null},
    {identity: suggested.identity, target: suggested.target, state: 'CONFLICT', source: 'AI', value: 'NO', conflict: {value: 'YES'}}];
  const c = await open(fields, saved);
  edit(c.flow, rightLower.identity, '2');
  edit(c.flow, rightUpper.identity, '1');
  press(c.flow, c.button('mirror', {fillSide: 'LEFT'}));
  assert.equal(c.intake.formValue(leftLower), undefined, 'a conflicting row is left for the user');
  assert.equal(c.intake.formValue(leftUpper), undefined, 'a saved "don\'t know" is the user\'s answer');
  assert.equal(c.intake.formValue(leftWrist), 2, 'the rows that were free were copied');
  assert.equal(c.lines.some(l => l.dataset.suggestionFor === suggested.identity), false, 'no suggestion beside a row that needs a conflict decision');
  c.flow.fillIntakeForm({kind: 'suggest', identity: suggested.identity});
  assert.equal(c.intake.formValue(suggested), undefined);
  // 9. A press only touches its own photo.
  const other = [...fields, wrist('LEFT', {}, 'photo:3'), wrist('RIGHT', {}, 'photo:3'), row('LEFT', 'lower_arm_base', LEVELS, {}, 'photo:3'), row('RIGHT', 'lower_arm_base', LEVELS, {}, 'photo:3')];
  const d = await open(other, [...facts, {identity: 'manual.RIGHT.wrist_base@photo:3', target: 'manual.RIGHT.wrist_base', state: 'KNOWN', source: 'POSE', value: 1}]);
  press(d.flow, d.buttons.find(b => b.dataset.fillKind === 'mirror' && b.dataset.fillSide === 'LEFT' && b.dataset.fillCondition === 'photo:3'));
  assert.equal(d.intake.formValue({identity: 'manual.LEFT.wrist_base@photo:3'}), 1);
  assert.equal(d.intake.formValue(leftWrist), undefined, 'the first photo\'s left wrist was not copied from the second photo');
  // 10. Nothing to copy says so inside the dialog instead of silently doing nothing.
  const e = await open();
  e.flow.fillIntakeForm({kind: 'mirror', side: 'RIGHT', condition: 'photo:2'});
  assert.match(e.note.textContent, /반대쪽 값을 먼저 정해 주세요/);
  console.log('PASS copy helpers fill boxes only, keep the user\'s own answers, estimates and conflicts, say how each value was chosen, and stay in step with the boxes');
})().catch(error => { console.error(error); process.exitCode = 1; });
