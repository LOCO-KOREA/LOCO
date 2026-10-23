"""Find unanswered inputs using the real calculators; let AI select and phrase them."""
from .contract import fields, key, POLICY, LIFT_FIELDS, PHOTO_VIEWS
from .photo_load import photo_load
from . import photo_facts
from ergo.engine.burden_rules import calculate_v2
from ergo.engine.reba_scoring import calculate_reba
from ergo.pose_contract import WRIST_REASONS


def paths(field, condition):
    d=field['destination']; kind=d['type']
    if field.get('path'): return [field['path']]
    if kind=='work_type': return [f'criteria.{n}.condition_present' for n in d['criteria']]
    if kind=='complete': return [f'criteria.{n}.rows_complete' for n in d['criteria']]
    if kind=='criterion':
        m=d['mapping']
        if 'exposure' in m: return [f"exposures.{m['exposure']}.minutes"]
        if 'criterion' in m: return [f"criteria.{n}.{m['criterion']}" for n in d['criteria']]
        name=m.get('lift') or m.get('row')
        return [f'criteria.{n}.rows.{condition}.{name}' for n in d['criteria'] if 'lift' not in m or name in LIFT_FIELDS[n]]
    return []


def assess(task, facts, views):
    return _assess(task, facts, views, fields())


def work_feature_needed(field, judgments):
    scope=field['destination'].get('criteria')
    return any(row['computed_status'] in ('NEEDS_INPUT','NEEDS_REVIEW') and
               (not scope or row['criterion_no'] in scope) for row in judgments)


def _assess(task, facts, views, catalogue, only_identity=None):
    judgments=calculate_v2(task['conditions'],task['legal'])['judgments']
    reba=calculate_reba(task, None) if views else None
    missing=set(p for j in judgments if j['computed_status'] in ('NEEDS_INPUT','NEEDS_REVIEW') for p in j['missing_fields'])
    if reba: missing.update(p for row in reba['slots'] for p in row['missing_fields'])
    load_state, load_kg = photo_load(facts)
    known=lambda t: load_state if t == 'load' else load_kg if t == 'load_kg' else (facts.get(key(t)) or {}).get('value')
    has=lambda t: key(t) in facts
    unknown_work=[f for f in catalogue if f['destination']['type']=='work_type' and not has(f['target'])]
    masses={f['value'] for f in facts.values() if f['target']=='card.lift.load_mass_kg' and f['state']=='KNOWN'}
    candidates=[]
    for field in catalogue:
        t=field['target']; d=field['destination']; kind=d['type']
        if only_identity is not None and not (only_identity.startswith(t + '@') or t == 'other_work'): continue
        if kind=='task': continue  # A report title can be edited later; it is not a calculation gap.
        if kind in ('work_type','other_work') and not work_feature_needed(field,judgments): continue
        if kind in ('context','view','manual','load','load_kg','load_link') and not views: continue
        if kind=='view' and d['view'] not in views: continue
        if kind=='manual' and known('context')!='YES': continue
        if kind=='manual' and d['field']=='coupling' and (known('load')=='UNLOADED' or known('load_kg')==0): continue
        if t=='load_link' and (len(masses)!=1 or has('load') or has('load_kg')): continue
        if t=='load' and load_state!='UNKNOWN': continue
        if t=='load_kg' and load_kg is not None: continue
        if t=='load' and len(masses)==1 and not has('load_link'): continue
        if t=='load_kg' and known('load')!='MEASURED': continue
        if t=='other_work' and (not unknown_work or not any(known('work_type.'+f['target'].split('.')[-1])=='YES' for f in catalogue if f['destination']['type']=='work_type')): continue
        if kind=='work_type' and not has('other_work') and any(f['target']=='other_work' for f in candidates): continue
        if field['gate'] and known('work_type.'+field['gate'])!='YES': continue
        conditions=sorted({f['condition'] for f in facts.values() if f['target'].startswith('card.'+str(field['gate'])+'.')}) or [POLICY['default_condition']]
        if kind!='criterion' or not (d.get('mapping',{}).get('row') or d.get('mapping',{}).get('lift')): conditions=[POLICY['default_condition']]
        if kind=='manual':conditions=[photo_facts.condition(slot['photo_id']) for slot in task['capture']['slots'] if slot.get('analysis_target',True) and slot.get('photo_id') in views.values()]
        if kind=='manual' and only_identity==key(t):conditions=[POLICY['default_condition']]
        for condition in conditions:
            if only_identity is not None and key(t,condition) != only_identity and t != 'other_work': continue
            owner=photo_facts.photo_id(dict(condition=condition),views) if kind=='manual' else None
            item=photo_facts.fact_for(facts,t,owner,views) if kind=='manual' else facts.get(key(t,condition))
            if item and (item['state']=='KNOWN' or item['state']=='UNKNOWN' and item['source']=='USER'): continue
            relevant=bool(set(paths(field,condition)) & missing)
            if kind=='manual':relevant=any(row['photo_id']==owner and bool(set(paths(field,condition)) & set(row['missing_fields'])) for row in (reba or {}).get('slots',[]))
            if kind=='criterion' and not relevant and not (item and item['state']=='CONFLICT'):
                # No row exists yet: ask the first row's facts only when that criterion still needs input.
                relevant=any(j['criterion_no'] in d['criteria'] and j['computed_status']=='NEEDS_INPUT' for j in judgments) and not any(task['legal']['criteria'][n-1].get('rows') for n in d['criteria'])
                if not relevant: continue
            if kind in ('manual','complete') and not relevant and not (item and item['state']=='CONFLICT'): continue
            if kind=='conditions' and not relevant: continue
            if t=='planned_duration_months' and known('one_off')!='YES': continue
            question=field['question']
            if t=='other_work': question+=' '+ ' · '.join(f['label'] for f in unknown_work)
            if t=='load_link': question=f"사진 속 물건도 설명한 {next(iter(masses))}kg 물건인가요?"
            if kind=='manual':question=photo_facts.label(owner,views)+' · '+question
            reason='결과 계산에 필요한 정보가 아직 없어요.'
            measurement_reason=bool(item and item['source'] in ('POSE','MOVENET') and item.get('measurement_diagnostic') in WRIST_REASONS)
            if measurement_reason: reason=WRIST_REASONS[item['measurement_diagnostic']]
            elif item and item.get('measurement_reason'):reason=item['measurement_reason'];measurement_reason=True
            if item and item['state']=='CONFLICT': reason='앞서 기록한 값과 새 설명이 달라 확인이 필요해요.'
            candidates.append(dict(field,target=t,condition=condition,text=question,reason=reason,
                **(dict(photo_id=owner,photo_label=photo_facts.label(owner,views),label=photo_facts.label(owner,views)+' · '+field['label'],display_condition=photo_facts.label(owner,views),legacy_primary=owner==next((views[view] for view in PHOTO_VIEWS if view in views),None)) if kind=='manual' else {}),
                identity=key(t,condition),priority=0 if item and item['state']=='CONFLICT' else field['priority'],photo_measurement_reason=measurement_reason))
    if any(c['target']=='other_work' for c in candidates) and not has('other_work'):
        candidates=[c for c in candidates if c['destination']['type']!='work_type']
    candidates.sort(key=lambda c:(c['priority'],c['target'],c['condition']))
    return dict(judgments=judgments,reba=reba,candidates=candidates,
                missing_count=len(candidates),complete=not any(j['computed_status'] in ('NEEDS_INPUT','NEEDS_REVIEW') for j in judgments) and (not reba or reba['status']=='COMPLETE'))


