"""Plain-language workbook content for ordinary readers.

The same sheet descriptions feed the Excel file and the in-app preview, so what people preview is what they get.
Confirmed results come from the stored snapshot. A read-only current-score projection preserves measured inputs and labels assumptions; stored inputs are unchanged. Codes are shown as everyday Korean words.
A sheet is {name, title, lead, tables:[{heading, columns, rows, widths, ...}], notes}; form.py adds only data-backed survey and criterion results.
"""
import json
import math
from datetime import datetime, timedelta, timezone

from .common import currentness
from .display import SOURCE, STATUS, UNIT, VALUE
from .labels import CRITERIA, EXPOSURES, MANUAL, RESULT_LABELS, criterion_name, input_label, reason_label, unit_for
from .input_trace import InputTrace
from ergo.user_language import user_text
from ergo.intake.photo_facts import VIEW_LABELS,photo_id as fact_photo_id
from ergo.pose_contract import WRIST_POLICY
from ergo.engine.reba_scoring import project_current_score, project_score_continuity, risk as reba_risk

KST = timezone(timedelta(hours=9))
SIDE = {'LEFT': '왼쪽', 'RIGHT': '오른쪽', 'COMMON': '공통', 'BOTH': '양쪽', 'FRONT': '정면·후면'}
CAMERA = {'LEFT': '왼쪽 몸이 보이는 쪽에서', 'RIGHT': '오른쪽 몸이 보이는 쪽에서', 'FRONT': '정면 또는 후면에서'}
FACING = {'SCREEN_LEFT': '사진의 왼쪽', 'SCREEN_RIGHT': '사진의 오른쪽'}
ANGLE = {'TRUNK_TILT_VERT': '몸통 기울기', 'NECK_TILT_VERT_PROXY': '목 기울기(추정)', 'NECK_FLEX_TRUNK_PROXY': '목 굽힘(몸통 기준, 추정)', 'UPPER_ARM_RAISE_VERT': '위팔 들림',
         'UPPER_ARM_FLEX_TRUNK': '위팔 굽힘(몸통 기준)', 'ELBOW_FLEX': '팔꿈치 굽힘', 'KNEE_FLEX': '무릎 굽힘',
         'ELBOW_FLEX_3D': '팔꿈치 굽힘', 'KNEE_FLEX_3D': '무릎 굽힘'}
ANGLE[WRIST_POLICY['angle_code']]='손목 굽힘(사진에서 측정)'
TAG = {'NECK_FORWARD_PROXY': '목을 앞으로 숙임', 'TRUNK_FLEX': '몸통을 앞으로 굽힘', 'TRUNK_EXT': '몸통을 뒤로 젖힘', 'UPPER_ARM_RAISE': '위팔을 들어 올림', 'HAND_ABOVE_HEAD': '손이 머리 위',
       'ELBOW_ABOVE_SHOULDER': '팔꿈치가 어깨 위', 'ELBOW_BEHIND_TRUNK': '팔꿈치가 몸통 뒤', 'NECK_TWIST': '목을 비틂', 'TRUNK_TWIST': '몸통을 비틂', 'SQUAT': '쪼그림', 'KNEEL': '무릎을 꿇음'}
SCOPE_PLAIN = {'pose': '사진에서 자세 읽기', 'tags': '자세 표시', 'reba': 'REBA 점수', 'judgment': '법정 기준 판정'}
CONDITIONS = [('daily_work_min', '하루 실제 작업시간', 'MIN_DAY'), ('annual_work_days', '1년에 작업하는 날 수', 'COUNT_YEAR'), ('one_off', '한 번만 하고 끝나는 일회성 작업인가', None),
              ('planned_duration_months', '예정 작업기간', 'MONTH'), ('work_height_cm', '작업 높이', 'cm'), ('worker_code', '작업자 코드(표시명)', None), ('method_description', '작업 방법', None),
              ('work_posture', '작업 자세', None), ('work_intensity', '작업 강도', None), ('work_frequency', '작업 빈도', None), ('hazard_factors', '관찰한 유해요인', None),
              ('hazard_causes', '유해요인의 원인', None), ('improvement_recommendations', '개선 제안', None)]
# What the person picked for the posture questions, in the words they saw on screen.
CHOICE = {
    'trunk_base': {1: '똑바로', 2: '조금(20° 이내)', 3: '많이(20~60°)', 4: '아주 많이(60° 초과)'},
    'knee_band': {'UNDER_30': '거의 안 굽힘(30° 미만)', 'FROM_30_TO_60': '30~60°', 'OVER_60': '60° 초과'},
    'upper_arm_base': {1: '몸 옆(20° 이내)', 2: '20~45°', 3: '45~90°', 4: '90° 초과'},
    'lower_arm_base': {1: '60~100°', 2: '그 밖(60° 미만·100° 초과)'},
    'neck_base': {1: '똑바로·조금 숙임(20° 이내)', 2: '20° 넘게 숙임', '2_EXTENSION': '뒤로 젖힘'},
    'wrist_base': {1: '15° 이내', 2: '15° 넘게'},
}
SOURCE_PLAIN = dict(SOURCE, AUTO_ACCEPTED='사진에서 자동 채택')
SHEET_NOTES = [
    '이 보고서는 작업 분석을 돕는 참고 자료예요. 법정 유해요인조사표·증상조사표를 대신하지 않아요.',
    '"해당 초안"은 입력한 값으로 계산한 결과예요. 최종 해당 여부는 조사자가 검토해 정해요. 조사자 결론은 법적 승인을 뜻하지 않아요.',
    '사진에서 읽은 자세 비율은 하루 노출시간이 아니에요. 점수가 비어 있으면 0점이 아니라 계산하지 못했다는 뜻이에요.',
]


