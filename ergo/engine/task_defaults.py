"""Task DTO defaults. New work uses the general 2.0 contract; legacy constants remain for reads."""
from datetime import datetime, timezone

PREPROCESS_VERSION = 'EXIF_OPENCV_LETTERBOX_V2'

PHASES = ['CYCLE_START', 'LIFT_OFF', 'MID_LIFT', 'SHELF_APPROACH', 'CYCLE_END']  # legacy 1.3 only
PHASE_NAMES = ['손 닿기 전', '바닥 분리 직후', '바닥면 절반 높이', '선반 접촉 직전', '손 놓은 후']  # legacy 1.3 only
EXPOSURES = ['C1_KEYBOARD_FOCUSED', 'C2_NECK', 'C2_SHOULDER', 'C2_ELBOW', 'C2_WRIST', 'C2_HAND', 'C3_UNION', 'C4_NECK_FLEX', 'C4_TRUNK_FLEX', 'C4_TRUNK_EXT', 'C4_NECK_TWIST', 'C4_TRUNK_TWIST', 'C4_UNION', 'C5_SQUAT', 'C5_KNEEL', 'C5_UNION', 'C6_QUALIFYING', 'C7_QUALIFYING', 'C10_LIFT', 'C11_IMPACT']  # legacy 1.3 only
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

def observation():
    return dict(phase_verified='UNKNOWN', load_state='UNKNOWN', single_person='UNKNOWN', full_frame='UNKNOWN', camera_fixed='UNKNOWN', normal_cycle='UNKNOWN', evidence=evidence())

def capture_observation():
    return dict(load_state='UNKNOWN', measured_load_kg=None, single_person='UNKNOWN', full_frame='UNKNOWN', normal_work='UNKNOWN', evidence=evidence())