def _without_value(task, field, condition, views):
    """Clear just this field's calculator input without replaying the saved facts."""
    d = field['destination']; kind = d['type']
    value = dict(task)
    if kind == 'conditions':
        value['conditions'] = dict(task['conditions'], **{d['field']: None})
    elif kind in ('work_type', 'complete', 'criterion'):
        value['legal'] = dict(task['legal'])
        mapping = d.get('mapping', {})
        if 'exposure' in mapping:
            value['legal']['exposures'] = [dict(row, minutes=None) if row['condition_code'] == mapping['exposure'] else row for row in task['legal']['exposures']]
        else:
            criteria = value['legal']['criteria'] = list(task['legal']['criteria'])
            for n in d['criteria']:
                criterion = criteria[n - 1] = dict(criteria[n - 1])
                if kind == 'work_type': criterion['condition_present'] = 'UNKNOWN'
                elif kind == 'complete': criterion['rows_complete'] = 'UNKNOWN'
                elif 'criterion' in mapping: criterion[mapping['criterion']] = 'UNKNOWN'
                else:
                    name = mapping.get('lift') or mapping.get('row')
                    if 'lift' in mapping and name not in LIFT_FIELDS[n]: continue
                    criterion['rows'] = [dict(row, **{name: None}) if row['row_id'] == condition else row for row in criterion.get('rows', [])]
    elif kind == 'manual':
        owner=photo_facts.photo_id(dict(condition=condition),views)
        primary = next((slot for slot in task['capture']['slots'] if slot['photo_id'] == owner), None)
        value['manual'] = [row for row in task['manual'] if not (primary and row['slot_no'] == primary['slot_no'] and row['photo_id'] == primary['photo_id'] and row['scope'] == d['scope'] and row['field'] == d['field'])]
    return value


