"""Tests for the strict, identifier-free GPT explanation boundary."""
import json
import unittest

from ergo.gpt import client, payload


def summary_fixture():
    return {'criteria': [
        {'criterion_no': n, 'basis': [{'item_code': f'C{n:02d}-B01', 'value': n * 10,
                                      'unit': 'MIN_DAY', 'operator': 'GE', 'threshold': 120}]}
        for n in range(1, 12)]}


def content_fixture(summary):
    return {'summary': '입력 근거를 기준별로 확인하세요.',
        'criteria': [{'criterion_no': n, 'explanation': '입력값을 다시 확인하세요.',
                      'basis_refs': [f'C{n:02d}-B01']} for n in range(1, 12)],
        'check_items': ['현장 조건을 확인하세요.'],
        'improvement_options': [{'proposal': '작업 조건을 조사자와 함께 검토하세요.',
                                 'basis_refs': ['C01-B01'], 'needs_confirmation': True}]}


class GptBoundary(unittest.TestCase):
    def test_numeric_summary_does_not_send_names_paths_or_photo_ids(self):
        analysis = {'snapshot': {
            'schema_version': '2.0', 'task_id': 8181, 'task_name': '비밀 작업명',
            'conditions': {'worker_code': '비밀 작업자 코드', 'method_description': '비밀 자유 문장'},
            'analysis_scope': {'judgment': True, 'pose': True, 'tags': True, 'reba': True},
            'capture': {'slots': [{'slot_no': 7, 'photo_id': 9191, 'label': '민감한 사진 이름',
                                  'analysis_target': True}], 'protocol': 'GENERAL_STILLS_V1'},
            'settings': {'burden_rule': 'MOEL_2020_12_GENERAL_V2', 'reba_rule': 'REBA_TABLE_2000_V2',
                         'posture_profile': {'version': 'POSTURE_TECH_V1'}}},
            'judgment': {'judgments': [{'criterion_no': 1, 'basis': [{'item_code': 'criteria.1.minutes',
                'value': 240, 'unit': 'MIN_DAY', 'operator': 'GE', 'threshold': 240}],
                'computed_status': 'APPLICABLE', 'investigator': {'status': None}, 'effective_status': 'APPLICABLE'}]},
            'pose': {'valid_count': 1}, 'reba': {'summary': {'complete_count': 1, 'available_max': 5, 'full_max': 5}},
            'tags': [], 'module_states': {}}
        encoded = json.dumps(payload.build_numeric_summary(analysis), ensure_ascii=False)
        for private in ('비밀 작업명', '비밀 작업자 코드', '비밀 자유 문장', '민감한 사진 이름', '8181', '9191', 'criteria.1.minutes'):
            self.assertNotIn(private, encoded)
        self.assertIn('C01-B01', encoded)

    def test_structured_content_must_reference_its_own_criterion(self):
        summary = summary_fixture(); content = content_fixture(summary)
        self.assertTrue(payload.validate_content(content, summary))
        content['criteria'][0]['basis_refs'] = ['C02-B01']
        self.assertFalse(payload.validate_content(content, summary))

    def test_extra_criteria_and_unsent_numbers_are_rejected(self):
        summary = summary_fixture(); content = content_fixture(summary)
        content['criteria'].append({'criterion_no': 12, 'explanation': '추가', 'basis_refs': []})
        self.assertFalse(payload.validate_content(content, summary))
        content = content_fixture(summary)
        content['criteria'][0]['explanation'] = '999분이 확인됐습니다.'
        self.assertFalse(payload.validate_content(content, summary))

    def test_missing_key_returns_fallback_without_creating_an_api_client(self):
        content, reason = client.generate({}, 'test-model', None)
        self.assertIsNone(content)
        self.assertEqual(reason, 'NO_API_KEY')


if __name__ == '__main__':
    unittest.main()
