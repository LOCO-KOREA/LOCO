"""Human-readable report messages. Stored DTO codes remain unchanged."""
MANUAL = {'trunk_base': '몸통 굽힘', 'trunk_twisted': '몸통 비틀림', 'trunk_side_bent': '몸통 옆으로 기울임', 'neck_base': '목 굽힘', 'neck_twisted': '목 비틀림', 'neck_side_bent': '목 옆으로 기울임', 'legs_support': '다리 지지', 'seated': '앉아서 작업', 'knee_band': '무릎 굽힘', 'shock_force': '갑작스러운 큰 힘·충격', 'static_over_1min': '같은 자세를 1분 넘게 유지', 'small_repeat_over_4min': '좁은 동작을 1분에 4번 넘게 반복', 'rapid_change_or_unstable': '자세가 크게 바뀌거나 불안정', 'upper_arm_base': '위팔 들림', 'arm_abducted_or_rotated': '팔을 옆으로 벌리거나 돌림', 'shoulder_raised': '어깨를 으쓱 듦', 'arm_supported_or_gravity_assisted': '팔을 받치거나 기댐', 'lower_arm_base': '팔꿈치 각도', 'wrist_base': '손목 꺾임', 'wrist_deviated_or_twisted': '손목 비틂·옆으로 꺾음', 'coupling': '손잡이·잡는 상태', 'hand_above_head': '손이 머리 위', 'elbow_above_shoulder': '팔꿈치가 어깨 위', 'elbow_behind_trunk': '팔꿈치가 몸통 뒤', 'squat': '쪼그림', 'kneel': '무릎 꿇음'}

INPUTS = {'box_mass_kg': '상자 전체 중량', 'shelf_height_cm': '선반 상판 높이', 'daily_work_min': '하루 실제 작업시간', 'one_off': '1회성 작업 여부', 'planned_duration_months': '예정 작업기간', 'annual_work_days': '연간 작업일수', 'lift_count_day': '하루 들기 횟수', 'condition_present': '해당 작업조건 존재', 'unsupported': '신체·물체가 지지되지 않는 조건', 'posture_restricted': '자세를 자유롭게 바꾸기 어려운 조건', 'posture_interpretation_pending': '자세 해석 확인', 'pinch_mass_kg': '한손 손가락 집기 중량', 'pinch_force_kg_equiv': '손가락에 가해지는 힘', 'single_hand_mass_kg': '한손 들기 중량', 'grip_force_kg_equiv': '한손 쥐기 힘', 'below_knee_count_day': '무릎 아래에서 들기', 'above_shoulder_count_day': '어깨 위에서 들기', 'extended_arm_count_day': '팔을 뻗어 들기', 'union_count_day': '중복을 제외한 들기 횟수', 'lift_rate_min': '작업 중 분당 들기 횟수', 'impact_rate_hour': '작업 중 시간당 충격 횟수', 'effective_load_kg': '적용 하중', 'photo_id': '사진 배정'}

EXPOSURES = {'C1_KEYBOARD_FOCUSED': '집중 키보드·마우스 사용', 'C2_NECK': '목 반복 동작', 'C2_SHOULDER': '어깨 반복 동작', 'C2_ELBOW': '팔꿈치 반복 동작', 'C2_WRIST': '손목 반복 동작', 'C2_HAND': '손 반복 동작', 'C3_UNION': '손·팔을 높이 드는 자세의 합친 시간(중복 제외)', 'C4_NECK_FLEX': '목 앞굽힘', 'C4_TRUNK_FLEX': '몸통 앞굽힘', 'C4_TRUNK_EXT': '몸통 뒤로 젖힘', 'C4_NECK_TWIST': '목 비틀림', 'C4_TRUNK_TWIST': '몸통 비틀림', 'C4_UNION': '허리·목 자세를 합친 시간(중복 제외)', 'C5_SQUAT': '쪼그림', 'C5_KNEEL': '무릎 굽힘', 'C5_UNION': '쪼그림·무릎 굽힘을 합친 시간(중복 제외)', 'C6_QUALIFYING': '한손 집기·힘 조건의 작업', 'C7_QUALIFYING': '한손 들기·힘 조건의 작업', 'C10_LIFT': '반복 들기', 'C11_IMPACT': '손·무릎 반복 충격'}

REASONS = {'COMBINATION_RULE': '여러 조건을 합산하는 해석 확인 필요', 'POSTURE_INTERPRETATION': '자세 정의·해석 확인 필요', 'BOUNDARY_REVIEW': '점수 경계 ±5° 이내 · 자세 재확인', 'INPUT_CONFLICT': '입력값 사이의 모순 또는 범위 확인 필요'}

