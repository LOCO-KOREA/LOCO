"""Grounded values and projection onto the existing task DTO. No database access."""
import copy
from ergo.pose_contract import PHOTO_SOURCES
from ergo.vision.contract import SOURCE as VISION_SOURCE
import json
import math
import re
from .contract import fields, key, POLICY, PHOTO_VIEWS, PHOTO_DESTINATIONS, LIFT_FIELDS, SESSION_KEY
from .grounding import evidence_quote, number_grounded, number_proof, unknown_evidence
from .photo_load import photo_load
from . import photo_facts
from ergo.vision.contract import SOURCE as VISION_SOURCE
from ergo.engine.task_defaults import now

TITLE_SENTENCE_END=re.compile(r'(?<!\d)\.|\.(?!\d)|[!?。\n]')

def initial_title(text):
    return TITLE_SENTENCE_END.split(text,1)[0][:POLICY['auto_title_length']].strip()

def evidence(fact):
    source = 'OTHER' if fact['source'] in ('AI',VISION_SOURCE,*PHOTO_SOURCES) else 'INTERVIEW'
    text=f"{fact['source']}: {fact.get('quote','')}"
    if fact['source']==VISION_SOURCE:
        text=json.dumps(dict(photo_vision=True,photo_id=fact.get('photo_id'),view=fact.get('view'),
            vision_signature=fact.get('vision_signature'),vision_observation=fact.get('vision_observation'),
            vision_proof=fact.get('vision_proof'),quote=fact.get('quote','')),ensure_ascii=False)
    return dict(source=source, text=text, observed_at=fact.get('updated_at') or now())


def _owns_visual_evidence(evidence_value, previous):
    if (evidence_value or {}).get('source')!='OTHER':return False
    try: proof=json.loads(evidence_value.get('text') or '')
    except (ValueError,TypeError):return False
    return isinstance(proof,dict) and proof.get('photo_vision') is True and bool(previous.get('vision_signature')) and \
        proof.get('vision_signature')==previous['vision_signature'] and proof.get('photo_id')==previous.get('photo_id')


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


