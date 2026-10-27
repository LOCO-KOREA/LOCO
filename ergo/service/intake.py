"""Persistent adaptive intake orchestration. The model never writes task DTOs directly."""
import copy
import hashlib
import json
import os
import time
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4
from pathlib import Path
from ergo.intake import contract, facts, planner
from ergo.intake import history as receipts
from ergo.intake import source_coverage, photo_facts, input_links
from ergo.gpt import client
from ergo import ai_config
from ergo import pose_contract
from ergo import photo_identity
from ergo.pose import engine as pose_engine
from ergo.engine.task_defaults import now
from .quick import handle_quick_preview
from . import photo_vision


FORM_ONLY = ('suggestion', 'checklist')


def _for_model(rows):
    """Hints for the form stay on the form: the model gets the questions, not another photo's reading."""
    return [{name: value for name, value in row.items() if name not in FORM_ONLY} for row in rows]


def _prepare(ctx, task_id, requested_views=None):
    with ctx.db_lock:
        task=ctx.require('task',task_id)
        session=copy.deepcopy(task['conditions'].get(contract.SESSION_KEY) or {})
        session.setdefault('version',contract.VERSION); session.setdefault('facts',{}); session.setdefault('messages',[])
        photos={p['photo_id']:p for p in ctx.store('list_photos',task_id)}
        views=requested_views if requested_views is not None else {view:identity for view,identity in session.get('views',{}).items() if identity in photos}
        if any(identity not in photos for identity in views.values()): raise ValueError('이 작업에 등록된 사진을 선택하세요.')
        signatures=[]
        for view,identity in sorted(views.items()):
            photo=photos[identity]
            try: digest=hashlib.sha256(Path(photo['file_path']).read_bytes()).hexdigest()
            except OSError: digest='unreadable'
            signatures.append([view,identity,digest,photo_identity.identity(photo)])
        settings=ctx.settings()['analysis']
    photo_signature=json.dumps(signatures,ensure_ascii=False,sort_keys=True)
    fingerprint=hashlib.sha256((photo_signature+json.dumps(dict(settings=settings,model=pose_engine.fingerprint(settings['pose_model'])),sort_keys=True)).encode()).hexdigest()
    current_facts=photo_facts.bind_aliases(session['facts'],session.get('views') or views)
    current_facts=photo_facts.bind_aliases(current_facts,views)
    catalogue={f['target']:f for f in contract.fields()}
    invalidated=set()
    if session.get('photo_signature') and session['photo_signature']!=photo_signature:
        old_views=session.get('views',{});old_signatures=json.loads(session['photo_signature'])
        new_hashes={entry[1]:(entry[2],entry[3]) for entry in signatures}
        old_hashes={entry[1]:(entry[2],entry[3] if len(entry)>3 else
            new_hashes[entry[1]][1] if entry[1] in new_hashes and new_hashes[entry[1]][1].startswith(photo_identity.LEGACY_PREFIX) else None)
            for entry in old_signatures}
        changed={identity for identity in set(old_hashes)|set(new_hashes) if old_hashes.get(identity)!=new_hashes.get(identity)}
        old_primary=next((old_views[view] for view in contract.PHOTO_VIEWS if view in old_views),None)
        primary=next((views[view] for view in contract.PHOTO_VIEWS if view in views),None)
        for identity,item in current_facts.items():
            destination=catalogue.get(item['target'],{}).get('destination',{});kind=destination.get('type')
            if kind=='manual':
                owner=photo_facts.photo_id(item,old_views)
                if owner in views.values() and owner in changed:invalidated.add(identity)
            elif kind=='view':
                view=destination['view']
                if old_views.get(view)!=views.get(view) or views.get(view) in changed:invalidated.add(identity)
            elif kind in ('context','load','load_kg','load_link') and (old_primary!=primary or primary in changed):invalidated.add(identity)
    elif session.get('fingerprint') and session['fingerprint']!=fingerprint:
        invalidated={k for k,f in current_facts.items() if f['source'] in pose_contract.PHOTO_SOURCES}
    for identity in invalidated:
        session.setdefault('invalidated_photo_facts',{})[identity+'@'+str(session.get('fingerprint',''))]=copy.deepcopy(current_facts[identity])
        current_facts[identity]=dict(current_facts[identity],value=None,state='UNKNOWN',source='POSE',quote='사진 또는 측정 설정이 바뀌어 다시 확인',conflict=None,reask=True)
    actual=facts.read_values(task)
    externally_changed=session.get('projected_revision') is not None and session['projected_revision']!=task['input_revision']
    for identity,item in actual.items():
        if identity in invalidated: continue
        if identity not in current_facts and identity in session.get('applied',{}) and session['applied'][identity]==item['value']:
            continue  # A projected alias is not a newly entered fact; reads must remain stable.
        if identity not in current_facts or externally_changed and current_facts[identity]['value']!=item['value']:
            item['source']='USER' if externally_changed else 'SAVED'; current_facts[identity]=item
    if externally_changed:
        for identity,old_value in session.get('applied',{}).items():
            if identity in invalidated: continue
            if identity not in actual and identity in current_facts:
                current_facts[identity]=dict(current_facts[identity],value=None,state='UNKNOWN',source='USER',quote='편집 화면에서 비움')
    cache=ctx.intake_previews.get(task_id)
    if cache and cache[0]==fingerprint: preview=copy.deepcopy(cache[1])
    else:
        preview=handle_quick_preview(ctx,'quick_preview',dict(task_id=task_id,views=views)) if views else dict(views={},measured=[],front=[],signals={},score=None,questions=[],diagnostics=[])
        ctx.intake_previews[task_id]=(fingerprint,copy.deepcopy(preview))
    session.update(facts=current_facts,views=views,fingerprint=fingerprint,photo_signature=photo_signature,photo_observations=photo_facts.snapshot(preview,views))
    photo_vision.refresh(task,session,ctx.settings(),preview,photos)
    session['facts']=facts.add_photo_facts(session['facts'],preview,views)
    selected=ai_config.values(ctx.settings())
    signature={key:selected[key] for key in ai_config.KEYS}
    if session.get('ai_settings')!=signature:
        session.pop('last_ai',None)
        session['ai_settings']=signature
    return task,session,preview


