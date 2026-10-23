"""Persistent adaptive intake orchestration. The model never writes task DTOs directly."""
import copy
import hashlib
import json
import os
import re
import time
from pathlib import Path
from ergo.intake import contract, facts, planner
from ergo.gpt import client
from ergo import ai_config
from ergo.engine.task_defaults import now
from .quick import handle_quick_preview


def _prepare(ctx, task_id, requested_views=None):
    with ctx.db_lock:
        task=ctx.require('task',task_id)
        session=copy.deepcopy(task['conditions'].get(contract.SESSION_KEY) or {})
        session.setdefault('version',contract.VERSION); session.setdefault('facts',{}); session.setdefault('messages',[])
        views=requested_views if requested_views is not None else session.get('views',{})
        photos={p['photo_id']:p for p in ctx.store('list_photos',task_id)}
        if any(identity not in photos for identity in views.values()): raise ValueError('이 작업에 등록된 사진을 선택하세요.')
        signatures=[]
        for view,identity in sorted(views.items()):
            photo=photos[identity]
            try: digest=hashlib.sha256(Path(photo['file_path']).read_bytes()).hexdigest()
            except OSError: digest='unreadable'
            signatures.append([view,identity,digest])
        settings=ctx.settings()['analysis']
    photo_signature=json.dumps(signatures,ensure_ascii=False,sort_keys=True)
    fingerprint=hashlib.sha256((photo_signature+json.dumps(settings,sort_keys=True)).encode()).hexdigest()
    current_facts=session['facts']
    catalogue={f['target']:f for f in contract.fields()}
    invalidated=set()
    if session.get('photo_signature') and session['photo_signature']!=photo_signature:
        photo_kinds=('context','view','manual','load','load_kg','load_link')
        invalidated={k for k,f in current_facts.items() if catalogue.get(f['target'],{}).get('destination',{}).get('type') in photo_kinds}
    elif session.get('fingerprint') and session['fingerprint']!=fingerprint:
        invalidated={k for k,f in current_facts.items() if f['source']=='MOVENET'}
    for identity in invalidated:
        current_facts[identity]=dict(current_facts[identity],value=None,state='UNKNOWN',source='MOVENET',quote='사진 또는 측정 설정이 바뀌어 다시 확인',conflict=None)
    actual=facts.read_values(task)
    externally_changed=session.get('projected_revision') is not None and session['projected_revision']!=task['input_revision']
    for identity,item in actual.items():
        if identity in invalidated: continue
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
    current_facts=facts.add_photo_facts(current_facts,preview,views)
    session.update(facts=current_facts,views=views,fingerprint=fingerprint,photo_signature=photo_signature)
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
    rows=[dict(f,identity=identity,label=catalogue[f['target']]['label'],unit=catalogue[f['target']]['unit'])
          for identity,f in session['facts'].items() if f['target'] in catalogue]
    return dict(task=task,contract=contract.public_contract(),facts=rows,questions=questions,
        remaining_count=assessment['missing_count'],complete=assessment['complete'],
        progress=planner.progress(task,session['facts'],session['views'],assessment['candidates']),
        judgments=assessment['judgments'],reba=assessment['reba'],preview=preview,
        reason=reason,dropped=list(dropped),messages=session['messages'],
        ai=copy.deepcopy(dict(status=contract.AI_STATES[0],model=None,reason=None) if session.get('local_answers_only') else session.get('last_ai') or dict(status=contract.AI_STATES[0],model=None,reason=None)))


def handle_intake_session(ctx,method,p):
    if method==contract.METHODS['contract']: return contract.public_contract()
    task,session,preview=_prepare(ctx,p['task_id'],p.get('views'))
    saved,ok=_save(ctx,task,session,preview)
    if not ok: return handle_intake_session(ctx,method,dict(task_id=p['task_id']))
    return _response(saved,session,preview)


