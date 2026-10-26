/* The posture checklist panel keeps its promises: each row says why it is asked, "확인 끝" never decides a row that still shows a photo reading,
   a copy and the confirmation give the same result in either order and never overwrite the user's own choice, and the notes never claim what is not true. */
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
  const MIRROR = '왼쪽은 오른쪽과 같다고 직접 선택 (선택한 때의 값)';
  const GENERIC = '결과 계산에 필요한 정보가 아직 없어요.';
  const ITEMS = [['몸통·목', 'trunk_twisted', '몸통을 비틀어 작업함'], ['몸통·목', 'trunk_side_bent', '몸통을 옆으로 기울여 작업함'], ['몸통·목', 'neck_twisted', '목을 비틀어 작업함'], ['몸통·목', 'neck_side_bent', '목을 옆으로 기울여 작업함'],
    ['어깨·팔·손목', 'shoulder_raised', '어깨를 으쓱 들어 올림', 'ARM'], ['어깨·팔·손목', 'arm_abducted_or_rotated', '팔을 옆으로 벌리거나 돌림', 'ARM'], ['어깨·팔·손목', 'arm_supported_or_gravity_assisted', '팔을 받치거나 기대어 작업함', 'ARM'],
    ['어깨·팔·손목', 'wrist_deviated_or_twisted', '손목을 비틀거나 옆으로 꺾음(앞뒤 굽힘과 별도)', 'ARM'], ['다리', 'legs_support', '한 발로 서거나 발 받침이 불안정함', 'LEGS'], ['다리', 'seated', '앉아서 작업함'],
    ['작업 중 움직임과 힘', 'shock_force', '갑자기 큰 힘이나 충격이 가해짐'], ['작업 중 움직임과 힘', 'static_over_1min', '같은 자세를 1분 넘게 유지함'],
    ['작업 중 움직임과 힘', 'small_repeat_over_4min', '좁은 범위 동작을 1분에 4번 넘게 반복함'], ['작업 중 움직임과 힘', 'rapid_change_or_unstable', '자세가 크게 바뀌거나 불안정함']];
  const by = (scope, field, condition = 'photo:2') => `manual.${scope}.${field}@${condition}`;
  const flags = (patch = {}, condition = 'photo:2') => ITEMS.flatMap(([group, field, label, kind], order) => (kind === 'ARM' ? ['LEFT', 'RIGHT'] : ['COMMON']).map(scope => {
    const row = {target: `manual.${scope}.${field}`, identity: by(scope, field, condition), condition, kind: 'choice', label: scope === 'COMMON' ? label : `${scope === 'LEFT' ? '왼쪽' : '오른쪽'} ${label}`, text: label,
      group: '사진 자세 보완', photo_label: '오른쪽에서 찍은 사진', choices: kind === 'LEGS' ? LEGS : YES_NO, destination: {type: 'manual', scope, field}, reason: GENERIC,
      checklist: {group, order, label, yes: kind === 'LEGS' ? 'UNILATERAL_OR_UNSTABLE' : 'YES', no: kind === 'LEGS' ? 'BILATERAL_STABLE' : 'NO'}};
    return {...row, ...(patch[row.identity] || {})};
  }));
  const LEVELS = [{value: 1, label: '낮음'}, {value: 2, label: '높음'}];
  const angle = (scope, field, extra = {}, condition = 'photo:2') => ({target: `manual.${scope}.${field}`, identity: by(scope, field, condition), condition, kind: 'choice', label: `${scope} ${field}`, text: field,
    group: '사진 자세 보완', photo_label: '오른쪽에서 찍은 사진', choices: LEVELS, destination: {type: 'manual', scope, field}, ...extra});
  const angles = () => [angle('LEFT', 'wrist_base'), angle('RIGHT', 'wrist_base'), angle('COMMON', 'neck_base')];
  const fact = (identity, state, source, value, extra = {}) => ({identity, target: identity.split('@')[0], condition: identity.split('@')[1], state, source, value, ...extra});
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
    const controls = rows.map(f => ({dataset: {intakeForm: f.identity}, value: ''}));
    const buttons = [...html.matchAll(/<button[^>]*data-quick="intake-fill"[^>]*>/g)].map(m => parseTag(m[0]));
    const lines = [...html.matchAll(/<small class="intake-suggestion"[^>]*>/g)].map(m => parseTag(m[0]));
    const boxes = [...html.matchAll(/<input type="checkbox"[^>]*>/g)].map(m => parseTag(m[0]));
    const statuses = [...html.matchAll(/<small data-checklist-status="([^"]*)">([^<]*)<\/small>/g)].map(m => ({dataset: {checklistStatus: m[1]}, textContent: m[2]}));
    const hints = [...html.matchAll(/(<small class="intake-fill-hint"[^>]*>)([^<]*)<\/small>/g)].map(m => ({...parseTag(m[1]), textContent: m[2]}));
    const note = {...parseTag(html.match(/<p class="intake-fill-note"[^>]*>/)[0]), textContent: ''};
    const flow = Object.create(QuickFlow.prototype), drafts = {saved: 0};
    const pick = {'[data-intake-form]': controls, '[data-quick="intake-fill"]': buttons, '[data-suggestion-for]': lines, '[data-intake-flag]': boxes, '[data-checklist-status]': statuses, '[data-fill-hint-for]': hints};
    const host = {querySelectorAll: selector => pick[selector] || [], querySelector: selector => selector === '[data-intake-fill-note]' ? note : null};
    Object.assign(flow, {intake, host, keepDraft() { drafts.saved++; }, async run(label, action) { await action(); }, async finish() { drafts.finished = true; }});
    const button = (kind, extra = {}) => buttons.find(b => b.dataset.fillKind === kind && Object.entries(extra).every(([name, value]) => b.dataset[name] === value));
    const box = identity => boxes.find(b => b.dataset.intakeFlag === identity);
    const hint = side => hints.find(h => h.dataset.fillHintFor === side);
    return {intake, flow, html, buttons, boxes, lines, statuses, hints, note, drafts, button, box, hint, rows};
  };
  const press = (flow, button) => flow.click({target: {closest: () => button}});
  const tick = (flow, identity, checked = true) => flow.input({target: {dataset: {intakeFlag: identity}, checked}});
  const edit = (flow, identity, value) => flow.input({target: {dataset: {intakeForm: identity}, value, setCustomValidity() {}, reportValidity() {}}});
  const answersOf = intake => Object.fromEntries(intake.formAnswers(1).map(a => [a.target + '@' + a.condition, `${a.value} | ${a.quote || 'plain'}`]));
  const text = html => html.replace(/<[^>]+>/g, ' ').replace(/\s+/g, ' ');

  // 1. [#2, #11] Every row that carries a reason of its own says it, next to the box and linked to it; the generic sentence is not repeated 18 times.
  const reasonRows = flags({
    [by('COMMON', 'trunk_twisted')]: {reask: true, photo_measurement_reason: true, reason: '사진 또는 측정 설정이 바뀌어 이전 확인을 쓸 수 없어요. 다시 확인해 주세요.'},
    [by('LEFT', 'arm_abducted_or_rotated')]: {photo_measurement_reason: true, reason: '이 사진의 작은 각도만으로 비틀림이나 회전이 없다고 확인할 수는 없어요.'},
    [by('LEFT', 'shoulder_raised')]: {photo_measurement_reason: true, reason: '어깨 높이는 이 사진에서 가려져 있어요.'},
    [by('RIGHT', 'shoulder_raised')]: {photo_measurement_reason: true, reason: '어깨 높이는 이 사진에서 가려져 있어요.'},
    [by('COMMON', 'seated')]: {photo_unused: true, photo_measurement_reason: true, reason: '사진 측정값은 쓰지 않기로 해서 직접 확인해 주세요.'}});
  const r = await open([...reasonRows, ...angles()]);
  const reasons = [...r.html.matchAll(/<small class="intake-measurement-reason" id="([^"]*)">([^<]*)<\/small>/g)].map(m => ({id: m[1], text: m[2]}));
  assert.deepEqual(reasons.map(x => x.text), ['사진 또는 측정 설정이 바뀌어 이전 확인을 쓸 수 없어요. 다시 확인해 주세요.', '어깨 높이는 이 사진에서 가려져 있어요.', '왼쪽: 이 사진의 작은 각도만으로 비틀림이나 회전이 없다고 확인할 수는 없어요.', '사진 측정값은 쓰지 않기로 해서 직접 확인해 주세요.'],
    'one sentence per distinct reason (a shared one once, a one-sided one with its side), in catalogue order');
  assert.ok(!r.html.includes(`class="intake-check-item"><label class="intake-check"><input type="checkbox" data-intake-flag="${by('COMMON', 'neck_twisted')}"`) || !text(r.html).includes(GENERIC), 'the generic "needed for the result" sentence is not shown on the 18 boxes');
  assert.doesNotMatch(r.html.slice(r.html.indexOf('intake-checklist'), r.html.indexOf('</section>', r.html.indexOf('intake-checklist'))), new RegExp(GENERIC));
  assert.equal(new Set(reasons.map(x => x.id)).size, reasons.length, 'every reason has its own id');
  const describedBy = identity => (r.html.match(new RegExp(`<input type="checkbox" data-intake-flag="${identity}"[^>]*?aria-describedby="([^"]*)"`)) || [])[1];
  assert.equal(describedBy(by('COMMON', 'trunk_twisted')), reasons[0].id, 'the box points at its reason');
  assert.equal(describedBy(by('LEFT', 'arm_abducted_or_rotated')), reasons[2].id);
  assert.equal(describedBy(by('RIGHT', 'arm_abducted_or_rotated')), undefined, 'the other side has no reason of its own');
  assert.equal(describedBy(by('LEFT', 'shoulder_raised')), reasons[1].id);
  assert.equal(describedBy(by('RIGHT', 'shoulder_raised')), reasons[1].id, 'a shared reason serves both boxes');
  assert.equal(describedBy(by('COMMON', 'seated')), reasons[3].id, 'a refused photo says why the box is asked');
  assert.equal(describedBy(by('COMMON', 'neck_twisted')), undefined);
  // [#11] a side box is named by its item and side; a single box by its own label
  assert.match(r.html, new RegExp(`data-intake-flag="${by('LEFT', 'shoulder_raised')}" aria-label="어깨를 으쓱 들어 올림 · 왼쪽"`));
  assert.match(r.html, new RegExp(`data-intake-flag="${by('RIGHT', 'shoulder_raised')}" aria-label="어깨를 으쓱 들어 올림 · 오른쪽"`));
  assert.doesNotMatch(r.html, new RegExp(`data-intake-flag="${by('COMMON', 'neck_twisted')}" aria-label`), 'a single box is already named by its text');

  // 2. [#3, #4] A box that still shows a photo reading is not decided by "확인 끝"; the line says which side; "아니에요" is the way to say no.
  const reading = (value, quote, extra = {}) => ({suggestion: {value, estimated: false, quote, photo_label: '정면·후면 사진', reading: '팔이 옆으로 벌어져 보여요', ...extra}});
  const sRows = flags({[by('COMMON', 'trunk_side_bent')]: reading('YES', '12.3°', {reading: '몸통이 옆으로 기울어 보여요'}),
    [by('LEFT', 'arm_abducted_or_rotated')]: reading('YES', '35°'), [by('RIGHT', 'arm_abducted_or_rotated')]: reading('YES', '41.0°')});
  const s = await open([...sRows, ...angles()]);
  assert.match(s.html, /<small class="intake-suggestion"[^>]*>왼쪽 · 정면·후면 사진에서 팔이 옆으로 벌어져 보여요 \(35°\)\. 맞나요\?/);
  assert.match(s.html, /<small class="intake-suggestion"[^>]*>오른쪽 · 정면·후면 사진에서 팔이 옆으로 벌어져 보여요 \(41\.0°\)\. 맞나요\?/);
  assert.match(s.html, /<small class="intake-suggestion"[^>]*>정면·후면 사진에서 몸통이 옆으로 기울어 보여요 \(12\.3°\)\. 맞나요\?/, 'a box without a side has no side in its sentence');
  assert.equal(s.buttons.filter(b => b.dataset.fillKind === 'decline').length, 3, 'each reading can be answered no');
  assert.equal(s.statuses[0].textContent, '체크하지 않은 15개는 아직 비어 있어요. 해당 없으면 위 버튼을 눌러 주세요. 사진이 본 3개는 위에서 ‘맞아요, 체크’나 ‘아니에요’를 눌러 주세요.');
  press(s.flow, s.button('confirm'));
  const decided = s.intake.formAnswers(1);
  assert.equal(decided.length, 15, 'the three boxes with a reading stay blank');
  for (const identity of [by('COMMON', 'trunk_side_bent'), by('LEFT', 'arm_abducted_or_rotated'), by('RIGHT', 'arm_abducted_or_rotated')])
    assert.equal(s.intake.formValues.has(identity), false, identity + ' is still the user\'s to decide');
  assert.match(s.note.textContent, /^15개 항목을 채웠어요\. 저장하면 반영돼요\. 다르면 직접 고쳐 주세요\. 사진이 본 3개는 비워 뒀어요\./);
  assert.match(s.statuses[0].textContent, /^사진이 본 3개는 위에서 ‘맞아요, 체크’나 ‘아니에요’를 눌러 주세요\.$/, 'never "all confirmed" while a reading waits');
  assert.equal(s.button('confirm').disabled, true, 'nothing left for the confirmation to fill');
  assert.equal(parseTag(s.intake.dialog(false).match(/<button[^>]*data-fill-kind="confirm"[^>]*>/)[0]).disabled, true, 'and a form drawn again keeps it off while only readings are waiting');
  s.flow.fillIntakeForm({kind: 'confirm', condition: 'photo:2'});
  assert.match(s.note.textContent, /사진이 본 3개는 위에서 ‘맞아요, 체크’나 ‘아니에요’를 눌러 주세요/, 'a second press says what is waiting');
  press(s.flow, s.button('decline', {fillIdentity: by('COMMON', 'trunk_side_bent')}));
  assert.equal(s.intake.formValue(sRows.find(f => f.identity === by('COMMON', 'trunk_side_bent'))), 'NO');
  assert.equal(answersOf(s.intake)[by('COMMON', 'trunk_side_bent')], 'NO | 정면·후면 사진에서 읽은 값(12.3°)은 아니라고 직접 선택');
  assert.equal(s.lines[0].hidden, true, 'the line goes away once answered');
  press(s.flow, s.button('suggest', {fillIdentity: by('LEFT', 'arm_abducted_or_rotated')}));
  assert.equal(s.box(by('LEFT', 'arm_abducted_or_rotated')).checked, true);
  assert.match(s.statuses[0].textContent, /^사진이 본 1개는/);
  tick(s.flow, by('RIGHT', 'arm_abducted_or_rotated'), true);
  assert.equal(s.statuses[0].textContent, '모든 항목을 확인했어요. 저장하면 반영돼요.');
  assert.equal(s.button('decline', {fillIdentity: by('LEFT', 'arm_abducted_or_rotated')}).disabled, true, 'an answered reading cannot be declined by a stray press');

  // 3. [#5] A copy and the confirmation give the same result in either order, and a copy never replaces what the user chose on that side.
  const cRows = [...flags(), ...angles()];
  const scenario = async (order, extra = () => {}) => {
    const c = await open(cRows);
    tick(c.flow, by('RIGHT', 'shoulder_raised'));
    tick(c.flow, by('RIGHT', 'arm_supported_or_gravity_assisted'));
    edit(c.flow, by('RIGHT', 'wrist_base'), '2');
    extra(c);
    for (const step of order) press(c.flow, step === 'copy' ? c.button('mirror', {fillSide: 'LEFT'}) : c.button('confirm'));
    return c;
  };
  const copyFirst = await scenario(['copy', 'confirm']), confirmFirst = await scenario(['confirm', 'copy']);
  assert.deepEqual(answersOf(confirmFirst.intake), answersOf(copyFirst.intake), 'either order ends with the same answers and the same way of choosing each');
  const done = answersOf(confirmFirst.intake);
  assert.equal(done[by('LEFT', 'shoulder_raised')], `YES | ${MIRROR}`, 'the right tick reached the left flag');
  assert.equal(done[by('LEFT', 'arm_supported_or_gravity_assisted')], `YES | ${MIRROR}`);
  assert.equal(done[by('LEFT', 'wrist_base')], `2 | ${MIRROR}`);
  assert.equal(done[by('LEFT', 'arm_abducted_or_rotated')], `NO | ${CONFIRM}`, 'what was not ticked stays "does not apply"');
  assert.equal(done[by('RIGHT', 'shoulder_raised')], `YES | ${TICK}`);
  assert.match(confirmFirst.note.textContent, /^3개 항목을 채웠어요\./, 'the note counts the two flags and the angle, not just the angle');
  assert.equal(confirmFirst.box(by('LEFT', 'shoulder_raised')).checked, true, 'the left box shows the copied tick');
  assert.equal(confirmFirst.box(by('LEFT', 'arm_abducted_or_rotated')).checked, false);
  // what the user ticked or chose on the left is theirs
  const own = await scenario(['confirm', 'copy'], c => { tick(c.flow, by('LEFT', 'arm_supported_or_gravity_assisted')); edit(c.flow, by('LEFT', 'wrist_base'), '1'); });
  assert.equal(answersOf(own.intake)[by('LEFT', 'arm_supported_or_gravity_assisted')], `YES | ${TICK}`, 'a ticked left box keeps its own quote');
  assert.equal(answersOf(own.intake)[by('LEFT', 'wrist_base')], '1 | plain', 'a chosen left value is not replaced');
  assert.match(own.note.textContent, /^1개 항목을 채웠어요\./, 'only the box the user had not decided was copied');
  // a bulk "does not apply" on the other side is not something to copy
  const bulkOnly = await open(cRows);
  press(bulkOnly.flow, bulkOnly.button('confirm'));
  assert.equal(bulkOnly.button('mirror', {fillSide: 'LEFT'}).disabled, true, 'nothing the user chose on the right yet');
  assert.equal(bulkOnly.button('mirror', {fillSide: 'RIGHT'}).disabled, true);
  assert.equal(bulkOnly.intake.fillPlan({kind: 'mirror', side: 'LEFT', condition: 'photo:2'}).length, 0);
  assert.equal(bulkOnly.hint('LEFT').textContent, '오른쪽 값을 먼저 정해 주세요.');

  // 4. [#9] After everything was copied the dimmed buttons say so (in words on the page, not only on hover) and are linked to that text.
  assert.equal(confirmFirst.button('mirror', {fillSide: 'LEFT'}).disabled, true);
  assert.equal(confirmFirst.button('mirror', {fillSide: 'LEFT'}).title, '복사할 값이 더 없어요.');
  assert.equal(confirmFirst.hint('LEFT').textContent, '복사할 값이 더 없어요.');
  assert.equal(confirmFirst.hint('LEFT').hidden, false, 'the reason is visible text');
  assert.equal(confirmFirst.intake.fillHint({kind: 'mirror', side: 'RIGHT', condition: 'photo:2'}), '복사할 값이 더 없어요.', 'the left has values now, but the right already has an answer for each of them');
  const fresh = await open(cRows);
  assert.equal(fresh.hint('LEFT').textContent, '오른쪽 값을 먼저 정해 주세요.', 'before anything is chosen the hint asks for the other side');
  assert.equal(fresh.hint('LEFT').hidden, false);
  const describes = (html, side) => (html.match(new RegExp(`<button[^>]*data-fill-side="${side}"[^>]*aria-describedby="([^"]*)"`)) || [])[1];
  assert.ok(fresh.html.includes(`id="${describes(fresh.html, 'LEFT')}"`), 'the button is linked to an element that exists');
  tick(fresh.flow, by('RIGHT', 'shoulder_raised'));
  assert.equal(fresh.hint('LEFT').hidden, true, 'the hint goes away while a press would fill something');
  assert.equal(fresh.hint('LEFT').textContent, '');
  assert.equal(fresh.button('mirror', {fillSide: 'LEFT'}).title, '');

  // 5. [#10] A "don't know" the user picked is an answer: a copy leaves it; the row's own suggestion can still be answered by its button.
  const unknown = await open([...flags(), ...angles()]);
  edit(unknown.flow, by('RIGHT', 'wrist_base'), '2');
  edit(unknown.flow, by('LEFT', 'wrist_base'), '');
  press(unknown.flow, unknown.button('mirror', {fillSide: 'LEFT'}));
  assert.equal(unknown.intake.formValue(angles()[0]), null, 'the left wrist stays "don\'t know"');
  assert.equal(unknown.intake.formAnswers(1).find(a => a.target === 'manual.LEFT.wrist_base').value, null);
  const withReading = await open([...flags(), angle('COMMON', 'neck_base', reading(2, '9°', {reading: '목이 숙여 보여요'}))]);
  edit(withReading.flow, by('COMMON', 'neck_base'), '');
  press(withReading.flow, withReading.button('suggest', {fillIdentity: by('COMMON', 'neck_base')}));
  assert.equal(withReading.intake.formValue(angle('COMMON', 'neck_base')), 2, 'pressing the reading\'s own button is an answer, even over a "don\'t know"');

  // 6. [#6] A refused photo has nothing "already reflected" and nothing it "could not read".
  const measured = [fact(by('COMMON', 'trunk_base'), 'KNOWN', 'POSE', 3, {photo_active: true}), fact(by('RIGHT', 'upper_arm_base'), 'KNOWN', 'POSE', 2, {photo_active: true})];
  const yes = await open([...flags(), ...angles()], [...measured, fact('context@default', 'KNOWN', 'USER', 'YES')]);
  assert.match(yes.html, /사진이 잰 값 2개는 이미 반영했어요/);
  assert.match(yes.html, /intake-angle-title/);
  const no = await open([...flags(), ...angles()], [...measured, fact('context@default', 'KNOWN', 'USER', 'NO')]);
  assert.doesNotMatch(no.html, /intake-measured-note/, 'the user said the photo is not usable');
  assert.doesNotMatch(no.html, /intake-angle-title/, 'and then no sentence claims what the photo could not read');
  assert.equal(no.intake.measuredCount('photo:2'), 0);
  const unusedRows = [...flags({[by('COMMON', 'seated')]: {photo_unused: true, photo_measurement_reason: true, reason: '사진 측정값은 쓰지 않기로 해서 직접 확인해 주세요.'}}), ...angles()];
  assert.doesNotMatch((await open(unusedRows, measured)).html, /intake-measured-note/, 'a row flagged as unused says the same without a context fact');
  assert.equal((await open([...flags(), ...angles()], [...measured, fact('context@default', 'UNKNOWN', 'USER', null)])).intake.measuredCount('photo:2'), 0, 'a "don\'t know" confirmation does not use the photo either');

  // 7. [#8] "All confirmed" is only said when it is true: a photo estimate that is still blank is counted.
  const seated = flags().find(f => f.identity === by('COMMON', 'seated'));
  const est = await open([...flags(), ...angles()], [fact(seated.identity, 'ESTIMATED', 'POSE', 'YES')]);
  press(est.flow, est.button('confirm'));
  assert.doesNotMatch(est.statuses[0].textContent, /모든 항목을 확인했어요/);
  assert.equal(est.statuses[0].textContent, '사진 추정·충돌 1개는 아래에서 직접 골라 주세요.');
  edit(est.flow, seated.identity, 'NO');
  assert.equal(est.statuses[0].textContent, '모든 항목을 확인했어요. 저장하면 반영돼요.');
  assert.equal(est.intake.checklistUndecided('photo:2'), 0);

  // 8. [#12] Pins for the counting rules: only what the photo measured and is still in use counts, from either engine; answered rows are not "open".
  const counted = [fact(by('COMMON', 'trunk_base'), 'KNOWN', 'POSE', 3, {photo_active: true}), fact(by('LEFT', 'upper_arm_base'), 'KNOWN', 'MOVENET', 2),
    fact(by('RIGHT', 'upper_arm_base'), 'KNOWN', 'POSE', 2, {photo_active: false}), fact(by('RIGHT', 'lower_arm_base'), 'KNOWN', 'POSE', 2, {alias_of: by('LEFT', 'lower_arm_base')}),
    fact(by('LEFT', 'lower_arm_base'), 'ESTIMATED', 'POSE', 2), fact(by('COMMON', 'neck_base'), 'KNOWN', 'USER', 1), fact(by('LEFT', 'wrist_base'), 'KNOWN', 'POSE', 1, {condition: 'photo:3'})];
  const m = await open([...flags(), ...angles()], counted);
  assert.equal(m.intake.measuredCount('photo:2'), 2, 'a POSE and a MOVENET reading count; a replaced photo, an alias, an estimate, an answer and another photo do not');
  const handledRows = flags().slice(0, 3);
  const h = await open(handledRows, [fact(handledRows[0].identity, 'UNKNOWN', 'USER', null), fact(handledRows[1].identity, 'KNOWN', 'USER', 'NO')]);
  assert.equal(h.intake.checklistOpen('photo:2'), 1, 'a row answered "don\'t know" earlier is not open, and neither is a known one');
  assert.equal(h.intake.fillPlan({kind: 'confirm', condition: 'photo:2'}).length, 1);

  // 9. Nothing here saves; while busy nothing can be pressed (the new buttons included).
  assert.equal(calls.filter(([method]) => method === 'turn').length, 0, 'no save happened');
  const busy = await open([...sRows, ...angles()], [], '저장하고 있어요');
  assert.ok(busy.buttons.length >= 4 && busy.buttons.every(b => b.disabled) && busy.boxes.every(b => b.disabled));
  console.log('PASS the checklist panel says why each row is asked, never decides a row that shows a photo reading, copies and confirms in either order, respects "don\'t know", and only claims what is true');
})().catch(error => { console.error(error); process.exitCode = 1; });
