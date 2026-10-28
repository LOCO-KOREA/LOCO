import unittest
from backend.report.form import _reba_tables
from backend.report.plain import _posture, _reba_text


class RebaReportDisplay(unittest.TestCase):
    def analysis(self):
        partial = dict(total=5, risk='MEDIUM', selected_side='LEFT', left=5, right=3,
                       assumed=['left.wrist_base'], assumption='확인 전 항목 포함')
        return dict(reba=dict(slots=[dict(slot_no=1, total=2, risk='LOW'),
                                    dict(slot_no=2, total=None, score_so_far=partial)],
                              summary=dict(complete_count=1, total_slot_count=2, available_max=2, full_max=None,
                                           score_so_far=dict(partial, slot_no=2))),
                    measurement_quality=dict(slots=[
                        dict(slot_no=1, measured_points=33, total_points=33, mean_confidence=0.95, confidence_level='HIGH'),
                        dict(slot_no=2, measured_points=5, total_points=33, mean_confidence=0.44, confidence_level='LOW')]))

    def test_current_score_and_quality_belong_to_the_same_photo(self):
        text = _reba_text(self.analysis())
        self.assertIn('현재 5점', text, 'a higher partial score must not disappear behind a lower completed photo')
        self.assertIn('5/33개', text)
        self.assertIn('측정 신뢰도 낮음 (44%)', text)
        self.assertNotIn('33/33개', text, 'the clearer other photo must not lend its confidence to this score')
        self.assertIn('확인 전 1항목', text)

    def test_overview_reba_row_shows_score_instead_of_a_zero_completed_message(self):
        tables = _reba_tables(dict(analysis=self.analysis(), name='작업'))
        cells = [str(value) for table in tables for row in table.get('rows', []) for value in row]
        text = '\n'.join(cells)
        self.assertIn('현재 5점', text)
        self.assertIn('5/33개', text)
        self.assertNotIn('계산하지 못했어요', text)
        self.assertNotIn('장을 계산했어요', text)
        self.assertIn('확인 전 항목 포함', text)

    def test_assumed_reference_does_not_present_a_measured_negligible_risk(self):
        analysis = self.analysis()
        reference = dict(total=1, risk='NEGLIGIBLE', selected_side='LEFT', left=1, right=1,
                         assumed=['common.trunk_base'], assumption='사진 측정 확인 필요', kind='ASSUMED_REFERENCE')
        analysis['reba'] = dict(slots=[dict(slot_no=2, total=None, score_so_far=reference)],
            summary=dict(complete_count=0, total_slot_count=1, available_max=None, full_max=None,
                         score_so_far=dict(reference, slot_no=2)))
        text = _reba_text(analysis)
        self.assertIn('가정 기준 1점', text)
        self.assertIn('실제 측정 확인 필요', text)
        self.assertNotIn('무시 가능', text)

    def test_photo_rows_use_each_projected_score_instead_of_raw_partial_or_other_photo(self):
        analysis = self.analysis()
        slots = analysis['reba']['slots']
        slots[0]['current_score'] = dict(total=2, risk='LOW', kind='CONFIRMED', slot_no=1)
        slots[1]['current_score'] = dict(total=7, risk='MEDIUM', kind='WITH_ASSUMPTIONS', slot_no=2)
        slots.append(dict(slot_no=3, total=None, current_score=dict(
            total=1, risk='NEGLIGIBLE', kind='ASSUMED_REFERENCE', slot_no=3)))
        analysis['reba']['summary']['current_score'] = slots[1]['current_score']
        analysis['snapshot'] = dict(settings={})
        sheet = _posture(dict(tasks=[dict(name='작업', analysis=analysis,
                                         source=dict(capture=dict(slots=[])))]))
        rows = sheet['tables'][0]['rows']
        self.assertEqual([row[2] for row in rows], ['2점', '7점', '1점'])
        self.assertEqual([row[3] for row in rows], [
            '확인 완료', '확인 전 항목 포함', '가정 기준 · 측정 확인 필요'])
        self.assertIn('5/33개', rows[1][4], 'quality must still belong to the same photo')


if __name__ == '__main__':
    unittest.main()
