import {userText} from './user-language.js';
import {selectPhotoCrop} from './photo-crop.js';
import {captureWorkspace, loadWorkspace, readWorkspaceDraft, writeWorkspaceDraft, WORKSPACE_STEPS, clearWorkspaceDraftForSurvey, workspaceTargetAvailable, missingWorkspaceRecord} from './quick-workspace-draft.js';

import {renderPoseSettings,readPoseSettings,poseForView,mountPoseSettings} from './pose-settings.js';
import {DRAFT_POLICY,localDrafts,initializeDrafts,newDraftId,readExplanationDraft,saveExplanationDraft,clearExplanationDraft} from './drafts.js';

import {renderQuickExplanation} from './quick-explanation.js';
import {renderRebaScale, rebaScoreClass} from './reba-scale.js';
import {AdaptiveIntake} from './intake/client.js';
import {renderActivity,updateActivity} from './intake/activity.js';
import {enabledAiSettings,persistedSettings} from './ai-settings.js';
// LOCO simple flow: everything happens here, in order, with question cards.
//   home -> photos (left / front-back / right) -> provisional REBA -> questions -> result -> review, AI explanation, Excel, before/after.
// Provisional scores are recalculated; known input facts and their evidence are stored by adaptive intake.
// and every final number comes from the regular calculation engine.
const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[c]));
const RISK = {NEGLIGIBLE: '무시 가능', LOW: '낮음', MEDIUM: '보통', HIGH: '높음', VERY_HIGH: '매우 높음'};
const STATUS = {APPLICABLE: '해당 초안', NOT_APPLICABLE: '비해당 초안', NEEDS_INPUT: '입력 필요', NEEDS_REVIEW: '검토 필요', EXCLUDED: '제외'};
const VIEWS = [
  {id: 'LEFT', title: '왼쪽에서', hint: '작업자의 왼쪽 몸이 보이게 옆에서'},
  {id: 'FRONT', title: '정면 또는 후면', hint: '앞이나 뒤에서 (선택)'},
  {id: 'RIGHT', title: '오른쪽에서', hint: '작업자의 오른쪽 몸이 보이게 옆에서'}
];
const VIEW_LABEL = {LEFT: '왼쪽 사진', FRONT: '정면·후면 사진', RIGHT: '오른쪽 사진'};
const VALUE_KO = {UNDER_30: '30° 미만', FROM_30_TO_60: '30~60°', OVER_60: '60° 초과'};
const FIELD_KO = {trunk_base: '몸통 굽힘', trunk_twisted: '몸통 비틀림', trunk_side_bent: '몸통 옆 기울임', neck_base: '목 굽힘', neck_twisted: '목 비틀림', neck_side_bent: '목 옆 기울임', legs_support: '다리 지지', seated: '앉은 자세', knee_band: '무릎 굽힘', shock_force: '충격', static_over_1min: '1분 이상 유지', small_repeat_over_4min: '반복', rapid_change_or_unstable: '불안정 자세', upper_arm_base: '위팔', arm_abducted_or_rotated: '팔 벌림', shoulder_raised: '어깨 들림', arm_supported_or_gravity_assisted: '팔 받침', lower_arm_base: '팔꿈치', wrist_base: '손목', wrist_deviated_or_twisted: '손목 비틀림', coupling: '손잡이', effective_load_kg: '무게'};
const CRIT_NAME = {1: '키보드·마우스 집중 입력', 2: '같은 동작 반복', 3: '손·팔의 부담 자세', 4: '목·허리 굽힘·비틀림', 5: '쪼그림·무릎 굽힘', 6: '한 손 손가락 집기', 7: '한 손 들기·쥐기', 8: '25kg 이상 들기', 9: '10kg 이상 불편한 위치 들기', 10: '반복 들기', 11: '손·무릎 충격'};
const TASK_KEYS = ['schema_version', 'task_kind', 'task_name', 'input_template', 'worker_count', 'conditions', 'legal', 'capture', 'manual', 'analysis_scope', 'legacy_input'];
const SURVEY_KEYS = ['survey_type', 'survey_date', 'investigator', 'department', 'process', 'title', 'occasional_reason', 'occasional_cause', 'previous_survey_date', 'workplace_situation', 'participation', 'symptom_survey'];
const STEPS = [['start', '사진·작업 설명'], ['provisional', '자동 정리·1차 점수'], ['questions', '추가 확인'], ['result', '결과'], ['review', '검토·설명'], ['excel', 'Excel']];
// Which ticked work type feeds which statutory criterion (numbers are never shown while answering).
const GATES = {1: 'keyboard', 2: 'repeat', 3: 'arm_over', 4: 'trunk_neck', 5: 'knee', 6: 'pinch', 7: 'grip', 8: 'lift', 9: 'lift', 10: 'lift', 11: 'impact'};
const GATE_CRITERIA = Object.entries(GATES).reduce((map, [n, gate]) => ({...map, [gate]: [...(map[gate] || []), Number(n)]}), {});
const AI_REASON = {DISABLED: 'AI 설명이 꺼져 있어요', NO_API_KEY: '이 PC에 AI 키가 없어요', MODEL_NOT_CONFIGURED: 'AI 모델이 정해지지 않았어요', TIMEOUT: 'AI 응답이 설정한 제한 시간 안에 오지 않았어요', API_ERROR: 'AI 서버가 요청을 받지 못했어요(키·모델·네트워크 확인)', INVALID_STRUCTURED_CONTENT: 'AI 응답이 정해진 형식과 맞지 않았어요', INCOMPLETE_RESPONSE: 'AI 응답이 끝까지 오지 않았어요', REFUSAL_OR_EMPTY_RESPONSE: 'AI가 답을 주지 않았어요', OPENAI_SDK_MISSING: 'AI 연결 부품이 없어요'};
const DRAFT_KEY = DRAFT_POLICY.legacyQuick;
const readDraft = () => { try { return JSON.parse(localStorage.getItem(DRAFT_KEY) || 'null'); } catch { return null; } };
const writeDraft = value => { try { value ? localStorage.setItem(DRAFT_KEY, JSON.stringify(value)) : localStorage.removeItem(DRAFT_KEY); return true; } catch { return false; } };
const evidence = (text, source = 'INTERVIEW') => ({source, text, observed_at: new Date().toISOString()});
const today = () => new Date().toLocaleDateString('sv-SE', {timeZone: 'Asia/Seoul'});


// Rebuild the answers a person gave from what was saved, so "개선 후 다시 비교" can start from the same answers
// even after the app was closed. Only values that were really saved are restored; everything else is asked again.
export function savedAnswers(questions, task, survey) {
  const a = {}, slots = (task.capture?.slots || []).filter(slot => slot.photo_id != null), first = slots[0];
  const obs = first?.observation || {};
  const manual = new Map((task.manual || []).map(m => [`${m.scope}.${m.field}`, m.value]));
  const saved = (scope, field) => manual.get(`${scope === 'BOTH' ? 'LEFT' : scope}.${field}`);
  const inChoices = (q, value) => q.choices.some(c => String(c.value) === String(value));
  for (const q of questions) {
    const t = q.target;
    if (q.id === 'context' && first) a.context = first.side_view_verified === 'YES' && obs.single_person === 'YES' ? 'YES' : 'NO';
    else if (q.id.startsWith('view_')) {
      const slot = slots.find(x => x.camera_side === q.id.slice(5));
      if (slot?.forward_direction) a[q.id] = slot.forward_direction;
    }
    else if (q.id === 'load' && obs.load_state && obs.load_state !== 'UNKNOWN') a.load = obs.load_state;
    else if (q.id === 'load_kg' && obs.measured_load_kg != null) a.load_kg = obs.measured_load_kg;
    else if (t.type === 'manual') {
      const value = saved(t.scope, t.field);
      if (value !== undefined && value !== null && value !== 'NOT_APPLICABLE' && inChoices(q, value)) a[q.id] = value;
    }
    else if (t.type === 'flags') {
      const present = q.items.some(item => item.sets.some(set => saved(set.scope, set.field) !== undefined));
      if (present) a[q.id] = q.items.filter(item => item.sets.every(set => set.checked === null || saved(set.scope, set.field) === set.checked)).map(item => item.key);
    }
    else if (t.type === 'conditions') {
      const value = task.conditions?.[t.field];
      if (value !== null && value !== undefined && value !== '') a[q.id] = value;
    }
    else if (t.type === 'task') {
      const value = task[t.field];
      if (value && !(t.field === 'task_name' && value === '사진 분석 작업')) a[q.id] = value;
    }
    else if (t.type === 'survey') { if (survey[t.field]) a[q.id] = survey[t.field]; }
    else if (t.type === 'situation') { const v = survey.workplace_situation?.[t.field]; if (v && v !== 'UNKNOWN') a[q.id] = v; }
    else if (t.type === 'participation') { const v = survey.participation?.[t.field]; if (v && v !== 'UNKNOWN') a[q.id] = v; }
    else if (t.type === 'symptom') { const v = survey.symptom_survey?.method; if (v && v !== 'UNKNOWN') a[q.id] = v; }
    else if (t.type === 'work_types') {
      const present = Object.entries(GATE_CRITERIA).filter(([, numbers]) => numbers.some(n => task.legal.criteria[n - 1]?.condition_present === 'YES')).map(([gate]) => gate);
      const known = Object.values(GATE_CRITERIA).flat().some(n => task.legal.criteria[n - 1]?.condition_present && task.legal.criteria[n - 1].condition_present !== 'UNKNOWN');
      if (known) a[q.id] = present;
    }
    else if (t.type === 'criterion_card') {
      const numbers = q.criteria || [q.criterion];
      const criteria = numbers.map(n => task.legal.criteria[n - 1]).filter(Boolean);
      if (!criteria.some(c => c.condition_present === 'YES')) continue;
      const values = {};
      for (const field of q.fields) {
        let value;
        if (field.to.exposure) value = task.legal.exposures.find(x => x.condition_code === field.to.exposure)?.minutes;
        else if (field.to.criterion) value = criteria[0][field.to.criterion];
        else if (field.to.lift) value = criteria.map(c => (c.rows || [])[0]?.[field.to.lift]).find(v => v !== undefined && v !== null);
        else value = (criteria[0].rows || [])[0]?.[field.to.row];
        if (value !== undefined && value !== null && !(field.type === 'truth' && value === 'UNKNOWN')) values[field.key] = value;
      }
      a[q.id] = {values};
    }
  }
  return a;
}

// ----- AI intake: one sentence about the work fills question boxes. Every item arrives with its own quote from the sentence.
const INTAKE_REASON = {...AI_REASON, NOTHING_FOUND: '문장에서 채울 수 있는 값을 찾지 못했어요. 작업 내용과 숫자(시간·횟수·무게)를 함께 적어 보세요.'};
// Survey information that does not change any calculation: asked after the result, not before it, when the AI intake is used.
export const LATER_GROUPS = ['조사 정보', '작업장 상황', '참여·증상'];

export function applyIntake(answers, questions, items) {
  const types = questions.find(q => q.id === 'work_types');
  for (const item of items) {
    if (item.kind === 'tick') {
      const keys = new Set(answers.work_types ?? (types?.items || []).filter(i => i.suggested).map(i => i.key));
      keys.add(item.gate); answers.work_types = [...keys];
    } else if (item.question_id.startsWith('crit_')) {
      const card = answers[item.question_id] ||= {values: {}};
      card.values ||= {}; card.values[item.field_key] = item.value;
    } else answers[item.question_id] = item.value;
  }
  return answers;
}

export function dropIntakeItem(answers, item) {
  if (item.kind === 'tick') {
    if (Array.isArray(answers.work_types)) answers.work_types = answers.work_types.filter(key => key !== item.gate);
    delete answers[`crit_${item.gate}`];
  } else if (item.question_id.startsWith('crit_')) {
    if (answers[item.question_id]?.values) delete answers[item.question_id].values[item.field_key];
  } else delete answers[item.question_id];
  return answers;
}

// A question the AI fully answered needs no second look on the compact page; a card with blanks stays, prefilled.
export function settledByIntake(q, answers, items) {
  if (q.id === 'work_types') return false;
  if (q.kind === 'criterion') {
    if (!items.some(i => i.question_id === q.id)) return false;
    const values = answers[q.id]?.values || {};
    return q.fields.every(f => values[f.key] !== undefined && values[f.key] !== null);
  }
  const item = items.find(i => i.question_id === q.id && i.kind !== 'tick');
  return Boolean(item) && answers[q.id] !== undefined && String(answers[q.id]) === String(item.value);
}

