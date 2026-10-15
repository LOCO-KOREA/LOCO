"""Pure DTO helpers and REBA calculations. No database access."""
from datetime import datetime, timezone

PHASES = ['CYCLE_START', 'LIFT_OFF', 'MID_LIFT', 'SHELF_APPROACH', 'CYCLE_END']
PHASE_NAMES = ['손 닿기 전', '바닥 분리 직후', '바닥면 절반 높이', '선반 접촉 직전', '손 놓은 후']
EXPOSURES = ['C1_KEYBOARD_FOCUSED', 'C2_NECK', 'C2_SHOULDER', 'C2_ELBOW', 'C2_WRIST', 'C2_HAND', 'C3_UNION', 'C4_NECK_FLEX', 'C4_TRUNK_FLEX', 'C4_TRUNK_EXT', 'C4_NECK_TWIST', 'C4_TRUNK_TWIST', 'C4_UNION', 'C5_SQUAT', 'C5_KNEEL', 'C5_UNION', 'C6_QUALIFYING', 'C7_QUALIFYING', 'C10_LIFT', 'C11_IMPACT']
COMMON = ['trunk_base', 'trunk_twisted', 'trunk_side_bent', 'neck_base', 'neck_twisted', 'neck_side_bent', 'legs_support', 'seated', 'knee_band', 'shock_force', 'static_over_1min', 'small_repeat_over_4min', 'rapid_change_or_unstable']
ARM = ['upper_arm_base', 'arm_abducted_or_rotated', 'shoulder_raised', 'arm_supported_or_gravity_assisted', 'lower_arm_base', 'wrist_base', 'wrist_deviated_or_twisted', 'coupling']
TAG_FIELDS = ['hand_above_head', 'elbow_above_shoulder', 'elbow_behind_trunk', 'squat', 'kneel']
TAGS = ['NECK_FORWARD_PROXY', 'TRUNK_FLEX', 'TRUNK_EXT', 'UPPER_ARM_RAISE', 'HAND_ABOVE_HEAD', 'ELBOW_ABOVE_SHOULDER', 'ELBOW_BEHIND_TRUNK', 'NECK_TWIST', 'TRUNK_TWIST', 'SQUAT', 'KNEEL']
TABLE_A = [[1,2,3,4,1,2,3,4,3,3,5,6],[2,3,4,5,3,4,5,6,4,5,6,7],[2,4,5,6,4,5,6,7,5,6,7,8],[3,5,6,7,5,6,7,8,6,7,8,9],[4,6,7,8,6,7,8,9,7,8,9,9]]
TABLE_B = [[1,2,2,1,2,3],[1,2,3,2,3,4],[3,4,5,4,5,5],[4,5,5,5,6,7],[6,7,8,7,8,8],[7,8,8,8,9,9]]
TABLE_C = [[1,1,1,2,3,3,4,5,6,7,7,7],[1,2,2,3,4,4,5,6,6,7,7,8],[2,3,3,3,4,5,6,7,7,8,8,8],[3,4,4,4,5,6,7,8,8,9,9,9],[4,4,4,5,6,7,8,8,9,9,9,9],[6,6,6,7,8,8,9,9,10,10,10,10],[7,7,7,8,9,9,9,10,10,11,11,11],[8,8,8,9,10,10,10,10,10,11,11,11],[9,9,9,10,10,10,11,11,11,12,12,12],[10,10,10,11,11,11,11,12,12,12,12,12],[11,11,11,11,12,12,12,12,12,12,12,12],[12,12,12,12,12,12,12,12,12,12,12,12]]

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
    return dict(analysis=dict(pose_model=dict(name='MoveNet Lightning singlepose TFLite float16', version='4', preprocess_version='EXIF_LETTERBOX_V1', input_size=192, point_count=17, confidence_min=0.5), posture_profile=dict(version='POSTURE_TECH_V1', neck_forward_deg=20, trunk_flex_deg=20, trunk_extension_deg=-20, upper_arm_raise_deg=45), reba_rule='REBA_TABLE_2000_V2', burden_rule='MOEL_2020_12_V1'), gpt_enabled=False, gpt_model='', ui=dict(loco_visible=True,loco_mode='normal'))