def merge_model(existing, raw, text, *, focus=(), prior_texts=(), outcomes=None, reconcile=False, preserve_conflicts=False, protect_photo_context=False):
    result, dropped = copy.deepcopy(existing), []
    catalogue = {f['target']: f for f in fields()}
    def record(item,index,outcome,reason=None,condition=None):
        if outcomes is not None:
            outcomes.append(dict(proposal_index=index,target=item.get('target') if isinstance(item,dict) else None,
                condition=condition or (item.get('condition') if isinstance(item,dict) else None) or POLICY['default_condition'],
                quote=item.get('quote') if isinstance(item,dict) else None,outcome=outcome,reason=reason,
                proposed_value=(item.get('number') if item.get('number') is not None else item.get('text')) if isinstance(item,dict) else None))
        if outcome=='REJECTED':dropped.append(dict(target=item.get('target') if isinstance(item,dict) else None,
            condition=condition or (item.get('condition') if isinstance(item,dict) else None) or POLICY['default_condition'],
            reason=reason,proposal_index=index))
    for index,item in enumerate(raw if isinstance(raw,list) else []):
        if not isinstance(item,dict) or item.get('target') not in catalogue:
            record(item,index,'REJECTED','UNKNOWN_TARGET'); continue
        field = catalogue[item['target']]
        if not field['ai_writable']:
            record(item,index,'REJECTED','EXPLICIT_FIELD_SELECTION_REQUIRED'); continue
        quote=evidence_quote(item.get('quote'),text)
        current_quote=quote is not None
        source_text=text
        if not current_quote:
            for prior in prior_texts:
                quote=evidence_quote(item.get('quote'),prior)
                if quote is not None:source_text=prior;break
        if quote is None:
            record(item,index,'REJECTED','QUOTE_NOT_IN_TEXT'); continue
        condition = item.get('condition') or POLICY['default_condition']
        if not isinstance(condition,str) or len(condition)>80:
            record(item,index,'REJECTED','BAD_CONDITION'); continue
        if not field['conditioned'] and not (field['destination']['type']=='manual' and condition.startswith(photo_facts.PHOTO_POLICY['condition_prefix'])): condition=POLICY['default_condition']
        if field['destination']['type']=='manual' and condition.startswith(photo_facts.PHOTO_POLICY['condition_prefix']) and not any(f.get('condition')==condition for f in existing.values()):
            record(item,index,'REJECTED','BAD_CONDITION',condition);continue
        focused = [f for f in focus if f['target']==field['target']]
        if condition==POLICY['default_condition'] and len(focused)==1: condition=focused[0]['condition']
        identity = key(field['target'],condition)
        previous = result.get(identity)
        raw_value = item.get('number') if field['kind']=='number' else item.get('text')
        if item.get('text')=='UNKNOWN' and unknown_evidence(item['quote']):
            if protect_photo_context and field['destination']['type'] in PHOTO_DESTINATIONS:
                record(item,index,'UNCHANGED' if previous and previous['value'] is None else 'REJECTED',
                    None if previous and previous['value'] is None else 'PHOTO_CONTEXT_CONFIRMATION_REQUIRED',condition);continue
            if previous and (not current_quote or reconcile) and previous.get('quote')!=quote:
                record(item,index,'REJECTED','STALE_QUOTE',condition);continue
            if previous and previous['source']=='USER':
                record(item,index,'UNCHANGED' if previous['value'] is None else 'REJECTED',
                       None if previous['value'] is None else 'USER_VALUE_KEPT',condition);continue
            result[identity]=fact(field,None,'USER',quote,condition); result[identity]['origin']='AI'
            record(item,index,'ACCEPTED',condition=condition)
            continue
        try: value = normalize(field,raw_value)
        except ValueError:
            record(item,index,'REJECTED','BAD_VALUE',condition); continue
        if value is None:
            record(item,index,'REJECTED','EMPTY_VALUE',condition); continue
        proof=None
        if field['kind']=='number':
            proof=number_proof(field,value,item['quote'],bare=bool(focused) and current_quote,context=source_text+' '+text,
                               source=source_text,calculation=item.get('calculation'))
            if proof is None:
                record(item,index,'REJECTED','UNIT_OR_NUMBER_NOT_GROUNDED',condition); continue
        if previous and previous['value']!=value and not current_quote:
            record(item,index,'REJECTED','STALE_QUOTE',condition); continue
        if previous and previous['source']=='USER':
            record(item,index,'REJECTED' if previous['value']!=value else 'UNCHANGED',
                   'USER_VALUE_KEPT' if previous['value']!=value else None,condition)
            continue
        if protect_photo_context and (field['destination']['type'] in PHOTO_DESTINATIONS
                or previous and previous.get('source')==VISION_SOURCE and previous.get('photo_id') is not None):
            record(item,index,'UNCHANGED' if previous and previous['value']==value else 'REJECTED',
                None if previous and previous['value']==value else 'PHOTO_CONTEXT_CONFIRMATION_REQUIRED',condition);continue
        if previous and previous['source']==VISION_SOURCE and not current_quote and previous['value']==value:
            record(item,index,'UNCHANGED',condition=condition);continue
        current_vision_text=bool(previous and previous['source']==VISION_SOURCE and current_quote)
        if previous and previous['state']=='CONFLICT' and (not current_quote or preserve_conflicts or reconcile) and not current_vision_text:
            record(item,index,'REJECTED','CONFLICT',condition);continue
        if reconcile and previous and previous['value']==value and not current_vision_text:
            record(item,index,'UNCHANGED',condition=condition);continue
        if previous and previous['state']=='KNOWN' and previous['value']!=value and not current_vision_text:
            if field['destination']['type']!='task' or reconcile:
                result[identity] = dict(previous,state='CONFLICT',conflict=dict(value=value,quote=quote))
                record(item,index,'REJECTED','CONFLICT',condition)
                continue
        result[identity] = fact(field,value,'AI',quote,condition)
        if proof and proof.get('operation'):result[identity]['calculation']=proof
        record(item,index,'ACCEPTED',condition=condition)
        if field['gate']:
            gate = catalogue['work_type.'+field['gate']]
            gate_key = key(gate['target'])
            if gate_key not in result: result[gate_key]=fact(gate,'YES','AI',quote)
    return result,dropped


