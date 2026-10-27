/* Scope cut (owner, 2026-10-27: "점수 계산에 안 쓰이면 보여주지마. 받지도 마."): the four record groups that never fed a score are not asked, not shown and not sent.
   They are the reason of an occasional survey, the worksite situation, the worker participation and the symptom survey.
   What the Excel header still prints (survey type, previous survey date, investigator, department, process, title, date) stays. */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const {pathToFileURL} = require('node:url');
const frontend = name => path.join(__dirname, '../frontend', name);
const url = name => pathToFileURL(frontend(name)).href;
const source = name => fs.readFileSync(frontend(name), 'utf8');

const REMOVED = ['occasional_reason', 'occasional_cause', 'occasional_cause_source', 'workplace_situation', 'participation', 'symptom_survey'];
const KEPT = ['department', 'investigator', 'previous_survey_date', 'process', 'survey_date', 'survey_type', 'title'];
const ASKING = ['참여', '증상', '작업설비', '작업량', '작업속도', '업무형태', '수시조사 사유', '근로자대표'];

(async () => {
  const {QuickFlow, savedAnswers, LATER_GROUPS} = await import(url('quick-flow.js'));

  // 1. The check before the Excel names only what the calculation lacks. An overview from an older service that still carries survey follow-ups does not show them.
  const panel = (overview, preview = {questions: [{id: 'crit_keyboard'}]}) => Object.assign(Object.create(QuickFlow.prototype),
    {overview, preview, result: {judgment: {judgments: []}}, visible: () => true}).checklistPanel();
  const gap = {kind: 'MISSING_INPUT', module: 'BURDEN', message: '키보드·마우스 집중 입력: 하루 총 시간 입력 필요', criterion_no: 1};
  const old = ['근로자대표 또는 해당 작업 근로자의 참여 여부·기록을 확인하세요.', '작업설비의 변경 여부와 주요 내용을 확인하세요.', '작업 관련 근골격계 징후·증상 조사 방법과 결과를 기록하세요.'];
  const withGap = panel({tasks: [{counts: {needs_input_count: 1, needs_review_count: 0}, next_inputs: [gap]}], survey_followups: old});
  for (const word of ASKING) assert.ok(!withGap.includes(word), `the panel does not mention ${word}`);
  assert.match(withGap, /has-gaps/);
  assert.match(withGap, /키보드·마우스 집중 입력/, 'a real calculation gap is still told');
  assert.equal((withGap.match(/data-jump=/g) || []).length, 1, 'and it still has its own way back to the question');
  assert.match(withGap, /data-jump="crit_keyboard"/);
  const clean = panel({tasks: [{counts: {needs_input_count: 0, needs_review_count: 0}, next_inputs: []}], survey_followups: old});
  assert.match(clean, /quick-check clean/, 'follow-ups of the removed groups can no longer keep the panel from being clean');
  assert.match(clean, /빠진 항목이 없어요/);
  assert.equal((clean.match(/data-jump=/g) || []).length, 0);
  assert.equal(typeof QuickFlow.prototype.followupTarget, 'undefined', 'no jump table for the removed groups');
  const tagsNote = {kind: 'REVIEW_REQUIRED', module: 'TAGS', message: '자세 표시(사진에서 몸통·목·팔 자세가 보인 횟수) 결과가 일부 비어 있어요.'};
  const onlyTags = panel({tasks: [{counts: {needs_input_count: 0, needs_review_count: 0}, next_inputs: [tagsNote]}]});
  assert.match(onlyTags, /quick-check clean/, 'the side calculation (자세 표시) that no score uses does not make the panel ask anything');
  assert.doesNotMatch(onlyTags, /자세 표시/);
  const tagsAndGap = panel({tasks: [{counts: {needs_input_count: 1, needs_review_count: 0}, next_inputs: [tagsNote, gap]}]});
  assert.doesNotMatch(tagsAndGap, /자세 표시/); assert.match(tagsAndGap, /키보드·마우스 집중 입력/, 'a real calculation gap next to it is still told');
  // The note under a real gap names the button that calculates again: the one page's save button, or the last group's button of the older questions.
  const note = (extra = {}) => Object.assign(Object.create(QuickFlow.prototype), {overview: {tasks: [{counts: {needs_input_count: 1, needs_review_count: 0}, next_inputs: [gap]}]}, preview: {questions: [{id: 'crit_keyboard'}]}, result: {judgment: {judgments: []}}, visible: () => true}, extra).checklistPanel();
  assert.match(note({intake: {state: {}}}), /"저장하고 결과 보기"를 다시 눌러야/, 'the one page is saved with its own button');
  assert.doesNotMatch(note({intake: {state: {}}}), /최종 결과 계산/);
  assert.match(note(), /"최종 결과 계산"을 다시 눌러야/, 'the older group-by-group questions keep their last-group button');

  // 2. Nothing of the four groups is sent: the survey draft holds only the kept fields, whatever the answers or the saved survey say.
  const saved = Object.fromEntries([...KEPT.map(key => [key, key === 'survey_type' ? 'REGULAR' : key.endsWith('date') ? '2026-10-26' : '']),
    ['occasional_reason', '새 설비'], ['occasional_cause', 'DISEASE_CASE'], ['workplace_situation', {equipment_status: 'YES'}], ['participation', {status: 'YES'}], ['symptom_survey', {method: 'QUESTIONNAIRE'}]]);
  const draft = QuickFlow.prototype.surveyDraft.call({answers: {investigator: '김조사', situation_equipment: 'YES', participation: 'YES', participation_method: 'MEETING', symptom: 'QUESTIONNAIRE'}}, saved);
  assert.deepEqual(Object.keys(draft).sort(), KEPT);
  assert.equal(draft.investigator, '김조사', 'the kept answers still go through');
  const source_ = source('quick-flow.js');
  for (const key of REMOVED) assert.ok(!source_.includes(key), `quick-flow.js has no ${key}`);

  // 3. A question of a removed kind is not restored from a saved survey any more (the question list has none either).
  const task = {task_name: '박스 포장', conditions: {}, capture: {slots: []}, manual: [], legal: {criteria: Array.from({length: 11}, (_, i) => ({criterion_no: i + 1, condition_present: 'UNKNOWN'})), exposures: []}};
  const questions = [{id: 'investigator', kind: 'text', target: {type: 'survey', field: 'investigator'}, choices: []},
    {id: 'situation_equipment', kind: 'choice', target: {type: 'situation', field: 'equipment_status'}, choices: [{value: 'YES'}]},
    {id: 'participation', kind: 'choice', target: {type: 'participation', field: 'status'}, choices: [{value: 'YES'}]},
    {id: 'symptom', kind: 'choice', target: {type: 'symptom', field: 'method'}, choices: [{value: 'QUESTIONNAIRE'}]}];
  assert.deepEqual(savedAnswers(questions, task, saved), {}, 'only the kept survey fields could ever come back, and this survey has none filled');
  assert.deepEqual(savedAnswers(questions, task, {...saved, investigator: '김조사'}), {investigator: '김조사'});
  assert.deepEqual(LATER_GROUPS, ['조사 정보'], 'the group list that waits behind "나중에" holds no removed group');

  // 4. The one-sheet survey editor: the removed panels are gone, the previous survey date and the survey type stay.
  const {views} = await import(url('survey/views.js'));
  const {inputs} = await import(url('survey/inputs.js'));
  const editor = Object.assign({host: {innerHTML: ''}}, views);
  views.render.call(editor);
  const html = editor.host.innerHTML;
  assert.deepEqual([...html.matchAll(/data-intake="([^"]+)"/g)].map(match => match[1]), ['previous_survey_date'], 'the one panel holds exactly one control');
  for (const word of [...ASKING, '작업장 상황', '근골격계', '익명', 'questionnaire', 'symptom', 'situation', 'occasional_cause']) assert.ok(!html.includes(word), `the editor panel does not show ${word}`);
  assert.equal(typeof views.renderResponses, 'undefined');
  assert.ok(!fs.existsSync(frontend('survey/events.js')), 'the anonymous response form and its events are gone');
  const filled = [];
  const node = name => name === 'previous_survey_date' ? {set value(v) { filled.push(v); }} : null;
  const reader = Object.assign({host: {querySelector: selector => node(selector.match(/data-intake="([^"]+)"/)[1])}}, inputs);
  inputs.fill.call(reader, {previous_survey_date: '2025-10-01', participation: {status: 'YES'}, symptom_survey: {responses: [{response_code: 'a'}]}, workplace_situation: {equipment_status: 'YES'}, occasional_cause: 'DISEASE_CASE'});
  assert.deepEqual(filled, ['2025-10-01'], 'a survey an older version saved opens, and only the kept date is read from it');
  const read = (value, extra = []) => inputs.collect.call(Object.assign({host: {querySelectorAll: () => [{dataset: {intake: 'previous_survey_date'}, value}, ...extra]}}, inputs), {});
  assert.deepEqual(read('2026-10-01'), {previous_survey_date: '2026-10-01'});
  assert.deepEqual(read(''), {previous_survey_date: null});
  assert.deepEqual(read('2026-10-01', [{dataset: {intake: 'participation_status'}, value: 'YES'}]), {previous_survey_date: '2026-10-01'}, 'a stray control of the old sections is not collected either');
  const editorSource = source('survey-editor.js');
  assert.match(editorSource, /const labels = \['기본 정보', '이전 조사'\];/);
  const intakeSource = source('survey-intake.js');
  assert.match(intakeSource, /value="INITIAL"/, 'the survey type choice keeps its third option');
  const desktop = source('desktop.js'), html_ = source('desktop.html');
  for (const key of REMOVED) { assert.ok(!desktop.includes(key), `desktop.js has no ${key}`); assert.ok(!html_.includes(key), `desktop.html has no ${key}`); }
  assert.ok(!html_.includes('수시 사유'), 'the free-text reason box of the survey form is gone');

  // 5. The sample survey is built without the groups, and the analysis workspace's Excel page neither lists them nor shows the follow-up lines.
  const {createSampleSurvey} = await import(url('sample-data.js'));
  const calls = [];
  await createSampleSurvey(async (method, params) => { calls.push([method, params]); return method === 'create_task' ? {task_id: 1, input_revision: 0, legal: {criteria: Array.from({length: 11}, () => ({evidence: {}})), exposures: [{evidence: {}}]}} : {survey_id: 1}; });
  assert.deepEqual(Object.keys(calls.find(([method]) => method === 'create_survey')[1].draft).sort(), ['department', 'investigator', 'process', 'survey_date', 'survey_type', 'title']);
  const {createExportView} = await import(url('analysis/export-view.js'));
  const overview = {state: {reviewed: false, review_current: false, has_incomplete: true, has_stale: false, survey_input_complete: false},
    counts: {needs_input_count: 1, needs_review_count: 0, incomplete_reba_count: 0}, comparisons: [], survey_followups: old,
    tasks: [{task_id: 1, task_name: '상자', analysis_id: null, currentness: 'NONE', review_status: 'NO_ANALYSIS', next_inputs: [{message: '분석을 아직 하지 않았어요'}]}]};
  const stub = {s: {survey: {survey_id: 1}, overview, comparisonPool: [], tasks: [{task_id: 1, task_name: '상자'}], comparisonBefore: '', comparisonAfter: '', comparisonNote: ''},
    LocoReview: {nextInput: item => item.message, comparison: () => ''}, inputLabel: value => value, $: () => null, e: value => String(value ?? ''), fmt: value => String(value ?? ''),
    badge: value => String(value ?? ''), field: () => '', select: () => '', card: (title, body) => `<section><h3>${title}</h3>${body}</section>`, empty: text => text,
    metric: (label, value) => `<b>${label}</b>${value}`, context: () => ''};
  const page = createExportView(stub).exportPage();
  assert.match(page, /분석 없음/, 'an unanalysed task remains identifiable in optional output status');
  assert.doesNotMatch(page, /id="next-inputs"|다음 입력 안내/, 'export does not become another mandatory input checklist');
  for (const label of ['조사자 검토 기록', '검토 현재성', '입력 또는 계산 미완료', '이전 분석 포함']) assert.ok(page.includes(label), `the optional state ${label} stays`);
  assert.ok(!page.includes('undefined'), 'a state key the page does not know is not drawn as an empty box');
  for (const word of [...old, '조사 단계 입력 보완', '별지1', '별지2', '서식 기반 추가']) assert.ok(!page.includes(word), `the Excel page does not show ${word}`);
  const placeholders = source('input-placeholders.js');
  for (const key of ['equipment_notes', 'workload_notes', 'speed_notes', 'work_pattern_notes', 'participant_code', 'participation_notes', 'symptom_summary', 'response_code', 'response_injury_sites']) assert.ok(!placeholders.includes(key), `no writing hint for ${key}`);
  console.log('PASS the four removed record groups are not asked, shown or sent; the calculation gaps, survey type and previous survey date stay');
})().catch(error => { console.error(error); process.exitCode = 1; });
