"""LOCO 2.0 analysis records service. Dependencies are supplied by Runtime."""
import copy
from ergo.engine.task_defaults import diagnostic
from ergo.gpt import payload as gpt_payload
from ergo.report import workbook as report
from ergo.pose import engine as pose_engine

def analysis(ctx, identity):
    result = ctx.require('analysis', identity)
    task = ctx.require('task', result['task_id'])
    result['currentness'] = report.currentness(task, result)
    result.setdefault('module_states', dict(pose='NOT_CALCULATED' if result.get('pose') is None else 'COMPLETE' if result['pose'].get('status') == 'DONE' else 'INCOMPLETE', tags='NOT_CALCULATED' if result.get('tags') is None else 'COMPLETE', reba='NOT_CALCULATED' if result.get('reba') is None else 'COMPLETE' if result['reba'].get('status') == 'COMPLETE' else 'INCOMPLETE', judgment='NOT_CALCULATED' if result.get('judgment') is None else 'COMPLETE'))
    try:
        for item in result.get('ai', []):
            try:
                current=gpt_payload.build_numeric_summary(result,item.get('purpose','TASK_EXPLANATION'),provisional_reba=item.get('provisional_reba_input'),analysis_currentness=result['currentness'])
                item['source_current']=result['currentness']=='CURRENT' and item.get('input_summary')==current
            except (TypeError,ValueError):
                item['source_current']=False
    except Exception:
        pass
    return result

def snapshot(ctx, task):
    value=dict(schema_version=task.get('schema_version', '1.3'), task_id=task['task_id'], input_revision=task['input_revision'], task_name=task['task_name'], task_kind=task.get('task_kind'), input_template=task.get('input_template'), worker_count=task.get('worker_count'), conditions=copy.deepcopy(task['conditions']), legal=copy.deepcopy(task['legal']), capture=copy.deepcopy(task['capture']), manual=copy.deepcopy(task['manual']), analysis_scope=copy.deepcopy(task.get('analysis_scope')), legacy_input=copy.deepcopy(task.get('legacy_input')), photos=ctx.store('list_photos', task['task_id']), settings=ctx.settings()['analysis'])
    value['pose_artifact']=pose_engine.fingerprint(value['settings']['pose_model'])
    return value

def persist_analysis(ctx, a, *, token=None):
    """Calculation worker writes calculation fields, never AI or display edits."""

    def update(latest):
        prior = {j['criterion_no']: j for j in (latest.get('judgment') or {}).get('judgments', [])}
        judgment = copy.deepcopy(a.get('judgment'))
        for item in (judgment or {}).get('judgments', []):
            old = prior.get(item['criterion_no'])
            if old:
                item['investigator'] = copy.deepcopy(old['investigator'])
                item['effective_status'] = old['investigator'].get('status') or item['computed_status']
        reba = copy.deepcopy(a.get('reba'))
        old_summary = (latest.get('reba') or {}).get('summary') or {}
        if reba and old_summary.get('selection') == 'MANUAL':
            no = old_summary.get('representative_slot_no')
            if any((s['slot_no'] == no and s['status'] == 'COMPLETE' for s in reba.get('slots', []))):
                reba['summary'].update(representative_slot_no=no, selection='MANUAL')
        for key in ('module_states', 'pose', 'slot_tags', 'tags', 'notes'):
            latest[key] = copy.deepcopy(a[key])
        latest.update(judgment=judgment, reba=reba)
    with ctx.db_lock:
        if token is not None and not ctx.analysis_is_current(a['analysis_id'], token):
            return False
        return ctx.store('update_analysis_result', a['analysis_id'], update, job=(a['status'], a['finished_at']))

def edit_result(ctx, identity, update, *, invalidate_review=False, token=None):
    with ctx.db_lock:
        if token is not None:
            ctx.require_analysis_token(identity, token)
        if not ctx.store('update_analysis_result', identity, update, invalidate_review=invalidate_review):
            raise LookupError(f'analysis {identity}를 찾을 수 없습니다')

