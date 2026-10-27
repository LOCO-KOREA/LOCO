"""REBA_TABLE_2000_V2 candidates and scores; pure DTO functions."""
import copy
import math
from .task_defaults import COMMON, ARM, AUXILIARY_CONDITION_KEYS, diagnostic
from ergo.pose_contract import WRIST_POLICY, PHOTO_SOURCES
from .angle_selection import selected_angle, WORLD_FOR_IMAGE

TABLE_A = [[1,2,3,4,1,2,3,4,3,3,5,6],[2,3,4,5,3,4,5,6,4,5,6,7],[2,4,5,6,4,5,6,7,5,6,7,8],[3,5,6,7,5,6,7,8,6,7,8,9],[4,6,7,8,6,7,8,9,7,8,9,9]]
TABLE_B = [[1,2,2,1,2,3],[1,2,3,2,3,4],[3,4,5,4,5,5],[4,5,5,5,6,7],[6,7,8,7,8,8],[7,8,8,8,9,9]]
TABLE_C = [[1,1,1,2,3,3,4,5,6,7,7,7],[1,2,2,3,4,4,5,6,6,7,7,8],[2,3,3,3,4,5,6,7,7,8,8,8],[3,4,4,4,5,6,7,8,8,9,9,9],[4,4,4,5,6,7,8,8,9,9,9,9],[6,6,6,7,8,8,9,9,10,10,10,10],[7,7,7,8,9,9,9,10,10,11,11,11],[8,8,8,9,10,10,10,10,10,11,11,11],[9,9,9,10,10,10,11,11,11,12,12,12],[10,10,10,11,11,11,11,12,12,12,12,12],[11,11,11,11,12,12,12,12,12,12,12,12],[12,12,12,12,12,12,12,12,12,12,12,12]]

# The no-burden option for every REBA item: used for the first-pass score and the score so far, never stored as an input.
NO_BURDEN = {
    'trunk_base': 1, 'trunk_twisted': 'NO', 'trunk_side_bent': 'NO', 'neck_base': 1,
    'neck_twisted': 'NO', 'neck_side_bent': 'NO', 'legs_support': 'BILATERAL_STABLE',
    'seated': 'NO', 'knee_band': 'UNDER_30', 'shock_force': 'NO', 'static_over_1min': 'NO',
    'small_repeat_over_4min': 'NO', 'rapid_change_or_unstable': 'NO',
    'upper_arm_base': 1, 'arm_abducted_or_rotated': 'NO', 'shoulder_raised': 'NO',
    'arm_supported_or_gravity_assisted': 'NO', 'lower_arm_base': 1, 'wrist_base': 1,
    'wrist_deviated_or_twisted': 'NO', 'coupling': 'NOT_APPLICABLE',
}

def risk(total):
    return 'NEGLIGIBLE' if total == 1 else 'LOW' if total <= 3 else 'MEDIUM' if total <= 7 else 'HIGH' if total <= 10 else 'VERY_HIGH'


def _conflicting_load(observation):
    state=observation.get('load_state','UNKNOWN');value=observation.get('measured_load_kg')
    return (state not in ('UNLOADED','MEASURED','UNKNOWN') or
            state in ('UNLOADED','UNKNOWN') and value is not None or
            state=='MEASURED' and (not isinstance(value,(int,float)) or isinstance(value,bool) or not math.isfinite(value) or value<0))

def _photo_measurements_refused(snapshot,slot):
    saved=((snapshot.get('conditions') or {}).get(AUXILIARY_CONDITION_KEYS[0]) or {}).get('facts') or {}
    context=saved.get('context@default') or {}
    return (context.get('state')=='KNOWN' and context.get('value')=='NO'
        or context.get('state')=='UNKNOWN' and context.get('source')=='USER'
        or any((slot.get('observation') or {}).get(field)=='NO' for field in ('single_person','full_frame','normal_work')))


def _measurement(row,value_key='value'):
    return dict(scope=row['scope'],field=row['field'],value=row.get(value_key),
        **{key:copy.deepcopy(row[key]) for key in ('angles','estimated','measurement_method','source','vision_proof','vision_confidence') if key in row})


def _saved_photo_measurements(snapshot, slot):
    """Return only this target photo's persisted REBA posture observations."""
    session = ((snapshot.get('conditions') or {}).get(AUXILIARY_CONDITION_KEYS[0]) or {})
    observations = ((session.get('photo_observations') or {}).get('observations') or [])
    result = []
    seen = set()
    if _photo_measurements_refused(snapshot,slot):return result
    for item in observations:
        scope, field, value = item.get('scope'), item.get('field'), item.get('value')
        key = (scope, field)
        if item.get('photo_id') != slot.get('photo_id') or scope not in ('COMMON', 'LEFT', 'RIGHT') or field not in COMMON + ARM:
            continue
        if value in (None, 'UNKNOWN') or key in seen:
            continue
        result.append(_measurement(item))
        seen.add(key)
    from ergo.intake.photo_facts import estimated_photo_inputs
    for item in estimated_photo_inputs(snapshot,slot):
        key=(item['scope'],item['field'])
        if item.get('source')!='VISION' or key in seen:continue
        result.append(_measurement(dict(item,measurement_method=item.get('measurement_method') or 'AI_PHOTO_CATEGORY')))
        seen.add(key)
    return result

