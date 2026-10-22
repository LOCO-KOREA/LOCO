"""The workbook for ordinary readers: everyday words only, no detailed record for experts, and a preview that matches the file."""
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from openpyxl import load_workbook

from ergo.engine.quick_assess import NO_BURDEN
from ergo.engine.task_defaults import ARM, COMMON, task_input
from ergo.report import workbook
from ergo.service import application
from tests.report_helpers import CODE, lifting_input, make_survey, run_analysis, update_survey

PLAIN_SHEETS = ['유해요인조사표', '부담작업 해당 여부', '체크리스트', '자세 분석(REBA)', '입력한 값', '확인사항']


def blocks(sheet):
    """{heading: the rows under it} for the 부담작업 해당 여부 sheet. A block runs until the next empty row."""
    result, rows = {}, list(sheet.iter_rows(values_only=True))
    for index, row in enumerate(rows):
        if row[0] and '→ 최종 판단:' in str(row[0]):
            body = []
            for later in rows[index + 2:]:
                if all(value in (None, '') for value in later):
                    break
                body.append(later)
            result[row[0]] = body
    return result


class PlainWorkbook(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        patcher = patch.object(application, 'DB', str(Path(self.temp.name) / 'loco.db'))
        patcher.start()
        self.addCleanup(patcher.stop)
        self.addCleanup(self.temp.cleanup)
        self.survey = make_survey()
        self.task = application.dispatch('create_task', {'survey_id': self.survey['survey_id'], 'draft': lifting_input()})
        self.analysis = run_analysis(self.task)

    def export(self, comparisons=None):
        destination = str(Path(self.temp.name) / 'report.xlsx')
        application.dispatch('export_excel', {'survey_id': self.survey['survey_id'], 'spec': {
            'analysis_ids': [], 'include_representative': False, 'comparisons': comparisons or [], 'destination': destination}})
        return load_workbook(destination, data_only=False)

    def cells(self, book, name):
        return [cell.value for row in book[name].iter_rows() for cell in row if cell.value not in (None, '')]

    def test_the_workbook_holds_only_the_plain_sheets(self):
        book = self.export()
        self.assertEqual(book.sheetnames, PLAIN_SHEETS)
        self.assertNotIn('전문가용 상세기록', book.sheetnames, 'the detailed record for experts was removed on request')

    def test_plain_sheets_contain_no_codes_or_internal_words(self):
        book = self.export()
        for name in PLAIN_SHEETS:
            for value in self.cells(book, name):
                if isinstance(value, str):
                    self.assertIsNone(CODE.search(value), f'{name}: {value!r}')

    def test_no_ids_versions_or_schema_on_the_first_sheet(self):
        text = ' '.join(str(v) for v in self.cells(self.export(), '유해요인조사표'))
        for word in ('조사 ID', '분석 ID', '작업 ID', '스키마', '보고서 버전', 'T0', '.000000'):
            self.assertNotIn(word, text)

    def test_criteria_blocks_hold_the_values_behind_each_status(self):
        found = blocks(self.export()['부담작업 해당 여부'])
        self.assertEqual(len(found), 11)
        names = [h.split(' → ')[0] for h in found]
        self.assertEqual(names[0], '키보드·마우스 집중 입력(법정 1호)')
        self.assertEqual(names[7], '25kg 이상 들기(법정 8호)')
        by = {h.split(' → ')[0]: (h, rows) for h, rows in found.items()}
        heading, rows = by['키보드·마우스 집중 입력(법정 1호)']
        self.assertTrue(heading.endswith('최종 판단: 부담작업'))
        self.assertEqual(rows[0][0], '기준: 하루 4시간 이상 집중적으로 키보드·마우스 조작')
        self.assertEqual(rows[1][:4], ('집중 키보드·마우스 사용', '240 분/일', '240 분/일 이상', '○'))
        heading, rows = by['25kg 이상 들기(법정 8호)']
        self.assertTrue(heading.endswith('최종 판단: 부담작업 아님'))
        self.assertEqual(rows[1][:4], ('물체 중량', '20 kg', '25 kg 이상', 'X'), 'a value under the rule is marked X')
        self.assertEqual(rows[2][:4], ('하루 들기 횟수', '30 회/일', '10 회/일 이상', '○'))
        _, rows = by['같은 동작 반복(법정 2호)']
        self.assertEqual(rows[1][0], '이 작업을 하지 않는다고 답함', 'a "no" answer does not list empty time boxes')

    def test_inputs_sheet_lists_what_was_entered_with_units_and_how(self):
        values = {tuple('' if c.value is None else str(c.value) for c in row[2:5]) for row in self.export()['입력한 값'].iter_rows(min_row=6)}
        self.assertIn(('키보드·마우스 집중 입력: 집중 키보드·마우스 사용 시간', '240 분/일', '면담'), values)
        self.assertIn(('25kg 이상 들기: 물체 중량', '20 kg', '면담'), values)
        self.assertIn(('하루 실제 작업시간', '480 분/일', ''), values)

    def test_time_is_written_as_korean_wall_time_not_iso_text(self):
        import re
        book = self.export()
        text = ' '.join(str(v) for v in self.cells(book, '유해요인조사표'))
        self.assertRegex(text, r'20\d\d-\d\d-\d\d \d\d:\d\d')
        self.assertNotIn('T', ' '.join(re.findall(r'\d{4}-\d\d-\d\dT\S+', text)))

    def test_checks_use_everyday_names_and_correct_particles(self):
        text = '\n'.join(str(v) for v in self.cells(self.export(), '확인사항'))
        self.assertNotIn('MoveNet', text)
        self.assertNotIn('기술태그', text)
        update_survey(self.survey['survey_id'], workplace_situation=dict(equipment_status='YES', workload_status='YES', speed_status='YES', work_pattern_status='YES',
                                                                       equipment_notes='', workload_notes='', speed_notes='', work_pattern_notes=''))
        text = '\n'.join(str(v) for v in self.cells(self.export(), '확인사항'))
        for phrase in ('작업설비가 변경되었다고', '작업량이 변경되었다고', '작업속도가 변경되었다고', '업무형태가 변경되었다고'):
            self.assertIn(phrase, text)

    def test_preview_shows_exactly_the_plain_sheets_that_the_file_contains(self):
        preview = application.dispatch('preview_excel_sheets', {'survey_id': self.survey['survey_id']})
        self.assertEqual([s['name'] for s in preview['sheets']], PLAIN_SHEETS)
        self.assertNotIn('expert_sheet', preview)
        self.assertNotIn('form_sheets', preview)
        book = self.export()
        for sheet in preview['sheets']:
            in_file = {str(v) for v in self.cells(book, sheet['name'])}
            for table in sheet['tables']:
                for row in table['rows']:
                    for value in row:
                        if value not in ('', None):
                            self.assertIn(str(value), in_file, f"{sheet['name']}: {value!r}")

    def test_preview_changes_nothing(self):
        before = application.dispatch('list_export_logs', {'survey_id': self.survey['survey_id']})
        application.dispatch('preview_excel_sheets', {'survey_id': self.survey['survey_id']})
        self.assertEqual(application.dispatch('list_export_logs', {'survey_id': self.survey['survey_id']}), before)

    def test_applied_explanation_gets_its_own_sheet_and_an_unapplied_one_does_not(self):
        self.assertNotIn('쉬운 설명', self.export().sheetnames)
        settings = application.dispatch('get_settings', {})
        settings.pop('gpt_key_present', None)
        settings.update(gpt_enabled=True, gpt_model='test-model')
        application.dispatch('update_settings', {'settings': settings})
        with patch('ergo.gpt.client.generate', return_value=(None, 'NO_API_KEY')):
            generated = application.dispatch('generate_ai_text', {'analysis_id': self.analysis['analysis_id'], 'purpose': 'TASK_EXPLANATION'})
        application.dispatch('apply_ai_text', {'analysis_id': self.analysis['analysis_id'], 'text_id': generated['text']['text_id'], 'use_edited': False})
        book = self.export()
        self.assertEqual(book.sheetnames, PLAIN_SHEETS + ['쉬운 설명'])
        self.assertIn('기본 설명(AI를 쓰지 못했어요)', self.cells(book, '쉬운 설명'))

    def test_before_after_sheet_is_in_words_and_hides_bookkeeping_changes(self):
        task = application.dispatch('get_task', {'task_id': self.task['task_id']})['task']
        updated = application.task_input(task)
        updated['legal']['exposures'][0]['minutes'] = 60
        updated['legal']['exposures'][0]['evidence'] = {'source': 'INTERVIEW', 'text': '다시 확인', 'observed_at': '2026-10-24T01:00:00Z'}
        saved = application.dispatch('save_task_input', {'task_id': task['task_id'], 'input': updated})
        after = run_analysis(saved)
        book = self.export([{'before_analysis_id': self.analysis['analysis_id'], 'after_analysis_id': after['analysis_id'], 'note': '시간 줄임'}])
        self.assertEqual(book.sheetnames, PLAIN_SHEETS + ['개선 전후 비교'])
        text = '\n'.join(str(v) for v in self.cells(book, '개선 전후 비교'))
        self.assertIn('집중 키보드·마우스 사용 시간', text)
        self.assertIn('240 분/일', text)
        self.assertIn('60 분/일', text)
        self.assertIn('시간 줄임', text)
        self.assertIsNone(CODE.search(text.replace('MOEL', '')), text)
        self.assertNotIn('observed_at', text)
        self.assertIn('계산에 영향이 없는 변경', text, 'the sheet says how many bookkeeping-only changes it left out')


@unittest.skipUnless(os.path.isfile(Path(__file__).resolve().parents[1] / '.local' / 'fixtures' / 'tensorflow-movenet-example.jpeg')
                     and os.path.isfile(Path(__file__).resolve().parents[1] / 'models' / 'movenet_lightning.tflite'), 'public example photo and official model required')
class PhotoWorkbook(unittest.TestCase):
    def test_photo_workbook_names_the_body_parts_places_the_photo_and_summarizes_the_reba_score(self):
        fixture = Path(__file__).resolve().parents[1] / '.local' / 'fixtures' / 'tensorflow-movenet-example.jpeg'
        with tempfile.TemporaryDirectory() as root, patch.object(application, 'DB', str(Path(root) / 'photo.db')):
            survey = make_survey('사진 보고서')
            task = application.dispatch('create_task', {'survey_id': survey['survey_id'], 'draft': task_input({'task_name': '사진 작업'})})
            photo = application.dispatch('import_photos', {'task_id': task['task_id'], 'file_paths': [str(fixture)]})['added'][0]
            draft = application.task_input(application.dispatch('get_task', {'task_id': task['task_id']})['task'])
            note = {'source': 'INTERVIEW', 'text': '테스트 입력', 'observed_at': '2026-10-23T01:00:00Z'}
            draft['capture']['slots'] = [dict(slot_no=1, photo_id=photo['photo_id'], label='오른쪽 사진', analysis_target=True, camera_side='RIGHT', forward_direction='SCREEN_RIGHT',
                                              side_view_verified='YES', observation=dict(load_state='UNLOADED', measured_load_kg=None, single_person='YES', full_frame='YES', normal_work='YES', evidence=dict(note)))]
            draft['manual'] = [dict(slot_no=1, photo_id=photo['photo_id'], scope=scope, field=field, value=NO_BURDEN[field], source='INTERVIEW', evidence=dict(note))
                               for scope, fields in (('COMMON', COMMON), ('LEFT', ARM), ('RIGHT', ARM)) for field in fields]
            saved = application.dispatch('save_task_input', {'task_id': task['task_id'], 'input': draft})
            analysis = run_analysis(saved, ('pose', 'tags', 'reba', 'judgment'))
            destination = str(Path(root) / 'photo.xlsx')
            application.dispatch('export_excel', {'survey_id': survey['survey_id'], 'spec': {
                'analysis_ids': [analysis['analysis_id']], 'include_representative': True, 'comparisons': [], 'destination': destination}})
            book = load_workbook(destination)
            sheet = book['자세 분석(REBA)']
            values = [c.value for row in sheet.iter_rows() for c in row if c.value not in (None, '')]
            for word in ('사진별 REBA 점수 (점수가 높을수록 몸에 부담이 커요)', '몸통', '위팔', '손목', '오른쪽 사진'):
                self.assertTrue(any(isinstance(v, str) and word in v for v in values), word)
            main = book['유해요인조사표']
            self.assertEqual(len(main._images), 1, 'the representative photo is embedded where the form asks for it')
            self.assertEqual(len(sheet._images), 0)
            text = '\n'.join(str(c.value) for row in main.iter_rows() for c in row if c.value not in (None, ''))
            for phrase in ('3-1. 인간공학적 작업·분석 평가 결과표', 'REBA(전신 자세 평가)', '대표 사진: 오른쪽 사진'):
                self.assertIn(phrase, text)
            for value in values:
                if isinstance(value, str):
                    self.assertIsNone(CODE.search(value), value)


if __name__ == '__main__':
    unittest.main()
