"""Direct-exposure draft judgments for MOEL_2020_12_V1; no photo ratios."""
from .task_defaults import exclusions, evidence

def calculate(conditions, legal):
    ex=exclusions(conditions); exposures={x['condition_code']:x for x in legal['exposures']}; output=[]
    for criterion in legal['criteria']:
        n=criterion['criterion_no']; basis=[]; missing=[]; conflicts=[]; reasons=[]; predicates=[]
        def compare(path,value,threshold,unit='MIN_DAY',limit=None):
            basis.append(dict(item_code=path,value=value,unit=unit,operator='GE',threshold=threshold,source='DIRECT_INPUT'))
            if value is None: return None,[path]
            if not isinstance(value,(int,float)) or value<0 or limit is not None and value>limit:
                conflicts.append(path); return None,[]
            return value>=threshold,[]
        def truth(path,value):
            basis.append(dict(item_code=path,value=value,unit='BOOLEAN',operator='EQ',threshold=None,source='DIRECT_INPUT'))
            return (True,[]) if value=='YES' else (False,[]) if value=='NO' else (None,[path])
        def either(items):
            if any(v is True for v,m in items): return True,[]
            if all(v is False for v,m in items): return False,[]
            return None,[p for v,m in items if v is None for p in m]
        def field(name,threshold,unit='KG'):
            return compare(f'criteria.{n}.{name}',criterion.get(name),threshold,unit)
        def duration(code,threshold):
            value=exposures[code]['minutes']; total=conditions.get('daily_work_min')
            result=compare(f'exposures.{code}.minutes',value,threshold,limit=1440)
            if total is not None and (total<0 or total>1440): conflicts.append('conditions.daily_work_min')
            if value is not None and total is not None and value>total: conflicts.append(f'exposures.{code}.minutes')
            if result[0] is True and total is None: return None,['conditions.daily_work_min']
            return result
        def grouped(codes,union,threshold,counts=False):
            raw=[criterion.get(code) if counts else exposures[code]['minutes'] for code in codes]
            uv=criterion.get(union) if counts else exposures[union]['minutes']
            items=[field(code,threshold,'COUNT_DAY') if counts else duration(code,threshold) for code in codes]
            un=field(union,threshold,'COUNT_DAY') if counts else duration(union,threshold)
            if uv is not None:
                known=[v for v in raw if v is not None]
                if known and uv<max(known) or len(known)==len(raw) and uv>sum(known): conflicts.append(f'criteria.{n}.{union}' if counts else f'exposures.{union}.minutes')
                if counts and legal.get('lift_count_day') is not None and uv>legal['lift_count_day']: conflicts.append(f'criteria.{n}.{union}')
            if any(v is True for v,m in items): return True,[]
            if un[0] is False: return False,[]
            if un[0] is True:
                reasons.append('COMBINATION_RULE')
                return (None,[p for v,m in items if v is None for p in m]) if any(v is None for v,m in items) else (True,[])
            return None,[p for v,m in items+[un] if v is None for p in m]
        excluded=[k for k,v in ex.items() if v=='YES']; exclusion='BOTH' if len(excluded)==2 else 'SHORT_TERM' if 'short_term' in excluded else 'INTERMITTENT' if excluded else None
        predicates.append(truth(f'criteria.{n}.condition_present',criterion['condition_present']))
        used=[]
        if n==1: used=['C1_KEYBOARD_FOCUSED']; predicates.append(duration(used[0],240))
        elif n==2: used=['C2_NECK','C2_SHOULDER','C2_ELBOW','C2_WRIST','C2_HAND']; predicates.append(either([duration(c,120) for c in used]))
        elif n==3: used=['C3_UNION']; predicates.append(duration(used[0],120))
        elif n==4:
            used=['C4_NECK_FLEX','C4_TRUNK_FLEX','C4_TRUNK_EXT','C4_NECK_TWIST','C4_TRUNK_TWIST','C4_UNION']
            predicates += [either([truth('criteria.4.unsupported',criterion['unsupported']),truth('criteria.4.posture_restricted',criterion['posture_restricted'])]),grouped(used[:-1],used[-1],120)]
        elif n==5: used=['C5_SQUAT','C5_KNEEL','C5_UNION']; predicates.append(grouped(used[:-1],used[-1],120))
        elif n in [6,7]:
            fields=['pinch_mass_kg','pinch_force_kg_equiv'] if n==6 else ['single_hand_mass_kg','grip_force_kg_equiv']; thresholds=[1,2] if n==6 else [4.5,4.5]
            used=[f'C{n}_QUALIFYING']; predicates += [truth(f'criteria.{n}.unsupported',criterion['unsupported']),either([field(f,t,'KG' if j==0 else 'KG_EQUIV') for j,(f,t) in enumerate(zip(fields,thresholds))]),duration(used[0],120)]
        elif n==8: predicates += [compare('conditions.box_mass_kg',conditions.get('box_mass_kg'),25,'KG'),compare('legal.lift_count_day',legal.get('lift_count_day'),10,'COUNT_DAY')]
        elif n==9:
            predicates += [compare('conditions.box_mass_kg',conditions.get('box_mass_kg'),10,'KG'),grouped(['below_knee_count_day','above_shoulder_count_day','extended_arm_count_day'],'union_count_day',25,True)]
        elif n==10: used=['C10_LIFT']; predicates += [compare('conditions.box_mass_kg',conditions.get('box_mass_kg'),4.5,'KG'),field('lift_rate_min',2,'COUNT_MIN'),duration(used[0],120)]
        else: used=['C11_IMPACT']; predicates += [field('impact_rate_hour',10,'COUNT_HOUR'),duration(used[0],120)]
        if criterion['condition_present']=='NO':
            if any((exposures[c]['minutes'] or 0)>0 for c in used): conflicts.append('condition_present / exposure')
            local_numeric=['pinch_mass_kg','pinch_force_kg_equiv'] if n==6 else ['single_hand_mass_kg','grip_force_kg_equiv'] if n==7 else ['below_knee_count_day','above_shoulder_count_day','extended_arm_count_day','union_count_day'] if n==9 else ['lift_rate_min'] if n==10 else ['impact_rate_hour'] if n==11 else []
            if any((criterion.get(f) or 0)>0 for f in local_numeric): conflicts.append('condition_present / observation')
        for f in ['planned_duration_months','annual_work_days']:
            if conditions.get(f) is not None and conditions[f]<0: conflicts.append('conditions.'+f)
        if conditions.get('box_mass_kg')==0 and n in [8,9,10]: conflicts.append('conditions.box_mass_kg')
        if n in [3,4,5,9] and criterion.get('posture_interpretation_pending'): reasons.append('POSTURE_INTERPRETATION')
        if exclusion: status='NOT_APPLICABLE'; reasons=[]
        elif conflicts: status='NEEDS_REVIEW'; reasons=['INPUT_CONFLICT']
        elif any(v is False for v,m in predicates): status='NOT_APPLICABLE'; reasons=[]
        else:
            missing=[p for v,m in predicates if v is None for p in m]
            if ex['short_term']=='UNKNOWN':
                if conditions.get('one_off')=='UNKNOWN': missing.append('conditions.one_off')
                if conditions.get('planned_duration_months') is None: missing.append('conditions.planned_duration_months')
            if ex['intermittent']=='UNKNOWN': missing.append('conditions.annual_work_days')
            status='NEEDS_INPUT' if missing else 'NEEDS_REVIEW' if reasons else 'APPLICABLE'
        inv=dict(criterion_no=n,status=None,reason=None,evidence=evidence(),reviewer=None,reviewed_at=None)
        output.append(dict(criterion_no=n,computed_status=status,exclusion=exclusion,basis=basis,missing_fields=sorted(set(missing)),review_reasons=list(dict.fromkeys(reasons)),source='MOEL_2020_12_V1',investigator=inv,effective_status=status))
    return dict(judgments=output)