def _merge_photo_measurements(saved, candidates_for_slot):
    """Prefer the original intake reading; use a formal pose candidate only to fill its gaps."""
    result = list(saved)
    seen = {(item['scope'], item['field']) for item in result}
    for item in candidates_for_slot:
        scope, field, value = item.get('scope'), item.get('field'), item.get('proposed_value')
        key = (scope, field)
        if scope in ('COMMON', 'LEFT', 'RIGHT') and field in COMMON + ARM and value not in (None, 'UNKNOWN'):
            if key in seen and any(a.get('coordinate_space')=='INFERRED_WORLD_3D' for a in item.get('angles',[])):
                result=[row for row in result if (row['scope'],row['field'])!=key]
                seen.discard(key)
            if key not in seen:
                result.append(_measurement(item,'proposed_value'))
                seen.add(key)
    return result

def score_so_far(snapshot, slot, current, open_paths, photo_measurements=(), *, require_anchor=True):
    """Score of the answers so far, every open item at its no-burden option; None until trunk and an upper arm are known (assumptions alone read as negligible).

    shortcut: arm support and sitting are assumed NO although YES scores lower, so this is not a strict minimum; upgrade if a lower bound is ever promised.
    """
    borrowed = []
    measurement_refs=[]
    saved = ((snapshot.get('conditions') or {}).get(AUXILIARY_CONDITION_KEYS[0]) or {}).get('facts') or {}
    confirmation = saved.get('context@default') or {}
    # While the photo confirmation is unanswered, readings the task does not project yet are borrowed and named. They were already filtered by view and confidence.
    photo_refused=_photo_measurements_refused(snapshot,slot)
    if not photo_refused and not (confirmation.get('state') == 'KNOWN' or confirmation.get('state') == 'UNKNOWN' and confirmation.get('source') == 'USER'):
        for item in saved.values():
            parts = item.get('target', '').split('.')
            if (len(parts) == 3 and parts[0] == 'manual' and item.get('source') in PHOTO_SOURCES and item.get('state') == 'KNOWN' and not item.get('alias_of')
                    and item.get('photo_id') == slot['photo_id'] and item.get('value') is not None and current.get((parts[1], parts[2])) in (None, 'UNKNOWN')):
                current = {**current, (parts[1], parts[2]): item['value']}
                borrowed.append(f'{parts[1].lower()}.{parts[2]}')
                proof=item.get('photo_proof') or {}
                measurement_refs.append(_measurement(dict(proof,scope=parts[1],field=parts[2],value=item['value'],angles=item.get('angles') or proof.get('angles',[]))))
    # A confirmed or still-reviewable observation from this exact photo can
    # complete the preliminary score. It never replaces a saved answer.
    context = saved.get('context@default') or {}
    measured_paths = []
    if not photo_refused:
        for item in photo_measurements or ():
            scope, field, value = item.get('scope'), item.get('field'), item.get('value')
            if scope not in ('COMMON', 'LEFT', 'RIGHT') or field not in COMMON + ARM or value in (None, 'UNKNOWN'):
                continue
            if current.get((scope, field)) in (None, 'UNKNOWN'):
                current = {**current, (scope, field): value}
                measured_paths.append(f'{scope.lower()}.{field}')
                measurement_refs.append(_measurement(item))
    known = lambda scope, field: current.get((scope, field)) not in (None, 'UNKNOWN')
    if require_anchor and not (known('COMMON', 'trunk_base') and (known('LEFT', 'upper_arm_base') or known('RIGHT', 'upper_arm_base'))):
        return None
    obs = dict(slot['observation'])
    assumed = sorted(path for path in open_paths if path.split('.')[0] in ('common', 'left', 'right') and path not in borrowed and path not in measured_paths)
    note = '지금까지 확인한 값으로 계산하고, 확인하지 못한 항목은 부담 없음으로 가정한 점수입니다. 실제 점수는 더 높을 수 있고 확정 점수가 아닙니다.'
    load_assumed=False
    if obs.get('load_state', 'UNKNOWN') == 'UNKNOWN' and obs.get('measured_load_kg') is None:
        load_assumed=True
        obs['load_state'] = 'UNLOADED'
        assumed.append('observation.load_state')
        note += ' 들고 있는 물건이 있는지 몰라 없는 것으로 계산했어요.'
    elif not require_anchor and _conflicting_load(obs):
        # Keep the real observation untouched; this read-only display candidate
        # uses the neutral load option and names the conflict explicitly.
        obs.update(load_state='UNLOADED', measured_load_kg=None)
        load_assumed=True
        assumed.append('observation.measured_load_kg')
        note += ' 물건 무게가 비어 있거나 하중 입력이 서로 맞지 않아 하중 없음으로 가정했습니다.'
    carrying = obs.get('load_state') == 'MEASURED' and obs.get('measured_load_kg') != 0
    coupling_values=('GOOD','FAIR','POOR','UNACCEPTABLE')
    assumed_carrying=load_assumed and slot['observation'].get('load_state','UNKNOWN') in ('MEASURED','UNKNOWN') and (
        slot['observation'].get('load_state')=='MEASURED' or any(current.get((side,'coupling')) in coupling_values for side in ('LEFT','RIGHT')))
    if assumed_carrying:
        note += ' 물건 무게에 따른 하중 가산점만 0으로 가정하고, 입력한 잡기 조건은 그대로 반영합니다.'
    rows = []
    for scope, fields in (('COMMON', COMMON), ('LEFT', ARM), ('RIGHT', ARM)):
        for field in fields:
            value = current.get((scope, field))
            if value in (None, 'UNKNOWN'):
                value = 'GOOD' if field == 'coupling' and (carrying or assumed_carrying) else NO_BURDEN[field]
            rows.append(dict(slot_no=slot['slot_no'], photo_id=slot['photo_id'], scope=scope, field=field, value=value))
    filled = dict(snapshot, capture=dict(slots=[dict(slot, observation=obs)]), manual=rows)
    result = calculate_reba(filled, None, with_score_so_far=False,_coupling_with_assumed_load=assumed_carrying)['slots'][0]
    if result['total'] is None:
        return None
    so_far = dict(total=result['total'], risk=result['risk'], selected_side=result['selected_side'], left=result['left']['total'],
                  right=result['right']['total'], assumed=sorted(set(assumed)), assumption=note)
    if borrowed: so_far['unconfirmed_photo'] = sorted(borrowed)
    if measurement_refs:so_far['measurement_refs']=measurement_refs
    if measured_paths:
        so_far['photo_measurements'] = sorted(set(measured_paths))
        so_far['assumption'] += ' 같은 사진의 측정 후보를 반영했으며 사람이 확인한 값과 구분해야 합니다.'
    return so_far