def input_label(path):
    parts = str(path).split('.')
    exposure = next((p for p in parts if p in EXPOSURES), None)
    if exposure:
        return EXPOSURES[exposure] + ' 시간'
    field = parts[-1]
    if field == 'rows_complete':
        return '하루의 모든 해당 조건 행 기록 여부'
    if field == 'value' and len(parts) >= 2 and parts[-2] == 'union':
        return '적격 행의 중복 제거 합집합 수치'
    name = INPUTS.get(field, MANUAL.get(field, RESULT_LABELS.get(field, str(path))))
    scope = {'common':'공통', 'left':'왼쪽', 'right':'오른쪽'}.get(parts[0])
    return scope + ' · ' + name if scope else name


def reason_label(code):
    return REASONS.get(code, code)


def investigator_text(value):
    evidence = value.get('evidence') or {}
    sources = {'DIRECT_OBSERVATION':'직접 관찰', 'INTERVIEW':'면담', 'DOCUMENT':'문서', 'OTHER':'기타'}
    lines = []
    for label, text in [('사유',value.get('reason')), ('근거',evidence.get('text')), ('출처',sources.get(evidence.get('source'))), ('관찰 시각',evidence.get('observed_at'))]:
        if text is not None and text != '':
            lines.append(label + ': ' + str(text))
    return '\n'.join(lines)


# The eleven statutory criteria in everyday words. The legal number is only a reference and never leads a sentence.
CRITERIA = {1: '키보드·마우스 집중 입력', 2: '같은 동작 반복', 3: '손·팔의 부담 자세', 4: '목·허리 굽힘·비틀림', 5: '쪼그림·무릎 굽힘', 6: '한 손 손가락 집기', 7: '한 손 들기·쥐기', 8: '25kg 이상 들기', 9: '10kg 이상 불편한 위치 들기', 10: '반복 들기', 11: '손·무릎 충격'}


def criterion_name(no):
    return f'{CRITERIA.get(no, "기준")}(법정 {no}호)'


def josa(word, with_final, without_final):
    """Pick the Korean particle by whether the last syllable of the word ends in a consonant (받침)."""
    for char in reversed(str(word)):
        if '\uac00' <= char <= '\ud7a3':
            return with_final if (ord(char) - 0xAC00) % 28 else without_final
    return with_final


# What each calculation step is called for a reader, and what to do when it is incomplete.
MODULE_PLAIN = {'pose': '사진에서 자세 읽기', 'tags': '자세 표시', 'reba': 'REBA 점수', 'judgment': '법정 기준 판정'}
INCOMPLETE = {
    'pose': '사진에서 자세를 읽은 결과 중 일부가 비어 있어요. 몸이 가려졌거나 잘 안 보이는 사진이 있을 수 있어요.',
    'tags': '자세 표시(사진에서 몸통·목·팔 자세가 보인 횟수) 결과가 일부 비어 있어요.',
    'reba': 'REBA 점수를 일부 계산하지 못했어요. 필요한 자세 입력을 채우면 계산돼요.',
    'judgment': '법정 기준 중 입력이나 검토가 더 필요한 항목이 있어요.',
}
AI_REASON_KO = {'DISABLED': 'AI 설명 설정이 꺼져 있음', 'NO_API_KEY': '이 PC에 AI 키가 없음', 'MODEL_NOT_CONFIGURED': 'AI 모델이 정해지지 않음', 'TIMEOUT': 'AI 응답이 늦어짐',
                'API_ERROR': 'AI 서버에 연결하지 못함', 'INVALID_STRUCTURED_CONTENT': 'AI 응답 형식이 맞지 않음', 'INCOMPLETE_RESPONSE': 'AI 응답이 끝까지 오지 않음',
                'REFUSAL_OR_EMPTY_RESPONSE': 'AI가 답을 주지 않음', 'OPENAI_SDK_MISSING': 'AI 연결 부품이 없음'}

