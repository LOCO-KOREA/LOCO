"""LOCO 2.0 analysis jobs service. Dependencies are supplied by Runtime."""
import copy
import sys
import threading
import traceback
from ergo.engine.task_defaults import now, evidence, diagnostic
from ergo.engine.reba_scoring import calculate_reba
from ergo.engine.pose_tags import calculate_tags
from ergo.engine import burden_rules as burden
from ergo.pose import engine as pose

def new_analysis(ctx, task, modules):
    with ctx.db_lock:
        return ctx._new_analysis(task, modules)

def _new_analysis(ctx, task, modules):
    ctx.settings()
    task = ctx.require('task', task['task_id'])
    snap = ctx.snapshot(task)
    old = ctx.store('get_analysis', task['latest_analysis_id']) if task['latest_analysis_id'] else None
    result = dict(module_states={key: 'RUNNING' if key in modules else 'NOT_REQUESTED' for key in ['pose', 'tags', 'reba', 'judgment']}, pose=None, slot_tags=[], tags=None, reba=None, judgment=None, ai=[], notes=[])
    if old and old.get('snapshot', {}).get('schema_version') == snap.get('schema_version') and (old['status'] != 'RUNNING') and (modules != ['pose', 'tags', 'reba', 'judgment']):
        previous = old['snapshot']

        def same(keys):
            return all((previous.get(k) == snap.get(k) for k in keys))
        pose_same = ctx.pose_inputs(previous) == ctx.pose_inputs(snap)
        pose_source = old if pose_same and old['pose'] is not None else None
        if pose_source is None:
            for candidate in reversed(ctx.store('list_analyses', task['task_id'])):
                if candidate['pose'] is not None and candidate['status'] == 'FINISHED' and (ctx.pose_inputs(candidate['snapshot']) == ctx.pose_inputs(snap)):
                    pose_source = candidate
                    break
        if pose_source is not None:
            result['pose'] = copy.deepcopy(pose_source['pose'])
            tag_fields = {'neck_twisted', 'trunk_twisted', 'hand_above_head', 'elbow_above_shoulder', 'elbow_behind_trunk', 'squat', 'kneel'}

            def tag_manual(data):
                return sorted(((m['slot_no'], m['photo_id'], m['scope'], m['field'], str(m['value'])) for m in data['manual'] if m['scope'] == 'COMMON' and m['field'] in tag_fields))
            if tag_manual(pose_source['snapshot']) == tag_manual(snap) and pose_source['snapshot']['settings']['posture_profile'] == snap['settings']['posture_profile']:
                result['slot_tags'] = copy.deepcopy(pose_source['slot_tags'])
                result['tags'] = copy.deepcopy(pose_source['tags'])
        if pose_same and same(['manual', 'capture', 'conditions']) and (previous['settings']['reba_rule'] == snap['settings']['reba_rule']):
            result['reba'] = old['reba']
        if same(['conditions', 'legal']) and previous['settings']['burden_rule'] == snap['settings']['burden_rule']:
            result['judgment'] = copy.deepcopy(old['judgment'])
            if result['judgment']:
                for j in result['judgment']['judgments']:
                    j['investigator'] = dict(criterion_no=j['criterion_no'], status=None, reason=None, evidence=evidence(), reviewer=None, reviewed_at=None)
                    j['effective_status'] = j['computed_status']
        for module, key in [('pose', 'pose'), ('reba', 'reba'), ('judgment', 'judgment')]:
            if module not in modules and (snap.get('analysis_scope') or {}).get(module) and (result[key] is None):
                result['notes'].append(diagnostic('RECALCULATE_REQUIRED', module + ' 결과가 없거나 관련 입력이 달라 재계산이 필요합니다'))
    for module in ['pose', 'tags', 'reba', 'judgment']:
        if module in modules:
            continue
        if not (snap.get('analysis_scope') or {}).get(module):
            result['module_states'][module] = 'NOT_REQUESTED'
        elif result.get(module) is None:
            result['module_states'][module] = 'NOT_CALCULATED'
        else:
            source = pose_source if module in ('pose', 'tags') and 'pose_source' in locals() else old
            result['module_states'][module] = (source or {}).get('module_states', {}).get(module, 'INCOMPLETE')
    targets = [s for s in snap['capture']['slots'] if s.get('analysis_target') and s.get('photo_id') is not None]
    if not modules:
        raise ValueError('분석 범위를 하나 이상 선택하세요')
    if not targets and 'tags' in modules:
        result['notes'].append(diagnostic('NO_ANALYSIS_TARGET', '자세 기술태그를 계산할 분석대상 사진이 없습니다'))
    if not targets and 'reba' in modules:
        result['notes'].append(diagnostic('NO_ANALYSIS_TARGET', 'REBA를 계산할 분석대상 사진이 없습니다'))
    if 'pose' in modules:
        result['pose'] = dict(status='RUNNING' if targets else 'FAILED', valid_count=0, total_slot_count=len(targets), terminal_error=None if targets else 'NO_ANALYSIS_TARGET', slots=[dict(slot_no=s['slot_no'], photo_id=s['photo_id'], status='PENDING', diagnostics=[], points=[], angles=[]) for s in targets])
        if not targets:
            result['module_states']['pose'] = 'FAILED'
    ids = [s['photo_id'] for s in targets]
    if len(ids) != len(set(ids)):
        result['notes'].append(diagnostic('DUPLICATE_PHOTO', '같은 사진이 여러 분석대상 슬롯에 배정되었습니다.'))
    identity = ctx.store('create_analysis', task['task_id'], task['input_revision'], 'RUNNING', snap, now(), result=result)
    ctx.analysis_token(identity, renew=True)
    return ctx.require('analysis', identity)

