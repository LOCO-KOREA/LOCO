"""경계 시험: 계약 ↔ ERD, 엔진 값 ↔ ERD 컬럼, GPT로 나가는 열의 목록."""
import dataclasses
import re
import subprocess
import sys
import unittest
from pathlib import Path

from ergo.db import open_db
from ergo.engine.types import KEYPOINT_NAMES, StillAngles
from ergo.gpt.payload import FILTER_COLUMNS, SENT_COLUMNS

ROOT = Path(__file__).resolve().parents[1]


class ContractVsErd(unittest.TestCase):
    def test_enums_and_dtos_match_the_database(self):
        r = subprocess.run([sys.executable, str(ROOT / "docs_src" / "api" / "check_contract.py")],
                           capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(r.returncode, 0, r.stderr)
        last = r.stdout.strip().splitlines()[-1]
        self.assertTrue(last.endswith("mismatches 0"), r.stdout)


class ErrorCodes(unittest.TestCase):
    def test_contract_codes_match_the_error_table_in_the_api_template(self):
        """contracts.ERROR_CODES와 API 계약서 8절 표의 코드가 같다 (표는 docs_src/api/api_template.md)."""
        from ergo import contracts as C
        text = (ROOT / "docs_src" / "api" / "api_template.md").read_text(encoding="utf-8")
        sec = text[text.index("## 8. 오류 코드"):text.index("## 9. 주요 시나리오")]
        table = set(re.findall(r"^\| ([EWI]-[A-Z]+-[0-9]{3}) \|", sec, re.M))
        self.assertEqual(table, set(C.ERROR_CODES))


class EngineTypes(unittest.TestCase):
    def test_still_angles_are_columns_of_still_angle(self):
        con = open_db()
        try:
            cols = {r[1] for r in con.execute("PRAGMA table_xinfo(still_angle)")}
        finally:
            con.close()
        fields = {f.name for f in dataclasses.fields(StillAngles)}
        self.assertEqual(fields - cols, set(), "DB에 없는 필드")
        self.assertEqual(cols - fields - {"run_id"}, set(), "DB에는 있는데 StillAngles에 없는 컬럼")

    def test_seventeen_keypoints(self):
        self.assertEqual(len(KEYPOINT_NAMES), 17)
        self.assertEqual(len(set(KEYPOINT_NAMES)), 17)


class GptPayload(unittest.TestCase):
    def test_every_view_column_is_classified_as_sent_or_filter_only(self):
        con = open_db()
        try:
            cols = [d[0] for d in con.execute("SELECT * FROM v_gpt_payload").description]
        finally:
            con.close()
        self.assertEqual(set(SENT_COLUMNS) & set(FILTER_COLUMNS), set())
        self.assertEqual(set(cols), set(SENT_COLUMNS) | set(FILTER_COLUMNS),
                         "뷰의 열이 바뀌었다. gpt/payload.py에서 '보냄'인지 '거르기용'인지 정해야 한다")

    def test_nothing_that_looks_like_a_name_or_path_is_sent(self):
        for c in SENT_COLUMNS:
            for bad in ("name", "path", "investigator", "dept", "process", "work", "participant", "desc"):
                self.assertNotIn(bad, c.replace("criterion_summary", "").replace("daily_work_h", ""), c)


if __name__ == "__main__":
    unittest.main()
