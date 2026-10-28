"""Persist image observations only for their original task, photo and source bytes."""
import copy
import hashlib
import json
import math
import os
from uuid import uuid4
from concurrent.futures import ThreadPoolExecutor, as_completed
from backend import ai_config
from backend import photo_identity
from backend.engine.task_defaults import now
from backend.intake import contract as intake_contract, facts, photo_facts
from backend.vision import contract, images, client

ERROR_MESSAGES=dict(NO_API_KEY='사진을 분석할 AI 연결 정보를 확인해 주세요.',
    MODEL_NOT_CONFIGURED='사진을 분석할 AI 모델을 정해 주세요.',
    INVALID_STRUCTURED_CONTENT='사진 관찰 결과를 읽지 못했어요. 다시 정리해 주세요.',
    IMAGE_UNREADABLE='등록한 사진을 읽지 못했어요. 사진 파일을 확인해 주세요.',
    STALE_PHOTO='분석 중 사진이 바뀌어 이전 사진의 관찰을 현재 사진에 적용하지 않았어요.',
    TASK_REPLACED='분석 중 작업이 삭제되거나 바뀌어 관찰 결과를 적용하지 않았어요.')

def _hash(value):return hashlib.sha256(json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()

def _safe_json(value):
    if isinstance(value,float) and not math.isfinite(value):return dict(invalid_number=repr(value))
    if isinstance(value,dict):return {key:_safe_json(item) for key,item in value.items()}
    if isinstance(value,list):return [_safe_json(item) for item in value]
    return copy.deepcopy(value)

def _context(session,view):
    # Text extraction in this turn must not invalidate its own image response.
    # View, source image, owner and image/model policy define visual context.
    return dict(view=view,evidence_policy='VISIBLE_IMAGE_ONLY')

def _descriptor(task,session,view,identity,digest,settings):
    selected=ai_config.values(settings)
    owner=dict(task_id=task['task_id'],task_created_at=task['created_at'],photo_id=identity,
        photo_generation=session.get('photo_vision',{}).get('owners',{}).get(str(identity)))
    configuration=dict(version=contract.VERSION,prompt=contract.PROMPT_VERSION,policy=contract.policy(),
        model=selected['gpt_model'],reasoning_effort=selected['gpt_reasoning_effort'])
    context=_context(session,view)
    signature=_hash(dict(owner=owner,view=view,source_sha256=digest,configuration=configuration,context=context))
    return dict(photo_id=identity,view=view,photo_label=photo_facts.VIEW_LABELS.get(view,'등록한 사진'),
        owner=owner,source_sha256=digest,signature=signature,configuration=configuration,context=context)

def _descriptors(task,session,settings):
    source={(entry[0],entry[1]):entry[2] for entry in json.loads(session.get('photo_signature') or '[]')}
    return [_descriptor(task,session,view,identity,source.get((view,identity),'unreadable'),settings)
        for view,identity in sorted(session.get('views',{}).items())]

def refresh(task,session,settings,preview=None,photos=None):
    """Pure cache selection/invalidation: never request a model during a read."""
    state=session.setdefault('photo_vision',dict(version=contract.VERSION,photos=[],history=[],catalogue=[]))
    if photos is not None:
        state['owners']={str(identity):photo_identity.identity(photos[identity]) for identity in session.get('views',{}).values() if identity in photos}
    records=state.get('photos',[])+state.get('history',[])
    desired=_descriptors(task,session,settings);selected=[]
    for item in desired:
        matching=[record for record in records if record.get('signature')==item['signature']]
        record=next((record for record in matching if record.get('status') in ('OBSERVED','UNCERTAIN')),
            next((record for record in reversed(matching) if record.get('status')=='ERROR'),None))
        if record:selected.append(copy.deepcopy(record))
    previous=state.get('photos',[])
    selected_by_id={record.get('request_id'):record for record in selected}
    previous_ids=[record.get('request_id') for record in previous]
    if (len(previous)==len(selected)==len(selected_by_id)==len(set(previous_ids))
            and all(identity for identity in previous_ids)
            and all(selected_by_id.get(record.get('request_id'))==record for record in previous)):
        selected=[selected_by_id[identity] for identity in previous_ids]
    active_ids={record.get('request_id') for record in selected}
    history=[];seen=set()
    for record in records:
        identity=record.get('request_id')
        if identity in active_ids or identity in seen:continue
        seen.add(identity);history.append(copy.deepcopy(record))
    state.update(version=contract.VERSION,photos=selected,history=history,
        catalogue=contract.public_contract()['catalogue'])
    active_signatures={record['signature'] for record in selected if record['status'] in ('OBSERVED','UNCERTAIN')}
    pose_known=set()
    if preview is not None:
        pose_known={intake_contract.key(f"manual.{row['scope']}.{row['field']}",photo_facts.condition(row['photo_id']))
            for row in photo_facts.observations(preview,session.get('views',{}))
            if row.get('value') is not None and not row.get('low_confidence') and not row.get('boundary_review')}
    for identity,item in list(session.get('facts',{}).items()):
        if item.get('source')!='VISION':continue
        canonical=item.get('alias_of') or identity
        if canonical in pose_known:
            session.setdefault('invalidated_photo_facts',{})[identity+'@'+str(item.get('vision_signature',''))]=copy.deepcopy(item)
            session['facts'].pop(identity,None)
        elif item.get('vision_signature') not in active_signatures:
            if item.get('vision_signature') is not None:
                session.setdefault('invalidated_photo_facts',{})[identity+'@'+str(item['vision_signature'])]=copy.deepcopy(item)
                # Keep an unknown tombstone so projection clears the formerly
                # owned manual/global value instead of reviving it as SAVED.
                session['facts'][identity]=dict(item,value=None,state='UNKNOWN',vision_signature=None,
                    quote='사진 또는 AI 사진 관찰 설정이 바뀌어 다시 확인',conflict=None)
    apply_context(session)
    return state

def public(session):return copy.deepcopy(session.get('photo_vision') or dict(version=contract.VERSION,photos=[],history=[],catalogue=contract.public_contract()['catalogue']))

def known(session):
    if session.get('facts',{}).get(intake_contract.key('context'),{}).get('value')=='NO':return []
    return [dict(photo_id=record['photo_id'],view=record['view'],signature=record['signature'],
        observations=copy.deepcopy(record['observations'])) for record in session.get('photo_vision',{}).get('photos',[])
        if record['status'] in ('OBSERVED','UNCERTAIN')]

def _diagnostic(record,code,message,**context):
    item=dict(code=code,message=message,**context)
    if item not in record.setdefault('diagnostics',[]):record['diagnostics'].append(item)

def apply_context(session):
    """Honor a user's negative photo context while retaining the visual receipt."""
    context=session.get('facts',{}).get(intake_contract.key('context'),{})
    state=session.get('photo_vision',{})
    if context.get('value')=='NO':
        state['application_reason']='사용자가 사진 상황을 확인하지 않아 사진 관찰을 작업 입력에 적용하지 않았어요.'
        for identity,item in list(session.get('facts',{}).items()):
            if item.get('source')!=contract.SOURCE or item.get('value') is None:continue
            session.setdefault('invalidated_photo_facts',{})[identity+'@'+str(item.get('vision_signature'))]=copy.deepcopy(item)
            session['facts'][identity]=dict(item,value=None,state='UNKNOWN',vision_signature=None,
                quote='사용자가 사진 상황을 확인하지 않아 관찰 적용에서 제외',conflict=None)
        return
    state.pop('application_reason',None)
    for record in state.get('photos',[]):_merge_candidates(session,record)

def _merge_candidates(session,record):
    raw=record.get('raw_response') or {}
    if record.get('status') not in ('OBSERVED','UNCERTAIN') or not contract.valid(raw):return
    if session.get('facts',{}).get(intake_contract.key('context'),{}).get('value')=='NO':return
    threshold=contract.policy()['manual_confidence'];catalogue={field['target']:field for field in intake_contract.fields()}
    def confident(value):return type(value) in (int,float) and math.isfinite(value) and threshold<=value<=1
    candidates=raw['manual_candidates'];values={}
    for item in candidates:
        if isinstance(item,dict) and isinstance(item.get('scope'),str) and isinstance(item.get('field'),str) and isinstance(item.get('value'),str):
            values.setdefault((item['scope'],item['field']),set()).add(item['value'])
    for item in candidates:
        if not isinstance(item,dict) or not isinstance(item.get('scope'),str) or not isinstance(item.get('field'),str):continue
        pair=(item.get('scope'),item.get('field'));expected_observation=contract.MANUAL_FIELDS.get(pair)
        observation=item.get('observation')
        allowed_observation=observation in contract.MANUAL_OBSERVATION_ALIASES.get(pair,(expected_observation,))
        if not isinstance(observation,str):observation=None
        visible=raw['observations'].get(observation,{})
        target=f"manual.{pair[0]}.{pair[1]}";identity=intake_contract.key(target,photo_facts.condition(record['photo_id']))
        observed_value=contract.manual_value(pair[0],pair[1],item.get('value'))
        posture=pair[1] in contract.POSTURE_VALUES
        confidence=item.get('confidence');seen_confidence=visible.get('confidence')
        def usable_confidence(value):
            return type(value) in (int,float) and math.isfinite(value) and (contract.policy()['posture_confidence'] if posture else threshold)<=value<=1
        hand=raw['observations'].get('wrist_'+str(pair[0]).lower(),{}) if pair[1]=='coupling' else None
        hand_visible=hand is None or hand.get('status')=='OBSERVED' and usable_confidence(hand.get('confidence'))
        valid=(expected_observation and allowed_observation and observed_value is not None and hand_visible
            and item.get('status')==visible.get('status')=='OBSERVED' and isinstance(item.get('evidence'),str)
            and bool(item['evidence'].strip()) and isinstance(visible.get('evidence'),str) and bool(visible['evidence'].strip())
            and usable_confidence(confidence)
            and usable_confidence(seen_confidence) and target in catalogue
            and len(values.get(pair,()))==1)
        if not valid:
            _diagnostic(record,'CANDIDATE_NOT_CONFIRMED','사진에서 분명히 확인하지 못한 값은 입력값으로 옮기지 않았어요.',target=target)
            continue
        previous=session['facts'].get(identity)
        if previous and (previous.get('source') in ('USER','AI','SAVED') or previous.get('state') in ('KNOWN','ESTIMATED') and previous.get('value') is not None and previous.get('source') in ('POSE','MOVENET')
                or previous.get('state')=='CONFLICT'):
            if previous.get('value')!=observed_value:
                _diagnostic(record,'EXISTING_INPUT_KEPT','사진 관찰과 다른 기존 입력·측정값을 유지했어요.',target=target,existing_source=previous.get('source'))
            continue
        if previous and previous.get('source')=='VISION' and previous.get('vision_signature')==record['signature']:continue
        value=facts.fact(catalogue[target],observed_value,'VISION',item['evidence'],photo_facts.condition(record['photo_id']))
        if posture:value['state']='ESTIMATED'
        value.update(photo_id=record['photo_id'],view=record['view'],photo_label=record['photo_label'],
            vision_signature=record['signature'],vision_observation=observation,
            vision_proof=copy.deepcopy(item),vision_confidence=confidence,vision_observation_evidence=visible['evidence'],
            **(dict(estimated=True,measurement_method='AI_PHOTO_CATEGORY') if posture else {}))
        session['facts'][identity]=value
    for item in raw['work_candidates']:
        if not isinstance(item,dict) or not isinstance(item.get('target'),str) or not isinstance(item.get('observation'),str):continue
        target=item.get('target');permitted=contract.WORK_FIELDS.get(target)
        keys=(permitted,) if isinstance(permitted,str) else permitted or ()
        observation=item.get('observation');visible=raw['observations'].get(observation,{})
        confidence=item.get('confidence');seen_confidence=visible.get('confidence')
        valid=(target in catalogue and observation in keys and item.get('value')=='YES'
            and item.get('status')==visible.get('status')=='OBSERVED'
            and isinstance(item.get('evidence'),str) and bool(item['evidence'].strip())
            and isinstance(visible.get('evidence'),str) and bool(visible['evidence'].strip()) and confident(confidence) and confident(seen_confidence))
        if not valid:
            _diagnostic(record,'WORK_FEATURE_NOT_CONFIRMED','사진에서 분명히 확인한 작업 특징만 입력에 반영해요.',target=target)
            continue
        identity=intake_contract.key(target);previous=session['facts'].get(identity)
        if previous:
            if previous.get('source') in ('USER','AI','SAVED','POSE','MOVENET') or previous.get('state')=='CONFLICT':continue
            if previous.get('source')=='VISION' and previous.get('vision_signature') in {r['signature'] for r in session['photo_vision']['photos']}:continue
        value=facts.fact(catalogue[target],'YES','VISION',item['evidence'])
        value.update(photo_id=record['photo_id'],view=record['view'],photo_label=record['photo_label'],
            vision_signature=record['signature'],vision_observation=observation,vision_proof=copy.deepcopy(item),vision_confidence=confidence)
        session['facts'][identity]=value

def _request(job,settings):
    record=copy.deepcopy(job['descriptor']);record.update(request_id=uuid4().hex,requested_at=now(),
        encoded_sha256=None,summary='',observations={},connection=None,diagnostics=[],status='ERROR')
    try:
        metadata,data_url=images.prepare(job['photo']['file_path'],contract.policy())
        record.update(image=metadata,encoded_sha256=metadata['encoded_sha256'])
        if metadata['source_sha256']!=record['source_sha256']:
            reason='STALE_PHOTO';raw=None
        else:
            context=dict(photo_id=record['photo_id'],photo_view=record['view'],photo_label=record['photo_label'],
                declared_context=record['context'],observation_keys=[key for key,_ in contract.CATALOGUE])
            raw,reason=client.observe(data_url,context,settings['gpt_model'],os.environ.get('OPENAI_API_KEY'),settings)
    except (OSError,ValueError):raw=None;reason='IMAGE_UNREADABLE'
    record['completed_at']=now();record['raw_response']=_safe_json(raw)
    if record['raw_response']!=raw:
        _diagnostic(record,'INVALID_NUMERIC_RESPONSE','AI 응답의 유효하지 않은 숫자를 입력값으로 쓰지 않고 진단에 보관했어요.')
    if raw is not None and reason is None and contract.valid(raw):
        record.update(status='OBSERVED' if any(item['status']=='OBSERVED' for item in raw['observations'].values()) else 'UNCERTAIN',
            summary=raw['summary'],observations=copy.deepcopy(raw['observations']),connection=copy.deepcopy(raw.get('_connection')))
    else:
        record['reason']=ERROR_MESSAGES.get(reason,'사진 관찰을 완료하지 못했어요. 기존 입력을 보존했으니 다시 정리해 주세요.')
        _diagnostic(record,reason or 'INVALID_STRUCTURED_CONTENT',record['reason'])
    return record

def request_turn(ctx,task,session,preview):
    """Request uncached observations without writing task/session state."""
    settings=ai_config.values(ctx.settings())
    initial_signature=session.get('photo_signature')
    if not settings['gpt_enabled'] or not settings.get('gpt_model') or not session.get('views'):
        return task,session,preview,initial_signature,[]
    with ctx.db_lock:
        current=ctx.require('task',task['task_id'])
        if current['created_at']!=task['created_at']:raise LookupError(ERROR_MESSAGES['TASK_REPLACED'])
        photos={photo['photo_id']:photo for photo in ctx.store('list_photos',task['task_id'])}
    refresh(task,session,settings,preview,photos)
    cached={record['signature'] for record in session['photo_vision']['photos'] if record['status'] in ('OBSERVED','UNCERTAIN')}
    jobs=[dict(descriptor=item,photo=photos[item['photo_id']]) for item in _descriptors(task,session,settings) if item['signature'] not in cached and item['photo_id'] in photos]
    records=[]
    with ThreadPoolExecutor(max_workers=contract.policy()['parallelism']) as executor:
        pending=[executor.submit(_request,job,settings) for job in jobs]
        for future in as_completed(pending):records.append(future.result())
    return task,session,preview,initial_signature,records

def reconcile_turn(ctx,task,session,preview,initial_signature,records,prepare,save,expected_input_revision=None):
    """Apply completed observations only after checking the latest task/photo owner."""
    input_changed=False
    expected_revision=expected_input_revision
    for record in records:
        with ctx.db_lock:
            try:current=ctx.require('task',task['task_id'])
            except ValueError:return task,session,preview,True,True
            if current['created_at']!=task['created_at']:raise LookupError(ERROR_MESSAGES['TASK_REPLACED'])
            if expected_revision is not None and current['input_revision']!=expected_revision:
                input_changed=True
            current,latest,current_preview=prepare(ctx,task['task_id'])
            desired={item['signature'] for item in _descriptors(current,latest,ctx.settings())}
            state=latest['photo_vision']
            if record['signature'] not in desired:
                record['status']='STALE';record['reason']=ERROR_MESSAGES['STALE_PHOTO']
                _diagnostic(record,'STALE_PHOTO',record['reason']);state['history'].append(record)
            else:
                previous=next((item for item in state['photos'] if item['signature']==record['signature']),None)
                if previous and previous['status'] in ('OBSERVED','UNCERTAIN'):
                    _diagnostic(record,'ALREADY_OBSERVED','같은 사진에서 먼저 저장된 관찰을 유지했어요.')
                    state['history'].append(record)
                else:
                    if previous:state['history'].append(copy.deepcopy(previous))
                    state['photos']=[item for item in state['photos'] if item['signature']!=record['signature']]+[record]
                    _merge_candidates(latest,record)
            saved,ok=save(ctx,current,latest,current_preview)
            if not ok:raise RuntimeError('사진 관찰을 현재 작업에 저장하지 못했어요.')
            expected_revision=saved['input_revision']
            task,session,preview=saved,latest,current_preview
    return task,session,preview,session.get('photo_signature')!=initial_signature,input_changed

def observe_turn(ctx,task,session,preview,prepare,save):
    """Explicit planning only; every completed response is reconciled without a TTL."""
    request=request_turn(ctx,task,session,preview)
    task,session,preview,stale,_=reconcile_turn(ctx,*request,prepare,save,task['input_revision'])
    return task,session,preview,stale
