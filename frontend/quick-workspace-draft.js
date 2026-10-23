// UI checkpoints are separate from the disposable, unfinished-analysis draft.
export const WORKSPACE_DRAFT_KEY = 'loco.quick.workspace-draft.v1';
export const WORKSPACE_STEPS = ['start', 'provisional', 'questions', 'result', 'review', 'excel'];
export function readWorkspaceDraft(storage = localStorage) {
  try {
    const value = JSON.parse(storage.getItem(WORKSPACE_DRAFT_KEY) || 'null');
    return value?.version === 1 && WORKSPACE_STEPS.includes(value.step) ? value : null;
  } catch { return null; }
}
export function writeWorkspaceDraft(value, storage = localStorage) {
  // An explicit save must report quota/access failures instead of claiming success.
  if (value) storage.setItem(WORKSPACE_DRAFT_KEY, JSON.stringify(value));
  else storage.removeItem(WORKSPACE_DRAFT_KEY);
}
export const missingWorkspaceRecord = error => error?.code === 'NOT_FOUND' || /^NOT_FOUND:/.test(error?.message || '');
export function clearWorkspaceDraftForSurvey(survey, storage = localStorage) {
  const draft = readWorkspaceDraft(storage);
  if (draft?.survey?.id !== survey.survey_id || draft.survey.createdAt !== survey.created_at) return false;
  writeWorkspaceDraft(null, storage);
  return true;
}
export async function workspaceTargetAvailable(draft, api) {
  if (!draft?.task) return true; // A text-only checkpoint has no DB parent yet.
  try {
    const survey = await api('get_survey', {survey_id: draft.survey?.id});
    const full = await api('get_task', {task_id: draft.task.id});
    return survey.created_at === draft.survey.createdAt && full.task.created_at === draft.task.createdAt &&
      full.task.survey_id === survey.survey_id;
  } catch (error) {
    if (missingWorkspaceRecord(error)) return false;
    throw error; // A disconnected service is not evidence of deletion.
  }
}
export function captureWorkspace(flow) {
  const ref = row => row ? {id: row.analysis_id, createdAt: row.created_at} : null;
  return {
    version: 1, savedAt: new Date().toISOString(), step: flow.step,
    survey: flow.survey && {id: flow.survey.survey_id, createdAt: flow.survey.created_at},
    task: flow.task && {id: flow.task.task_id, createdAt: flow.task.created_at, revision: flow.task.input_revision},
    result: ref(flow.result), baseline: ref(flow.baseline),
    photos: Object.fromEntries(Object.entries(flow.photos || {}).map(([view, item]) => [view, item.photo.photo_id])),
    adaptive: Boolean(flow.intake?.state), preview: flow.preview,
    ui: Object.fromEntries(['answers', 'group', 'review', 'aiDraft', 'aiEditorOpen', 'ai', 'intakeText',
      'laterOpen', 'excelTab', 'selectedPhotoView', 'reopened', 'stale'].map(key => [key, flow[key]])),
    intake: {state: flow.intake?.state, questions: flow.intake?.questions || [],
      text: flow.intake?.text || '', dialogOpen: Boolean(flow.intake?.dialogOpen),
      editing: flow.intake?.editing, writingFor: flow.intake?.writingFor, focusPair: flow.intake?.focusPair,
      values: [...(flow.intake?.values || [])], pairValues: [...(flow.intake?.pairValues || [])]}
  };
}
export async function loadWorkspace(draft, api) {
  if (draft?.version !== 1 || !WORKSPACE_STEPS.includes(draft.step)) throw Error('임시 저장 형식을 확인할 수 없어요.');
  if (!draft.task) {
    if (draft.step !== 'start' || draft.survey || draft.result || draft.baseline || Object.keys(draft.photos || {}).length)
      throw Error('임시 저장 대상이 올바르지 않아요.');
    return {survey: null, task: null, photos: {}, result: null, baseline: null};
  }
  const survey = await api('get_survey', {survey_id: draft.survey?.id});
  const full = await api('get_task', {task_id: draft.task.id});
  if (survey.survey_id !== draft.survey?.id || survey.created_at !== draft.survey.createdAt ||
      full.task.task_id !== draft.task.id || full.task.survey_id !== survey.survey_id ||
      full.task.created_at !== draft.task.createdAt)
    throw Error('삭제되었거나 다른 데이터의 기록이라 이어 갈 수 없어요.');
  if (full.task.input_revision !== draft.task.revision)
    throw Error('임시 저장 후 작업 입력이 변경됐어요. 최신 기록을 열어 확인해 주세요. 임시 메모는 보관돼요.');
  const analysis = async ref => {
    if (!ref) return null;
    const row = await api('get_analysis', {analysis_id: ref.id});
    if (row.analysis_id !== ref.id || row.task_id !== full.task.task_id || row.created_at !== ref.createdAt)
      throw Error('임시 저장 당시의 분석 기록을 찾지 못했어요.');
    return row;
  };
  const result = await analysis(draft.result), baseline = await analysis(draft.baseline);
  if (['result', 'review', 'excel'].includes(draft.step) && !result) throw Error('분석 기록이 없어 이 단계로 돌아갈 수 없어요.');
  const photos = {};
  for (const [view, id] of Object.entries(draft.photos || {})) {
    const photo = full.photos.find(row => row.photo_id === id);
    if (!photo) throw Error('임시 저장한 사진이 삭제됐어요. 최신 기록을 열어 확인해 주세요.');
    photos[view] = {photo, image: await api('get_photo_preview', {photo})};
  }
  return {survey, task: full.task, photos, result, baseline};
}
