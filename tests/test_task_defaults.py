"""General task defaults shared by create, save, and analysis snapshots."""
import unittest

from ergo.engine.task_defaults import EXPOSURE_V2, legal_inputs, task_input


class GeneralTaskDefaults(unittest.TestCase):
    def test_new_task_does_not_infer_work_kind_from_its_name(self):
        for name in ('상자 들기', '키보드 입력', '조립 작업'):
            with self.subTest(name=name):
                draft = task_input({'task_name': name})
                self.assertEqual(draft['task_kind'], 'GENERAL_TASK')
                self.assertEqual(draft['schema_version'], '2.0')
                self.assertEqual(draft['task_name'], name)

    def test_default_direct_inputs_are_unknown_or_empty_not_false_or_zero(self):
        value = legal_inputs()
        self.assertEqual([x['criterion_no'] for x in value['criteria']], list(range(1, 12)))
        self.assertTrue(all(x['condition_present'] == 'UNKNOWN' for x in value['criteria']))
        self.assertEqual([x['condition_code'] for x in value['exposures']], EXPOSURE_V2)
        self.assertTrue(all(x['minutes'] is None for x in value['exposures']))
        self.assertTrue(all(not x.get('rows') and x.get('rows_complete') == 'UNKNOWN'
                            for x in value['criteria'][5:]))


if __name__ == '__main__':
    unittest.main()
