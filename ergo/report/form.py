"""Build data-only LOCO workbook sheets from the selected immutable snapshot.

The workbook contains recorded survey/task inputs and results that can be computed from them.
Unasked fields and blank official-form templates are not exported. Preview and Excel share these sheet definitions.
"""
from .display import OPERATOR
from .labels import CRITERIA, EXPOSURES, HAZARD_KIND, REBA_ACTION, criterion_name, input_label
from .plain import SHEET_NOTES, SOURCE_PLAIN, _reba_text, _sheet, _table, kst, note, say, with_unit
from .input_trace import InputTrace
from ergo.engine.reba_scoring import project_current_score

FORM_TAB = '1F3A5F'
TICK, BOX = '☑', '☐'
WIDE = [22, 40, 22, 40, 16]
SYMPTOM_WIDTHS = [26, 18, 18, 18, 18, 18, 18]
DISEASE_CASE_NOTICE = '선택한 질환자 발생·업무상 질병 인정 사유는 안전보건규칙 제657조제2항제1호 조사 대상일 수 있어요(최근 1년 내 조사·개선 예외 확인). 해당 조사라면 제658조와 고용노동부고시 제2020-12호 제4조의 방법 및 별지 제1·2호서식을 활용해야 해요. 이 Excel은 기록 요약이며 법정 서식을 대체하지 않아요.'
SURVEY_TYPES = [('REGULAR', '정기조사'), ('INITIAL', '최초조사'), ('OCCASIONAL', '수시조사 (산업안전보건기준에 관한 규칙 제657조 제2항에 근거)')]
OCCASIONAL_CAUSES = [('DISEASE_CASE', '근골격계질환자가 발생했거나 업무상 질병으로 인정받은 경우'),
                     ('NEW_TASK_OR_EQUIPMENT', '근골격계부담작업에 해당하는 새로운 작업·설비를 도입한 경우'),
                     ('WORK_ENVIRONMENT_CHANGE', '근골격계부담작업에 해당하는 업무의 양과 작업공정 등 작업환경을 변경한 경우')]
ROLE = {'WORKER_REPRESENTATIVE': '근로자대표', 'AFFECTED_WORKER': '해당 근로자', 'BOTH': '근로자대표와 해당 근로자'}
SITUATION = [('equipment', '작업설비'), ('workload', '작업량'), ('speed', '작업속도'), ('work_pattern', '업무형태')]
SCALE_A = ['매우 쉬움', '쉬움', '약간 힘듦', '힘듦', '매우 힘듦']
SCALE_B = ['매우 가끔(년 2~3회)', '가끔(하루 또는 주 2~3일에 1회)', '자주(1일 4시간 미만)', '계속(1일 4시간 이상)', '초과근무 시간(1일 8시간 이상)']
FINAL = {'APPLICABLE': '부담작업', 'NOT_APPLICABLE': '부담작업 아님', 'NEEDS_INPUT': '입력 필요', 'NEEDS_REVIEW': '검토 필요', 'EXCLUDED': '제외'}
# The same rules as CRITERION_RULE, short enough for the summary matrix.
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


def _criterion_recorded(source, number):
    trace = InputTrace(source)
    legal = source.get('legal') or {}
    criterion = next((item for item in legal.get('criteria', []) if item.get('criterion_no') == number), {})
    state = criterion.get('condition_present')
    if trace.criterion_presence_recorded(criterion, number):
        return True
    if any(item.get('condition_code', '').startswith(f'C{number}_') and item.get('minutes') is not None
           for item in legal.get('exposures', [])):
        return True
    for field in ('unsupported', 'posture_restricted'):
        value = criterion.get(field)
        if value in ('YES', 'NO') or trace.lookup('criterion', value, field=field, criterion=number):
            return True
    complete = criterion.get('rows_complete')
    if trace.lookup('complete', complete, criterion=number):
        return True
    if any(value not in (None, '') for row in criterion.get('rows') or []
           for key, value in row.items() if key not in ('row_id', 'label', 'evidence')):
        return True
    for fact in trace.facts.values():
        definition = trace.catalogue.get(fact.get('target'))
        if definition and number in definition['destination'].get('criteria', []):
            return True
    return False


