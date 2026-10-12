"""스텁 서비스가 계약 시험을 통과하는지, 그리고 스텁이 쓰는 기준 값이 DB 시드와 같은지."""
import unittest

from ergo import contracts as C
from ergo.db import open_db
from ergo.service.stub import _CRITERIA, _MODELS, _THRESHOLDS, StubService
from tests.contract_suite import ServiceContractTests


class StubServiceContract(ServiceContractTests, unittest.TestCase):
    def make_service(self, progress_delay_s: float = 0.0):
        return StubService(progress_delay_s=progress_delay_s)


class StubMatchesSeed(unittest.TestCase):
    """스텁에 적어 둔 11개 기준 이름·각도·모델 목록이 시드와 같아야 한다 (두 곳에 적은 값이 갈라지지 않게)."""

    def setUp(self):
        self.con = open_db()

    def tearDown(self):
        self.con.close()

    def test_criteria_names(self):
        rows = dict(self.con.execute("SELECT criterion_no, short_name FROM criterion"))
        self.assertEqual(rows, _CRITERIA)

    def test_threshold_defaults(self):
        rows = {r[0]: (r[1], r[2], float(r[3]), r[4]) for r in self.con.execute(
            "SELECT threshold_cd, criterion_no, measure_cd, value_deg, source_ref FROM threshold_default")}
        want = {code.value: (no, measure, value, ref) for code, (no, measure, value, ref) in _THRESHOLDS.items()}
        self.assertEqual(rows, want)

    def test_models(self):
        rows = [C.PoseModel(*r) for r in self.con.execute(
            "SELECT model_id, model_name, model_version, keypoint_cnt FROM pose_model ORDER BY model_id")]
        self.assertEqual(rows, list(_MODELS))


if __name__ == "__main__":
    unittest.main()