def exclusions(c):
    m, d = c.get('planned_duration_months'), c.get('annual_work_days')
    short = 'UNKNOWN' if m is not None and m < 0 else ('NO' if c.get('one_off') == 'NO' or m is not None and m > 2 else 'YES' if c.get('one_off') == 'YES' and m is not None else 'UNKNOWN')
    intermittent = 'UNKNOWN' if d is None or d < 0 else 'YES' if d <= 60 else 'NO'
    return dict(short_term=short, intermittent=intermittent)

def risk(total):
    return 'NEGLIGIBLE' if total == 1 else 'LOW' if total <= 3 else 'MEDIUM' if total <= 7 else 'HIGH' if total <= 10 else 'VERY_HIGH'

def candidates(slot, pose, camera_side):
    angles = (pose or {}).get('angles', [])
    specs = [('COMMON','trunk_base',[camera_side],'TRUNK_TILT_VERT'),('COMMON','knee_band',['LEFT','RIGHT'],'KNEE_FLEX')]
    specs += [(side,field,[side],code) for side in ['LEFT','RIGHT'] for field,code in [('upper_arm_base','UPPER_ARM_FLEX_TRUNK'),('lower_arm_base','ELBOW_FLEX')]]
    result=[]
    for scope,field,sides,code in specs:
        refs=[a for a in angles if a['side'] in sides and a['angle_code']==code]
        usable=len(refs)==len(sides) and all(a['value_deg'] is not None and (a['min_confidence'] or 0)>=0.5 for a in refs)
        value=None; reasons=[]
        if usable:
            angle=max(a['value_deg'] for a in refs)
            if field=='trunk_base': value=1 if angle==0 else 2 if -20<=angle<=20 else 3 if angle<=60 else 4; bounds=[-20,0,20,60]
            elif field=='upper_arm_base': value=1 if -20<=angle<=20 else 2 if angle< -20 or angle<=45 else 3 if angle<=90 else 4; bounds=[-20,20,45,90]
            elif field=='lower_arm_base': value=1 if 60<=angle<=100 else 2; bounds=[60,100]
            else: value='UNDER_30' if angle<30 else 'FROM_30_TO_60' if angle<=60 else 'OVER_60'; bounds=[30,60]
            if any(abs(a['value_deg']-b)<=5 for a in refs for b in bounds): reasons=['BOUNDARY_REVIEW']
        result.append(dict(slot_no=slot['slot_no'],photo_id=slot['photo_id'],scope=scope,field=field,proposed_value=value,angles=refs,min_confidence=min(a['min_confidence'] for a in refs) if usable else None,review_reasons=reasons,diagnostics=[] if usable else [diagnostic('MISSING_ANGLE','후보에 필요한 관절·각도가 없습니다')]))
    return result