export class QuickFlow {
  constructor({host, toolbar, api, notify, onError, onOpenDetail}) {
    Object.assign(this, {host, api, notify, onError, onOpenDetail});
    this.toolbar = toolbar;
    toolbar?.addEventListener('click', event => this.click(event));
    this.drafts=localDrafts();
    this.intake = new AdaptiveIntake({api, notify,drafts:this.drafts, changed: () => { if (document.activeElement?.dataset.intakeValue) { const status = this.host.querySelector('.intake-save'); if (status) status.textContent = this.intake.saveStatus(); this.keepDraft(); } else this.render(); }});
    this.reset();
    this.step = 'home';
    host.addEventListener('click', event => this.click(event));
    host.addEventListener('input', event => this.input(event));
    host.addEventListener('change', event => this.input(event));
    host.addEventListener('cancel', event => { if (event.target.matches('[data-intake-dialog]')) { event.preventDefault(); this.intake.dialogOpen=false; this.render(); } }, true);
    host.addEventListener('toggle', event => {
      if (event.target.isConnected && event.target.matches('[data-ai-editor]')) this.aiEditorOpen = event.target.open;
    }, true);
    host.addEventListener('dragover', event => { if (event.target.closest('[data-drop]')) event.preventDefault(); });
    host.addEventListener('drop', event => this.drop(event));
    // The re-rendered page would otherwise close the "later" section after every answer.
    host.addEventListener('toggle', event => { if (event.target.classList?.contains('quick-later')) this.laterOpen = event.target.open; }, true);
    document.addEventListener('keydown', event => {
      if ((this.step === 'questions' || this.intake.dialogOpen) && (event.ctrlKey || event.metaKey) && event.key === 'Enter') {
        const dialogActions=document.activeElement?.matches('[data-intake-reply]')?['adaptive-next']:['intake-group-save','intake-pair-save','adaptive-next'];
        const next = this.intake.dialogOpen ? dialogActions.map(action=>host.querySelector(`[data-intake-dialog] [data-quick="${action}"]`)).find(Boolean) : host.querySelector('[data-quick="next"]');
        if (next && !next.disabled) { event.preventDefault(); next.click(); }
      }
    });
  }

  reset({preserveActivity=false}={}) {
    if(!preserveActivity) { clearInterval(this.busyTimer); this.busyTimer=null; this.busyStartedAt=null; }
    this.photoCropAbort?.abort();this.photoOperation=null;
    this.intake?.reset();
    Object.assign(this, {step: 'start', busy: preserveActivity?this.busy:false, survey: null, task: null, photos: {}, preview: null, stale: true, answers: {}, group: 0,
      result: null, exported: null, baseline: null, comparison: null, reopened: false, saved: null, review: {reviewer: '', note: ''}, draftId:null,aiDraft: null, aiEditorOpen: false, confirmDelete: null, ai: null, intakeText: '', laterOpen: false, excelPreview: null, excelTab: 0, selectedPhotoView: 'LEFT', overview: null});
  }

  async open() { if (this.step === 'home') await this.loadHome(); else this.render(); }

  async run(label, action) {
    if (this.busy) return;
    this.busy = label || true; this.busyStartedAt=Date.now(); this.render();
    const busyTimer=setInterval(()=>{if(this.busyTimer===busyTimer&&this.busy)updateActivity(this.host,Math.floor((Date.now()-this.busyStartedAt)/1000));},1000);
    this.busyTimer=busyTimer;
    try { await action(); } catch (error) { this.onError(error); }
    finally { clearInterval(busyTimer); if(this.busyTimer===busyTimer) { this.busyTimer=null; this.busyStartedAt=null; this.busy = false; this.render(); } }
  }

  // ================= home
  async saveWorkspace(announce = true) {
    if (this.busy || this.photoOperation || this.step === 'home') return false;
    let saved = false;
    await this.run('작성 중인 내용을 임시 저장하고 있어요…', async () => {
      await this.intake.flush();
      if (this.task) {
        // Photo registration can advance the task revision without refreshing this screen's DTO.
        const fresh = (await this.api('get_task', {task_id: this.task.task_id})).task;
        if (fresh.created_at !== this.task.created_at || fresh.survey_id !== this.survey?.survey_id)
          throw Error('저장 대상이 삭제되었거나 교체됐어요. 현재 기록을 확인해 주세요.');
        this.task = fresh;
      }
      writeWorkspaceDraft(captureWorkspace(this));
      // The old draft's discard/new path must never delete this checkpoint's survey.
      const old = readDraft();
      if (old && old.surveyId === this.survey?.survey_id) writeDraft(null);
      saved = true;
      if (announce) this.notify('현재 화면과 작성 중 내용을 이 PC에 임시 저장했어요.');
    });
    return saved;
  }

  async workspaceHome() {
    if (this.busy || this.photoOperation || this.step === 'home') return;
    if (!await this.saveWorkspace(false)) return;
    this.reset(); this.step = 'home'; await this.loadHome();
  }

  async workspaceBack() {
    if (this.busy || this.photoOperation || this.intake?.saving) return;
    const index = WORKSPACE_STEPS.indexOf(this.step);
    if (index <= 0) return this.workspaceHome();
    let target = WORKSPACE_STEPS[index - 1];
    if (['questions', 'provisional'].includes(target) && !this.preview) target = 'start';
    this.intake.dialogOpen = false;
    this.step = target; this.render(); window.scrollTo({top: 0});
  }

  async resumeWorkspace() {
    const draft = readWorkspaceDraft();
    if (!draft) return;
    await this.run('임시 저장한 화면을 불러오고 있어요…', async () => {
      let loaded;
      try { loaded = await loadWorkspace(draft, this.api); }
      catch (error) {
        if (!missingWorkspaceRecord(error)) throw error;
        this.workspaceUnavailable = JSON.stringify(draft);
        this.notify('이어 갈 기록이 삭제되었거나 현재 데이터에 없어 목록에서 제외했어요.');
        return;
      }
      // Restore display candidates locally. intake_session/quick_preview can run pose inference
      // or project inputs; neither belongs to reopening an explicitly saved UI checkpoint.
      const preview = draft.preview || null;
      const contract = draft.adaptive ? await this.intake.loadContract() : null;
      if (draft.adaptive && draft.intake.state?.contract?.version !== contract.version)
        throw Error('입력 화면 형식이 변경됐어요. 최신 기록을 열어 확인해 주세요. 임시 메모는 보관돼요.');
      const settings = this.settings;
      this.reset({preserveActivity: true});
      Object.assign(this, loaded, draft.ui, {settings, preview, busy: '임시 저장한 화면을 불러오고 있어요…', step: draft.step});
      if (draft.adaptive) {
        this.intake.state = {...draft.intake.state, task: this.task, contract};
        this.intake.questions = draft.intake.questions;
      }
      Object.assign(this.intake, {text: draft.intake.text, dialogOpen: draft.intake.dialogOpen,
        editing: draft.intake.editing, writingFor: draft.intake.writingFor, focusPair: draft.intake.focusPair,
        formStage: draft.intake.formStage||0, formValues: new Map(draft.intake.formValues||[]), values: new Map(draft.intake.values), ...(this.intake.pairValues ? {pairValues: new Map(draft.intake.pairValues)} : {})});
      if (this.baseline && this.result) await this.compare();
      if (draft.step === 'excel') {
        const args = {survey_id: this.survey.survey_id, analysis_ids: [this.result.analysis_id], comparisons: this.comparison ? [this.comparison.spec] : []};
        [this.overview, this.excelPreview] = await Promise.all([this.api('preview_excel', args), this.api('preview_excel_sheets', args)]);
      }
    });
  }

  async loadHome() {
    await this.run('', async () => {
      await initializeDrafts();
      this.surveys = await this.api('list_surveys');
      const checkpoint = readWorkspaceDraft();
      this.workspaceUnavailable = null;
      if (checkpoint?.task) {
        try {
          if (!await workspaceTargetAvailable(checkpoint, this.api)) this.workspaceUnavailable = JSON.stringify(checkpoint);
        } catch { /* Keep the checkpoint available for retry after a transient service failure. */ }
      }
      this.settings = await this.api('get_settings');
      await this.intake.loadContract();
      this.step = 'home';
    });
  }

  async openExisting(surveyId) {
    await this.run('결과를 불러오고 있어요…', async () => {
      const survey = await this.api('get_survey', {survey_id: surveyId});
      const tasks = await this.api('list_tasks', {survey_id: surveyId});
      const task = tasks[0];
      if (!task) throw new Error('이 조사에 작업이 없어요.');
      if(!task.latest_analysis_id){const saved=this.quickDrafts().find(d=>d.taskId===task.task_id&&d.createdAt===survey.created_at);await this.restoreDraft(saved||{id:newDraftId(),surveyId,createdAt:survey.created_at,taskId:task.task_id,taskCreatedAt:task.created_at,adaptive:this.intake.hasSession(task),step:'questions'});return;}
      const bundle = await this.api('get_task_result', {task_id: task.task_id});
      const full = await this.api('get_task', {task_id: task.task_id});
      const photos = {};
      for (const slot of full.task.capture.slots) {
        if (slot.photo_id == null) continue;
        const photo = full.photos.find(p => p.photo_id === slot.photo_id);
        const view = VIEWS.find(item => item.id === slot.label || VIEW_LABEL[item.id] === slot.label)?.id || (photos.LEFT ? 'RIGHT' : 'LEFT');
        if (photo && !photos[view]) photos[view] = {photo, image: await this.api('get_photo_preview', {photo})};
      }
      const settings = this.settings || await this.api('get_settings');
      this.reset({preserveActivity:true});
      Object.assign(this, {survey, task, photos, result: bundle.analysis, reopened: true, stale: false, step: 'result', settings});
      if (this.intake.hasSession(task)) { const restored = await this.intake.open(task.task_id); this.preview = restored.preview; this.task = restored.task;this.result=await this.api('get_analysis',{analysis_id:bundle.analysis.analysis_id}); }
    });
  }

  async deleteSurvey(id) {
    if (this.confirmDelete !== id) { this.confirmDelete = id; return this.render(); }
    this.confirmDelete = null;
    await this.run('삭제하고 있어요…', async () => {
      const checkpoint = readWorkspaceDraft();
      const target = checkpoint?.survey?.id === id ? await this.api('get_survey', {survey_id: id}) : null;
      await this.api('delete_survey', {survey_id: id});
      if (target) clearWorkspaceDraftForSurvey(target);
      for(const draft of this.quickDrafts().filter(item=>item.surveyId===id&&item.createdAt===target?.created_at))this.drafts.remove('quick',draft.id);
      const old = readDraft();
      if (target && old?.surveyId === id && old.createdAt === target.created_at) writeDraft(null);
      this.surveys = await this.api('list_surveys');
      this.notify('기록을 삭제했어요. 원본 사진과 Excel 파일은 그대로예요.');
    });
  }

  // ================= step 1: photos (any of three views, each replaceable)
  async ensureTask(isCurrent=()=>true) {
    if (this.task) return;
    const survey = await this.api('create_survey', {draft: {survey_type: 'REGULAR', survey_date: today(), title: `빠른 분석 ${today()}`, investigator: '', department: '', process: '', occasional_reason: ''}});
    if(!isCurrent())return;
    this.survey=survey;
    const task = await this.api('create_task', {survey_id: survey.survey_id, draft: {task_name: '사진 분석 작업', input_template: 'GENERAL', conditions: {}}});
    if(isCurrent())this.task=task;
  }

  async setPhoto(view, path) {
    if (!path || this.busy) return;
    const owner={step:this.step},abort=new AbortController();
    this.photoOperation=owner;this.photoCropAbort=abort;
    const current=()=>this.photoOperation===owner&&this.step===owner.step;
    this.busy='사진을 불러오고 있어요…';this.render();
    try {
      const source=await this.api('preview_photo_file',{file_path:path});
      if(!current())return;
      const crop=await (this.choosePhotoCrop||selectPhotoCrop)(source,{signal:abort.signal});
      if(!crop||!current())return;
      this.busy='선택 영역을 등록하고 있어요…';this.render();
      await this.ensureTask(current);
      if(!current())return;
      const task=this.task;
      const photo=await this.api('import_cropped_photo',{task_id:task.task_id,task_created_at:task.created_at,
        file_path:path,source_sha256:source.source_sha256,crop});
      if(!current()||this.task!==task)return;
      const image=await this.api('get_photo_preview',{photo});
      if(!current()||this.task!==task)return;
      const old = this.photos[view];
      this.photos[view] = {photo,image};
      this.stale = true;
      if (old) await this.discard(old.photo);
    } catch(error){if(current())this.onError(error);}
    finally{
      abort.abort();
      if(this.photoOperation===owner){this.photoOperation=null;this.photoCropAbort=null;this.busy=false;this.render();}
    }
  }

  async removePhoto(view) {
    const old = this.photos[view];
    if (!old) return;
    delete this.photos[view]; this.stale = true;
    await this.run('사진을 빼고 있어요…', () => this.discard(old.photo));
  }

  async discard(photo) {
    // A photo already used by a saved analysis stays in the record; only unused ones are removed.
    if (!this.result && !this.baseline) await this.api('delete_photo', {photo_id: photo.photo_id}).catch(() => {});
  }

  async analyze() {
    if (!Object.keys(this.photos).length && !this.intakeText.trim()) return;
    if (!this.stale && this.preview && this.intake?.state) { this.step = 'provisional'; return this.render(); }
    await this.run('사진을 분석하고 있어요…', async () => {
      await this.ensureTask();
      const views = Object.fromEntries(Object.entries(this.photos).map(([view, item]) => [view, item.photo.photo_id]));
      let state = await this.intake.open(this.task.task_id, views);
      if (!state) return;
      await this.ensureAiOn(); state = await this.intake.turn(this.intakeText);
      if (!state) return;
      this.task = state.task; this.preview = state.preview;
      this.stale = false; this.step = 'provisional'; this.group = 0;
      this.intake.dialogOpen=Boolean(state.questions.length || state.reason);
    });
  }

