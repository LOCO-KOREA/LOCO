// Opt-in writing hints; missing keys and numeric/date controls have no hint.
// These strings never become input values or saved data.
export function inputPlaceholder(label, type = 'text', key = '') {
  if (!['text', 'textarea'].includes(type)) return '';
  const withExample = (topic, example) => `${topic} 작성하세요.${type === 'textarea' ? '\n' : ' '}예: ${example}`;
  const hints = {
    task_name: ['작업명을', '부품 조립'],
    'conditions.worker_code': ['작업자 코드를', '작업자 A'],
    'conditions.work_posture': ['신체 자세와 지지 상태를', '서서 허리를 굽히고 팔을 앞으로 뻗어 부품을 집음'],
    'conditions.method_description': ['작업 수행 순서를', '부품 집기 → 작업대에 놓기 → 조립 → 완성품 이동'],
    'conditions.hazard_factors': ['관찰한 부담 요인을', '같은 손목 동작 반복, 팔을 뻗은 자세 유지'],
    'conditions.hazard_causes': ['유해요인이 생기는 원인을', '부품함이 멀리 있어 팔을 뻗어야 함'],
    'conditions.improvement_recommendations': ['검토할 개선 방법과 확인사항을', '부품함 위치 변경과 작업대 높이 조절 가능 여부 검토'],
    'conditions.evidence.text': ['작업 조건을 확인한 방법과 근거를', '현장 관찰·작업자 면담·작업일지를 대조함'],
    equipment_notes: ['현재 설비와 변경 내용을', '높이 고정 작업대를 사용 중이며 최근 설비 변경 없음'],
    workload_notes: ['현재 작업량과 변경 내용을', '제품 종류가 늘어 포장 작업량이 증가함'],
    speed_notes: ['현재 작업 속도와 변경 내용을', '컨베이어 속도를 높인 뒤 조립 간격이 짧아짐'],
    work_pattern_notes: ['현재 업무 형태와 변경 내용을', '주간 고정 근무에서 주·야간 교대근무로 변경됨'],
    participant_code: ['참여자 코드를', '참여자 A'],
    participation_notes: ['참여자가 제기한 문제점과 개선 의견을', '부품을 집을 때 팔을 뻗어야 하므로 부품함을 가까이 두자는 의견'],
    symptom_summary: ['보고된 증상과 조사 결과를', '어깨 불편 호소가 있어 추가 면담 예정'],
    response_code: ['익명 응답 코드를', '익명-001'],
    response_department: ['작업부서를', '생산팀'],
    response_job: ['수행 작업을', '제품 포장'],
    response_current_work: ['주로 하는 작업을', '상자를 접어 제품을 담고 테이프로 포장함'],
    response_rest_breaks: ['휴식 횟수와 시간을', '오전·오후 각 10분씩 휴식'],
    response_previous_work: ['이전 작업을', '창고에서 부품 분류'],
    response_leisure: ['여가·취미 활동을', '자전거 타기'],
    response_injury_sites: ['상해 부위를', '목, 어깨, 허리'],
    'review-note': ['검토 의견을', '야간 작업 구간 추가 관찰 필요'],
    'comparison-note': ['비교 내용을', '작업대 높이 조정 전후 비교'],
    'manual-evidence': ['직접 확인한 근거를', '측면 관찰로 목의 숙임과 지지 여부 확인'],
    'inv.reason': ['판단 이유를', '작업 자세와 하루 노출 기록을 대조함'],
    'inv.evidence': ['판단 근거를', '현장 관찰표와 작업자 면담 기록 확인'],
    'photo.label': ['사진 표시명을', '작업대 앞 부품 조립'],
    'photo.path': ['사진 경로를', 'D:\\작업사진\\사진01.jpg'],
    'photo.evidence': ['관찰 내용과 확인 방법을', '측면에서 팔을 뻗는 자세를 관찰하고 취급 물체는 현장에서 저울로 측정함'],
    'analysis.explanation': ['계산 결과와 근거를 확인해 설명을', '직접 확인한 내용과 추가 관찰이 필요한 내용을 구분해 기록함'],
    'analysis.improvement': ['실제 작업 조건을 확인해 개선 검토 내용을', '작업대 높이 조절 가능 여부와 적용 시 작업 동선을 현장에서 검토함'],
  };
  if (Object.hasOwn(hints, key)) return withExample(...hints[key]);
  if (/^legal\.exposures\.\d+\.evidence\.text$/.test(key)) {
    return withExample('하루 노출시간을 확인한 방법과 근거를', '작업일지의 시작·종료 시각과 작업자 면담 내용을 대조함');
  }
  if (/^legal\.criteria\.\d+\.rows\.\d+\.label$/.test(key)) {
    return withExample('조건 행 이름을', '오전 부품 운반');
  }
  if (/^legal\.criteria\.\d+\.rows\.\d+\.union_evidence\.text$/.test(key)) {
    return withExample('자세별 들기 횟수의 중복을 제외한 방법을', '무릎 아래·팔 뻗음에 함께 해당하는 같은 들기는 한 번만 집계함');
  }
  const row = /^legal\.criteria\.(\d+)\.rows\.\d+\.evidence\.text$/.exec(key);
  if (row) {
    // Criteria paths are zero-based: index 5 is criterion 6.
    const hint = {
      5: ['손가락 집기 중량·힘과 시간을 확인한 근거를', '중량·힘 측정 기록과 손가락 집기 작업의 비지지 구간 시간을 대조함'],
      6: ['한 손 중량·힘과 시간을 확인한 근거를', '중량·쥐기 힘 측정 기록과 한 손 작업의 비지지 구간 시간을 대조함'],
      7: ['중량과 하루 들기 횟수를 확인한 근거를', '같은 중량의 물체를 드는 횟수를 하루 작업 기록에서 집계함'],
      8: ['중량과 자세별 들기 횟수를 확인한 근거를', '물체 중량을 측정하고 같은 들기 동작의 높이·팔 뻗음 여부를 관찰표에 기록함'],
      9: ['중량·분당 들기 횟수·지속시간을 확인한 근거를', '같은 중량을 다루는 구간의 들기 횟수와 시작·종료 시각을 기록함'],
      10: ['실제 충격 여부·횟수·지속시간을 확인한 근거를', '손으로 물체에 충격을 가하는 구간의 횟수와 시간을 현장에서 기록함'],
    }[row[1]];
    return hint ? withExample(...hint) : '';
  }
  if (/^legal\.criteria\.8\.totals\.evidence\.text$/.test(key)) {
    return withExample('선택한 조건 행의 횟수를 중복 없이 집계한 방법을', '선택 행의 자세별 횟수를 모으고 같은 들기 동작은 한 번만 집계함');
  }
  const union = /^legal\.criteria\.(\d+)\.union\.evidence\.text$/.exec(key);
  if (union) return union[1] === '7'
    ? withExample('선택한 조건 행의 횟수를 중복 없이 집계한 방법을', '행별 들기 기록을 대조하고 같은 들기는 한 번만 집계함')
    : withExample('선택한 조건 행의 겹치는 시간을 제외한 방법을', '행별 시작·종료 시각을 대조하고 겹친 구간은 한 번만 포함함');
  if (/^legal\.criteria\.\d+\.evidence\.text$/.test(key)) {
    return withExample('작업조건과 입력 수치를 확인한 방법·자료를', '현장 관찰표·작업일지·작업자 면담 내용을 대조함');
  }
  return '';
}