def candidates(slot, pose, camera_side, confidence_min=0.5):
    angles = (pose or {}).get('angles', [])
    observation=slot.get('observation') or {}
    context_ok=(camera_side in ('LEFT','RIGHT') and slot.get('forward_direction') in ('SCREEN_RIGHT','SCREEN_LEFT') and
        slot.get('side_view_verified')=='YES' and observation.get('single_person')=='YES' and
        observation.get('full_frame')=='YES' and observation.get('normal_work')=='YES')
    specs = [('COMMON','trunk_base',[camera_side],'TRUNK_TILT_VERT'),('COMMON','knee_band',['LEFT','RIGHT'],'KNEE_FLEX')]
    if any(a['angle_code']=='NECK_FLEX_TRUNK_PROXY' for a in angles):
        specs.append(('COMMON','neck_base',[camera_side],'NECK_FLEX_TRUNK_PROXY'))
    specs += [(side,field,[side],code) for side in ['LEFT','RIGHT'] for field,code in [('upper_arm_base','UPPER_ARM_FLEX_TRUNK'),('lower_arm_base','ELBOW_FLEX')]]
    if any(a['angle_code']==WRIST_POLICY['angle_code'] for a in angles):
        specs += [(side,'wrist_base',[side],WRIST_POLICY['angle_code']) for side in ['LEFT','RIGHT']]
    result=[]
    for scope,field,sides,code in specs:
        refs=([a for side in sides if (a:=selected_angle(pose,side,code,confidence_min)) is not None] if code in WORLD_FOR_IMAGE
            else [a for a in angles if a['side'] in sides and a['angle_code']==code])
        usable=context_ok and len(refs)==len(sides) and all(a['value_deg'] is not None and (a['min_confidence'] or 0)>=confidence_min for a in refs)
        if field=='wrist_base':
            usable=usable and all(a.get('measurement',{}).get('coordinate_space')=='ORIGINAL_IMAGE_2D' and
                a.get('measurement',{}).get('used_world_coordinates') is False and
                (a.get('measurement',{}).get('auto_eligible') or a.get('diagnostic_code')=='WRIST_BOUNDARY') for a in refs)
        value=None; reasons=[]
        if usable:
            angle=max(a['value_deg'] for a in refs)
            if field=='trunk_base': value=1 if angle==0 else 2 if -20<=angle<=20 else 3 if angle<=60 else 4; bounds=[-20,0,20,60]
            elif field=='neck_base': value='2_EXTENSION' if angle<0 else 1 if angle<=20 else 2; bounds=[0,20]
            elif field=='upper_arm_base': value=1 if -20<=angle<=20 else 2 if angle< -20 or angle<=45 else 3 if angle<=90 else 4; bounds=[-20,20,45,90]
            elif field=='lower_arm_base': value=1 if 60<=angle<=100 else 2; bounds=[60,100]
            elif field=='wrist_base': value=1 if angle<=WRIST_POLICY['category_boundary_deg'] else 2; bounds=[WRIST_POLICY['category_boundary_deg']]
            else: value='UNDER_30' if angle<30 else 'FROM_30_TO_60' if angle<=60 else 'OVER_60'; bounds=[30,60]
            margin=WRIST_POLICY['boundary_margin_deg'] if field=='wrist_base' else 5
            if any(abs(a['value_deg']-b)<=margin for a in refs for b in bounds) or field=='wrist_base' and any(a.get('diagnostic_code')=='WRIST_BOUNDARY' for a in refs): reasons=['BOUNDARY_REVIEW']
        if not context_ok: note=diagnostic('CAPTURE_CONTEXT_UNCONFIRMED','측면·전방·단일 작업자·전신·통상 작업 확인이 필요합니다','capture.observation')
        elif not usable: note=diagnostic('MISSING_ANGLE','후보에 필요한 관절·각도가 없습니다')
        else: note=None
        result.append(dict(slot_no=slot['slot_no'],photo_id=slot['photo_id'],scope=scope,field=field,proposed_value=value,angles=refs,min_confidence=min(a['min_confidence'] for a in refs) if usable else None,review_reasons=reasons,diagnostics=[note] if note else [],
            **(dict(estimated=True,measurement_method='NECK_FLEX_TRUNK_PROXY') if field=='neck_base' else
               dict(estimated=True,measurement_method='INFERRED_WORLD_3D') if any(a.get('coordinate_space')=='INFERRED_WORLD_3D' for a in refs) else {})))
    return result