def capture():
    return dict(protocol='BOX_LIFT_15_V1', camera_side=None, forward_direction=None, slots=[dict(slot_no=i+1, cycle_no=i//5+1, phase=PHASES[i%5], photo_id=None, observation=observation()) for i in range(15)])

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

def upgrade_task(task):
    """Expose a 1.3 row as an editable 2.0 DTO without altering its stored JSON."""
    if task.get('schema_version') == '2.0':
        return task
    legacy = {k:v for k,v in task.items() if k not in {'task_id','survey_id','input_revision','latest_analysis_id','created_at','updated_at'}}
    old_conditions=legacy.get('conditions') or {}
    old_legal=legacy.get('legal') or {}
    old_exposures={x.get('condition_code'):x for x in old_legal.get('exposures',[])}
    old_criteria={x.get('criterion_no'):x for x in old_legal.get('criteria',[])}
    data=task_input(dict(task_name=legacy.get('task_name',''),input_template='LIFTING',worker_count=legacy.get('worker_count')))
    data['legacy_input']=legacy
    data['conditions'].update(worker_code=old_conditions.get('worker_code',''),method_description=old_conditions.get('method_description',''),work_posture=old_conditions.get('work_posture',''),work_height_cm=old_conditions.get('shelf_height_cm'),daily_work_min=old_conditions.get('daily_work_min'),one_off=old_conditions.get('one_off','UNKNOWN'),planned_duration_months=old_conditions.get('planned_duration_months'),annual_work_days=old_conditions.get('annual_work_days'),evidence=old_conditions.get('evidence') or evidence())
    criteria={x['criterion_no']:x for x in data['legal']['criteria']}
    for number in range(1,6):
        criteria[number]['condition_present']=old_criteria.get(number,{}).get('condition_present','UNKNOWN')
        criteria[number]['evidence']=old_criteria.get(number,{}).get('evidence') or evidence()
        criteria[number]['posture_interpretation_pending']=bool(old_criteria.get(number,{}).get('posture_interpretation_pending',False))
    criteria[4]['unsupported']=old_criteria.get(4,{}).get('unsupported','UNKNOWN')
    criteria[4]['posture_restricted']=old_criteria.get(4,{}).get('posture_restricted','UNKNOWN')
    new_exposures={x['condition_code']:x for x in data['legal']['exposures']}
    for code,item in new_exposures.items():
        previous=old_exposures.get(code)
        if previous:
            item['minutes']=previous.get('minutes')
            item['evidence']=previous.get('evidence') or evidence()
    old6=old_criteria.get(6,{})
    if old_exposures.get('C6_QUALIFYING') or any(old6.get(k) is not None for k in ['pinch_mass_kg','pinch_force_kg_equiv']):
        criteria[6]['rows']=[dict(row_id='legacy-c6',label='기존 6호 입력 · 재확인',evidence=old6.get('evidence') or evidence(),unsupported=old6.get('unsupported','UNKNOWN'),pinch_mass_kg=old6.get('pinch_mass_kg'),pinch_force_kg_equiv=old6.get('pinch_force_kg_equiv'),minutes=(old_exposures.get('C6_QUALIFYING') or {}).get('minutes'))]
        criteria[6]['rows_complete']='UNKNOWN'
    old7=old_criteria.get(7,{})
    if old_exposures.get('C7_QUALIFYING') or any(old7.get(k) is not None for k in ['single_hand_mass_kg','grip_force_kg_equiv']):
        criteria[7]['rows']=[dict(row_id='legacy-c7',label='기존 7호 입력 · 재확인',evidence=old7.get('evidence') or evidence(),unsupported=old7.get('unsupported','UNKNOWN'),single_hand_mass_kg=old7.get('single_hand_mass_kg'),grip_force_kg_equiv=old7.get('grip_force_kg_equiv'),minutes=(old_exposures.get('C7_QUALIFYING') or {}).get('minutes'))]
        criteria[7]['rows_complete']='UNKNOWN'
    old_mass=old_conditions.get('box_mass_kg')
    old8_count=old_legal.get('lift_count_day')
    if old_mass is not None or old8_count is not None:
        criteria[8]['rows']=[dict(row_id='legacy-c8',label='기존 상자 입력 · 재확인',evidence=old_conditions.get('evidence') or evidence(),load_mass_kg=old_mass,lift_count_day=old8_count)]
    old9=old_criteria.get(9,{})
    if old_mass is not None or any(old9.get(k) is not None for k in ['below_knee_count_day','above_shoulder_count_day','extended_arm_count_day','union_count_day']):
        rid='legacy-c9'; criteria[9]['rows']=[dict(row_id=rid,label='기존 상자 입력 · 재확인',evidence=old9.get('evidence') or evidence(),load_mass_kg=old_mass,below_knee_count_day=old9.get('below_knee_count_day'),above_shoulder_count_day=old9.get('above_shoulder_count_day'),extended_arm_count_day=old9.get('extended_arm_count_day'),union_count_day=old9.get('union_count_day'),union_evidence=old9.get('union_evidence') or evidence())]
        criteria[9]['totals'].update(below_knee_count_day=old9.get('below_knee_count_day'),above_shoulder_count_day=old9.get('above_shoulder_count_day'),extended_arm_count_day=old9.get('extended_arm_count_day'),union_count_day=old9.get('union_count_day'),row_ids=[rid],evidence=old9.get('union_evidence') or evidence())
    old10=old_criteria.get(10,{})
    if old_mass is not None or old10.get('lift_rate_min') is not None or old_exposures.get('C10_LIFT'):
        criteria[10]['rows']=[dict(row_id='legacy-c10',label='기존 상자 입력 · 재확인',evidence=old10.get('evidence') or evidence(),load_mass_kg=old_mass,lift_rate_min=old10.get('lift_rate_min'),minutes=(old_exposures.get('C10_LIFT') or {}).get('minutes'))]
    old11=old_criteria.get(11,{})
    if old11.get('impact_rate_hour') is not None or old_exposures.get('C11_IMPACT'):
        criteria[11]['rows']=[dict(row_id='legacy-c11',label='기존 11호 입력 · 재확인',evidence=old11.get('evidence') or evidence(),impact_verified='UNKNOWN',impact_rate_hour=old11.get('impact_rate_hour'),minutes=(old_exposures.get('C11_IMPACT') or {}).get('minutes'))]
    old_capture=legacy.get('capture') or {}
    slots=[]
    for index,old in enumerate(old_capture.get('slots',[]),1):
        number=old.get('slot_no',index); obs=old.get('observation') or {}
        slots.append(dict(slot_no=number,photo_id=old.get('photo_id'),label=f"기존 사진 {number}",analysis_target=old.get('photo_id') is not None,camera_side=old_capture.get('camera_side'),forward_direction=old_capture.get('forward_direction'),side_view_verified='UNKNOWN',observation=dict(load_state='UNKNOWN',measured_load_kg=None,single_person=obs.get('single_person','UNKNOWN'),full_frame=obs.get('full_frame','UNKNOWN'),normal_work=obs.get('normal_cycle','UNKNOWN'),evidence=obs.get('evidence') or evidence())))
    data['capture']['slots']=slots
    data['manual']=legacy.get('manual') or []
    data['analysis_scope']=dict(judgment=True,pose=True,tags=True,reba=True)
    return dict(**data,task_id=task['task_id'],survey_id=task['survey_id'],input_revision=task['input_revision'],latest_analysis_id=task.get('latest_analysis_id'),created_at=task.get('created_at'),updated_at=task.get('updated_at'),source_schema_version='1.3')

def default_settings():
    return dict(analysis=dict(pose_model=dict(name='MoveNet Lightning singlepose TFLite float16', version='4', preprocess_version=PREPROCESS_VERSION, input_size=192, point_count=17, confidence_min=0.5), posture_profile=dict(version='POSTURE_TECH_V1', neck_forward_deg=20, trunk_flex_deg=20, trunk_extension_deg=-20, upper_arm_raise_deg=45), reba_rule='REBA_TABLE_2000_V2', burden_rule='MOEL_2020_12_GENERAL_V2'), gpt_enabled=False, gpt_model='gpt-6-luna', ui=dict(loco_visible=True,loco_mode='normal'))

def exclusions(c):
    m, d = c.get('planned_duration_months'), c.get('annual_work_days')
    valid_months=m is None or isinstance(m,(int,float)) and not isinstance(m,bool) and 0<=m< float('inf')
    valid_days=d is None or isinstance(d,int) and not isinstance(d,bool) and d>=0
    short='UNKNOWN' if not valid_months else 'NO' if c.get('one_off')=='NO' or m is not None and m>2 else 'YES' if c.get('one_off')=='YES' and m is not None else 'UNKNOWN'
    intermittent='UNKNOWN' if not valid_days or d is None else 'YES' if d<=60 else 'NO'
    return dict(short_term=short, intermittent=intermittent)