def pose_inputs(ctx, snap):
    """Inference and validity dependencies; load observations are excluded."""
    cap = snap['capture']
    assigned = {s['photo_id'] for s in cap['slots'] if s['photo_id'] is not None and s.get('analysis_target', True)}
    slots = []
    for slot in cap['slots']:
        observation = slot.get('observation') or {}
        slots.append((
            slot['slot_no'], slot['photo_id'], slot.get('analysis_target'),
            slot.get('camera_side'), slot.get('forward_direction'),
            slot.get('side_view_verified'),
            observation.get('single_person'), observation.get('full_frame'),
            observation.get('normal_work'),
        ))
    return dict(
        slots=slots,
        photos=sorted(
            (
                p['photo_id'], p['file_path'],
                p.get('width_px'), p.get('height_px'),
            )
            for p in snap['photos']
            if p['photo_id'] in assigned
        ),
        context={
            k: snap['conditions'].get(k)
            for k in ['worker_code', 'method_description', 'work_height_cm']
        },
        model=snap['settings']['pose_model'],artifact=snap.get('pose_artifact'),
    )

def handle_get_analysis(ctx, method, p):
    return ctx.analysis(p['analysis_id'])

def handle_list_analysis_history(ctx, method, p):
    return [ctx.analysis(a['analysis_id']) for a in reversed(ctx.store('list_analyses', p['task_id']))]

def handle_get_task_result(ctx, method, p):
    task = ctx.require('task', p['task_id'])
    a = ctx.analysis(task['latest_analysis_id']) if task['latest_analysis_id'] else None
    ov = report.overview(ctx.export_snapshot(task['survey_id'], []))
    t = next((t for t in ov['tasks'] if t['task_id'] == task['task_id']))
    warnings = [dict(criterion_no=j['criterion_no'], from_='INVESTIGATOR' if j['investigator']['status'] else 'COMPUTED', message='부담작업 해당 후보입니다') for j in (a or {}).get('judgment', {}).get('judgments', []) if j['effective_status'] == 'APPLICABLE'] if a and a.get('judgment') else []
    for w in warnings:
        w['from'] = w.pop('from_')
    return dict(task=task, currentness=t['currentness'], analysis=a, warnings=warnings, review_current=t['state']['review_current'])

def handle_select_representative(ctx, method, p):

    def update(result):
        reba = result.get('reba')
        slot = next((s for s in (reba or {}).get('slots', []) if s['slot_no'] == p['slot_no']), None)
        if slot and slot['status'] == 'COMPLETE':
            reba['summary'].update(representative_slot_no=slot['slot_no'], selection='MANUAL')
        else:
            result.setdefault('notes', []).append(diagnostic('INCOMPLETE_REPRESENTATIVE', '완전 REBA 사진만 점수 대표로 선택할 수 있습니다. 미리보기는 가능합니다.'))
    ctx.edit_result(p['analysis_id'], update)
    return ctx.analysis(p['analysis_id'])

def handle_set_investigator_conclusion(ctx, method, p):
    conclusion = copy.deepcopy(p['conclusion'])
    if conclusion.get('status') not in (None, 'APPLICABLE', 'NOT_APPLICABLE') or type(conclusion.get('criterion_no')) is not int or conclusion['criterion_no'] not in range(1, 12):
        raise ValueError('조사자 결론은 1~11호의 해당/비해당 또는 해제여야 합니다')

    def update(result):
        if result.get('judgment') is None:
            raise LookupError('고시 초안 계산을 먼저 실행하세요')
        j = next((j for j in result['judgment']['judgments'] if j['criterion_no'] == conclusion['criterion_no']))
        j['investigator'] = conclusion
        j['effective_status'] = conclusion['status'] or j['computed_status']
    ctx.edit_result(p['analysis_id'], update, invalidate_review=True)
    return ctx.analysis(p['analysis_id'])
