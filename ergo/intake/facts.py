"""Grounded values and projection onto the existing task DTO. No database access."""
import copy
import json
import math
import re
from .contract import fields, key, POLICY, PHOTO_VIEWS, LIFT_FIELDS
from ergo.engine.task_defaults import now

NUMBER_WORDS = {'한':1,'하나':1,'두':2,'둘':2,'세':3,'셋':3,'네':4,'넷':4,'다섯':5,'여섯':6,'일곱':7,'여덟':8,'아홉':9,'열':10,'스무':20}
NUMBER = r'(\d+(?:\.\d+)?|스무|여덟|일곱|여섯|다섯|아홉|하나|둘|셋|넷|한|두|세|네|열)'


def evidence(fact):
    source = 'OTHER' if fact['source'] in ('AI','MOVENET') else 'INTERVIEW'
    return dict(source=source, text=f"{fact['source']}: {fact.get('quote','')}", observed_at=fact.get('updated_at') or now())


def number_grounded(value, quote, unit, *, bare=False):
    def number(s): return NUMBER_WORDS[s] if s in NUMBER_WORDS else float(s)
    text = re.sub(r'\s+', '', quote).lower()
    minute_rate=bool(re.search(r'분당|매분|(?<![\d.])(?:1|한)?분에|/분',text))
    hour_rate=bool(re.search(r'시간당|매시간|(?<![\d.])(?:1|한)?시간에|/시간',text))
    day_rate=bool(re.search(r'하루|일일|일당|/일',text))
    if unit=='회/분' and not minute_rate and not bare: return False
    if unit=='회/시간' and not hour_rate and not bare: return False
    if unit=='회/일' and (minute_rate or hour_rate): return False
    if unit=='일' and re.search(r'주당|매주|주\d|월당|매월',text): return False
    units = {'kg': [('kg',1),('킬로그램',1),('킬로',1),('g',.001)],
             'kg 상당': [('kg',1),('킬로',1)], '분': [('시간',60),('분',1),('초',1/60)],
             '일': [('일',1)], '회/일': [('번',1),('회',1)], '회/시간': [('번',1),('회',1)],
             '회/분': [('번',1),('회',1)],'개월':[('개월',1),('달',1)]}
    choices = units.get(unit, units['분'] if unit.startswith('분') else [])
    for suffix, scale in choices:
        for match in re.finditer(NUMBER + re.escape(suffix), text):
            observed = number(match.group(1))*scale
            if suffix=='시간' and text[match.end():].startswith('반'): observed += 30
            if math.isclose(value, observed, abs_tol=1e-6): return True
    return bool(bare and re.fullmatch(r'\d+(?:\.\d+)?',text) and math.isclose(value,float(text)))


def normalize(field, raw, *, unknown=False):
    if unknown or raw is None or raw == 'UNKNOWN': return None
    if field['kind']=='number':
        if isinstance(raw,bool) or not isinstance(raw,(int,float)) or not math.isfinite(raw) or raw<0:
            raise ValueError('0 이상 유한한 숫자를 입력하세요.')
        if field['maximum'] is not None and raw>field['maximum']:
            raise ValueError(f"{field['maximum']} {field['unit']} 이내로 입력하세요.")
        if field['unit'] in ('일','회/일','회/시간') and int(raw)!=raw:
            raise ValueError('횟수와 일수는 정수로 입력하세요.')
        return int(raw) if field['unit'] in ('일','회/일','회/시간') else raw
    if field['kind']=='choice':
        choice = next((c['value'] for c in field['choices'] if str(c['value'])==str(raw) or c['label']==raw), None)
        if choice is None: raise ValueError('목록에서 값을 선택하세요.')
        return choice
    if not isinstance(raw,str) or not raw.strip() or len(raw.strip())>80:
        raise ValueError('작업 이름은 1~80자로 입력하세요.')
    return raw.strip()


def fact(field, value, source, quote='', condition=None, *, previous=None):
    return dict(target=field['target'],condition=condition or POLICY['default_condition'],value=value,
                state='UNKNOWN' if value is None or value=='UNKNOWN' else 'KNOWN',source=source,
                quote=quote,updated_at=now(), conflict=None)


