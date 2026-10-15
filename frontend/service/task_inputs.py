"""Task input DTO defaults and storage adapter; no score or legal judgment engine."""
from copy import deepcopy
from datetime import datetime, timezone
from ergo.db import storage

EXPOSURES = [
    'C1_KEYBOARD_FOCUSED', 'C2_NECK', 'C2_SHOULDER', 'C2_ELBOW', 'C2_WRIST', 'C2_HAND',
    'C3_UNION', 'C4_NECK_FLEX', 'C4_TRUNK_FLEX', 'C4_TRUNK_EXT', 'C4_NECK_TWIST', 'C4_TRUNK_TWIST',
    'C4_UNION', 'C5_SQUAT', 'C5_KNEEL', 'C5_UNION', 'C6_QUALIFYING', 'C7_QUALIFYING', 'C10_LIFT', 'C11_IMPACT',
]
PHASES = ['CYCLE_START', 'LIFT_OFF', 'MID_LIFT', 'SHELF_APPROACH', 'CYCLE_END']
INPUT_KEYS = ['task_kind', 'task_name', 'worker_count', 'conditions', 'legal', 'capture', 'manual']

def evidence():
    return dict(source=None, text=None, observed_at=None)

def observation():
    return dict(phase_verified='UNKNOWN', load_state='UNKNOWN', single_person='UNKNOWN', full_frame='UNKNOWN', camera_fixed='UNKNOWN', normal_cycle='UNKNOWN', evidence=evidence())

def legal_inputs():
    criteria = [dict(criterion_no=i, condition_present='UNKNOWN', evidence=evidence(), posture_interpretation_pending=False) for i in range(1, 12)]
    for i in [4, 6, 7]:
        criteria[i-1]['unsupported'] = 'UNKNOWN'
    criteria[3]['posture_restricted'] = 'UNKNOWN'
    for i, names in {6:['pinch_mass_kg','pinch_force_kg_equiv'], 7:['single_hand_mass_kg','grip_force_kg_equiv'], 9:['below_knee_count_day','above_shoulder_count_day','extended_arm_count_day','union_count_day'], 10:['lift_rate_min'], 11:['impact_rate_hour']}.items():
        criteria[i-1].update({name:None for name in names})
    criteria[8]['union_evidence'] = evidence()
    return dict(lift_count_day=None, criteria=criteria, exposures=[dict(condition_code=code, minutes=None, evidence=evidence()) for code in EXPOSURES])

def settings():
    return dict(pose_model=dict(name='MoveNet Lightning', version='4', preprocess_version='EXIF_LETTERBOX_V1', input_size=192, point_count=17, confidence_min=0.5), posture_profile=dict(version='POSTURE_TECH_V1', neck_forward_deg=20, trunk_flex_deg=20, trunk_extension_deg=-20, upper_arm_raise_deg=45), reba_rule='REBA_TABLE_2000_V2', burden_rule='MOEL_2020_12_V1')

def task_by_id(task_id, db_path):
    task = storage.get_task(task_id, db_path=db_path)
    if task is None:
        raise LookupError('작업을 찾을 수 없습니다.')
    return task

def exclusions(conditions):
    months, days, one_off = conditions.get('planned_duration_months'), conditions.get('annual_work_days'), conditions.get('one_off')
    short = 'UNKNOWN'
    if months is None or months >= 0:
        if one_off == 'NO' or months is not None and months > 2:
            short = 'NO'
        elif one_off == 'YES' and months is not None and months <= 2:
            short = 'YES'
    intermittent = 'UNKNOWN' if days is None or days < 0 else 'YES' if days <= 60 else 'NO'
    return dict(short_term=short, intermittent=intermittent)

def dispatch_task(method, params, db_path):
    if method == 'create_task':
        if storage.get_survey(params['survey_id'], db_path=db_path) is None:
            raise LookupError('조사를 찾을 수 없습니다.')
        draft = params['draft']
        data = dict(task_kind='FLOOR_TO_SHELF_BOX_SINGLE_PERSON', task_name=draft['task_name'], worker_count=1, conditions=deepcopy(draft['conditions']), legal=legal_inputs(), manual=[], capture=dict(protocol='BOX_LIFT_15_V1', camera_side=None, forward_direction=None, slots=[dict(slot_no=i+1, cycle_no=i//5+1, phase=PHASES[i%5], photo_id=None, observation=observation()) for i in range(15)]))
        timestamp = datetime.now(timezone.utc).isoformat()
        task_id = storage.create_task(params['survey_id'], data, timestamp, timestamp, db_path=db_path)
        return task_by_id(task_id, db_path)
    task = task_by_id(params['task_id'], db_path)
    if method == 'get_task':
        saved_settings = storage.get_settings(db_path=db_path) or {}
        return dict(task=task, exclusions=exclusions(task['conditions']), photos=storage.list_photos(task['task_id'], db_path=db_path), settings=saved_settings.get('analysis') or settings())
    if method == 'delete_task':
        storage.delete_task(task['task_id'], db_path=db_path)
        return dict(message='작업을 삭제했습니다. 원본 사진과 외부 Excel은 유지됩니다.')
    data = {key:deepcopy(task[key]) for key in INPUT_KEYS}
    if method == 'rename_task':
        data['task_name'] = params['task_name']
    elif method == 'set_task_conditions':
        new = params['conditions']
        if any(new.get(key) != data['conditions'].get(key) for key in ['worker_code','method_description','shelf_height_cm']):
            data['manual'] = []
            for slot in data['capture']['slots']:
                slot['observation'] = observation()
        data['conditions'] = deepcopy(new)
    elif method == 'set_legal_inputs':
        data['legal'] = deepcopy(params['legal'])
    else:
        raise LookupError('아직 연결하지 않은 작업 메서드입니다: ' + method)
    if any(data[key] != task[key] for key in INPUT_KEYS):
        storage.update_task_input(task['task_id'], data, datetime.now(timezone.utc).isoformat(), db_path=db_path)
    return task_by_id(task['task_id'], db_path)