# ----- small formatting helpers
def kst(value, date_only=False):
    """ISO time -> Korean wall time text. Dates without a time stay as they are."""
    if value in (None, ''):
        return None
    text = str(value)
    if len(text) == 10 and text[4] == '-' and text[7] == '-':
        return text
    try:
        moment = datetime.fromisoformat(text.replace('Z', '+00:00'))
    except ValueError:
        return text
    moment = moment.astimezone(KST) if moment.tzinfo else moment + timedelta(hours=9)
    return moment.strftime('%Y-%m-%d' if date_only else '%Y-%m-%d %H:%M')


def say(value):
    """A stored value as words: codes become Korean, True/False become 예/아니오, 240.0 becomes 240."""
    if value is None or value == '':
        return ''
    if isinstance(value, bool):
        return '예' if value else '아니오'
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    if isinstance(value, str):
        return VALUE.get(value, value)
    return str(value)


def with_unit(value, unit):
    if value is None or value == '':
        return ''
    if not unit or unit == 'BOOLEAN':
        return say(value)
    return f'{say(value)} {UNIT.get(unit, unit)}'


def value_label(field, value):
    if value in CHOICE.get(field, {}):
        return CHOICE[field][value]
    return say(value)


def note(text):
    """Evidence text without the app's internal wording."""
    if not text:
        return ''
    text = str(text)
    if text.startswith('{'):
        try:
            data = json.loads(text)
        except ValueError:
            return text
        angles = data.get('angles') if isinstance(data, dict) else None
        if isinstance(data, dict) and data.get('photo_vision'):
            return 'AI 사진 관찰: ' + str(data.get('quote') or '')
        if angles:
            return '사진에서 잰 각도 ' + ' / '.join(f"{a.get('value_deg')}°" for a in angles if a.get('value_deg') is not None)
        return ''
    for old, new in (('빠른 분석 질문: ', '질문: '), ('빠른 분석 체크: ', '체크: '), ('빠른 분석 검토', '조사자 검토'), ('빠른 분석: ', '')):
        if text.startswith(old):
            return new + text[len(old):]
    return text


def _source(evidence):
    code = (evidence or {}).get('source')
    return SOURCE_PLAIN.get(code, code or '')


def _table(columns, rows, widths=None, heading=None, **extra):
    """A table description. Extra keys (header, labels, merges, bordered, ...) ask the writer and the preview for form-style drawing."""
    return dict(heading=heading, columns=list(columns), rows=[[_plain_cell(v) for v in row] for row in rows], widths=list(widths or []), **extra)


def _plain_cell(value):
    if value is None:
        return ''
    if isinstance(value, bool):
        return '예' if value else '아니오'
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return value


def _sheet(name, lead, tables, notes=None, title=None):
    return dict(name=name, title=title or name, lead=lead, tables=[t for t in tables if t], notes=list(notes or []))


def _slot_names(source):
    return {s.get('slot_no'): VIEW_LABELS.get(s.get('label'),s.get('label') or f"사진 {s.get('slot_no')}") for s in (source.get('capture') or {}).get('slots', [])}


def _owned_measurement(rows,slot):
    candidates=[row for row in rows if isinstance(row,dict) and row.get('slot_no')==slot.get('slot_no')]
    exact=[row for row in candidates if row.get('photo_id')==slot.get('photo_id')]
    if len(exact)==1:return exact[0]
    if not exact and len(candidates)==1 and candidates[0].get('photo_id') is None:return candidates[0]
    return None


def _owned_rows(rows,source):
    slots=[slot for slot in (source.get('capture') or {}).get('slots',[]) if slot.get('photo_id') is not None and slot.get('analysis_target',source.get('schema_version')!='2.0')]
    if not slots and source.get('schema_version')!='2.0':return list(rows),0
    selected=[row for slot in slots if (row:=_owned_measurement(rows,slot)) is not None]
    return selected,max(0,len(rows)-len(selected))


def _context(snapshot, ov):
    analyses = {a['task_id']: project_score_continuity(a) for a in snapshot.get('analyses', [])}
    tasks = []
    for item in ov['tasks']:
        task = next(t for t in snapshot['tasks'] if t['task_id'] == item['task_id'])
        a = analyses.get(item['task_id'])
        name = item['task_name'] or ''
        if name == '사진 분석 작업': name = ''  # Legacy QuickFlow placeholder, never user-entered task metadata.
        tasks.append(dict(item=item, task=task, analysis=a, source=a['snapshot'] if a else task, name=name))
    return dict(snapshot=snapshot, ov=ov, survey=snapshot['survey'], tasks=tasks)


# ----- 요약
def _measurement_text(analysis, slot_no):
    quality = (analysis or {}).get('measurement_quality') or {}
    owners=[slot for slot in ((analysis or {}).get('snapshot') or {}).get('capture',{}).get('slots',[]) if slot.get('slot_no')==slot_no]
    rows=quality.get('slots',[])
    selected = _owned_measurement(rows,owners[0]) if len(owners)==1 else next((item for item in rows if item.get('slot_no')==slot_no),None)
    if selected is None:
        if rows and owners:return ''
        selected = quality if len(quality.get('slots', [])) <= 1 else {}
    if not selected or not selected.get('total_points'):
        return ''
    label = {'HIGH': '높음', 'MEDIUM': '보통', 'LOW': '낮음', 'MISSING': '측정값 없음'}.get(selected.get('confidence_level'), '확인 전')
    confidence = selected.get('mean_confidence')
    percent = f' ({confidence:.0%})' if isinstance(confidence, (int, float)) and not isinstance(confidence, bool) and math.isfinite(confidence) and 0 <= confidence <= 1 else ''
    return f"측정 관절 {selected.get('measured_points', 0)}/{selected['total_points']}개 · 측정 신뢰도 {label}{percent}"