  // ================= step 3: questions
  visible(q) {
    if (!q.show_if) return true;
    return Object.entries(q.show_if).every(([id, values]) => {
      const answer = this.answers[id];
      return Array.isArray(answer) ? values.some(value => answer.includes(value)) : values.includes(answer);
    });
  }
  groups() {
    const names = [];
    for (const q of this.preview.questions) if (this.visible(q) && !names.includes(q.group)) names.push(q.group);
    return names.map(name => ({name, questions: this.preview.questions.filter(q => q.group === name && this.visible(q))}));
  }
  answered(q) {
    const a = this.answers[q.id];
    if (q.kind === 'text') return !q.required || String(a ?? '').trim() !== '';
    if (q.kind === 'criterion') return q.implicit ? true : a?.present !== undefined;
    return Object.prototype.hasOwnProperty.call(this.answers, q.id);
  }
  numberOk(q, value) { return value === null || value === undefined || (value >= 0 && (!q.maximum || value <= q.maximum)); }
  groupReady(group) {
    return group.questions.every(q => {
      if (!this.answered(q)) return false;
      if (q.kind === 'number') return this.numberOk(q, this.answers[q.id]);
      if (q.kind === 'criterion') return q.fields.every(f => f.type !== 'number' || this.numberOk(f, this.answers[q.id]?.values?.[f.key]));
      return true;
    });
  }

  // ================= step 4: write confirmed answers, run the regular engine
  primaryView() { return ['LEFT', 'RIGHT', 'FRONT'].find(view => this.photos[view]); }

  // What MoveNet estimated for a posture question (a low-confidence value shown pre-selected), so the saved note says
  // whether the person confirmed the estimate or chose something else.
  estimateNote(q, value) {
    const t = q.target;
    if (t.type !== 'manual' || q.suggested == null) return '';
    const guess = (this.preview.measured || []).find(m => m.low_confidence && m.field === t.field && (t.scope === 'BOTH' ? m.scope !== 'COMMON' : m.scope === t.scope));
    if (!guess) return '';
    const degrees = guess.angles.map(x => `${x.value_deg}°`).join('/');
    return String(value) === String(q.suggested) ? ` · 사진 추정 ${degrees}(신뢰도 낮음)를 그대로 확인` : ` · 사진 추정 ${degrees}(신뢰도 낮음)와 다르게 선택`;
  }

  // Work types the person ticked decide which criteria are asked about; the ones left unticked are recorded as "not applicable".
  applyCriteria(input) {
    const a = this.answers, types = Array.isArray(a.work_types) ? a.work_types : null;
    if (types) {
      const note = evidence('빠른 분석: "이 작업의 특징"에서 선택하지 않음(해당 없음)');
      for (let n = 1; n <= 11; n++) {
        if (types.includes(GATES[n])) continue;
        const criterion = input.legal.criteria[n - 1];
        criterion.condition_present = 'NO'; criterion.evidence = note;
        if (n >= 6) { criterion.rows = []; criterion.rows_complete = 'YES'; }
      }
    }
    for (const q of this.preview.questions) {
      if (q.kind !== 'criterion' || !this.visible(q)) continue;
      const values = a[q.id]?.values || {}, note = `빠른 분석 질문: ${q.text}`;
      const value = field => values[field.key] === undefined ? (field.type === 'truth' ? 'UNKNOWN' : null) : values[field.key];
      if (q.mode === 'lift') {
        const shared = {};
        for (const field of q.fields) shared[field.to.lift] = value(field);
        const pick = keys => Object.fromEntries(keys.map(key => [key, shared[key] ?? null]));
        const shapes = {8: pick(['load_mass_kg', 'lift_count_day']), 9: pick(['load_mass_kg', 'below_knee_count_day', 'above_shoulder_count_day', 'extended_arm_count_day', 'union_count_day']), 10: pick(['load_mass_kg', 'lift_rate_min', 'minutes'])};
        for (const n of q.criteria) {
          const criterion = input.legal.criteria[n - 1];
          criterion.condition_present = 'YES'; criterion.evidence = evidence(note);
          criterion.rows = [{row_id: 'quick-1', label: '빠른 분석 입력', evidence: evidence(note), ...shapes[n]}]; criterion.rows_complete = 'YES';
        }
        continue;
      }
      const criterion = input.legal.criteria[q.criterion - 1];
      criterion.condition_present = 'YES'; criterion.evidence = evidence(note);
      const row = {row_id: 'quick-1', label: '빠른 분석 입력', evidence: evidence(note)};
      for (const field of q.fields) {
        const stored = value(field);
        if (field.to.exposure) {
          const slot = input.legal.exposures.find(x => x.condition_code === field.to.exposure);
          slot.minutes = stored; slot.evidence = evidence(`${note} · ${field.label}`);
        } else if (field.to.criterion) criterion[field.to.criterion] = stored === null ? 'UNKNOWN' : stored;
        else row[field.to.row] = stored;
      }
      if (q.mode === 'row') { criterion.rows = [row]; criterion.rows_complete = 'YES'; }
    }
  }

  build(task) {
    const a = this.answers, input = Object.fromEntries(TASK_KEYS.map(key => [key, structuredClone(task[key])]));
    const usable = a.context === 'YES', known = usable ? 'YES' : 'UNKNOWN';
    const load = a.load === 'UNLOADED' ? 0 : a.load === 'MEASURED' ? a.load_kg : null;
    const primary = this.primaryView(), primaryPhoto = this.photos[primary].photo.photo_id;
    const observation = () => ({
      load_state: a.load === 'MEASURED' && load == null ? 'UNKNOWN' : (a.load ?? 'UNKNOWN'), measured_load_kg: a.load === 'MEASURED' ? load : null,
      single_person: known, full_frame: known, normal_work: known, evidence: evidence('빠른 분석: 사진 확인 질문 답변')
    });
    const order = ['LEFT', 'RIGHT', 'FRONT'].filter(view => this.photos[view]);
    input.capture.slots = order.map((view, i) => ({
      slot_no: i + 1, photo_id: this.photos[view].photo.photo_id, label: VIEW_LABEL[view], analysis_target: view === primary,
      camera_side: view === 'FRONT' ? 'FRONT' : !usable ? null : (this.preview.views?.[view]?.guess?.camera_side || view), forward_direction: view === 'FRONT' || !usable ? null : a[`view_${view}`] ?? null,
      side_view_verified: view === 'FRONT' ? 'NO' : known, observation: observation()
    }));
    input.task_name = String(a.task_name ?? '').trim() || '사진 분석 작업';
    input.input_template = a.template || 'GENERAL';
    const manual = new Map(), put = (scope, field, value, source, note, evidenceSource) => {
      if (value === null || value === undefined) return;
      for (const side of scope === 'BOTH' ? ['LEFT', 'RIGHT'] : [scope]) {
        manual.set(`${side}.${field}`, {slot_no: 1, photo_id: primaryPhoto, scope: side, field, value, source, evidence: evidence(note, evidenceSource || source)});
      }
    };
    if (usable) for (const m of this.preview.measured.filter(item => !item.low_confidence)) {
      const note = `빠른 분석: ${VIEW_LABEL[m.view]} ${m.label} ${m.angles.map(x => x.value_deg + '°').join('/')}`;
      if (m.view === primary) put(m.scope, m.field, m.value, 'AUTO_ACCEPTED', JSON.stringify({angles: m.angles, quick_preview: true}), 'OTHER');
      else put(m.scope, m.field, m.value, 'DIRECT_OBSERVATION', note + ' (사용자 확인)', 'DIRECT_OBSERVATION');
    }
    for (const q of this.preview.questions) {
      if (!this.visible(q) || !this.answered(q)) continue;
      const value = a[q.id], t = q.target;
      if (t.type === 'manual' && value !== 'UNKNOWN') put(t.scope, t.field, t.field === 'coupling' && load === 0 ? 'NOT_APPLICABLE' : value, 'INTERVIEW', `빠른 분석 질문: ${q.text}${this.estimateNote(q, value)}`);
      if (t.type === 'flags') for (const item of q.items) for (const set of item.sets) {
        put(set.scope, set.field, value.includes(item.key) ? set.checked : set.unchecked, 'INTERVIEW', `빠른 분석 체크: ${item.label}${item.suggested ? ` (${item.evidence})` : ''}`);
      }
      if (t.type === 'conditions') input.conditions[t.field] = value === 'UNKNOWN' ? (t.field === 'one_off' ? 'UNKNOWN' : null) : value;
    }
    if (load === 0) put('BOTH', 'coupling', 'NOT_APPLICABLE', 'INTERVIEW', '빠른 분석: 든 물건 없음');
    input.manual = [...manual.values()];
    this.applyCriteria(input);
    input.analysis_scope = {judgment: true, pose: true, tags: true, reba: true};
    return input;
  }

  surveyDraft(survey) {
    const a = this.answers, draft = Object.fromEntries(SURVEY_KEYS.map(key => [key, structuredClone(survey[key])]));
    const name = String(a.task_name ?? '').trim();
    draft.title = name ? `${name} (${draft.survey_date || today()})` : draft.title;
    for (const key of ['investigator', 'department', 'process']) if (String(a[key] ?? '').trim()) draft[key] = String(a[key]).trim();
    for (const key of ['equipment', 'workload', 'speed', 'work_pattern']) {
      const value = a[`situation_${key}`];
      if (value) draft.workplace_situation[`${key}_status`] = value;
    }
    if (a.participation) {
      draft.participation.status = a.participation;
      if (a.participation === 'YES' && a.participation_method) draft.participation.method = a.participation_method;
    }
    if (a.symptom) draft.symptom_survey.method = a.symptom;
    return draft;
  }

  async finish() {
    this.intake.dialogOpen=false;
    await this.run('최종 결과를 계산하고 있어요…', async () => {
      if (this.intake?.state) {
        await this.intake.flush();
        this.task = (await this.api('get_task', {task_id: this.task.task_id})).task;
        const handle = await this.api('start_analysis', {task_id: this.task.task_id});
        let analysis;
        for (let i = 0; i < 300; i++) {
          analysis = await this.api('get_analysis', {analysis_id: handle.analysis_id});
          if (analysis.status !== 'RUNNING') break;
          await new Promise(resolve => setTimeout(resolve, 200));
        }
        if (analysis.status === 'RUNNING') throw Error('분석이 계속되고 있어요. 잠시 뒤 다시 열어 주세요.');
        this.result = analysis; this.survey = await this.api('get_survey', {survey_id: this.survey.survey_id});
        this.settings = this.settings || await this.api('get_settings');
      this.exported = null; this.step = 'result'; this.clearCurrentDraft();
        if (this.baseline && this.baseline.analysis_id !== analysis.analysis_id) await this.compare();
        return;
      }
      await this.api('update_survey', {survey_id: this.survey.survey_id, draft: this.surveyDraft(await this.api('get_survey', {survey_id: this.survey.survey_id}))});
      // Save photos first: a changed photo row drops that row's manual values, so answers go in a second save.
      const {task} = await this.api('get_task', {task_id: this.task.task_id});
      const input = this.build(task), answers = input.manual;
      const placed = await this.api('save_task_input', {task_id: task.task_id, input: {...input, manual: []}, expected_revision: task.input_revision});
      await this.api('save_task_input', {task_id: task.task_id, input: {...input, manual: answers}, expected_revision: placed.input_revision});
      const handle = await this.api('start_analysis', {task_id: task.task_id});
      let analysis;
      for (let i = 0; i < 300; i++) {
        analysis = await this.api('get_analysis', {analysis_id: handle.analysis_id});
        if (analysis.status !== 'RUNNING') break;
        await new Promise(resolve => setTimeout(resolve, 200));
      }
      if (analysis.status === 'RUNNING') throw new Error('분석이 오래 걸려요. 잠시 뒤 다시 열어 주세요.');
      this.survey = await this.api('get_survey', {survey_id: this.survey.survey_id});
      this.settings = this.settings || await this.api('get_settings');
      this.result = analysis; this.exported = null; this.comparison = null; this.step = 'result';
      this.clearCurrentDraft();
      if (this.baseline && this.baseline.analysis_id !== analysis.analysis_id) await this.compare();
    });
  }

  async compare() {
    const spec = {before_analysis_id: this.baseline.analysis_id, after_analysis_id: this.result.analysis_id, note: '개선 전후 빠른 비교'};
    const overview = await this.api('preview_excel', {survey_id: this.survey.survey_id, analysis_ids: [], comparisons: [spec]});
    this.comparison = overview.comparisons[0] || null;
  }

  async improveAgain() {
    await this.run('이전 답변을 불러오고 있어요…', async () => {
      if (this.reopened) this.saved = {task: (await this.api('get_task', {task_id: this.task.task_id})).task, survey: await this.api('get_survey', {survey_id: this.survey.survey_id})};
      this.baseline = this.result; this.comparison = null; this.exported = null; this.reopened = false;
      this.step = 'start'; this.preview = null; this.stale = true; this.result = null; this.excelPreview = null; this.overview = null; this.review = {reviewer: this.review.reviewer, note: ''};
      this.notify('개선 후 사진으로 바꿔 넣고 "분석 시작"을 눌러 주세요. 이전 답변은 그대로 유지돼요.');
    });
  }

  // ================= step 5: review, AI explanation, Excel
  openReview() { this.step = 'review'; this.render(); window.scrollTo({top: 0}); }

