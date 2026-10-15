"""Human-readable report messages. Stored DTO codes remain unchanged."""
MANUAL = {'trunk_base': '몸통 기본범주', 'trunk_twisted': '몸통 비틀림', 'trunk_side_bent': '몸통 옆굽힘', 'neck_base': '목 기본범주', 'neck_twisted': '목 비틀림', 'neck_side_bent': '목 옆굽힘', 'legs_support': '다리 지지', 'seated': '앉은 자세', 'knee_band': '양쪽 중 큰 무릎 범주', 'shock_force': '충격·급격한 힘', 'static_over_1min': '1분 초과 정적 유지', 'small_repeat_over_4min': '분당 4회 초과 작은 반복', 'rapid_change_or_unstable': '급격한 변화·불안정', 'upper_arm_base': '위팔 기본범주', 'arm_abducted_or_rotated': '팔 벌림·회전', 'shoulder_raised': '어깨 들림', 'arm_supported_or_gravity_assisted': '팔 지지·중력 보조', 'lower_arm_base': '아래팔 기본범주', 'wrist_base': '손목 기본범주', 'wrist_deviated_or_twisted': '손목 편위·비틀림', 'coupling': '손잡이·쥐기', 'hand_above_head': '머리 위 손', 'elbow_above_shoulder': '어깨 위 팔꿈치', 'elbow_behind_trunk': '몸통 뒤 팔꿈치', 'squat': '쪼그림', 'kneel': '무릎 접촉'}

INPUTS = {'box_mass_kg': '상자 전체 중량', 'shelf_height_cm': '선반 상판 높이', 'daily_work_min': '하루 실제 작업시간', 'one_off': '1회성 작업 여부', 'planned_duration_months': '예정 작업기간', 'annual_work_days': '연간 작업일수', 'lift_count_day': '하루 들기 횟수', 'condition_present': '해당 작업조건 존재', 'unsupported': '신체·물체가 지지되지 않는 조건', 'posture_restricted': '자세를 자유롭게 바꾸기 어려운 조건', 'posture_interpretation_pending': '자세 해석 확인', 'pinch_mass_kg': '한손 손가락 집기 중량', 'pinch_force_kg_equiv': '손가락에 가해지는 힘', 'single_hand_mass_kg': '한손 들기 중량', 'grip_force_kg_equiv': '한손 쥐기 힘', 'below_knee_count_day': '무릎 아래에서 들기', 'above_shoulder_count_day': '어깨 위에서 들기', 'extended_arm_count_day': '팔을 뻗어 들기', 'union_count_day': '중복을 제외한 들기 횟수', 'lift_rate_min': '작업 중 분당 들기 횟수', 'impact_rate_hour': '작업 중 시간당 충격 횟수', 'effective_load_kg': '적용 하중', 'photo_id': '사진 배정'}

EXPOSURES = {'C1_KEYBOARD_FOCUSED': '집중 키보드·마우스 사용', 'C2_NECK': '목 반복 동작', 'C2_SHOULDER': '어깨 반복 동작', 'C2_ELBOW': '팔꿈치 반복 동작', 'C2_WRIST': '손목 반복 동작', 'C2_HAND': '손 반복 동작', 'C3_UNION': '3호 자세의 중복을 제외한 시간', 'C4_NECK_FLEX': '목 앞굽힘', 'C4_TRUNK_FLEX': '몸통 앞굽힘', 'C4_TRUNK_EXT': '몸통 뒤로 젖힘', 'C4_NECK_TWIST': '목 비틀림', 'C4_TRUNK_TWIST': '몸통 비틀림', 'C4_UNION': '4호 자세의 중복을 제외한 시간', 'C5_SQUAT': '쪼그림', 'C5_KNEEL': '무릎 굽힘', 'C5_UNION': '5호 자세의 중복을 제외한 시간', 'C6_QUALIFYING': '한손 집기·힘 조건의 작업', 'C7_QUALIFYING': '한손 들기·힘 조건의 작업', 'C10_LIFT': '반복 들기', 'C11_IMPACT': '손·무릎 반복 충격'}

REASONS = {'COMBINATION_RULE': '여러 조건을 합산하는 해석 확인 필요', 'POSTURE_INTERPRETATION': '자세 정의·해석 확인 필요', 'BOUNDARY_REVIEW': '점수 경계 ±5° 이내 · 자세 재확인', 'INPUT_CONFLICT': '입력값 사이의 모순 또는 범위 확인 필요'}

def input_label(path):
    parts = str(path).split('.')
    exposure = next((p for p in parts if p in EXPOSURES), None)
    if exposure:
        return EXPOSURES[exposure] + ' 시간'
    field = parts[-1]
    name = INPUTS.get(field, MANUAL.get(field, str(path)))
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
