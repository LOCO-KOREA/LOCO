"""Sheets that follow the official forms for the 유해요인조사, filled in from the stored snapshot.

The layout follows 별지 제1호서식 유해요인조사표 and 별지 제2호서식 근골격계질환 증상조사표 of 고용노동부고시 제2020-12호 as KOSHA GUIDE
E-G-1-2025 prints them (조사 구분, 작업장 상황, 작업조건 1~3단계, 3-1, 결과 요약), plus the checklist and the 해당 여부 판단 tables of its
appendices. Nothing is recalculated here: every value comes from the stored snapshot, and a cell the app has no value for stays
empty so the investigator can write it in. The sheets are the same plain descriptions the other sheets use, so the preview and the
file stay identical. Table keys beyond the plain ones: header (False hides the dark header row), labels / label_rows / label_cells
(form label cells), merges ([first_row, first_col, last_row, last_col]), bordered, heights, break (new printed page), photo ({task_id, row}).
"""
from .display import CURRENTNESS, EXCLUSION, OPERATOR, REVIEW
from .labels import CRITERIA, CRITERION_RULE, EXPOSURES, HAZARD_KIND, REBA_ACTION, criterion_name, input_label, reason_label
from .plain import SHEET_NOTES, SOURCE_PLAIN, _reba_text, _sheet, _table, kst, note, say, with_unit

FORM_TAB = '1F3A5F'
TICK, BOX = '☑', '☐'
WIDE = [22, 40, 22, 40, 16]
SYMPTOM_WIDTHS = [26, 18, 18, 18, 18, 18, 18]
SURVEY_TYPES = [('REGULAR', '정기조사'), ('INITIAL', '최초조사'), ('OCCASIONAL', '수시조사 (산업안전보건기준에 관한 규칙 제657조 제2항에 근거)')]
OCCASIONAL_CAUSES = [('DISEASE_CASE', '근골격계질환자가 발생했거나 업무상 질병으로 인정받은 경우'),
                     ('NEW_TASK_OR_EQUIPMENT', '근골격계부담작업에 해당하는 새로운 작업·설비를 도입한 경우'),
                     ('WORK_ENVIRONMENT_CHANGE', '근골격계부담작업에 해당하는 업무의 양과 작업공정 등 작업환경을 변경한 경우')]
ROLE = {'WORKER_REPRESENTATIVE': '근로자대표', 'AFFECTED_WORKER': '해당 근로자', 'BOTH': '근로자대표와 해당 근로자'}
SITUATION = [('equipment', '작업설비'), ('workload', '작업량'), ('speed', '작업속도'), ('work_pattern', '업무형태')]
SCALE_A = ['매우 쉬움', '쉬움', '약간 힘듦', '힘듦', '매우 힘듦']
SCALE_B = ['매우 가끔(년 2~3회)', '가끔(하루 또는 주 2~3일에 1회)', '자주(1일 4시간 미만)', '계속(1일 4시간 이상)', '초과근무 시간(1일 8시간 이상)']
FINAL = {'APPLICABLE': '부담작업', 'NOT_APPLICABLE': '부담작업 아님', 'NEEDS_INPUT': '입력 필요', 'NEEDS_REVIEW': '검토 필요', 'EXCLUDED': '제외'}
# The same rules as CRITERION_RULE, short enough for a narrow column of the checklist.
CHECK_RULE = {1: '하루 4시간 이상', 2: '하루 총 2시간 이상', 3: '하루 총 2시간 이상', 4: '하루 총 2시간 이상', 5: '하루 총 2시간 이상',
              6: '하루 총 2시간 이상\n(1kg 이상 집기, 2kg 이상 쥐기)', 7: '하루 총 2시간 이상\n(4.5kg 이상)', 8: '하루 10회 이상\n(25kg 이상)',
              9: '하루 25회 이상\n(10kg 이상)', 10: '하루 총 2시간 이상\n분당 2회 이상\n(4.5kg 이상)', 11: '하루 총 2시간 이상\n시간당 10회 이상'}
