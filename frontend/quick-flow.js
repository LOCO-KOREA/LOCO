// LOCO simple flow: everything happens here, in order, with question cards.
//   home -> photos (left / front-back / right) -> provisional REBA -> questions -> result -> review, AI explanation, Excel, before/after.
// Provisional scores are never saved. Only confirmed answers are written through the usual task APIs,
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
const BONES = [['left_shoulder', 'right_shoulder'], ['left_hip', 'right_hip'], ['left_shoulder', 'left_hip'], ['right_shoulder', 'right_hip'],
  ['left_shoulder', 'left_elbow'], ['left_elbow', 'left_wrist'], ['right_shoulder', 'right_elbow'], ['right_elbow', 'right_wrist'],
  ['left_hip', 'left_knee'], ['left_knee', 'left_ankle'], ['right_hip', 'right_knee'], ['right_knee', 'right_ankle'],
  ['left_ear', 'left_shoulder'], ['right_ear', 'right_shoulder'], ['nose', 'left_eye'], ['nose', 'right_eye']];
const TASK_KEYS = ['schema_version', 'task_kind', 'task_name', 'input_template', 'worker_count', 'conditions', 'legal', 'capture', 'manual', 'analysis_scope', 'legacy_input'];
const SURVEY_KEYS = ['survey_type', 'survey_date', 'investigator', 'department', 'process', 'title', 'occasional_reason', 'occasional_cause', 'previous_survey_date', 'workplace_situation', 'participation', 'symptom_survey'];
const STEPS = [['start', '사진 넣기'], ['provisional', '1차 점수'], ['questions', '로코 질문'], ['result', '결과'], ['review', '검토·출력']];
const DEFAULT_MODEL = 'gpt-4.1';
const AI_REASON = {DISABLED: 'AI 설명이 꺼져 있어요', NO_API_KEY: '이 PC에 AI 키가 없어요', MODEL_NOT_CONFIGURED: 'AI 모델이 정해지지 않았어요', TIMEOUT: 'AI 응답이 15초 안에 오지 않았어요', API_ERROR: 'AI 서버가 요청을 받지 못했어요(키·모델·네트워크 확인)', INVALID_STRUCTURED_CONTENT: 'AI 응답이 정해진 형식과 맞지 않았어요', INCOMPLETE_RESPONSE: 'AI 응답이 끝까지 오지 않았어요', REFUSAL_OR_EMPTY_RESPONSE: 'AI가 답을 주지 않았어요', OPENAI_SDK_MISSING: 'AI 연결 부품이 없어요'};
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
    else if (t.type === 'criterion_card') {
      const criterion = task.legal.criteria[t.criterion - 1];
      if (!criterion || criterion.condition_present === 'UNKNOWN') continue;
      const row = (criterion.rows || [])[0], values = {};
      for (const field of q.fields) {
        let value;
        if (field.to.exposure) value = task.legal.exposures.find(x => x.condition_code === field.to.exposure)?.minutes;
        else if (field.to.criterion) value = criterion[field.to.criterion];
        else value = row?.[field.to.row];
        if (value !== undefined && !(field.type === 'truth' && value === 'UNKNOWN')) values[field.key] = value;
      }
      a[q.id] = {present: criterion.condition_present, values};
    }
  }
  return a;
}

export class QuickFlow {
  constructor({host, api, notify, onError, onOpenDetail}) {
    Object.assign(this, {host, api, notify, onError, onOpenDetail});
    this.reset();
    this.step = 'home';
    host.addEventListener('click', event => this.click(event));
    host.addEventListener('input', event => this.input(event));
    host.addEventListener('change', event => this.input(event));
    host.addEventListener('dragover', event => { if (event.target.closest('[data-drop]')) event.preventDefault(); });
    host.addEventListener('drop', event => this.drop(event));
  }

  reset() {
    Object.assign(this, {step: 'start', busy: false, survey: null, task: null, photos: {}, preview: null, stale: true, answers: {}, group: 0,
      result: null, exported: null, baseline: null, comparison: null, reopened: false, saved: null, review: {reviewer: '', note: ''}, aiDraft: '', confirmDelete: null});
  }

  async open() { if (this.step === 'home') await this.loadHome(); else this.render(); }

  async run(label, action) {
    if (this.busy) return;
    this.busy = label || true; this.render();
    try { await action(); } catch (error) { this.onError(error); } finally { this.busy = false; this.render(); }
  }

