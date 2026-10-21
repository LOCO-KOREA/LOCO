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
from ergo.service.application import create_service

ROOT = Path(__file__).resolve().parents[1]


class JsonLinesIntegration(unittest.TestCase):
    def test_gpt_request_does_not_block_a_later_service_response(self):
        # Real service/storage and request preparation; only the external call is delayed.
        with tempfile.TemporaryDirectory() as temporary:
            service = create_service(str(Path(temporary) / "async-gpt.db"))
            survey = service.dispatch("create_survey", {"draft": {"title": "async fixture"}})
            task = service.dispatch("create_task", {"survey_id": survey["survey_id"], "draft": {}})
            analysis = service.dispatch("recalculate_judgments", {"task_id": task["task_id"]})
            settings = service.settings()
            settings["gpt_enabled"] = True
            service.dispatch("update_settings", {"settings": settings})
            started, release = threading.Event(), threading.Event()
            output = io.StringIO()
            workers = []
            real_thread = threading.Thread

            def delayed_generate(*args):
                started.set()
                if not release.wait(timeout=3):
                    raise RuntimeError("test synchronization timeout")
                return None, "INJECTED_API_FAILURE"

            def track_thread(*args, **kwargs):
                worker = real_thread(*args, **kwargs)
                workers.append(worker)
                return worker

            with patch.object(json_lines, "dispatch", service.dispatch), \
                    patch.object(json_lines, "prepare_dispatch", service.prepare_dispatch), \
                    patch("ergo.gpt.client.generate", side_effect=delayed_generate), \
                    patch.object(json_lines.threading, "Thread", side_effect=track_thread), \
                    patch("sys.stdout", output):
                try:
                    json_lines.handle({"request_id": 1, "method": "generate_ai_text", "params": {
                        "analysis_id": analysis["analysis_id"], "purpose": "TASK_EXPLANATION"}})
                    self.assertTrue(started.wait(timeout=1), "GPT 작업 스레드가 시작되지 않았습니다")
                    json_lines.handle({"request_id": 2, "method": "list_surveys", "params": {}})
                    lines = output.getvalue().splitlines()
                    self.assertEqual(len(lines), 1)
                    self.assertEqual(json.loads(lines[0])["request_id"], 2)
                finally:
                    release.set()
                    for worker in workers:
                        worker.join(timeout=3)
                self.assertTrue(all(not worker.is_alive() for worker in workers))
                responses = [json.loads(line) for line in output.getvalue().splitlines()]
                self.assertEqual({item["request_id"] for item in responses}, {1, 2})
                self.assertEqual([item["request_id"] for item in responses], [2, 1])
                self.assertTrue(all(item["result"]["ok"] for item in responses), responses)
                self.assertEqual(responses[1]["result"]["value"]["text"]["result"], "FALLBACK")
            saved = service.analysis(analysis["analysis_id"])
            self.assertEqual(saved["ai"][0]["fallback_reason"], "INJECTED_API_FAILURE")

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
                self.assertEqual(receipt["sheets"], ["요약", "기준별 결과", "입력한 값", "사진 자세", "확인사항"])
                history = call("list_analysis_history", {"task_id": task["task_id"]})
                self.assertEqual([item["analysis_id"] for item in history], [started["analysis_id"]])
                workbook = load_workbook(destination, read_only=True, data_only=False)
                try:
                    self.assertEqual(workbook.sheetnames, receipt["sheets"])
                    self.assertTrue(any("상자 들기" in row for row in workbook["요약"].iter_rows(min_row=1, values_only=True)))
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
