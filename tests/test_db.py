"""DB: 연결 규칙 (ERD 6.1절)과 제약 시험 30개 (ERD 9절)."""
import importlib.util
import sqlite3
import tempfile
import unittest
from pathlib import Path

from ergo.db import SCHEMA_VERSION, open_db

ROOT = Path(__file__).resolve().parents[1]


class OpenDb(unittest.TestCase):
    def test_in_memory_has_schema_seed_and_foreign_keys(self):
        con = open_db()
        try:
            self.assertEqual(con.execute("PRAGMA foreign_keys").fetchone()[0], 1)
            self.assertEqual(con.execute("PRAGMA user_version").fetchone()[0], SCHEMA_VERSION)
            self.assertEqual(con.execute("SELECT MAX(version_no) FROM schema_version").fetchone()[0], SCHEMA_VERSION)
            self.assertEqual(con.execute("SELECT COUNT(*) FROM criterion").fetchone()[0], 11)
            with self.assertRaises(sqlite3.IntegrityError):          # 외래키가 실제로 켜져 있다
                con.execute("INSERT INTO unit_task(survey_id,task_name,worker_cnt,period_type_cd) VALUES (999,'x',1,'ONGOING')")
        finally:
            con.close()

    def test_file_db_uses_wal_and_reopens(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "ergo_assist.db"
            con = open_db(path)
            self.assertEqual(con.execute("PRAGMA journal_mode").fetchone()[0].lower(), "wal")
            con.execute("INSERT INTO survey(survey_type_cd,survey_date,investigator_name,dept_name,process_name,work_name)"
                        " VALUES ('REGULAR','2026-10-23','홍길동','a','b','c')")
            con.commit()
            con.close()
            again = open_db(path)
            self.assertEqual(again.execute("SELECT COUNT(*) FROM survey").fetchone()[0], 1)
            again.close()

    def test_old_sqlite_is_refused_with_a_clear_message(self):
        from unittest import mock
        with mock.patch.object(sqlite3, "sqlite_version_info", (3, 30, 0)), mock.patch.object(sqlite3, "sqlite_version", "3.30.0"):
            with self.assertRaises(RuntimeError) as cm:
                open_db()
        self.assertIn("3.38.0", str(cm.exception))

    def test_unknown_schema_version_is_refused(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "x.db"
            raw = sqlite3.connect(path)
            raw.execute("PRAGMA user_version = 99")
            raw.execute("CREATE TABLE t(a)")
            raw.commit()
            raw.close()
            with self.assertRaises(RuntimeError):
                open_db(path)


class ConstraintTests(unittest.TestCase):
    """docs_src/erd/build_and_test.py의 30개 시험을 그대로 돌린다 (통과해야 할 8개, DB가 막아야 할 22개)."""

    @classmethod
    def setUpClass(cls):
        spec = importlib.util.spec_from_file_location("erd_build_and_test", ROOT / "docs_src" / "erd" / "build_and_test.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        cls.results = mod.results

    def test_at_least_30_cases(self):
        self.assertGreaterEqual(len(self.results), 30)

    def test_every_case_behaves_as_expected(self):
        for r in self.results:
            with self.subTest(case=r["id"], name=r["name"]):
                self.assertTrue(r["ok"], f"{r['id']} {r['name']}: {r['msg']}")


if __name__ == "__main__":
    unittest.main()
