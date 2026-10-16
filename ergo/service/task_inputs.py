"""LOCO 2.0 task inputs service. Dependencies are supplied by Runtime."""
import copy
from ergo.legacy.v13 import upgrade_task
from ergo.engine.task_defaults import now, evidence, task_input as new_task_input, exclusions, EXPOSURE_V2, COMMON, ARM, TAG_FIELDS

def task_input(ctx, task):
    keys = ['schema_version', 'task_kind', 'task_name', 'input_template', 'worker_count', 'conditions', 'legal', 'capture', 'manual', 'analysis_scope', 'legacy_input']
    return {key: copy.deepcopy(task[key]) for key in keys if key in task}

def save_task(ctx, task, *, force=False):
    current = ctx.require('task', task['task_id'])
    if force or ctx.task_input(current) != ctx.task_input(task):
        ctx.store('update_task_input', task['task_id'], ctx.task_input(task), now())
    return ctx.require('task', task['task_id'])

def reconcile_capture(ctx, task, capture_value):
    if not isinstance(capture_value, dict) or capture_value.get('protocol') != 'GENERAL_STILLS_V1' or (not isinstance(capture_value.get('slots'), list)):
        raise ValueError('capture는 GENERAL_STILLS_V1 사진 행 목록이어야 합니다')
    photos = {p['photo_id'] for p in ctx.store('list_photos', task['task_id'])}
    old = {slot['slot_no']: slot for slot in task['capture'].get('slots', [])}
    seen = set()
    new_slots = []
    changed = set()
    for slot in capture_value['slots']:
        if not isinstance(slot, dict):
            raise ValueError('사진 행 형식이 올바르지 않습니다')
        no = slot.get('slot_no')
        photo_id = slot.get('photo_id')
        if isinstance(no, bool) or not isinstance(no, int) or no < 1 or (no in seen):
            raise ValueError('사진 행 번호는 중복 없는 양의 정수여야 합니다')
        if photo_id is not None and (isinstance(photo_id, bool) or not isinstance(photo_id, int) or photo_id not in photos):
            raise ValueError(f'{no}번 행의 사진이 이 작업에 속하지 않습니다')
        if not isinstance(slot.get('analysis_target'), bool):
            raise ValueError(f'{no}번 행의 분석대상은 참/거짓이어야 합니다')
        if slot.get('camera_side') not in (None, 'LEFT', 'RIGHT', 'FRONT', 'OTHER') or slot.get('forward_direction') not in (None, 'SCREEN_RIGHT', 'SCREEN_LEFT'):
            raise ValueError(f'{no}번 행의 카메라 방향 값이 올바르지 않습니다')
        if slot.get('side_view_verified') not in (None, 'YES', 'NO', 'UNKNOWN'):
            raise ValueError(f'{no}번 행의 측면 확인 값이 올바르지 않습니다')
        previous = old.get(no)
        row = copy.deepcopy(slot)
        if previous is not None and any((row.get(key) != previous.get(key) for key in ['photo_id', 'camera_side', 'forward_direction'])):
            changed.add(no)
            row['side_view_verified'] = 'UNKNOWN'
            row['observation'] = dict(load_state='UNKNOWN', measured_load_kg=None, single_person='UNKNOWN', full_frame='UNKNOWN', normal_work='UNKNOWN', evidence=evidence())
        elif previous is not None and ('observation' not in slot or row.get('observation') == previous.get('observation')):
            row['observation'] = copy.deepcopy(previous.get('observation') or row.get('observation'))
        if not isinstance(row.get('observation'), dict):
            raise ValueError(f'{no}번 행의 관찰값 형식이 올바르지 않습니다')
        obs = row['observation']
        if obs.get('load_state', 'UNKNOWN') not in ('UNKNOWN', 'UNLOADED', 'MEASURED'):
            raise ValueError(f'{no}번 행의 하중 상태 값이 올바르지 않습니다')
        for key in ('single_person', 'full_frame', 'normal_work'):
            if obs.get(key, 'UNKNOWN') not in ('YES', 'NO', 'UNKNOWN'):
                raise ValueError(f'{no}번 행의 {key} 값이 올바르지 않습니다')
        measured = obs.get('measured_load_kg')
        if measured is not None and (isinstance(measured, bool) or not isinstance(measured, (int, float))):
            raise ValueError(f'{no}번 행의 측정 하중은 숫자 또는 비어 있음이어야 합니다')
        ev = obs.get('evidence')
        if ev is not None and (not isinstance(ev, dict) or any((ev.get(k) is not None and (not isinstance(ev.get(k), str)) for k in ('source', 'text', 'observed_at')))):
            raise ValueError(f'{no}번 행의 근거 형식이 올바르지 않습니다')
        seen.add(no)
        new_slots.append(row)
    removed = set(old) - seen
    task['manual'] = [m for m in task['manual'] if m.get('slot_no') not in removed | changed]
    task['capture'] = dict(protocol='GENERAL_STILLS_V1', slots=new_slots)