# Words for the symptom survey options (the standard form's own wording where it has one).
SYMPTOM = {'NONE': '없음', 'MALE': '남', 'FEMALE': '여', 'UNKNOWN': '모름', 'LEFT': '왼쪽', 'RIGHT': '오른쪽', 'BOTH': '양쪽',
           'LT_1_DAY': '1일 미만', 'DAY_TO_WEEK': '1일~1주일 미만', 'WEEK_TO_MONTH': '1주일~1개월 미만', 'MONTH_TO_6_MONTHS': '1개월~6개월 미만', 'GE_6_MONTHS': '6개월 이상',
           'MILD': '약한 통증', 'MODERATE': '중간 정도 통증', 'SEVERE': '심한 통증', 'VERY_SEVERE': '매우 심한 통증', 'YES': '예', 'NO': '아니오'}
SITES = [('neck', '목'), ('shoulder', '어깨'), ('arm_elbow', '팔/팔꿈치'), ('hand_wrist', '손/손목/손가락'), ('back', '허리'), ('leg_foot', '다리/발')]


def _word(value):
    return SYMPTOM.get(value, say(value)) if isinstance(value, str) else ('' if value is None else value)


def _box(on):
    return TICK if on else BOX


def _form(rows, widths, heading=None, labels=(), label_rows=(), label_cells=(), merges=(), heights=None, photo=None):
    """A form-style table: no dark header row, bordered, with label cells."""
    table = _table([''] * max(len(r) for r in rows), rows, widths, heading, header=False, bordered=True,
                   labels=list(labels), label_rows=list(label_rows), label_cells=[list(c) for c in label_cells], merges=[list(m) for m in merges])
    if heights:
        table['heights'] = dict(heights)
    if photo:
        table['photo'] = dict(photo)
    return table


def _grid(table):
    return dict(table, bordered=True)


def _page(table):
    """Start a new printed page before this table (the official form puts each part on its own page)."""
    return dict(table, **{'break': True})


def _judgments(t):
    return ((t['analysis'] or {}).get('judgment') or {}).get('judgments')


def _final(j):
    return j.get('effective_status') or j.get('computed_status')


def _burden_text(t):
    """The 부담작업(호) cell: the numbers that apply, and how many are still open."""
    judgments = _judgments(t)
    if judgments is None:
        return '계산 전'
    numbers = [j['criterion_no'] for j in judgments if _final(j) == 'APPLICABLE']
    open_count = sum(1 for j in judgments if _final(j) in ('NEEDS_INPUT', 'NEEDS_REVIEW'))
    text = ', '.join(str(n) for n in numbers) if numbers else ('확정된 호 없음' if open_count else '해당 없음')
    return text + (f'\n(미확정 {open_count}개)' if open_count else '')


def _whole(value):
    return isinstance(value, int) and not isinstance(value, bool) and 1 <= value <= 5


# ----- 가·나. 조사 개요와 작업장 상황
def _participation_text(p):
    status = p.get('status')
    if status == 'NO':
        return '참여하지 않음'
    if status != 'YES':
        return '입력 필요'
    parts = [ROLE.get(p.get('role'), ''), say(p.get('method')) if p.get('method') not in (None, 'UNKNOWN') else '',
             kst(p.get('date'), True) or '', f"참여자 {p['participant_code']}" if p.get('participant_code') else '', p.get('notes') or '']
    return '참여함' + (' · ' + ' · '.join(x for x in parts if x) if any(parts) else '')


def _cause_cell(survey):
    on, cause = survey.get('survey_type') == 'OCCASIONAL', survey.get('occasional_cause')
    lines = [f'{_box(on and cause == code)} {label}' for code, label in OCCASIONAL_CAUSES]
    extra = ' · '.join(x for x in ('기타' if on and cause == 'OTHER' else '', survey.get('occasional_reason') or '') if x)
    return '\n'.join(lines + ([f'사유: {extra}'] if extra else []))


def _overview(c):
    survey = c['survey']
    names = '\n'.join(t['name'] for t in c['tasks'])
    rows = [['조사 구분', '\n'.join(f"{_box(survey.get('survey_type') == code)} {label}" for code, label in SURVEY_TYPES), '수시조사 사유', _cause_cell(survey)],
            ['조사 일시', kst(survey.get('survey_date'), True) or '', '조사자', survey.get('investigator') or ''],
            ['조사부서명', survey.get('department') or '', '작업공정명', survey.get('process') or ''],
            ['작업명', names, '', ''],
            ['이전 조사일', kst(survey.get('previous_survey_date'), True) or '', '근로자 참여', _participation_text(survey.get('participation') or {})]]
    return _form(rows, WIDE, '가. 조사 개요', labels=[0, 2], merges=[[3, 1, 3, 3]])


