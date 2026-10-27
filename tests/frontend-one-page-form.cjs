/* Everything the user is asked sits on ONE page: no wizard, no stepper, one save button, sections in a fixed order that open while they hold something to answer,
   a photo question that comes first and reveals the checklist in place, a sentence box that is only an option, and selectable presets for the number boxes. */
const assert = require('node:assert/strict');
const path = require('node:path');
const {pathToFileURL} = require('node:url');
const url = name => pathToFileURL(path.join(__dirname, '../frontend', name)).href;

(async () => {
  const {AdaptiveIntake} = await import(url('intake/client.js'));
  const YES_NO = [{value: 'YES', label: '예'}, {value: 'NO', label: '아니오'}];
  const contract = {policy: {quick_review_interval: 5, default_condition: 'default', text_limit: 2400, form_prompt_limit: 3, optional_photo_destinations: ['context', 'view', 'manual', 'load', 'load_kg', 'load_link']},
    methods: {session: 'session', turn: 'turn'}, fields: []};
  const row = (target, destination, extra = {}) => ({target, identity: `${target}@default`, condition: 'default', kind: 'choice', label: target, text: target, group: '작업 조건', choices: YES_NO, destination: {type: destination}, ...extra});
  const num = (target, unit, extra = {}) => row(target, 'condition', {kind: 'number', unit, choices: [], label: `${target} 값`, ...extra});
  const work = n => row(`work_type.${n}`, 'work_type', {label: `${n} 작업`, group: '작업 특징'});
  const WORK = ['keyboard', 'lift', 'repeat'].map(work);
  const CONDITIONS = [num('annual_work_days', '일', {maximum: 366}), num('daily_work_min', '분', {maximum: 1440}), num('card.keyboard.C1_KEYBOARD_FOCUSED', '분/일', {maximum: 1440}),
    num('card.lift.load_mass_kg', 'kg'), num('card.lift.lift_count_day', '회/일'), num('card.lift.lift_rate_min', '회/분'), num('planned_duration_months', '개월', {maximum: 1200}),
    num('card.impact.impact_rate_hour', '회/시간'), row('one_off', 'condition', {label: '일회성 작업인가요?'})];
  const PHOTO = [row('load', 'load', {label: '손에 든 물건이 있나요?', group: '물건과 힘', choices: [{value: 'UNLOADED', label: '없음'}, {value: 'MEASURED', label: '있음'}]}),
    row('view_LEFT', 'view', {label: '왼쪽 사진 방향', group: '사진 확인', choices: [{value: 'SCREEN_LEFT', label: '화면 왼쪽'}, {value: 'SCREEN_RIGHT', label: '화면 오른쪽'}]}),
    row('context', 'context', {label: '올린 사진이 모두 한 사람의 전신이 나온 평소 작업 모습인가요?', group: '사진 확인'}),
    row('load_link', 'load_link', {label: '사진 속 물건도 같은 무게인가요?', group: '사진 속 물건 확인'})];
  const ITEMS = [['몸통·목', 'trunk_twisted', '몸통을 비틀어 작업함'], ['몸통·목', 'neck_twisted', '목을 비틀어 작업함'], ['어깨·팔·손목', 'shoulder_raised', '어깨를 으쓱 들어 올림', 'ARM'], ['다리', 'seated', '앉아서 작업함']];
  const by = (scope, field, condition = 'photo:2') => `manual.${scope}.${field}@${condition}`;
  const flags = () => ITEMS.flatMap(([group, field, label, kind], order) => (kind === 'ARM' ? ['LEFT', 'RIGHT'] : ['COMMON']).map(scope => ({target: `manual.${scope}.${field}`, identity: by(scope, field), condition: 'photo:2', kind: 'choice',
    label: scope === 'COMMON' ? label : `${scope === 'LEFT' ? '왼쪽' : '오른쪽'} ${label}`, text: label, group: '사진 자세 보완', photo_label: '오른쪽에서 찍은 사진', choices: YES_NO, destination: {type: 'manual', scope, field}, reason: '결과 계산에 필요한 정보가 아직 없어요.',
    checklist: {group, order, label, yes: 'YES', no: 'NO'}})));
  const angles = () => [['LEFT', 'wrist_base'], ['RIGHT', 'wrist_base'], ['COMMON', 'neck_base']].map(([scope, field]) => ({target: `manual.${scope}.${field}`, identity: by(scope, field), condition: 'photo:2', kind: 'choice', label: `${scope} ${field}`, text: field,
    group: '사진 자세 보완', photo_label: '오른쪽에서 찍은 사진', choices: [{value: 1, label: '낮음'}, {value: 2, label: '높음'}], destination: {type: 'manual', scope, field}}));
  const fact = (identity, state, source, value) => ({identity, target: identity.split('@')[0], condition: identity.split('@')[1], state, source, value});
  const open = async (rows, saved = [], {busy = false, text = ''} = {}) => {
    const state = {contract, task: {task_id: 1, input_revision: 1}, facts: saved, messages: [], questions: [], form_fields: rows, remaining_count: rows.length, complete: false,
      progress: {completed_count: 0, total_count: rows.length, remaining_count: rows.length, percent: 0, dynamic: true}};
    const intake = new AdaptiveIntake({changed() {}, notify() {}, api: async method => method === 'intake_contract' ? contract : structuredClone(state)});
    await intake.open(1);
    intake.dialogOpen = true; intake.text = text;
    return {intake, html: intake.dialog(busy)};
  };
  const sections = html => [...html.matchAll(/<details class="intake-form-section"[^>]*data-intake-section="([a-z]+)"[^>]*>/g)].map(m => ({name: m[1], tag: m[0], at: m.index}));
  const part = (html, name) => { const all = sections(html), i = all.findIndex(s => s.name === name); return i < 0 ? '' : html.slice(all[i].at, html.indexOf('</details>', all[i].at)); };
  const identities = html => [...html.matchAll(/data-intake-form="([^"]*)"/g)].map(m => m[1]);
  const visible = html => html.replace(/<[^>]+>/g, ' ').replace(/\s+/g, ' ');

  // 1. One page: no wizard, no stepper, no progress bar, no "back"; one save button; the title says it is the single page.
  const all = await open([...WORK, ...CONDITIONS, ...PHOTO]);
  assert.match(all.html, /<h2 id="intake-dialog-title">작업 정보를 한 번에 확인해 주세요<\/h2>/);
  for (const gone of [/intake-form-steps/, /intake-form-progress/, /입력 단계/, /intake-form-back/, />이전</, /저장하고 작업 조건 확인/, /1\. 작업 특징/, /2\. 작업 조건/, /role="progressbar"/])
    assert.doesNotMatch(all.html, gone, `the wizard is gone: ${gone}`);
  assert.equal([...all.html.matchAll(/data-quick="intake-form-next"/g)].length, 1, 'exactly one save button');
  assert.match(all.html, /<button type="button" class="primary" data-quick="intake-form-next"[^>]*>저장하고 결과 보기 →<\/button>/);
  assert.match(all.html, /<button type="button" data-quick="intake-close"[^>]*>나중에 확인<\/button>/);
  assert.match(all.html, /<p class="intake-fill-note" data-intake-fill-note role="status" hidden><\/p>/, 'the in-dialog note area stays');
  // the page is the same whatever stage the (old) client still says
  const staged = await open([...WORK, ...CONDITIONS, ...PHOTO]); staged.intake.formStage = 1;
  assert.equal(staged.intake.dialog(false), all.html, 'the stage no longer changes the page');

  // 2. Sections come in a fixed order and are open while they hold something to answer; the one count line replaces the stepper.
  const full = await open([...WORK, ...CONDITIONS, ...PHOTO, ...flags(), ...angles()]);
  const found = sections(full.html);
  assert.deepEqual(found.map(s => s.name), ['work', 'conditions', 'photo', 'checklist', 'angles']);
  assert.ok(found.every(s => / open(?=[\s>])/.test(s.tag)), 'every section that has something to answer is open');
  assert.ok(['photo', 'checklist', 'angles'].every(name => /data-intake-photo-optional/.test(found.find(s => s.name === name).tag)), 'the photo sections keep the marker the tests and the test harness use');
  const remaining = full.html.match(/<p class="intake-remaining" data-intake-remaining>([^<]*)<\/p>/);
  // 3 work + 9 conditions + 4 photo + 1 checklist (one decision for the whole list) + 3 angle rows
  assert.equal(remaining[1], '남은 확인 20개 · 모르면 비워 두세요(미확인으로 남아요)');
  assert.match(full.html, /아직 확인하지 못한 항목만 보여 드려요\./);
  full.intake.setFormValue('work_type.lift@default', 'YES', '직접 선택');
  assert.match(full.intake.dialog(false), /남은 확인 19개 · /, 'a box the user answered is no longer counted');
  full.intake.setFormValue(by('COMMON', 'trunk_twisted'), 'YES', '직접 체크');
  assert.match(full.intake.dialog(false), /남은 확인 19개 · /, 'one ticked box does not finish the checklist: it stays one decision');
  full.intake.formValues.clear();

  // 3. The work section holds only the work features and the single "no other work" button.
  const workPart = part(full.html, 'work');
  assert.deepEqual(identities(workPart), WORK.map(f => f.identity));
  assert.equal([...full.html.matchAll(/data-quick="intake-no-other-work"/g)].length, 1);
  assert.ok(workPart.includes('data-quick="intake-no-other-work"'), 'the button sits inside the work section');
  assert.match(workPart, /선택하지 않은 나머지 작업은 모두 안 해요/);
  const conditionsPart = part(full.html, 'conditions');
  assert.deepEqual(identities(conditionsPart), CONDITIONS.map(f => f.identity), 'the conditions are the rows stage 2 used to hold, without the photo ones');

  // 4. The photo section opens first with the situation question; gates are marked for the in-place refresh.
  const photoPart = part(full.html, 'photo');
  assert.equal(identities(photoPart)[0], 'context@default', 'the photo situation is asked first');
  assert.deepEqual(identities(photoPart).sort(), PHOTO.map(f => f.identity).sort());
  const gateTag = identity => (full.html.match(new RegExp(`<(?:select|input)[^>]*data-intake-form="${identity.replace(/[.]/g, '\\.')}"[^>]*>`)) || [''])[0];
  for (const f of [...WORK, PHOTO[2]]) assert.match(gateTag(f.identity), /data-intake-gate="1"/, `${f.identity} is a gate`);
  for (const f of [...CONDITIONS, PHOTO[0], PHOTO[1], PHOTO[3]]) assert.doesNotMatch(gateTag(f.identity), /data-intake-gate/, `${f.identity} is not a gate`);
  assert.match(photoPart, /intake-section-lead/);
  assert.doesNotMatch(photoPart, /intake-checklist/, 'the checklist is not in the photo question section');

  // 5. The checklist and the angle rows are their own sections, with the panel and its buttons.
  const checklistPart = part(full.html, 'checklist'), anglesPart = part(full.html, 'angles');
  assert.equal([...checklistPart.matchAll(/<input type="checkbox"/g)].length, 5, 'the whole checklist is on the page');
  assert.match(checklistPart, /data-fill-kind="confirm"/);
  assert.match(checklistPart, /<h3>오른쪽에서 찍은 사진<\/h3>/);
  assert.deepEqual(identities(anglesPart), angles().map(f => f.identity));
  assert.match(anglesPart, /<h4 class="intake-angle-title">사진이 읽지 못해 직접 골라야 하는 항목<\/h4>/);
  assert.ok(full.html.indexOf('data-intake-section="photo"') < full.html.indexOf('data-intake-section="checklist"') && full.html.indexOf('data-intake-section="checklist"') < full.html.indexOf('data-intake-section="angles"'));

  // 6. Before the photo question is answered there is no checklist yet: only the question and a line that says what comes after it.
  const early = await open([...WORK, ...CONDITIONS, ...PHOTO]);
  assert.deepEqual(sections(early.html).map(s => s.name), ['work', 'conditions', 'photo']);
  assert.match(part(early.html, 'photo'), /고르면 바로 아래에 자세 항목이 나와요/);
  const answered = await open([...WORK, ...CONDITIONS, ...PHOTO, ...flags()], [fact('context@default', 'KNOWN', 'USER', 'YES')]);
  assert.doesNotMatch(part(answered.html, 'photo'), /고르면 바로 아래에 자세 항목이 나와요/, 'the line is gone once the question is answered');
  assert.doesNotMatch(identities(part(answered.html, 'photo')).join(), /context@default/, 'an answered question is not asked again');

  // 7. A section with nothing left to answer is not on the page; the answered rows wait in the closed summary.
  const done = await open([...WORK, ...CONDITIONS], WORK.map(f => fact(f.identity, 'KNOWN', 'USER', 'NO')));
  assert.deepEqual(sections(done.html).map(s => s.name), ['conditions'], 'no empty work section');
  assert.match(done.html, /<details class="intake-form-section" data-intake-confirmed><summary>이미 확인한 정보 3개 · 수정하기<\/summary>/);
  const nothing = await open([...WORK], WORK.map(f => fact(f.identity, 'KNOWN', 'AI', 'NO')));
  assert.deepEqual(sections(nothing.html), []);
  assert.match(nothing.html, /남은 확인이 없어요 · 저장하고 결과를 확인해 주세요/);
  assert.match(nothing.html, /추가로 입력할 항목이 없어요\. 저장하고 결과를 확인해 주세요\./);
  assert.doesNotMatch(nothing.html, /다음 단계/);

  // 8. The sentence box is an option, not a question: closed, titled "문장으로 더 적기", still working; open only when a draft is waiting.
  const natural = all.html.match(/<details class="intake-form-section" data-intake-natural-answer([^>]*)><summary>([^<]*)<\/summary>/);
  assert.ok(natural, 'the sentence box is a details element');
  assert.doesNotMatch(natural[1], /\bopen\b/, 'closed by default');
  assert.equal(natural[2], '문장으로 더 적기');
  assert.doesNotMatch(all.html, /설명이 다르거나 더할 내용이 있나요/, 'it is not a headline question');
  assert.doesNotMatch(all.html, /<h3>[^<]*(?:더할|아래 작업도)/);
  assert.match(all.html, /<textarea data-intake-reply maxlength="2400"/);
  assert.match(all.html, /<button type="button" data-quick="adaptive-next" disabled>답변 정리<\/button>/);
  assert.ok(all.html.indexOf('data-intake-form=') < all.html.indexOf('data-intake-natural-answer'), 'the choices come before the optional sentence box');
  const drafted = await open([...WORK], [], {text: '허리를 자주 숙여요 <초안>'});
  assert.match(drafted.html, /data-intake-natural-answer open>/, 'a waiting draft is never hidden');
  assert.match(drafted.html, /허리를 자주 숙여요 &lt;초안&gt;/);
  assert.match(drafted.html, /<button type="button" data-quick="adaptive-next" >답변 정리<\/button>/);

  // 9. Number boxes get selectable presets: one datalist per kind of field, only the values the box allows, nothing pre-filled.
  const list = identity => (gateTag(identity).match(/ list="([^"]*)"/) || [])[1];
  const options = id => { const m = full.html.match(new RegExp(`<datalist id="${id}">([\\s\\S]*?)</datalist>`)); return m ? [...m[1].matchAll(/<option value="(\d+)">/g)].map(x => Number(x[1])) : null; };
  const expect = {'annual_work_days@default': [100, 150, 200, 220, 250, 300, 365], 'daily_work_min@default': [30, 60, 120, 240, 360, 480], 'card.keyboard.C1_KEYBOARD_FOCUSED@default': [30, 60, 120, 240, 360, 480],
    'card.lift.load_mass_kg@default': [1, 5, 10, 15, 20, 25], 'card.lift.lift_count_day@default': [10, 25, 50, 100, 200, 500], 'card.lift.lift_rate_min@default': [1, 2, 3, 5, 10], 'planned_duration_months@default': [1, 3, 6, 12, 24]};
  for (const [identity, values] of Object.entries(expect)) { assert.ok(list(identity), `${identity} has a preset list`); assert.deepEqual(options(list(identity)), values, identity); }
  assert.equal(list('card.impact.impact_rate_hour@default'), undefined, 'a field the presets do not know gets none');
  assert.equal(list('one_off@default'), undefined);
  assert.equal(list('daily_work_min@default'), list('card.keyboard.C1_KEYBOARD_FOCUSED@default'), 'the same kind of field shares one list');
  assert.match(gateTag('annual_work_days@default'), /value="" placeholder="미확인"/, 'a preset is only a suggestion; the box is not pre-filled');
  assert.match(gateTag('annual_work_days@default'), /type="number" min="0" step="any" max="366"/, 'the allowed range stays');
  const capped = await open([num('x', '분', {maximum: 100})]);
  const cappedList = capped.html.match(/<input[^>]* list="([^"]*)"/)[1];
  assert.deepEqual([...capped.html.match(new RegExp(`<datalist id="${cappedList}">([\\s\\S]*?)</datalist>`))[1].matchAll(/value="(\d+)"/g)].map(x => Number(x[1])), [30, 60], 'presets above the allowed maximum are not offered');
  assert.notEqual(cappedList, list('daily_work_min@default'), 'a capped list is its own list');
  assert.equal([...full.html.matchAll(/<datalist id="/g)].length, new Set(Object.keys(expect).map(list)).size, 'each list is written once');

  // 10. Waiting disables everything that sends, including the gate selects and the single save button.
  const busy = await open([...WORK, ...PHOTO], [], {busy: '저장하고 있어요'});
  assert.match(busy.html, /<select data-intake-form="work_type\.lift@default" data-intake-gate="1" disabled>/);
  assert.match(busy.html, /<button type="button" class="primary" data-quick="intake-form-next" disabled>/);
  assert.match(busy.html, /data-quick="intake-no-other-work" disabled/);
  assert.match(busy.html, /aria-busy="true"/);

  // 11. Escaping and plain language.
  const hostile = await open([row('work_type.x', 'work_type', {label: '<img src=x onerror=alert(1)>', group: '<b>'})]);
  assert.doesNotMatch(hostile.html, /<img src=x/);
  assert.match(hostile.html, /&lt;img src=x onerror=alert\(1\)&gt;/);
  assert.doesNotMatch(visible(full.html), /undefined|NaN|\[object/);

  console.log('PASS one page: no wizard or stepper, one save button, ordered sections that open while they hold something, photo question first with gate markers, closed sentence box, selectable presets, busy lock and escaping');
})().catch(error => { console.error(error); process.exitCode = 1; });