def _save(ctx, task, session, preview):
    with ctx.db_lock:
        current=ctx.require('task',task['task_id'])
        if current['input_revision']!=task['input_revision'] or current['created_at']!=task['created_at']: return current,False
        photo_vision.apply_context(session)
        session['facts']=photo_facts.bind_aliases(session['facts'],session['views'])
        session['facts']=input_links.synchronize(session)
        projected=facts.project(current,session['facts'],session['views'],preview)
        session['applied']={k:f['value'] for k,f in facts.read_values(projected).items()}
        projected['conditions'][contract.SESSION_KEY]=copy.deepcopy(session)
        incoming=ctx.task_input(projected)
        if incoming==ctx.task_input(current): return current,True
        session['projected_revision']=current['input_revision']+1
        projected['conditions'][contract.SESSION_KEY]=copy.deepcopy(session)
        ctx.validate_task_input_shape(ctx.task_input(projected))
        # Validate ownership and capture first, then apply this turn's values to the reconciled rows.
        reconciled=copy.deepcopy(current)
        ctx.reconcile_capture(reconciled,projected['capture'])
        reconciled.update(ctx.task_input(projected))
        return ctx.save_task(reconciled),True


def _response(task,session,preview,*,reason=None,proposed=(),dropped=()):
    assessment=planner.assess(task,session['facts'],session['views'])
    suggestions=proposed or session.get('suggestions',[])
    questions=[planner.with_answer_questions(planner.with_paired_question(question,assessment['candidates']),assessment['candidates'],session['facts']) for question in planner.choose(assessment['candidates'],suggestions)]
    catalogue={f['target']:f for f in contract.fields()}
    rows=[dict(f,identity=identity,label=(f.get('photo_label','')+' · ' if f['target'].startswith('manual.') and f.get('photo_label') else '')+catalogue[f['target']]['label'],unit=catalogue[f['target']]['unit'])
          for identity,f in session['facts'].items() if f['target'] in catalogue]
    return dict(task=task,contract=contract.public_contract(),facts=rows,questions=questions,
        form_fields=planner.form_fields(task,session['facts'],session['views'],assessment['candidates']),
        remaining_count=assessment['missing_count'],complete=assessment['complete'],
        progress=planner.progress(task,session['facts'],session['views'],assessment['candidates']),
        judgments=assessment['judgments'],reba=assessment['reba'],preview=preview,photo_vision=photo_vision.public(session),
        reason=reason,dropped=list(dropped),diagnostics=receipts.diagnostics(session),
        history=copy.deepcopy(session.get('turns',[])),messages=session['messages'],
        ai=copy.deepcopy(dict(status=contract.AI_STATES[0],model=None,reason=None) if session.get('local_answers_only') else session.get('last_ai') or dict(status=contract.AI_STATES[0],model=None,reason=None)))