def _reba_text(a):
    if not a:
        return '분석 없음'
    reba = a.get('reba')
    if not reba:
        return '계산하지 않았어요'
    summary = reba.get('summary') or {}
    current = project_current_score(reba)
    if not current:
        return '분석대상 사진 없음' if not summary.get('total_slot_count') else '측정값 확인 필요'
    kind = current.get('kind')
    lines = [f"가정 기준 {current['total']}점 · 실제 측정 확인 필요" if kind == 'ASSUMED_REFERENCE'
             else f"현재 {current['total']}점 ({say(current.get('risk'))})"]
    quality = _measurement_text(a, current.get('slot_no'))
    if quality:
        lines.append(quality)
    if kind != 'CONFIRMED':
        assumed = current.get('assumed') or []
        slot = next((item for item in reba.get('slots', []) if item.get('slot_no') == current.get('slot_no')), {})
        partial = slot.get('score_so_far') or summary.get('score_so_far') or {}
        notes = [f'확인 전 {len(assumed)}항목은 부담 없음으로 가정'] if assumed else []
        if partial.get('unconfirmed_photo'):
            notes.append(f"사진 확인 전 값 {len(partial['unconfirmed_photo'])}개 포함")
        if 'observation.load_state' in assumed:
            notes.append('들고 있는 물건 없음으로 가정')
        if notes:
            lines.append(' · '.join(notes))
    return '\n'.join(lines)


# ----- 입력한 값
def _legal_rows(name, source):
    trace=InputTrace(source)
    legal = source.get('legal') or {}
    criteria = {x.get('criterion_no'): x for x in legal.get('criteria', [])}
    exposures = [e for e in legal.get('exposures', []) if e.get('minutes') is not None]
    group, rows, done = '법정 기준에 입력한 값', [], set()
    for no in range(1, 12):
        c = criteria.get(no) or {}
        short, state = CRITERIA[no], c.get('condition_present')
        ev = c.get('evidence') or {}
        origin=trace.lookup('work_type',state,criterion=no)
        if trace.criterion_presence_recorded(c, no):
            presence = f'물건 들기·옮기기 작업({no}호 입력)' if origin and no in (8, 9, 10) else short
            rows.append([name, group, f'{presence}: 이 작업을 한다', say(state), *(origin or (_source(ev),note(ev.get('text'))))])
        for e in exposures:
            if int(e['condition_code'][1:e['condition_code'].index('_')]) == no:
                done.add(e['condition_code'])
                eev = e.get('evidence') or {}
                origin=trace.lookup('criterion',e['minutes'],field=e['condition_code']) or (_source(eev),note(eev.get('text')))
                rows.append([name, group, f"{short}: {EXPOSURES.get(e['condition_code'], e['condition_code'])} 시간", with_unit(e['minutes'], 'MIN_DAY'), *origin])
        for key in ('unsupported', 'posture_restricted'):
            if c.get(key) in ('YES', 'NO'):
                origin=trace.lookup('criterion',c[key],field=key,criterion=no) or (_source(ev),note(ev.get('text')))
                rows.append([name, group, f'{short}: {input_label(key)}', say(c[key]), *origin])
        complete=c.get('rows_complete')
        complete_origin=trace.lookup('complete',complete,criterion=no)
        if complete_origin:
            rows.append([name,group,f'{short}: {input_label("rows_complete")}',say(complete),*complete_origin])
        listed = c.get('rows') or []
        for index, row in enumerate(listed, 1):
            rev = row.get('evidence') or {}
            for key, value in row.items():
                if key in ('row_id', 'label', 'evidence') or value in (None, ''):
                    continue
                suffix = f' (조건 {index})' if len(listed) > 1 else ''
                origin=trace.lookup('criterion',value,field=key,criterion=no,condition=row['row_id']) or (_source(rev),note(rev.get('text')))
                if value in (None, '', 'UNKNOWN') and not trace.lookup('criterion',value,field=key,criterion=no,condition=row['row_id']):
                    continue
                shown = '모름' if value in (None, 'UNKNOWN') else with_unit(value, unit_for(key))
                rows.append([name, group, f'{short}: {input_label(key)}{suffix}', shown, *origin])
    for e in exposures:
        if e['condition_code'] not in done and e['minutes'] is not None:
            eev = e.get('evidence') or {}
            origin=trace.lookup('criterion',e['minutes'],field=e['condition_code']) or (_source(eev),note(eev.get('text')))
            rows.append([name, group, f"{EXPOSURES.get(e['condition_code'], e['condition_code'])} 시간", with_unit(e['minutes'], 'MIN_DAY'), *origin])
    return rows


