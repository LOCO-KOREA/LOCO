"""Integrity checks for the preserved source copy of MOEL Notice 2020-12."""
import hashlib
import re
import unittest
from pathlib import Path

FIXTURE = Path(__file__).parent / 'fixtures' / '고시_제2020-12호_본문.txt'
BODY_SHA256 = '9bddf9611101878843de8679a1f926d934e2f9397d36843e1255ef773a649004'


def normalized(value):
    return ' '.join(value.split())


def source_body():
    return FIXTURE.read_text(encoding='utf-8').split('=== 본문 ===\n', 1)[1]


def source_items():
    text = source_body()
    section = text[text.index('제3조(근골격계부담작업)'):text.index('제4조(유해요인조사 방법)')]
    return {int(number): normalized(body) for number, body in re.findall(r'^([0-9]+)\. (.+)$', section, re.M)}


class LawSource(unittest.TestCase):
    def test_preserved_source_hash_and_eleven_items(self):
        self.assertEqual(hashlib.sha256(normalized(source_body()).encode('utf-8')).hexdigest(), BODY_SHA256)
        self.assertEqual(sorted(source_items()), list(range(1, 12)))

    def test_comparison_detects_changed_threshold_and_spacing(self):
        original = source_items()
        changed = dict(original); changed[4] = changed[4].replace('2시간', '3시간')
        self.assertEqual([n for n in original if changed[n] != original[n]], [4])
        changed = dict(original); changed[3] = changed[3].replace('어깨위에', '어깨 위에')
        self.assertEqual([n for n in original if changed[n] != original[n]], [3])

    def test_exclusion_definitions_remain_in_the_source_copy(self):
        text = normalized(source_body())
        for phrase in ('2개월 이내에 종료되는 1회성 작업', '연간 총 작업일수가 60일을 초과하지 않는 작업',
                       '1일 소정근로시간과 1일 연장근로시간', '실제로 수행한 시간을 합산한 시간'):
            self.assertIn(phrase, text)


if __name__ == '__main__':
    unittest.main()
