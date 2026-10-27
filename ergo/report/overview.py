"""Survey completeness, review state and actionable missing inputs."""
from .common import currentness
from .comparisons import build_comparisons
from .labels import AI_REASON_KO, INCOMPLETE, MODULE_PLAIN, criterion_name, input_label, reason_label

def overview(snapshot):
    tasks = []
    reba_task_ids = set()
    survey = snapshot['survey']
    review = survey.get('review') or {}
    for task in snapshot['tasks']:
        a = next((x for x in snapshot['analyses'] if x['task_id'] == task['task_id']), None)
        source = a['snapshot'] if a else task
        cur = currentness(task, a)
        pose = a.get('pose') if a else None
        tags = a.get('tags') if a else None
        reba = a.get('reba') if a else None
        judgment = a.get('judgment') if a else None
        judgments = (judgment or {}).get('judgments', [])
        slots = (source.get('capture') or {}).get('slots', [])
        v2 = source.get('schema_version') == '2.0'
        targets = [s for s in slots if s.get('photo_id') is not None and s.get('analysis_target', not v2)]
        scope = source.get('analysis_scope') or dict(judgment=True, pose=True, tags=True, reba=True)
        requested = {'pose': scope.get('pose', True), 'tags': scope.get('tags', True), 'reba': scope.get('reba', True), 'judgment': scope.get('judgment', True)}
        if requested['reba']:
            reba_task_ids.add(task['task_id'])
        values = {'pose': pose, 'tags': tags, 'reba': reba, 'judgment': judgment}
        stored = (a or {}).get('module_states') or {}
        states = {}
        for module, value in values.items():
            if not requested[module]:
                state = 'NOT_REQUESTED'
            elif not a:
                state = 'NOT_CALCULATED'
            elif stored.get(module):
                state = stored[module]
            elif value is None:
                state = 'NOT_CALCULATED'
            elif module == 'pose':
                state = 'COMPLETE' if value.get('status') == 'DONE' else 'FAILED' if value.get('status') == 'FAILED' else 'INCOMPLETE'
            elif module == 'reba':
                state = 'COMPLETE' if value.get('status') == 'COMPLETE' else 'INCOMPLETE'
            elif module == 'tags':
                state = 'COMPLETE' if targets and all((x.get('observed_count') == len(targets) for x in value)) else 'INCOMPLETE'
            else:
                state = 'INCOMPLETE' if any((j.get('computed_status') in ('NEEDS_INPUT', 'NEEDS_REVIEW') for j in (value or {}).get('judgments', []))) else 'COMPLETE'
            states[module] = state
        burden_countable = bool(a and requested['judgment'] and (judgment is not None))
        reba_countable = bool(a and requested['reba'] and (reba is not None))
        counts = dict(needs_input_count=sum((j['computed_status'] == 'NEEDS_INPUT' for j in judgments)) if burden_countable else None, needs_review_count=sum((j['computed_status'] == 'NEEDS_REVIEW' for j in judgments)) if burden_countable else None, incomplete_reba_count=max(0, len(targets) - (reba or {}).get('summary', {}).get('complete_count', 0)) if reba_countable else None)
        reviewed = bool(a and review.get('reviewed') and (a['analysis_id'] in (review.get('reviewed_analysis_ids') or [])))
        incomplete = not a or any((requested[m] and states[m] != 'COMPLETE' for m in requested))
        state = dict(reviewed=reviewed, review_current=reviewed and review.get('reviewed_metadata_revision') == survey.get('metadata_revision') and (cur == 'CURRENT'), has_incomplete=incomplete, has_stale=cur == 'STALE')
        next_inputs = []

        def add(module, kind, message, slot=None, criterion=None, fields=None, reasons=None):
            next_inputs.append(dict(module=module, kind=kind, slot_no=slot, criterion_no=criterion, field_paths=fields or [], reason_codes=reasons or [], message=message))
        if not a:
            add('ANALYSIS', 'NOT_CALCULATED', '분석을 아직 하지 않았어요')
        else:
            labels = MODULE_PLAIN
            kinds = {'NOT_CALCULATED': 'NOT_CALCULATED', 'RUNNING': 'NOT_CALCULATED', 'FAILED': 'REVIEW_REQUIRED', 'INCOMPLETE': 'REVIEW_REQUIRED', 'CANCELED': 'REVIEW_REQUIRED'}
            for module, label in labels.items():
                module_state = states[module]
                if requested[module] and module_state != 'COMPLETE' and (module_state != 'NOT_REQUESTED'):
                    kind = kinds.get(module_state, 'NOT_CALCULATED')
                    if module_state in ('NOT_CALCULATED', 'RUNNING'):
                        add(module.upper(), 'NOT_CALCULATED', label + ' 계산이 아직 끝나지 않았어요')
                    elif module == 'tags' and (not targets):
                        add('TAGS', 'MISSING_INPUT', '자세 표시를 계산할 분석 대상 사진이 없어요')
                    elif module == 'reba' and (not targets):
                        add('REBA', 'MISSING_INPUT', 'REBA 점수를 계산할 분석 대상 사진이 없어요')
                    else:
                        add(module.upper(), kind, INCOMPLETE[module])
            if requested['pose'] and (not targets):
                add('POSE', 'MISSING_INPUT', '분석 대상으로 고른 사진이 없어요')
            for slot in targets:
                no = slot['slot_no']
                label = slot.get('label') or f'사진 {no}'
                p = next((x for x in (pose or {}).get('slots', []) if x['slot_no'] == no), None)
                r = next((x for x in (reba or {}).get('slots', []) if x['slot_no'] == no), None)
                if requested['reba'] and r and r.get('missing_fields'):
                    add('REBA', 'MISSING_INPUT', label + ': ' + ', '.join((input_label(f) for f in r['missing_fields'])) + ' 입력 필요', no, fields=r['missing_fields'])
                if requested['pose'] and p and (p['status'] != 'VALID'):
                    add('POSE', 'REVIEW_REQUIRED', label + ': ' + ' / '.join((d['message'] for d in p.get('diagnostics', []))), no, fields=list(dict.fromkeys((d['field_path'] for d in p.get('diagnostics', []) if d.get('field_path')))), reasons=list(dict.fromkeys((d['code'] for d in p.get('diagnostics', [])))))
                if requested['reba'] and r:
                    reasons = list(dict.fromkeys(r.get('left', {}).get('review_reasons', []) + r.get('right', {}).get('review_reasons', [])))
                    if reasons:
                        add('REBA', 'REVIEW_REQUIRED', label + ': ' + ', '.join((reason_label(x) for x in reasons)), no, reasons=reasons)
            for j in judgments:
                if j.get('missing_fields'):
                    add('BURDEN', 'MISSING_INPUT', f'{criterion_name(j['criterion_no'])}: ' + ', '.join((input_label(x) for x in j['missing_fields'])) + ' 입력 필요', criterion=j['criterion_no'], fields=j['missing_fields'])
                if j.get('review_reasons'):
                    add('BURDEN', 'REVIEW_REQUIRED', f'{criterion_name(j['criterion_no'])}: ' + ', '.join((reason_label(x) for x in j['review_reasons'])), criterion=j['criterion_no'], reasons=j['review_reasons'])
            for note in a.get('notes', []):
                add('ANALYSIS', 'REVIEW_REQUIRED', note.get('message', '분석 진단'), reasons=[note.get('code')] if note.get('code') else [])
            for ai in a.get('ai') or []:
                if ai.get('result') in ('FALLBACK', 'DISABLED'):
                    add('EXPLANATION', 'REVIEW_REQUIRED', 'AI 설명을 쓰지 못해 기본 문구로 대신했어요(이유: ' + AI_REASON_KO.get(ai.get('fallback_reason') or ai.get('result'), '설정이나 연결 상태를 확인하세요') + ')')
        next_inputs.sort(key=lambda item: 0 if item['kind'] == 'MISSING_INPUT' else 1)
        tasks.append(dict(task_id=task['task_id'], task_name=source['task_name'], analysis_id=a['analysis_id'] if a else None, input_revision=source['input_revision'], source_schema_version=source.get('schema_version', '1.3'), module_states=states if a else None, currentness=cur, state=state, review_status='NO_ANALYSIS' if not a else 'UNREVIEWED' if not reviewed else 'REVIEWED_CURRENT' if state['review_current'] else 'REVIEWED_HISTORY', counts=counts, next_inputs=next_inputs))
    state = {key: bool(tasks) and all((t['state'][key] for t in tasks)) if key in ('reviewed', 'review_current') else any((t['state'][key] for t in tasks)) for key in ('reviewed', 'review_current', 'has_incomplete', 'has_stale')}
    counts = {key: sum((t['counts'][key] for t in tasks)) if all((t['counts'][key] is not None for t in tasks)) else None for key in ('needs_input_count', 'needs_review_count')}
    reba_requested = [t for t in tasks if t['task_id'] in reba_task_ids]
    counts['incomplete_reba_count'] = sum((t['counts']['incomplete_reba_count'] for t in reba_requested)) if reba_requested and all((t['counts']['incomplete_reba_count'] is not None for t in reba_requested)) else None
    comparisons = build_comparisons(snapshot)
    return dict(report_version='2.0', state=state, counts=counts, tasks=tasks, comparisons=comparisons)