def _reconcile_late(ctx,task,turn,session):
    """Reconcile every late proposal with the current owner; never expire by age."""
    with ctx.db_lock:
        current=ctx.require('task',task['task_id'])
        if current['created_at']==task['created_at']:
            current,latest,preview=_prepare(ctx,task['task_id'])
            message=next((m for m in session['messages'] if m.get('message_id')==turn['message_id']),None)
            if message and not any(m.get('message_id')==turn['message_id'] for m in latest['messages']):latest['messages'].append(copy.deepcopy(message))
            reconciled=copy.deepcopy(turn)
            reconciled['status']='RECONCILED'
            if reconciled['decisions']:reconciled.setdefault('decision_history',[]).append(copy.deepcopy(reconciled['decisions']))
            reconciled['decisions']=[d for d in reconciled['decisions'] if d['outcome']=='USER_SAVED']
            catalogue={field['target']:field for field in contract.fields()}
            focus=[dict(catalogue[q['target']],condition=q['condition']) for q in turn['focus'] if q['target'] in catalogue]
            dropped=[]
            for index,request in enumerate(reconciled['requests']):
                if request['phase'] in ('EXTRACT_AND_PLAN','FOLLOWUP'):
                    outcomes=[]
                    latest['facts'],dropped=facts.merge_model(latest['facts'],request['answers'],(message or {}).get('text',''),focus=focus,
                        prior_texts=[m['text'] for m in latest['messages'] if m.get('text')],outcomes=outcomes,reconcile=True,preserve_conflicts=request['phase']=='FOLLOWUP',
                        protect_photo_context=source_coverage.photo_changed(request.get('context',{}),session,latest))
                    receipts.record_decisions(latest,reconciled,outcomes,index)
            turns=latest.setdefault('turns',[])
            found=next((i for i,t in enumerate(turns) if t['turn_id']==turn['turn_id']),None)
            if found is None:turns.append(reconciled)
            else:turns[found]=reconciled
            saved,ok=_save(ctx,current,latest,preview)
            if ok:return _response(saved,latest,preview,reason='INPUT_CHANGED',dropped=dropped)
    return handle_intake_session(ctx,contract.METHODS['session'],dict(task_id=task['task_id'])) | dict(reason='INPUT_CHANGED')


def handle_intake_session(ctx,method,p):
    if method==contract.METHODS['contract']: return contract.public_contract()
    task,session,preview=_prepare(ctx,p['task_id'],p.get('views'))
    saved,ok=_save(ctx,task,session,preview)
    if not ok: return handle_intake_session(ctx,method,dict(task_id=p['task_id']))
    return _response(saved,session,preview)