def handle_intake_turn(ctx,method,p):
    task,session,preview=_prepare(ctx,p['task_id'])
    if p.get('task_created_at',task['created_at'])!=task['created_at']:
        return _response(task,session,preview,reason='INPUT_CHANGED')
    if p.get('expected_revision',task['input_revision'])!=task['input_revision']:
        return _response(task,session,preview,reason='INPUT_CHANGED')
    focus=planner.choose(planner.assess(facts.project(task,session['facts'],session['views'],preview),session['facts'],session['views'])['candidates'],session.get('suggestions',[]))
    by_target={f['target']:f for f in contract.fields()}
    if p.get('focus'):
        focus=[dict(by_target[q['target']],condition=q.get('condition') or contract.POLICY['default_condition']) for q in p['focus'] if isinstance(q,dict) and q.get('target') in by_target]
    session['facts']=facts.apply_answers(session['facts'],p.get('answers',[]),focus)
    text=p.get('text','').strip()
    if text and contract.key('task_name') not in session['facts'] and task['task_name'] in ('','사진 분석 작업'):
        title=re.split(r'[.!?。\n]',text,1)[0][:contract.POLICY['auto_title_length']].strip()
        if title: session['facts'][contract.key('task_name')]=facts.fact(by_target['task_name'],title,'SAVED',title)
    if text or p.get('answers'): session['messages'].append(dict(text=text,answers=p.get('answers',[])))
    local_answers_only = bool(p.get('plan', True) and p.get('answers') and not text)
    if p.get('plan', True):
        if local_answers_only:
            session['local_answers_only'] = True
            session['suggestions'] = []
        else:
            session.pop('local_answers_only', None)
    # Direct edits survive even if the subsequent model request fails or times out.
    task,ok=_save(ctx,task,session,preview)
    if not ok: return handle_intake_session(ctx,method,dict(task_id=p['task_id']))
    if not p.get('plan',True) or local_answers_only: return _response(task,session,preview)
    assessment=planner.assess(task,session['facts'],session['views'])
    reason=None; raw=None
    settings=ctx.settings()
    started=time.monotonic()
    history=session['messages'][:-1] if text or p.get('answers') else session['messages']
    prior_texts=[m['text'] for m in history[-contract.POLICY['history_context_turns']:] if m['text']]
    if settings['gpt_enabled'] and settings.get('gpt_model'):
        payload=dict(phase='EXTRACT_AND_PLAN',text=text,known=[dict(target=f['target'],condition=f['condition'],value=f['value'],state=f['state'],source=f['source']) for f in session['facts'].values()],
            targets=contract.fields(),missing=assessment['candidates'],asked=focus,
            question_limit=contract.POLICY['question_limit'],
            prior_user_text=prior_texts)
        raw,reason=client.adaptive_intake(payload,contract.response_schema(),settings['gpt_model'],os.environ.get('OPENAI_API_KEY'),settings)
    else: reason='DISABLED'
    session['last_ai']=dict(status=contract.AI_STATES[1] if isinstance(raw,dict) and reason is None else contract.AI_STATES[2],
        model=(raw or {}).get('_connection',{}).get('model') or settings.get('gpt_model'),reason=reason,observed_at=now(),elapsed_ms=round((time.monotonic()-started)*1000),
        reasoning_effort=(raw or {}).get('_connection',{}).get('reasoning_effort'),requested_reasoning_effort=settings['gpt_reasoning_effort'],
        response_id=(raw or {}).get('_connection',{}).get('response_id'))
    with ctx.db_lock:
        latest=ctx.require('task',task['task_id'])
        if latest['input_revision']!=task['input_revision'] or latest['created_at']!=task['created_at']:
            return handle_intake_session(ctx,method,dict(task_id=p['task_id'])) | dict(reason='INPUT_CHANGED')
    dropped=[]
    if isinstance(raw,dict):
        session['facts'],dropped=facts.merge_model(session['facts'],raw.get('answers'),text,focus=focus,
            prior_texts=prior_texts)
        session['suggestions']=raw.get('questions',[])
    session['last_dropped']=dropped
    projected=facts.project(task,session['facts'],session['views'],preview)
    assessment=planner.assess(projected,session['facts'],session['views'])
    admissible={q['identity'] for q in assessment['candidates']}
    has_ai_question=any(contract.key(q.get('target',''),q.get('condition')) in admissible for q in session.get('suggestions',[]) if isinstance(q,dict))
    # Extraction can reveal a new condition. Save the extracted facts before asking AI
    # to phrase the actual remaining gap; never hold a DB lock during either request.
    if isinstance(raw,dict) and assessment['candidates'] and not has_ai_question:
        task,ok=_save(ctx,task,session,preview)
        if not ok: return handle_intake_session(ctx,method,dict(task_id=p['task_id'])) | dict(reason='INPUT_CHANGED')
        payload.update(phase='FOLLOWUP',text='',known=[dict(target=f['target'],condition=f['condition'],value=f['value'],state=f['state'],source=f['source']) for f in session['facts'].values()],
            missing=assessment['candidates'],asked=[],prior_user_text=[m['text'] for m in session['messages'][-contract.POLICY['history_context_turns']:] if m['text']])
        followup,reason=client.adaptive_intake(payload,contract.response_schema(),settings['gpt_model'],os.environ.get('OPENAI_API_KEY'),settings)
        session['last_ai'].update(status=contract.AI_STATES[1] if isinstance(followup,dict) and reason is None else contract.AI_STATES[2],
            model=(followup or {}).get('_connection',{}).get('model') or settings.get('gpt_model'),
            reasoning_effort=(followup or {}).get('_connection',{}).get('reasoning_effort'),
            reason=reason,observed_at=now(),elapsed_ms=round((time.monotonic()-started)*1000),
            response_id=(followup or {}).get('_connection',{}).get('response_id'))
        if isinstance(followup,dict): session['suggestions']=followup.get('questions',[])
    session['suggestions']=[dict(target=q['target'],condition=q['condition'],text=q['text'],reason=q['reason']) for q in planner.choose(assessment['candidates'],session.get('suggestions',[]))]
    saved,ok=_save(ctx,task,session,preview)
    if not ok: return handle_intake_session(ctx,method,dict(task_id=p['task_id'])) | dict(reason='INPUT_CHANGED')
    return _response(saved,session,preview,reason=reason,proposed=session['suggestions'],dropped=dropped)