def calculate_reba(snapshot, pose, with_score_so_far=True, *, _coupling_with_assumed_load=False):
    # The private flag is only for score_so_far's transient no-load assumption:
    # an unknown mass is not an answer that no object is held. Normal/official
    # calculations still require a valid weight and retain the old zero-load rule.
    if snapshot.get('schema_version')!='2.0': raise ValueError('과거 REBA는 저장된 결과로 읽으세요. 새 계산에는 2.0 입력이 필요합니다')
    output=[]
    targets=[s for s in snapshot['capture']['slots'] if s.get('analysis_target',True) and s.get('photo_id') is not None]
    for slot in targets:
        number=slot['slot_no']; obs=slot['observation']
        expected='UNLOADED' if obs.get('load_state')=='UNLOADED' else 'MEASURED'
        load=0 if expected=='UNLOADED' else obs.get('measured_load_kg') if obs.get('load_state')=='MEASURED' else None
        load_conflict=False
        state=obs.get('load_state','UNKNOWN'); measured=obs.get('measured_load_kg')
        if state not in ('UNLOADED','MEASURED','UNKNOWN') or state in ('UNLOADED','UNKNOWN') and measured is not None:
            load=None; load_conflict=True
        elif state=='MEASURED':
            try: finite=isinstance(measured,(int,float)) and not isinstance(measured,bool) and math.isfinite(measured)
            except OverflowError: finite=False
            if not finite or measured<0:
                load=None; load_conflict=True
        current={ (v['scope'],v['field']):v['value'] for v in snapshot['manual'] if v['slot_no']==number and v['photo_id']==slot['photo_id'] }
        sides={}
        for side in ['LEFT','RIGHT']:
            missing=[]; reasons=[]; values={}
            for scope, fields in [('COMMON',COMMON),(side,ARM)]:
                for field in fields:
                    val=current.get((scope,field)); values[field]=val
                    if val is None or val=='UNKNOWN': missing.append(f'{scope.lower()}.{field}')
            # Unknown members of an already-confirmed OR do not change its score.
            irrelevant=set()
            if values.get('trunk_twisted') == 'YES': irrelevant.add('trunk_side_bent')
            if values.get('trunk_side_bent') == 'YES': irrelevant.add('trunk_twisted')
            if values.get('neck_twisted') == 'YES': irrelevant.add('neck_side_bent')
            if values.get('neck_side_bent') == 'YES': irrelevant.add('neck_twisted')
            if values.get('seated') == 'YES': irrelevant.add('knee_band')
            missing=[path for path in missing if path.split('.')[-1] not in irrelevant]
            if slot['photo_id'] is None: missing.append('photo_id')
            if load is None: missing.append('effective_load_kg')
            keys=['trunk','neck','legs','table_a','load_score','score_a','upper_arm','lower_arm','wrist','table_b','coupling_score','score_b','table_c','activity_score','total']
            score=dict.fromkeys(keys); score.update(side=side,risk=None,missing_fields=missing,review_reasons=reasons)
            if load_conflict:
                score['review_reasons']=['INPUT_CONFLICT']; score['missing_fields'].append('observation.load_state')
            if not missing:
                try:
                    for field in COMMON+ARM:
                        value=values[field]
                        if field in irrelevant: continue
                        if field in ['trunk_base','neck_base','upper_arm_base','lower_arm_base','wrist_base']:
                            limit={'trunk_base':4,'neck_base':2,'upper_arm_base':4,'lower_arm_base':2,'wrist_base':2}[field]
                            if field=='neck_base' and value=='2_EXTENSION': value=2; values[field]=2
                            if isinstance(value,bool) or not isinstance(value,int) or value not in range(1,limit+1): raise ValueError(field)
                        elif field=='legs_support' and value not in ['BILATERAL_STABLE','UNILATERAL_OR_UNSTABLE']: raise ValueError(field)
                        elif field=='knee_band' and value not in ['UNDER_30','FROM_30_TO_60','OVER_60']: raise ValueError(field)
                        elif field=='coupling' and (value not in (['NOT_APPLICABLE'] if load==0 and not _coupling_with_assumed_load else ['GOOD','FAIR','POOR','UNACCEPTABLE'])): raise ValueError(field)
                        elif field not in ['legs_support','knee_band','coupling'] and field not in ['trunk_base','neck_base','upper_arm_base','lower_arm_base','wrist_base'] and value not in ['YES','NO']: raise ValueError(field)
                    if isinstance(load,bool) or not isinstance(load,(int,float)) or load<0 or not math.isfinite(load): raise ValueError('effective_load_kg')
                    yes=lambda f:int(values[f]=='YES')
                    trunk=values['trunk_base']+int(yes('trunk_twisted') or yes('trunk_side_bent'))
                    neck=values['neck_base']+int(yes('neck_twisted') or yes('neck_side_bent'))
                    legs=(1 if values['legs_support']=='BILATERAL_STABLE' else 2)+(0 if yes('seated') else ['UNDER_30','FROM_30_TO_60','OVER_60'].index(values['knee_band']))
                    upper=max(1,values['upper_arm_base']+yes('arm_abducted_or_rotated')+yes('shoulder_raised')-yes('arm_supported_or_gravity_assisted'))
                    lower=values['lower_arm_base']; wrist=values['wrist_base']+yes('wrist_deviated_or_twisted')
                    a=TABLE_A[trunk-1][(neck-1)*4+legs-1]; ls=(0 if load<5 else 1 if load<=10 else 2)+yes('shock_force')
                    b=TABLE_B[upper-1][(lower-1)*3+wrist-1]; cs=0 if load==0 and not _coupling_with_assumed_load else ['GOOD','FAIR','POOR','UNACCEPTABLE'].index(values['coupling'])
                    c=TABLE_C[a+ls-1][b+cs-1]; activity=sum(yes(f) for f in ['static_over_1min','small_repeat_over_4min','rapid_change_or_unstable'])
                    score.update(trunk=trunk,neck=neck,legs=legs,table_a=a,load_score=ls,score_a=a+ls,upper_arm=upper,lower_arm=lower,wrist=wrist,table_b=b,coupling_score=cs,score_b=b+cs,table_c=c,activity_score=activity,total=c+activity,risk=risk(c+activity))
                except (ValueError,IndexError,TypeError): score['review_reasons']=['INPUT_CONFLICT']; score['missing_fields'].append('범주·하중 입력 확인')
            sides[side.lower()]=score
        complete=all(sides[s]['total'] is not None for s in ['left','right'])
        chosen=('LEFT' if sides['left']['total']>=sides['right']['total'] else 'RIGHT') if complete else None
        total=sides[chosen.lower()]['total'] if chosen else None
        ps=next((p for p in (pose or {}).get('slots',[]) if p['slot_no']==number and p.get('photo_id')==slot['photo_id']),None)
        camera=slot.get('camera_side'); confidence=(snapshot.get('settings') or {}).get('pose_model',{}).get('confidence_min',0.5)
        candidate_rows=candidates(slot,ps,camera,confidence)
        entry=dict(slot_no=number,photo_id=slot['photo_id'],candidates=candidate_rows,load_state=obs.get('load_state','UNKNOWN'),effective_load_kg=load,status='COMPLETE' if complete else 'INCOMPLETE',**sides,selected_side=chosen,total=total,risk=risk(total) if total is not None else None,missing_fields=sorted(set(sides['left']['missing_fields']+sides['right']['missing_fields'])))
        photo_measurements=_merge_photo_measurements(_saved_photo_measurements(snapshot,slot),candidate_rows)
        so_far=None if complete or not with_score_so_far else score_so_far(snapshot,slot,current,entry['missing_fields'],photo_measurements)
        if so_far: entry['score_so_far']=so_far
        output.append(entry)
    by_photo={}
    for slot in output: by_photo.setdefault(slot['photo_id'],[]).append(slot)
    for repeated in by_photo.values():
        if len(repeated)>1:
            for slot in repeated:
                slot.update(status='INCOMPLETE',selected_side=None,total=None,risk=None)
                slot.pop('score_so_far',None)
                slot['missing_fields']=sorted(set(slot['missing_fields']+['duplicate_photo_id']))
    done=[s for s in output if s['total'] is not None]; highest=max((s['total'] for s in done),default=None)
    representative=next((s['slot_no'] for s in done if s['total']==highest),None)
    summary=dict(complete_count=len(done),total_slot_count=len(targets),available_max=highest,full_max=highest if len(done)==len(targets) and bool(targets) else None,representative_slot_no=representative,selection='AUTO' if done else None)
    unfinished=[s for s in output if 'score_so_far' in s]
    if unfinished:
        best=max(unfinished,key=lambda s:s['score_so_far']['total'])
        summary['score_so_far']=dict(best['score_so_far'],slot_no=best['slot_no'])
    return dict(status='COMPLETE' if len(done)==len(targets) and bool(targets) else 'INCOMPLETE',slots=output,summary=summary)