def validate_task_input_shape(ctx, value):
    if not isinstance(value, dict) or value.get('schema_version') != '2.0' or value.get('task_kind') != 'GENERAL_TASK':
        raise ValueError('일반 작업 입력 2.0이 필요합니다')
    if value.get('input_template') not in ('GENERAL', 'OFFICE', 'REPETITION', 'POSTURE', 'HAND_FORCE', 'LIFTING', 'IMPACT'):
        raise ValueError('지원하지 않는 입력 템플릿입니다')
    if not isinstance(value.get('task_name'), str):
        raise ValueError('작업명은 문자열이어야 합니다')
    count = value.get('worker_count')
    if count is not None and (type(count) is not int or count < 0):
        raise ValueError('작업자 수는 0 이상 정수 또는 비어 있음이어야 합니다')
    scope = value.get('analysis_scope')
    if not isinstance(scope, dict) or set(scope) != {'judgment', 'pose', 'tags', 'reba'} or any((type(v) is not bool for v in scope.values())) or (scope.get('judgment') is not True):
        raise ValueError('analysis_scope는 네 모듈의 참/거짓 선택이어야 합니다')
    conditions = value.get('conditions')
    if not isinstance(conditions, dict):
        raise ValueError('작업조건 객체가 필요합니다')
    for key in ('work_intensity', 'work_frequency'):
        score = conditions.get(key)
        if score is not None and (isinstance(score, bool) or not isinstance(score, int) or (not 1 <= score <= 5)):
            raise ValueError(f'conditions.{key}는 1~5 또는 비어 있음이어야 합니다')
    for key in ('work_posture', 'method_description', 'hazard_factors', 'hazard_causes', 'improvement_recommendations'):
        if conditions.get(key) is not None and (not isinstance(conditions.get(key), str)):
            raise ValueError(f'conditions.{key}는 문자열이어야 합니다')
    legal = value.get('legal')
    criteria = legal.get('criteria') if isinstance(legal, dict) else None
    if not isinstance(criteria, list) or len(criteria) != 11 or any((not isinstance(x, dict) for x in criteria)):
        raise ValueError('11개 기준 입력이 필요합니다')
    criterion_ids = [x.get('criterion_no') for x in criteria]
    if any((isinstance(x, bool) or not isinstance(x, int) for x in criterion_ids)) or criterion_ids != list(range(1, 12)):
        raise ValueError('기준 번호는 1호부터 11호까지 한 번씩 있어야 합니다')
    exposures = legal.get('exposures')
    codes = [x.get('condition_code') for x in exposures] if isinstance(exposures, list) and all((isinstance(x, dict) for x in exposures)) else None
    if codes != EXPOSURE_V2:
        raise ValueError('일일 노출 입력 코드는 2.0 기준 목록과 일치해야 합니다')
    for number in range(6, 12):
        criterion = criteria[number - 1]
        rows = criterion.get('rows')
        if not isinstance(rows, list):
            raise ValueError(f'{number}호 조건 행 목록이 필요합니다')
        ids = [row.get('row_id') for row in rows if isinstance(row, dict)]
        if len(ids) != len(rows) or any((not isinstance(x, str) or not x for x in ids)) or len(ids) != len(set(ids)):
            raise ValueError(f'{number}호 조건 행 ID는 비어 있거나 중복될 수 없습니다')
        if number == 9:
            if not isinstance(criterion.get('totals'), dict):
                raise ValueError('9호 합집합 입력이 필요합니다')
        elif not isinstance(criterion.get('union'), dict):
            raise ValueError(f'{number}호 합집합 입력이 필요합니다')
    capture_value = value.get('capture')
    if not isinstance(capture_value, dict) or capture_value.get('protocol') != 'GENERAL_STILLS_V1' or (not isinstance(capture_value.get('slots'), list)):
        raise ValueError('일반 사진 행 목록이 필요합니다')
    slots = capture_value['slots']
    slot_ids = [x.get('slot_no') for x in slots if isinstance(x, dict)]
    if len(slot_ids) != len(slots) or any((isinstance(x, bool) or not isinstance(x, int) or x < 1 for x in slot_ids)) or len(slot_ids) != len(set(slot_ids)):
        raise ValueError('사진 행 번호는 중복 없는 양의 정수여야 합니다')
    if any((type(x.get('analysis_target')) is not bool or not isinstance(x.get('observation'), dict) for x in slots)):
        raise ValueError('사진 행의 분석대상과 관찰 입력 형식이 올바르지 않습니다')
    if not isinstance(value.get('manual'), list):
        raise ValueError('수동 관찰 입력은 목록이어야 합니다')
    slots_by_no = {s['slot_no']: s for s in slots}
    seen = set()
    for manual in value['manual']:
        if not isinstance(manual, dict):
            raise ValueError('수동 관찰은 객체여야 합니다')
        if 'value' not in manual:
            raise ValueError('수동 관찰 값(value)이 필요합니다. 미확인은 null로 저장하세요')
        no = manual.get('slot_no')
        photo_id = manual.get('photo_id')
        scope = manual.get('scope')
        field = manual.get('field')
        slot = slots_by_no.get(no) if type(no) is int else None
        if slot is None or type(photo_id) is not int or photo_id != slot.get('photo_id'):
            raise ValueError('수동 관찰은 해당 사진 행의 현재 사진에 연결되어야 합니다')
        fields = COMMON + TAG_FIELDS if scope == 'COMMON' else ARM if scope in ('LEFT', 'RIGHT') else []
        if field not in fields:
            raise ValueError('수동 관찰의 좌우/공통 필드 계약이 올바르지 않습니다')
        key = (no, scope, field)
        if key in seen:
            raise ValueError('같은 사진·측면·필드의 수동 관찰은 중복될 수 없습니다')
        seen.add(key)