def merge_model(existing, raw, text, *, focus=(), prior_texts=()):
    result, dropped = copy.deepcopy(existing), []
    catalogue = {f['target']: f for f in fields()}
    for item in raw if isinstance(raw,list) else []:
        if not isinstance(item,dict) or item.get('target') not in catalogue:
            dropped.append(dict(reason='UNKNOWN_TARGET')); continue
        field = catalogue[item['target']]
        if not field['ai_writable']:
            dropped.append(dict(target=field['target'],reason='EXPLICIT_FIELD_SELECTION_REQUIRED')); continue
        quote = item.get('quote')
        current_quote=isinstance(quote,str) and re.sub(r'\s+','',quote) in re.sub(r'\s+','',text)
        prior_quote=isinstance(quote,str) and any(re.sub(r'\s+','',quote) in re.sub(r'\s+','',prior) for prior in prior_texts)
        if not isinstance(quote,str) or not quote.strip() or not (current_quote or prior_quote):
            dropped.append(dict(target=field['target'],reason='QUOTE_NOT_IN_TEXT')); continue
        condition = item.get('condition') or POLICY['default_condition']
        if not isinstance(condition,str) or len(condition)>80: continue
        if not field['conditioned']: condition=POLICY['default_condition']
        focused = [f for f in focus if f['target']==field['target']]
        if condition==POLICY['default_condition'] and len(focused)==1: condition=focused[0]['condition']
        identity = key(field['target'],condition)
        raw_value = item.get('number') if field['kind']=='number' else item.get('text')
        if item.get('text')=='UNKNOWN' and re.search(r'모르|모름|알\s*수\s*없|미확인',quote):
            if result.get(identity,{}).get('source')!='USER':
                result[identity]=fact(field,None,'USER',quote,condition); result[identity]['origin']='AI'
            continue
        try: value = normalize(field,raw_value)
        except ValueError:
            dropped.append(dict(target=field['target'],reason='BAD_VALUE')); continue
        if value is None: continue
        if field['kind']=='number' and not number_grounded(value,quote,field['unit'],bare=bool(focused) and current_quote):
            dropped.append(dict(target=field['target'],reason='UNIT_OR_NUMBER_NOT_GROUNDED')); continue
        previous = result.get(identity)
        if previous and previous['value']!=value and not current_quote:
            dropped.append(dict(target=field['target'],reason='STALE_QUOTE')); continue
        if previous and previous['source']=='USER':
            if previous['value']!=value: dropped.append(dict(target=field['target'],reason='USER_VALUE_KEPT'))
            continue
        if previous and previous['state']=='KNOWN' and previous['value']!=value:
            if field['destination']['type']!='task':
                result[identity] = dict(previous,state='CONFLICT',conflict=dict(value=value,quote=quote))
                continue
        result[identity] = fact(field,value,'AI',quote,condition)
        if field['gate']:
            gate = catalogue['work_type.'+field['gate']]
            gate_key = key(gate['target'])
            if gate_key not in result: result[gate_key]=fact(gate,'YES','AI',quote)
    return result,dropped


def apply_answers(existing, answers, candidates=()):
    result = copy.deepcopy(existing)
    catalogue = {f['target']:f for f in fields()}
    for item in answers:
        if not isinstance(item,dict) or item.get('target') not in catalogue: raise ValueError('알 수 없는 입력 항목입니다.')
        field = catalogue[item['target']]
        condition = item.get('condition') or POLICY['default_condition']
        if not isinstance(condition,str) or len(condition)>80: raise ValueError('작업 조건 이름은 80자 이내로 입력하세요.')
        if not field['conditioned']: condition=POLICY['default_condition']
        value = normalize(field,item.get('value'))
        identity=key(field['target'],condition)
        prior=result.get(identity)
        result[identity] = fact(field,value,'USER',item.get('quote') or '직접 입력',condition)
        if prior and prior['source']=='MOVENET' and prior['value']==value:
            result[identity].update(origin='MOVENET',quote='사진 추정 확인: '+prior['quote'],angles=prior.get('angles',[]))
        if field['target']=='other_work' and value in ('NO',None):
            for other in catalogue.values():
                identity=key(other['target'])
                if other['destination']['type']=='work_type' and (identity not in result or result[identity]['state']=='UNKNOWN'):
                    result[identity]=fact(other,value,'USER','설명한 작업 외에 다른 작업은 없다고 답함' if value=='NO' else '다른 작업 여부를 모른다고 답함')
    return result