def assumed_reference_score(slot_no=1, photo_id=0):
    """Numeric no-burden reference for a photo with no usable score evidence."""
    slot=dict(slot_no=slot_no,photo_id=photo_id,analysis_target=True,camera_side='LEFT',forward_direction='SCREEN_RIGHT',
              side_view_verified='YES',observation=dict(load_state='UNLOADED',measured_load_kg=None))
    manual=[dict(slot_no=slot_no,photo_id=photo_id,scope=scope,field=field,value=NO_BURDEN[field])
            for scope,fields in (('COMMON',COMMON),('LEFT',ARM),('RIGHT',ARM)) for field in fields]
    result=calculate_reba(dict(schema_version='2.0',capture=dict(slots=[slot]),manual=manual,settings={}),None,with_score_so_far=False)['slots'][0]
    assumed=sorted([f'{scope.lower()}.{field}' for scope,fields in (('COMMON',COMMON),('LEFT',ARM),('RIGHT',ARM)) for field in fields]+['observation.load_state'])
    return dict(total=result['total'],risk=result['risk'],kind='ASSUMED_REFERENCE',source='ASSUMED_REFERENCE',selected_side=result['selected_side'],left=result['left']['total'],right=result['right']['total'],
                assumed=assumed,assumption='측정값이나 충분한 답변이 없어 모든 REBA 항목을 부담 없음으로 둔 참조용 가정 점수입니다. 측정·확정 점수가 아닙니다.')