def _capture_rows(name, source):
    rows = []
    trace=InputTrace(source)
    primary=next((s for s in (source.get('capture') or {}).get('slots',[]) if s.get('analysis_target')),None)
    for slot in (source.get('capture') or {}).get('slots', []):
        if slot.get('photo_id') is None:
            continue
        label = slot.get('label') or f"사진 {slot.get('slot_no')}"
        obs = slot.get('observation') or {}
        ev = obs.get('evidence') or {}
        front = slot.get('camera_side') == 'FRONT'
        load = {'UNLOADED': '없음'}.get(obs.get('load_state'))
        if obs.get('load_state') == 'MEASURED':
            load = '있음' + (f" ({say(obs['measured_load_kg'])} kg)" if obs.get('measured_load_kg') is not None else '')
        checks = [('옆모습 사진', None if front else slot.get('side_view_verified')), ('한 사람만 나옴', obs.get('single_person')), ('전신이 나옴', obs.get('full_frame')),
                  ('평소 작업 모습', obs.get('normal_work'))]
        checks = [(title, value) for title, value in checks if value not in (None, '', 'UNKNOWN')]
        if checks and all(value == 'YES' for _, value in checks):
            confirmed = ('옆모습 사진이고, ' if not front else '') + '한 사람만 나오고, 전신이 나오고, 평소 작업 모습이에요'
        else:
            confirmed = ' · '.join(f'{title}: {say(value)}' for title, value in checks)
        pairs = [('찍은 방향', CAMERA.get(slot.get('camera_side'))), ('작업자가 보는 방향', None if front else FACING.get(slot.get('forward_direction'))),
                 ('사진 확인', confirmed), ('들고 있는 물건', load), ('REBA 점수 계산에 쓴 사진', say(slot.get('analysis_target')))]
        for title, value in pairs:
            if value not in (None, ''):
                origin=None
                if primary and slot['slot_no']==primary['slot_no'] and slot['photo_id']==primary['photo_id']:
                    if title=='작업자가 보는 방향':origin=trace.lookup('view',slot.get('forward_direction'),view=slot.get('label'))
                    elif title=='사진 확인' and len({obs.get(key) for key in ('single_person','full_frame','normal_work')})==1:origin=trace.lookup('context',obs.get('normal_work'))
                    elif title=='들고 있는 물건':origin=(trace.lookup('load_kg',obs.get('measured_load_kg')) if obs.get('load_state')=='MEASURED' else None) or trace.lookup('load',obs.get('load_state'))
                rows.append([name, '사진 확인', f'{label} · {title}', value, *(origin or (_source(ev),note(ev.get('text'))))])
    return rows


def _manual_rows(name, source):
    """Posture values per photo. Left and right with the same answer become one "양쪽" line; every "아니오" becomes a single line."""
    names, groups, order = _slot_names(source), {}, []
    trace=InputTrace(source)
    primary=next((s for s in (source.get('capture') or {}).get('slots',[]) if s.get('analysis_target')),None)
    manual=list(source.get('manual') or [])
    owners={}
    for slot in (source.get('capture') or {}).get('slots',[]):
        if slot.get('photo_id') is not None:owners.setdefault(slot['photo_id'],[]).append(slot)
    existing={(row.get('slot_no'),row.get('photo_id'),row.get('scope'),row.get('field')) for row in manual}
    for item in trace.facts.values():
        if item.get('alias_of') or item.get('source')!='USER' or item.get('state')!='UNKNOWN' or item.get('value') not in (None,'UNKNOWN') or item.get('photo_active') is False:
            continue
        destination=(trace.catalogue.get(item.get('target')) or {}).get('destination') or {}
        if destination.get('type')!='manual':continue
        owner=fact_photo_id(item,{'LEFT':primary['photo_id']} if primary else {})
        if item.get('photo_id') is not None and item['photo_id']!=owner:continue
        slots=owners.get(owner,[])
        if len(slots)!=1:continue
        identity=(slots[0]['slot_no'],owner,destination['scope'],destination['field'])
        if identity in existing:continue
        # A deliberate "unknown" is an answer even though the scoring projector
        # removes its manual row. Restore display metadata only; unasked pose
        # gaps and facts from stale/removed photo owners stay absent.
        manual.append(dict(slot_no=identity[0],photo_id=owner,scope=identity[2],field=identity[3],value='UNKNOWN',source='INTERVIEW'))
        existing.add(identity)
    for m in manual:
        origin=trace.lookup('manual',m.get('value'),scope=m.get('scope'),field=m.get('field'),photo_id=m.get('photo_id'))
        if m.get('value') in (None, '', 'UNKNOWN') and not origin:
            continue
        origin=origin or (SOURCE_PLAIN.get(m.get('source'),m.get('source') or ''),note((m.get('evidence') or {}).get('text')))
        key = (m.get('slot_no'), m.get('field'), json.dumps(m.get('value')), *origin)
        if key not in groups:
            groups[key] = []
            order.append(key)
        groups[key].append(m.get('scope'))
    rows, said_no = [], {}
    for key in order:
        slot_no, field, value_json, src, memo = key
        value, scopes = json.loads(value_json), groups[key]
        origin = (src, memo)
        if value in (None, '', 'UNKNOWN') and not any(isinstance(item, str) and item.strip() for item in origin):
            continue
        scope = '양쪽' if {'LEFT', 'RIGHT'} <= set(scopes) else SIDE.get(scopes[0], scopes[0])
        label = ('' if scope == '공통' else scope + ' ') + MANUAL.get(field, field)
        photo = names.get(slot_no, f'사진 {slot_no}')
        if value == 'NO':
            said_no.setdefault((slot_no, src, memo), []).append(label)
            continue
        shown = '모름' if value in (None, 'UNKNOWN') else value_label(field, value)
        rows.append([name, '자세 입력', f'{photo} · {label}', shown, SOURCE_PLAIN.get(src, src or ''), memo])
    for (slot_no, src, memo), labels in said_no.items():
        rows.append([name, '자세 입력', f"{names.get(slot_no, '사진 ' + str(slot_no))} · 아니오로 기록한 항목", ', '.join(labels), SOURCE_PLAIN.get(src, src or ''),
                     memo or '아니오로 입력한 관찰 항목이에요'])
    return rows