def add_photo_facts(existing, preview, views):
    result=copy.deepcopy(existing); catalogue={f['target']:f for f in fields()}
    primary=next((v for v in PHOTO_VIEWS if v in views),None)
    for view,data in preview.get('views',{}).items():
        direction=(data.get('guess') or {}).get('forward_direction')
        target='view_'+view
        if direction and target in catalogue and (key(target) not in result or result[key(target)]['state']=='UNKNOWN' and result[key(target)]['source']=='MOVENET'):
            result[key(target)]=fact(catalogue[target],direction,'MOVENET','사진에서 바라보는 방향 추정')
    for measured in preview.get('measured',[]):
        if measured['view']!=primary: continue
        target=f"manual.{measured['scope']}.{measured['field']}"
        if target in catalogue and (key(target) not in result or result[key(target)]['state']=='UNKNOWN' and result[key(target)]['source']=='MOVENET'):
            f=fact(catalogue[target],measured['value'],'MOVENET',' / '.join(str(a['value_deg'])+'°' for a in measured['angles']))
            f['angles']=measured['angles']
            if measured.get('low_confidence') or measured.get('boundary_review'): f['state']='ESTIMATED'
            result[key(target)]=f
    if preview.get('signals',{}).get('seated') and (key('manual.COMMON.seated') not in result or result[key('manual.COMMON.seated')]['state']=='UNKNOWN' and result[key('manual.COMMON.seated')]['source']=='MOVENET'):
        result[key('manual.COMMON.seated')]=fact(catalogue['manual.COMMON.seated'],'YES','MOVENET','사진에서 앉은 자세 감지')
    return result


def project(task, facts, views, preview):
    value=copy.deepcopy(task); catalogue={f['target']:f for f in fields()}
    default=POLICY['default_condition']
    known=lambda target: (facts.get(key(target)) or {}).get('value')
    primary=next((v for v in PHOTO_VIEWS if v in views),None)
    context=known('context'); usable=context=='YES'
    load_state=known('load') or 'UNKNOWN'; load_kg=known('load_kg')
    masses={f['value'] for f in facts.values() if f['target']=='card.lift.load_mass_kg' and f['state']=='KNOWN'}
    if known('load_link')=='YES' and len(masses)==1: load_kg=next(iter(masses)); load_state='MEASURED'
    if load_kg is not None and load_state=='UNKNOWN': load_state='MEASURED'
    slots=[]
    for i,view in enumerate(v for v in PHOTO_VIEWS if v in views):
        guess=(preview.get('views',{}).get(view) or {}).get('guess') or {}
        verified=usable and guess.get('orientation') in ('SIDE','OBLIQUE')
        slots.append(dict(slot_no=i+1,photo_id=views[view],label=view,analysis_target=view==primary,
            camera_side='FRONT' if view=='FRONT' else guess.get('camera_side') or view,
            forward_direction=known('view_'+view),side_view_verified='YES' if verified else 'UNKNOWN',
            observation=dict(load_state=load_state,measured_load_kg=load_kg if load_state=='MEASURED' else None,
                single_person=context or 'UNKNOWN',full_frame=context or 'UNKNOWN',normal_work=context or 'UNKNOWN',
                evidence=dict(source='INTERVIEW',text='추가 확인: 사진과 작업 정보',observed_at=(facts.get(key('context')) or {}).get('updated_at')))))
    value['capture']=dict(protocol='GENERAL_STILLS_V1',slots=slots)
    primary_id=views.get(primary)
    # Preserve edits from other photos and fields the intake has never owned.
    manual={(m['slot_no'],m['scope'],m['field']):m for m in value['manual'] if any(s['slot_no']==m['slot_no'] and s['photo_id']==m['photo_id'] for s in slots)}
    row_values={}
    for item in facts.values():
        field=catalogue.get(item['target'])
        if not field: continue
        destination=field['destination']; kind=destination['type']; val=item['value']
        if kind=='work_type':
            for n in destination['criteria']:
                value['legal']['criteria'][n-1]['condition_present']=val or 'UNKNOWN'
                value['legal']['criteria'][n-1]['evidence']=evidence(item)
        elif kind=='conditions': value['conditions'][destination['field']]=val if val is not None else ('UNKNOWN' if destination['field']=='one_off' else None)
        elif kind=='task' and val is not None: value[destination['field']]=val
        elif kind=='complete':
            for n in destination['criteria']: value['legal']['criteria'][n-1]['rows_complete']=val or 'UNKNOWN'
        elif kind=='manual' and primary_id is not None:
            identity=(1,destination['scope'],destination['field'])
            if val is None or item['state']=='ESTIMATED' or item['source']=='MOVENET' and not usable:
                manual.pop(identity,None); continue
            source='AUTO_ACCEPTED' if item['source']=='MOVENET' else 'INTERVIEW'
            ev=evidence(item)
            if source=='AUTO_ACCEPTED': ev['text']=json.dumps(dict(angles=item.get('angles',[]),quick_preview=True))
            manual[identity]=dict(slot_no=1,photo_id=primary_id,scope=destination['scope'],field=destination['field'],value=val,source=source,evidence=ev)
        elif kind=='criterion':
            mapping=destination['mapping']
            if 'exposure' in mapping:
                exposure=next(e for e in value['legal']['exposures'] if e['condition_code']==mapping['exposure'])
                exposure.update(minutes=val,evidence=evidence(item))
            elif 'criterion' in mapping:
                value['legal']['criteria'][destination['criteria'][0]-1][mapping['criterion']]=val or 'UNKNOWN'
            else:
                name=mapping.get('lift') or mapping.get('row')
                for n in destination['criteria']:
                    if 'lift' in mapping and name not in LIFT_FIELDS[n]: continue
                    row=row_values.setdefault(n,{}).setdefault(item['condition'],dict(row_id=item['condition'],label=item['condition'],evidence=evidence(item)))
                    row[name]=val
    for n,rows in row_values.items():
        criterion=value['legal']['criteria'][n-1]
        prior={r['row_id']:r for r in criterion.get('rows',[])}
        prior.update(rows); criterion['rows']=list(prior.values())
        # The user must state completeness; the presence of one extracted row is not proof.
        criterion['rows_complete']=known('complete.'+next(f['gate'] for f in catalogue.values() if f['destination'].get('type')=='complete' and n in f['destination']['criteria'])) or criterion.get('rows_complete','UNKNOWN')
    if primary_id is not None and (load_state=='UNLOADED' or load_state=='MEASURED' and load_kg==0):
        for side in ('LEFT','RIGHT'):
            manual[(1,side,'coupling')]=dict(slot_no=1,photo_id=primary_id,scope=side,field='coupling',value='NOT_APPLICABLE',source='INTERVIEW',evidence=dict(source='INTERVIEW',text='물건 없음',observed_at=now()))
    value['manual']=list(manual.values())
    value['analysis_scope']=dict(judgment=True,pose=bool(slots),tags=bool(slots),reba=bool(slots))
    return value