def _saved_photo_view(snapshot, photo_id):
    session=((snapshot.get('conditions') or {}).get(AUXILIARY_CONDITION_KEYS[0]) or {})
    views=((session.get('photo_observations') or {}).get('views') or {})
    value=views.get(str(photo_id)) or views.get(photo_id) or {}
    return value if isinstance(value,dict) else {}


def _manual_for_slot(snapshot, slot):
    current={};conflict=False;answers=False
    for item in snapshot.get('manual') or []:
        if item.get('slot_no')!=slot.get('slot_no') or item.get('photo_id')!=slot.get('photo_id'):
            continue
        scope,field,value=item.get('scope'),item.get('field'),item.get('value')
        if scope not in ('COMMON','LEFT','RIGHT') or field not in COMMON+ARM or value in (None,'UNKNOWN'):
            continue
        key=(scope,field)
        if key in current and current[key]!=value:
            conflict=True
            current.pop(key,None)
            continue
        if key not in current: current[key]=value
        if item.get('source') not in ('AUTO_ACCEPTED','POSE','MOVENET','VISION'):
            answers=True
    return current,conflict,answers


def _photo_baseline(snapshot, slot, reba_slot):
    """Reconstruct a same-photo baseline from immutable intake observations/candidates."""
    from . import quick_assess
    if _photo_measurements_refused(snapshot,slot):return None
    measurements=_merge_photo_measurements(_saved_photo_measurements(snapshot,slot),reba_slot.get('candidates') or [])
    measurements=[item for item in measurements if item['field']!='coupling']
    view=_saved_photo_view(snapshot,slot.get('photo_id'))
    front=copy.deepcopy(view.get('front') or [])
    if not front:
        facts=((snapshot.get('conditions') or {}).get(AUXILIARY_CONDITION_KEYS[0]) or {}).get('photo_observations') or {}
        for item in facts.get('observations') or []:
            if item.get('photo_id')!=slot.get('photo_id') or item.get('value')!='YES': continue
            key={( 'COMMON','trunk_side_bent'):'trunk_turn',('COMMON','neck_side_bent'):'neck_turn',
                 ('LEFT','arm_abducted_or_rotated'):'arm_abducted',('RIGHT','arm_abducted_or_rotated'):'arm_abducted'}.get((item.get('scope'),item.get('field')))
            if key and not any(row.get('key')==key for row in front): front.append(dict(key=key,suggested=True))
    seated=bool((view.get('signals') or {}).get('seated'))
    if not measurements and not any(item.get('suggested') for item in front) and not seated:
        return None
    settings=(snapshot.get('settings') or {})
    if 'pose_model' not in settings: settings=dict(settings,pose_model={})
    first=quick_assess.provisional(measurements,front,settings,seated)
    return dict(first,kind='WITH_ASSUMPTIONS',source='FIRST_PASS',slot_no=slot['slot_no'],photo_count=1)


def _slot_current_candidate(snapshot, slot, reba_slot, photo_measurements):
    current,manual_conflict,has_answers=_manual_for_slot(snapshot,slot)
    if manual_conflict:
        ref=assumed_reference_score(slot['slot_no'],slot['photo_id'])
        ref['assumption']+=' 서로 다른 수동 입력이 충돌해 실제 입력을 임의로 고르지 않았습니다.'
        return dict(total=ref['total'],risk=ref['risk'],kind='ASSUMED_REFERENCE',source='ASSUMED_REFERENCE',slot_no=slot['slot_no'],assumed=ref['assumed'],assumption=ref['assumption'])
    observation=slot.get('observation') or {}
    load_state=observation.get('load_state','UNKNOWN');load_value=observation.get('measured_load_kg')
    load_conflict=_conflicting_load(observation)
    open_paths=list(reba_slot.get('missing_fields') or [])
    if not open_paths:
        for scope,fields in (('COMMON',COMMON),('LEFT',ARM),('RIGHT',ARM)):
            open_paths.extend(f'{scope.lower()}.{field}' for field in fields if current.get((scope,field)) in (None,'UNKNOWN'))
    answer=score_so_far(snapshot,slot,current,open_paths,photo_measurements,require_anchor=False)
    if answer is None:
        ref=assumed_reference_score(slot['slot_no'],slot['photo_id'])
        ref['assumption']+=' 저장 입력이 유효한 점수로 계산되지 않아 원본을 유지하고 참조값을 표시합니다.'
        return dict(total=ref['total'],risk=ref['risk'],kind='ASSUMED_REFERENCE',source='ASSUMED_REFERENCE',slot_no=slot['slot_no'],assumed=ref['assumed'],assumption=ref['assumption'])
    has_load_answer=not load_conflict and (load_state=='UNLOADED' or load_state=='MEASURED' and load_value is not None)
    has_photo=bool(answer.get('photo_measurements') or answer.get('unconfirmed_photo'))
    has_manual=bool(current)
    if load_conflict:
        answer['assumption'] += ' 서로 맞지 않는 하중 입력은 원본을 유지하고 점수에는 반영하지 않았습니다.'
    if not has_manual and not has_photo and not has_load_answer:
        kind,source='ASSUMED_REFERENCE','ASSUMED_REFERENCE'
    else:
        kind='WITH_ASSUMPTIONS'
        source='ANSWERS_SO_FAR' if has_answers or has_load_answer else 'FIRST_PASS'
    if kind=='ASSUMED_REFERENCE' and not has_manual and not has_photo and not has_load_answer:
        answer=assumed_reference_score(slot['slot_no'],slot['photo_id'])
    return dict(total=answer['total'],risk=answer['risk'],kind=kind,source=source,slot_no=slot['slot_no'],
                assumed=answer.get('assumed') or [],assumption=answer.get('assumption') or '',
                **(dict(measurement_refs=copy.deepcopy(answer['measurement_refs'])) if answer.get('measurement_refs') else {}))