def apply_answers(existing, answers, candidates=(), *, photo_views=None):
    result = copy.deepcopy(existing)
    catalogue = {f['target']:f for f in fields()}
    for item in answers:
        if not isinstance(item,dict) or item.get('target') not in catalogue: raise ValueError('알 수 없는 입력 항목입니다.')
        field = catalogue[item['target']]
        condition = item.get('condition') or POLICY['default_condition']
        if not isinstance(condition,str) or len(condition)>80: raise ValueError('작업 조건 이름은 80자 이내로 입력하세요.')
        if field['destination']['type']=='manual' and condition.startswith(photo_facts.PHOTO_POLICY['condition_prefix']):
            if photo_views is not None and photo_facts.photo_id(dict(condition=condition),photo_views) not in photo_views.values():raise ValueError('현재 작업에 등록된 사진의 자세만 수정할 수 있어요.')
        elif not field['conditioned']: condition=POLICY['default_condition']
        value = normalize(field,item.get('value'))
        identity=key(field['target'],condition)
        prior=result.get(identity)
        result[identity] = fact(field,value,'USER',item.get('quote') or '직접 입력',condition)
        if prior and prior['source'] in PHOTO_SOURCES and prior['value']==value:
            result[identity].update(origin=prior['source'],quote='사진 추정 확인: '+prior['quote'],angles=prior.get('angles',[]))
        if field['target']=='other_work' and value in ('NO',None):
            for other in catalogue.values():
                identity=key(other['target'])
                if other['destination']['type']=='work_type' and (identity not in result or result[identity]['state']=='UNKNOWN'):
                    result[identity]=fact(other,value,'USER','설명한 작업 외에 다른 작업은 없다고 답함' if value=='NO' else '다른 작업 여부를 모른다고 답함')
    return result


def add_photo_facts(existing, preview, views):
    return photo_facts.add(existing,preview,views)