def _whole(value):
    return isinstance(value, int) and not isinstance(value, bool) and 1 <= value <= 5


# ----- 가·나. 조사 개요와 작업장 상황
def _participation_text(p):
    status = p.get('status')
    if status == 'NO':
        return '참여하지 않음'
    if status != 'YES':
        return ''
    parts = [ROLE.get(p.get('role'), ''), say(p.get('method')) if p.get('method') not in (None, 'UNKNOWN') else '',
             kst(p.get('date'), True) or '', f"참여자 {p['participant_code']}" if p.get('participant_code') else '', p.get('notes') or '']
    return '참여함' + (' · ' + ' · '.join(x for x in parts if x) if any(parts) else '')


def _support_overview(c):
    survey = c['survey']
    rows = []
    survey_type = dict(SURVEY_TYPES).get(survey.get('survey_type'))
    if survey_type and survey.get('survey_type_source') == 'USER':
        rows.append(['조사 구분', survey_type])
    if (survey.get('survey_type') == 'OCCASIONAL' and survey.get('survey_type_source') == 'USER'
            and survey.get('occasional_cause_source') == 'USER'):
        cause = dict(OCCASIONAL_CAUSES).get(survey.get('occasional_cause'))
        if cause:
            reason = survey.get('occasional_reason')
            rows.append(['수시조사 사유', cause + (f' · {reason}' if reason else '')])
    names = '\n'.join(t['name'] for t in c['tasks'] if t['name'])
    fields = [('조사 제목', survey.get('title')), ('조사 일시', kst(survey.get('survey_date'), True)), ('조사자', survey.get('investigator')),
              ('조사부서명', survey.get('department')), ('작업공정명', survey.get('process')),
              ('작업명', names), ('이전 조사일', kst(survey.get('previous_survey_date'), True))]
    rows.extend([[label, value] for label, value in fields if value not in (None, '')])
    participation = survey.get('participation') or {}
    if participation.get('status') in ('YES', 'NO'):
        rows.append(['근로자 참여', _participation_text(participation)])
    if not rows:
        return None
    return _table(['조사 항목', '기록'], rows, [28, 110], '조사 개요')


def _situation(c):
    situation = c['survey'].get('workplace_situation') or {}
    labels = dict(SITUATION)
    rows = []
    for key, label in SITUATION:
        status = situation.get(f'{key}_status', 'UNKNOWN')
        notes = (situation.get(f'{key}_notes') or '').strip()
        record = {'YES': '변경 있음', 'NO': '변경 없음'}.get(status, '')
        if notes:
            record = ' · '.join(x for x in (record, notes) if x)
        if record:
            rows.append([labels[key], record])
    if not rows:
        return None
    return _table(['항목', '기록'], rows, [28, 110], '작업장 상황')



def _step1(c, official=False):
    rows = []
    for task in c['tasks']:
        if task['name']:
            rows.append([task['name'], '작업명', task['name']])
        method = ((task['source'].get('conditions') or {}).get('method_description') or '').strip()
        if method:
            rows.append([task['name'], '작업 방법', method])
    if not rows:
        return []
    return [_table(['작업', '기록 항목', '기록'], rows, [36, 38, 100], '작업 정보')]

def _step2(c, official=False):
    rows = []
    for task in c['tasks']:
        conditions = task['source'].get('conditions') or {}
        intensity, frequency = conditions.get('work_intensity'), conditions.get('work_frequency')
        if _whole(intensity):
            rows.append([task['name'], '작업강도', intensity])
        if _whole(frequency):
            rows.append([task['name'], '작업빈도', frequency])
        if _whole(intensity) and _whole(frequency):
            rows.append([task['name'], '작업강도 × 작업빈도', intensity * frequency])
    if not rows:
        return []
    return [_table(['작업', '기록 항목', '값'], rows, [36, 58, 18], '작업강도와 작업빈도')]


