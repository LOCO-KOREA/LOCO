"""Render Korean workbooks from an immutable export snapshot."""
import json
from datetime import datetime, timedelta
from io import BytesIO
from .common import NOTICE, HEADERS, HEADER_LABELS, flatten
from .overview import overview
from .statutory_forms import _append_statutory_forms
from .labels import input_label, reason_label, investigator_text

def render(snapshot, destination):
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment
    from openpyxl.utils import get_column_letter
    from openpyxl.drawing.image import Image as ExcelImage
    from ergo.engine.images import read_image
    ov = overview(snapshot)
    rows = {key: [] for key in HEADERS}
    survey = snapshot['survey']
    representatives = []
    labels = {'worker_code': '작업자 코드', 'method_description': '작업 방법', 'work_posture': '작업 자세', 'work_height_cm': '작업 높이', 'daily_work_min': '하루 실제 작업시간', 'one_off': '일회성 여부', 'planned_duration_months': '예정 작업기간', 'annual_work_days': '연간 작업일수', 'condition_present': '해당 작업조건 존재', 'unsupported': '지지 여부', 'posture_restricted': '자세 변경 제한', 'pinch_mass_kg': '손가락 집기 중량', 'pinch_force_kg_equiv': '손가락 힘', 'single_hand_mass_kg': '한 손 중량', 'grip_force_kg_equiv': '쥐기 힘', 'load_mass_kg': '물체 중량', 'lift_count_day': '하루 들기 횟수', 'below_knee_count_day': '무릎 아래 횟수', 'above_shoulder_count_day': '어깨 위 횟수', 'extended_arm_count_day': '팔 뻗음 횟수', 'union_count_day': '중복 제거 횟수', 'lift_rate_min': '분당 들기 횟수', 'impact_rate_hour': '시간당 충격 횟수', 'minutes': '하루 노출시간', 'measured_load_kg': '측정 하중', 'analysis_target': '분석대상', 'camera_side': '카메라 측면', 'forward_direction': '작업자 전방', 'side_view_verified': '측면 확인', 'single_person': '단일 작업자', 'full_frame': '전신 확인', 'normal_work': '통상 작업', 'total': '합계', 'risk': '위험수준'}

    def unit_for(code):
        leaf = code.split('.')[-1]
        if leaf.endswith('value_deg'):
            return 'DEG'
        if leaf.endswith(('_px', 'x_px', 'y_px')):
            return 'PX'
        if leaf in ('confidence', 'min_confidence', 'sample_ratio'):
            return 'RATIO'
        if leaf in ('minutes', 'daily_work_min'):
            return 'MIN_DAY'
        if leaf in ('load_mass_kg', 'measured_load_kg', 'effective_load_kg', 'box_mass_kg', 'pinch_mass_kg', 'single_hand_mass_kg'):
            return 'KG'
        if leaf in ('pinch_force_kg_equiv', 'grip_force_kg_equiv'):
            return 'KG_EQUIV'
        if leaf.endswith('count_day') or leaf == 'lift_count_day':
            return 'COUNT_DAY'
        if leaf == 'lift_rate_min':
            return 'COUNT_MIN'
        if leaf == 'impact_rate_hour':
            return 'COUNT_HOUR'
        if leaf == 'planned_duration_months':
            return 'MONTH'
        if leaf == 'annual_work_days':
            return 'COUNT_YEAR'
        return None

    def result_rows(tid, aid, revision, group, value):
        if value is None:
            return
        flat = list(flatten(value, group))
        evidence_map = {}
        for code, v in flat:
            for suffix, field in [('.evidence.source', 'source'), ('.evidence.text', 'text'), ('.evidence.observed_at', 'observed_at')]:
                if code.endswith(suffix):
                    evidence_map.setdefault(code[:-len(suffix)], {})[field] = v
        for code, val in flat:
            if val is None:
                rendered = '미입력 또는 미계산'
            elif isinstance(val, (dict, list)):
                rendered = json.dumps(val, ensure_ascii=False, separators=(',', ':'))
            else:
                rendered = val
            candidates = [path for path in evidence_map if code.startswith(path + '.')]
            ev = evidence_map[max(candidates, key=len)] if candidates else {}
            label = labels.get(code.split('.')[-1], input_label(code))
            chunks = [str(rendered)[i:i + 30000] for i in range(0, len(str(rendered)), 30000)] if isinstance(rendered, str) and len(rendered) > 30000 else [rendered]
            for index, chunk in enumerate(chunks):
                item_code = code + (f'#part{index + 1}' if len(chunks) > 1 else '')
                rows['작업별 결과'].append([tid, aid, group, item_code, label + (' · 계속' if index else ''), chunk, unit_for(code), ev.get('source'), ev.get('text'), ev.get('observed_at')])
    for item in ov['tasks']:
        a = next((x for x in snapshot['analyses'] if x['task_id'] == item['task_id']), None)
        task = next((x for x in snapshot['tasks'] if x['task_id'] == item['task_id']))
        source = a['snapshot'] if a else task
        pose = a.get('pose') if a else None
        reba = a.get('reba') if a else None
        judgment = a.get('judgment') if a else None
        judgments = (judgment or {}).get('judgments', [])
        aid = item['analysis_id']
        tid = item['task_id']
        applicable = ', '.join((str(j['criterion_no']) + '호' for j in judgments if j.get('effective_status') == 'APPLICABLE')) if judgment else None
        rows['요약'].append([tid, item['task_name'], aid, item['currentness'], item['review_status'], applicable, item['counts']['needs_input_count'], item['counts']['needs_review_count'], item['next_inputs'][0]['message'] if item['next_inputs'] else None])
        for group, key, value in [('작업조건', 'conditions', source.get('conditions')), ('11개기준 입력', 'legal', source.get('legal')), ('사진·관찰', 'capture', source.get('capture')), ('수동 관찰', 'manual', source.get('manual')), ('분석 설정', 'settings', source.get('settings', {})), ('모듈 상태', 'module_states', (a or {}).get('module_states')), ('MoveNet', 'pose', pose), ('자세 기술태그', 'tags', dict(summary=(a or {}).get('tags'), slots=(a or {}).get('slot_tags')) if a else None), ('REBA', 'reba', reba), ('GPT 설명', 'ai', (a or {}).get('ai'))]:
            result_rows(tid, aid, item['input_revision'], group, value)
        capture = (source.get('capture') or {}).get('slots', [])
        v2 = source.get('schema_version') == '2.0'
        targets = [s for s in capture if s.get('photo_id') is not None and s.get('analysis_target', not v2)]
        for slot in targets:
            no = slot['slot_no']
            p = next((x for x in (pose or {}).get('slots', []) if x['slot_no'] == no), {})
            r = next((x for x in (reba or {}).get('slots', []) if x['slot_no'] == no), {})
            for group, value in [('사진별 포즈', p), ('사진별 REBA', r)]:
                result_rows(tid, aid, item['input_revision'], f'{group} · 행 {no}', value)
            if p.get('diagnostics'):
                for d in p['diagnostics']:
                    rows['확인사항'].append([tid, aid, 'POSE', no, None, 'REVIEW_REQUIRED', d.get('message'), d.get('code'), None])
            if r.get('missing_fields'):
                rows['확인사항'].append([tid, aid, 'REBA', no, None, 'MISSING_INPUT', ', '.join((input_label(x) for x in r['missing_fields'])), None, None])
            if r.get('left', {}).get('review_reasons') or r.get('right', {}).get('review_reasons'):
                reasons = list(dict.fromkeys(r.get('left', {}).get('review_reasons', []) + r.get('right', {}).get('review_reasons', [])))
                rows['확인사항'].append([tid, aid, 'REBA', no, None, 'REVIEW_REQUIRED', ', '.join((reason_label(x) for x in reasons)), None, None])
        for notice in item['next_inputs']:
            rows['확인사항'].append([tid, aid, notice['module'], notice['slot_no'], notice['criterion_no'], notice['kind'], notice['message'], ','.join(notice['reason_codes']) or None, None])
        source_criteria = {x['criterion_no']: x for x in (source.get('legal') or {}).get('criteria', [])}
        for no in range(1, 12):
            j = next((x for x in judgments if x['criterion_no'] == no), {})
            inv = j.get('investigator', {})
            ci = source_criteria.get(no, {})
            comparison = '\n'.join((' | '.join((str(b.get(k, '')) for k in ['item_code', 'value', 'unit', 'operator', 'threshold', 'source'])) for b in j.get('basis', []))) or None
            evidence_data = inv.get('evidence') or {}
            rows['판정 근거'].append([tid, aid, no, j.get('computed_status'), inv.get('status'), j.get('effective_status'), j.get('exclusion'), comparison, '\n'.join((input_label(x) for x in j.get('missing_fields', []))), '\n'.join((reason_label(x) for x in j.get('review_reasons', []))), j.get('source'), inv.get('reason'), evidence_data.get('text') or (ci.get('evidence') or {}).get('text'), inv.get('reviewer'), inv.get('reviewed_at')])
        representatives.append((tid, aid, source, a, reba))
    for comparison in ov['comparisons']:
        spec = comparison['spec']
        label = f'비교 #{spec['before_analysis_id']} → #{spec['after_analysis_id']}'
        if spec.get('note'):
            rows['확인사항'].append([None, None, 'COMPARISON', None, None, 'NOTE', spec['note'], None, None])
        for note in comparison['notes']:
            rows['확인사항'].append([None, None, 'COMPARISON', None, None, 'LIMITATION', note, None, None])
        rows['확인사항'].append([None, None, 'COMPARISON', None, None, 'SUMMARY', f'{label} · REBA 호환 {comparison['rule_compatible']} · 표본 호환 {comparison['sampling_compatible']} · 후−전 최대 점수 {comparison['reba_max_delta']}', None, None])
        for change in comparison['condition_changes']:
            rows['확인사항'].append([None, None, 'COMPARISON', None, None, 'CONDITION_CHANGE', f'{change['field_path']}: {change['before']} → {change['after']}', None, None])
        for diff in comparison['criteria']:
            rows['확인사항'].append([None, None, 'COMPARISON', None, diff['criterion_no'], 'CRITERION_CHANGE', f'{diff['before_status']} → {diff['after_status']} (계산 {diff['before_computed_status']} → {diff['after_computed_status']}; 조사자 {diff['before_investigator_status']} → {diff['after_investigator_status']})', None, None])
    situation = survey.get('workplace_situation') or {}
    participation = survey.get('participation') or {}
    symptoms = survey.get('symptom_survey') or {}
    for key, label in [('survey_type', '조사 구분'), ('occasional_cause', '수시 사유 유형'), ('occasional_reason', '수시 사유 상세'), ('previous_survey_date', '이전 조사일')]:
        if survey.get(key) is not None:
            rows['작업별 결과'].append([None, None, '조사 개요', key, label, survey.get(key), None, None, None, None])
    situation_labels = {'equipment_status': '설비 변경 여부', 'equipment_notes': '설비 변경 내용', 'workload_status': '작업량 변경 여부', 'workload_notes': '작업량 변경 내용', 'speed_status': '작업속도 변경 여부', 'speed_notes': '작업속도 변경 내용', 'work_pattern_status': '업무형태 변경 여부', 'work_pattern_notes': '업무형태 변경 내용'}
    for key, label in situation_labels.items():
        value = situation.get(key)
        rows['작업별 결과'].append([None, None, '작업장 상황', key, label, value, None, None, None, None])
    for key, label in [('status', '근로자 참여 여부'), ('role', '참여자 역할'), ('participant_code', '참여자 코드/표시명'), ('method', '참여 방법'), ('date', '참여 일자'), ('notes', '참여 의견')]:
        rows['작업별 결과'].append([None, None, '근로자 참여', key, label, participation.get(key), None, None, None, None])
    for key, label in [('method', '증상조사 방법'), ('date', '증상조사 일자'), ('respondent_count', '응답자 수'), ('summary', '증상조사 요약')]:
        rows['작업별 결과'].append([None, None, '증상조사', key, label, symptoms.get(key), None, None, None, None])
    for response in symptoms.get('responses') or []:
        rows['작업별 결과'].append([None, None, '증상 응답', response.get('response_code'), '증상조사 응답', json.dumps(response, ensure_ascii=False, separators=(',', ':')), None, 'WORKER_QUESTIONNAIRE', None, symptoms.get('date')])
    wb = Workbook()
    wb.remove(wb.active)
    exported = datetime.fromisoformat(snapshot['exported_at']) + timedelta(hours=9)
    exported = exported.replace(tzinfo=None)
    for message in ov.get('survey_followups', []):
        rows['확인사항'].append([None, None, 'SURVEY', None, None, 'MISSING_INPUT', message, 'SAFETY_RULES_657_658', None])
    for name, headers in HEADERS.items():
        ws = wb.create_sheet(name)
        ws.append(['LOCO 작업 자세 분석 보고서 — ' + name])
        ws['A1'].font = Font(name='맑은 고딕', size=17, bold=True, color='1F3A5F')
        ws.append(['조사 ID', survey['survey_id'], '보고서 버전', '2.0', '스키마 버전', '2.0', '출력 시각', exported])
        ws['H2'].number_format = 'yyyy-mm-dd hh:mm'
        ws.append(['조사', survey.get('title'), '조사자', survey.get('investigator'), '부서', survey.get('department'), '공정', survey.get('process')])
        ws.append(['조사일', datetime.fromisoformat(survey['survey_date']) if survey.get('survey_date') else None])
        ws['B4'].number_format = 'yyyy-mm-dd'
        ws.append(HEADER_LABELS[name])
        start = 5
        for row in rows[name]:
            chunks = max([1] + [(len(str(value)) + 29999) // 30000 for value in row if isinstance(value, str)])
            for index in range(chunks):
                part = [value[index * 30000:(index + 1) * 30000] if isinstance(value, str) and len(value) > 30000 else value for value in row]
                ws.append(part)
        end = max(start, ws.max_row)
        ws.auto_filter.ref = f'A{start}:{get_column_letter(len(headers))}{end}'
        ws.freeze_panes = 'D6'
        ws.print_title_rows = '1:5'
        ws.page_setup.orientation = 'landscape'
        for index, header in enumerate(headers, 1):
            ws.column_dimensions[get_column_letter(index)].width = 42 if header in ('message', 'comparison_values', 'evidence_text', 'investigator_evidence', 'reviewer_memo', 'first_next_input', 'label') else 22 if header in ('task_name', 'item_code') else 15
        for row in ws.iter_rows(min_row=1, max_row=end):
            for cell in row:
                if cell.row == 1:
                    continue
                cell.font = Font(name='맑은 고딕', size=11, color='FFFFFF' if cell.row == 5 else '25324A', bold=cell.row == 5)
                cell.fill = PatternFill('solid', fgColor='1F3A5F' if cell.row == 5 else 'F4F6F8' if cell.row % 2 == 0 else 'FFFFFF')
                cell.alignment = Alignment(vertical='top', wrap_text=True)
                if cell.row > 5:
                    if cell.value in ('NEEDS_INPUT', 'INCOMPLETE', 'MISSING_INPUT'):
                        cell.fill = PatternFill('solid', fgColor='FCE4D6')
                    elif cell.value in ('NEEDS_REVIEW', 'REVIEW_REQUIRED'):
                        cell.fill = PatternFill('solid', fgColor='FFF2CC')
                    if isinstance(cell.value, str):
                        cell.data_type = 's'
            if row[0].row > 5:
                ws.row_dimensions[row[0].row].height = 48
        ws.append([])
        ws.append([NOTICE])
        ws.append(['사진 표본 비율은 하루 노출시간이나 해당 확률이 아닙니다. 미완료 점수는 0점이 아니며, 조사자 결론은 법적 승인을 뜻하지 않습니다.'])
    result_ws = wb['작업별 결과']
    for tid, aid, source, a, reba in representatives:
        rep = (reba or {}).get('summary', {}).get('representative_slot_no')
        result_ws.append([])
        result_ws.append([f'작업 {tid} / 분석 {aid} 대표 사진 행 {(rep if rep is not None else '없음')}'])
        if rep is None:
            result_ws.append(['대표 사진 점수 없음'])
            continue
        slot = next((s for s in source['capture']['slots'] if s['slot_no'] == rep), None)
        result = next((r for r in (reba or {}).get('slots', []) if r['slot_no'] == rep), None)
        if slot is None or result is None:
            result_ws.append(['대표 사진 상세를 찾을 수 없습니다'])
            continue
        result_ws.append(['대표 행', rep, '표시명', slot.get('label'), '계산 최대', reba['summary'].get('available_max'), '대상 전체 최대', reba['summary'].get('full_max'), '대표 점수', result.get('total')])
        if snapshot.get('include_representative'):
            photo = next((p for p in source.get('photos', []) if p['photo_id'] == slot['photo_id']), None)
            try:
                if not photo:
                    raise FileNotFoundError('대표 사진 파일 메타데이터가 없습니다')
                with read_image(photo['file_path']) as image:
                    image.thumbnail((300, 240))
                    stream = BytesIO()
                    image.save(stream, format='PNG')
                    stream.seek(0)
                row = result_ws.max_row + 2
                result_ws.add_image(ExcelImage(stream), f'K{row}')
                result_ws.cell(row, 1, '대표 사진 미리보기')
            except Exception as error:
                result_ws.append(['대표 이미지 생략', str(error)])
        else:
            result_ws.append(['대표 이미지 제외'])
    if survey.get('survey_type') == 'OCCASIONAL' and survey.get('occasional_cause') == 'DISEASE_CASE':
        _append_statutory_forms(wb, snapshot)
    for ws in wb:
        for row in ws.iter_rows():
            for cell in row:
                if isinstance(cell.value, str):
                    cell.data_type = 's'
    wb.save(destination)
    return dict(file_path=destination, sheets=list(wb.sheetnames), overview=ov)