  // The check list and the preview are built from the same stored results the Excel file will use.
  async openExcel() {
    await this.run('Excel 미리보기를 만들고 있어요…', async () => {
      const comparisons = this.baseline && this.comparison ? [this.comparison.spec] : [];
      const args = {survey_id: this.survey.survey_id, analysis_ids: [this.result.analysis_id], comparisons};
      [this.overview, this.excelPreview] = await Promise.all([this.api('preview_excel', args), this.api('preview_excel_sheets', args)]);
      this.excelTab = 0; this.step = 'excel';
    });
    window.scrollTo({top: 0});
  }

  // From the check list back to the question that fills the gap. Only possible while the questions of this session exist.
  jumpTo(questionId) {
    if (this.intake?.state) { this.intake.questions = this.intake?.state.questions; this.intake.dialogOpen=true; this.step = 'questions'; this.render(); return; }
    if (this.ai) { this.step = 'questions'; this.render(); window.scrollTo({top: 0}); return; }
    const groups = this.groups(), index = groups.findIndex(group => group.questions.some(q => q.id === questionId));
    if (index < 0) return;
    this.step = 'questions'; this.group = index; this.render(); window.scrollTo({top: 0});
  }

  followupTarget(message) {
    const table = [[/참여/, 'participation'], [/증상/, 'symptom'], [/설비/, 'situation_equipment'], [/작업량/, 'situation_workload'], [/속도/, 'situation_speed'], [/업무형태|업무 형태/, 'situation_work_pattern']];
    return table.find(([pattern]) => pattern.test(message))?.[1] || null;
  }

  checklistPanel() {
    const overview = this.overview, item = overview?.tasks?.[0];
    if (!item) return '';
    const canJump = Boolean(this.preview);
    const conclusions = (this.result.judgment?.judgments || []).filter(j => j.investigator?.status).length;
    const cardFor = n => { const id = `crit_${GATES[n]}`, shown = this.preview?.questions.find(q => q.id === id && this.visible(q)); return shown ? id : 'work_types'; };
    const jump = id => canJump && id ? `<button type="button" data-jump="${esc(id)}">입력하러 가기</button>` : '';
    const lines = [];
    for (const message of overview.survey_followups || []) lines.push(`<li><span>${esc(message)}</span>${jump(this.followupTarget(message))}</li>`);
    for (const next of item.next_inputs || []) {
      if (next.kind !== 'MISSING_INPUT' && next.kind !== 'REVIEW_REQUIRED') continue;
      lines.push(`<li><span>${esc(next.message)}</span>${jump(next.criterion_no ? cardFor(next.criterion_no) : null)}</li>`);
    }
    const counts = item.counts || {};
    return `<section class="panel quick-check ${lines.length ? 'has-gaps' : 'clean'}"><h3>Excel 만들기 전 확인</h3>
      <p class="quick-note">입력 필요 기준 <b>${counts.needs_input_count ?? 0}</b>개 · 검토 필요 <b>${counts.needs_review_count ?? 0}</b>개 · 조사자 결론 <b>${conclusions}</b>/11개</p>
      ${lines.length ? `<ul class="quick-check-list">${lines.join('')}</ul>${canJump ? '<p class="quick-note">답을 고치면 마지막 묶음에서 "최종 결과 계산"을 다시 눌러야 반영돼요.</p>' : '<p class="quick-note">다시 연 결과라 질문으로 바로 돌아갈 수 없어요. "개선 후 사진으로 다시 비교"에서 이전 답을 불러와 고칠 수 있어요.</p>'}`
      : '<p class="quick-ok">빠진 항목이 없어요. 그대로 Excel로 저장해도 돼요.</p>'}</section>`;
  }

  async conclude(number, status) {
    await this.run('결론을 저장하고 있어요…', async () => {
      const current = this.result.judgment.judgments.find(j => j.criterion_no === number)?.investigator?.status ?? null;
      const next = current === status ? null : status;
      const conclusion = {criterion_no: number, status: next, reason: null, evidence: evidence('빠른 분석 검토', 'DIRECT_OBSERVATION'), reviewer: this.review.reviewer || null, reviewed_at: new Date().toISOString()};
      this.result = await this.api('set_investigator_conclusion', {analysis_id: this.result.analysis_id, conclusion});
    });
  }

  async markReviewed(reviewed) {
    await this.run('검토 표시를 저장하고 있어요…', async () => {
      const survey = await this.api('get_survey', {survey_id: this.survey.survey_id});
      const tasks = await this.api('list_tasks', {survey_id: this.survey.survey_id});
      const ids = tasks.map(t => t.task_id === this.task.task_id ? this.result.analysis_id : t.latest_analysis_id).filter(Boolean);
      const review = {reviewed, reviewed_analysis_ids: ids, reviewed_metadata_revision: survey.metadata_revision, reviewer: this.review.reviewer || survey.investigator || null, reviewed_at: new Date().toISOString(), note: this.review.note || null};
      this.survey = await this.api('set_survey_review', {survey_id: survey.survey_id, review});
      this.notify(reviewed ? '검토 완료로 표시했어요. 계산 완전성과는 별개예요.' : '검토 표시를 해제했어요.');
    });
  }

  // Pressing "AI가 정리하기" is the opt-in; only the typed sentence is sent.
  async ensureAiOn() {
    const current = this.settings || await this.api('get_settings');
    if (current.gpt_enabled && current.gpt_model) return;
    const settings = enabledAiSettings(await this.api('get_settings'));
    await this.api('update_settings', {settings:persistedSettings(settings)});
    this.settings = await this.api('get_settings');
  }

  undoIntake() {
    if (!this.ai) return;
    for (const item of this.ai.items) dropIntakeItem(this.answers, item);
    this.ai = null;
  }

  async interpret() {
    const text = this.intakeText.trim();
    if (!text || !this.preview) return;
    await this.run('AI가 문장을 칸에 옮기고 있어요…', async () => {
      await this.ensureAiOn();
      if (this.intake?.state) {
        const state = await this.intake.turn(text);
        if (state) { this.task = state.task; this.preview = state.preview; this.notify('작업 설명과 사진에서 파악한 정보를 저장했어요.'); }
        return;
      }
      const result = await this.api('quick_interpret', {text});
      if (!result.items.length) { this.onError(new Error(INTAKE_REASON[result.reason] || INTAKE_REASON.API_ERROR)); return; }
      this.undoIntake();
      applyIntake(this.answers, this.preview.questions, result.items);
      this.ai = {items: result.items, dropped: result.dropped || []};
      this.notify(`AI가 ${result.items.length}개 칸을 채웠어요. 틀린 것은 "빼기"를 눌러 주세요.`);
    });
  }

  clearIntake() { this.undoIntake(); this.intakeText = ''; this.render(); }

  dropIntake(target) {
    const item = this.ai?.items.find(i => i.target === target);
    if (!item) return;
    dropIntakeItem(this.answers, item);
    this.ai.items = this.ai.items.filter(i => i !== item);
    if (!this.ai.items.length) this.ai = null;
    this.render();
  }

  async enableAi() {
    await this.run('AI 설명을 켜고 있어요…', async () => {
      const settings = enabledAiSettings(await this.api('get_settings'));
      await this.api('update_settings', {settings:persistedSettings(settings)});
      this.settings = await this.api('get_settings');
    });
  }

  async refreshResult() { this.result = await this.api('get_analysis', {analysis_id: this.result.analysis_id}); }

  async generateAi() {
    await this.run('AI가 설명을 쓰고 있어요…', async () => {
      const current = this.settings || await this.api('get_settings');
      if (!(current.gpt_enabled && current.gpt_model)) {
        // Pressing the button is the opt-in (only the numeric summary is ever sent). Without a key this still yields an appliable plain explanation.
        const settings = enabledAiSettings(await this.api('get_settings'));
        await this.api('update_settings', {settings:persistedSettings(settings)});
        this.settings = await this.api('get_settings');
      }
      await this.api('generate_ai_text', {analysis_id: this.result.analysis_id, purpose: 'TASK_EXPLANATION'});
      await this.refreshResult(); this.aiDraft = null; this.aiEditorOpen = false;
    });
  }

  activeAi() { return (this.result.ai || []).filter(x => x.purpose === 'TASK_EXPLANATION').at(-1); }

  async applyAi(useEdited) {
    const ai = this.activeAi();
    if (!ai) return;
    const edited = this.editedExplanation(ai);
    if (useEdited && !edited.trim()) return this.onError(new Error('수정한 설명을 입력한 뒤 적용해 주세요.'));
    await this.run('설명을 적용하고 있어요…', async () => {
      if (useEdited) await this.api('edit_ai_text', {analysis_id: this.result.analysis_id, text_id: ai.text_id, text: edited});
      if(useEdited)clearExplanationDraft(this.result,ai,edited,this.drafts);
      await this.api('apply_ai_text', {analysis_id: this.result.analysis_id, text_id: ai.text_id, use_edited: useEdited});
      await this.refreshResult(); this.aiDraft = null; this.aiEditorOpen = false;
      this.notify('설명을 적용했어요. 계산 결과는 바뀌지 않아요.');
    });
  }

  async exportExcel() {
    if (!window.loco?.choose_export_destination) return this.onError(new Error('Excel 저장은 앱에서만 할 수 있어요.'));
    const destination = await window.loco.choose_export_destination();
    if (!destination) return;
    await this.run('Excel을 만들고 있어요…', async () => {
      const comparisons = this.baseline && this.comparison ? [this.comparison.spec] : [];
      this.exported = await this.api('export_excel', {survey_id: this.survey.survey_id, spec: {destination, analysis_ids: [this.result.analysis_id], include_representative: true, comparisons}});
      this.notify(`Excel을 저장했어요: ${this.exported.file_path}`);
    });
  }

  // ================= events
  click(event) {
    const b = event.target.closest('button');
    if (!b || b.disabled) return;
    const d = b.dataset;
    if (d.choose) {
      if (!window.loco?.choose_photo_paths) return this.onError(new Error('사진 선택은 앱에서만 할 수 있어요.'));
      window.loco.choose_photo_paths().then(paths => this.setPhoto(d.choose, paths?.[0])).catch(error => this.onError(error));
    }
    else if (d.remove) this.removePhoto(d.remove);
    else if (d.open) this.openExisting(Number(d.open));
    else if (d.del) this.deleteSurvey(Number(d.del));
    else if (d.crit) this.critClick(d);
    else if (d.concl) this.conclude(Number(d.concl), d.status);
    else if (d.quick === 'new') this.startNew();
    else if (d.quick === 'workspace-save') this.saveWorkspace();
    else if (d.quick === 'workspace-back') this.workspaceBack();
    else if (d.quick === 'workspace-top') window.scrollTo({top: 0, behavior: window.matchMedia?.('(prefers-reduced-motion: reduce)').matches ? 'instant' : 'smooth'});
    else if (d.quick === 'workspace-resume') this.resumeWorkspace();
    else if (d.quick === 'resume') this.resumeDraft(d.draft);
    else if (d.quick === 'discard-draft') this.run('선택한 초안을 버리고 있어요…',()=>this.discardDraft(d.draft));
    else if (d.quick === 'home' || d.quick === 'home-bar') this.workspaceHome();
    else if (d.quick === 'analyze') this.analyze();
    else if (d.quick === 'photos') { this.step = 'start'; this.render(); }
    else if (d.quick === 'questions') { this.step = 'questions'; this.group = 0; if(this.intake.state) { this.intake.continueQuestions(); this.intake.dialogOpen=true; } this.render(); }
    else if (d.quick === 'intake-close') { this.intake.dialogOpen=false; this.render(); }
    else if (d.quick === 'intake-form-back') { this.intake.formStage=0; this.render(); }
    else if (d.quick === 'intake-form-next') this.saveIntakeForm();
    else if (d.quick === 'intake-continue') { this.intake.continueQuestions(); this.render(); }
    else if (d.quick === 'prev') { if (this.ai) this.step = 'provisional'; else this.group = Math.max(0, this.group - 1); this.render(); window.scrollTo({top: 0}); }
    else if (d.quick === 'next') {
      if (this.intake?.state) this.finish();
      else if (!this.ai && this.group < this.groups().length - 1) { this.group++; this.render(); window.scrollTo({top: 0}); } else this.finish();
    }
    else if (d.quick === 'intake-write') { this.intake.writingFor=this.intake.questions[0]?.identity; this.intake.focusPair=null; this.render(); }
    else if (d.intakePairPick) {
      const field=this.intake.field(d.intakePairPick);
      if(field) { this.intake.pairValues.set(field.identity,this.intake.parseValue(field.identity,d.value)); this.intake.focusPair=field.identity; this.render(); }
    }
    else if (d.quick === 'intake-group-save') {
      const answers=this.intake.selectedAnswers();
      if(answers.length) this.respondIntake('',answers);
    }
    else if (d.quick === 'intake-pair-save') {
      const q=this.intake.questions[0],group=q?.paired_question?[q,q.paired_question]:[];
      if(group.length===2&&group.every(field=>this.intake.pairValues.has(field.identity))) this.respondIntake('',group.map(field=>({target:field.target,condition:field.condition,value:this.intake.pairValues.get(field.identity)})));
    }
    else if (d.quick === 'adaptive-next') this.respondIntake();
    else if (d.intakePick) {
      const field=this.intake.field(d.intakePick);
      if(field) this.respondIntake('',[{target:field.target,condition:field.condition,value:this.intake.parseValue(d.intakePick,d.value)}]);
    }
    else if (d.intakeEdit) { this.intake.editing = this.intake.editing === d.intakeEdit ? null : d.intakeEdit; this.render(); }
    else if (d.intakeChoice) {
      const value = this.intake.parseValue(d.intakeChoice, d.value);
      this.intake.answer(d.intakeChoice, value).catch(error => { this.onError(error); this.render(); });
    }
    else if (d.quick === 'intake') this.interpret();
    else if (d.quick === 'intake-clear') this.clearIntake();
    else if (d.quickIntakeDrop) this.dropIntake(d.quickIntakeDrop);
    else if (d.quick === 'allno') this.allNo();
    else if (d.quick === 'review') this.openReview();
    else if (d.quick === 'preview') this.openExcel();
    else if (d.photoView && VIEWS.some(view => view.id === d.photoView) && this.photos[d.photoView]) {
      this.selectedPhotoView = d.photoView; this.render();
      this.host.querySelector(`[data-photo-view="${d.photoView}"]`)?.focus({preventScroll: true});
    }
    else if (d.quick === 'excel-tab') { this.excelTab = Number(d.tab); this.render(); }
    else if (d.jump) this.jumpTo(d.jump);
    else if (d.quick === 'result') { this.step = 'result'; this.render(); }
    else if (d.quick === 'reviewed') this.markReviewed(true);
    else if (d.quick === 'unreview') this.markReviewed(false);
    else if (d.quick === 'gen-ai') this.generateAi();
    else if (d.quick === 'apply-ai') this.applyAi(false);
    else if (d.quick === 'apply-edited') this.applyAi(true);
    else if (d.quick === 'excel') this.exportExcel();
    else if (d.quick === 'improve') this.improveAgain();
    else if (d.quick === 'detail') this.onOpenDetail({surveyId: this.survey?.survey_id, taskId: this.task?.task_id});
    else if (d.answer) {
      const q = this.preview.questions.find(x => x.id === d.answer);
      this.answers[q.id] = q.kind === 'number' ? (d.value === '' ? null : Number(d.value)) : q.choices.find(c => String(c.value) === d.value).value;
      this.render();
    }
  }