def _inputs(c):
    rows = []
    for t in c['tasks']:
        name, source = t['name'], t['source']
        trace=InputTrace(source)
        cond = source.get('conditions') or {}
        ev = cond.get('evidence') or {}
        for key, label, unit in CONDITIONS:
            value=cond.get(key)
            origin=trace.lookup('conditions',value,field=key)
            if value not in (None, '', 'UNKNOWN') or origin:
                shown=with_unit(value,unit) if value is not None else '모름'
                rows.append([name, '작업 조건', label, shown, *(origin or (_source(ev),note(ev.get('text'))))])
        rows += _legal_rows(name, source) + _capture_rows(name, source) + _manual_rows(name, source) + _estimated_rows(name,source,t.get('analysis') or {})
    if not rows:
        return None
    has_provenance = any(any(isinstance(row[index], str) and row[index].strip() for index in (4, 5)) for row in rows)
    rows = [row[:3] + [f"{row[3]} · {' · '.join(str(item).strip() for item in row[4:6] if isinstance(item, str) and item.strip())}" if any(isinstance(item, str) and item.strip() for item in row[4:6]) else row[3]] for row in rows]
    columns, widths = ['작업', '구분', '항목', '값'], [22, 22, 52, 100]
    lead = '계산에 쓴 값이에요.'
    if has_provenance:
        lead = '계산에 쓴 값마다 입력 방법과 근거를 함께 적었어요.'
    return _sheet('입력한 값', lead, [
        _table(columns, rows, widths)], [])


# ----- 사진 자세
def _estimated_rows(name,source,analysis):
    from ergo.intake.photo_facts import estimated_photo_inputs
    names=_slot_names(source);rows=[]
    for slot in (source.get('capture') or {}).get('slots',[]):
        reba=_owned_measurement((analysis.get('reba') or {}).get('slots') or [],slot) or {}
        current=reba.get('current_score') or reba.get('score_so_far') or {}
        refs=current.get('measurement_refs') or [] if current.get('kind')!='CONFIRMED' else []
        for item in estimated_photo_inputs(source,slot):
            method=item.get('measurement_method') or (item.get('photo_proof') or {}).get('measurement_method')
            used=any(ref.get('scope')==item['scope'] and ref.get('field')==item['field'] and ref.get('value')==item['value'] and ref.get('measurement_method')==method for ref in refs)
            confidence=item.get('vision_confidence')
            notes=['추정값 · 사람이 확인한 입력과 구분', '현재 REBA 초안에 사용' if used else '현재 REBA 점수에 사용하지 않음']
            if type(confidence) in (int,float) and math.isfinite(confidence):notes.append(f'사진 관찰 확신도 {round(confidence*100)}%')
            proof=(item.get('vision_proof') or {}).get('evidence') or item.get('measurement_reason') or item.get('quote')
            if proof:notes.append(note(proof))
            label=names.get(slot.get('slot_no'),'등록한 사진')+' · '+('' if item['scope']=='COMMON' else SIDE[item['scope']]+' ')+MANUAL.get(item['field'],'자세 항목')
            rows.append([name,'사진 자세 추정',label,value_label(item['field'],item['value']),'AI 사진 추정' if item['source']=='VISION' else '사진 자동 측정 추정',' · '.join(notes)])
    return rows


def _world_angle_used(reba_slot,angle):
    current=reba_slot.get('current_score') or reba_slot.get('score_so_far') or {}
    value=angle.get('value_deg')
    if (current.get('kind')=='CONFIRMED' or type(value) not in (int,float) or not math.isfinite(value) or
            angle.get('coordinate_space','INFERRED_WORLD_3D')!='INFERRED_WORLD_3D'):return False
    return any(ref.get('coordinate_space')=='INFERRED_WORLD_3D' and ref.get('used_for_reba') is True and
               ref.get('side')==angle.get('side') and ref.get('angle_code')==angle.get('angle_code') and
               type(ref.get('value_deg')) in (int,float) and math.isfinite(ref['value_deg']) and
               ref['value_deg'] in (value,round(value,1))  # Stored quick_assess evidence precision.
               for item in current.get('measurement_refs') or [] for ref in item.get('angles') or [])


