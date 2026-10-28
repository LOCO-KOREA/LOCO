"""Generated source labels are readable; stored codes and exact quotes stay intact."""
import copy
import unittest

from backend.intake.contract import SESSION_KEY
from backend.report.input_trace import InputTrace


class SourceLanguage(unittest.TestCase):
    def test_source_prefixes_never_expose_storage_codes_or_rewrite_quotes(self):
        for code, label, prefix in (
            ('USER', '직접 입력', '직접 입력'),
            ('AI', '작업 설명(AI 정리)', 'AI'),
            ('SAVED', '저장된 입력', '저장된 입력'),
            ('POSE', '사진 자동 측정', '사진 자동 측정'),
            ('MOVENET', '사진 자동 측정', '사진 자동 측정'),
            ('VISION', 'AI 사진 관찰', 'AI 사진 관찰'),
        ):
            with self.subTest(source=code):
                quote = '원문 속 USER: 같은 표현은 그대로 보존해요.'
                source = dict(conditions={SESSION_KEY: dict(facts={
                    'daily_work_min@default': dict(target='daily_work_min', condition='default',
                        value=300, source=code, state='KNOWN', quote=quote)
                })})
                before = copy.deepcopy(source)
                self.assertEqual(InputTrace(source).lookup('conditions', 300, field='daily_work_min'),
                                 (label, prefix + ': ' + quote))
                self.assertEqual(source, before)


if __name__ == '__main__':
    unittest.main()
