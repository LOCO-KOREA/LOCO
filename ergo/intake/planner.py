"""Find unanswered inputs using the real calculators; let AI select and phrase them."""
from .contract import fields, key, POLICY, LIFT_FIELDS
from ergo.engine.burden_rules import calculate_v2
from ergo.engine.reba_scoring import calculate_reba


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
    judgments=calculate_v2(task['conditions'],task['legal'])['judgments']
    reba=calculate_reba(task, None) if views else None
    missing=set(p for j in judgments if j['computed_status'] in ('NEEDS_INPUT','NEEDS_REVIEW') for p in j['missing_fields'])
    if reba: missing.update(p for row in reba['slots'] for p in row['missing_fields'])
    catalogue=fields()
    known=lambda t: (facts.get(key(t)) or {}).get('value')
    has=lambda t: key(t) in facts
    unknown_work=[f for f in catalogue if f['destination']['type']=='work_type' and not has(f['target'])]
    masses={f['value'] for f in facts.values() if f['target']=='card.lift.load_mass_kg' and f['state']=='KNOWN'}
    candidates=[]
    for field in catalogue:
        t=field['target']; d=field['destination']; kind=d['type']
        if kind=='task': continue  # A report title can be edited later; it is not a calculation gap.
        if kind in ('context','view','manual','load','load_kg','load_link') and not views: continue
        if kind=='view' and d['view'] not in views: continue
        if kind=='manual' and known('context')!='YES': continue
        if kind=='manual' and d['field']=='coupling' and (known('load')=='UNLOADED' or known('load_kg')==0): continue
        if t=='load_link' and (len(masses)!=1 or has('load') or has('load_kg')): continue
        if t=='load' and len(masses)==1 and not has('load_link'): continue
        if t=='load_kg' and known('load')!='MEASURED': continue
        if t=='other_work' and (not unknown_work or not any(known('work_type.'+f['target'].split('.')[-1])=='YES' for f in catalogue if f['destination']['type']=='work_type')): continue
        if kind=='work_type' and not has('other_work') and any(f['target']=='other_work' for f in candidates): continue
        if field['gate'] and known('work_type.'+field['gate'])!='YES': continue
        conditions=sorted({f['condition'] for f in facts.values() if f['target'].startswith('card.'+str(field['gate'])+'.')}) or [POLICY['default_condition']]
        if kind!='criterion' or not (d.get('mapping',{}).get('row') or d.get('mapping',{}).get('lift')): conditions=[POLICY['default_condition']]
        for condition in conditions:
            item=facts.get(key(t,condition))
            if item and (item['state']=='KNOWN' or item['state']=='UNKNOWN' and item['source']=='USER'): continue
            relevant=bool(set(paths(field,condition)) & missing)
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
            reason='결과 계산에 필요한 정보가 아직 없어요.'
            if item and item['state']=='CONFLICT': reason='앞서 기록한 값과 새 설명이 달라 확인이 필요해요.'
            candidates.append(dict(field,target=t,condition=condition,text=question,reason=reason,
                identity=key(t,condition),priority=0 if item and item['state']=='CONFLICT' else field['priority']))
    if any(c['target']=='other_work' for c in candidates) and not has('other_work'):
        candidates=[c for c in candidates if c['destination']['type']!='work_type']
    candidates.sort(key=lambda c:(c['priority'],c['target'],c['condition']))
    return dict(judgments=judgments,reba=reba,candidates=candidates,
                missing_count=len(candidates),complete=not any(j['computed_status'] in ('NEEDS_INPUT','NEEDS_REVIEW') for j in judgments) and (not reba or reba['status']=='COMPLETE'))


def choose(candidates, proposed=()):
    by_id={c['identity']:c for c in candidates}; chosen=[]; seen=set()
    for candidate in candidates:
        if candidate['priority']==0:
            chosen.append(candidate); seen.add(candidate['identity'])
    for p in proposed if isinstance(proposed,list) else []:
        if not isinstance(p,dict): continue
        identity=key(p.get('target',''),p.get('condition'))
        if identity not in by_id or identity in seen: continue
        original=by_id[identity]
        # A question may change wording, never the field, choices, units or ownership.
        text=p.get('text'); reason=p.get('reason')
        chosen.append(dict(original,text=text[:300] if isinstance(text,str) and text.strip() else original['text'],
                           reason=reason[:300] if isinstance(reason,str) and reason.strip() else original['reason']))
        seen.add(identity)
    for candidate in candidates:
        if len(chosen)>=POLICY['question_limit']: break
        if candidate['identity'] not in seen: chosen.append(candidate); seen.add(candidate['identity'])
    return chosen[:POLICY['question_limit']]