def _fail_analysis(ctx, a, error, token, *, code='ANALYSIS_ERROR'):
    """Fail unfinished modules while keeping completed or reused results."""
    pose_running = a.get('module_states', {}).get('pose') == 'RUNNING'
    a['status'] = 'FAILED'
    a['finished_at'] = now()
    a['notes'].append(diagnostic(code, str(error)))
    for key, state in a.get('module_states', {}).items():
        if state == 'RUNNING':
            a['module_states'][key] = 'FAILED'
    if pose_running and a['pose']:
        a['pose']['status'] = 'FAILED'
        a['pose']['terminal_error'] = str(error)
        for slot in a['pose']['slots']:
            if slot['status'] == 'PENDING':
                slot.update(status='NOT_PROCESSED', diagnostics=[diagnostic(code, str(error))])
    return ctx.persist_analysis(a, token=token)


def _release_cancel(ctx, identity, cancel):
    with ctx.db_lock:
        if ctx.cancels.get(identity) is cancel:
            ctx.cancels.pop(identity, None)


def fail_recalculation_start(ctx, a, cancel, token, error):
    try:
        return _fail_analysis(ctx, a, error, token, code='ANALYSIS_START_ERROR')
    finally:
        _release_cancel(ctx, a['analysis_id'], cancel)


def run(ctx, a, modules, cancel, token):
    try:
        with ctx.analysis_lock:
            targets = [s for s in a['snapshot']['capture']['slots'] if s.get('analysis_target') and s.get('photo_id') is not None]
            if 'pose' in modules:
                assigned = [slot['photo_id'] for slot in targets]
                duplicates = {identity for identity in assigned if assigned.count(identity) > 1}
                for i, slot in enumerate(targets):
                    if cancel.is_set():
                        for rest in a['pose']['slots'][i:]:
                            rest.update(status='CANCELED', diagnostics=[diagnostic('CANCELED', '분석이 취소되었습니다')])
                        break
                    a['pose']['slots'][i] = pose.process(slot, a['snapshot'])
                    if slot['photo_id'] in duplicates:
                        a['pose']['slots'][i]['status'] = 'INVALID'
                        a['pose']['slots'][i].setdefault('diagnostics', []).append(diagnostic('DUPLICATE_PHOTO', '같은 사진이 다른 분석대상 행에도 배정되어 별도 표본으로 계산하지 않습니다'))
                    a['pose']['valid_count'] = sum((p['status'] == 'VALID' for p in a['pose']['slots']))
                    ctx.persist_analysis(a, token=token)
                count = a['pose']['valid_count']
                statuses = [p['status'] for p in a['pose']['slots']]
                all_errors = not targets or all((status == 'ERROR' for status in statuses))
                a['pose']['status'] = 'CANCELED' if cancel.is_set() else 'DONE' if count == len(targets) and count else 'FAILED' if all_errors else 'PARTIAL_REVIEW'
                a['module_states']['pose'] = 'CANCELED' if cancel.is_set() else 'COMPLETE' if count == len(targets) and count else 'FAILED' if all_errors else 'INCOMPLETE'
            if cancel.is_set():
                for key in modules:
                    if a['module_states'].get(key) == 'RUNNING':
                        a['module_states'][key] = 'CANCELED'
                a['status'] = 'CANCELED'
                a['finished_at'] = now()
                ctx.persist_analysis(a, token=token)
                return
            if 'tags' in modules:
                tags = calculate_tags(a['snapshot'], a['pose'])
                a['slot_tags'] = tags['slots']
                a['tags'] = tags['summary']
                unique_targets = len({s['photo_id'] for s in targets}) == len(targets)
                a['module_states']['tags'] = 'COMPLETE' if targets and unique_targets and all((x['observed_count'] == len(targets) for x in tags['summary'])) else 'INCOMPLETE'
            if cancel.is_set():
                for key in modules:
                    if a['module_states'].get(key) == 'RUNNING':
                        a['module_states'][key] = 'CANCELED'
                a['status'] = 'CANCELED'
                a['finished_at'] = now()
                ctx.persist_analysis(a, token=token)
                return
            if 'reba' in modules:
                a['reba'] = calculate_reba(a['snapshot'], a['pose'])
                a['module_states']['reba'] = 'COMPLETE' if targets and a['reba']['status'] == 'COMPLETE' else 'INCOMPLETE'
            if cancel.is_set():
                for key in modules:
                    if a['module_states'].get(key) == 'RUNNING':
                        a['module_states'][key] = 'CANCELED'
                a['status'] = 'CANCELED'
                a['finished_at'] = now()
                ctx.persist_analysis(a, token=token)
                return
            if 'judgment' in modules:
                a['judgment'] = burden.calculate(a['snapshot']['conditions'], a['snapshot']['legal'], a['snapshot'].get('schema_version', '1.3'))
                a['module_states']['judgment'] = 'INCOMPLETE' if any((j['computed_status'] in ['NEEDS_INPUT', 'NEEDS_REVIEW'] for j in a['judgment']['judgments'])) else 'COMPLETE'
            a['status'] = 'CANCELED' if cancel.is_set() else 'FINISHED'
            a['finished_at'] = now()
            ctx.persist_analysis(a, token=token)
    except Exception as error:
        traceback.print_exc(file=sys.stderr)
        try:
            _fail_analysis(ctx, a, error, token)
        except Exception:
            traceback.print_exc(file=sys.stderr)
    finally:
        _release_cancel(ctx, a['analysis_id'], cancel)