  critClick(d) {
    const [id, key] = d.crit.split('|'), card = this.answers[id] ||= {values: {}};
    card.values ||= {};
    if (d.chip !== undefined) card.values[key] = d.chip === '' ? null : Number(d.chip);
    else if (d.truth !== undefined) card.values[key] = d.truth;
    this.render();
  }

  async saveIntakeForm() {
    const invalid=this.host?.querySelector('[data-intake-form]:invalid');
    if(invalid) { invalid.reportValidity(); return; }
    let saved=false, last=this.intake.formStage===1;
    await this.run('입력한 내용을 저장하고 있어요…',async()=>{
      await this.intake.flush();
      const answers=this.intake.formAnswers();
      const text=this.intake.text.trim();
      if(text)await this.ensureAiOn();
      const state=answers.length||text?await this.intake.turn(text,answers):this.intake.state;
      if(!state||state.reason)return;
      this.task=state.task;this.preview=state.preview;
      for(const answer of answers)this.intake.formValues.delete(answer.target+'@'+answer.condition);
      if(!last)this.intake.formStage=1;
      saved=true;
    });
    if(saved&&last)await this.finish();
  }

  async respondIntake(text=this.intake.text,answers=[]) {
    const submittedText=text,directNumber=!answers.length?this.intake.numericAnswer(text):null;
    if(directNumber) { answers=[directNumber]; text=''; }
    let ready=false;
    const needsAi=Boolean(text.trim())||!answers.length;
    await this.run(needsAi?'답변을 정리하고 있어요…':'답변을 저장하고 있어요…',async()=>{
      await this.intake.flush();if(needsAi)await this.ensureAiOn();
      const state=await this.intake.turn(text,answers);
      if(!state)return;
      this.task=state.task;this.preview=state.preview;
      if(directNumber&&!state.reason&&this.intake.text===submittedText) { this.intake.text=''; this.intake.writingFor=null; }
      ready=!Array.isArray(state.form_fields)&&!state.questions.length&&!state.reason&&!this.intake.text.trim();
      if(ready)this.intake.dialogOpen=false;
    });
    if(ready)await this.finish();
  }

  allNo() {
    const group = this.groups()[this.group];
    for (const q of group.questions) if (q.kind === 'criterion' && this.answers[q.id]?.present === undefined) this.answers[q.id] = {present: 'NO', values: {}};
    this.render();
  }

  input(event) {
    const el = event.target;
    const d = el.dataset;
    if (d.intakeForm) {
      const field=this.intake.formFields().find(f=>f.identity===d.intakeForm);
      if(!field||this.busy)return;
      const raw=el.value;
      if(field.kind==='number'&&raw!==''&&(!Number.isFinite(Number(raw))||Number(raw)<0||field.maximum!=null&&Number(raw)>field.maximum)) { el.setCustomValidity('입력 범위를 확인해 주세요.'); el.reportValidity(); return; }
      el.setCustomValidity('');
      this.intake.formValues.set(field.identity,raw===''?null:field.kind==='number'?Number(raw):field.kind==='choice'?field.choices.find(c=>String(c.value)===raw)?.value:raw);
      this.keepDraft();
    }
    else if (d.intakeReply !== undefined) { this.intake.text = el.value; const send=this.host.querySelector('[data-intake-dialog] [data-quick="adaptive-next"]'); if(send)send.disabled=Boolean(this.busy)||!el.value.trim()&&this.intake.state?.ai?.status!=='ERROR'; this.keepDraft(); }
    else if (d.intakeGroupValue) {
      if(!this.busy&&this.intake.selectGroupValue(d.intakeGroupValue,el.value)) {
        const save=this.host.querySelector('[data-intake-dialog] [data-quick="intake-group-save"]');
        if(save)save.disabled=!this.intake.selectedAnswers().length;
        this.keepDraft();
      }
    }
    else if (d.intakeValue) {
      const value = this.intake.parseValue(d.intakeValue, el.value);
      this.intake.values.set(d.intakeValue, value);
      if (event.type === 'input') this.intake.schedule(d.intakeValue, value, error => this.onError(error));
      if (event.type === 'change') this.intake.answer(d.intakeValue, value).catch(error => { this.onError(error); this.render(); });
    }
    else if (d.number) {
      const raw = el.value.trim();
      if (raw === '') delete this.answers[d.number]; else this.answers[d.number] = Number(raw);
      if (event.type === 'change') this.render();
    } else if (d.flag) {
      const id = d.flag, list = new Set(this.answers[id] || []);
      el.checked ? list.add(el.value) : list.delete(el.value);
      this.answers[id] = [...list];
    } else if (d.text) {
      this.answers[d.text] = el.value;
      if (event.type === 'change') this.render();
    } else if (d.cnum) {
      const [id, key] = d.cnum.split('|'), card = this.answers[id] ||= {values: {}};
      card.values ||= {};
      const raw = el.value.trim();
      card.values[key] = raw === '' ? undefined : Number(raw);
      if (event.type === 'change') this.render();
    } else if (d.rev) this.review[d.rev] = el.value;
    else if (d.aidraft !== undefined) { this.aiDraft = el.value;saveExplanationDraft(this.result,this.activeAi(),el.value,this.drafts); }
    else if (d.quickIntake !== undefined) {
      // Typing does not re-render the page, so the button has to follow the text itself.
      this.intakeText = el.value;
      this.keepDraft();
      const button = this.host.querySelector('[data-quick="intake"]');
      if (button) button.disabled = Boolean(this.busy) || !el.value.trim();
      const analyze = this.host.querySelector('[data-quick="analyze"]');
      if (analyze) analyze.disabled = Boolean(this.busy) || !(el.value.trim() || Object.keys(this.photos).length);
    }
    const status=this.host.querySelector('[data-draft-status]');if(status){status.textContent=this.drafts?.error||'';status.hidden=!this.drafts?.error;}
  }

  drop(event) {
    const zone = event.target.closest('[data-drop]');
    if (!zone) return;
    event.preventDefault();
    const file = event.dataTransfer?.files?.[0];
    if (file && window.loco?.path_for_file) this.setPhoto(zone.dataset.drop, window.loco.path_for_file(file));
  }

  // ================= views
  render() {
    if (this.toolbar) {
      this.toolbar.hidden = this.step === 'home';
      for (const button of this.toolbar.querySelectorAll('button')) button.disabled = Boolean(this.busy || this.photoOperation);
    }
    const index = STEPS.findIndex(([id]) => id === this.step);
    const bar = this.step === 'home' ? '' : `<div class="quick-bar"><ol class="quick-steps">${STEPS.map(([id, label], i) => `<li class="${i < index ? 'done' : i === index ? 'current' : ''}">${i + 1}. ${label}</li>`).join('')}</ol></div>`;
    const body = {home: () => this.viewHome(), start: () => this.viewStart(), provisional: () => this.viewProvisional(), questions: () => this.viewQuestions(), result: () => this.viewResult(), review: () => this.viewReview(), excel: () => this.viewExcel()}[this.step]();
    this.intake.busyElapsedSeconds=this.busy&&this.busyStartedAt!=null?Math.floor((Date.now()-this.busyStartedAt)/1000):0;
    const busy = typeof this.busy === 'string' && this.busy && !this.intake.dialogOpen ? renderActivity(this.busy,this.intake.busyElapsedSeconds) : '';
    this.host.innerHTML = `${bar}${busy}${body}<p class="quick-warn" data-draft-status role="alert" ${this.drafts?.error?'':'hidden'}>${esc(this.drafts?.error||'')}</p>${this.intake.dialog(this.busy)}`;
    this.intake.mount(this.host,this.busy);
    mountPoseSettings(this.host,this.settings);
    this.keepDraft();
  }

  quickDrafts(){
    this.drafts||=localDrafts();
    const all=this.drafts.list('quick'),legacy=readDraft();
    if(legacy&&(!legacy.scope||legacy.scope===this.drafts.scope)&&!all.some(value=>value.id===legacy.id||value.taskId&&value.taskId===legacy.taskId&&value.createdAt===legacy.createdAt))all.push({...legacy,id:legacy.id||`legacy:${legacy.surveyId}:${legacy.createdAt}`});
    return all.sort((a,b)=>(b.savedAt||'').localeCompare(a.savedAt||''));
  }
  startNew(){
    this.keepDraft();this.drafts||=localDrafts();
    const legacy=readDraft();
    if(legacy&&(!legacy.scope||legacy.scope===this.drafts.scope)&&this.drafts.put('quick',legacy.id||`legacy:${legacy.surveyId}:${legacy.createdAt}`,{...legacy,id:legacy.id||`legacy:${legacy.surveyId}:${legacy.createdAt}`}))writeDraft(null);
    this.reset();this.draftId=newDraftId();this.render();
  }
  clearCurrentDraft(){
    this.drafts||=localDrafts();if(this.draftId)this.drafts.remove('quick',this.draftId);
    const legacy=readDraft();if(legacy&&(legacy.id===this.draftId||legacy.taskId!=null&&legacy.taskId===this.task?.task_id&&legacy.createdAt===this.survey?.created_at))writeDraft(null);
  }
  editedExplanation(ai){return readExplanationDraft(this.result,ai,this.drafts)?.text??this.aiDraft??ai.edited_text??userText(ai.generated_text??'');}
  // Every unfinished record, including pre-task text, has its own durable bookmark.
  keepDraft() {
    if (readWorkspaceDraft()?.task?.id === this.task?.task_id && this.task) return;
    if (!['start', 'provisional', 'questions'].includes(this.step) || this.result || this.reopened) return;
    if(!this.task&&!this.intakeText?.trim()&&!this.intake?.text?.trim()&&!Object.keys(this.photos||{}).length){if(this.draftId)this.clearCurrentDraft();return;}
    this.drafts||=localDrafts();this.draftId||=newDraftId();
    const draft={id:this.draftId,scope:this.drafts.scope,
      surveyId: this.survey?.survey_id, surveyTitle: this.survey?.title, createdAt: this.survey?.created_at, taskId: this.task?.task_id,taskCreatedAt:this.task?.created_at, step: this.step === 'start' ? 'start' : 'questions', group: this.group,
      photos: Object.fromEntries(Object.entries(this.photos).map(([view, item]) => [view, item.photo.photo_id])),
      formStage:this.intake?.formStage||0, formValues:[...(this.intake?.formValues||[])], answers: this.answers, adaptive: Boolean(this.intake?.state), intakeText: this.intakeText, reply: this.intake?.text||'', ai: this.ai ? {text: this.intakeText, items: this.ai.items, dropped: this.ai.dropped} : null, savedAt: new Date().toISOString(), baseline: Boolean(this.baseline)};
    if(this.drafts.put('quick',this.draftId,draft)&&!writeDraft(draft))this.drafts.error='임시 저장 안내를 갱신하지 못했어요. 저장 공간을 확인해 주세요.';
  }