def handle_delete_survey(ctx, method, p):
    with ctx.db_lock:
        identity = p['survey_id'] if method == 'delete_survey' else p['task_id']
        ctx.require('survey' if method == 'delete_survey' else 'task', identity)
        tasks = ctx.store('list_tasks', identity) if method == 'delete_survey' else [ctx.require('task', identity)]
        analyses = [a for task in tasks for a in ctx.store('list_analyses', task['task_id'])]
        for a in analyses:
            cancel = ctx.cancels.get(a['analysis_id'])
            if cancel:
                cancel.set()
        ctx.store(method, identity)
        for a in analyses:
            ctx.forget_analysis(a['analysis_id'])
    return dict(message='기록을 삭제했습니다. 원본 사진과 Excel은 유지됩니다.')

def handle_list_tasks(ctx, method, p):
    ctx.require('survey', p['survey_id'])
    return [upgrade_task(t) for t in ctx.store('list_tasks', p['survey_id'])]

def handle_create_task(ctx, method, p):
    ctx.require('survey', p['survey_id'])
    if not isinstance(p['draft'], dict) or p['draft'].get('schema_version', '2.0') != '2.0' or p['draft'].get('task_kind', 'GENERAL_TASK') != 'GENERAL_TASK':
        raise ValueError('새 작업은 일반 작업 2.0 계약을 사용해야 합니다')
    data = new_task_input(p['draft'])
    ctx.validate_task_input_shape(data)
    if any((slot.get('photo_id') is not None for slot in data['capture']['slots'])):
        raise ValueError('새 작업을 저장한 뒤 해당 작업에 사진을 등록하세요')
    identity = ctx.store('create_task', p['survey_id'], data, now(), now())
    return ctx.require('task', identity)