  // ================= home
  async loadHome() {
    await this.run('', async () => {
      this.surveys = await this.api('list_surveys');
      this.settings = await this.api('get_settings');
      this.step = 'home';
    });
  }

  async openExisting(surveyId) {
    await this.run('결과를 불러오고 있어요…', async () => {
      const survey = await this.api('get_survey', {survey_id: surveyId});
      const tasks = await this.api('list_tasks', {survey_id: surveyId});
      const task = tasks[0];
      if (!task || !task.latest_analysis_id) throw new Error('아직 분석 결과가 없는 조사예요. "새 분석 시작"으로 시작해 주세요.');
      const bundle = await this.api('get_task_result', {task_id: task.task_id});
      const full = await this.api('get_task', {task_id: task.task_id});
      const photos = {};
      for (const slot of full.task.capture.slots) {
        if (slot.photo_id == null) continue;
        const photo = full.photos.find(p => p.photo_id === slot.photo_id);
        const view = Object.keys(VIEW_LABEL).find(key => VIEW_LABEL[key] === slot.label) || (photos.LEFT ? 'RIGHT' : 'LEFT');
        if (photo && !photos[view]) photos[view] = {photo, image: await this.api('get_photo_preview', {photo})};
      }
      const settings = this.settings || await this.api('get_settings');
      this.reset();
      Object.assign(this, {survey, task, photos, result: bundle.analysis, reopened: true, stale: false, step: 'result', settings});
    });
  }

  async deleteSurvey(id) {
    if (this.confirmDelete !== id) { this.confirmDelete = id; return this.render(); }
    this.confirmDelete = null;
    await this.run('삭제하고 있어요…', async () => {
      await this.api('delete_survey', {survey_id: id});
      this.surveys = await this.api('list_surveys');
      this.notify('기록을 삭제했어요. 원본 사진과 Excel 파일은 그대로예요.');
    });
  }

  async saveSettings() {
    const enabled = this.host.querySelector('[data-setting="gpt_enabled"]')?.value === 'YES';
    const model = this.host.querySelector('[data-setting="gpt_model"]')?.value.trim() || '';
    await this.run('설정을 저장하고 있어요…', async () => {
      const settings = await this.api('get_settings');
      delete settings.gpt_key_present;
      Object.assign(settings, {gpt_enabled: enabled, gpt_model: model});
      await this.api('update_settings', {settings});
      this.settings = await this.api('get_settings');
      this.notify('설정을 저장했어요.');
    });
  }

  // ================= step 1: photos (any of three views, each replaceable)
  async ensureTask() {
    if (this.task) return;
    this.survey = await this.api('create_survey', {draft: {survey_type: 'REGULAR', survey_date: today(), title: `빠른 분석 ${today()}`, investigator: '', department: '', process: '', occasional_reason: ''}});
    this.task = await this.api('create_task', {survey_id: this.survey.survey_id, draft: {task_name: '사진 분석 작업', input_template: 'GENERAL', conditions: {}}});
  }

  async setPhoto(view, path) {
    if (!path) return;
    await this.run('사진을 불러오고 있어요…', async () => {
      await this.ensureTask();
      const imported = await this.api('import_photos', {task_id: this.task.task_id, file_paths: [path]});
      if (!imported.added.length) throw new Error('사진을 읽지 못했어요. JPG·PNG 사진인지 확인해 주세요.');
      const old = this.photos[view];
      this.photos[view] = {photo: imported.added[0], image: await this.api('get_photo_preview', {photo: imported.added[0]})};
      this.stale = true;
      if (old) await this.discard(old.photo);
    });
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
    if (!Object.keys(this.photos).length) return;
    if (!this.stale && this.preview) { this.step = 'provisional'; return this.render(); }
    await this.run('사진을 분석하고 있어요…', async () => {
      const views = Object.fromEntries(Object.entries(this.photos).map(([view, item]) => [view, item.photo.photo_id]));
      this.preview = await this.api('quick_preview', {task_id: this.task.task_id, views});
      if (this.saved) {
        for (const [id, value] of Object.entries(savedAnswers(this.preview.questions, this.saved.task, this.saved.survey))) if (!(id in this.answers)) this.answers[id] = value;
        this.saved = null;
      }
      for (const q of this.preview.questions) if (q.suggested != null && !(q.id in this.answers)) this.answers[q.id] = q.suggested;
      this.stale = false; this.step = 'provisional'; this.group = 0;
    });
  }