def _situation(c):
    situation = c['survey'].get('workplace_situation') or {}
    rows = [['항목', '변경 여부', '주요 변경 내용', '']]
    for key, label in SITUATION:
        status = situation.get(f'{key}_status', 'UNKNOWN')
        notes = situation.get(f'{key}_notes') or ''
        rows.append([label, f"{_box(status == 'NO')} 변경 없음\n{_box(status == 'YES')} 변경 있음", notes if status == 'YES' and notes else ('' if status == 'NO' else '입력 필요'), ''])
    return _form(rows, WIDE, '나. 작업장 상황 조사', labels=[0], label_rows=[0], merges=[[r, 2, r, 3] for r in range(len(rows))])


# ----- 다. 작업조건 조사
def _step1(c):
    if not c['tasks']:
        return _page(_form([['작업명', '작업이 아직 없어요', '', '']], WIDE, '다. 작업조건 조사 (인간공학적 측면을 고려한 조사) — 1단계: 작업별 주요 작업내용', labels=[0], merges=[[0, 1, 0, 3]]))
    rows = []
    for t in c['tasks']:
        method = ((t['source'].get('conditions') or {}).get('method_description') or '').strip()
        rows.append(['작업명', t['name'], '', ''])
        rows.append(['작업내용\n(단위작업명)', f"1) {t['name']}" + (f'\n{method}' if method else ''), '', ''])
    return _page(_form(rows, WIDE, '다. 작업조건 조사 (인간공학적 측면을 고려한 조사) — 1단계: 작업별 주요 작업내용', labels=[0], merges=[[r, 1, r, 3] for r in range(len(rows))]))


def _step2(c):
    legend = _grid(_table(['작업강도(A)', '작업빈도(B)'], [[f'{i} · {a}', f'{i} · {b}'] for i, (a, b) in enumerate(zip(SCALE_A, SCALE_B), 1)], WIDE[:2], '2단계: 작업별 작업강도 및 작업빈도 (근로자 면담)'))
    rows = []
    for t in c['tasks']:
        cond = t['source'].get('conditions') or {}
        a, b = cond.get('work_intensity'), cond.get('work_frequency')
        rows.append([t['name'], _burden_text(t), a if _whole(a) else '', b if _whole(b) else '', a * b if _whole(a) and _whole(b) else ''])
    return [legend, _grid(_table(['단위작업명', '부담작업(호)', '작업강도(A)', '작업빈도(B)', '총점수(A×B)'], rows or [['', '', '', '', '']], WIDE))]


def _photo_table(c, t):
    a = t['analysis']
    representative = (((a or {}).get('reba') or {}).get('summary') or {}).get('representative_slot_no')
    slot = next((s for s in (t['source'].get('capture') or {}).get('slots', []) if s.get('slot_no') == representative), None) if representative is not None else None
    include = bool(c['snapshot'].get('include_representative'))
    label = (slot or {}).get('label') or f'사진 {representative}'
    heading = '단위작업별 사진 또는 그림' + (f' — 대표 사진: {label}' if slot else '')
    if slot is None:
        return _form([['대표 사진이 없어요', '', '', '']], WIDE, heading, merges=[[0, 0, 0, 3]])
    if not include:
        return _form([['대표 사진 이미지는 포함하지 않았어요.', '', '', '']], WIDE, heading, merges=[[0, 0, 0, 3]])
    return _form([['', '', '', '']], WIDE, heading, merges=[[0, 0, 0, 3]], heights={0: 160}, photo=dict(task_id=t['task']['task_id'], row=0))


