"""Read-only 1.3 task adapter. Writes happen only after an explicit 2.0 save."""
def upgrade_task(task):
    """Expose a 1.3 row as an editable 2.0 DTO without altering its stored JSON."""
    from ergo.engine.task_defaults import task_input, evidence
    def direct_minutes(item):
        source=str(item.get('source') or (item.get('evidence') or {}).get('source') or '').upper()
        derived=item.get('derived_from_photos') is True or source in ('PHOTO_RATIO','POSE_RATIO','SAMPLE_RATIO','ESTIMATED_FROM_PHOTOS')
        return None if derived else item.get('minutes')
    if task.get('schema_version') == '2.0': return task
    if task.get('schema_version') not in (None, '1.3'):
        raise ValueError('지원하지 않는 저장 자료 버전입니다')
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
            item['minutes']=direct_minutes(previous)
            item['evidence']=previous.get('evidence') or evidence()
    old6=old_criteria.get(6,{})
    if old_exposures.get('C6_QUALIFYING') or any(old6.get(k) is not None for k in ['pinch_mass_kg','pinch_force_kg_equiv']):
        criteria[6]['rows']=[dict(row_id='legacy-c6',label='기존 6호 입력 · 재확인',evidence=old6.get('evidence') or evidence(),unsupported=old6.get('unsupported','UNKNOWN'),pinch_mass_kg=old6.get('pinch_mass_kg'),pinch_force_kg_equiv=old6.get('pinch_force_kg_equiv'),minutes=direct_minutes(old_exposures.get('C6_QUALIFYING') or {}))]
        criteria[6]['rows_complete']='UNKNOWN'
    old7=old_criteria.get(7,{})
    if old_exposures.get('C7_QUALIFYING') or any(old7.get(k) is not None for k in ['single_hand_mass_kg','grip_force_kg_equiv']):
        criteria[7]['rows']=[dict(row_id='legacy-c7',label='기존 7호 입력 · 재확인',evidence=old7.get('evidence') or evidence(),unsupported=old7.get('unsupported','UNKNOWN'),single_hand_mass_kg=old7.get('single_hand_mass_kg'),grip_force_kg_equiv=old7.get('grip_force_kg_equiv'),minutes=direct_minutes(old_exposures.get('C7_QUALIFYING') or {}))]
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
        criteria[10]['rows']=[dict(row_id='legacy-c10',label='기존 상자 입력 · 재확인',evidence=old10.get('evidence') or evidence(),load_mass_kg=old_mass,lift_rate_min=old10.get('lift_rate_min'),minutes=direct_minutes(old_exposures.get('C10_LIFT') or {}))]
    old11=old_criteria.get(11,{})
    if old11.get('impact_rate_hour') is not None or old_exposures.get('C11_IMPACT'):
        criteria[11]['rows']=[dict(row_id='legacy-c11',label='기존 11호 입력 · 재확인',evidence=old11.get('evidence') or evidence(),impact_verified='UNKNOWN',impact_rate_hour=old11.get('impact_rate_hour'),minutes=direct_minutes(old_exposures.get('C11_IMPACT') or {}))]
    old_capture=legacy.get('capture') or {}
    slots=[]
    for index,old in enumerate(old_capture.get('slots',[]),1):
        number=old.get('slot_no',index); obs=old.get('observation') or {}
        slots.append(dict(slot_no=number,photo_id=old.get('photo_id'),label=f"기존 사진 {number} · {old.get('cycle_no', '?')}회차 · {old.get('phase', '순간 미확인')}",analysis_target=old.get('photo_id') is not None,camera_side=old_capture.get('camera_side'),forward_direction=old_capture.get('forward_direction'),side_view_verified='UNKNOWN',observation=dict(load_state='UNKNOWN',measured_load_kg=None,single_person=obs.get('single_person','UNKNOWN'),full_frame=obs.get('full_frame','UNKNOWN'),normal_work=obs.get('normal_cycle','UNKNOWN'),evidence=obs.get('evidence') or evidence())))
    data['capture']['slots']=slots
    data['manual']=legacy.get('manual') or []
    data['analysis_scope']=dict(judgment=True,pose=True,tags=True,reba=True)
    return dict(**data,task_id=task['task_id'],survey_id=task['survey_id'],input_revision=task['input_revision'],latest_analysis_id=task.get('latest_analysis_id'),created_at=task.get('created_at'),updated_at=task.get('updated_at'),source_schema_version='1.3')