def _photo_table(c, t):
    analysis = t['analysis']
    representative = (((analysis or {}).get('reba') or {}).get('summary') or {}).get('representative_slot_no')
    slot = next((item for item in (t['source'].get('capture') or {}).get('slots', [])
                 if item.get('slot_no') == representative), None) if representative is not None else None
    if slot is None or not c['snapshot'].get('include_representative'):
        return None
    label = slot.get('label') or f'사진 {representative}'
    return _form([['', '', '', '']], WIDE, f'대표 사진 · {label}',
                 merges=[[0, 0, 0, 3]], heights={0: 160},
                 photo=dict(task_id=t['task']['task_id'], row=0))


def _elements(j, criterion):
    """Only captured criterion values; unasked and unavailable fields are not workbook rows."""
    rows = (criterion or {}).get('rows') or []
    order = {r.get('row_id'): i for i, r in enumerate(rows, 1)}
    out = []
    for basis in j.get('basis') or []:
        code = basis.get('item_code') or ''
        parts = code.split('.')
        value = basis.get('value')
        if value in (None, '', 'UNKNOWN'):
            continue
        if parts[-1] in ('condition_present', 'rows_complete') or (parts[-2:] == ['union', 'value']):
            continue
        label = EXPOSURES.get(parts[1], input_label(code)) if parts[0] == 'exposures' and len(parts) > 1 else input_label(code)
        if parts[0] == 'criteria' and 'totals' in parts:
            label = '하루 합계 · ' + label
        if 'rows' in parts and parts.index('rows') + 2 < len(parts) and len(rows) > 1 and parts[parts.index('rows') + 1] in order:
            label += f" (조건 {order[parts[parts.index('rows') + 1]]})"
        threshold, operator = basis.get('threshold'), basis.get('operator')
        shown = with_unit(value, basis.get('unit'))
        rule = f"{with_unit(threshold, basis.get('unit'))} {OPERATOR.get(operator, '')}".strip() if threshold is not None else ''
        if threshold is None or isinstance(value, (bool, str)):
            mark = ''
        else:
            met = {'GE': value >= threshold, 'GT': value > threshold, 'LE': value <= threshold, 'LT': value < threshold, 'EQ': value == threshold}.get(operator)
            mark = '' if met is None else ('○' if met else 'X')
        out.append((label, shown, rule, mark))
    return out


def _cause(j, criterion):
    elements = _elements(j, criterion)
    return '\n'.join(f'{label}: {value}' for label, value, _, _ in elements if value)


def _hazard_rows(t):
    judgments = _judgments(t)
    if judgments is None:
        return []
    legal = {item.get('criterion_no'): item for item in (t['source'].get('legal') or {}).get('criteria', [])}
    rows = []
    for judgment in judgments:
        number, final = judgment['criterion_no'], _final(judgment)
        said_yes = any(str(basis.get('item_code', '')).endswith('condition_present')
                       and basis.get('value') == 'YES' for basis in judgment.get('basis') or [])
        if final not in ('APPLICABLE', 'NEEDS_REVIEW') or not said_yes:
            continue
        cause = _cause(judgment, legal.get(number))
        if cause:
            rows.append([f'{HAZARD_KIND[number]}({number}호)', cause])
    conditions = t['source'].get('conditions') or {}
    for label, key in (('관찰한 유해요인', 'hazard_factors'), ('유해요인의 원인', 'hazard_causes')):
        value = (conditions.get(key) or '').strip()
        if value:
            rows.append([label, value])
    return rows

def _reba_tables(t, official=False):
    a = t['analysis']
    reba = (a or {}).get('reba')
    if not reba:
        return []
    summary = reba.get('summary') or {}
    current = project_current_score(reba)
    result = _reba_text(a)
    if summary.get('total_slot_count'):
        result += f"\n분석 사진 {summary['total_slot_count']}장 기준"
    state = ('확인 완료' if current and current.get('kind') == 'CONFIRMED' and summary.get('full_max') is not None
             else '가정 기준 · 측정 확인 필요' if current and current.get('kind') == 'ASSUMED_REFERENCE'
             else '확인 전 항목 포함' if current else '사진 확인 필요')
    detail = _grid(_table(['작업·분석평가도구', '현재 점수와 측정 근거', '확인 상태'],
                          [['REBA(전신 자세 평가)', result, state]],
                          WIDE[:3], None if official else f"3-1. REBA 자세 평가 — {t['name']}"))
    if official:
        return [_page(_form([['작업명', t['name'], '단위작업명', t['name']]], WIDE,
                            f"3-1. 인간공학적 작업·분석 평가 결과표 — {t['name']}", labels=[0, 2])), detail]
    return [detail]



