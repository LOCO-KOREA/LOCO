/* One list for the yes/no posture items: the user ticks what applies, only an explicit press fills the rest with "does not apply", and the photo section then asks only what the photo could not read. */
const assert = require('node:assert/strict');
const path = require('node:path');
const {pathToFileURL} = require('node:url');
const url = name => pathToFileURL(path.join(__dirname, '../frontend', name)).href;

(async () => {
  const {AdaptiveIntake} = await import(url('intake/client.js'));
  const {QuickFlow} = await import(url('quick-flow.js'));
  const YES_NO = [{value: 'YES', label: '예'}, {value: 'NO', label: '아니오'}];
  const LEGS = [{value: 'UNILATERAL_OR_UNSTABLE', label: '예'}, {value: 'BILATERAL_STABLE', label: '아니오'}];
  const contract = {policy: {quick_review_interval: 5, default_condition: 'default', text_limit: 2400, form_prompt_limit: 3, optional_photo_destinations: ['context', 'view', 'manual', 'load', 'load_kg', 'load_link']},
    methods: {session: 'session', turn: 'turn'}, fields: []};
  const TICK = '자세 체크리스트에서 해당한다고 직접 체크';
  const CONFIRM = '자세 체크리스트에서 체크하지 않은 항목을 해당 없음으로 직접 확인';
  // The same 14 items, in the same order, as the service catalogue (an arm item has a left and a right box).
  const ITEMS = [['몸통·목', 'trunk_twisted', '몸통을 비틀어 작업함'], ['몸통·목', 'trunk_side_bent', '몸통을 옆으로 기울여 작업함'], ['몸통·목', 'neck_twisted', '목을 비틀어 작업함'], ['몸통·목', 'neck_side_bent', '목을 옆으로 기울여 작업함'],
    ['어깨·팔·손목', 'shoulder_raised', '어깨를 으쓱 들어 올림', 'ARM'], ['어깨·팔·손목', 'arm_abducted_or_rotated', '팔을 옆으로 벌리거나 돌림', 'ARM'], ['어깨·팔·손목', 'arm_supported_or_gravity_assisted', '팔을 받치거나 기대어 작업함', 'ARM'],
    ['어깨·팔·손목', 'wrist_deviated_or_twisted', '손목을 비틀거나 옆으로 꺾음(앞뒤 굽힘과 별도)', 'ARM'], ['다리', 'legs_support', '한 발로 서거나 발 받침이 불안정함', 'LEGS'], ['다리', 'seated', '앉아서 작업함'],
    ['작업 중 움직임과 힘', 'shock_force', '갑자기 큰 힘이나 충격이 가해짐'], ['작업 중 움직임과 힘', 'static_over_1min', '같은 자세를 1분 넘게 유지함'],
    ['작업 중 움직임과 힘', 'small_repeat_over_4min', '좁은 범위 동작을 1분에 4번 넘게 반복함'], ['작업 중 움직임과 힘', 'rapid_change_or_unstable', '자세가 크게 바뀌거나 불안정함']];
  const flags = (condition = 'photo:2') => ITEMS.flatMap(([group, field, label, kind], order) => (kind === 'ARM' ? ['LEFT', 'RIGHT'] : ['COMMON']).map(scope => ({
    target: `manual.${scope}.${field}`, identity: `manual.${scope}.${field}@${condition}`, condition, kind: 'choice', label: scope === 'COMMON' ? label : `${scope === 'LEFT' ? '왼쪽' : '오른쪽'} ${label}`, text: label,
    group: '사진 자세 보완', photo_label: '오른쪽에서 찍은 사진', choices: kind === 'LEGS' ? LEGS : YES_NO, destination: {type: 'manual', scope, field},
    checklist: {group, order, label, yes: kind === 'LEGS' ? 'UNILATERAL_OR_UNSTABLE' : 'YES', no: kind === 'LEGS' ? 'BILATERAL_STABLE' : 'NO'}})));
  const angle = (scope, field, choices, condition = 'photo:2') => ({target: `manual.${scope}.${field}`, identity: `manual.${scope}.${field}@${condition}`, condition, kind: 'choice', label: `${scope} ${field}`, text: field,
    group: '사진 자세 보완', photo_label: '오른쪽에서 찍은 사진', choices, destination: {type: 'manual', scope, field}});
  const LEVELS = [{value: 1, label: '낮음'}, {value: 2, label: '높음'}];
  const angles = (condition) => [angle('COMMON', 'neck_base', [{value: 1, label: '똑바로'}, {value: 2, label: '숙임'}], condition), angle('LEFT', 'wrist_base', LEVELS, condition), angle('RIGHT', 'wrist_base', LEVELS, condition)];
  const all = flags();
  const by = (scope, field, condition = 'photo:2') => `manual.${scope}.${field}@${condition}`;
  const calls = [];

  const camel = text => text.replace(/-([a-z])/g, (_, letter) => letter.toUpperCase());
  const parseTag = tag => ({dataset: Object.fromEntries([...tag.matchAll(/ data-([a-z-]+)="([^"]*)"/g)].map(m => [camel(m[1]), m[2]])),
    disabled: / disabled(?=[\s>])/.test(tag), hidden: / hidden(?=[\s>])/.test(tag), checked: / checked(?=[\s>])/.test(tag), title: (tag.match(/ title="([^"]*)"/) || [])[1] || ''});
  const open = async (rows, saved = [], busy = false) => {
    const state = {contract, task: {task_id: 1, input_revision: 1}, facts: saved, messages: [], questions: [], form_fields: rows, remaining_count: rows.length, complete: false,
      progress: {completed_count: 0, total_count: rows.length, remaining_count: rows.length, percent: 0, dynamic: true}};
    const intake = new AdaptiveIntake({changed() {}, notify() {}, api: async (method, params) => { calls.push([method, params]); return method === 'intake_contract' ? contract : structuredClone(state); }});
    await intake.open(1);
    intake.formStage = 1;
    intake.dialogOpen = true;
    const html = intake.dialog(busy);
    const selects = rows.map(f => ({dataset: {intakeForm: f.identity}, value: ''}));
    const buttons = [...html.matchAll(/<button[^>]*data-quick="intake-fill"[^>]*>/g)].map(m => parseTag(m[0]));
    const lines = [...html.matchAll(/<small class="intake-suggestion"[^>]*>/g)].map(m => parseTag(m[0]));
    const boxes = [...html.matchAll(/<input type="checkbox"[^>]*>/g)].map(m => parseTag(m[0]));
    const statuses = [...html.matchAll(/<small data-checklist-status="([^"]*)">([^<]*)<\/small>/g)].map(m => ({dataset: {checklistStatus: m[1]}, textContent: m[2]}));
    const note = {...parseTag(html.match(/<p class="intake-fill-note"[^>]*>/)[0]), textContent: ''};
    const drafts = {saved: 0}, flow = Object.create(QuickFlow.prototype);
    const pick = {'[data-intake-form]': selects, '[data-quick="intake-fill"]': buttons, '[data-suggestion-for]': lines, '[data-intake-flag]': boxes, '[data-checklist-status]': statuses};
    const host = {querySelectorAll: selector => pick[selector] || [], querySelector: selector => selector === '[data-intake-fill-note]' ? note : null};
    Object.assign(flow, {intake, host, keepDraft() { drafts.saved++; }, async run(label, action) { await action(); }, async finish() { drafts.finished = true; }});
    const button = (kind, extra = {}) => buttons.find(b => b.dataset.fillKind === kind && Object.entries(extra).every(([name, value]) => b.dataset[name] === value));
    const box = identity => boxes.find(b => b.dataset.intakeFlag === identity);
    return {intake, flow, html, buttons, boxes, lines, statuses, note, drafts, button, box};
  };
  const press = (flow, button) => flow.click({target: {closest: () => button}});
  const tick = (flow, identity, checked) => flow.input({target: {dataset: {intakeFlag: identity}, checked}});
  const edit = (flow, identity, value) => flow.input({target: {dataset: {intakeForm: identity}, value, setCustomValidity() {}, reportValidity() {}}});
  const quoteOf = (intake, identity) => intake.formAnswers(1).find(a => a.target + '@' + a.condition === identity)?.quote;
  const measured = [{identity: by('COMMON', 'trunk_base'), target: 'manual.COMMON.trunk_base', condition: 'photo:2', state: 'KNOWN', source: 'POSE', value: 3, photo_active: true},
    {identity: by('RIGHT', 'upper_arm_base'), target: 'manual.RIGHT.upper_arm_base', condition: 'photo:2', state: 'KNOWN', source: 'POSE', value: 2, photo_active: true},
    {identity: by('LEFT', 'upper_arm_base'), target: 'manual.LEFT.upper_arm_base', condition: 'photo:2', state: 'ESTIMATED', source: 'POSE', value: 2, photo_active: true}];

  // 1. The section: what the photo already measured, one checklist in four groups, then only what the photo could not read.
  const a = await open([...all, ...angles()], measured);
  assert.match(a.html, /<p class="intake-measured-note">사진이 잰 값 2개는 이미 반영했어요\./, 'an estimate is not counted as measured');
  assert.equal((a.html.match(/<section class="intake-checklist"/g) || []).length, 1);
  assert.deepEqual([...a.html.matchAll(/<legend>([^<]*)<\/legend>/g)].map(m => m[1]), ['몸통·목', '어깨·팔·손목', '다리', '작업 중 움직임과 힘']);
  assert.equal(a.boxes.length, 18, 'one box per yes/no field');
  assert.equal(a.boxes.filter(b => b.checked).length, 0);
  assert.equal((a.html.match(/class="intake-check-item intake-check-pair"/g) || []).length, 4, 'an arm item is one line with a left and a right box');
  for (const [, , label] of ITEMS.slice(0, 4)) assert.match(a.html, new RegExp(`<span>${label}</span>`), 'each twist or bend box says which one it asks');
  for (const field of all) assert.doesNotMatch(a.html, new RegExp(`data-intake-form="${field.identity}"`), 'a checklist item is not also an ordinary select');
  assert.match(a.html, /<h4 class="intake-angle-title">사진이 읽지 못해 직접 골라야 하는 항목<\/h4>/);
  assert.match(a.html, /data-intake-form="manual\.COMMON\.neck_base@photo:2"/, 'what the photo could not read is still asked');
  assert.equal(a.button('confirm').disabled, false);
  assert.equal(a.statuses[0].textContent, '체크하지 않은 18개는 아직 비어 있어요. 해당 없으면 위 버튼을 눌러 주세요.');
  assert.doesNotMatch((await open(angles())).html, /intake-checklist"/, 'no panel without yes/no rows');
  const unsorted = await open([...all, ...angles()].reverse(), []);
  assert.deepEqual([...unsorted.html.matchAll(/<legend>([^<]*)<\/legend>/g)].map(m => m[1]), ['몸통·목', '어깨·팔·손목', '다리', '작업 중 움직임과 힘'], 'the order comes from the catalogue, not from the order the rows arrive in');
  assert.equal(unsorted.boxes[0].dataset.intakeFlag, by('COMMON', 'trunk_twisted'));
  assert.doesNotMatch(unsorted.html, /intake-measured-note/, 'nothing measured, nothing claimed');
  assert.doesNotMatch((await open(angles())).html, /intake-angle-title/, 'and no extra heading either');

  // 2. A tick is the user's own answer and says so; unticking takes it back to blank (not "don't know"); nothing is saved.
  tick(a.flow, by('COMMON', 'trunk_side_bent'), true);
  assert.equal(a.intake.formValue(all.find(f => f.identity === by('COMMON', 'trunk_side_bent'))), 'YES');
  assert.equal(quoteOf(a.intake, by('COMMON', 'trunk_side_bent')), TICK);
  assert.equal(a.statuses[0].textContent.startsWith('체크하지 않은 17개'), true, 'the status follows the ticks');
  tick(a.flow, by('COMMON', 'legs_support'), true);
  assert.equal(a.intake.formValue(all.find(f => f.identity === by('COMMON', 'legs_support'))), 'UNILATERAL_OR_UNSTABLE', 'the leg box keeps its own values');
  tick(a.flow, by('COMMON', 'legs_support'), false);
  assert.equal(a.intake.formValues.has(by('COMMON', 'legs_support')), false, 'unticked means blank, never "don\'t know"');
  assert.equal(a.intake.formValues.has('quote:' + by('COMMON', 'legs_support')), false);
  assert.equal(calls.filter(([method]) => method === 'turn').length, 0, 'no save happened');

  // 3. "확인 끝": every box that was neither ticked nor answered becomes "does not apply", with the sentence that says the user confirmed it.
  const before = a.drafts.saved;
  press(a.flow, a.button('confirm'));
  assert.equal(a.drafts.saved, before + 1);
  const answers = a.intake.formAnswers(1).filter(x => x.target !== 'manual.COMMON.neck_base');
  assert.equal(answers.length, 18);
  assert.deepEqual(answers.filter(x => x.value === 'YES').map(x => x.target), ['manual.COMMON.trunk_side_bent'], 'the ticked one stays yes');
  assert.equal(answers.find(x => x.target === 'manual.COMMON.trunk_side_bent').quote, TICK);
  assert.equal(answers.filter(x => x.quote === CONFIRM).length, 17);
  assert.equal(answers.find(x => x.target === 'manual.COMMON.legs_support').value, 'BILATERAL_STABLE');
  assert.equal(answers.find(x => x.target === 'manual.RIGHT.shoulder_raised').value, 'NO');
  assert.match(a.note.textContent, /17개 항목을 채웠어요\. 저장하면 반영돼요/);
  assert.equal(a.statuses[0].textContent, '모든 항목을 확인했어요. 저장하면 반영돼요.');
  assert.equal(a.button('confirm').disabled, true, 'nothing left to confirm');
  assert.equal(a.boxes.filter(b => b.checked).length, 1, 'only the ticked box shows a tick');
  assert.equal(a.intake.formValue(angles()[0]), undefined, 'the angles the photo could not read are never filled by the checklist');
  // A form drawn again keeps the ticks and the switched-off button.
  const again = a.intake.dialog(false), againBoxes = [...again.matchAll(/<input type="checkbox"[^>]*>/g)].map(m => parseTag(m[0]));
  assert.deepEqual(againBoxes.filter(b => b.checked).map(b => b.dataset.intakeFlag), [by('COMMON', 'trunk_side_bent')]);
  assert.equal(parseTag(again.match(/<button[^>]*data-fill-kind="confirm"[^>]*>/)[0]).disabled, true);
  a.flow.fillIntakeForm({kind: 'confirm', condition: 'photo:2'});
  assert.match(a.note.textContent, /체크하지 않은 항목이 없어서 채울 칸이 없어요/, 'a second press says why nothing happened');
  // 4. Unticking after the confirmation leaves a blank to confirm again; ticking a confirmed "no" makes it a yes.
  tick(a.flow, by('COMMON', 'trunk_side_bent'), false);
  assert.equal(a.button('confirm').disabled, false, 'the blank can be confirmed again');
  tick(a.flow, by('COMMON', 'seated'), true);
  assert.equal(a.intake.formValue(all.find(f => f.identity === by('COMMON', 'seated'))), 'YES');
  assert.equal(quoteOf(a.intake, by('COMMON', 'seated')), TICK);
  // 5. Saving sends every answer with its quote and leaves no draft key behind; the checklist is a view over the same boxes.
  const kept = new Map([...a.intake.formValues]);
  await a.flow.saveIntakeForm();
  const sent = calls.filter(([method]) => method === 'turn').at(-1)[1].answers;
  assert.equal(sent.find(x => x.target === 'manual.COMMON.seated').quote, TICK);
  assert.equal(sent.find(x => x.target === 'manual.COMMON.shock_force').quote, CONFIRM);
  assert.equal(sent.length, 17, 'the unticked-again box was not sent');
  assert.ok(sent.every(x => !String(x.target).startsWith('quote:')));
  assert.equal(a.intake.formValues.size, 0);
  a.intake.formValues = kept;
  assert.equal(quoteOf(a.intake, by('COMMON', 'shock_force')), CONFIRM, 'a restored draft still knows how each value was chosen');

  // 6. A photo estimate or a conflict is the user's own decision: such a box is an ordinary select below, and the confirmation never fills it.
  const seated = all.find(f => f.identity === by('COMMON', 'seated')), shock = all.find(f => f.identity === by('COMMON', 'shock_force'));
  const saved = [{identity: seated.identity, target: seated.target, condition: 'photo:2', state: 'ESTIMATED', source: 'POSE', value: 'YES'},
    {identity: shock.identity, target: shock.target, condition: 'photo:2', state: 'CONFLICT', source: 'AI', value: 'YES', conflict: {value: 'NO'}},
    {identity: by('COMMON', 'neck_twisted'), target: 'manual.COMMON.neck_twisted', condition: 'photo:2', state: 'KNOWN', source: 'USER', value: 'NO'},
    {identity: by('COMMON', 'static_over_1min'), target: 'manual.COMMON.static_over_1min', condition: 'photo:2', state: 'UNKNOWN', source: 'USER', value: null}];
  const pending = all.filter(f => ![by('COMMON', 'neck_twisted'), by('COMMON', 'static_over_1min')].includes(f.identity));
  const b = await open([...pending, ...angles()], saved);
  assert.equal(b.boxes.length, 18 - 4, 'answered, estimated and conflicting boxes are not ticks');
  assert.match(b.html, new RegExp(`data-intake-form="${seated.identity}"`), 'the estimate stays an ordinary select');
  assert.match(b.html, new RegExp(`data-intake-form="${shock.identity}"`));
  assert.match(b.html, /사진 추정: 예 · 직접 확인해 주세요\./);
  assert.match(b.html, /기존 설명과 다른 값이 있어 확인이 필요해요\./);
  assert.equal(b.statuses[0].textContent.startsWith('체크하지 않은 14개'), true);
  press(b.flow, b.button('confirm'));
  assert.equal(b.intake.formValue(seated), undefined, 'the estimate is not replaced by "no"');
  assert.equal(b.intake.formValue(shock), undefined, 'the conflict is not decided for the user');
  assert.equal(b.intake.formAnswers(1).filter(x => x.quote === CONFIRM).length, 14);
  edit(b.flow, seated.identity, 'NO');
  assert.equal(b.intake.formValue(seated), 'NO', 'the user can still decide it by hand');

  // 7. Each photo has its own list; a press only touches its own photo.
  const c = await open([...all, ...flags('photo:3'), ...angles()], measured);
  assert.equal((c.html.match(/<section class="intake-checklist"/g) || []).length, 2);
  press(c.flow, c.button('confirm', {fillCondition: 'photo:3'}));
  assert.equal(c.intake.formAnswers(1).length, 18);
  assert.ok(c.intake.formAnswers(1).every(x => x.condition === 'photo:3'));

  // 8. Copy to the other side works on ticks too, and the boxes follow it.
  const d = await open([...all, ...angles()], measured);
  assert.equal(d.button('mirror', {fillSide: 'LEFT'}).disabled, true, 'nothing on the right to copy yet');
  tick(d.flow, by('RIGHT', 'shoulder_raised'), true);
  assert.equal(d.button('mirror', {fillSide: 'LEFT'}).disabled, false, 'the button turns on when there is something to copy');
  press(d.flow, d.button('mirror', {fillSide: 'LEFT'}));
  assert.equal(d.box(by('LEFT', 'shoulder_raised')).checked, true, 'the left box shows the copied tick');
  assert.equal(quoteOf(d.intake, by('LEFT', 'shoulder_raised')), '왼쪽은 오른쪽과 같다고 직접 선택 (선택한 때의 값)');
  assert.equal(d.box(by('LEFT', 'arm_abducted_or_rotated')).checked, false, 'what was not ticked on the right is not copied as a tick');

  // 9. A front-photo suggestion sits beside its box; one press ticks it and says where the value came from.
  const withHint = flags().map(f => f.identity === by('COMMON', 'trunk_side_bent') ? {...f, suggestion: {value: 'YES', estimated: false, quote: '12.3°', photo_label: '정면·후면 사진', reading: '몸통이 옆으로 기울어 보여요'}} : f);
  const e = await open([...withHint, ...angles()], measured);
  assert.match(e.html, /intake-check-item">[^]*?정면·후면 사진에서 몸통이 옆으로 기울어 보여요 \(12\.3°\)\. 맞나요\? <button[^>]*>맞아요, 체크<\/button>/);
  press(e.flow, e.button('suggest', {fillIdentity: by('COMMON', 'trunk_side_bent')}));
  assert.equal(e.box(by('COMMON', 'trunk_side_bent')).checked, true);
  assert.equal(quoteOf(e.intake, by('COMMON', 'trunk_side_bent')), '정면·후면 사진에서 읽은 값(12.3°)을 확인해 직접 선택');
  assert.equal(e.lines[0].hidden, true, 'the line goes away once the box is answered');

  // 10. While the form is busy nothing can be ticked or pressed.
  const f = await open([...all, ...angles()], measured, '저장하고 있어요');
  assert.ok(f.boxes.every(b => b.disabled) && f.buttons.every(b => b.disabled));
  console.log('PASS the posture checklist ticks what applies, confirms the rest only when asked, leaves estimates, conflicts and unread angles to the user, and says how each value was chosen');
})().catch(error => { console.error(error); process.exitCode = 1; });
