// Synthetic example survey for first-time users and demos; no real worker or health data.
const today = () => new Date().toLocaleDateString('sv-SE', {timeZone: 'Asia/Seoul'});
const TASK_KEYS = ['schema_version', 'task_kind', 'task_name', 'input_template', 'worker_count',
  'conditions', 'legal', 'capture', 'manual', 'analysis_scope', 'legacy_input'];

export async function createSampleSurvey(api) {
  const survey = await api('create_survey', {draft: {
    survey_type: 'REGULAR', survey_date: today(),
    investigator: '샘플 조사자', department: '총무팀', process: '문서 입력 공정',
    title: '[샘플] 사무실 문서 입력 정기 조사', occasional_reason: '',
    workplace_situation: {
      equipment_status: 'NO', equipment_notes: '샘플: 설비 변경 없음',
      workload_status: 'NO', workload_notes: '샘플: 작업량 변화 없음',
      speed_status: 'NO', speed_notes: '', work_pattern_status: 'NO', work_pattern_notes: ''
    },
    participation: {
      status: 'YES', role: 'AFFECTED_WORKER', participant_code: '샘플-001',
      method: 'INTERVIEW', date: today(), notes: '샘플 면담'
    },
    symptom_survey: {
      method: 'INTERVIEW', date: today(), respondent_count: 1,
      summary: '샘플 응답입니다. 실제 건강자료가 아닙니다.', responses: []
    }
  }});
  const created = await api('create_task', {survey_id: survey.survey_id, draft: {
    task_name: '[샘플] 키보드 문서 입력', input_template: 'OFFICE',
    conditions: {
      worker_code: '작업자 A', daily_work_min: 480, one_off: 'NO', annual_work_days: 220,
      work_posture: '앉은 자세로 키보드와 마우스를 사용한다.',
      method_description: '문서를 보고 시스템에 입력한다.'
    }
  }});
  const input = Object.fromEntries(TASK_KEYS.map(key => [key, structuredClone(created[key])]));
  input.worker_count = 2;
  input.legal.criteria[0].condition_present = 'YES';
  input.legal.criteria[0].evidence.text = '샘플: 하루 약 4시간 키보드 입력 작업(면담)';
  input.legal.exposures[0].minutes = 240;
  await api('save_task_input', {task_id: created.task_id, input, expected_revision: created.input_revision});
  return {survey, task: created};
}