def _elements(j, criterion):
    """One line per input behind a judgment: (what, the value, the rule it is held to, ○ / X / 입력 필요 / 입력 안 됨 / '').

    A blank is "입력 필요" only when the calculation says it still needs that input; a blank it does not need stays plain "입력 안 됨"."""
    rows = (criterion or {}).get('rows') or []
    order = {r.get('row_id'): i for i, r in enumerate(rows, 1)}
    needed = set(j.get('missing_fields') or [])
    out = []
    for b in j.get('basis') or []:
        code = b.get('item_code') or ''
        parts = code.split('.')
        if parts[-1] in ('condition_present', 'rows_complete') or (parts[-2:] == ['union', 'value'] and b.get('value') is None):
            continue
        label = EXPOSURES.get(parts[1], input_label(code)) if parts[0] == 'exposures' and len(parts) > 1 else input_label(code)
        if parts[-2:] == ['union', 'value']:
            label = '중복을 제외한 합계'
        if parts[0] == 'criteria' and 'totals' in parts:
            label = '하루 합계 · ' + label
        if 'rows' in parts and parts.index('rows') + 2 < len(parts) and len(rows) > 1 and parts[parts.index('rows') + 1] in order:
            label += f" (조건 {order[parts[parts.index('rows') + 1]]})"
        value, threshold, operator = b.get('value'), b.get('threshold'), b.get('operator')
        shown = '' if value is None else with_unit(value, b.get('unit'))
        rule = f"{with_unit(threshold, b.get('unit'))} {OPERATOR.get(operator, '')}".strip() if threshold is not None else ''
        if value is None:
            mark = '입력 필요' if code in needed else '입력 안 됨'
        elif threshold is None or isinstance(value, (bool, str)):
            mark = ''
        else:
            met = {'GE': value >= threshold, 'GT': value > threshold, 'LE': value <= threshold, 'LT': value < threshold, 'EQ': value == threshold}.get(operator)
            mark = '' if met is None else ('○' if met else 'X')
        out.append((label, shown, rule, mark))
    return out


def _cause(j, criterion):
    elements = _elements(j, criterion)
    lines = [f'{label}: {value}' for label, value, _, _ in elements if value]
    missing = [label for label, value, _, mark in elements if mark == '입력 필요']
    if missing:
        lines.append('입력 필요: ' + ', '.join(missing))
    return '\n'.join(lines) or '이 작업을 한다고 답함'


def _hazard_rows(t):
    judgments = _judgments(t)
    if judgments is None:
        return [['계산 전', '분석을 마치면 채워져요', '']]
    legal = {x.get('criterion_no'): x for x in (t['source'].get('legal') or {}).get('criteria', [])}
    rows = []
    for j in judgments:
        no, final = j['criterion_no'], _final(j)
        said_yes = any(str(b.get('item_code', '')).endswith('condition_present') and b.get('value') == 'YES' for b in j.get('basis') or [])
        if final == 'APPLICABLE' or (final in ('NEEDS_INPUT', 'NEEDS_REVIEW') and said_yes):
            inv = j.get('investigator') or {}
            remark = {'NEEDS_INPUT': '입력 필요', 'NEEDS_REVIEW': '검토 필요'}.get(final) or ('조사자 결론' if inv.get('status') and inv['status'] != j.get('computed_status') else '')
            rows.append([f'{HAZARD_KIND[no]}({no}호)', _cause(j, legal.get(no)), remark])
    cond = t['source'].get('conditions') or {}
    for label, key in (('관찰한 유해요인', 'hazard_factors'), ('유해요인의 원인', 'hazard_causes')):
        if cond.get(key):
            rows.append([label, cond[key], ''])
    return rows or [['해당하는 유해요인이 없어요', '', '']]


def _reba_tables(t):
    a = t['analysis']
    reba = (a or {}).get('reba')
    if not reba:
        return []
    summary = reba.get('summary') or {}
    top = summary.get('full_max') if summary.get('full_max') is not None else summary.get('available_max')
    slot = next((s for s in reba.get('slots', []) if s.get('total') == top), {}) if top is not None else {}
    result = _reba_text(a)
    if summary.get('total_slot_count'):
        result += f"\n사진 {summary['total_slot_count']}장 중 {summary.get('complete_count', 0)}장을 계산했어요"
    return [_page(_form([['작업명', t['name'], '단위작업명', t['name']]], WIDE, f"3-1. 인간공학적 작업·분석 평가 결과표 — {t['name']}", labels=[0, 2])),
            _grid(_table(['작업·분석평가도구', '평가결과', '판정'], [['REBA(전신 자세 평가)', result, REBA_ACTION.get(slot.get('risk'), '') if top is not None else '']], WIDE[:3]))]


def _step3(c):
    tables = []
    for t in c['tasks']:
        cond = t['source'].get('conditions') or {}
        tables.append(_page(_form([['작업명', t['name'], '근로자명', cond.get('worker_code') or '']], WIDE, f"3단계: 유해요인평가 — {t['name']}", labels=[0, 2])))
        tables.append(_photo_table(c, t))
        tables.append(_form([['단위작업명', t['name'], '부담작업(호)', _burden_text(t)]], WIDE, '작업별 관찰된 유해요인에 대한 원인분석', labels=[0, 2]))
        tables.append(_grid(_table(['유해요인', '발생 원인 또는 노출특징', '비고'], _hazard_rows(t), WIDE[:3])))
        tables += _reba_tables(t)
    return tables