def calculate_reba(snapshot, pose):
    output=[]
    for slot in snapshot['capture']['slots']:
        number=slot['slot_no']; obs=slot['observation']; expected='UNLOADED' if slot['phase'] in [PHASES[0],PHASES[4]] else 'FULL_BOX'
        load=0 if expected=='UNLOADED' else snapshot['conditions'].get('box_mass_kg')
        if obs['phase_verified']!='YES' or obs['load_state']!=expected: load=None
        current={ (v['scope'],v['field']):v['value'] for v in snapshot['manual'] if v['slot_no']==number and v['photo_id']==slot['photo_id'] }
        sides={}
        for side in ['LEFT','RIGHT']:
            missing=[]; reasons=[]; values={}
            for scope, fields in [('COMMON',COMMON),(side,ARM)]:
                for field in fields:
                    val=current.get((scope,field)); values[field]=val
                    if val is None or val=='UNKNOWN': missing.append(f'{scope.lower()}.{field}')
            if slot['photo_id'] is None: missing.append('photo_id')
            if load is None: missing.append('effective_load_kg')
            keys=['trunk','neck','legs','table_a','load_score','score_a','upper_arm','lower_arm','wrist','table_b','coupling_score','score_b','table_c','activity_score','total']
            score=dict.fromkeys(keys); score.update(side=side,risk=None,missing_fields=missing,review_reasons=reasons)
            if not missing:
                try:
                    for field in COMMON+ARM:
                        value=values[field]
                        if field in ['trunk_base','neck_base','upper_arm_base','lower_arm_base','wrist_base']:
                            limit={'trunk_base':4,'neck_base':2,'upper_arm_base':4,'lower_arm_base':2,'wrist_base':2}[field]
                            if value not in range(1,limit+1): raise ValueError(field)
                        elif field=='legs_support' and value not in ['BILATERAL_STABLE','UNILATERAL_OR_UNSTABLE']: raise ValueError(field)
                        elif field=='knee_band' and value not in ['UNDER_30','FROM_30_TO_60','OVER_60']: raise ValueError(field)
                        elif field=='coupling' and (value not in (['NOT_APPLICABLE'] if expected=='UNLOADED' else ['GOOD','FAIR','POOR','UNACCEPTABLE'])): raise ValueError(field)
                        elif field not in ['legs_support','knee_band','coupling'] and field not in ['trunk_base','neck_base','upper_arm_base','lower_arm_base','wrist_base'] and value not in ['YES','NO']: raise ValueError(field)
                    if load<0 or expected=='FULL_BOX' and load<=0: raise ValueError('box_mass_kg')
                    yes=lambda f:int(values[f]=='YES')
                    trunk=values['trunk_base']+int(yes('trunk_twisted') or yes('trunk_side_bent'))
                    neck=values['neck_base']+int(yes('neck_twisted') or yes('neck_side_bent'))
                    legs=(1 if values['legs_support']=='BILATERAL_STABLE' else 2)+(0 if yes('seated') else ['UNDER_30','FROM_30_TO_60','OVER_60'].index(values['knee_band']))
                    upper=max(1,values['upper_arm_base']+yes('arm_abducted_or_rotated')+yes('shoulder_raised')-yes('arm_supported_or_gravity_assisted'))
                    lower=values['lower_arm_base']; wrist=values['wrist_base']+yes('wrist_deviated_or_twisted')
                    a=TABLE_A[trunk-1][(neck-1)*4+legs-1]; ls=(0 if load<5 else 1 if load<=10 else 2)+yes('shock_force')
                    b=TABLE_B[upper-1][(lower-1)*3+wrist-1]; cs=0 if expected=='UNLOADED' else ['GOOD','FAIR','POOR','UNACCEPTABLE'].index(values['coupling'])
                    c=TABLE_C[a+ls-1][b+cs-1]; activity=sum(yes(f) for f in ['static_over_1min','small_repeat_over_4min','rapid_change_or_unstable'])
                    score.update(trunk=trunk,neck=neck,legs=legs,table_a=a,load_score=ls,score_a=a+ls,upper_arm=upper,lower_arm=lower,wrist=wrist,table_b=b,coupling_score=cs,score_b=b+cs,table_c=c,activity_score=activity,total=c+activity,risk=risk(c+activity))
                except (ValueError,IndexError,TypeError): score['review_reasons']=['INPUT_CONFLICT']; score['missing_fields'].append('범주·하중 입력 확인')
            sides[side.lower()]=score
        complete=all(sides[s]['total'] is not None for s in ['left','right'])
        chosen=('LEFT' if sides['left']['total']>=sides['right']['total'] else 'RIGHT') if complete else None
        total=sides[chosen.lower()]['total'] if chosen else None
        ps=next((p for p in (pose or {}).get('slots',[]) if p['slot_no']==number),None)
        output.append(dict(slot_no=number,photo_id=slot['photo_id'],candidates=candidates(slot,ps,snapshot['capture']['camera_side']),load_state=obs['load_state'],effective_load_kg=load,status='COMPLETE' if complete else 'INCOMPLETE',**sides,selected_side=chosen,total=total,risk=risk(total) if total is not None else None,missing_fields=sorted(set(sides['left']['missing_fields']+sides['right']['missing_fields']))))
    done=[s for s in output if s['total'] is not None]; highest=max((s['total'] for s in done),default=None)
    representative=next((s['slot_no'] for s in done if s['total']==highest),None)
    return dict(status='COMPLETE' if len(done)==15 else 'INCOMPLETE',slots=output,summary=dict(complete_count=len(done),total_slot_count=15,available_max=highest,full_max=highest if len(done)==15 else None,representative_slot_no=representative,selection='AUTO' if done else None))
