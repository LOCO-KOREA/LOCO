"""Task DTO defaults. New work uses the general 2.0 contract; historical reads live in backend.legacy.v13."""
from datetime import datetime, timezone
from backend import ai_config
from backend import pose_contract

PREPROCESS_VERSION = pose_contract.MODELS[pose_contract.DEFAULT_MODEL]['preprocess_version']
AUXILIARY_CONDITION_KEYS = ('intake_session',)

EXPOSURE_V2 = ['C1_KEYBOARD_FOCUSED', 'C2_NECK', 'C2_SHOULDER', 'C2_ELBOW', 'C2_WRIST', 'C2_HAND', 'C3_UNION', 'C4_NECK_FLEX', 'C4_TRUNK_FLEX', 'C4_NECK_TWIST', 'C4_TRUNK_TWIST', 'C4_UNION', 'C5_SQUAT', 'C5_KNEEL', 'C5_UNION']
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

def capture_observation():
    return dict(load_state='UNKNOWN', measured_load_kg=None, single_person='UNKNOWN', full_frame='UNKNOWN', normal_work='UNKNOWN', evidence=evidence())

def legal_inputs():
    criteria = [dict(criterion_no=i, condition_present='UNKNOWN', evidence=evidence(), posture_interpretation_pending=False) for i in range(1,12)]
    criteria[3].update(unsupported='UNKNOWN', posture_restricted='UNKNOWN')
    criteria[5].update(rows=[], rows_complete='UNKNOWN', union=dict(row_ids=[], value=None, evidence=evidence()))
    criteria[6].update(rows=[], rows_complete='UNKNOWN', union=dict(row_ids=[], value=None, evidence=evidence()))
    criteria[7].update(rows=[], rows_complete='UNKNOWN', union=dict(row_ids=[], value=None, evidence=evidence()))
    criteria[8].update(rows=[], rows_complete='UNKNOWN', totals=dict(below_knee_count_day=None, above_shoulder_count_day=None, extended_arm_count_day=None, union_count_day=None, row_ids=[], evidence=evidence()))
    criteria[9].update(rows=[], rows_complete='UNKNOWN', union=dict(row_ids=[], value=None, evidence=evidence()))
    criteria[10].update(rows=[], rows_complete='UNKNOWN', union=dict(row_ids=[], value=None, evidence=evidence()))
    return dict(criteria=criteria, exposures=[dict(condition_code=c, minutes=None, evidence=evidence()) for c in EXPOSURE_V2])

def task_input(draft):
    defaults=dict(worker_code='', method_description='', work_posture='', work_height_cm=None, daily_work_min=None,
        work_intensity=None, work_frequency=None, hazard_factors='', hazard_causes='', improvement_recommendations='',
        one_off='UNKNOWN', planned_duration_months=None, annual_work_days=None, evidence=evidence())
    defaults.update(draft.get('conditions') or {})
    return dict(schema_version='2.0', task_kind='GENERAL_TASK', task_name=draft.get('task_name', ''),
        input_template=draft.get('input_template', 'GENERAL'), worker_count=draft.get('worker_count'),
        conditions=defaults,
        legal=draft.get('legal', legal_inputs()), capture=draft.get('capture', dict(protocol='GENERAL_STILLS_V1', slots=[])),
        manual=draft.get('manual', []), analysis_scope=draft.get('analysis_scope', dict(judgment=True, pose=False, tags=False, reba=False)), legacy_input=None)

def default_settings():
    return dict(analysis=dict(pose_model=pose_contract.defaults(), posture_profile=dict(version='POSTURE_TECH_V1', neck_forward_deg=20, trunk_flex_deg=20, trunk_extension_deg=-20, upper_arm_raise_deg=45), reba_rule='REBA_TABLE_2000_V2', burden_rule='MOEL_2020_12_GENERAL_V2'), **ai_config.defaults(), ui=dict(loco_visible=True,loco_mode='normal'))

def exclusions(c):
    m, d = c.get('planned_duration_months'), c.get('annual_work_days')
    valid_months=m is None or isinstance(m,(int,float)) and not isinstance(m,bool) and 0<=m< float('inf')
    valid_days=d is None or isinstance(d,int) and not isinstance(d,bool) and d>=0
    short='UNKNOWN' if not valid_months else 'NO' if c.get('one_off')=='NO' or m is not None and m>2 else 'YES' if c.get('one_off')=='YES' and m is not None else 'UNKNOWN'
    intermittent='UNKNOWN' if not valid_days or d is None else 'YES' if d<=60 else 'NO'
    return dict(short_term=short, intermittent=intermittent)
