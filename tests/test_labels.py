import unittest

from backend.report.labels import input_label


class ReportInputLabels(unittest.TestCase):
    def test_criteria_row_completeness_and_union_paths_are_human_readable(self):
        self.assertEqual(
            input_label('criteria.6.rows_complete'),
            '하루의 모든 해당 조건 행 기록 여부',
        )
        self.assertEqual(
            input_label('criteria.6.union.value'),
            '적격 행의 중복 제거 합집합 수치',
        )


if __name__ == '__main__':
    unittest.main()
