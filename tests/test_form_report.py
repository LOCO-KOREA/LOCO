"""The sheets that follow the official 유해요인조사 forms: what goes in each form cell, and that the file and the preview agree."""
import re
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from openpyxl import load_workbook

from ergo.report.form import CHECK_RULE
from ergo.report.labels import CRITERION_RULE, HAZARD_KIND
from ergo.service import application
from tests.report_helpers import lifting_input, make_survey, run_analysis, update_survey

LAW_TEXT = Path(__file__).parent / 'fixtures' / '고시_제2020-12호_본문.txt'
NUMBER = re.compile(r'\d+(?:\.\d+)?')


def text_of(sheet):
    return [str(cell.value) for row in sheet.iter_rows() for cell in row if cell.value not in (None, '')]


def row_with(sheet, first):
    """The values of the first row whose first cell is `first`."""
    return next((tuple(cell.value for cell in row) for row in sheet.iter_rows() if row[0].value == first), None)


class FormWorkbook(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        patcher = patch.object(application, 'DB', str(Path(self.temp.name) / 'loco.db'))
        patcher.start()
        self.addCleanup(patcher.stop)
        self.addCleanup(self.temp.cleanup)
        self.survey = make_survey('양식 검증')
        self.task = application.dispatch('create_task', {'survey_id': self.survey['survey_id'], 'draft': lifting_input()})
        self.analysis = run_analysis(self.task)

    def export(self):
        destination = str(Path(self.temp.name) / 'report.xlsx')
        application.dispatch('export_excel', {'survey_id': self.survey['survey_id'], 'spec': {
            'analysis_ids': [], 'include_representative': False, 'comparisons': [], 'destination': destination}})
        return load_workbook(destination, data_only=False)

    def preview(self):
        return application.dispatch('preview_excel_sheets', {'survey_id': self.survey['survey_id']})['sheets']

    def rerun(self, **conditions):
        task = application.dispatch('get_task', {'task_id': self.task['task_id']})['task']
        updated = application.task_input(task)
        updated['conditions'].update(conditions)
        run_analysis(application.dispatch('save_task_input', {'task_id': task['task_id'], 'input': updated}))

    # ----- 가. 조사 개요
    def test_survey_kind_and_cause_are_boxes_that_follow_the_survey(self):
        sheet = self.export()['유해요인조사표']
        self.assertEqual(row_with(sheet, '조사 구분')[1], '☑ 정기조사\n☐ 최초조사\n☐ 수시조사 (산업안전보건기준에 관한 규칙 제657조 제2항에 근거)')
        self.assertNotIn('☑', row_with(sheet, '조사 구분')[3], 'no cause is ticked for a regular survey')
        update_survey(self.survey['survey_id'], survey_type='OCCASIONAL', occasional_cause='NEW_TASK_OR_EQUIPMENT', occasional_reason='새 컨베이어')
        row = row_with(self.export()['유해요인조사표'], '조사 구분')
        self.assertIn('☑ 수시조사', row[1])
        self.assertIn('☐ 정기조사', row[1])
        self.assertIn('☑ 근골격계부담작업에 해당하는 새로운 작업·설비를 도입한 경우', row[3])
        self.assertIn('☐ 근골격계질환자가 발생했거나 업무상 질병으로 인정받은 경우', row[3])
        self.assertIn('사유: 새 컨베이어', row[3])
        update_survey(self.survey['survey_id'], survey_type='INITIAL', occasional_cause=None, occasional_reason=None)
        self.assertIn('☑ 최초조사', row_with(self.export()['유해요인조사표'], '조사 구분')[1])

    def test_survey_facts_fill_the_overview_and_unknown_participation_is_asked_for(self):
        sheet = self.export()['유해요인조사표']
        self.assertEqual(row_with(sheet, '조사 일시')[1], '2026-10-23')
        self.assertEqual(row_with(sheet, '조사 일시')[3], '조사자')
        self.assertEqual(row_with(sheet, '조사부서명')[1], '팀')
        self.assertEqual(row_with(sheet, '조사부서명')[3], '공정')
        self.assertEqual(row_with(sheet, '작업명')[1], '상자 들기')
        self.assertEqual(row_with(sheet, '이전 조사일')[3], '입력 필요', 'participation was never recorded')
        update_survey(self.survey['survey_id'], participation=dict(status='YES', role='BOTH', method='MEETING', participant_code='P-7', date='2026-10-22', notes=''))
        self.assertEqual(row_with(self.export()['유해요인조사표'], '이전 조사일')[3], '참여함 · 근로자대표와 해당 근로자 · 회의 · 2026-10-22 · 참여자 P-7')

    # ----- 나. 작업장 상황 조사
    def test_workplace_situation_ticks_the_right_box_and_asks_for_what_is_unknown(self):
        update_survey(self.survey['survey_id'], workplace_situation=dict(equipment_status='NO', workload_status='YES', workload_notes='물량 증가', speed_status='UNKNOWN', work_pattern_status='YES', work_pattern_notes=''))
        sheet = self.export()['유해요인조사표']
        self.assertEqual(row_with(sheet, '작업설비')[1:3], ('☑ 변경 없음\n☐ 변경 있음', None))
        self.assertEqual(row_with(sheet, '작업량')[1:3], ('☐ 변경 없음\n☑ 변경 있음', '물량 증가'))
        self.assertEqual(row_with(sheet, '작업속도')[1:3], ('☐ 변경 없음\n☐ 변경 있음', '입력 필요'))
        self.assertEqual(row_with(sheet, '업무형태')[2], '입력 필요', 'a change with no summary still needs one')

    # ----- 다. 작업조건 조사
    def test_burden_numbers_and_the_intensity_times_frequency_score(self):
        table = lambda sheet: row_with(sheet, '상자 들기')
        sheet = self.export()['유해요인조사표']
        unit_row = next(r for r in sheet.iter_rows(values_only=True) if r[0] == '상자 들기' and r[1] == '1' and r[4] is None)
        self.assertEqual(unit_row[1:5], ('1', None, None, None), 'only keyboard work reaches its rule; the intensity and frequency are written by hand')
        self.rerun(work_intensity=3, work_frequency=4)
        unit_row = next(r for r in self.export()['유해요인조사표'].iter_rows(values_only=True) if r[0] == '상자 들기' and r[1] == '1')
        self.assertEqual(unit_row[1:5], ('1', 3, 4, 12))
        self.rerun(work_intensity=3, work_frequency=None)
        unit_row = next(r for r in self.export()['유해요인조사표'].iter_rows(values_only=True) if r[0] == '상자 들기' and r[1] == '1')
        self.assertEqual(unit_row[2:5], (3, None, None), 'no score without both numbers')

    def test_the_scale_table_is_the_forms_own(self):
        text = text_of(self.export()['유해요인조사표'])
        for phrase in ('1 · 매우 쉬움', '5 · 매우 힘듦', '1 · 매우 가끔(년 2~3회)', '3 · 자주(1일 4시간 미만)', '5 · 초과근무 시간(1일 8시간 이상)'):
            self.assertIn(phrase, text)

    def test_cause_rows_name_the_hazard_kind_and_the_value_that_caused_it(self):
        sheet = self.export()['유해요인조사표']
        row = row_with(sheet, '반복동작(1호)')
        self.assertEqual(row[1], '집중 키보드·마우스 사용: 240 분/일')
        self.assertIsNone(row_with(sheet, '과도한 힘(들기)(8호)'), 'a rule that is not reached is not listed as a hazard')
        self.assertEqual(HAZARD_KIND[8], '과도한 힘(들기)')

    def test_no_photo_and_no_score_say_so_instead_of_leaving_a_silent_gap(self):
        text = text_of(self.export()['유해요인조사표'])
        self.assertIn('대표 사진이 없어요', text)
        self.assertFalse(any('3-1.' in value for value in text), 'the REBA result table is only written when a score exists')

    # ----- 체크리스트
    def test_checklist_matrix_marks_each_rule_for_each_task(self):
        sheet = self.export()['체크리스트']
        header = row_with(sheet, '작업\n(단위작업)')
        self.assertEqual(header[1], '키보드·마우스 집중 입력\n(1호)')
        self.assertEqual(header[11], '손·무릎 충격\n(11호)')
        rules = row_with(sheet, '기준(하루 노출)')
        self.assertEqual(rules[1], '하루 4시간 이상')
        self.assertEqual(rules[8], '하루 10회 이상\n(25kg 이상)')
        marks = row_with(sheet, '상자 들기')
        self.assertEqual(marks[1], '○')
        self.assertEqual(marks[8], 'X')
        self.assertEqual(marks[12], '부담작업')
        self.assertEqual(row_with(sheet, '사업장명')[0], '사업장명', 'the form asks for a business name the app does not hold; the cell stays empty')

    # ----- 사진 없이 만든 파일도 양식의 틀은 같다
    def test_form_tables_are_drawn_as_forms_in_the_file(self):
        sheet = self.export()['유해요인조사표']
        label = next(c for row in sheet.iter_rows() for c in row if c.value == '조사 구분')
        self.assertTrue(label.font.bold)
        self.assertTrue(str(label.fill.fgColor.rgb).endswith('E6EBF2'))
        self.assertIsNotNone(label.border.left.style)
        self.assertGreater(len(sheet.merged_cells.ranges), 5)
        self.assertEqual(sheet.sheet_properties.tabColor.rgb[-6:], '1F3A5F')
        self.assertTrue(sheet.row_breaks.brk, 'each part of the form starts a new printed page')

    def test_merged_blocks_sit_on_the_rows_the_preview_says(self):
        """The preview tells which cells are merged relative to its table; the file must merge the same cells."""
        sheet = self.export()['유해요인조사표']
        preview = next(s for s in self.preview() if s['name'] == '유해요인조사표')
        overview = preview['tables'][0]
        self.assertEqual(overview['heading'], '가. 조사 개요')
        self.assertIs(overview['header'], False)
        first = next(cell.row for row in sheet.iter_rows() for cell in row if cell.value == '조사 구분')
        for r1, c1, r2, c2 in overview['merges']:
            self.assertIn(f'{chr(66)}{first + r1}:{chr(65 + c2)}{first + r2}', {str(m) for m in sheet.merged_cells.ranges})

    def test_the_preview_marks_form_cells_for_the_screen(self):
        preview = next(s for s in self.preview() if s['name'] == '체크리스트')
        info, matrix = preview['tables']
        self.assertIs(info['header'], False)
        self.assertTrue(info['bordered'])
        self.assertEqual(matrix['label_rows'], [0])
        self.assertEqual(len(matrix['columns']), 13)

    # ----- 부담작업 해당 여부
    def test_open_inputs_are_only_flagged_when_the_calculation_needs_them(self):
        sheet = self.export()['부담작업 해당 여부']
        text = text_of(sheet)
        # keyboard work is the only reached rule here; nothing else is open, so no cell may ask for input
        self.assertNotIn('입력 필요', text)
        self.assertIn('○', text)

    # ----- 여러 작업, 아직 분석하지 않은 작업
    def test_two_tasks_get_their_own_rows_and_blocks(self):
        second = application.dispatch('create_task', {'survey_id': self.survey['survey_id'], 'draft': lifting_input('포장 작업')})
        run_analysis(second)
        book = self.export()
        sheet = book['유해요인조사표']
        self.assertEqual(row_with(sheet, '작업명')[1], '상자 들기\n포장 작업')
        text = text_of(sheet)
        for heading in ('3단계: 유해요인평가 — 상자 들기', '3단계: 유해요인평가 — 포장 작업'):
            self.assertIn(heading, text)
        headings = [str(row[0].value) for row in book['부담작업 해당 여부'].iter_rows() if row[0].value and '→ 최종 판단:' in str(row[0].value)]
        self.assertEqual(len(headings), 22)
        self.assertTrue(headings[0].startswith('[상자 들기] 키보드·마우스 집중 입력(법정 1호)'))
        self.assertTrue(headings[11].startswith('[포장 작업] 키보드·마우스 집중 입력(법정 1호)'))
        checklist = book['체크리스트']
        self.assertEqual(row_with(checklist, '상자 들기')[1], '○')
        self.assertEqual(row_with(checklist, '포장 작업')[1], '○')

    def test_a_task_without_an_analysis_says_it_is_not_calculated(self):
        application.dispatch('create_task', {'survey_id': self.survey['survey_id'], 'draft': lifting_input('나중에 분석할 작업')})
        book = self.export()
        text = text_of(book['유해요인조사표'])
        self.assertIn('계산 전', text)
        self.assertIn('분석을 마치면 채워져요', text)
        burden = text_of(book['부담작업 해당 여부'])
        self.assertTrue(any('판정 결과가 아직 없어요' in value for value in burden))
        self.assertEqual(row_with(book['체크리스트'], '나중에 분석할 작업')[12], '계산 전')

    # ----- 법령 문구와의 대조
    def test_rule_phrases_carry_exactly_the_numbers_of_the_preserved_notice(self):
        body = LAW_TEXT.read_text(encoding='utf-8').split('=== 본문 ===\n', 1)[1]
        section = body[body.index('제3조(근골격계부담작업)'):body.index('제4조(유해요인조사 방법)')]
        items = {int(number): ' '.join(text.split()) for number, text in re.findall(r'^([0-9]+)\. (.+)$', section, re.M)}
        self.assertEqual(sorted(items), list(range(1, 12)))
        for number, item in items.items():
            law = sorted(NUMBER.findall(item))
            self.assertEqual(sorted(set(NUMBER.findall(CRITERION_RULE[number]))), sorted(set(law)), f'{number}호 기준 문구의 숫자')
            self.assertEqual(sorted(set(NUMBER.findall(CHECK_RULE[number]))), sorted(set(law)), f'{number}호 체크리스트 문구의 숫자')


if __name__ == '__main__':
    unittest.main()
