"""Current task DTO defaults for API schema 1.3. No database access."""
from datetime import datetime, timezone

PREPROCESS_VERSION = 'EXIF_OPENCV_LETTERBOX_V2'

PHASES = ['CYCLE_START', 'LIFT_OFF', 'MID_LIFT', 'SHELF_APPROACH', 'CYCLE_END']
PHASE_NAMES = ['손 닿기 전', '바닥 분리 직후', '바닥면 절반 높이', '선반 접촉 직전', '손 놓은 후']
EXPOSURES = ['C1_KEYBOARD_FOCUSED', 'C2_NECK', 'C2_SHOULDER', 'C2_ELBOW', 'C2_WRIST', 'C2_HAND', 'C3_UNION', 'C4_NECK_FLEX', 'C4_TRUNK_FLEX', 'C4_TRUNK_EXT', 'C4_NECK_TWIST', 'C4_TRUNK_TWIST', 'C4_UNION', 'C5_SQUAT', 'C5_KNEEL', 'C5_UNION', 'C6_QUALIFYING', 'C7_QUALIFYING', 'C10_LIFT', 'C11_IMPACT']
COMMON = ['trunk_base', 'trunk_twisted', 'trunk_side_bent', 'neck_base', 'neck_twisted', 'neck_side_bent', 'legs_support', 'seated', 'knee_band', 'shock_force', 'static_over_1min', 'small_repeat_over_4min', 'rapid_change_or_unstable']
ARM = ['upper_arm_base', 'arm_abducted_or_rotated', 'shoulder_raised', 'arm_supported_or_gravity_assisted', 'lower_arm_base', 'wrist_base', 'wrist_deviated_or_twisted', 'coupling']
TAG_FIELDS = ['hand_above_head', 'elbow_above_shoulder', 'elbow_behind_trunk', 'squat', 'kneel']
TAGS = ['NECK_FORWARD_PROXY', 'TRUNK_FLEX', 'TRUNK_EXT', 'UPPER_ARM_RAISE', 'HAND_ABOVE_HEAD', 'ELBOW_ABOVE_SHOULDER', 'ELBOW_BEHIND_TRUNK', 'NECK_TWIST', 'TRUNK_TWIST', 'SQUAT', 'KNEEL']

def now():
    return datetime.now(timezone.utc).isoformat()

def evidence():
    return dict(source=None, text=None, observed_at=None)

def diagnostic(code, message, field_path=None):
    return dict(code=code, message=message, field_path=field_path)

def observation():
    return dict(phase_verified='UNKNOWN', load_state='UNKNOWN', single_person='UNKNOWN', full_frame='UNKNOWN', camera_fixed='UNKNOWN', normal_cycle='UNKNOWN', evidence=evidence())

def capture():
    return dict(protocol='BOX_LIFT_15_V1', camera_side=None, forward_direction=None, slots=[dict(slot_no=i+1, cycle_no=i//5+1, phase=PHASES[i%5], photo_id=None, observation=observation()) for i in range(15)])

def legal_inputs():
    criteria = [dict(criterion_no=i, condition_present='UNKNOWN', evidence=evidence(), posture_interpretation_pending=False) for i in range(1,12)]
    for i in [4,6,7]: criteria[i-1]['unsupported'] = 'UNKNOWN'
    criteria[3]['posture_restricted'] = 'UNKNOWN'
    for i, fields in {6:['pinch_mass_kg','pinch_force_kg_equiv'],7:['single_hand_mass_kg','grip_force_kg_equiv'],9:['below_knee_count_day','above_shoulder_count_day','extended_arm_count_day','union_count_day'],10:['lift_rate_min'],11:['impact_rate_hour']}.items():
        criteria[i-1].update({field:None for field in fields})
    criteria[8]['union_evidence'] = evidence()
    return dict(lift_count_day=None, criteria=criteria, exposures=[dict(condition_code=c, minutes=None, evidence=evidence()) for c in EXPOSURES])

def default_settings():
    return dict(analysis=dict(pose_model=dict(name='MoveNet Lightning singlepose TFLite float16', version='4', preprocess_version=PREPROCESS_VERSION, input_size=192, point_count=17, confidence_min=0.5), posture_profile=dict(version='POSTURE_TECH_V1', neck_forward_deg=20, trunk_flex_deg=20, trunk_extension_deg=-20, upper_arm_raise_deg=45), reba_rule='REBA_TABLE_2000_V2', burden_rule='MOEL_2020_12_V1'), gpt_enabled=False, gpt_model='', ui=dict(loco_visible=True,loco_mode='normal'))

def exclusions(c):
    m, d = c.get('planned_duration_months'), c.get('annual_work_days')
    short = 'UNKNOWN' if m is not None and m < 0 else ('NO' if c.get('one_off') == 'NO' or m is not None and m > 2 else 'YES' if c.get('one_off') == 'YES' and m is not None else 'UNKNOWN')
    intermittent = 'UNKNOWN' if d is None or d < 0 else 'YES' if d <= 60 else 'NO'
    return dict(short_term=short, intermittent=intermittent)