def progress(task, facts, views, candidates):
    """Count resolved inputs only while they belong to the current question scope.

    Clearing one answer and planning again makes the calculators decide relevance:
    saved values for an inactive work type, removed photo or satisfied alternative
    cannot inflate progress. This is a dynamic field count, not a promise of a
    fixed number of turns, and USER unknown means handled rather than calculated.
    The probe uses copies; actual inputs and snapshots stay untouched.
    """
    catalogue = fields(); by_target = {field['target']: field for field in catalogue}
    completed = 0
    for identity, item in facts.items():
        if item.get('alias_of'):continue
        field = by_target.get(item['target'])
        if not field or field['destination']['type'] == 'task': continue
        if item['state'] != 'KNOWN' and not (item['state'] == 'UNKNOWN' and item['source'] == 'USER'): continue
        # A confirmed work feature remains part of the scope even when the other
        # unknown work features are currently folded into one other_work question.
        if field['destination']['type'] == 'work_type':
            completed += 1
            continue
        # Removing only the fact leaves its saved conditions/manual/row value.
        # Clear both the fact and the actual calculator input for this probe.
        probe = dict(facts); del probe[identity]
        if item['target'].startswith('manual.') and (probe.get(key(item['target'])) or {}).get('alias_of')==identity:probe.pop(key(item['target']),None)
        without_value = _without_value(task, field, item['condition'], views)
        if any(candidate['identity'] == identity for candidate in _assess(without_value, probe, views, catalogue, only_identity=identity)['candidates']):
            completed += 1
    remaining = len(candidates)
    total = completed + remaining
    return dict(completed_count=completed, total_count=total, remaining_count=remaining,
                percent=completed * 100 // total if total else 100, dynamic=True)


def with_paired_question(question, candidates):
    """Present two unresolved sides together without changing field ownership/counts."""
    result = {name: value for name, value in question.items() if name != 'paired_question'}
    if not any(candidate['identity'] == question['identity'] for candidate in candidates): return result
    destination = question['destination']; kind = destination['type']
    side_key = 'scope' if kind == 'manual' else 'view' if kind == 'view' else None
    side = destination.get(side_key) if side_key else None
    if side not in ('LEFT', 'RIGHT'): return result
    other_side = 'RIGHT' if side == 'LEFT' else 'LEFT'
    for candidate in candidates:
        other = candidate['destination']
        if candidate['condition'] != question['condition'] or other['type'] != kind: continue
        if other.get(side_key) != other_side: continue
        if kind == 'manual' and other['field'] != destination['field']: continue
        result['paired_question'] = {name: value for name, value in candidate.items() if name != 'paired_question'}
        break
    return result


def with_answer_questions(question, candidates, saved_facts):
    """Group only pending related inputs; every member keeps its own answer target."""
    metadata = {'answer_questions', 'group_title'}
    result = {name: value for name, value in question.items() if name not in metadata}
    if not any(candidate['identity'] == question['identity'] for candidate in candidates): return result
    destination = question['destination']; kind = destination['type']
    condition = question['condition']
    virtual_work = kind == 'other_work'

    def unresolved(candidate):
        item = saved_facts.get(candidate['identity'])
        return not item or not (item['state'] == 'KNOWN' or item['state'] == 'UNKNOWN' and item['source'] == 'USER')

    if kind == 'work_type' or virtual_work:
        title = '작업 특징을 함께 확인해 주세요'
        if virtual_work:
            members = []
            for field in fields():
                if field['destination']['type'] != 'work_type': continue
                member = dict(field, condition=condition, identity=key(field['target'], condition), text=field['question'],
                    reason='이 작업 특징이 있는지 확인해 주세요.')
                if not unresolved(member): continue
                item = saved_facts.get(member['identity'])
                if item and item['state'] == 'CONFLICT':
                    member.update(priority=0, reason='앞서 기록한 값과 새 설명이 달라 확인이 필요해요.')
                members.append(member)
        else:
            members = [candidate for candidate in candidates if candidate['destination']['type'] == 'work_type']
    elif kind == 'manual':
        common_groups = (
            ('몸통·목 자세를 함께 확인해 주세요', {'trunk_base', 'neck_base', 'trunk_twisted', 'trunk_side_bent', 'neck_twisted', 'neck_side_bent'}),
            ('다리 자세를 함께 확인해 주세요', {'legs_support', 'seated', 'knee_band'}),
            ('작업 중 움직임과 힘을 함께 확인해 주세요', {'shock_force', 'static_over_1min', 'small_repeat_over_4min', 'rapid_change_or_unstable'}),
        )
        arm_flags = {'arm_abducted_or_rotated', 'shoulder_raised', 'arm_supported_or_gravity_assisted', 'wrist_deviated_or_twisted'}
        scope = destination['scope']; name = destination['field']
        names = None
        if scope == 'COMMON':
            for title, group in common_groups:
                if name in group:
                    names = group
                    break
        elif scope in ('LEFT', 'RIGHT') and name in arm_flags:
            title = '양팔·손목의 추가 자세를 함께 확인해 주세요'
            names = arm_flags
        if names is None: return result
        members = [candidate for candidate in candidates if candidate['destination']['type'] == 'manual'
            and candidate['destination']['field'] in names
            and (candidate['destination']['scope'] == 'COMMON' if scope == 'COMMON' else candidate['destination']['scope'] in ('LEFT', 'RIGHT'))]
    else:
        return result
    members = [candidate for candidate in members if candidate['condition'] == condition and unresolved(candidate)]
    if not virtual_work:
        members = [question] + [candidate for candidate in members if candidate['identity'] != question['identity']]
        if not unresolved(question): return result
    if len(members) < (1 if virtual_work else 2): return result
    # Members never recursively carry a pair/group; the root may keep its pair for older renderers.
    nested = metadata | {'paired_question'}
    result['answer_questions'] = [{name: value for name, value in candidate.items() if name not in nested} for candidate in members]
    result['group_title'] = title
    return result


def choose(candidates, proposed=()):
    by_id={c['identity']:c for c in candidates}; chosen=[]; seen=set()
    by_id.update({key(c['target']):c for c in candidates if c.get('legacy_primary')})
    for candidate in candidates:
        if candidate['priority']==0:
            chosen.append(candidate); seen.add(candidate['identity'])
    for p in proposed if isinstance(proposed,list) else []:
        if not isinstance(p,dict): continue
        identity=key(p.get('target',''),p.get('condition'))
        if identity not in by_id: continue
        original=by_id[identity]
        identity=original['identity']
        if identity in seen:continue
        # A question may change wording, never the field, choices, units or ownership.
        text=p.get('text'); reason=p.get('reason')
        display_text=text[:300] if isinstance(text,str) and text.strip() and photo_facts.PHOTO_POLICY['condition_prefix'] not in text else original['text']
        if original.get('photo_label') and not display_text.startswith(original['photo_label']):display_text=original['photo_label']+' · '+display_text
        chosen.append(dict(original,text=display_text,
                           reason=reason[:300] if not original.get('photo_measurement_reason') and isinstance(reason,str) and reason.strip() and photo_facts.PHOTO_POLICY['condition_prefix'] not in reason else original['reason']))
        seen.add(identity)
    for candidate in candidates:
        if len(chosen)>=POLICY['question_limit']: break
        if candidate['identity'] not in seen: chosen.append(candidate); seen.add(candidate['identity'])
    return chosen[:POLICY['question_limit']]


def form_fields(task, saved, views, candidates):
    """Finite form metadata, including relevant saved values for correction."""
    catalogue = fields()
    judgments=calculate_v2(task['conditions'],task['legal'])['judgments']
    by_target = {f['target']: f for f in catalogue}
    result = {c['identity']: c for c in candidates if c['target'] != 'other_work'}
    for field in catalogue:
        if field['destination']['type'] == 'work_type':
            identity = key(field['target'])
            if identity in saved or work_feature_needed(field,judgments):
                result[identity] = dict(field, identity=identity, condition=POLICY['default_condition'])
    for identity, item in saved.items():
        if item.get('alias_of') or not photo_facts.active(item,views):continue
        field = by_target.get(item['target'])
        if not field or field['destination']['type'] in ('task', 'other_work'): continue
        probe = dict(saved); probe.pop(identity)
        if item['target'].startswith('manual.') and (probe.get(key(item['target'])) or {}).get('alias_of')==identity:probe.pop(key(item['target']),None)
        relevant = _assess(_without_value(task, field, item['condition'], views), probe, views, catalogue, only_identity=identity)['candidates']
        if any(c['identity'] == identity for c in relevant):
            metadata=dict(photo_id=item['photo_id'],photo_label=item.get('photo_label'),display_condition=item.get('photo_label'),label=item.get('photo_label','등록한 사진')+' · '+field['label']) if field['destination']['type']=='manual' and item.get('photo_id') is not None else {}
            result.setdefault(identity,dict(field, identity=identity, condition=item['condition'],**metadata))
    return list(result.values())
