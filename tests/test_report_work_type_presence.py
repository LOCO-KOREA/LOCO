"""A general lifting answer must not look like a confirmed 25kg threshold."""
import copy
import unittest

from backend.intake.contract import SESSION_KEY
from backend.report.plain import _legal_rows


class WorkTypePresenceLabels(unittest.TestCase):
    def lifting_source(self, origin='AI'):
        return {
            'conditions': {SESSION_KEY: {'facts': {
                'work_type.lift@default': {
                    'target': 'work_type.lift', 'condition': 'default', 'value': 'YES',
                    'source': origin, 'quote': '20kg 상자를 하루 120회, 1분에 2회씩, 하루 총 60분 들어 옮깁니다.'}
            }}},
            'legal': {'criteria': [
                {'criterion_no': 8, 'condition_present': 'YES',
                 'rows': [{'row_id': '20kg 상자', 'load_mass_kg': 20, 'lift_count_day': 120}]},
                {'criterion_no': 9, 'condition_present': 'YES',
                 'rows': [{'row_id': '20kg 상자', 'load_mass_kg': 20}]},
                {'criterion_no': 10, 'condition_present': 'YES',
                 'rows': [{'row_id': '20kg 상자', 'load_mass_kg': 20, 'lift_rate_min': 2, 'minutes': 60}]},
            ], 'exposures': []},
        }

    def test_twenty_kg_general_lifting_does_not_claim_the_twenty_five_kg_work_exists(self):
        for origin in ('AI', 'USER'):
            with self.subTest(origin=origin):
                source = self.lifting_source(origin)
                original = copy.deepcopy(source)
                rows = _legal_rows('상자 옮기기', source)
                presence = [row for row in rows if row[2].endswith(': 이 작업을 한다')]
                self.assertEqual([row[2] for row in presence], [
                    f'물건 들기·옮기기 작업({number}호 입력): 이 작업을 한다' for number in (8, 9, 10)])
                self.assertTrue(all(row[3] == '예' for row in presence))
                numeric = {row[2]: row[3] for row in rows if row not in presence}
                self.assertEqual(numeric['25kg 이상 들기: 물체 중량'], '20 kg')
                self.assertEqual(numeric['25kg 이상 들기: 하루 들기 횟수'], '120 회/일')
                self.assertEqual(numeric['10kg 이상 불편한 위치 들기: 물체 중량'], '20 kg')
                self.assertEqual(numeric['반복 들기: 작업 중 분당 들기 횟수'], '2 회/분')
                self.assertEqual(numeric['반복 들기: 하루 노출시간'], '60 분/일')
                self.assertEqual(source, original, 'display labels must not alter the input or scoring data')

    def test_direct_qualified_criterion_answer_keeps_its_original_label(self):
        source = {'legal': {'criteria': [{
            'criterion_no': 8, 'condition_present': 'YES',
            'evidence': {'source': 'INTERVIEW', 'text': '조사자가 25kg 이상 들기 조건을 직접 확인함'},
            'rows': [{'row_id': '확인한 물건', 'load_mass_kg': 25, 'lift_count_day': 120}],
        }], 'exposures': []}}
        rows = _legal_rows('직접 확인한 작업', source)
        presence = next(row for row in rows if row[2].endswith(': 이 작업을 한다'))
        self.assertEqual(presence[2:4], ['25kg 이상 들기: 이 작업을 한다', '예'])

    def test_unasked_unknown_general_work_is_not_exported_as_an_answer(self):
        source = {'legal': {'criteria': [
            {'criterion_no': number, 'condition_present': 'UNKNOWN', 'rows': []}
            for number in (8, 9, 10)], 'exposures': []}}
        self.assertEqual(_legal_rows('미확인 작업', source), [])


if __name__ == '__main__':
    unittest.main()
