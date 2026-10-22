"""Map an immutable export snapshot to original-form fields; never calculate rules."""
from copy import deepcopy
from .overview import overview
SITUATION = [('equipment','작업설비'),('workload','작업량'),
             ('speed','작업속도'),('work_pattern','업무 변화')]


def map_snapshot(snapshot):
    snapshot = deepcopy(snapshot)
    survey = snapshot['survey']
    analyses = {a['task_id']: a for a in snapshot['analyses']}
    appendix, warnings, tasks = [], [], []

    situation = []
    for key, label in SITUATION:
        data = survey.get('workplace_situation') or {}
        state, note = data.get(key+'_status','UNKNOWN'), data.get(key+'_notes','')
        if state not in ('YES','NO','UNKNOWN') or not isinstance(note,str):
            raise ValueError('작업장 상황 입력 형식이 올바르지 않습니다.')
        situation.append({'key':key,'state':state,'note':note})
        if key != 'equipment' and state == 'YES':
            message=f'{label}: 변경 있음. 줄음·늘어남·기타와 시점은 별도 확인이 필요합니다.'
            warnings.append(message)

    for task in snapshot['tasks']:
        analysis = analyses.get(task['task_id'])
        source = analysis['snapshot'] if analysis else task
        name = source.get('task_name') or task.get('task_name') or ''
        cond = source.get('conditions') or {}
        a,b = cond.get('work_intensity'),cond.get('work_frequency')
        for value in (a,b):
            if value is not None and (type(value) is not int or not 1<=value<=5):
                raise ValueError('작업부하와 작업빈도는 1~5 정수 또는 미입력이어야 합니다.')
        confirmed, judgments = [], ((analysis or {}).get('judgment') or {}).get('judgments',[])
        for judgment in judgments:
            investigator = judgment.get('investigator') or {}
            n = judgment['criterion_no']
            if investigator.get('status')=='APPLICABLE':
                confirmed.append(str(n))
        if not confirmed:
            warnings.append(name+': 원본 부담작업 호 칸의 공란은 비해당 확정을 뜻하지 않습니다.')
        selected = None
        if snapshot.get('include_representative'):
            reba = (analysis or {}).get('reba') or {}
            number = (reba.get('summary') or {}).get('representative_slot_no')
            slot = next((s for s in (source.get('capture') or {}).get('slots',[]) if s.get('slot_no')==number),None) if number is not None else None
            if slot and slot.get('photo_id') is not None:
                selected = next((p for p in source.get('photos',[]) if p.get('photo_id')==slot['photo_id']),None)
        tasks.append({'task_id':task['task_id'],'name':name,'description':cond.get('method_description') or '',
                      'intensity':a,'frequency':b,'total':a*b if a is not None and b is not None else None,
                      'confirmed_criteria':', '.join(confirmed),'worker_name':None,
                      'factor':cond.get('hazard_factors') or '', 'cause':cond.get('hazard_causes') or '',
                      'photo':deepcopy(selected)})
    if not tasks:
        raise ValueError('PDF에 포함할 작업을 선택해 주세요.')
    # Detail and follow-up information remains available to the app. Only the
    # renderer adds an appendix when text for an actual form field overflows.
    ov = overview(snapshot)
    state = ov['state']
    if state.get('has_stale'):warnings.append('과거 입력 기준의 분석이 포함되어 있습니다.')
    if state.get('has_incomplete'):warnings.append('미완성 또는 미계산 결과가 포함되어 있습니다.')
    return {'survey':survey,'tasks':tasks,'situation':situation,'appendix':appendix,
            'warnings':list(dict.fromkeys(warnings)),'state':state,'overview':ov}