  // ================= step 3: questions
  visible(q) {
    if (!q.show_if) return true;
    return Object.entries(q.show_if).every(([id, values]) => values.includes(this.answers[id]));
  }
  groups() {
    const names = [];
    for (const q of this.preview.questions) if (this.visible(q) && !names.includes(q.group)) names.push(q.group);
    return names.map(name => ({name, questions: this.preview.questions.filter(q => q.group === name && this.visible(q))}));
  }
  answered(q) {
    const a = this.answers[q.id];
    if (q.kind === 'text') return !q.required || String(a ?? '').trim() !== '';
    if (q.kind === 'criterion') return a?.present !== undefined;
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

  applyCriteria(input) {
    const a = this.answers;
    for (const q of this.preview.questions) {
      if (q.kind !== 'criterion') continue;
      const card = a[q.id];
      if (!card || card.present === 'UNKNOWN') continue;
      const criterion = input.legal.criteria[q.criterion - 1], note = `빠른 분석 질문: ${q.text}`;
      criterion.condition_present = card.present;
      criterion.evidence = evidence(note);
      if (q.mode === 'row') { criterion.rows = []; criterion.rows_complete = 'YES'; }
      if (card.present !== 'YES') continue;
      const row = {row_id: 'quick-1', label: '빠른 분석 입력', evidence: evidence(note)};
      for (const field of q.fields) {
        const value = card.values?.[field.key];
        const stored = value === undefined ? (field.type === 'truth' ? 'UNKNOWN' : null) : value;
        if (field.to.exposure) {
          const slot = input.legal.exposures.find(x => x.condition_code === field.to.exposure);
          slot.minutes = stored; slot.evidence = evidence(`${note} · ${field.label}`);
        } else if (field.to.criterion) criterion[field.to.criterion] = stored === null ? 'UNKNOWN' : stored;
        else row[field.to.row] = stored;
      }
      if (q.mode === 'row') criterion.rows = [row];
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
      camera_side: view === 'FRONT' ? 'FRONT' : !usable ? null : view, forward_direction: view === 'FRONT' || !usable ? null : a[`view_${view}`] ?? null,
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
    if (usable) for (const m of this.preview.measured) {
      const note = `빠른 분석: ${VIEW_LABEL[m.view]} ${m.label} ${m.angles.map(x => x.value_deg + '°').join('/')}`;
      if (m.view === primary) put(m.scope, m.field, m.value, 'AUTO_ACCEPTED', JSON.stringify({angles: m.angles, quick_preview: true}), 'OTHER');
      else put(m.scope, m.field, m.value, 'DIRECT_OBSERVATION', note + ' (사용자 확인)', 'DIRECT_OBSERVATION');
    }
    for (const q of this.preview.questions) {
      if (!this.visible(q) || !this.answered(q)) continue;
      const value = a[q.id], t = q.target;
      if (t.type === 'manual' && value !== 'UNKNOWN') put(t.scope, t.field, t.field === 'coupling' && load === 0 ? 'NOT_APPLICABLE' : value, 'INTERVIEW', `빠른 분석 질문: ${q.text}`);
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
    await this.run('최종 결과를 계산하고 있어요…', async () => {
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
      this.step = 'start'; this.preview = null; this.stale = true; this.result = null; this.review = {reviewer: this.review.reviewer, note: ''};
      this.notify('개선 후 사진으로 바꿔 넣고 "분석 시작"을 눌러 주세요. 이전 답변은 그대로 유지돼요.');
    });
  }

  // ================= step 5: review, AI explanation, Excel
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

  async enableAi() {
    await this.run('AI 설명을 켜고 있어요…', async () => {
      const settings = await this.api('get_settings');
      delete settings.gpt_key_present;
      Object.assign(settings, {gpt_enabled: true, gpt_model: settings.gpt_model || DEFAULT_MODEL});
      await this.api('update_settings', {settings});
      this.settings = await this.api('get_settings');
    });
  }

  async refreshResult() { this.result = await this.api('get_analysis', {analysis_id: this.result.analysis_id}); }

  async generateAi() {
    await this.run('AI가 설명을 쓰고 있어요… (5~15초 걸려요)', async () => {
      const current = this.settings || await this.api('get_settings');
      if (!(current.gpt_enabled && current.gpt_model)) {
        // Pressing the button is the opt-in (only the numeric summary is ever sent). Without a key this still yields an appliable plain explanation.
        const settings = await this.api('get_settings');
        delete settings.gpt_key_present;
        Object.assign(settings, {gpt_enabled: true, gpt_model: settings.gpt_model || DEFAULT_MODEL});
        await this.api('update_settings', {settings});
        this.settings = await this.api('get_settings');
      }
      await this.api('generate_ai_text', {analysis_id: this.result.analysis_id, purpose: 'TASK_EXPLANATION'});
      await this.refreshResult(); this.aiDraft = '';
    });
  }

  activeAi() { return (this.result.ai || []).filter(x => x.purpose === 'TASK_EXPLANATION').at(-1); }

  async applyAi(useEdited) {
    const ai = this.activeAi();
    await this.run('설명을 적용하고 있어요…', async () => {
      if (useEdited) await this.api('edit_ai_text', {analysis_id: this.result.analysis_id, text_id: ai.text_id, text: this.aiDraft});
      await this.api('apply_ai_text', {analysis_id: this.result.analysis_id, text_id: ai.text_id, use_edited: useEdited});
      await this.refreshResult(); this.aiDraft = '';
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
    else if (d.quick === 'new') { this.reset(); this.render(); }
    else if (d.quick === 'home') { this.reset(); this.step = 'home'; this.loadHome(); }
    else if (d.quick === 'settings') this.saveSettings();
    else if (d.quick === 'analyze') this.analyze();
    else if (d.quick === 'photos') { this.step = 'start'; this.render(); }
    else if (d.quick === 'questions') { this.step = 'questions'; this.group = 0; this.render(); }
    else if (d.quick === 'prev') { this.group = Math.max(0, this.group - 1); this.render(); window.scrollTo({top: 0}); }
    else if (d.quick === 'next') {
      if (this.group < this.groups().length - 1) { this.group++; this.render(); window.scrollTo({top: 0}); } else this.finish();
    }
    else if (d.quick === 'allno') this.allNo();
    else if (d.quick === 'review') { this.step = 'review'; this.render(); window.scrollTo({top: 0}); }
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
    const [id, key] = d.crit.split('|'), card = this.answers[id] ||= {present: undefined, values: {}};
    card.values ||= {};
    if (d.present) card.present = d.present;
    else if (d.chip !== undefined) card.values[key] = d.chip === '' ? null : Number(d.chip);
    else if (d.truth !== undefined) card.values[key] = d.truth;
    this.render();
  }

  allNo() {
    const group = this.groups()[this.group];
    for (const q of group.questions) if (q.kind === 'criterion' && this.answers[q.id]?.present === undefined) this.answers[q.id] = {present: 'NO', values: {}};
    this.render();
  }

  input(event) {
    const el = event.target;
    const d = el.dataset;
    if (d.number) {
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
      const [id, key] = d.cnum.split('|'), card = this.answers[id] ||= {present: undefined, values: {}};
      card.values ||= {};
      const raw = el.value.trim();
      card.values[key] = raw === '' ? undefined : Number(raw);
      if (event.type === 'change') this.render();
    } else if (d.rev) this.review[d.rev] = el.value;
    else if (d.aidraft !== undefined) this.aiDraft = el.value;
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
    const index = STEPS.findIndex(([id]) => id === this.step);
    const bar = this.step === 'home' ? '' : `<ol class="quick-steps">${STEPS.map(([id, label], i) => `<li class="${i < index ? 'done' : i === index ? 'current' : ''}">${i + 1}. ${label}</li>`).join('')}</ol>`;
    const body = {home: () => this.viewHome(), start: () => this.viewStart(), provisional: () => this.viewProvisional(), questions: () => this.viewQuestions(), result: () => this.viewResult(), review: () => this.viewReview()}[this.step]();
    const busy = typeof this.busy === 'string' && this.busy ? `<div class="quick-busy" role="status">${esc(this.busy)}</div>` : '';
    this.host.innerHTML = `${bar}${busy}${body}`;
  }

  viewHome() {
    const list = (this.surveys || []).slice().sort((a, b) => (b.survey_date || '').localeCompare(a.survey_date || '') || b.survey_id - a.survey_id);
    const s = this.settings || {};
    const badge = x => x.review_current ? '<span class="badge current">검토 완료</span>' : '<span class="badge none">미검토</span>';
    return `<section class="panel quick-hero"><h2>작업 사진 한 장으로 REBA와 법정 기준 초안을 만들어요</h2>
      <p>사진을 넣고, 로코의 질문에 버튼으로 답하면 결과와 Excel까지 이 화면에서 끝나요.</p>
      <button class="primary" data-quick="new" ${this.busy ? 'disabled' : ''}>＋ 새 분석 시작</button></section>
      <section class="panel"><h3>최근 분석</h3>${list.length ? `<ul class="quick-list">${list.map(x => `<li>
        <div><strong>${esc(x.title || '제목 없음')}</strong><span>${esc(x.survey_date || '')} · 작업 ${x.task_count}개 ${badge(x)}</span></div>
        <div class="quick-list-actions"><button data-open="${x.survey_id}">열기</button>
        <button class="${this.confirmDelete === x.survey_id ? 'danger' : ''}" data-del="${x.survey_id}">${this.confirmDelete === x.survey_id ? '정말 삭제' : '삭제'}</button></div></li>`).join('')}</ul>` : '<p class="quick-note">아직 분석이 없어요. "새 분석 시작"을 눌러 보세요.</p>'}</section>
      <details class="panel quick-settings"><summary>설정</summary>
        <p class="quick-note">AI 설명은 계산 결과를 쉬운 말로 풀어 줄 뿐, 해당 여부나 점수를 바꾸지 않아요. 키는 PC 환경변수 OPENAI_API_KEY에서 읽고 화면·DB에는 저장하지 않아요. ${s.gpt_key_present ? '<b>키가 설정되어 있어요.</b>' : '<b>키가 아직 없어요.</b>'}</p>
        <div class="quick-setting-row"><label>AI 설명 <select data-setting="gpt_enabled"><option value="YES" ${s.gpt_enabled ? 'selected' : ''}>사용</option><option value="NO" ${s.gpt_enabled ? '' : 'selected'}>사용 안 함</option></select></label>
        <label>모델 <input data-setting="gpt_model" value="${esc(s.gpt_model || DEFAULT_MODEL)}" placeholder="${DEFAULT_MODEL}"></label>
        <button data-quick="settings">저장</button></div></details>`;
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
      <div class="quick-nav"><button data-quick="home">← 처음으로</button><button class="primary" data-quick="analyze" ${count && !this.busy ? '' : 'disabled'}>${this.preview && !this.stale ? '1차 점수 보기 →' : '분석 시작 →'}</button></div>`;
  }

  pointsFor(view) {
    const fromPreview = this.preview?.views?.[view]?.points;
    if (fromPreview) return fromPreview;
    const id = this.photos[view]?.photo.photo_id;
    return this.result?.pose?.slots?.find(slot => slot.photo_id === id)?.points || [];
  }

  photoStrip() {
    const views = VIEWS.filter(view => this.photos[view.id]);
    return `<div class="quick-strip ${views.length > 1 ? 'multi' : ''}">${views.map(view => {
      const item = this.photos[view.id];
      const w = item.image.width_px, h = item.image.height_px, r = Math.max(w, h) / 120;
      const p = Object.fromEntries(this.pointsFor(view.id).filter(x => x.confidence >= 0.3).map(x => [x.name, x]));
      const lines = BONES.filter(([a, b]) => p[a] && p[b]).map(([a, b]) => `<line x1="${p[a].x_px}" y1="${p[a].y_px}" x2="${p[b].x_px}" y2="${p[b].y_px}"/>`).join('');
      const dots = Object.values(p).map(x => `<circle cx="${x.x_px}" cy="${x.y_px}" r="${r}"/>`).join('');
      return `<figure class="quick-photo"><img src="${item.image.data_url}" alt="${esc(VIEW_LABEL[view.id])}"><svg viewBox="0 0 ${w} ${h}" preserveAspectRatio="xMidYMid meet" style="--r:${r}px">${lines}${dots}</svg><figcaption>${esc(VIEW_LABEL[view.id])}</figcaption></figure>`;
    }).join('')}${this.reopened || this.step === 'review' ? '' : '<button type="button" class="quick-change" data-quick="photos">사진 바꾸기</button>'}</div>`;
  }

  viewProvisional() {
    const pv = this.preview, s = pv.score;
    const side = m => m.scope === 'COMMON' ? '' : m.scope === 'LEFT' ? '왼쪽 ' : '오른쪽 ';
    const measured = pv.measured.map(m => `<li><strong>${esc(m.label)}</strong> ${m.angles.map(a => `${a.value_deg}°`).join(' / ')} → ${esc(side(m))}${esc(VALUE_KO[m.value] || m.value + '단계')} <small>${esc(VIEW_LABEL[m.view])}</small>${m.boundary_review ? ' <em>경계값</em>' : ''}</li>`).join('');
    const front = pv.front.map(f => `<li><strong>${esc(f.label)}</strong> ${f.value_deg}° ${f.suggested ? '→ <em>있음으로 제안</em>' : '→ 거의 없음'}</li>`).join('');
    return `<div class="quick-columns">${this.photoStrip()}
      <section class="panel quick-score">
        <h2>1차 REBA 점수</h2>
        ${s ? `<div class="quick-big"><strong>${s.total}</strong><span>점 · ${esc(RISK[s.risk] || s.risk)}</span></div>
          <p class="quick-note">${esc(s.assumption)}</p>` : '<p class="quick-note">사진에서 측정한 값이 없어 1차 점수를 내지 못했어요. 질문에 답하면 계산할 수 있어요.</p>'}
        <h3>사진에서 측정한 값</h3>
        <ul class="quick-measured">${measured || '<li>측면 사진에서 측정한 값이 없어요.</li>'}</ul>
        ${front ? `<h3>정면·후면 사진 제안</h3><ul class="quick-measured">${front}</ul>` : ''}
        ${pv.diagnostics.map(d => `<p class="quick-warn">${esc(d.message)}</p>`).join('')}
        <div class="quick-nav"><button data-quick="photos">← 사진 바꾸기</button><button class="primary" data-quick="questions">로코의 질문에 답하기 →</button></div>
      </section></div>`;
  }

  critCard(q) {
    const card = this.answers[q.id] || {}, values = card.values || {};
    const pick = (present, label) => `<button type="button" class="${card.present === present ? 'selected' : ''}" data-crit="${esc(q.id)}" data-present="${present}">${label}</button>`;
    const fields = card.present === 'YES' ? q.fields.map(f => {
      const key = `${q.id}|${f.key}`, value = values[f.key];
      if (f.type === 'truth') return `<div class="quick-field"><label>${esc(f.label)}</label><div class="quick-choices">${[['YES', '예'], ['NO', '아니오'], ['UNKNOWN', '모름']].map(([v, l]) => `<button type="button" class="${value === v ? 'selected' : ''}" data-crit="${esc(key)}" data-truth="${v}">${l}</button>`).join('')}</div></div>`;
      return `<div class="quick-field"><label>${esc(f.label)}</label><div class="quick-number"><input type="number" min="0" ${f.maximum ? `max="${f.maximum}"` : ''} step="any" inputmode="decimal" data-cnum="${esc(key)}" value="${value ?? ''}"><span>${esc(f.unit)}</span>
        <div class="quick-choices">${f.chips.map(c => `<button type="button" class="${value === c ? 'selected' : ''}" data-crit="${esc(key)}" data-chip="${c}">${c}</button>`).join('')}<button type="button" class="${value === null ? 'selected' : ''}" data-crit="${esc(key)}" data-chip="">모름</button></div></div></div>`;
    }).join('') : '';
    return `<article class="quick-q crit ${card.present !== undefined ? 'answered' : ''}"><h3>${esc(q.text)}${q.hint ? ' <small class="quick-hint">사진 제안</small>' : ''}</h3><p class="quick-ask-text">${esc(q.ask)}</p>${q.help ? `<p>${esc(q.help)}</p>` : ''}
      <div class="quick-choices">${pick('YES', '예')}${pick('NO', '아니오')}${pick('UNKNOWN', '모름')}</div>${fields}</article>`;
  }

  question(q) {
    if (q.kind === 'criterion') return this.critCard(q);
    const value = this.answers[q.id];
    let body = '';
    if (q.kind === 'choice') body = `<div class="quick-choices">${q.choices.map(c => `<button type="button" class="${value !== undefined && String(value) === String(c.value) ? 'selected' : ''}" data-answer="${esc(q.id)}" data-value="${esc(c.value)}">${esc(c.label)}${q.suggested != null && String(q.suggested) === String(c.value) ? ' <small>추정</small>' : ''}</button>`).join('')}</div>`;
    if (q.kind === 'number') body = `<div class="quick-number"><input type="number" min="0" ${q.maximum ? `max="${q.maximum}"` : ''} inputmode="decimal" data-number="${esc(q.id)}" value="${value ?? ''}" aria-label="${esc(q.text)}"><span>${esc(q.unit)}</span>
      <div class="quick-choices">${q.chips.map(c => `<button type="button" class="${value === c ? 'selected' : ''}" data-answer="${esc(q.id)}" data-value="${c}">${c}${esc(q.unit)}</button>`).join('')}<button type="button" class="${value === null ? 'selected' : ''}" data-answer="${esc(q.id)}" data-value="">모름</button></div></div>`;
    if (q.kind === 'checklist') body = `<div class="quick-flags">${q.items.map(item => `<label><input type="checkbox" data-flag="${esc(q.id)}" value="${esc(item.key)}" ${(value || []).includes(item.key) ? 'checked' : ''}> ${esc(item.label)}${item.suggested ? ` <small class="quick-hint">사진 제안 · ${esc(item.evidence)}</small>` : ''}</label>`).join('')}</div>`;
    if (q.kind === 'text') body = `<input type="text" class="quick-text" maxlength="${q.maxlength}" data-text="${esc(q.id)}" value="${esc(value ?? '')}" placeholder="${esc(q.placeholder)}" aria-label="${esc(q.text)}">`;
    return `<article class="quick-q ${this.answered(q) && (q.kind !== 'text' || String(value ?? '').trim()) ? 'answered' : ''}"><h3>${esc(q.text)}${q.required ? ' <small>필수</small>' : ''}</h3>${q.help ? `<p>${esc(q.help)}</p>` : ''}${body}</article>`;
  }

  viewQuestions() {
    const groups = this.groups(), group = groups[Math.min(this.group, groups.length - 1)];
    for (const q of group.questions) if (q.kind === 'checklist' && this.answers[q.id] === undefined) this.answers[q.id] = q.items.filter(i => i.suggested).map(i => i.key);
    const ready = this.groupReady(group), last = this.group >= groups.length - 1;
    const hasCards = group.questions.some(q => q.kind === 'criterion');
    return `<div class="quick-columns">${this.photoStrip()}
      <section class="panel quick-ask">
        <div class="quick-loco"><b>로코</b> ${esc(group.name)} (${this.group + 1}/${groups.length})</div>
        ${hasCards ? '<div class="quick-bulk"><button type="button" data-quick="allno">아직 답하지 않은 기준은 모두 "아니오"로 (직접 확인했어요)</button></div>' : ''}
        ${group.questions.map(q => this.question(q)).join('')}
        ${ready ? '' : '<p class="quick-note">모든 질문에 답해 주세요. 모르면 "모름"을 고르면 돼요. 숫자는 0 이상이고, 하루 시간은 1440분 이하예요.</p>'}
        <div class="quick-nav"><button data-quick="prev" ${this.group === 0 ? 'disabled' : ''}>← 이전</button>
          <button class="primary" data-quick="next" ${ready && !this.busy ? '' : 'disabled'}>${last ? '최종 결과 계산 →' : '다음 →'}</button></div>
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
    return `<h2>최종 REBA 점수</h2><div class="quick-big"><strong>${slot.total}</strong><span>점 · ${esc(RISK[slot.risk] || slot.risk)}</span></div>
      <p class="quick-note">왼쪽 ${slot.left.total ?? '—'}점 · 오른쪽 ${slot.right.total ?? '—'}점 중 높은 쪽(${side})${first}</p>`;
  }

  criteriaRows(editable) {
    const rows = this.result.judgment?.judgments || [];
    return `<table class="quick-table"><thead><tr><th>기준</th><th>계산 초안</th>${editable ? '<th>조사자 결론</th>' : ''}</tr></thead><tbody>${rows.map(j => {
      const inv = j.investigator?.status ?? null;
      const conclude = editable ? `<td><div class="quick-choices small"><button type="button" class="${inv === 'APPLICABLE' ? 'selected' : ''}" data-concl="${j.criterion_no}" data-status="APPLICABLE">해당</button><button type="button" class="${inv === 'NOT_APPLICABLE' ? 'selected' : ''}" data-concl="${j.criterion_no}" data-status="NOT_APPLICABLE">비해당</button></div></td>` : '';
      return `<tr><td>${j.criterion_no}호 · ${esc(CRIT_NAME[j.criterion_no])}</td><td><span class="quick-status ${esc(j.computed_status)}">${esc(STATUS[j.computed_status] || j.computed_status)}</span>${(j.missing_fields || []).length ? ` <small>추가 입력 ${j.missing_fields.length}개</small>` : ''}</td>${conclude}</tr>`;
    }).join('')}</tbody></table>`;
  }

  comparePanel() {
    const c = this.comparison;
    if (!c) return '';
    const label = x => STATUS[x] || x || '—';
    const changed = c.criteria.filter(x => x.before_status !== x.after_status);
    const delta = c.reba_max_delta;
    return `<section class="panel quick-compare"><h3>개선 전후 비교</h3>
      <div class="quick-big small"><strong>${delta == null ? '—' : (delta > 0 ? '+' : '') + delta}</strong><span>REBA 최대 점수 변화 ${delta == null ? '(비교할 수 없어요)' : delta < 0 ? '(낮아졌어요)' : delta > 0 ? '(높아졌어요)' : '(같아요)'}</span></div>
      ${changed.length ? `<ul class="quick-measured">${changed.map(x => `<li>${x.criterion_no}호 ${esc(CRIT_NAME[x.criterion_no])}: ${esc(label(x.before_status))} → <strong>${esc(label(x.after_status))}</strong></li>`).join('')}</ul>` : '<p class="quick-note">기준 판정이 바뀐 항목은 없어요.</p>'}
      ${(c.notes || []).map(n => `<p class="quick-note">${esc(n)}</p>`).join('')}
      <p class="quick-note">입력값 변경 ${c.condition_changes.length}건은 Excel의 전후 비교 시트에 모두 담겨요.</p></section>`;
  }

  viewResult() {
    return `<div class="quick-columns">${this.photoStrip()}
      <div><section class="panel quick-score">${this.rebaPanel()}
        <h3>법정 기준 11개 초안</h3>${this.criteriaRows(false)}
        <p class="quick-note">초안은 입력한 값으로 계산한 결과예요. 최종 해당 여부는 조사자가 검토해 정해요.</p>
        <div class="quick-nav"><button data-quick="home">처음으로</button><button class="primary" data-quick="review">검토하고 설명·Excel 만들기 →</button></div></section>
        ${this.comparePanel()}</div></div>`;
  }

  aiPanel() {
    const s = this.settings || {};
    const ai = this.activeAi();
    let body = '<p class="quick-note">AI에는 계산된 숫자 요약만 보내요. 이름·사진·메모는 보내지 않아요.</p>';
    if (!s.gpt_key_present) body = '<p class="quick-warn">AI 키(OPENAI_API_KEY)가 이 PC에 없어요. 없어도 "기본 설명"을 만들 수 있어요.</p>';
    body += `<div class="quick-nav left"><button class="primary" data-quick="gen-ai" ${this.busy ? 'disabled' : ''}>${ai ? '설명 다시 만들기' : (s.gpt_key_present ? 'AI 설명 만들기' : '기본 설명 만들기')}</button></div>`;
    if (ai) {
      const text = this.aiDraft || ai.edited_text || ai.generated_text;
      const kind = ai.result === 'GENERATED' ? 'AI가 쓴 설명' : '기본 설명(AI를 쓰지 못했어요)';
      const reason = ai.result === 'DISABLED' ? AI_REASON.DISABLED : (AI_REASON[ai.fallback_reason] || ai.fallback_reason || '');
      body += `<p class="quick-note">${esc(kind)}${ai.result !== 'GENERATED' ? ` · 이유: ${esc(reason)}` : ''}${ai.is_active ? ' · <b>적용 중</b>' : ''}</p>
        <textarea class="quick-ai" rows="9" data-aidraft>${esc(text)}</textarea>
        <div class="quick-nav left"><button data-quick="apply-ai">이 설명 적용</button><button data-quick="apply-edited">고친 내용으로 적용</button></div>
        <p class="quick-note">설명은 보고서에 들어갈 문장일 뿐, 계산 결과와 판정은 바뀌지 않아요.</p>`;
    }
    return `<section class="panel"><h3>③ 쉬운 설명</h3>${body}</section>`;
  }

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
      <section class="panel"><h3>④ Excel로 저장</h3>
        <p class="quick-note">요약·작업별 결과·확인사항·판정 근거 시트가 한글로 만들어져요.${this.comparison ? ' 개선 전후 비교도 함께 들어가요.' : ''}</p>
        ${this.exported ? `<p class="quick-ok">저장한 파일: ${esc(this.exported.file_path)}</p>` : ''}
        <div class="quick-nav left"><button class="primary" data-quick="excel">Excel로 저장</button></div></section>
      <section class="panel"><h3>⑤ 그다음</h3>
        <div class="quick-nav left"><button data-quick="result">← 결과 보기</button>
          <button data-quick="improve">개선 후 사진으로 다시 비교</button>
          <button data-quick="home">처음으로</button><button class="quick-advanced" data-quick="detail">고급 편집</button></div></section>${this.comparePanel()}</div></div>`;
  }
}