def handle_start_analysis(ctx, method, p):
    with ctx.db_lock:
        task = ctx.require('task', p['task_id'])
        scope = task.get('analysis_scope') or dict(judgment=True, pose=False, tags=False, reba=False)
        modules = [key for key in ['pose', 'tags', 'reba', 'judgment'] if scope.get(key)]
        a = ctx.new_analysis(task, modules)
        cancel = threading.Event()
        ctx.cancels[a['analysis_id']] = cancel
        token = ctx.analysis_token(a['analysis_id'])
    try:
        threading.Thread(target=ctx.run, args=(a, modules, cancel, token), daemon=True).start()
    except Exception as error:
        fail_recalculation_start(ctx, a, cancel, token, error)
        raise
    return dict(analysis_id=a['analysis_id'], task_id=a['task_id'], status='RUNNING')

def handle_cancel_analysis(ctx, method, p):
    a = ctx.analysis(p['analysis_id'])
    cancel = ctx.cancels.get(a['analysis_id'])
    if cancel:
        cancel.set()
    return dict(analysis_id=a['analysis_id'], task_id=a['task_id'], status=a['status'])

RECALCULATION_METHODS = frozenset({
    'recalculate_reba', 'recalculate_judgments', 'recalculate_tags',
})


def prepare_recalculation(ctx, method, p):
    """Capture inputs before the IPC loop accepts another input write."""
    modules = {'recalculate_reba': ['reba'], 'recalculate_judgments': ['judgment'], 'recalculate_tags': ['tags']}[method]
    with ctx.db_lock:
        task = ctx.require('task', p['task_id'])
        if not task['analysis_scope'].get(modules[0]):
            task['analysis_scope'][modules[0]] = True
            task = ctx.save_task(task)
        a = ctx.new_analysis(task, modules)
        cancel = threading.Event()
        ctx.cancels[a['analysis_id']] = cancel
        token = ctx.analysis_token(a['analysis_id'])
    return a, modules, cancel, token


def finish_recalculation(ctx, a, modules, cancel, token):
    """Save and return only the analysis lifetime captured during preparation."""
    ctx.run(a, modules, cancel, token)
    with ctx.db_lock:
        ctx.require_analysis_token(a['analysis_id'], token)
        return ctx.analysis(a['analysis_id'])


def handle_recalculate_reba(ctx, method, p):
    a, modules, cancel, token = prepare_recalculation(ctx, method, p)
    return finish_recalculation(ctx, a, modules, cancel, token)