# ----- 라. 유해요인 조사 결과
def _count_text(value):
    return '계산 전' if value is None else f'{value}개'


def _symptom_summary(survey):
    sym = survey.get('symptom_survey') or {}
    method = sym.get('method')
    if method in (None, 'UNKNOWN') and not sym.get('summary') and not sym.get('responses'):
        return '입력 필요'
    parts = [f'방법: {say(method)}' if method not in (None, 'UNKNOWN') else '', f"조사일 {kst(sym.get('date'), True)}" if sym.get('date') else '',
             f"응답자 {sym['respondent_count']}명" if sym.get('respondent_count') is not None else '', sym.get('summary') or '']
    return ' · '.join(x for x in parts if x)


def _result(c):
    rows = []
    for t in c['tasks']:
        item, counts = t['item'], t['item'].get('counts') or {}
        first = item['next_inputs'][0]['message'] if item['next_inputs'] else ''
        todo = f"입력이 더 필요한 기준 {_count_text(counts.get('needs_input_count'))} · 검토가 필요한 기준 {_count_text(counts.get('needs_review_count'))}" + (f'\n먼저 할 일: {first}' if first else '')
        rows.append([t['name'], _burden_text(t), _reba_text(t['analysis']), todo,
                     f"{CURRENTNESS.get(item.get('currentness'), item.get('currentness'))} · {REVIEW.get(item.get('review_status'), item.get('review_status'))}"])
    summary = _page(_grid(_table(['작업', '부담작업(호)', '자세 점수(REBA)', '더 입력·검토할 것', '결과 기준 · 검토 상태'], rows or [['', '', '', '', '']], WIDE, '라. 유해요인 조사 결과 (결과 요약)')))
    comment = _form([['증상조사\n(근골격계 징후·증상)', _symptom_summary(c['survey']), '', '', ''], ['조사자 종합 의견\n(직접 쓰는 칸)', '', '', '', '']], WIDE,
                    labels=[0], merges=[[0, 1, 0, 4], [1, 1, 1, 4]], heights={1: 110})
    return [summary, comment]


def main_sheet(c):
    lead = '고용노동부 고시 별지 제1호서식(유해요인조사표)의 칸 구성에 맞춰 입력한 값으로 채웠어요. 앱에 입력란이 없는 칸은 비워 두었으니 직접 써 넣으세요.'
    tables = [_overview(c), _situation(c), _step1(c)] + _step2(c) + _step3(c) + _result(c)
    notes = ['한국산업안전보건공단 KOSHA GUIDE E-G-1-2025(2025.3)가 싣고 있는 서식 구성을 따랐어요. 이 시트는 참고 자료이며 공식 서식 파일을 대신하지 않아요. 제출용이면 공식 서식에 옮겨 쓰세요.',
             '"판정"은 REBA 점수에 대한 표준 해석이에요. 법정 판정이 아니에요.'] + SHEET_NOTES
    sheet = _sheet('유해요인조사표', lead, tables, notes)
    return dict(sheet, tab_color=FORM_TAB)


# ----- 부담작업 해당 여부
def _extra_rows(j):
    """Rows added under a judgment only when there is something to say: the investigator's conclusion, what is missing, what to check."""
    rows = []
    inv = j.get('investigator') or {}
    if inv.get('status'):
        ev = inv.get('evidence') or {}
        memo = ' / '.join(x for x in (inv.get('reason'), note(ev.get('text')), SOURCE_PLAIN.get(ev.get('source')), f"검토자 {inv['reviewer']}" if inv.get('reviewer') else '', kst(inv.get('reviewed_at'))) if x)
        rows.append(['조사자 결론', f"{FINAL.get(inv['status'], inv['status'])} (계산 초안은 {FINAL.get(j.get('computed_status'), '')})" + (f'\n{memo}' if memo else ''), '', ''])
    if j.get('missing_fields'):
        rows.append(['더 필요한 입력', '\n'.join(input_label(x) for x in j['missing_fields']), '', ''])
    checks = [reason_label(x) for x in j.get('review_reasons', [])]
    if j.get('exclusion'):
        checks.insert(0, '제외 사유: ' + EXCLUSION.get(j['exclusion'], str(j['exclusion'])))
    if checks:
        rows.append(['확인할 점', '\n'.join(checks), '', ''])
    return rows


