"""Three-valued burden-rule engine; v1.3 remains readable for historical snapshots."""
import math
from .task_defaults import exclusions, evidence

def calculate_legacy(conditions, legal):
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


def _truth(value):
    return True if value == 'YES' else False if value == 'NO' else None


def _number(value, integer=False):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value < 0:
        return False
    try:
        if not math.isfinite(value): return False
    except OverflowError:
        return False
    return not integer or int(value) == value


def calculate_v2(conditions, legal):
    """Evaluate the 2.0 direct-input rules with three-valued facts and auditable row unions."""
    conditions = conditions if isinstance(conditions, dict) else {}
    legal = legal if isinstance(legal, dict) else {}
    exclusion = exclusions(conditions)
    raw_exposures = legal.get('exposures') if isinstance(legal.get('exposures'), list) else []
    raw_criteria = legal.get('criteria') if isinstance(legal.get('criteria'), list) else []
    exposures = {x.get('condition_code'): x for x in raw_exposures if isinstance(x, dict)}
    criteria = {x.get('criterion_no'): x for x in raw_criteria if isinstance(x, dict)}
    output = []

    def either(values):
        return True if any(v is True for v in values) else False if values and all(v is False for v in values) else None

    def both(values):
        return False if any(v is False for v in values) else True if values and all(v is True for v in values) else None

    for n in range(1, 12):
        criterion = criteria.get(n) or {'criterion_no': n, 'condition_present': 'UNKNOWN'}
        basis, missing, conflicts, reasons = [], set(), [], []
        unknown = set()

        def add(path, value, unit, threshold=None, operator='GE'):
            basis.append(dict(item_code=path, value=value, unit=unit, operator=operator, threshold=threshold, source='DIRECT_INPUT'))
            if value is None:
                unknown.add(path)

        def truth(path, value):
            add(path, value, 'BOOLEAN', None, 'EQ')
            state = _truth(value)
            if state is None and value not in (None, 'UNKNOWN'):
                conflicts.append(path)
            return state

        def measure(path, value, threshold, unit, integer=False, maximum=None):
            add(path, value, unit, threshold)
            if value is None:
                return None
            if not _number(value, integer) or maximum is not None and value > maximum:
                conflicts.append(path)
                return None
            return value >= threshold

        def duration(code, threshold):
            path = f'exposures.{code}.minutes'
            item = exposures.get(code)
            if item is None:
                conflicts.append(path)
                unknown.add(path)
                return None
            value = item.get('minutes')
            state = measure(path, value, threshold, 'MIN_DAY', maximum=1440)
            total = conditions.get('daily_work_min')
            if total is not None:
                if not _number(total) or total > 1440:
                    conflicts.append('conditions.daily_work_min')
                elif value is not None and _number(value) and value > total:
                    conflicts.append(path)
            if state is True and total is None:
                missing.add('conditions.daily_work_min')
                return None
            return state

        present = truth(f'criteria.{n}.condition_present', criterion.get('condition_present'))
        predicates = [present]
        if present is None:
            missing.add(f'criteria.{n}.condition_present')
        for field, integer, maximum in [('daily_work_min', False, 1440), ('planned_duration_months', False, None), ('annual_work_days', True, None)]:
            value = conditions.get(field)
            if value is not None and (not _number(value, integer) or maximum is not None and value > maximum):
                conflicts.append('conditions.' + field)
        if conditions.get('one_off') not in ('YES', 'NO', 'UNKNOWN', None):
            conflicts.append('conditions.one_off')

        if n == 1:
            state=duration('C1_KEYBOARD_FOCUSED', 240)
            predicates.append(state)
            if state is None: missing.update(path for path in unknown if path.startswith('exposures.C1_'))
        elif n == 2:
            states=[duration('C2_' + part, 120) for part in ['NECK', 'SHOULDER', 'ELBOW', 'WRIST', 'HAND']]
            state=either(states); predicates.append(state)
            if state is None: missing.update(path for path in unknown if path.startswith('exposures.C2_'))
        elif n == 3:
            state=duration('C3_UNION', 120); predicates.append(state)
            if state is None: missing.update(path for path in unknown if path.startswith('exposures.C3_'))
        elif n in (4, 5):
            if n == 4:
                support = either([truth('criteria.4.unsupported', criterion.get('unsupported')), truth('criteria.4.posture_restricted', criterion.get('posture_restricted'))])
                if support is None: missing.update(path for path in unknown if path in ('criteria.4.unsupported','criteria.4.posture_restricted'))
                codes, union_code = ['C4_NECK_FLEX', 'C4_TRUNK_FLEX', 'C4_NECK_TWIST', 'C4_TRUNK_TWIST'], 'C4_UNION'
            else:
                support, codes, union_code = True, ['C5_SQUAT', 'C5_KNEEL'], 'C5_UNION'
            component = [duration(code, 120) for code in codes]
            union = duration(union_code, 120)
            component_values = [(exposures.get(code) or {}).get('minutes') for code in codes]
            union_value = (exposures.get(union_code) or {}).get('minutes')
            known_component_values = [value for value in component_values if _number(value)]
            if union_value is not None and _number(union_value) and known_component_values:
                if union_value < max(known_component_values) or len(known_component_values)==len(component_values) and union_value>sum(known_component_values):
                    conflicts.append(f'exposures.{union_code}.minutes')
            if any(v is True for v in component):
                time_state = True
            elif union is True and all(v is False for v in component):
                time_state = True
                reasons.append('COMBINATION_RULE')
            elif union is False and all(v is False for v in component):
                time_state = False
            else:
                time_state = None
                if union is True and any(v is None for v in component):
                    missing.update(path for path in unknown if path.startswith(f'exposures.C{n}_'))
            predicates += [support, time_state]
            if time_state is None: missing.update(path for path in unknown if path.startswith(f'exposures.C{n}_'))
        elif 6 <= n <= 11:
            rows = criterion.get('rows') if isinstance(criterion.get('rows'), list) else []
            completeness = truth(f'criteria.{n}.rows_complete', criterion.get('rows_complete'))
            row_states, row_values, row_details, row_unknowns = {}, {}, {}, {}
            seen = set()
            unit, threshold, integer = ({6:('MIN_DAY',120,False),7:('MIN_DAY',120,False),8:('COUNT_DAY',10,True),9:('COUNT_DAY',25,True),10:('MIN_DAY',120,False),11:('MIN_DAY',120,False)})[n]

            def row_measure(row, rid, key, unit, threshold, integer=False, maximum=None):
                path = f'criteria.{n}.rows.{rid}.{key}'
                return measure(path, row.get(key), threshold, unit, integer, maximum)

            for row in rows:
                if not isinstance(row, dict):
                    conflicts.append(f'criteria.{n}.rows')
                    continue
                rid = row.get('row_id')
                if not isinstance(rid, str) or not rid or rid in seen:
                    conflicts.append(f'criteria.{n}.rows.row_id')
                    continue
                seen.add(rid)
                unknown_before=set(unknown)
                prefix = f'criteria.{n}.rows.{rid}.'
                if n in (6, 7):
                    support = truth(prefix + 'unsupported', row.get('unsupported'))
                    if n == 6:
                        metrics = [row_measure(row, rid, 'pinch_mass_kg', 'KG', 1), row_measure(row, rid, 'pinch_force_kg_equiv', 'KG_EQUIV', 2)]
                    else:
                        metrics = [row_measure(row, rid, 'single_hand_mass_kg', 'KG', 4.5), row_measure(row, rid, 'grip_force_kg_equiv', 'KG_EQUIV', 4.5)]
                    eligible = False if support is False else both([support, either(metrics)])
                    value_key, unit, threshold, integer = 'minutes', 'MIN_DAY', 120, False
                elif n == 8:
                    eligible = row_measure(row, rid, 'load_mass_kg', 'KG', 25)
                    value_key, unit, threshold, integer = 'lift_count_day', 'COUNT_DAY', 10, True
                elif n == 9:
                    eligible = row_measure(row, rid, 'load_mass_kg', 'KG', 10)
                    value_key, unit, threshold, integer = None, 'COUNT_DAY', 25, True
                elif n == 10:
                    mass = row_measure(row, rid, 'load_mass_kg', 'KG', 4.5)
                    rate = row_measure(row, rid, 'lift_rate_min', 'COUNT_MIN', 2)
                    eligible = both([mass, rate])
                    value_key, unit, threshold, integer = 'minutes', 'MIN_DAY', 120, False
                else:
                    impact = truth(prefix + 'impact_verified', row.get('impact_verified'))
                    rate = row_measure(row, rid, 'impact_rate_hour', 'COUNT_HOUR', 10)
                    eligible = both([impact, rate])
                    value_key, unit, threshold, integer = 'minutes', 'MIN_DAY', 120, False

                if value_key:
                    value = row.get(value_key)
                    amount = row_measure(row, rid, value_key, unit, threshold, integer, None if n == 8 else 1440)
                    total = conditions.get('daily_work_min')
                    if n != 8 and total is not None and _number(total) and total <= 1440 and _number(value) and value > total:
                        conflicts.append(prefix + value_key)
                    row_values[rid] = (value, amount, value_key)
                else:
                    row_values[rid] = (None, None, None)
                row_states[rid] = eligible
                row_details[rid] = row
                row_unknowns[rid] = unknown-set(unknown_before)

            eligible_ids = {rid for rid, state in row_states.items() if state is True}
            unknown_ids = {rid for rid, state in row_states.items() if state is None}

            if n == 9:
                totals = criterion.get('totals') if isinstance(criterion.get('totals'), dict) else {}
                location_keys = ['below_knee_count_day', 'above_shoulder_count_day', 'extended_arm_count_day']
                row_location_states = {}
                row_union_states = {}
                for rid in eligible_ids | unknown_ids:
                    row = row_details[rid]
                    unknown_before=set(unknown)
                    row_location_states[rid] = {key: row_measure(row, rid, key, 'COUNT_DAY', 25, True) for key in location_keys}
                    row_union = row_measure(row, rid, 'union_count_day', 'COUNT_DAY', 25, True)
                    row_union_states[rid] = row_union
                    row_unknowns.setdefault(rid,set()).update(unknown-set(unknown_before))
                    raw = [row.get(key) for key in location_keys]
                    if all(_number(x, True) for x in raw):
                        if row.get('union_count_day') is not None and (row.get('union_count_day') < max(raw) or row.get('union_count_day') > sum(raw)):
                            conflicts.append(f'criteria.9.rows.{rid}.union_count_day')
                selected_raw = totals.get('row_ids') if isinstance(totals.get('row_ids'), list) else []
                selected = [rid for rid in selected_raw if isinstance(rid, str)]
                selected_path = 'criteria.9.totals.row_ids'
                if len(selected) != len(selected_raw) or len(selected) != len(set(selected)):
                    conflicts.append(selected_path)
                selected_eligible = []
                for rid in selected:
                    if rid not in row_states or row_states[rid] is False:
                        conflicts.append(selected_path)
                    elif row_states[rid] is None:
                        missing.update(row_unknowns.get(rid,set()))
                    else:
                        selected_eligible.append(rid)
                totals_states = {key: measure(f'criteria.9.totals.{key}', totals.get(key), 25, 'COUNT_DAY', True) for key in location_keys + ['union_count_day']}
                vals_by_key = {key: [row_details[rid].get(key) for rid in selected_eligible] for key in location_keys + ['union_count_day']}
                for key, vals in vals_by_key.items():
                    total_value = totals.get(key)
                    known = [v for v in vals if _number(v, True)]
                    if total_value is not None and known and (total_value < max(known) or len(known) == len(vals) and total_value > sum(known)):
                        conflicts.append(f'criteria.9.totals.{key}')
                total_positions = [totals.get(key) for key in location_keys]
                if all(_number(x, True) for x in total_positions) and totals.get('union_count_day') is not None:
                    if totals['union_count_day'] < max(total_positions) or totals['union_count_day'] > sum(total_positions):
                        conflicts.append('criteria.9.totals.union_count_day')

                row_location_positive = any(state is True for states in row_location_states.values() for state in states.values())
                row_union_combination = any(row_union_states.get(rid) is True and all(state is False for state in row_location_states.get(rid, {}).values()) for rid in eligible_ids)
                totals_supported = bool(selected_eligible) and eligible_ids.issubset(set(selected)) and not any(rid in unknown_ids for rid in selected)
                totals_location_positive = any(totals_states[key] is True for key in location_keys)
                totals_combination = totals_states['union_count_day'] is True and all(totals.get(key) is not None and totals.get(key) < 25 for key in location_keys)
                if row_location_positive:
                    metric_state = True
                elif row_union_combination:
                    metric_state = True
                    reasons.append('COMBINATION_RULE')
                elif (totals_location_positive or totals_combination) and not totals_supported:
                    metric_state = None
                    missing.add(selected_path)
                    if totals_combination:
                        missing.update(f'criteria.9.totals.{key}' for key in location_keys if totals.get(key) is None)
                elif totals_location_positive:
                    metric_state = True
                elif totals_combination:
                    metric_state = True
                    reasons.append('COMBINATION_RULE')
                elif not eligible_ids and not unknown_ids and completeness is True:
                    metric_state = False
                elif len(eligible_ids) == 1 and not unknown_ids and completeness is True:
                    rid = next(iter(eligible_ids)); row = row_details[rid]
                    vals = [row.get(key) for key in location_keys]; union_value = row.get('union_count_day')
                    if all(_number(x, True) for x in vals) and _number(union_value, True):
                        if any(x >= 25 for x in vals): metric_state = True
                        elif union_value >= 25:
                            metric_state = True; reasons.append('COMBINATION_RULE')
                        else: metric_state = False
                    else: metric_state = None; missing.update(row_unknowns.get(rid,set()))
                elif completeness is True and not unknown_ids and eligible_ids and eligible_ids.issubset(set(selected)) and all(state is False for state in totals_states.values()):
                    metric_state = False
                else:
                    metric_state = None
                    if completeness is not True: missing.add(f'criteria.{n}.rows_complete')
                    if eligible_ids - set(selected): missing.add(selected_path)
                    if unknown_ids: missing.update(unknown)
                    for key, state in totals_states.items():
                        if state is None: missing.add(f'criteria.9.totals.{key}')
                predicates.append(metric_state)
            else:
                union = criterion.get('union') if isinstance(criterion.get('union'), dict) else {}
                selected_raw = union.get('row_ids') if isinstance(union.get('row_ids'), list) else []
                selected = [rid for rid in selected_raw if isinstance(rid, str)]
                union_path = f'criteria.{n}.union.row_ids'
                if len(selected) != len(selected_raw) or len(selected) != len(set(selected)):
                    conflicts.append(union_path)
                selected_eligible = []
                for rid in selected:
                    if rid not in row_states or row_states[rid] is False:
                        conflicts.append(union_path)
                    elif row_states[rid] is None:
                        missing.update(row_unknowns.get(rid,set()))
                    else:
                        selected_eligible.append(rid)
                union_value = union.get('value')
                union_state = measure(f'criteria.{n}.union.value', union_value, threshold, unit, integer, None if n == 8 else 1440)
                selected_values = [row_values[rid][0] for rid in selected_eligible if row_values.get(rid, (None, None, None))[0] is not None]
                if union_value is not None and selected_values:
                    if union_value < max(selected_values) or len(selected_values) == len(selected_eligible) and union_value > sum(selected_values):
                        conflicts.append(f'criteria.{n}.union.value')
                individual_cross = any(row_states.get(rid) is True and row_values.get(rid, (None, None, None))[1] is True for rid in row_states)
                if individual_cross:
                    metric_state = True
                elif not eligible_ids and not unknown_ids and completeness is True:
                    metric_state = False
                elif union_state is True and selected_eligible and not any(rid in unknown_ids for rid in selected):
                    metric_state = True
                elif len(eligible_ids) == 1 and not unknown_ids and completeness is True:
                    rid = next(iter(eligible_ids)); value, value_state, value_key = row_values[rid]
                    if union_value is not None and value is not None and union_value != value:
                        conflicts.append(f'criteria.{n}.union.value')
                    metric_state = value_state
                    if metric_state is None: missing.add(f'criteria.{n}.rows.{rid}.{value_key}')
                elif union_state is False and completeness is True and not unknown_ids and eligible_ids.issubset(set(selected)):
                    metric_state = False
                else:
                    metric_state = None
                    if completeness is not True: missing.add(f'criteria.{n}.rows_complete')
                    for rid in unknown_ids: missing.update(row_unknowns.get(rid,set()))
                    if eligible_ids - set(selected): missing.add(union_path)
                    if union_value is None: missing.add(f'criteria.{n}.union.value')
                predicates.append(metric_state)

        # A confirmed absence conflicts with evidence showing this work condition actually occurs.
        if present is False:
            positive = False
            if n <= 5:
                codes = {1:['C1_KEYBOARD_FOCUSED'], 2:['C2_NECK','C2_SHOULDER','C2_ELBOW','C2_WRIST','C2_HAND'], 3:['C3_UNION'], 4:['C4_NECK_FLEX','C4_TRUNK_FLEX','C4_NECK_TWIST','C4_TRUNK_TWIST','C4_UNION'], 5:['C5_SQUAT','C5_KNEEL','C5_UNION']}[n]
                positive = any(_number((exposures.get(code) or {}).get('minutes')) and (exposures.get(code) or {}).get('minutes') > 0 for code in codes)
            elif n in range(6, 12):
                positive = any(row_states.get(rid) is True and _number(row_values.get(rid, (None, None, None))[0]) and row_values.get(rid, (None, None, None))[0] > 0 for rid in row_states)
                if n == 9:
                    positive = positive or any(row_states.get(rid) is True and any(_number(row_details[rid].get(key), True) and row_details[rid].get(key)>0 for key in ['below_knee_count_day','above_shoulder_count_day','extended_arm_count_day','union_count_day']) for rid in row_states)
            if positive:
                conflicts.append(f'criteria.{n}.condition_present / measurements')
        if n in (3, 4, 5, 9) and criterion.get('posture_interpretation_pending') is True:
            reasons.append('POSTURE_INTERPRETATION')

        ex_yes = exclusion['short_term'] == 'YES' or exclusion['intermittent'] == 'YES'
        if ex_yes:
            status, reasons = 'NOT_APPLICABLE', []
        elif conflicts:
            status, reasons = 'NEEDS_REVIEW', ['INPUT_CONFLICT']
        elif any(value is False for value in predicates):
            status, reasons = 'NOT_APPLICABLE', []
        else:
            if exclusion['short_term'] == 'UNKNOWN':
                missing.update(['conditions.one_off', 'conditions.planned_duration_months'])
            if exclusion['intermittent'] == 'UNKNOWN':
                missing.add('conditions.annual_work_days')
            status = 'NEEDS_INPUT' if any(value is None for value in predicates) or missing else 'NEEDS_REVIEW' if reasons else 'APPLICABLE'
        inv = dict(criterion_no=n, status=None, reason=None, evidence=evidence(), reviewer=None, reviewed_at=None)
        output.append(dict(criterion_no=n, computed_status=status,
                           exclusion='BOTH' if exclusion['short_term']=='YES' and exclusion['intermittent']=='YES' else 'SHORT_TERM' if exclusion['short_term']=='YES' else 'INTERMITTENT' if exclusion['intermittent']=='YES' else None,
                           basis=basis, missing_fields=sorted(missing), review_reasons=list(dict.fromkeys(reasons)),
                           source='MOEL_2020_12_GENERAL_V2', investigator=inv, effective_status=status))
    return dict(judgments=output)


def calculate(conditions, legal, schema_version='1.3'):
    return calculate_v2(conditions, legal) if schema_version == '2.0' else calculate_legacy(conditions, legal)