def _resume_coverage(ctx,task,turn,session):
    response=_reconcile_late(ctx,task,turn,session)
    if response['task']['created_at']!=task['created_at']:return None,response
    resumed=copy.deepcopy(response['task']['conditions'].get(contract.SESSION_KEY) or {})
    saved_turn=next((item for item in resumed.get('turns',[]) if item['turn_id']==turn['turn_id']),None)
    return (response['task'],resumed,response['preview'],saved_turn) if saved_turn else None,response


def handle_intake_turn(ctx,method,p):
    task,session,preview=_prepare(ctx,p['task_id'])
    if p.get('task_created_at',task['created_at'])!=task['created_at']:
        return _response(task,session,preview,reason='INPUT_CHANGED')
    stale_client=p.get('expected_revision',task['input_revision'])!=task['input_revision']
    if stale_client and (p.get('answers') or not p.get('plan',True)):
        return _response(task,session,preview,reason='INPUT_CHANGED')
    focus=planner.choose(planner.assess(facts.project(task,session['facts'],session['views'],preview),session['facts'],session['views'])['candidates'],session.get('suggestions',[]))
    by_target={f['target']:f for f in contract.fields()}
    if p.get('focus'):
        focus=[dict(by_target[q['target']],condition=q.get('condition') or contract.POLICY['default_condition']) for q in p['focus'] if isinstance(q,dict) and q.get('target') in by_target]
    session['facts']=facts.apply_answers(session['facts'],p.get('answers',[]),focus,photo_views=session['views'])
    text=p.get('text','').strip()
    if text and contract.key('task_name') not in session['facts'] and task['task_name'] in ('','사진 분석 작업'):
        title=facts.initial_title(text)
        if title: session['facts'][contract.key('task_name')]=facts.fact(by_target['task_name'],title,'SAVED',title)
    message=dict(message_id=uuid4().hex,text=text,answers=p.get('answers',[]),source_photo_scope=source_coverage.photo_scope(session,preview)) if text or p.get('answers') else None
    if message:session['messages'].append(message)
    turn=receipts.begin(session,message,task,p.get('answers',[]),focus)
    if stale_client:turn['rebased_from_revision']=p.get('expected_revision')
    local_answers_only = bool(p.get('plan', True) and p.get('answers') and not text)
    if p.get('plan', True):
        if local_answers_only:
            session['local_answers_only'] = True
            session['suggestions'] = []
        else:
            session.pop('local_answers_only', None)
    if p.get('plan',True) and not local_answers_only:turn['status']='REQUESTING'
    # Direct edits survive even if the subsequent model request fails or times out.
    task,ok=_save(ctx,task,session,preview)
    if not ok:
        if not p.get('answers') and p.get('plan',True):return handle_intake_turn(ctx,method,p)
        return handle_intake_session(ctx,method,dict(task_id=p['task_id'])) | dict(reason='INPUT_CHANGED')
    if not p.get('plan',True) or local_answers_only: return _response(task,session,preview)
    reason=None; raw=None
    settings=ctx.settings()
    started=time.monotonic()
    source_scope=source_coverage.photo_scope(session,preview)
    original_created_at=task['created_at']
    ai_enabled=settings['gpt_enabled'] and bool(settings.get('gpt_model'))

    def intake_payload(assessment,observations):
        return dict(phase='EXTRACT_AND_PLAN',text=text,known=source_coverage.known_values(session),source_photo_scope=copy.deepcopy(source_scope),
            known_visual_observations=observations,
            visual_observation_policy='이미 사진에서 확인한 자세는 다시 묻지 마세요. 관찰은 사진별로만 적용하고 사용자 인용문으로 쓰지 마세요. 무게·시간·횟수는 사진에서 만들지 마세요.',
            targets=_for_model(contract.fields()),missing=_for_model(assessment['candidates']),asked=_for_model(focus),
            question_limit=contract.POLICY['question_limit'],
            prior_user_text=receipts.context(session,message['message_id'] if message else None)['texts'])

    if ai_enabled and text:
        payload=intake_payload(planner.assess(task,session['facts'],session['views']),photo_vision.known(session))
        with ThreadPoolExecutor(max_workers=1,thread_name_prefix='loco-intake-text') as executor:
            response=executor.submit(client.adaptive_intake,payload,contract.response_schema(),settings['gpt_model'],
                                    os.environ.get('OPENAI_API_KEY'),settings)
            # Photo requests are read-only here; reconcile their results after both APIs finish.
            photo_request=photo_vision.request_turn(ctx,task,session,preview)
            # Keep both API calls overlapped, but never let a photo-result save race a user's edit.
            raw,reason=response.result()
            with ctx.db_lock:
                current=ctx.require('task',task['task_id'])
                input_changed_during_requests=current['input_revision']!=task['input_revision']
            task,session,preview,photo_stale,input_changed_during_reconcile=photo_vision.reconcile_turn(
                ctx,*photo_request,_prepare,_save,task['input_revision'])
            input_changed_during_requests=input_changed_during_requests or input_changed_during_reconcile
    else:
        input_changed_during_requests=False
        task,session,preview,photo_stale=photo_vision.observe_turn(ctx,task,session,preview,_prepare,_save)

    if task['created_at']!=original_created_at:return handle_intake_session(ctx,contract.METHODS['session'],dict(task_id=task['task_id'])) | dict(reason='INPUT_CHANGED')
    saved_turn=next((item for item in session.get('turns',[]) if item['turn_id']==turn['turn_id']),None)
    if saved_turn is None:return _response(task,session,preview,reason='INPUT_CHANGED')
    turn=saved_turn
    if message:message=next((item for item in session['messages'] if item.get('message_id')==message['message_id']),message)
    stale_client=stale_client or photo_stale or input_changed_during_requests
    assessment=planner.assess(task,session['facts'],session['views'])
    source_context=receipts.context(session,message['message_id'] if message else None)
    source_context['source_photo_scope']=copy.deepcopy(source_scope)
    prior_texts=[m['text'] for m in session['messages'] if m is not message and m.get('text')]
    if ai_enabled and not text:
        payload=intake_payload(assessment,photo_vision.known(session))
        raw,reason=client.adaptive_intake(payload,contract.response_schema(),settings['gpt_model'],os.environ.get('OPENAI_API_KEY'),settings)
    elif not ai_enabled: reason='DISABLED'
    session['last_ai']=dict(status=contract.AI_STATES[1] if isinstance(raw,dict) and reason is None else contract.AI_STATES[2],
        model=(raw or {}).get('_connection',{}).get('model') or settings.get('gpt_model'),reason=reason,observed_at=now(),elapsed_ms=round((time.monotonic()-started)*1000),
        reasoning_effort=(raw or {}).get('_connection',{}).get('reasoning_effort'),requested_reasoning_effort=settings['gpt_reasoning_effort'],
        response_id=(raw or {}).get('_connection',{}).get('response_id'))
    receipts.request(turn,'EXTRACT_AND_PLAN',raw,reason,session['last_ai'],source_context)
    reconciled=False
    with ctx.db_lock:
        latest=ctx.require('task',task['task_id'])
        if input_changed_during_requests or latest['input_revision']!=task['input_revision'] or latest['created_at']!=task['created_at']:
            if not text or not settings['gpt_enabled'] or not settings.get('gpt_model'):return _reconcile_late(ctx,task,turn,session)
            resumed,response=_resume_coverage(ctx,task,turn,session)
            if resumed is None:return response
            task,session,preview,turn=resumed
            reconciled=True
    dropped=[]
    if isinstance(raw,dict) and not reconciled:
        outcomes=[]
        session['facts'],dropped=facts.merge_model(session['facts'],raw.get('answers'),text,focus=focus,
            prior_texts=prior_texts,outcomes=outcomes,reconcile=stale_client,protect_photo_context=stale_client)
        receipts.record_decisions(session,turn,outcomes)
        session['suggestions']=raw.get('questions',[])
    if not reconciled:session['last_dropped']=dropped
    session['facts']=input_links.synchronize(session)
    projected=facts.project(task,session['facts'],session['views'],preview)
    assessment=planner.assess(projected,session['facts'],session['views'])
    admissible={q['identity'] for q in assessment['candidates']}
    has_ai_question=any(contract.key(q.get('target',''),q.get('condition')) in admissible for q in session.get('suggestions',[]) if isinstance(q,dict))
    # A valid next question is not proof that every explicit source fact was saved.
    # Each new natural statement gets one source check, including a failed extraction.
    # Blank manual retries retain their existing question-planning behavior.
    coverage=bool(text and settings['gpt_enabled'] and settings.get('gpt_model') and contract.POLICY['source_coverage_passes'])
    if coverage or isinstance(raw,dict) and assessment['candidates'] and not has_ai_question:
        saved,ok=_save(ctx,task,session,preview)
        if not ok:
            resumed,response=_resume_coverage(ctx,task,turn,session)
            if resumed is None:return response
            task,session,preview,turn=resumed;reconciled=True
            assessment=planner.assess(task,session['facts'],session['views'])
        else:task=saved
        followup_context=receipts.context(session)
        followup_context['source_photo_scope']=copy.deepcopy(source_scope)
        followup_payload=source_coverage.payload(payload,session,preview,turn,followup_context,source_scope,_for_model(assessment['candidates']))
        followup_payload['known_visual_observations']=photo_vision.known(session)
        if not coverage:followup_payload.update(text='',purpose='QUESTION_PLANNING')
        session.pop('local_answers_only',None)
        followup,reason=client.adaptive_intake(followup_payload,contract.response_schema(),settings['gpt_model'],os.environ.get('OPENAI_API_KEY'),settings)
        session.setdefault('last_ai',dict(model=settings.get('gpt_model'),requested_reasoning_effort=settings['gpt_reasoning_effort']))
        session['last_ai'].update(status=contract.AI_STATES[1] if isinstance(followup,dict) and reason is None else contract.AI_STATES[2],
            model=(followup or {}).get('_connection',{}).get('model') or settings.get('gpt_model'),
            reasoning_effort=(followup or {}).get('_connection',{}).get('reasoning_effort'),
            reason=reason,observed_at=now(),elapsed_ms=round((time.monotonic()-started)*1000),
            response_id=(followup or {}).get('_connection',{}).get('response_id'))
        receipts.request(turn,'FOLLOWUP',followup,reason,session['last_ai'],followup_context)
        if isinstance(followup,dict):
            outcomes=[]
            session['facts'],additional=facts.merge_model(session['facts'],followup.get('answers'),text,focus=focus,
                prior_texts=prior_texts,outcomes=outcomes,preserve_conflicts=True,reconcile=stale_client or reconciled,
                protect_photo_context=stale_client or source_coverage.photo_changed(followup_context,session,session))
            receipts.record_decisions(session,turn,outcomes,len(turn['requests'])-1)
            dropped.extend(additional);session['last_dropped']=dropped
            session['suggestions']=followup.get('questions',[])
            session['facts']=input_links.synchronize(session)
            projected=facts.project(task,session['facts'],session['views'],preview)
            assessment=planner.assess(projected,session['facts'],session['views'])
    session['suggestions']=[dict(target=q['target'],condition=q['condition'],text=q['text'],reason=q['reason']) for q in planner.choose(assessment['candidates'],session.get('suggestions',[]))]
    turn['status']='ERROR' if reason else 'RECONCILED' if reconciled else 'COMPLETE'
    saved,ok=_save(ctx,task,session,preview)
    if not ok: return _reconcile_late(ctx,task,turn,session)
    if any(item['reason']=='PHOTO_CONTEXT_CONFIRMATION_REQUIRED' for item in dropped):reason='INPUT_CHANGED'
    return _response(saved,session,preview,reason=reason or ('INPUT_CHANGED' if reconciled else None),proposed=session['suggestions'],dropped=dropped)