def _valid_score(value):
    return isinstance(value,dict) and type(value.get('total')) is int and 1<=value['total']<=15 and value.get('risk')==risk(value['total'])


def project_current_score(reba):
    """Return the single display score selected from a REBA object; never mutate it."""
    if not isinstance(reba,dict): return None
    summary=reba.get('summary') or {}
    saved=summary.get('current_score')
    if _valid_score(saved) and saved.get('kind') in ('CONFIRMED','WITH_ASSUMPTIONS','ASSUMED_REFERENCE'):
        return copy.deepcopy(saved)
    candidates=[]
    for slot in reba.get('slots') or []:
        if not isinstance(slot,dict): continue
        if slot.get('status')!='INCOMPLETE' and _valid_score(slot):
            candidates.append(dict(total=slot['total'],risk=slot['risk'],kind='CONFIRMED',source='COMPLETE',slot_no=slot.get('slot_no'),
                                   complete_count=summary.get('complete_count',0),total_slot_count=summary.get('total_slot_count',len(reba.get('slots') or [])),assumed=[],assumption=''))
        partial=slot.get('score_so_far')
        if _valid_score(partial): candidates.append(dict(total=partial['total'],risk=partial['risk'],kind=partial.get('kind') if partial.get('kind') in ('CONFIRMED','WITH_ASSUMPTIONS','ASSUMED_REFERENCE') else 'WITH_ASSUMPTIONS',source=partial.get('source') or 'ANSWERS_SO_FAR',slot_no=slot.get('slot_no'),
            complete_count=summary.get('complete_count',0),total_slot_count=summary.get('total_slot_count',len(reba.get('slots') or [])),assumed=partial.get('assumed') or [],assumption=partial.get('assumption') or ''))
    partial=summary.get('score_so_far')
    if not candidates and _valid_score(partial):
        candidates.append(dict(total=partial['total'],risk=partial['risk'],kind=partial.get('kind') if partial.get('kind') in ('CONFIRMED','WITH_ASSUMPTIONS','ASSUMED_REFERENCE') else 'WITH_ASSUMPTIONS',source=partial.get('source') or 'ANSWERS_SO_FAR',slot_no=partial.get('slot_no'),
            complete_count=summary.get('complete_count',0),total_slot_count=summary.get('total_slot_count',len(reba.get('slots') or [])),assumed=partial.get('assumed') or [],assumption=partial.get('assumption') or ''))
    first=summary.get('first_pass')
    if not candidates and _valid_score(first):
        candidates.append(dict(total=first['total'],risk=first['risk'],kind='WITH_ASSUMPTIONS',source='FIRST_PASS',slot_no=first.get('slot_no'),
            complete_count=summary.get('complete_count',0),total_slot_count=summary.get('total_slot_count',len(reba.get('slots') or [])),assumed=first.get('assumed') or [],assumption=first.get('assumption') or ''))
    if candidates:
        priority={'CONFIRMED':0,'WITH_ASSUMPTIONS':1,'ASSUMED_REFERENCE':2}
        return max(candidates,key=lambda item:(item['total'],-priority.get(item['kind'],3),-(item.get('slot_no') or 0)))
    count=summary.get('total_slot_count',len(reba.get('slots') or []))
    if type(count) is not int or count<=0: return None
    slot_no=next((slot.get('slot_no') for slot in reba.get('slots') or [] if type(slot.get('slot_no')) is int),1)
    return dict(assumed_reference_score(slot_no),kind='ASSUMED_REFERENCE',source='ASSUMED_REFERENCE',slot_no=slot_no,
                complete_count=summary.get('complete_count',0),total_slot_count=count)


