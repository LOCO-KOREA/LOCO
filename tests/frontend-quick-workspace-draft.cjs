const assert = require('node:assert/strict');
const path = require('node:path');
const {pathToFileURL} = require('node:url');
(async () => {
  const load = file => import(pathToFileURL(path.resolve(__dirname, '../frontend', file)).href);
  const {QuickFlow} = await load('quick-flow.js');
  const {captureWorkspace, loadWorkspace, readWorkspaceDraft, writeWorkspaceDraft, WORKSPACE_STEPS, WORKSPACE_DRAFT_KEY} = await load('quick-workspace-draft.js');
  const memory = new Map();
  global.localStorage = {getItem: key => memory.get(key) || null, setItem: (key, value) => memory.set(key, value), removeItem: key => memory.delete(key)};
  global.window = {scrollTo() {}};
  const survey = {survey_id: 1, created_at: 'survey-original'};
  const task = {task_id: 2, survey_id: 1, created_at: 'task-original', input_revision: 7};
  const analysis = {analysis_id: 3, task_id: 2, created_at: 'analysis-original', ai: []};
  const photo = {photo_id: 4};
  const make = (step = 'start') => {
    const calls = [], errors = [], notes = [];
    const flow = Object.create(QuickFlow.prototype);
    Object.assign(flow, {survey: {...survey}, task: {...task}, step, busy: false, photos: {LEFT: {photo}},
      result: ['result', 'review', 'excel'].includes(step) ? {...analysis} : null, baseline: null,
      preview: null, answers: {unknown: null, count: 0}, group: 1, review: {reviewer: '검토자', note: '미저장 메모'},
      aiDraft: '적용 전 설명', aiEditorOpen: true, intakeText: '정리 전 작업 설명', ai: null, settings: {}, stale: true,
      laterOpen: true, excelTab: 2, selectedPhotoView: 'LEFT', reopened: false,
      render() {}, notify: text => notes.push(text), onError: error => errors.push(error.message),
      intake: {text: '아직 보내지 않은 답변', state: null, values: new Map(), pairValues: new Map([['pair', null]]),
        dialogOpen: false, async flush() {}, reset() {this.state = null; this.text = ''; this.values = new Map(); this.pairValues = new Map();}},
      api: async (method, args) => {
        calls.push([method, args]);
        if (method === 'get_survey') return {...survey};
        if (method === 'get_settings') return {};
        if (method === 'get_task') return {task: {...task}, photos: [photo]};
        if (method === 'get_analysis') return {...analysis};
        if (method === 'get_photo_preview') return {data_url: 'photo'};
        if (method === 'preview_excel') return {tasks: [], comparisons: []};
        if (method === 'preview_excel_sheets') return {sheets: [{name: 'one'}, {name: 'two'}, {name: 'three'}]};
        if (method === 'quick_preview') return {questions: []};
        throw Error('Unexpected API: ' + method);
      }});
    return {flow, calls, errors, notes};
  };
  // Adaptive intake stores raw direction codes; earlier quick records used Korean labels.
  // Reopening must not funnel FRONT through the LEFT/RIGHT legacy fallback.
  const directionNames = {LEFT: '왼쪽 사진', RIGHT: '오른쪽 사진', FRONT: '정면·후면 사진'};
  for (const labels of [
    ['LEFT', 'RIGHT', 'FRONT'], ['FRONT', 'RIGHT', 'LEFT'],
    ['왼쪽 사진', '정면·후면 사진', '오른쪽 사진'], ['LEFT', '정면·후면 사진', 'RIGHT'], ['FRONT']
  ]) {
    const reopening = make('home');
    const reopenedTask = {...task, latest_analysis_id: analysis.analysis_id, capture: {slots: labels.map((label, i) => ({
      label, photo_id: i + 11, camera_side: 'RIGHT'
    }))}};
    const registered = labels.map((_, i) => ({photo_id: i + 11}));
    reopening.flow.intake.hasSession = () => false;
    reopening.flow.api = async (method, params) => {
      reopening.calls.push([method, params]);
      if (method === 'get_survey') return {...survey};
      if (method === 'list_tasks') return [reopenedTask];
      if (method === 'get_task_result') return {analysis: {...analysis}};
      if (method === 'get_task') return {task: reopenedTask, photos: registered};
      if (method === 'get_photo_preview') return {data_url: `photo-${params.photo.photo_id}`, width_px: 600, height_px: 1200};
      throw Error('Unexpected reopen API: ' + method);
    };
    await reopening.flow.openExisting(survey.survey_id);
    assert.deepEqual(reopening.errors, []);
    assert.equal(Object.keys(reopening.flow.photos).length, labels.length);
    for (const [i, label] of labels.entries()) {
      const view = Object.keys(directionNames).find(key => key === label || directionNames[key] === label);
      assert.equal(reopening.flow.photos[view].photo.photo_id, registered[i].photo_id, 'display direction follows its stored slot, not inferred camera side');
    }
    await reopening.flow.workspaceBack();
    assert.equal(reopening.flow.step, 'start');
    assert.equal(Object.keys(reopening.flow.photos).length, labels.length, 'returning to photo input preserves every restored photo');
    assert.ok(reopening.flow.photos.FRONT);
    assert.ok(reopening.calls.every(([method]) => /^(get_|list_)/.test(method)), 'direction restoration never writes photo/task records');
  }
  for (const step of WORKSPACE_STEPS) {
    memory.clear();
    const saved = make(step);
    assert.equal(await saved.flow.saveWorkspace(), true);
    const resumed = make('home');
    await resumed.flow.resumeWorkspace();
    assert.deepEqual(resumed.errors, []);
    assert.equal(resumed.flow.step, step);
    assert.equal(resumed.flow.review.note, '미저장 메모');
    assert.equal(resumed.flow.aiDraft, '적용 전 설명');
    assert.equal(resumed.flow.intakeText, '정리 전 작업 설명');
    assert.equal(resumed.flow.intake.text, '아직 보내지 않은 답변');
    assert.equal(resumed.flow.selectedPhotoView, 'LEFT');
    assert.deepEqual(resumed.flow.answers, {unknown: null, count: 0});
    assert.equal(resumed.flow.intake.pairValues.get('pair'), null);
    assert.ok(resumed.calls.every(([m]) => /^(get_|preview_excel)/.test(m)), 'resume performs reads, never AI/recalculation/export');
    if (step === 'excel') assert.equal(resumed.flow.excelTab, 2);
  }
  const viewer = make('result');
  viewer.flow.photos = Object.fromEntries(['LEFT', 'FRONT', 'RIGHT'].map((view, i) => [view, {
    photo: {photo_id: i + 1}, image: {data_url: view, width_px: 600, height_px: 1200}
  }]));
  viewer.flow.selectedPhotoView = 'RIGHT';
  viewer.flow.host = {querySelector: () => ({focus() {}})};
  let markup = viewer.flow.photoStrip();
  assert.equal((markup.match(/<figure/g) || []).length, 1, 'only the selected photo is rendered');
  assert.equal((markup.match(/data-photo-view=/g) || []).length, 3);
  assert.match(markup, /data-photo-view="RIGHT" aria-pressed="true"/);
  assert.match(markup, /<img src="RIGHT"/);
  viewer.flow.click({target: {closest: () => ({dataset: {photoView: 'FRONT'}})}});
  assert.equal(viewer.flow.selectedPhotoView, 'FRONT');
  assert.equal(viewer.flow.result.analysis_id, analysis.analysis_id);
  assert.deepEqual(viewer.calls, [], 'photo display switching does not call scoring, representative selection or saving APIs');
  assert.equal(captureWorkspace(viewer.flow).ui.selectedPhotoView, 'FRONT');
  delete viewer.flow.photos.FRONT;
  markup = viewer.flow.photoStrip();
  assert.match(markup, /data-photo-view="LEFT" aria-pressed="true"/);
  assert.match(markup, /data-photo-view="FRONT"[^>]*disabled/);
  viewer.flow.photos = {};
  assert.match(viewer.flow.photoStrip(), /등록된 사진이 없어요/);
  assert.doesNotMatch(viewer.flow.photoStrip(), /<figure/);
  memory.clear();
  const textOnly = make();
  Object.assign(textOnly.flow, {survey: null, task: null, photos: {}});
  await textOnly.flow.saveWorkspace();
  const restoredText = make('home');
  await restoredText.flow.resumeWorkspace();
  assert.equal(restoredText.flow.intakeText, textOnly.flow.intakeText);
  assert.deepEqual(restoredText.calls, [], 'saving bare text never creates a DB row');

  const fixture = captureWorkspace(make('review').flow);
  const photoRevision = make(); photoRevision.flow.task.input_revision = 6;
  await photoRevision.flow.saveWorkspace();
  assert.equal(readWorkspaceDraft().task.revision, 7, 'photo registration revision is refreshed before checkpointing');
  for (const change of [
    (m, value) => m === 'get_survey' ? {...value, created_at: 'replacement'} : value,
    (m, value) => m === 'get_task' ? {...value, task: {...value.task, created_at: 'replacement'}} : value,
    (m, value) => m === 'get_task' ? {...value, task: {...value.task, input_revision: 8}} : value,
    (m, value) => m === 'get_task' ? {...value, photos: []} : value,
    (m, value) => m === 'get_analysis' ? {...value, created_at: 'replacement'} : value,
    (m, value) => m === 'get_analysis' ? {...value, task_id: 999} : value
  ]) {
    const {flow} = make();
    await assert.rejects(loadWorkspace(fixture, async (m, p) => change(m, await flow.api(m, p))));
  }
  writeWorkspaceDraft(fixture);
  const deleted = make('home');
  deleted.flow.api = async () => {throw Error('삭제된 기록');};
  await deleted.flow.resumeWorkspace();
  assert.equal(deleted.flow.step, 'home');
  assert.equal(readWorkspaceDraft().ui.review.note, '미저장 메모', 'failed restore retains checkpoint');

  // A successful deletion owns cleanup; a failed deletion or unrelated target does not.
  for (const [id, fail, expected] of [[1, false, false], [1, true, true], [9, false, true]]) {
    writeWorkspaceDraft(fixture);
    const deleting = make('home'), originalApi = deleting.flow.api;
    deleting.flow.confirmDelete = id;
    deleting.flow.api = async (method, params) => {
      if (method === 'delete_survey') {if (fail) throw Error('삭제 실패'); return {};}
      if (method === 'list_surveys') return [];
      return originalApi(method, params);
    };
    await deleting.flow.deleteSurvey(id);
    assert.equal(Boolean(readWorkspaceDraft()), expected);
    if (!expected) assert.doesNotMatch(deleting.flow.viewHome(), /data-quick="workspace-resume"/);
  }
  writeWorkspaceDraft(fixture);
  const replaced = make('home'), replacementApi = replaced.flow.api;
  replaced.flow.confirmDelete = 1;
  replaced.flow.api = async (method, params) => {
    if (method === 'get_survey') return {...survey, created_at: 'different-database'};
    if (method === 'delete_survey') return {};
    if (method === 'list_surveys') return [];
    return replacementApi(method, params);
  };
  await replaced.flow.deleteSurvey(1);
  assert.ok(readWorkspaceDraft(), 'deleting a reused ID in another DB retains the original checkpoint');

  for (const missing of ['get_survey', 'get_task']) {
    writeWorkspaceDraft(fixture);
    const orphan = make('home'), originalApi = orphan.flow.api;
    orphan.flow.surveys = [survey];
    orphan.flow.api = async (method, params) => {
      if (method === missing) throw Error('NOT_FOUND: missing record');
      if (method === 'list_surveys') return [survey];
      return originalApi(method, params);
    };
    orphan.flow.intake.loadContract = async () => ({});
    await orphan.flow.loadHome();
    assert.doesNotMatch(orphan.flow.viewHome(), /data-quick="workspace-resume"/);
    assert.deepEqual(orphan.errors, []);
    assert.ok(readWorkspaceDraft(), 'missing in the selected DB does not erase another DB checkpoint');
    // Also handle deletion between rendering the home card and clicking it.
    orphan.flow.workspaceUnavailable = null;
    await orphan.flow.resumeWorkspace();
    assert.doesNotMatch(orphan.flow.viewHome(), /data-quick="workspace-resume"/);
    assert.deepEqual(orphan.errors, []);
    assert.match(orphan.notes[0], /삭제되었거나/);
  }
  writeWorkspaceDraft(fixture);
  const disconnected = make('home');
  disconnected.flow.surveys = [survey];
  disconnected.flow.api = async () => {throw Error('서비스 연결 끊김');};
  await disconnected.flow.resumeWorkspace();
  assert.match(disconnected.flow.viewHome(), /data-quick="workspace-resume"/);
  assert.ok(readWorkspaceDraft());
  assert.deepEqual(disconnected.errors, ['서비스 연결 끊김']);

  const full = make();
  let reachedHome = false;
  full.flow.loadHome = async () => {reachedHome = true;};
  const originalSet = localStorage.setItem;
  localStorage.setItem = () => {throw Error('저장 공간 부족');};
  await full.flow.workspaceHome();
  assert.equal(reachedHome, false);
  assert.equal(full.flow.step, 'start');
  assert.equal(full.notes.length, 0);
  assert.deepEqual(full.errors, ['저장 공간 부족']);
  localStorage.setItem = originalSet;

  const failedAutoSave = make();
  failedAutoSave.flow.intake.flush = async () => {throw Error('입력 저장 실패');};
  assert.equal(await failedAutoSave.flow.saveWorkspace(), false);
  assert.equal(failedAutoSave.notes.length, 0);

  const adaptive = make('questions');
  adaptive.flow.intake.state = {task, contract: {version: 'test'}};
  await adaptive.flow.saveWorkspace();
  const adaptiveResume = make('home');
  adaptiveResume.flow.intake.loadContract = async () => ({version: 'test'});
  adaptiveResume.flow.intake.open = async () => {throw Error('session must not run on restore');};
  await adaptiveResume.flow.resumeWorkspace();
  assert.deepEqual(adaptiveResume.errors, []);
  assert.equal(adaptiveResume.flow.step, 'questions');
  assert.equal(adaptiveResume.flow.intake.text, '아직 보내지 않은 답변');

  for (const [step, expected] of [['provisional', 'start'], ['questions', 'provisional'], ['result', 'questions'], ['review', 'result'], ['excel', 'review']]) {
    const {flow} = make(step); flow.preview = {questions: []};
    await flow.workspaceBack(); assert.equal(flow.step, expected);
  }
  const reopened = make('result');
  await reopened.flow.workspaceBack(); assert.equal(reopened.flow.step, 'start');
  const locked = make('review'); locked.flow.busy = true;
  await locked.flow.workspaceBack(); assert.equal(locked.flow.step, 'review');
  assert.equal(await locked.flow.saveWorkspace(), false);
  const savingAnswer = make('questions'); savingAnswer.flow.intake.saving = true;
  await savingAnswer.flow.workspaceBack(); assert.equal(savingAnswer.flow.step, 'questions');

  // New/discard actions must not delete a manually checkpointed survey, even with an old draft present.
  writeWorkspaceDraft(fixture);
  localStorage.setItem('loco.quick.draft.v1', JSON.stringify({surveyId: 1}));
  const guarded = make('home'); guarded.flow.loadHome = async () => {};
  await guarded.flow.discardDraft();
  assert.equal(guarded.calls.length, 0);
  localStorage.setItem('loco.quick.draft.v1', JSON.stringify({surveyId: 1}));
  guarded.flow.click({target: {closest: () => ({dataset: {quick: 'new'}})}});
  assert.equal(guarded.calls.length, 0);
  localStorage.setItem(WORKSPACE_DRAFT_KEY, '{malformed');
  assert.equal(readWorkspaceDraft(), null);
  console.log('PASS workspace stages 1–6, text-only draft, local notes, identity/revision/deletion guards, storage errors, navigation, and no implicit AI/export');
})().catch(error => {console.error(error); process.exitCode = 1;});