# Field names for the values people type in (shared by the detailed record and the plain sheets).
RESULT_LABELS = {'worker_code': '작업자 코드', 'method_description': '작업 방법', 'work_posture': '작업 자세', 'work_height_cm': '작업 높이', 'daily_work_min': '하루 실제 작업시간', 'one_off': '일회성 여부', 'planned_duration_months': '예정 작업기간', 'annual_work_days': '연간 작업일수', 'condition_present': '해당 작업조건 존재', 'unsupported': '지지 여부', 'posture_restricted': '자세 변경 제한', 'pinch_mass_kg': '손가락 집기 중량', 'pinch_force_kg_equiv': '손가락 힘', 'single_hand_mass_kg': '한 손 중량', 'grip_force_kg_equiv': '쥐기 힘', 'load_mass_kg': '물체 중량', 'lift_count_day': '하루 들기 횟수', 'below_knee_count_day': '무릎 아래 횟수', 'above_shoulder_count_day': '어깨 위 횟수', 'extended_arm_count_day': '팔 뻗음 횟수', 'union_count_day': '중복 제거 횟수', 'lift_rate_min': '분당 들기 횟수', 'impact_rate_hour': '시간당 충격 횟수', 'minutes': '하루 노출시간', 'measured_load_kg': '측정 하중', 'analysis_target': '분석대상', 'camera_side': '카메라 측면', 'forward_direction': '작업자 전방', 'side_view_verified': '측면 확인', 'single_person': '단일 작업자', 'full_frame': '전신 확인', 'normal_work': '통상 작업', 'total': '합계', 'risk': '위험수준'}


def unit_for(code):
    """Unit code of a stored field path (shown as words by display.UNIT)."""
    leaf = code.split('.')[-1]
    if leaf.endswith('value_deg'):
        return 'DEG'
    if leaf.endswith(('_px', 'x_px', 'y_px')):
        return 'PX'
    if leaf in ('confidence', 'min_confidence', 'sample_ratio'):
        return 'RATIO'
    if leaf in ('minutes', 'daily_work_min'):
        return 'MIN_DAY'
    if leaf in ('load_mass_kg', 'measured_load_kg', 'effective_load_kg', 'box_mass_kg', 'pinch_mass_kg', 'single_hand_mass_kg'):
        return 'KG'
    if leaf in ('pinch_force_kg_equiv', 'grip_force_kg_equiv'):
        return 'KG_EQUIV'
    if leaf.endswith('count_day') or leaf == 'lift_count_day':
        return 'COUNT_DAY'
    if leaf == 'lift_rate_min':
        return 'COUNT_MIN'
    if leaf == 'impact_rate_hour':
        return 'COUNT_HOUR'
    if leaf == 'planned_duration_months':
        return 'MONTH'
    if leaf == 'annual_work_days':
        return 'COUNT_YEAR'
    return None


# What each of the eleven items asks, in the words of 고용노동부고시 제2020-12호 제3조 (numbers checked against the preserved notice text in the tests).
CRITERION_RULE = {
    1: '하루 4시간 이상 집중적으로 키보드·마우스 조작',
    2: '하루 총 2시간 이상 같은 동작 반복',
    3: '하루 총 2시간 이상 손이 머리 위·팔꿈치가 어깨 위·몸통에서 들림·몸통 뒤',
    4: '하루 총 2시간 이상 목·허리를 구부리거나 틂 (지지되지 않거나 자세를 바꿀 수 없을 때)',
    5: '하루 총 2시간 이상 쪼그려 앉거나 무릎을 굽힘',
    6: '하루 총 2시간 이상 1kg 이상 집기 또는 2kg 이상에 상응하는 힘으로 쥐기',
    7: '하루 총 2시간 이상 4.5kg 이상을 한 손으로 들거나 같은 힘으로 쥐기',
    8: '하루 10회 이상 25kg 이상 들기',
    9: '하루 25회 이상 10kg 이상을 무릎 아래·어깨 위·팔을 뻗어 들기',
    10: '하루 총 2시간 이상, 분당 2회 이상 4.5kg 이상 들기',
    11: '하루 총 2시간 이상, 시간당 10회 이상 손·무릎으로 충격 주기',
}
# The same eleven items as the hazard kind the form lists in its 원인분석 table (KOSHA GUIDE 부록 예시).
HAZARD_KIND = {1: '반복동작', 2: '반복동작', 3: '부적절한 자세', 4: '부적절한 자세', 5: '부적절한 자세', 6: '과도한 힘(집기)', 7: '과도한 힘(잡기)',
               8: '과도한 힘(들기)', 9: '과도한 힘·부적절한 자세', 10: '과도한 힘·반복성', 11: '접촉스트레스'}
# Standard REBA action levels worded for the form's 판정 column. They interpret the score; they are not a legal judgment.
REBA_ACTION = {'NEGLIGIBLE': '조치가 필요 없어요', 'LOW': '변화가 필요할 수 있어요', 'MEDIUM': '더 조사하고 곧 개선해야 해요',
               'HIGH': '조사하고 개선해야 해요', 'VERY_HIGH': '바로 개선해야 해요'}