  async resumeDraft(id) {
    const draft = this.quickDrafts().find(value=>!id||value.id===id);
    if (!draft) return;
    await this.run('작성 중이던 분석을 불러오고 있어요…', () => this.restoreDraft(draft));
  }
  async restoreDraft(draft){
      if(!draft.taskId){const settings=this.settings;this.reset({preserveActivity:true});Object.assign(this,{draftId:draft.id,settings,intakeText:draft.intakeText||'',step:'start'});this.intake.text=draft.reply||'';return;}
      const survey = await this.api('get_survey', {survey_id: draft.surveyId});
      if (survey.created_at !== draft.createdAt) throw new Error('이 기록은 다른 데이터에서 작성하던 것이라 이어 갈 수 없어요.');
      const full = await this.api('get_task', {task_id: draft.taskId});
      if(draft.taskCreatedAt&&full.task.created_at!==draft.taskCreatedAt)throw Error('작성하던 작업이 다른 작업으로 바뀌었어요. 기록을 확인해 주세요.');
      const photos = {};
      const savedViews=Object.keys(draft.photos||{}).length?draft.photos:full.task.conditions?.[this.intake.contract?.session_key]?.views||Object.fromEntries(full.task.capture.slots.filter(slot=>slot.photo_id!=null).map(slot=>[slot.camera_side||'RIGHT',slot.photo_id]));
      for (const [view, photoId] of Object.entries(savedViews)) {
        const photo = full.photos.find(item => item.photo_id === photoId);
        if (photo) photos[view] = {photo, image: await this.api('get_photo_preview', {photo})};
      }
      const settings = this.settings;
      this.reset({preserveActivity:true});
      Object.assign(this, {draftId:draft.id,survey, task: full.task, photos, answers: draft.answers || {}, ai: draft.ai?.items?.length ? {items: draft.ai.items, dropped: draft.ai.dropped || []} : null, intakeText: draft.intakeText??draft.ai?.text??'', stale: true, settings, step: 'start'});
      this.intake.text=draft.reply||'';
      const views = Object.fromEntries(Object.entries(photos).map(([view, item]) => [view, item.photo.photo_id]));
      if (draft.adaptive || this.intake.hasSession(full.task)) {
        let state = await this.intake.open(full.task.task_id, views);

        this.preview = state.preview; this.task = state.task; this.stale = false;
        this.intakeText = draft.intakeText || ''; this.intake.text = draft.reply || ''; this.intake.formStage=draft.formStage||0; this.intake.formValues=new Map(draft.formValues||[]);
        this.intake.dialogOpen=Boolean(state.questions.length);
        this.step = draft.step === 'questions' ? 'questions' : 'provisional'; return;
      }
      if(draft.step==='start')return;
      this.preview = await this.api('quick_preview', {task_id: full.task.task_id, views});
      this.stale = false;
      this.step = draft.step === 'questions' ? 'questions' : 'provisional';
      this.group = Math.min(draft.group || 0, Math.max(0, this.groups().length - 1));
  }

  async discardDraft(id) {
    const draft = this.quickDrafts().find(value=>!id||value.id===id);if(!draft)return;
    if(draft.surveyId&&draft.createdAt&&!(readWorkspaceDraft()?.survey?.id===draft.surveyId&&readWorkspaceDraft()?.survey?.createdAt===draft.createdAt)){const surveys=await this.api('list_surveys');if(surveys.some(s=>s.survey_id===draft.surveyId)){const survey=await this.api('get_survey',{survey_id:draft.surveyId});if(survey.created_at!==draft.createdAt)throw Error('다른 조사로 바뀐 기록은 삭제하지 않았어요.');await this.api('delete_survey',{survey_id:draft.surveyId});}}
    this.drafts.remove('quick',draft.id);if(readDraft()?.id===draft.id||!readDraft()?.id&&readDraft()?.taskId===draft.taskId)writeDraft(null);
    this.step='home';if(this.busy)this.surveys=await this.api('list_surveys');else await this.loadHome();
  }

  viewHome() {
    const list = (this.surveys || []).slice().sort((a, b) => (b.survey_date || '').localeCompare(a.survey_date || '') || b.survey_id - a.survey_id);
    const s = this.settings || {};
    const checkpoint=readWorkspaceDraft();
    const drafts = this.quickDrafts().filter(draft=>!(checkpoint?.task?.id===draft.taskId&&checkpoint?.task?.createdAt===draft.taskCreatedAt));
    const shown = list.filter(x => !drafts.some(draft=>draft.surveyId===x.survey_id&&draft.createdAt===x.created_at));
    const badge = x => x.review_current ? '<span class="badge current">검토 완료</span>' : '<span class="badge none">미검토</span>';
    const draftCard = drafts.map(draft=>`<section class="panel quick-draft"><div><strong>${esc(draft.surveyTitle||'작성 중인 작업 설명')}</strong>
      <span>${Object.keys(draft.photos || {}).length}장의 사진 · ${esc(new Date(draft.savedAt).toLocaleString('ko-KR', {timeZone: 'Asia/Seoul'}))}에 저장됨</span></div>
      <div class="quick-list-actions"><button class="primary" data-quick="resume" data-draft="${esc(draft.id)}">이어서 하기</button><button data-quick="discard-draft" data-draft="${esc(draft.id)}">버리기</button></div></section>`).join('');
    const checkpointVisible = checkpoint && this.workspaceUnavailable !== JSON.stringify(checkpoint) && (!checkpoint.survey || list.some(row => row.survey_id === checkpoint.survey.id));
    const checkpointCard = checkpointVisible ? `<section class="panel quick-draft"><div><strong>임시 저장한 작업이 있어요</strong><span>${WORKSPACE_STEPS.indexOf(checkpoint.step) + 1}단계 · ${esc(new Date(checkpoint.savedAt).toLocaleString('ko-KR'))} · 이 PC에 보관</span></div><button class="primary" data-quick="workspace-resume">이어서 하기</button></section>` : '';
    return `${checkpointCard}${draftCard}<section class="panel quick-hero"><h2>사진과 작업 설명으로, 필요한 정보만 확인해요</h2>
      <p>사진과 설명에서 파악한 값은 저장하고, 부족한 부분만 물어볼게요. 결과와 Excel까지 이어져요.</p>
      <button class="primary" data-quick="new" ${this.busy ? 'disabled' : ''}>＋ 새 분석 시작</button></section>
      <section class="panel"><h3>최근 분석</h3>${shown.length ? `<ul class="quick-list">${shown.map(x => `<li>
        <div><strong>${esc(x.title || '제목 없음')}</strong><span>${esc(x.survey_date || '')} · 작업 ${x.task_count}개 ${badge(x)}</span></div>
        <div class="quick-list-actions"><button data-open="${x.survey_id}">열기</button>
        <button class="${this.confirmDelete === x.survey_id ? 'danger' : ''}" data-del="${x.survey_id}">${this.confirmDelete === x.survey_id ? '정말 삭제' : '삭제'}</button></div></li>`).join('')}</ul>` : '<p class="quick-note">아직 분석이 없어요. "새 분석 시작"을 눌러 보세요.</p>'}</section>`;
  }

  viewStart() {
    const count = Object.keys(this.photos).length;
    const slot = view => {
      const item = this.photos[view.id];
      return `<section class="panel quick-slot ${item ? 'filled' : ''}" data-drop="${view.id}">
        <h3>${esc(view.title)}</h3><p>${esc(view.hint)}</p>
        ${item ? `<img src="${item.image.data_url}" alt="${esc(VIEW_LABEL[view.id])}">` : '<div class="quick-slot-empty">사진을 끌어다 놓거나<br>선택하세요</div>'}
        <div class="quick-slot-actions"><button type="button" class="${item ? '' : 'primary'}" data-choose="${view.id}" ${this.busy ? 'disabled' : ''}>${item ? '바꾸기' : '사진 선택'}</button>
        ${item ? `<button type="button" data-remove="${view.id}" ${this.busy ? 'disabled' : ''}>빼기</button>` : ''}</div>
      </section>`;
    };
    return `${this.baseline ? '<p class="quick-ok">개선 전 결과를 기억하고 있어요. 개선 후 사진으로 넣으면 전후를 비교해 드려요.</p>' : ''}
      <p class="quick-lead">옆에서 찍은 작업자 전신 사진이 있으면 관절 각도로 1차 REBA 점수를 바로 보여 드려요. 양쪽 옆 사진이 있으면 두 팔을 모두 재고, 정면(또는 후면) 사진이 있으면 옆으로 기울임·팔 벌림을 제안해요. 한 장만 넣어도 돼요.</p>
      <div class="quick-slots">${VIEWS.map(slot).join('')}</div>
      <section class="panel intake-start"><h3>어떤 작업인가요?</h3><p class="quick-note">아는 만큼 적어 주세요. 사진과 설명에서 파악한 값은 저장하고, 부족한 부분만 다시 물어볼게요.</p><textarea data-quick-intake rows="3" ${this.intake?.contract ? `maxlength="${this.intake.contract.policy.text_limit}"` : ''} aria-label="작업 설명" placeholder="예: 20kg 상자를 하루 30번 옮겨요. 나머지는 앉아서 키보드를 4시간 사용해요.">${esc(this.intakeText)}</textarea></section>
      <div class="quick-nav"><button class="quick-back" data-quick="workspace-back">뒤로 가기</button><button class="primary" data-quick="analyze" ${(count || this.intakeText.trim()) && !this.busy ? '' : 'disabled'}>${this.preview && !this.stale ? '자동 정리 보기' : '사진·작업 설명 정리'}</button></div>`;
  }

  pointsFor(view) {
    const fromPreview = this.preview?.views?.[view]?.points;
    if (fromPreview) return fromPreview;
    const id = this.photos[view]?.photo.photo_id;
    return this.result?.pose?.slots?.find(slot => slot.photo_id === id)?.points || [];
  }

  photoStrip() {
    const views = VIEWS.filter(view => this.photos[view.id]);
    const selected = views.find(view => view.id === this.selectedPhotoView) || views[0];
    const tabs = `<div class="quick-photo-tabs" role="group" aria-label="사진 방향 선택">${VIEWS.map(view => {
      const available = Boolean(this.photos[view.id]), active = view.id === selected?.id;
      return `<button type="button" data-photo-view="${view.id}" aria-pressed="${active}" class="${active ? 'selected' : ''}" ${available ? '' : 'disabled title="등록된 사진이 없어요"'}>${esc(VIEW_LABEL[view.id])}</button>`;
    }).join('')}</div>`;
    const picture = selected ? (() => {
      const view = selected;
      const item = this.photos[view.id];
      const w = item.image.width_px || item.photo.width_px || 1, h = item.image.height_px || item.photo.height_px || 1, r = Math.max(w, h) / 120;
      const pose=poseForView(this,view.id),model=pose.engine || this.settings?.analysis?.pose_model;
      const floor=model?.confidence_min ?? 0.5;
      const p = Object.fromEntries(this.pointsFor(view.id).filter(x => x.confidence >= floor).map(x => [x.name, x]));
      const connections=pose.connections || this.settings?.pose_contract?.connections?.[model?.provider] || [];
      const lines = connections.filter(([a, b]) => p[a] && p[b]).map(([a, b]) => `<line x1="${p[a].x_px}" y1="${p[a].y_px}" x2="${p[b].x_px}" y2="${p[b].y_px}"/>`).join('');
      const dots = Object.values(p).map(x => `<circle cx="${x.x_px}" cy="${x.y_px}" r="${r}"/>`).join('');
      return `<figure class="quick-photo"><img src="${item.image.data_url}" alt="${esc(VIEW_LABEL[view.id])}"><svg viewBox="0 0 ${w} ${h}" preserveAspectRatio="xMidYMid meet" style="--r:${r}px">${lines}${dots}</svg></figure>`;
    })() : '<div class="quick-photo-empty">등록된 사진이 없어요.</div>';
    return `<div class="quick-strip">${tabs}${picture}${this.reopened || this.step === 'review' ? '' : '<button type="button" class="quick-change" data-quick="photos">사진 바꾸기</button>'}</div>`;
  }

  viewProvisional() {
    const pv = this.preview, s = pv.score;
    const side = m => m.scope === 'COMMON' ? '' : m.scope === 'LEFT' ? '왼쪽 ' : '오른쪽 ';
    const measured = pv.measured.map(m => `<li><strong>${esc(m.label)}</strong> ${m.angles.map(a => `${a.value_deg}°`).join(' / ')} → ${esc(side(m))}${esc(VALUE_KO[m.value] || m.value + '단계')} <small>${esc(VIEW_LABEL[m.view])}</small>${m.boundary_review ? ' <em>경계값</em>' : ''}</li>`).join('');
    const spatial=Object.entries(pv.views || {}).flatMap(([view,pose])=>(pose.world_angles || []).filter(a=>a.value_deg!=null).map(a=>`<li>${esc(VIEW_LABEL[view])} · ${a.side==='LEFT'?'왼쪽':'오른쪽'} ${esc(a.label)} ${a.value_deg.toFixed(1)}°</li>`)).join('');
    const front = pv.front.map(f => `<li><strong>${esc(f.label)}</strong> ${f.value_deg}° ${f.suggested ? '→ <em>있음으로 제안</em>' : '→ 거의 없음'}</li>`).join('');
    return `<div class="quick-columns">${this.photoStrip()}
      <section class="panel quick-score">
        <h2>1차 REBA 점수</h2>
        ${s ? `<div class="quick-big"><strong class="${rebaScoreClass(s.total)}">${s.total}</strong><span>점 · ${esc(RISK[s.risk] || s.risk)}</span></div>
          ${renderRebaScale(s.total, {provisional: true})}
          <p class="quick-note">${esc(s.assumption)}</p>` : '<p class="quick-note">사진에서 측정한 값이 없어 1차 점수를 내지 못했어요. 질문에 답하면 계산할 수 있어요.</p>'}
        <h3>사진에서 측정한 값</h3>
        <ul class="quick-measured">${measured || '<li>측면 사진에서 측정한 값이 없어요.</li>'}</ul>
        ${front ? `<h3>정면·후면 사진 제안</h3><ul class="quick-measured">${front}</ul>` : ''}
        ${spatial ? `<details class="quick-spatial"><summary>3D 추정 각도 (참고)</summary><p class="quick-note">사진 한 장에서 추정한 분절각이에요. REBA에는 기존 사진 각도와 확인값을 사용해요.</p><ul>${spatial}</ul></details>` : ''}${pv.diagnostics.map(d => `<p class="quick-warn">${esc(d.message)}</p>`).join('')}
        ${this.intake?.state ? this.intake.summary() : ''}${this.intakePanel()}
        <div class="quick-nav"><button class="quick-back" data-quick="photos">뒤로 가기</button><button class="primary" data-quick="questions">부족한 부분만 확인</button>${this.intake?.state ? '<button data-quick="next">현재 정보로 결과 보기</button>' : ''}</div>
      </section></div>`;
  }