def handle_save_task_input(ctx, method, p):
    task = ctx.require('task', p['task_id'])
    raw = ctx.store('get_task', p['task_id'])
    incoming = p.get('input')
    if p.get('expected_revision', task['input_revision']) != task['input_revision']:
        raise ValueError('다른 화면에서 작업이 변경되었습니다. 최신 작업을 다시 열고 저장하세요.')
    ctx.validate_task_input_shape(incoming)
    old_conditions = task['conditions']
    for key in ['task_name', 'input_template', 'worker_count', 'conditions', 'legal', 'manual', 'analysis_scope', 'legacy_input']:
        if key not in incoming:
            raise ValueError(f'필수 입력 누락: {key}')
        task[key] = copy.deepcopy(incoming[key])
    ctx.reconcile_capture(task, incoming.get('capture'))
    if any((old_conditions.get(f) != task['conditions'].get(f) for f in ['worker_code', 'method_description', 'work_height_cm'])):
        task['manual'] = []
        for slot in task['capture']['slots']:
            slot['observation'] = dict(load_state='UNKNOWN', measured_load_kg=None, single_person='UNKNOWN', full_frame='UNKNOWN', normal_work='UNKNOWN', evidence=evidence())
    return ctx.save_task(task, force=raw.get('schema_version') != '2.0')

def handle_get_task(ctx, method, p):
    analysis_settings = ctx.settings()['analysis']
    task = ctx.require('task', p['task_id'])
    return dict(task=task, source_schema_version=task.get('source_schema_version', '2.0'), exclusions=exclusions(task['conditions']), photos=ctx.store('list_photos', task['task_id']), settings=analysis_settings)

def handle_rename_task(ctx, method, p):
    task = ctx.require('task', p['task_id'])
    key = {'rename_task': 'task_name', 'set_task_conditions': 'conditions', 'set_legal_inputs': 'legal', 'set_capture': 'capture', 'set_manual_values': 'manual'}[method]
    value = p[key]
    reset = key == 'conditions' and any((task['conditions'].get(f) != value.get(f) for f in ['worker_code', 'method_description', 'work_height_cm']))
    if key == 'capture':
        ctx.reconcile_capture(task, value)
    else:
        task[key] = value
    if reset:
        task['manual'] = []
        for slot in task['capture']['slots']:
            slot['observation'] = dict(load_state='UNKNOWN', measured_load_kg=None, single_person='UNKNOWN', full_frame='UNKNOWN', normal_work='UNKNOWN', evidence=evidence())
    ctx.validate_task_input_shape(task)
    return ctx.save_task(task)

def handle_set_task_profile(ctx, method, p):
    task = ctx.require('task', p['task_id'])
    task['input_template'] = p['input_template']
    task['worker_count'] = p.get('worker_count')
    ctx.validate_task_input_shape(task)
    return ctx.save_task(task)

def handle_set_analysis_scope(ctx, method, p):
    task = ctx.require('task', p['task_id'])
    task['analysis_scope'] = p['scope']
    ctx.validate_task_input_shape(task)
    return ctx.save_task(task)