def _posture(c):
    score_rows, reba_rows, angle_rows, tag_rows = [], [], [], []
    for t in c['tasks']:
        a = t['analysis']
        if not a:
            continue
        names = _slot_names(t['source'])
        reba = a.get('reba') or {}
        representative = (reba.get('summary') or {}).get('representative_slot_no')
        reba_rows_owned,rejected_reba=_owned_rows(reba.get('slots', []),t['source'])
        if rejected_reba:
            angle_rows.append([t['name'],'등록 사진','','사진 연결 확인 필요','','사진과 REBA 결과의 소유 정보가 맞지 않아 해당 결과를 표시하지 않았어요.'])
        for r in reba_rows_owned:
            no = r.get('slot_no')
            label = names.get(no, f'사진 {no}')
            current = project_current_score(dict(slots=[r], summary=dict(
                current_score=r.get('current_score'), total_slot_count=1,
                complete_count=int(r.get('total') is not None))))
            current_components=(current or {}).get('components') or (r.get('score_so_far') or {}).get('components') or {}
            if current:
                basis = {'CONFIRMED': '확인 완료', 'WITH_ASSUMPTIONS': '확인 전 항목 포함', 'ASSUMED_REFERENCE': '가정 기준 · 측정 확인 필요'}.get(current.get('kind'), '확인 전')
                score_rows.append([t['name'], label, f"{current['total']}점", basis, _measurement_text(a, no)])
            for side in ('left', 'right'):
                s = r.get(side) or {}
                if not s:
                    continue
                components=current_components.get(side) or {}
                value=lambda key: s.get(key) if s.get(key) is not None else components.get(key)
                remarks = []
                if no == representative:
                    remarks.append('대표 사진')
                if r.get('selected_side') == side.upper():
                    remarks.append('두 쪽 중 높은 쪽')
                if s.get('review_reasons'):
                    remarks.append('확인: ' + ', '.join(reason_label(x) for x in s['review_reasons']))
                if r.get('score_so_far') and s.get('total') is None:
                    remarks.append(f"확정 전 {r['score_so_far'][side]}점 (가정 {len(r['score_so_far']['assumed'])}개 포함)")
                side_total = value('total')
                if side_total is None:
                    side_total = (r.get('score_so_far') or {}).get(side)
                reba_rows.append([t['name'], label, SIDE[side.upper()], value('trunk'), value('neck'), value('legs'), value('upper_arm'), value('lower_arm'), value('wrist'),
                                  value('load_score'), value('coupling_score'), value('activity_score'), side_total if side_total is not None else '확인 전',
                                  say(s.get('risk') or (reba_risk(side_total) if side_total is not None else None)), ' · '.join(remarks)])
        floor = ((a['snapshot'].get('settings') or {}).get('pose_model') or {}).get('confidence_min', 0.5)
        pose_rows_owned,rejected_pose=_owned_rows((a.get('pose') or {}).get('slots', []),t['source'])
        if rejected_pose:
            angle_rows.append([t['name'],'등록 사진','','사진 연결 확인 필요','','사진과 자세 측정 결과의 소유 정보가 맞지 않아 해당 측정값을 표시하지 않았어요.'])
        for p in pose_rows_owned:
            label = names.get(p.get('slot_no'), f"사진 {p.get('slot_no')}")
            owner=next((slot for slot in (t['source'].get('capture') or {}).get('slots',[]) if slot.get('slot_no')==p.get('slot_no')),p)
            current_reba=_owned_measurement(reba_rows_owned,owner) or {}
            engine=p.get('engine') or {}
            if engine:
                angle_rows.append([t['name'],label,'','자세 추론 모델',engine.get('name',''),f"관절 {len(p.get('points',[]))}개 · 모델 버전 {engine.get('version','')}"])
            for angle in p.get('world_angles',[]):
                used=_world_angle_used(current_reba,angle)
                notes=['단안 사진에서 추정한 각도', '현재 REBA 초안에 사용' if used else '현재 REBA 점수에 사용하지 않음']
                if angle.get('diagnostic'):notes.append(angle['diagnostic'])
                if angle.get('value_deg') is not None and (angle.get('min_confidence') or 0)<floor:notes.append('관절이 잘 안 보여 참고용이에요')
                angle_rows.append([t['name'],label,SIDE.get(angle.get('side'),''),'3D 추정 '+(ANGLE.get(angle.get('angle_code')) or angle.get('label') or '분절 각도'),
                                   round(angle['value_deg'],1) if angle.get('value_deg') is not None else '측정 불가',' · '.join(notes)])
            unread = 0
            for angle in p.get('angles', []):
                if angle.get('value_deg') is None:
                    unread += 1
                    continue
                weak = (angle.get('min_confidence') or 0) < floor
                angle_rows.append([t['name'], label, SIDE.get(angle.get('side'), angle.get('side')), ANGLE.get(angle.get('angle_code'), angle.get('angle_code')),
                                   round(angle['value_deg'], 1), '관절이 잘 안 보여 참고용이에요' if weak else ''])
            safe_diagnostics = {
                'MODEL_ERROR': '자세 분석을 끝내지 못했어요. 사진과 자세 모델 설정을 확인해 주세요.',
                'UNREADABLE_FILE': '사진 파일을 읽지 못했어요. 사진을 다시 선택해 주세요.',
            }
            problems = ' / '.join(
                safe_diagnostics.get(d.get('code'), d.get('message', ''))
                for d in p.get('diagnostics', [])
                if safe_diagnostics.get(d.get('code'), d.get('message', ''))
            )
            if unread or problems:
                typed = any(m.get('slot_no') == p.get('slot_no') for m in t['source'].get('manual') or [])
                angle_rows.append([t['name'], label, '', '읽지 못한 항목', f'{unread}개' if unread else '',
                                   (problems or '관절이 잘 안 보이거나 사진 밖이에요') + (' · 점수 계산에는 직접 확인한 값이 쓰였어요(입력한 값 시트 참고)' if typed else '')])
        pose_status = (a.get('pose') or {}).get('status')
        slot_tags = a.get('slot_tags') or []
        for tag in a.get('tags') or []:
            observed_count = tag.get('observed_count') or 0
            yes_count = tag.get('yes_count') or 0
            manual_count = tag.get('manual_observed_count')
            if manual_count is None:
                manual_count = sum(
                    item.get('tag') == tag.get('tag') and item.get('source') == 'MANUAL' and item.get('value') in ('YES', 'NO')
                    for item in slot_tags
                )
            if pose_status == 'FAILED':
                # A failed pose run cannot contribute angle-based observations. Keep only
                # investigator-entered observations so a model failure cannot become 0%.
                manual_rows = [
                    item for item in slot_tags
                    if item.get('tag') == tag.get('tag') and item.get('source') == 'MANUAL' and item.get('value') in ('YES', 'NO')
                ]
                if manual_rows:
                    observed_count = len(manual_rows)
                    yes_count = sum(item.get('value') == 'YES' for item in manual_rows)
                    manual_count = observed_count
                elif manual_count == observed_count and observed_count:
                    # Older snapshots may only store the summary, but can still prove that
                    # every observation came from a person.
                    pass
                else:
                    continue
            if observed_count:
                if manual_count is None:
                    method = '확인 방식 기록 없음'
                elif manual_count >= observed_count:
                    method = '조사자가 직접 확인'
                elif manual_count:
                    method = '사진 각도·조사자 직접 확인'
                else:
                    method = '사진 각도에서 확인'
                tag_rows.append([t['name'], TAG.get(tag['tag'], tag['tag']), yes_count, observed_count,
                                 f"{round(100 * yes_count / observed_count)}%", method])
    tables = []
    if score_rows:
        tables.append(_table(['작업', '사진', 'REBA 현재 점수', '계산 기준', '측정 관절·신뢰도'], score_rows,
                             [22, 24, 18, 32, 60], '사진별 현재 점수와 측정 신뢰도'))
    if reba_rows:
        tables.append(_table(['작업', '사진', '쪽', '몸통', '목', '다리', '위팔', '아래팔', '손목', '하중 가산', '손잡이 가산', '활동 가산', '합계 점수', '위험도', '비고'], reba_rows,
                             [22, 18, 10, 8, 8, 8, 8, 10, 8, 12, 12, 12, 12, 12, 40], '사진별 REBA 점수 (점수가 높을수록 몸에 부담이 커요)'))
    if angle_rows:
        tables.append(_table(['작업', '사진', '쪽', '항목', '각도(°) 또는 값', '비고'], angle_rows, [22, 18, 10, 30, 18, 40], '사진에서 읽은 각도'))
    if tag_rows:
        tables.append(_table(['작업', '자세', '보인 사진 수', '확인한 사진 수', '비율', '확인 방식'], tag_rows, [22, 30, 14, 16, 10, 26], '자세 표시 (사진 몇 장에서 보였는지, 하루 시간이 아니에요)'))
    if not tables:
        return None
    return _sheet('자세 분석(REBA)', '사진에서 읽은 자세와 REBA 점수를 자세히 적은 표예요. REBA는 몸의 각 부위 자세를 점수로 매겨 몸에 가는 부담을 보는 방법이고, 조사 결과의 3-1 결과표가 이 값을 요약해요.', tables, [])