  aiTag(q, item) {
    if (q.id !== 'work_types' || !this.ai) return '';
    const quote = this.ai.items.find(i => i.kind === 'tick' && i.gate === item.key)?.quote;
    return quote ? ` <small class="quick-hint">AI 정리 · “${esc(quote)}”</small>` : '';
  }

  intakeValue(item) {
    if (item.kind === 'choice') return item.value === 'YES' ? '예' : item.value === 'NO' ? '아니오' : String(item.value);
    return item.kind === 'number' ? `${item.value}${item.unit ? ' ' + item.unit : ''}` : String(item.value);
  }

  intakePanel() {
    const busy = Boolean(this.busy);
    if (this.intake?.state) return `<section class="quick-intake"><details><summary>작업 설명 더하기·수정하기</summary><p class="quick-note">설명과 관련 입력값을 AI에 보내 부족한 정보만 확인해요. 사진은 보내지 않아요. 이름·건강정보는 적지 마세요.</p><textarea data-quick-intake rows="3" maxlength="${this.intake.state.contract.policy.text_limit}" aria-label="작업 설명">${esc(this.intakeText)}</textarea><button type="button" class="primary" data-quick="intake" ${busy || !this.intakeText.trim() ? 'disabled' : ''}>설명 반영</button></details></section>`;
    return `<section class="quick-intake"><h3>작업을 한 줄로 알려 주세요 <small>(선택 · 말한 것만 AI가 칸에 채워 드려요)</small></h3>
      <p class="quick-note">예) “20kg 상자를 바닥에서 들어 선반에 하루 30번쯤 옮기고, 오후엔 4시간 키보드를 쳐요”. 적지 않은 값은 지어내지 않고 비워 둬요. 이 문장만 AI에 보내요(사진·이름은 보내지 않아요). 이름 같은 개인정보는 쓰지 마세요. 말로 하려면 Windows에서 Win+H를 누르세요.</p>
      <textarea data-quick-intake rows="3" maxlength="600" placeholder="작업 내용, 무게, 하루에 몇 번·몇 시간을 적어 주세요" aria-label="작업 설명">${esc(this.intakeText)}</textarea>
      <div class="quick-nav"><button class="primary" data-quick="intake" ${busy || !this.intakeText.trim() ? 'disabled' : ''}>AI가 정리하기</button>${this.ai ? '<button data-quick="intake-clear">지우고 다시</button>' : ''}</div>
      ${this.ai ? this.intakeSummary() : ''}</section>`;
  }

  intakeSummary() {
    const questions = this.preview?.questions || [];
    const cardShown = item => { const q = questions.find(x => x.id === item.question_id); return !q || this.visible(q); };
    const ticks = this.ai.items.filter(i => i.kind === 'tick');
    const rows = this.ai.items.filter(i => i.kind !== 'tick' && cardShown(i));
    return `<div class="quick-intake-result"><h4>AI가 이렇게 이해했어요</h4>
      <ul class="quick-intake-list">
        ${ticks.length ? `<li><span><b>작업 종류</b> ${esc(ticks.map(i => i.label).join(' · '))}<small>아래 체크 목록에서 더하거나 뺄 수 있어요</small></span></li>` : ''}
        ${rows.map(i => `<li><span><b>${esc(i.label)}</b> ${esc(this.intakeValue(i))}<small>근거 “${esc(i.quote)}”</small></span><button type="button" data-quick-intake-drop="${esc(i.target)}">빼기</button></li>`).join('')}
      </ul>
      ${this.ai.dropped?.length ? `<p class="quick-note">문장에서 근거를 찾지 못한 값 ${this.ai.dropped.length}개는 채우지 않았어요.</p>` : ''}
      <p class="quick-note">말하지 않은 값은 비워 두었어요. 틀린 값은 "빼기"를 누르세요.</p></div>`;
  }

  viewQuestionsCompact() {
    const settled = q => settledByIntake(q, this.answers, this.ai.items), groups = this.groups();
    const todo = groups.filter(g => !LATER_GROUPS.includes(g.name)).map(g => ({name: g.name, questions: g.questions.filter(q => !settled(q))})).filter(g => g.questions.length);
    const later = groups.filter(g => LATER_GROUPS.includes(g.name));
    for (const g of [...todo, ...later]) for (const q of g.questions) if (q.kind === 'checklist' && this.answers[q.id] === undefined) this.answers[q.id] = q.items.filter(i => i.suggested).map(i => i.key);
    const ready = todo.every(g => this.groupReady(g)), count = todo.reduce((n, g) => n + g.questions.length, 0);
    return `<div class="quick-columns">${this.photoStrip()}
      <section class="panel quick-ask">
        <div class="quick-loco"><b>로코</b> 남은 확인 ${count}개 · 한 화면에서 끝내요</div>
        ${this.intakeSummary()}
        ${todo.map(g => `<h4 class="quick-section">${esc(g.name)}</h4>${g.questions.map(q => this.question(q)).join('')}`).join('')}
        ${later.length ? `<details class="quick-later" ${this.laterOpen ? 'open' : ''}><summary>조사 정보·작업장 상황 (나중에 입력해도 돼요)</summary>${later.map(g => g.questions.map(q => this.question(q)).join('')).join('')}</details>` : ''}
        ${ready ? '' : '<p class="quick-note">확인할 질문에 답해 주세요. 모르면 "모름"을 고르면 돼요. 숫자는 0 이상이고, 하루 시간은 1440분 이하예요.</p>'}
        <div class="quick-nav"><button data-quick="prev">이전</button>
          <button class="primary" data-quick="next" ${ready && !this.busy ? '' : 'disabled'}>최종 결과 계산</button></div>
      </section></div>`;
  }

  critCard(q) {
    const card = this.answers[q.id] || {}, values = card.values || {};
    const fieldHtml = f => {
      const key = `${q.id}|${f.key}`, value = values[f.key];
      if (f.type === 'truth') return `<div class="quick-field"><label>${esc(f.label)}</label><div class="quick-choices">${[['YES', '예'], ['NO', '아니오'], ['UNKNOWN', '모름']].map(([v, l]) => `<button type="button" class="${value === v ? 'selected' : ''}" data-crit="${esc(key)}" data-truth="${v}">${l}</button>`).join('')}</div></div>`;
      return `<div class="quick-field"><label>${esc(f.label)}</label><div class="quick-number"><input type="number" min="0" ${f.maximum ? `max="${f.maximum}"` : ''} step="any" inputmode="decimal" data-cnum="${esc(key)}" value="${value ?? ''}"><span>${esc(f.unit)}</span>
        <div class="quick-choices">${f.chips.map(c => `<button type="button" class="${value === c ? 'selected' : ''}" data-crit="${esc(key)}" data-chip="${c}">${c}</button>`).join('')}<button type="button" class="${value === null ? 'selected' : ''}" data-crit="${esc(key)}" data-chip="">모름</button></div></div></div>`;
    };
    return `<article class="quick-q crit answered"><h3>${esc(q.text)}</h3><p class="quick-ask-text">${esc(q.ask)}</p>${q.help ? `<p>${esc(q.help)}</p>` : ''}${q.fields.map(fieldHtml).join('')}</article>`;
  }

  question(q) {
    if (q.kind === 'criterion') return this.critCard(q);
    const value = this.answers[q.id];
    let body = '';
    if (q.kind === 'choice') body = `<div class="quick-choices">${q.choices.map(c => `<button type="button" class="${value !== undefined && String(value) === String(c.value) ? 'selected' : ''}" data-answer="${esc(q.id)}" data-value="${esc(c.value)}">${esc(c.label)}${q.suggested != null && String(q.suggested) === String(c.value) ? ' <small>추정</small>' : ''}</button>`).join('')}</div>`;
    if (q.kind === 'number') body = `<div class="quick-number"><input type="number" min="0" ${q.maximum ? `max="${q.maximum}"` : ''} inputmode="decimal" data-number="${esc(q.id)}" value="${value ?? ''}" aria-label="${esc(q.text)}"><span>${esc(q.unit)}</span>
      <div class="quick-choices">${q.chips.map(c => `<button type="button" class="${value === c ? 'selected' : ''}" data-answer="${esc(q.id)}" data-value="${c}">${c}${esc(q.unit)}</button>`).join('')}<button type="button" class="${value === null ? 'selected' : ''}" data-answer="${esc(q.id)}" data-value="">모름</button></div></div>`;
    if (q.kind === 'checklist') body = `<div class="quick-flags">${q.items.map(item => `<label><input type="checkbox" data-flag="${esc(q.id)}" value="${esc(item.key)}" ${(value || []).includes(item.key) ? 'checked' : ''}> ${esc(item.label)}${item.suggested ? ` <small class="quick-hint">사진 제안 · ${esc(item.evidence)}</small>` : ''}${this.aiTag(q, item)}</label>`).join('')}</div>`;
    if (q.kind === 'text') body = `<input type="text" class="quick-text" maxlength="${q.maxlength}" data-text="${esc(q.id)}" value="${esc(value ?? '')}" placeholder="${esc(q.placeholder)}" aria-label="${esc(q.text)}">`;
    return `<article class="quick-q ${this.answered(q) && (q.kind !== 'text' || String(value ?? '').trim()) ? 'answered' : ''}"><h3>${esc(q.text)}${q.required ? ' <small>필수</small>' : ''}</h3>${q.help ? `<p>${esc(q.help)}</p>` : ''}${body}</article>`;
  }

  viewQuestions() {
    if (this.intake?.state) return `<div class="intake-page">${this.intake.summary()}${this.intake.panel(this.busy)}</div>`;
    if (this.ai) return this.viewQuestionsCompact();
    const groups = this.groups(), group = groups[Math.min(this.group, groups.length - 1)];
    for (const q of group.questions) if (q.kind === 'checklist' && this.answers[q.id] === undefined) this.answers[q.id] = q.items.filter(i => i.suggested).map(i => i.key);
    const ready = this.groupReady(group), last = this.group >= groups.length - 1;
    const hasCards = group.questions.some(q => q.kind === 'criterion' && !q.implicit);
    return `<div class="quick-columns">${this.photoStrip()}
      <section class="panel quick-ask">
        <div class="quick-loco"><b>로코</b> ${esc(group.name)} (${this.group + 1}/${groups.length})</div>
        ${hasCards ? '<div class="quick-bulk"><button type="button" data-quick="allno">아직 답하지 않은 기준은 모두 "아니오"로 (직접 확인했어요)</button></div>' : ''}
        ${group.questions.map(q => this.question(q)).join('')}
        ${ready ? '' : '<p class="quick-note">모든 질문에 답해 주세요. 모르면 "모름"을 고르면 돼요. 숫자는 0 이상이고, 하루 시간은 1440분 이하예요.</p>'}
        <div class="quick-nav"><button data-quick="prev" ${this.group === 0 ? 'disabled' : ''}>이전</button>
          <button class="primary" data-quick="next" ${ready && !this.busy ? '' : 'disabled'}>${last ? '최종 결과 계산' : '다음'}</button></div>
      </section></div>`;
  }

  rebaPanel() {
    const r = this.result, slot = r.reba?.slots?.[0], pv = this.preview?.score;
    if (!slot) return '<h2>REBA</h2><p class="quick-note">이 분석에는 REBA 계산이 없어요.</p>';
    if (slot.total == null) {
      const missing = [...new Set([...(slot.left?.missing_fields || []), ...(slot.right?.missing_fields || [])].map(f => FIELD_KO[f.split('.').pop()] || f))];
      return `<h2>최종 REBA 점수</h2><p class="quick-warn">아직 점수를 계산할 수 없어요. 빠진 항목: ${esc(missing.join(', ') || '사진 확인')}.</p>`;
    }
    const side = slot.selected_side === 'LEFT' ? '왼쪽' : '오른쪽';
    const first = pv ? ` · 1차 점수 ${pv.total ?? '—'}점에서 답변을 반영했어요.` : '';
    return `<h2>최종 REBA 점수</h2><div class="quick-big"><strong class="${rebaScoreClass(slot.total)}">${slot.total}</strong><span>점 · ${esc(RISK[slot.risk] || slot.risk)}</span></div>
      ${renderRebaScale(slot.total)}
      <p class="quick-note">왼쪽 ${slot.left.total ?? '—'}점 · 오른쪽 ${slot.right.total ?? '—'}점 중 높은 쪽(${side})${first}</p>`;
  }