def _block(prefix, no, j, criterion):
    final = _final(j)
    heading = f"{prefix}{criterion_name(no)} → 최종 판단: {FINAL.get(final, '계산 전')}"
    basis = j.get('basis') or []
    answer = next((b.get('value') for b in basis if str(b.get('item_code', '')).endswith('condition_present')), None)
    rows = [[f'기준: {CRITERION_RULE[no]}', '', '', '']]
    if answer == 'NO':
        rows.append(['이 작업을 하지 않는다고 답함', '', '', ''])
    else:
        if answer != 'YES':
            rows.append(['이 작업을 하는지 아직 답하지 않음', '', '', '입력 필요'])
        rows += [[label, value, rule, mark] for label, value, rule, mark in _elements(j, criterion)]
    extra = _extra_rows(j)
    body = len(rows)
    rows += extra
    table = _table(['부담작업 요소', '입력한 값', '기준', '요소별 해당 여부'], rows, [40, 28, 28, 24], heading, bordered=True)
    table['merges'] = [[0, 0, 0, 3]] + [[body + i, 1, body + i, 3] for i in range(len(extra))]
    table['label_rows'] = [0]
    table['label_cells'] = [[body + i, 0] for i in range(len(extra))]
    return table


def burden_sheet(c):
    tables, many = [], len(c['tasks']) > 1
    for t in c['tasks']:
        judgments = _judgments(t)
        prefix = f"[{t['name']}] " if many else ''
        if judgments is None:
            tables.append(_table(['안내'], [[f'{prefix}판정 결과가 아직 없어요. 분석을 마치면 채워져요.']], [40]))
            continue
        legal = {x.get('criterion_no'): x for x in (t['source'].get('legal') or {}).get('criteria', [])}
        for no in range(1, 12):
            tables.append(_block(prefix, no, next((x for x in judgments if x.get('criterion_no') == no), {}), legal.get(no)))
    if not c['tasks']:
        tables.append(_table(['안내'], [['작업이 아직 없어요.']], [40]))
    lead = '11가지 근골격계부담작업 기준마다 입력한 값을 기준과 견준 결과예요. ○는 기준을 채운 것, X는 기준에 못 미친 것이에요.'
    sheet = _sheet('부담작업 해당 여부', lead, tables, [SHEET_NOTES[1]])
    return dict(sheet, tab_color=FORM_TAB)


# ----- 체크리스트
def _mark(j):
    return {'APPLICABLE': '○', 'NOT_APPLICABLE': 'X', 'NEEDS_INPUT': '입력 필요', 'NEEDS_REVIEW': '검토 필요', 'EXCLUDED': '제외'}.get(_final(j) if j else None, '')


def checklist_sheet(c):
    survey = c['survey']
    pair = lambda l1, v1, l2, v2: [l1, v1, '', '', '', '', l2, '', v2, '', '', '', '']
    info_rows = [pair('사업장명', '', '조사 일시', kst(survey.get('survey_date'), True) or ''), pair('공정명', survey.get('process') or '', '조사자', survey.get('investigator') or ''),
                 pair('공정 내용', '', '작업명', ' / '.join(t['name'] for t in c['tasks']))]
    merges = [m for r in range(3) for m in ([r, 1, r, 5], [r, 6, r, 7], [r, 8, r, 12])]
    widths = [22] + [14] * 11 + [18]
    info = _form(info_rows, widths, merges=merges, label_cells=[[r, col] for r in range(3) for col in (0, 6)])
    rows = [['기준(하루 노출)'] + [CHECK_RULE[no] for no in range(1, 12)] + ['']]
    for t in c['tasks']:
        judgments = _judgments(t)
        by = {j['criterion_no']: j for j in judgments or []}
        numbers = [no for no, j in by.items() if _final(j) == 'APPLICABLE']
        open_count = sum(1 for j in by.values() if _final(j) in ('NEEDS_INPUT', 'NEEDS_REVIEW'))
        if judgments is None:
            verdict = '계산 전'
        elif numbers:
            verdict = '부담작업' + (f'\n(미확정 {open_count}개)' if open_count else '')
        else:
            verdict = '미확정' if open_count else '부담작업 아님'
        rows.append([t['name']] + [_mark(by.get(no)) for no in range(1, 12)] + [verdict])
    matrix = _table(['작업\n(단위작업)'] + [f'{CRITERIA[no]}\n({no}호)' for no in range(1, 12)] + ['부담작업 여부'], rows, widths, bordered=True, label_rows=[0], labels=[0])
    lead = '작업마다 11가지 기준에 해당하는지 한눈에 보는 표예요. ○ 해당, X 해당하지 않음. 입력이나 검토가 더 필요하면 그렇게 적혀 있어요.'
    sheet = _sheet('체크리스트', lead, [info, matrix], [SHEET_NOTES[1]])
    return dict(sheet, tab_color=FORM_TAB)