# ----- 확인사항
def _explanations(c):
    kinds = {'MODEL': 'AI가 쓴 설명', 'INVESTIGATOR': '조사자가 고친 설명', 'FALLBACK': '기본 설명(AI를 쓰지 못했어요)'}
    rows = []
    for t in c['tasks']:
        analysis = t['analysis']
        if not analysis or currentness(t['task'], analysis) != 'CURRENT':
            continue
        for ai in analysis.get('ai') or []:
            if ai.get('is_active') and ai.get('applied_text') and ai.get('applied_at') and (ai.get('source_current') is True or ai.get('confirmation_current') is True):
                rows.append([t['name'], kinds.get(ai.get('applied_kind'), '설명'), kst(ai.get('applied_at')), user_text(ai['applied_text'])])
    if not rows:
        return None
    return _sheet('결과 설명', '조사자가 확인해 확정한 설명이에요. 확정한 시각과 문장을 기록하며, 설명은 계산 결과와 판정을 바꾸지 않아요.', [_table(['작업', '설명 종류', '확정 시각', '확정한 설명'], rows, [24, 26, 24, 110])], [])


def _human_review(c):
    review = c['survey'].get('review') or {}
    rows = []
    for task in c['tasks']:
        if task['item'].get('review_status') != 'REVIEWED_CURRENT':
            continue
        rows.append([task['name'], '검토 완료', review.get('reviewer') or '',
                     kst(review.get('reviewed_at')) or '', review.get('note') or ''])
    if not rows:
        return None
    return _sheet('사람 검토', '현재 작업 입력과 분석을 확인한 조사자의 검토 기록이에요.',
                  [_table(['작업명', '검토 상태', '검토자', '검토 시각', '메모'], rows, [32, 18, 24, 24, 60])], [])


# ----- 개선 전후 비교 (only when a comparison was chosen)
MINOR = ('.evidence.', '.photo_id', '.slot_no')
CAPTURE_FIELDS = {'camera_side': '찍은 방향', 'forward_direction': '작업자가 보는 방향', 'side_view_verified': '옆모습 사진으로 확인함', 'analysis_target': '분석에 사용함',
                  'load_state': '들고 있는 물건', 'measured_load_kg': '든 물건 무게', 'single_person': '한 사람만 나옴', 'full_frame': '전신이 나옴', 'normal_work': '평소 작업 모습임'}