  criteriaRows(editable) {
    const rows = this.result.judgment?.judgments || [];
    const line = j => {
      const inv = j.investigator?.status ?? null;
      const conclude = editable ? `<td><div class="quick-choices small"><button type="button" class="${inv === 'APPLICABLE' ? 'selected' : ''}" data-concl="${j.criterion_no}" data-status="APPLICABLE">해당</button><button type="button" class="${inv === 'NOT_APPLICABLE' ? 'selected' : ''}" data-concl="${j.criterion_no}" data-status="NOT_APPLICABLE">비해당</button></div></td>` : '';
      return `<tr><td>${esc(CRIT_NAME[j.criterion_no])} <small>(법정 ${j.criterion_no}호)</small></td><td><span class="quick-status ${esc(j.computed_status)}">${esc(STATUS[j.computed_status] || j.computed_status)}</span>${(j.missing_fields || []).length ? ` <small>추가 입력 ${j.missing_fields.length}개</small>` : ''}</td>${conclude}</tr>`;
    };
    const table = list => `<table class="quick-table"><thead><tr><th>기준</th><th>계산 초안</th>${editable ? '<th>조사자 결론</th>' : ''}</tr></thead><tbody>${list.map(line).join('')}</tbody></table>`;
    const relevant = rows.filter(j => j.computed_status !== 'NOT_APPLICABLE'), none = rows.filter(j => j.computed_status === 'NOT_APPLICABLE');
    return `${relevant.length ? table(relevant) : '<p class="quick-note">해당하거나 더 확인할 기준이 없어요.</p>'}${none.length ? `<details class="quick-none"><summary>해당 없음 ${none.length}개 보기</summary>${table(none)}</details>` : ''}`;
  }

  comparePanel() {
    const c = this.comparison;
    if (!c) return '';
    const label = x => STATUS[x] || x || '—';
    const changed = c.criteria.filter(x => x.before_status !== x.after_status);
    const delta = c.reba_max_delta;
    return `<section class="panel quick-compare"><h3>개선 전후 비교</h3>
      <div class="quick-big small"><strong>${delta == null ? '—' : (delta > 0 ? '+' : '') + delta}</strong><span>REBA 최대 점수 변화 ${delta == null ? '(비교할 수 없어요)' : delta < 0 ? '(낮아졌어요)' : delta > 0 ? '(높아졌어요)' : '(같아요)'}</span></div>
      ${changed.length ? `<ul class="quick-measured">${changed.map(x => `<li>${esc(CRIT_NAME[x.criterion_no])}(법정 ${x.criterion_no}호): ${esc(label(x.before_status))} → <strong>${esc(label(x.after_status))}</strong></li>`).join('')}</ul>` : '<p class="quick-note">기준 판정이 바뀐 항목은 없어요.</p>'}
      ${(c.notes || []).map(n => `<p class="quick-note">${esc(n)}</p>`).join('')}
      <p class="quick-note">바뀐 입력값은 Excel의 "개선 전후 비교" 시트에 정리돼요.</p></section>`;
  }

  resultSummary() {
    const rows = this.result.judgment?.judgments || [];
    if (!rows.length) return '';
    const count = status => rows.filter(j => j.computed_status === status).length, need = count('NEEDS_INPUT'), review = count('NEEDS_REVIEW');
    return `<p class="quick-lead">법정 기준 11개 중 <b>${count('APPLICABLE')}개</b>가 해당 초안이에요${need ? ` · 입력이 더 필요한 기준 <b>${need}개</b>` : ''}${review ? ` · 검토가 필요한 기준 <b>${review}개</b>` : ''}.</p>`;
  }

  // The result has its own screen: the score and the criteria, nothing to edit.
  viewResult() {
    return `<div class="quick-columns">${this.photoStrip()}
      <div><section class="panel quick-score">${this.rebaPanel()}
        ${this.resultSummary()}
        <h3>관련 법정 기준 초안</h3>${this.criteriaRows(false)}
        <p class="quick-note">초안은 입력한 값으로 계산한 결과예요. 최종 해당 여부는 조사자가 검토해 정해요.</p>
        <div class="quick-nav"><button class="quick-back" data-quick="workspace-back">뒤로 가기</button><button data-quick="preview">Excel 미리보기</button><button class="primary" data-quick="review">검토하고 설명 만들기</button></div></section>
        ${this.comparePanel()}</div></div>`;
  }

  aiPanel() {
    const s = this.settings || {};
    const ai = this.activeAi();
    let body = '<p class="quick-note">AI에는 계산된 숫자 요약만 보내요. 이름·사진·메모는 보내지 않아요.</p>';
    if (!s.gpt_key_present) body = '<p class="quick-warn">AI 키(OPENAI_API_KEY)가 이 PC에 없어요. 없어도 "기본 설명"을 만들 수 있어요.</p>';
    body += `<div class="quick-nav left"><button class="primary" data-quick="gen-ai" ${this.busy ? 'disabled' : ''}>${ai ? '설명 다시 만들기' : (s.gpt_key_present ? 'AI 설명 만들기' : '기본 설명 만들기')}</button></div>`;
    if (ai) {
      const text = this.editedExplanation(ai);
      const shown = (ai.is_active ? ai.applied_text : null) ?? ai.edited_text ?? ai.generated_text ?? '';
      const kind = shown !== ai.generated_text ? '조사자가 수정한 설명' : ai.result === 'GENERATED' ? 'AI가 쓴 설명' : '기본 설명(AI를 쓰지 못했어요)';
      const reason = ai.result === 'DISABLED' ? AI_REASON.DISABLED : (AI_REASON[ai.fallback_reason] || userText(ai.fallback_reason) || '');
      body += `<p class="quick-note">${esc(kind)}${ai.result !== 'GENERATED' ? ` · 이유: ${esc(reason)}` : ''}${ai.is_active ? ' · <b>적용 중</b>' : ''}</p>
        <div class="quick-explanation-reading">${renderQuickExplanation(ai, shown)}</div>
        <div class="quick-nav left"><button data-quick="apply-ai">생성 원문 적용</button></div>
        <details class="quick-explanation-details quick-explanation-editor" data-ai-editor ${this.aiEditorOpen ? 'open' : ''}><summary>전체 원문 보기 · 직접 수정</summary>
          <p class="quick-note">수정 내용은 ‘수정본 적용’을 누른 뒤 위 읽기 화면에 반영돼요.</p>
          ${readExplanationDraft(this.result,ai,this.drafts)?'<p class="quick-note" data-explanation-draft>수정 중인 문장을 이 PC에 임시 저장했어요. 수정문 적용을 누르면 결과에 반영돼요.</p>':''}<textarea class="quick-ai" rows="12" aria-label="쉬운 설명 원문 수정" data-aidraft>${esc(text)}</textarea>
          <div class="quick-nav left"><button data-quick="apply-edited">수정본 적용</button></div>
        </details>
        <p class="quick-note">설명은 보고서에 들어갈 문장일 뿐, 계산 결과와 판정은 바뀌지 않아요.</p>`;
    }
    return `<section class="panel"><h3>③ 쉬운 설명</h3>${body}</section>`;
  }

  // Review: the investigator's conclusions, the review mark and the easy explanation.
  viewReview() {
    const reviewed = this.survey?.review?.reviewed && this.survey?.review?.reviewed_metadata_revision === this.survey?.metadata_revision;
    return `<div class="quick-columns">${this.photoStrip()}
      <div><section class="panel"><h3>① 조사자 결론</h3>
        <p class="quick-note">계산 초안을 보고 최종 해당 여부를 직접 정해요. 정하지 않으면 초안 그대로 남아요. 같은 버튼을 다시 누르면 취소돼요.</p>${this.criteriaRows(true)}</section>
      <section class="panel"><h3>② 검토 표시</h3>
        <div class="quick-setting-row"><label>검토자<input type="text" data-rev="reviewer" value="${esc(this.review.reviewer)}" placeholder="이름"></label>
        <label>메모<input type="text" data-rev="note" value="${esc(this.review.note)}" placeholder="예: 야간 작업 추가 관찰 필요"></label></div>
        <div class="quick-nav left"><button class="primary" data-quick="reviewed">검토 완료로 표시</button>${reviewed ? '<button data-quick="unreview">검토 표시 해제</button>' : ''}</div>
        <p class="quick-note">${reviewed ? '<b>검토 완료</b>로 표시되어 있어요.' : '아직 검토 표시가 없어요.'} 검토 표시는 계산 완전성과 별개예요.</p></section>
      ${this.aiPanel()}
      <section class="panel"><div class="quick-nav"><button class="quick-back" data-quick="result">뒤로 가기</button><button class="primary" data-quick="preview">Excel 미리보기</button></div></section></div></div>`;
  }

  // Excel: what is missing, a preview of the sheets exactly as the file will contain them, and the save button.
  viewExcel() {
    return `<div class="quick-excel-page">
      <section class="panel quick-excel"><h3>Excel 미리보기</h3>${this.excelPreviewPanel()}</section>
      ${this.checklistPanel()}
      <section class="panel"><h3>Excel로 저장</h3>
        <p class="quick-note">위 미리보기와 같은 내용이 파일로 저장돼요.${this.comparison ? ' 개선 전후 비교도 함께 들어가요.' : ''}</p>
        ${this.exported ? `<p class="quick-ok">저장한 파일: ${esc(this.exported.file_path)}</p>` : ''}
        <div class="quick-nav left"><button class="primary" data-quick="excel">Excel로 저장</button></div></section>
      <section class="panel"><h3>그다음</h3>
        <div class="quick-nav left"><button data-quick="workspace-back">뒤로 가기</button><button data-quick="improve">개선 후 사진으로 다시 비교</button>
          <button class="quick-advanced" data-quick="detail">고급 편집</button></div></section>${this.comparePanel()}</div>`;
  }

  excelPreviewPanel() {
    const p = this.excelPreview;
    if (!p?.sheets?.length) return '<p class="quick-note">미리 볼 시트가 없어요.</p>';
    const index = Math.min(this.excelTab, p.sheets.length - 1), sheet = p.sheets[index];
    const cellClass = value => value === '입력 필요' ? 'missing' : value === '검토 필요' ? 'review' : '';
    const cell = value => esc(value).replace(/\n/g, '<br>');
    // Form-style tables (no dark header, label cells, merged cells) come from the same description the Excel file is written from.
    const table = t => {
      const labels = new Set(t.labels || []), labelRows = new Set(t.label_rows || []), labelCells = new Set((t.label_cells || []).map(([r, c]) => `${r}:${c}`));
      const starts = new Map(), covered = new Set();
      (t.merges || []).forEach(([r1, c1, r2, c2]) => {
        starts.set(`${r1}:${c1}`, [r2 - r1 + 1, c2 - c1 + 1]);
        for (let r = r1; r <= r2; r++) for (let c = c1; c <= c2; c++) if (r !== r1 || c !== c1) covered.add(`${r}:${c}`);
      });
      const head = t.header === false ? '' : `<thead><tr>${t.columns.map(c => `<th>${cell(c)}</th>`).join('')}</tr></thead>`;
      const row = (values, r) => `<tr>${values.map((value, c) => {
        if (covered.has(`${r}:${c}`)) return '';
        const span = starts.get(`${r}:${c}`) || [1, 1];
        const classes = [cellClass(value), labels.has(c) || labelRows.has(r) || labelCells.has(`${r}:${c}`) ? 'label' : ''].filter(Boolean).join(' ');
        return `<td class="${classes}"${span[0] > 1 ? ` rowspan="${span[0]}"` : ''}${span[1] > 1 ? ` colspan="${span[1]}"` : ''}>${cell(value)}</td>`;
      }).join('')}</tr>`;
      const body = t.rows.length ? t.rows.map(row).join('') : `<tr><td colspan="${t.columns.length}" class="empty">내용이 없어요</td></tr>`;
      const kind = `${t.bordered ? ' form' : ''}${t.columns.length > 8 ? ' wide' : ''}`;
      return `${t.heading ? `<h4 class="quick-sheet-heading">${esc(t.heading)}</h4>` : ''}<div class="quick-sheet-wrap"><table class="quick-sheet${kind}">${head}<tbody>${body}</tbody></table></div>`;
    };
    return `<div class="quick-tabs" role="tablist">${p.sheets.map((x, i) => `<button type="button" role="tab" aria-selected="${i === index}" class="${i === index ? 'selected' : ''}" data-quick="excel-tab" data-tab="${i}">${esc(x.name)}</button>`).join('')}</div>
      ${sheet.lead ? `<p class="quick-note">${esc(sheet.lead)}</p>` : ''}${sheet.tables.map(table).join('')}${(sheet.notes || []).map(n => `<p class="quick-note">${esc(n)}</p>`).join('')}
      <p class="quick-note">저장하는 파일에는 위 시트가 같은 내용으로 들어가요. 대표 사진 이미지는 파일에만 들어가요.</p>`;
  }
}
