"""REBA_TABLE_2000_V2 candidates and scores; pure DTO functions."""
from .task_defaults import COMMON, ARM, AUXILIARY_CONDITION_KEYS, diagnostic
from ergo.pose_contract import WRIST_POLICY, PHOTO_SOURCES
import math

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

def score_so_far(snapshot, slot, current, open_paths):
    """Score of the answers so far, every open item at its no-burden option; None until trunk and an upper arm are known (assumptions alone read as negligible).

    shortcut: arm support and sitting are assumed NO although YES scores lower, so this is not a strict minimum; upgrade if a lower bound is ever promised.
    """
    borrowed = []
    saved = ((snapshot.get('conditions') or {}).get(AUXILIARY_CONDITION_KEYS[0]) or {}).get('facts') or {}
    confirmation = saved.get('context@default') or {}
    # While the photo confirmation is unanswered, readings the task does not project yet are borrowed and named. They were already filtered by view and confidence.
    if not (confirmation.get('state') == 'KNOWN' or confirmation.get('state') == 'UNKNOWN' and confirmation.get('source') == 'USER'):
        for item in saved.values():
            parts = item.get('target', '').split('.')
            if (len(parts) == 3 and parts[0] == 'manual' and item.get('source') in PHOTO_SOURCES and item.get('state') == 'KNOWN' and not item.get('alias_of')
                    and item.get('photo_id') == slot['photo_id'] and item.get('value') is not None and current.get((parts[1], parts[2])) in (None, 'UNKNOWN')):
                current = {**current, (parts[1], parts[2]): item['value']}
                borrowed.append(f'{parts[1].lower()}.{parts[2]}')
    known = lambda scope, field: current.get((scope, field)) not in (None, 'UNKNOWN')
    if not (known('COMMON', 'trunk_base') and (known('LEFT', 'upper_arm_base') or known('RIGHT', 'upper_arm_base'))):
        return None
    obs = dict(slot['observation'])
    assumed = sorted(path for path in open_paths if path.split('.')[0] in ('common', 'left', 'right') and path not in borrowed)
    note = '지금까지 확인한 값으로 계산하고, 확인하지 못한 항목은 부담 없음으로 가정한 점수입니다. 실제 점수는 더 높을 수 있고 확정 점수가 아닙니다.'
    if obs.get('load_state', 'UNKNOWN') == 'UNKNOWN' and obs.get('measured_load_kg') is None:
        obs['load_state'] = 'UNLOADED'
        assumed.append('observation.load_state')
        note += ' 들고 있는 물건이 있는지 몰라 없는 것으로 계산했어요.'
    carrying = obs.get('load_state') == 'MEASURED' and obs.get('measured_load_kg') != 0
    rows = []
    for scope, fields in (('COMMON', COMMON), ('LEFT', ARM), ('RIGHT', ARM)):
        for field in fields:
            value = current.get((scope, field))
            if value in (None, 'UNKNOWN'):
                value = 'GOOD' if field == 'coupling' and carrying else NO_BURDEN[field]
            rows.append(dict(slot_no=slot['slot_no'], photo_id=slot['photo_id'], scope=scope, field=field, value=value))
    filled = dict(snapshot, capture=dict(slots=[dict(slot, observation=obs)]), manual=rows)
    result = calculate_reba(filled, None, with_score_so_far=False)['slots'][0]
    if result['total'] is None:
        return None
    so_far = dict(total=result['total'], risk=result['risk'], selected_side=result['selected_side'], left=result['left']['total'],
                  right=result['right']['total'], assumed=assumed, assumption=note)
    if borrowed: so_far['unconfirmed_photo'] = sorted(borrowed)
    return so_far