def project(task, facts, views, preview):
    value=copy.deepcopy(task); catalogue={f['target']:f for f in fields()}
    default=POLICY['default_condition']
    known=lambda target: (facts.get(key(target)) or {}).get('value')
    primary=next((v for v in PHOTO_VIEWS if v in views),None)
    context=known('context'); usable=context=='YES'
    load_state, load_kg = photo_load(facts)
    load_link=(facts.get(key('load_kg')) or {}).get('input_link') or {}
    prior_link=(((task.get('conditions') or {}).get(SESSION_KEY) or {}).get('facts',{}).get(key('load_kg')) or {})
    prior_slots={slot.get('photo_id'):slot for slot in (task.get('capture') or {}).get('slots',[]) if slot.get('photo_id') is not None}
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
        if load_link or prior_link.get('origin')=='INPUT_LINK':
            old=(prior_slots.get(views[view]) or {}).get('observation') or {}
            old_owned=prior_link.get('origin')=='INPUT_LINK' and views[view] in (prior_link.get('input_link') or {}).get('photo_ids',[]) and old.get('measured_load_kg')==prior_link.get('value')
            valid_mass=type(old.get('measured_load_kg')) in (int,float) and math.isfinite(old['measured_load_kg']) and old['measured_load_kg']>=0
            if not old_owned and (old.get('load_state')=='UNLOADED' or old.get('load_state')=='MEASURED' and valid_mass):
                # A photo-specific observation has priority over the work-wide
                # derived link. Keep its own evidence as well as its value.
                slots[-1]['observation'].update(load_state=old['load_state'],measured_load_kg=old.get('measured_load_kg'),evidence=copy.deepcopy(old.get('evidence') or slots[-1]['observation']['evidence']))
    value['capture']=dict(protocol='GENERAL_STILLS_V1',slots=slots)
    primary_id=views.get(primary)
    # Preserve edits from other photos and fields the intake has never owned.
    manual={(m['slot_no'],m['scope'],m['field']):m for m in value['manual'] if any(s['slot_no']==m['slot_no'] and s['photo_id']==m['photo_id'] for s in slots)}
    # Removing a visual fact must also remove its still-owned projection. Otherwise
    # an old photo's YES would survive in the calculator after its fact disappeared.
    previous=(task.get('conditions',{}).get(SESSION_KEY) or {}).get('facts',{})
    for identity,old in previous.items():
        if old.get('source')!=VISION_SOURCE or old.get('alias_of') or identity in facts:continue
        field=catalogue.get(old.get('target'))
        if not field:continue
        destination=field['destination']
        if destination['type']=='work_type':
            for no in destination['criteria']:
                row=value['legal']['criteria'][no-1]
                if _owns_visual_evidence(row.get('evidence'),old):
                    row['condition_present']='UNKNOWN'
                    row['evidence']=dict(source='OTHER',text='사진 관찰의 근거가 바뀌어 다시 확인이 필요해요.',observed_at=old.get('updated_at'))
        elif destination['type']=='manual':
            for location,row in list(manual.items()):
                if row['photo_id']==old.get('photo_id') and row['scope']==destination['scope'] and row['field']==destination['field'] \
                        and row.get('source')=='AUTO_ACCEPTED' and _owns_visual_evidence(row.get('evidence'),old):
                    manual.pop(location)
    row_values={}
    for item in facts.values():
        if item.get('alias_of'):continue
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
            owner=photo_facts.photo_id(item,views)
            slot=next((slot for slot in slots if slot['photo_id']==owner),None)
            if slot is None:continue
            identity=(slot['slot_no'],destination['scope'],destination['field'])
            if val is None or item['state']=='ESTIMATED' or item['source'] in PHOTO_SOURCES and not usable:
                manual.pop(identity,None); continue
            source='AUTO_ACCEPTED' if item['source'] in (*PHOTO_SOURCES,VISION_SOURCE) else 'INTERVIEW'
            ev=evidence(item)
            if source=='AUTO_ACCEPTED' and item['source']!=VISION_SOURCE:
                ev['text']=json.dumps(dict(angles=item.get('angles',[]),quick_preview=True,photo_id=owner,view=item.get('view'),photo_proof=item.get('photo_proof')))
            manual[identity]=dict(slot_no=slot['slot_no'],photo_id=owner,scope=destination['scope'],field=destination['field'],value=val,source=source,evidence=ev)
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
        load_fact=facts.get(key('load')) if load_state=='UNLOADED' else facts.get(key('load_kg'))
        if known('load_link')=='YES' and load_state=='MEASURED' and load_kg==0 and load_fact is None:
            load_fact=next(f for f in facts.values() if f['target']=='card.lift.load_mass_kg' and f['value']==0 and f['state']=='KNOWN')
        for side in ('LEFT','RIGHT'):
            manual[(1,side,'coupling')]=dict(slot_no=1,photo_id=primary_id,scope=side,field='coupling',value='NOT_APPLICABLE',source='INTERVIEW',evidence=dict(source='INTERVIEW',text='물건 없음',observed_at=(load_fact or {}).get('updated_at')))
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
    catalogue={field['target']:field for field in fields()}
    for row in task['manual']:
        target=f"manual.{row['scope']}.{row['field']}"
        if target not in catalogue or row['value'] in (None,'UNKNOWN','NOT_APPLICABLE',''):continue
        slot=next((slot for slot in slots if slot['slot_no']==row['slot_no'] and slot['photo_id']==row['photo_id']),None)
        if slot is None:continue
        item=fact(catalogue[target],row['value'],'SAVED','저장된 입력',photo_facts.condition(row['photo_id']))
        item.update(photo_id=row['photo_id'],view=slot.get('label'),photo_label=photo_facts.VIEW_LABELS.get(slot.get('label'),'등록한 사진'))
        values[key(target,item['condition'])]=item
    return values
