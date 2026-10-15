"""Exercise the same JSON Lines process boundary used by the Electron main process."""
import io
import json
import os
import subprocess
import sys
import tempfile
import time
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

from openpyxl import load_workbook

from ergo.engine.task_defaults import task_input
from ergo.service import json_lines

ROOT = Path(__file__).resolve().parents[1]


class JsonLinesIntegration(unittest.TestCase):
    def test_gpt_request_does_not_block_a_later_service_response(self):
        started = threading.Event()
        release = threading.Event()
        output = io.StringIO()

        def delayed_dispatch(method, params):
            if method == "generate_ai_text":
                started.set()
                release.wait(timeout=3)
                return {"text": {"result": "GENERATED"}}
            return []

        with patch.object(json_lines, "dispatch", side_effect=delayed_dispatch), patch("sys.stdout", output):
            try:
                json_lines.handle({"request_id": 1, "method": "generate_ai_text", "params": {}})
                self.assertTrue(started.wait(timeout=1), "GPT 작업 스레드가 시작되지 않았습니다")
                json_lines.handle({"request_id": 2, "method": "list_surveys", "params": {}})
                lines = output.getvalue().splitlines()
                self.assertEqual(len(lines), 1)
                self.assertEqual(json.loads(lines[0])["request_id"], 2)
            finally:
                release.set()
            deadline = time.monotonic() + 2
            while len(output.getvalue().splitlines()) < 2 and time.monotonic() < deadline:
                time.sleep(0.01)
            responses = [json.loads(line) for line in output.getvalue().splitlines()]
            self.assertEqual({item["request_id"] for item in responses}, {1, 2})

    def test_lifting_task_runs_through_service_process_and_exports_four_sheets(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary)
            env = dict(os.environ, LOCO_DB_PATH=str(folder / "loco.db"), PYTHONIOENCODING="utf-8")
            service = subprocess.Popen(
                [sys.executable, "-u", "-m", "ergo.service.json_lines"],
                cwd=ROOT, env=env, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                stderr=subprocess.PIPE, text=True, encoding="utf-8",
            )
            request_id = 0

            def call(method, params=None):
                nonlocal request_id
                request_id += 1
                request = {"request_id": request_id, "method": method, "params": params or {}}
                service.stdin.write(json.dumps(request, ensure_ascii=False, allow_nan=False) + "\n")
                service.stdin.flush()
                line = service.stdout.readline()
                self.assertTrue(line, f"JSON Lines 서비스가 {method} 요청에 응답하지 않았습니다")
                response = json.loads(line)
                self.assertEqual(response["request_id"], request_id)
                self.assertTrue(response["result"]["ok"], response["result"].get("error"))
                return response["result"]["value"]

            try:
                survey = call("create_survey", {"draft": {
                    "survey_type": "REGULAR", "survey_date": "2026-10-23", "investigator": "조사자",
                    "department": "팀", "process": "공정", "title": "JSON Lines 검증", "occasional_reason": None,
                }})
                draft = task_input({"task_name": "상자 들기", "input_template": "LIFTING"})
                task = call("create_task", {"survey_id": survey["survey_id"], "draft": draft})
                self.assertEqual(task["task_kind"], "GENERAL_TASK")
                self.assertEqual(len(task["legal"]["criteria"]), 11)

                started = call("start_analysis", {"task_id": task["task_id"]})
                analysis = None
                deadline = time.monotonic() + 10
                while time.monotonic() < deadline:
                    analysis = call("get_analysis", {"analysis_id": started["analysis_id"]})
                    if analysis["status"] != "RUNNING":
                        break
                    time.sleep(0.05)
                self.assertIsNotNone(analysis)
                self.assertEqual(analysis["status"], "FINISHED")
                self.assertEqual(len(analysis["judgment"]["judgments"]), 11)
                self.assertEqual(analysis["module_states"]["pose"], "NOT_REQUESTED")

                preview = call("preview_excel", {"survey_id": survey["survey_id"], "analysis_ids": []})
                self.assertEqual(preview["counts"]["needs_input_count"], 11)
                destination = folder / "loco.xlsx"
                receipt = call("export_excel", {"survey_id": survey["survey_id"], "spec": {
                    "analysis_ids": [], "include_representative": False, "comparisons": [],
                    "destination": str(destination),
                }})
                self.assertEqual(receipt["sheets"], ["요약", "작업별 결과", "확인사항", "판정 근거"])
                history = call("list_analysis_history", {"task_id": task["task_id"]})
                self.assertEqual([item["analysis_id"] for item in history], [started["analysis_id"]])
                workbook = load_workbook(destination, read_only=True, data_only=False)
                try:
                    self.assertEqual(workbook.sheetnames, receipt["sheets"])
                    self.assertTrue(any(len(row) > 1 and row[1] == "상자 들기" for row in workbook["요약"].iter_rows(min_row=1, values_only=True)))
                finally:
                    workbook.close()
            finally:
                if service.stdin:
                    service.stdin.close()
                try:
                    code = service.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    service.kill()
                    service.wait(timeout=5)
                    self.fail("JSON Lines 서비스가 표준 입력 종료 뒤 끝나지 않았습니다")
                stderr = service.stderr.read() if service.stderr else ""
                self.assertEqual(code, 0, stderr)
                if service.stdout:
                    service.stdout.close()
                if service.stderr:
                    service.stderr.close()


if __name__ == "__main__":
    unittest.main()