def change_value(path, value):
    """A before/after value in the words the person saw (posture choices by name, numbers with their unit)."""
    parts = str(path).split('.')
    if parts[0] == 'manual' and len(parts) >= 5 and parts[-1] == 'value':
        return value_label(parts[3], value) or '없음'
    if parts[0] == 'capture' and parts[-1] == 'camera_side':
        return CAMERA.get(value, say(value)) or '없음'
    if parts[0] == 'capture' and parts[-1] == 'forward_direction':
        return FACING.get(value, say(value)) or '없음'
    return (with_unit(value, unit_for(path)) if value is not None else '') or '없음'


def change_label(path):
    """A stored field path as words, or None for bookkeeping (evidence time, photo assignment) that is not a real input change."""
    parts = str(path).split('.')
    if any(m in '.' + path + ('.' if not path.endswith('.') else '') for m in MINOR) or parts[-1] in ('observed_at', 'photo_id', 'slot_no', 'source') and parts[0] == 'manual':
        return None
    head = parts[0]
    if head == 'conditions':
        return '작업 조건 · ' + next((label for key, label, _ in CONDITIONS if key == parts[1]), RESULT_LABELS.get(parts[1], parts[1]))
    if head == 'analysis_scope':
        return '분석 범위 · ' + SCOPE_PLAIN.get(parts[1], parts[1])
    if head == 'legal' and len(parts) >= 3 and parts[1] == 'exposures':
        return f"{EXPOSURES.get(parts[2], parts[2])} 시간"
    if head == 'legal' and len(parts) >= 4 and parts[1] == 'criteria' and parts[2].isdigit():
        short = CRITERIA.get(int(parts[2]), f'{parts[2]}호')
        rest = parts[3:]
        if rest[0] == 'condition_present':
            return f'{short}: 이 작업을 한다'
        if rest[0] == 'rows' and len(rest) >= 3:
            return f'{short}: {input_label(rest[-1])}' + ('' if rest[1].startswith('quick-') else f' (조건 {rest[1]})')
        if rest[0] == 'union':
            return f'{short}: 중복을 제외한 합계'
        return f'{short}: {input_label(rest[-1])}'
    if head == 'manual' and len(parts) >= 5 and parts[-1] == 'value':
        return f'사진 {parts[1]} · {SIDE.get(parts[2], parts[2])} {MANUAL.get(parts[3], parts[3])}'
    if head == 'capture' and len(parts) >= 4 and parts[1] == 'slots' and parts[2].isdigit() and parts[-1] in CAPTURE_FIELDS:
        return f'사진 {parts[2]} · {CAPTURE_FIELDS[parts[-1]]}'
    if head == 'settings':
        return None
    return None


def _comparisons(c):
    comparisons = c['ov'].get('comparisons') or []
    if not comparisons:
        return None
    tables, notes = [], []
    for k, comp in enumerate(comparisons, 1):
        spec = comp['spec']
        title = f"비교 {k}: 분석 {spec['before_analysis_id']}(개선 전) → 분석 {spec['after_analysis_id']}(개선 후)"
        delta = comp.get('reba_max_delta')
        tables.append(_table(['메모', '점수 변화(개선 후 − 개선 전)', '계산 방식이 같음', '촬영 방식이 같음'],
                             [[spec.get('note') or '', '비교할 수 없어요' if delta is None else (f'+{delta}' if delta > 0 else str(delta)), say(comp.get('rule_compatible')), say(comp.get('sampling_compatible'))]],
                             [40, 26, 18, 18], title + ' · 요약'))
        diffs = []
        for d in comp.get('criteria', []):
            before_code, after_code = d.get('before_status'), d.get('after_status')
            if before_code in (None, 'NEEDS_INPUT') and after_code in (None, 'NEEDS_INPUT'):
                continue
            before = STATUS.get(before_code, before_code or '')
            after = STATUS.get(after_code, after_code or '')
            diffs.append([criterion_name(d['criterion_no']), before, after, '바뀜' if before != after else '같음'])
        tables.append(_table(['기준', '개선 전', '개선 후', '변화'], diffs, [40, 16, 16, 12], '기준별 변화'))
        changes = []
        for ch in comp.get('condition_changes', []):
            label = change_label(ch['field_path'])
            if label:
                changes.append([label, change_value(ch['field_path'], ch.get('before')), change_value(ch['field_path'], ch.get('after'))])
        if changes:
            tables.append(_table(['바뀐 입력', '개선 전', '개선 후'], changes, [56, 26, 26], '입력한 값이 바뀐 항목'))
        notes += comp.get('notes', [])
        minor = len(comp.get('condition_changes', [])) - len(changes)
        if minor > 0:
            notes.append(f'근거 메모·관찰 시각처럼 계산에 영향이 없는 변경 {minor}건은 이 시트에서 뺐어요.')
    return _sheet('개선 전후 비교', '개선 전과 개선 후 분석을 견준 결과예요. 표본 자세 변화의 참고값이며 질환 감소나 인과 효과를 입증하지 않아요.', tables, list(dict.fromkeys(notes)))


def plain_sheets(snapshot, ov):
    """Return the data-backed LOCO report and conditional form-assistance sheets used by both preview and Excel."""
    from .form import form_sheets
    c = _context(snapshot, ov)
    sheets = form_sheets(c) + [s for s in (_posture(c), _inputs(c)) if s]
    sheets += [s for s in (_human_review(c), _explanations(c), _comparisons(c)) if s]
    from .photo_vision import observation_sheet
    observed = observation_sheet(c)
    if observed:
        sheets.append(observed)
    return sheets
