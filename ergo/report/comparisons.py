"""Compare stored snapshots without recomputing historical results."""
from .common import flatten
from ergo.engine.task_defaults import AUXILIARY_CONDITION_KEYS

def build_comparisons(snapshot):
    comparisons = []
    analyses = {x['analysis_id']: x for x in snapshot.get('analyses', []) + snapshot.get('comparison_analyses', [])}
    for spec in snapshot.get('comparison_specs', []):
        before = analyses.get(spec.get('before_analysis_id'))
        after = analyses.get(spec.get('after_analysis_id'))
        if before is None or after is None:
            continue
        bset = before['snapshot']
        aset = after['snapshot']
        bsettings = bset.get('settings') or {}
        asettings = aset.get('settings') or {}
        rule_ok = bool(bsettings.get('burden_rule') and asettings.get('burden_rule') and bsettings.get('reba_rule') and asettings.get('reba_rule') and (bsettings.get('burden_rule') == asettings.get('burden_rule')) and (bsettings.get('reba_rule') == asettings.get('reba_rule')))
        bslots = [s for s in (bset.get('capture') or {}).get('slots', []) if s.get('photo_id') is not None and s.get('analysis_target', bset.get('schema_version') != '2.0')]
        aslots = [s for s in (aset.get('capture') or {}).get('slots', []) if s.get('photo_id') is not None and s.get('analysis_target', aset.get('schema_version') != '2.0')]
        br = before.get('reba') or {}
        ar = after.get('reba') or {}
        sampling = bset.get('capture', {}).get('protocol') == aset.get('capture', {}).get('protocol') and len(bslots) > 0 and (len(bslots) == len(aslots)) and (br.get('status') == 'COMPLETE') and (ar.get('status') == 'COMPLETE') and (br.get('summary', {}).get('complete_count') == len(bslots)) and (ar.get('summary', {}).get('complete_count') == len(aslots))
        reba_rule_ok = bool(bsettings.get('reba_rule') and bsettings.get('reba_rule') == asettings.get('reba_rule'))
        delta = ar.get('summary', {}).get('full_max') - br.get('summary', {}).get('full_max') if reba_rule_ok and sampling and (br.get('summary', {}).get('full_max') is not None) and (ar.get('summary', {}).get('full_max') is not None) else None
        bj = {j['criterion_no']: j for j in (before.get('judgment') or {}).get('judgments', [])}
        aj = {j['criterion_no']: j for j in (after.get('judgment') or {}).get('judgments', [])}
        criterion_diff = [dict(criterion_no=n, before_computed_status=bj.get(n, {}).get('computed_status'), before_investigator_status=bj.get(n, {}).get('investigator', {}).get('status'), before_status=bj.get(n, {}).get('effective_status'), after_computed_status=aj.get(n, {}).get('computed_status'), after_investigator_status=aj.get(n, {}).get('investigator', {}).get('status'), after_status=aj.get(n, {}).get('effective_status')) for n in range(1, 12)]
        before_task = before['task_id']
        after_task = after['task_id']
        changes = []
        for label, obj1, obj2 in [('conditions', bset.get('conditions') or {}, aset.get('conditions') or {}), ('analysis_scope', bset.get('analysis_scope') or {}, aset.get('analysis_scope') or {}), ('legal', bset.get('legal') or {}, aset.get('legal') or {}), ('capture',bset.get('capture') or {},aset.get('capture') or {}), ('manual',bset.get('manual') or [],aset.get('manual') or []), ('settings',bset.get('settings') or {},aset.get('settings') or {})]:
            if label=='conditions':
                obj1={k:v for k,v in obj1.items() if k not in AUXILIARY_CONDITION_KEYS}
                obj2={k:v for k,v in obj2.items() if k not in AUXILIARY_CONDITION_KEYS}
            flat1 = dict(flatten(obj1, label))
            flat2 = dict(flatten(obj2, label))
            for path in sorted(set(flat1) | set(flat2)):
                if flat1.get(path) != flat2.get(path):
                    changes.append(dict(field_path=path, before=flat1.get(path), after=flat2.get(path)))
        notes = []
        if not rule_ok:
            notes.append('고시 또는 REBA 규칙 버전이 달라 점수 비교가 제한됩니다.')
        if not sampling:
            notes.append('촬영 프로토콜·대상 수·전체 평가 완성이 맞지 않아 REBA 최대값 차이를 계산하지 않았습니다.')
        if before_task != after_task:
            notes.append('서로 다른 작업을 비교합니다. 작업 조건과 표본 대표성을 함께 확인하세요.')
        if changes:
            notes.append('작업 조건 또는 분석 범위가 달라졌습니다.')
        notes.append('전후 비교는 표본 자세 변화의 참고값이며 질환 감소나 인과 효과를 입증하지 않습니다.')
        comparisons.append(dict(spec=spec, before_task_id=before_task, after_task_id=after_task, rule_compatible=rule_ok, sampling_compatible=sampling, reba_max_delta=delta, criteria=criterion_diff, condition_changes=changes, notes=notes))
    return comparisons