def candidates(slot, pose, camera_side, confidence_min=0.5):
    angles = (pose or {}).get('angles', [])
    observation=slot.get('observation') or {}
    context_ok=(camera_side in ('LEFT','RIGHT') and slot.get('forward_direction') in ('SCREEN_RIGHT','SCREEN_LEFT') and
        slot.get('side_view_verified')=='YES' and observation.get('single_person')=='YES' and
        observation.get('full_frame')=='YES' and observation.get('normal_work')=='YES')
    specs = [('COMMON','trunk_base',[camera_side],'TRUNK_TILT_VERT'),('COMMON','knee_band',['LEFT','RIGHT'],'KNEE_FLEX')]
    specs += [(side,field,[side],code) for side in ['LEFT','RIGHT'] for field,code in [('upper_arm_base','UPPER_ARM_FLEX_TRUNK'),('lower_arm_base','ELBOW_FLEX')]]
    if any(a['angle_code']==WRIST_POLICY['angle_code'] for a in angles):
        specs += [(side,'wrist_base',[side],WRIST_POLICY['angle_code']) for side in ['LEFT','RIGHT']]
    result=[]
    for scope,field,sides,code in specs:
        refs=[a for a in angles if a['side'] in sides and a['angle_code']==code]
        usable=context_ok and len(refs)==len(sides) and all(a['value_deg'] is not None and (a['min_confidence'] or 0)>=confidence_min for a in refs)
        if field=='wrist_base':
            usable=usable and all(a.get('measurement',{}).get('coordinate_space')=='ORIGINAL_IMAGE_2D' and
                a.get('measurement',{}).get('used_world_coordinates') is False and
                (a.get('measurement',{}).get('auto_eligible') or a.get('diagnostic_code')=='WRIST_BOUNDARY') for a in refs)
        value=None; reasons=[]
        if usable:
            angle=max(a['value_deg'] for a in refs)
            if field=='trunk_base': value=1 if angle==0 else 2 if -20<=angle<=20 else 3 if angle<=60 else 4; bounds=[-20,0,20,60]
            elif field=='upper_arm_base': value=1 if -20<=angle<=20 else 2 if angle< -20 or angle<=45 else 3 if angle<=90 else 4; bounds=[-20,20,45,90]
            elif field=='lower_arm_base': value=1 if 60<=angle<=100 else 2; bounds=[60,100]
            elif field=='wrist_base': value=1 if angle<=WRIST_POLICY['category_boundary_deg'] else 2; bounds=[WRIST_POLICY['category_boundary_deg']]
            else: value='UNDER_30' if angle<30 else 'FROM_30_TO_60' if angle<=60 else 'OVER_60'; bounds=[30,60]
            margin=WRIST_POLICY['boundary_margin_deg'] if field=='wrist_base' else 5
            if any(abs(a['value_deg']-b)<=margin for a in refs for b in bounds) or field=='wrist_base' and any(a.get('diagnostic_code')=='WRIST_BOUNDARY' for a in refs): reasons=['BOUNDARY_REVIEW']
        if not context_ok: note=diagnostic('CAPTURE_CONTEXT_UNCONFIRMED','측면·전방·단일 작업자·전신·통상 작업 확인이 필요합니다','capture.observation')
        elif not usable: note=diagnostic('MISSING_ANGLE','후보에 필요한 관절·각도가 없습니다')
        else: note=None
        result.append(dict(slot_no=slot['slot_no'],photo_id=slot['photo_id'],scope=scope,field=field,proposed_value=value,angles=refs,min_confidence=min(a['min_confidence'] for a in refs) if usable else None,review_reasons=reasons,diagnostics=[note] if note else []))
    return result

def calculate_reba(snapshot, pose, with_score_so_far=True):
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
                        elif field=='coupling' and (value not in (['NOT_APPLICABLE'] if load==0 else ['GOOD','FAIR','POOR','UNACCEPTABLE'])): raise ValueError(field)
                        elif field not in ['legs_support','knee_band','coupling'] and field not in ['trunk_base','neck_base','upper_arm_base','lower_arm_base','wrist_base'] and value not in ['YES','NO']: raise ValueError(field)
                    if isinstance(load,bool) or not isinstance(load,(int,float)) or load<0 or not math.isfinite(load): raise ValueError('effective_load_kg')
                    yes=lambda f:int(values[f]=='YES')
                    trunk=values['trunk_base']+int(yes('trunk_twisted') or yes('trunk_side_bent'))
                    neck=values['neck_base']+int(yes('neck_twisted') or yes('neck_side_bent'))
                    legs=(1 if values['legs_support']=='BILATERAL_STABLE' else 2)+(0 if yes('seated') else ['UNDER_30','FROM_30_TO_60','OVER_60'].index(values['knee_band']))
                    upper=max(1,values['upper_arm_base']+yes('arm_abducted_or_rotated')+yes('shoulder_raised')-yes('arm_supported_or_gravity_assisted'))
                    lower=values['lower_arm_base']; wrist=values['wrist_base']+yes('wrist_deviated_or_twisted')
                    a=TABLE_A[trunk-1][(neck-1)*4+legs-1]; ls=(0 if load<5 else 1 if load<=10 else 2)+yes('shock_force')
                    b=TABLE_B[upper-1][(lower-1)*3+wrist-1]; cs=0 if load==0 else ['GOOD','FAIR','POOR','UNACCEPTABLE'].index(values['coupling'])
                    c=TABLE_C[a+ls-1][b+cs-1]; activity=sum(yes(f) for f in ['static_over_1min','small_repeat_over_4min','rapid_change_or_unstable'])
                    score.update(trunk=trunk,neck=neck,legs=legs,table_a=a,load_score=ls,score_a=a+ls,upper_arm=upper,lower_arm=lower,wrist=wrist,table_b=b,coupling_score=cs,score_b=b+cs,table_c=c,activity_score=activity,total=c+activity,risk=risk(c+activity))
                except (ValueError,IndexError,TypeError): score['review_reasons']=['INPUT_CONFLICT']; score['missing_fields'].append('범주·하중 입력 확인')
            sides[side.lower()]=score
        complete=all(sides[s]['total'] is not None for s in ['left','right'])
        chosen=('LEFT' if sides['left']['total']>=sides['right']['total'] else 'RIGHT') if complete else None
        total=sides[chosen.lower()]['total'] if chosen else None
        ps=next((p for p in (pose or {}).get('slots',[]) if p['slot_no']==number),None)
        camera=slot.get('camera_side'); confidence=(snapshot.get('settings') or {}).get('pose_model',{}).get('confidence_min',0.5)
        entry=dict(slot_no=number,photo_id=slot['photo_id'],candidates=candidates(slot,ps,camera,confidence),load_state=obs.get('load_state','UNKNOWN'),effective_load_kg=load,status='COMPLETE' if complete else 'INCOMPLETE',**sides,selected_side=chosen,total=total,risk=risk(total) if total is not None else None,missing_fields=sorted(set(sides['left']['missing_fields']+sides['right']['missing_fields'])))
        so_far=None if complete or not with_score_so_far else score_so_far(snapshot,slot,current,entry['missing_fields'])
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