def read_values(task):
    """Read actual saved values; never reconstruct missing data from defaults."""
    values={}; slots=task['capture'].get('slots',[]); primary=next((s for s in slots if s['analysis_target']),None)
    manual={(m['scope'],m['field']):m for m in task['manual'] if primary and m['photo_id']==primary['photo_id'] and m['slot_no']==primary['slot_no']}
    for field in fields():
        d=field['destination']; kind=d['type']; rows=[]
        if kind=='work_type':
            states=[task['legal']['criteria'][n-1]['condition_present'] for n in d['criteria']]
            val='YES' if 'YES' in states else 'NO' if all(s=='NO' for s in states) else None
        elif kind=='conditions': val=task['conditions'].get(d['field'])
        elif kind=='task': val=task.get(d['field']); val=None if val=='사진 분석 작업' else val
        elif kind=='context':
            obs=primary.get('observation',{}) if primary else {}
            states=[obs.get(k,'UNKNOWN') for k in ('single_person','full_frame','normal_work')]
            val='YES' if all(s=='YES' for s in states) else 'NO' if 'NO' in states else None
        elif kind=='load': val=(primary or {}).get('observation',{}).get('load_state')
        elif kind=='load_kg': val=(primary or {}).get('observation',{}).get('measured_load_kg')
        elif kind=='view': val=next((s.get('forward_direction') for s in slots if s.get('camera_side')==d['view']),None)
        elif kind=='manual': val=(manual.get((d['scope'],d['field'])) or {}).get('value')
        elif kind=='complete':
            states=[task['legal']['criteria'][n-1].get('rows_complete') for n in d['criteria']]
            val=states[0] if len(set(states))==1 else None
        elif kind=='criterion':
            mapping=d['mapping']; val=None
            if 'exposure' in mapping: val=next((e['minutes'] for e in task['legal']['exposures'] if e['condition_code']==mapping['exposure']),None)
            elif 'criterion' in mapping: val=task['legal']['criteria'][d['criteria'][0]-1].get(mapping['criterion'])
            else:
                name=mapping.get('lift') or mapping.get('row')
                for n in d['criteria']:
                    if 'lift' in mapping and name not in LIFT_FIELDS[n]: continue
                    for row in task['legal']['criteria'][n-1]['rows']:
                        if row.get(name) is not None: rows.append((row['row_id'],row[name]))
        else: val=None
        for condition,number in rows:
            values[key(field['target'],condition)]=fact(field,number,'SAVED','저장된 입력',condition)
        if val is not None and val not in ('UNKNOWN','NOT_APPLICABLE',''):
            values[key(field['target'])]=fact(field,val,'SAVED','저장된 입력')
    return values