# ----- 증상조사표
def _years_months(months):
    return '' if months is None else f'{months}개월'


def _pair_rows(response):
    sites = ', '.join(dict(SITES).get(x, x) for x in response.get('injury_sites') or [])
    injury = _word(response.get('injury_history')) + (f' ({sites})' if sites else '')
    pairs = [('성명(선택)', response.get('name') or '', '연령', '' if response.get('age_years') is None else f"만 {response['age_years']}세"),
             ('성별', _word(response.get('sex')), '현 직장 경력', _years_months(response.get('workplace_tenure_months'))),
             ('작업부서', response.get('department') or '', '수행 작업(직무)', response.get('job') or ''),
             ('현재 작업 내용', response.get('current_work') or '', '현재 작업 기간', _years_months(response.get('current_work_months'))),
             ('1일 근무시간', '' if response.get('daily_work_hours') is None else f"{response['daily_work_hours']}시간", '휴식', response.get('rest_breaks') or ''),
             ('이전 작업', response.get('previous_work') or '', '이전 작업 기간', _years_months(response.get('previous_work_months'))),
             ('규칙적인 여가·취미', response.get('leisure_activities') or '', '가사노동', _word(response.get('household_work'))),
             ('의사 진단 경험', _word(response.get('medical_history')), '사고·상해 경험', injury),
             ('현재 일의 육체적 부담(1~5)', '' if response.get('physical_burden') is None else response['physical_burden'], '지난 1년 작업 관련 증상', _word(response.get('work_related_symptoms_last_year')))]
    return [[a, b, '', c, d, '', ''] for a, b, c, d in pairs]


def symptom_sheet(c):
    survey = c['survey']
    responses = (survey.get('symptom_survey') or {}).get('responses') or []
    if not responses:
        return None
    tables = []
    for index, response in enumerate(responses, 1):
        rows = _pair_rows(response)
        merges = [m for r in range(len(rows)) for m in ([r, 1, r, 2], [r, 4, r, 6])]
        tables.append(_form(rows, SYMPTOM_WIDTHS, f"응답 {index} · {response.get('response_code') or ''}", merges=merges,
                            label_cells=[[r, col] for r in range(len(rows)) for col in (0, 3)]))
        regions = response.get('regions') or {}
        pain = [['통증의 구체적 부위'] + [_word((regions.get(site) or {}).get('side')) for site, _ in SITES],
                ['통증 기간'] + [_word((regions.get(site) or {}).get('duration')) for site, _ in SITES],
                ['아픈 정도'] + [_word((regions.get(site) or {}).get('severity')) for site, _ in SITES],
                ['지난 1주일 동안 증상'] + [_word((regions.get(site) or {}).get('last_week')) for site, _ in SITES]]
        tables.append(_grid(_table(['지난 1년 동안 통증 부위'] + [label for _, label in SITES], pain, SYMPTOM_WIDTHS, labels=[0])))
    lead = '근골격계질환 증상조사표(별지 제2호서식)의 칸 구성에 맞춰 익명 응답을 옮겼어요.'
    notes = ['이 앱에는 "지난 1년 동안 얼마나 자주"와 "통증으로 인한 조치" 문항을 입력하는 곳이 없어 표에 넣지 않았어요.',
             '응답 코드를 쓰기를 권해요. 개인을 알아볼 수 있는 정보나 건강 정보가 들어 있으면 파일을 아무나 열지 못하게 하세요.',
             '증상을 과대·과소 평가하지 마세요. 증상조사 결과는 질환을 인정하거나 부정하는 근거로 쓸 수 없어요.']
    sheet = _sheet('증상조사표', lead, tables, notes)
    return dict(sheet, tab_color=FORM_TAB)


def form_sheets(c):
    """The sheets that follow the official forms, in the order they go in the workbook."""
    return [main_sheet(c), burden_sheet(c), checklist_sheet(c)] + [s for s in (symptom_sheet(c),) if s]