def _step3(c, official=False):
    tables = []
    for task in c['tasks']:
        conditions = task['source'].get('conditions') or {}
        if conditions.get('worker_code'):
            tables.append(_table(['작업', '작업자 코드'], [[task['name'], conditions['worker_code']]],
                                 [36, 44], f'작업자 정보 · {task["name"]}'))
        photo = _photo_table(c, task)
        if photo:
            tables.append(photo)
        hazards = _hazard_rows(task)
        if hazards:
            tables.append(_table(['유해요인', '기록된 원인·노출'], hazards, [36, 102],
                                 f'유해요인 기록 · {task["name"]}'))
        tables.extend(_reba_tables(task))
    return tables

def _symptom_summary(survey):
    symptom = survey.get('symptom_survey') or {}
    method = symptom.get('method')
    parts = [f'방법: {say(method)}' if method not in (None, 'UNKNOWN') else '',
             f"조사일 {kst(symptom.get('date'), True)}" if symptom.get('date') else '',
             f"응답자 {symptom['respondent_count']}명" if symptom.get('respondent_count') is not None else '',
             symptom.get('summary') or '']
    return ' · '.join(part for part in parts if part)

def _next_input_text(item):
    """Keep the original first action, grouping structured gaps for scanning."""
    if not item.get('next_inputs'): return ''
    first = item['next_inputs'][0]
    if first.get('kind') != 'MISSING_INPUT' or not first.get('field_paths'): return first['message']
    groups = {}
    for path in first['field_paths']:
        label = input_label(path)
        scope, separator, name = label.partition(' · ')
        if not separator: scope, name = '작업 조건', label
        if scope == '공통':
            field = path.split('.')[-1]
            scope = '목·몸통' if field.startswith(('neck_', 'trunk_')) else '다리' if field in ('legs_support', 'seated', 'knee_band') else '움직임·힘'
        scope = {'왼쪽': '왼팔·손목', '오른쪽': '오른팔·손목'}.get(scope, scope)
        groups.setdefault(scope, []).append(name)
    title = f"사진 {first['slot_no']} · 보완할 항목" if first.get('slot_no') is not None else '보완할 항목'
    lines = [title]
    for group, names in groups.items():
        lines.append(f'【{group}】')
        for start in range(0, len(names), 3):
            lines.append('• ' + ' / '.join(names[start:start + 3]))
    return '\n'.join(lines)



def _result(c, official=False):
    rows = []
    for task in c['tasks']:
        reba = ((task['analysis'] or {}).get('reba') or {})
        summary = reba.get('summary') or {}
        if summary.get('total_slot_count') or summary.get('full_max') is not None or summary.get('available_max') is not None:
            rows.append([task['name'], 'REBA 자세 점수', _reba_text(task['analysis'])])
            if summary.get('total_slot_count'):
                rows.append([task['name'], '양쪽 확정 계산 완료 사진', f"{summary.get('complete_count', 0)}장 / {summary['total_slot_count']}장"])
    symptom = _symptom_summary(c['survey'])
    if symptom:
        rows.append(['조사 전체', '증상조사 기록', symptom])
    if not rows:
        return []
    return [_table(['작업', '결과 항목', '기록'], rows, [36, 40, 62], '분석 결과')]