def project_score_continuity(analysis):
    """Build current score, first-pass, and landmark quality as a non-mutating read projection."""
    from .measurement_quality import from_analysis
    value=copy.deepcopy(analysis)
    if not isinstance(value,dict): return value
    value['measurement_quality']=from_analysis(value)
    snapshot=value.get('snapshot') or {};reba=value.get('reba')
    if snapshot.get('schema_version')!='2.0' or not isinstance(reba,dict): return value
    # Older/minimal analysis snapshots may omit the optional capture observation.
    # Supply an UNKNOWN value only on this private scoring copy; never rewrite the
    # immutable snapshot returned to callers or stored by the service.
    scoring_snapshot=copy.deepcopy(snapshot)
    targets=[slot for slot in (scoring_snapshot.get('capture') or {}).get('slots',[]) if slot.get('analysis_target',True) and slot.get('photo_id') is not None]
    for slot in targets:
        slot.setdefault('observation',dict(load_state='UNKNOWN',measured_load_kg=None))
    if not targets:
        return value
    try:
        fresh=calculate_reba(scoring_snapshot,value.get('pose'))
        fresh_by={(slot.get('slot_no'),slot.get('photo_id')):slot for slot in fresh.get('slots') or []}
    except (KeyError,TypeError,ValueError,IndexError):
        fresh_by={}
    old_by={(slot.get('slot_no'),slot.get('photo_id')):slot for slot in reba.get('slots') or []}
    # Older response DTOs can omit photo_id while retaining a unique slot owner.
    # Reuse that row instead of appending a duplicate slot and hiding its saved
    # component scores. An explicit different photo_id is never borrowed.
    for target in targets:
        key=(target.get('slot_no'),target.get('photo_id'))
        anonymous=[row for row in reba.get('slots') or [] if row.get('slot_no')==key[0] and row.get('photo_id') is None]
        if key not in old_by and len(anonymous)==1 and sum(other.get('slot_no')==key[0] for other in targets)==1:
            old_by[key]=anonymous[0]
    summary=reba.setdefault('summary',{})
    first_passes=[];current_candidates=[]
    duplicate_ids={slot['photo_id'] for slot in targets if sum(1 for other in targets if other.get('photo_id')==slot.get('photo_id'))>1}
    for target in targets:
        key=(target.get('slot_no'),target.get('photo_id'));old=old_by.get(key) or {};computed=fresh_by.get(key) or {}
        photos=_merge_photo_measurements(_saved_photo_measurements(scoring_snapshot,target),computed.get('candidates') or old.get('candidates') or [])
        first=None if target.get('photo_id') in duplicate_ids else _photo_baseline(scoring_snapshot,target,dict(computed,**({} if computed.get('candidates') else {'candidates':old.get('candidates') or []})))
        if first: first_passes.append(first)
        if old.get('status')!='COMPLETE' or old.get('total') is None:
            if target.get('photo_id') in duplicate_ids:
                ref=assumed_reference_score(target['slot_no'],target['photo_id'])
                current_candidates.append(dict(total=ref['total'],risk=ref['risk'],kind='ASSUMED_REFERENCE',source='ASSUMED_REFERENCE',slot_no=target['slot_no'],
                    complete_count=summary.get('complete_count',0),total_slot_count=summary.get('total_slot_count',len(targets)),assumed=ref['assumed'],assumption=ref['assumption']+' 같은 사진이 여러 슬롯에 중복되어 참조용으로 표시합니다.'))
                continue
            candidate=_slot_current_candidate(scoring_snapshot,target,dict(old or computed),photos)
            if candidate:
                candidate.update(complete_count=summary.get('complete_count',0),total_slot_count=summary.get('total_slot_count',len(targets)))
                current_candidates.append(candidate)
            elif first and target.get('photo_id') not in duplicate_ids:
                current_candidates.append(dict(total=first['total'],risk=first['risk'],kind='WITH_ASSUMPTIONS',source='FIRST_PASS',slot_no=target['slot_no'],
                    complete_count=summary.get('complete_count',0),total_slot_count=summary.get('total_slot_count',len(targets)),assumed=first.get('assumed') or [],assumption=first.get('assumption') or ''))
            else:
                ref=assumed_reference_score(target['slot_no'],target['photo_id'])
                current_candidates.append(dict(total=ref['total'],risk=ref['risk'],kind='ASSUMED_REFERENCE',source='ASSUMED_REFERENCE',slot_no=target['slot_no'],
                    complete_count=summary.get('complete_count',0),total_slot_count=summary.get('total_slot_count',len(targets)),assumed=ref['assumed'],assumption=ref['assumption']))
        else:
            current_candidates.append(dict(total=old['total'],risk=old.get('risk') or risk(old['total']),kind='CONFIRMED',source='COMPLETE',slot_no=target['slot_no'],
                complete_count=summary.get('complete_count',0),total_slot_count=summary.get('total_slot_count',len(targets)),assumed=[],assumption=''))
        if key in old_by and key in fresh_by and 'score_so_far' not in old and 'score_so_far' in computed:
            old_by[key]['score_so_far']=copy.deepcopy(computed['score_so_far'])
    if first_passes:
        summary['first_pass']=max(first_passes,key=lambda item:(item['total'],-item['slot_no']))
    else:
        summary.pop('first_pass',None)
    # Every photo consumer receives the same score chosen for this photo.
    # The task summary is an aggregate and must never be borrowed by another row.
    for target,candidate in zip(targets,current_candidates):
        key=(target.get('slot_no'),target.get('photo_id'))
        row=old_by.get(key)
        if row is None:
            row=copy.deepcopy(fresh_by.get(key) or dict(slot_no=key[0],photo_id=key[1],status='INCOMPLETE',total=None,risk=None))
            reba.setdefault('slots',[]).append(row)
        row['current_score']=copy.deepcopy(candidate)
    if current_candidates:
        priority={'CONFIRMED':0,'WITH_ASSUMPTIONS':1,'ASSUMED_REFERENCE':2}
        summary['current_score']=max(current_candidates,key=lambda item:(item['total'],-priority.get(item['kind'],3),-item['slot_no']))
    else:
        summary['current_score']=None
    return value