def main_sheet(c):
    tables = [_support_overview(c), _situation(c)]
    tables += _step1(c) + _step2(c) + _step3(c) + _result(c)
    tables = [table for table in tables if table]
    notes = ['이 파일에는 기록된 입력과 실제 분석 결과만 담아요. 공식 조사 서식의 완성 여부를 증명하지 않아요.']
    survey = c['survey']
    if (survey.get('survey_type') == 'OCCASIONAL' and survey.get('survey_type_source') == 'USER'
            and survey.get('occasional_cause_source') == 'USER' and survey.get('occasional_cause') == 'DISEASE_CASE'):
        notes.append(DISEASE_CASE_NOTICE)
    notes += ['"판정"은 REBA 점수에 대한 표준 해석이에요. 법정 판정이 아니에요.'] + SHEET_NOTES
    sheet = _sheet('조사 결과', '조사에 기록한 내용과 계산된 분석 결과예요.', tables, notes)
    return dict(sheet, tab_color=FORM_TAB)


def burden_sheet(c):
    rows = []
    for task in c['tasks']:
        judgments = _judgments(task)
        if judgments is None:
            continue
        for judgment in judgments:
            number = judgment.get('criterion_no')
            conclusion=(judgment.get('investigator') or {}).get('status') in ('APPLICABLE','NOT_APPLICABLE')
            if number not in CRITERIA or not (conclusion or _criterion_recorded(task['source'], number)):
                continue
            status = _final(judgment)
            if status not in ('APPLICABLE', 'NOT_APPLICABLE', 'EXCLUDED', 'NEEDS_REVIEW'):
                continue
            rows.append([task['name'], f'{criterion_name(number)}({number}호)', FINAL[status]])
    if not rows:
        return None
    sheet = _sheet('부담작업 해당 여부', '저장한 조사자 결론과 입력된 기준의 계산 결과를 표시해요.',
                   [_table(['작업', '기준', '적용 결과'], rows, [36, 54, 30])],
                   [SHEET_NOTES[1]])
    return dict(sheet, tab_color=FORM_TAB)

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
    symptom = c['survey'].get('symptom_survey') or {}
    responses = symptom.get('responses') or []
    rows = []
    for index, response in enumerate(responses, 1):
        response_rows = []
        for pair in _pair_rows(response):
            for label, value in ((pair[0], pair[1]), (pair[3], pair[4])):
                if value not in (None, '', '모름'):
                    response_rows.append([f"응답 {index} · {response.get('response_code') or index}", label, value])
        regions = response.get('regions') or {}
        for site, site_label in SITES:
            region = regions.get(site) or {}
            for key, label in (('side', '통증 부위'), ('duration', '통증 기간'),
                               ('severity', '아픈 정도'), ('last_week', '지난 1주일 증상')):
                value = region.get(key)
                if value not in (None, '', 'UNKNOWN'):
                    response_rows.append([f"응답 {index} · {response.get('response_code') or index}",
                                          f'{site_label} · {label}', _word(value)])
        if response_rows:
            rows.extend(response_rows)
    response_has_data = bool(rows)
    if symptom.get('method') not in (None, 'UNKNOWN'):
        rows.append(['조사 전체', '증상조사 방법', say(symptom['method'])])
    if symptom.get('date'):
        rows.append(['조사 전체', '증상조사 일시', kst(symptom['date'], True)])
    if symptom.get('summary'):
        rows.append(['조사 전체', '증상조사 요약', symptom['summary']])
    count = symptom.get('respondent_count')
    if count is not None and (not responses or response_has_data):
        rows.append(['조사 전체', '응답자 수', f'{count}명'])
    if not rows:
        return None
    sheet = _sheet('증상조사 요약', '기록된 증상조사 응답만 모았어요.',
                   [_table(['응답', '항목', '기록'], rows, [32, 48, 60])],
                   ['이 요약은 진단이나 질환 인정 여부를 결정하지 않아요.',
                    '개인 정보나 건강 정보가 포함되어 있으면 파일 접근을 제한하세요.'])
    return dict(sheet, tab_color=FORM_TAB)


def form_sheets(c):
    """Build only data-backed survey and analysis result sheets; never generate blank official-form templates."""
    sheets = [main_sheet(c)]
    burden = burden_sheet(c)
    if burden:
        sheets.append(burden)
    symptom = symptom_sheet(c)
    if symptom:
        sheets.append(symptom)
    return sheets
