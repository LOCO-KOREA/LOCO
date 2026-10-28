"""S02 regressions on disposable SQLite services, with injected worker failures.

These checks use real service/storage code and synthetic local image files.
MoveNet output and thread-start failures are controlled doubles; no inference,
external GPT account, Electron process, or original user database is exercised.
"""
import contextlib
import copy
import io
import json
import sqlite3
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image

from backend.engine.task_defaults import evidence
from backend.service import analysis_jobs, json_lines
from backend.service.application import create_service


class S02ServiceRegressions(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.folder = Path(temporary.name)
        self.app = create_service(str(self.folder / 's02-isolated.db'))
        self.survey = self.app.dispatch('create_survey', {
            'draft': {'title': 'S02 disposable fixture', 'survey_type': 'REGULAR'},
        })
        self.task = self.new_task()
        # An unexpected external request must fail the check, never use an account.
        no_external = patch('backend.gpt.client.generate', side_effect=AssertionError(
            'External GPT must not be called by S02 regressions'))
        no_external.start()
        self.addCleanup(no_external.stop)

    def new_task(self):
        return self.app.dispatch('create_task', {
            'survey_id': self.survey['survey_id'],
            'draft': {'task_name': 'Disposable task'},
        })

    def add_target(self):
        file = self.folder / 'synthetic.png'
        Image.new('RGB', (8, 12), 'white').save(file)
        photos = self.app.dispatch('import_photos', {
            'task_id': self.task['task_id'], 'file_paths': [str(file)],
        })
        photo_id = photos['added'][0]['photo_id']
        slot = dict(
            slot_no=1, photo_id=photo_id, label='Synthetic model-double case',
            analysis_target=True, camera_side='LEFT',
            forward_direction='SCREEN_RIGHT', side_view_verified='YES',
            observation=dict(load_state='UNLOADED', measured_load_kg=None,
                             single_person='YES', full_frame='YES', normal_work='YES',
                             evidence=evidence()),
        )
        self.task = self.app.dispatch('set_capture', {
            'task_id': self.task['task_id'],
            'capture': {'protocol': 'GENERAL_STILLS_V1', 'slots': [slot]},
        })
        self.task = self.app.dispatch('set_analysis_scope', {
            'task_id': self.task['task_id'],
            'scope': dict(judgment=True, pose=True, tags=False, reba=False),
        })
        # Known values are injected solely to distinguish preservation from mutation.
        return dict(
            slot_no=1, photo_id=photo_id, status='VALID', diagnostics=[],
            points=[dict(point_no=5, name='left_shoulder', x_px=3, y_px=2,
                         confidence=0.91)],
            angles=[dict(side='LEFT', angle_code='TRUNK_TILT_VERT', value_deg=17,
                         min_confidence=0.91, diagnostic=None)],
        )

    def seed_pose(self):
        pose_slot = self.add_target()
        a = self.app.new_analysis(self.task, ['pose'])
        with patch.object(analysis_jobs.pose, 'process', return_value=pose_slot):
            self.app.run(a, ['pose'], threading.Event(),
                         self.app.analysis_token(a['analysis_id']))
        saved = self.app.analysis(a['analysis_id'])
        self.assertEqual(saved['module_states']['pose'], 'COMPLETE')
        self.assertEqual(saved['pose']['status'], 'DONE')
        return saved

    def handle_lines(self, requests):
        output, errors = io.StringIO(), io.StringIO()
        with patch.object(json_lines, 'dispatch', self.app.dispatch), \
                patch.object(json_lines, 'prepare_dispatch', self.app.prepare_dispatch), \
                contextlib.redirect_stdout(output), contextlib.redirect_stderr(errors):
            for request in requests:
                json_lines.handle(request)
        return [json.loads(line) for line in output.getvalue().splitlines()]

    def test_start_failures_emit_one_error_and_accept_next_request(self):
        methods = [('start_analysis', 'judgment'),
                   ('recalculate_judgments', 'judgment'),
                   ('recalculate_tags', 'tags'), ('recalculate_reba', 'reba')]
        for index, (method, module) in enumerate(methods):
            with self.subTest(method=method):
                task = self.new_task()
                request_id = 100 + index * 2
                with patch('threading.Thread.start', side_effect=RuntimeError('start blocked')):
                    replies = self.handle_lines([
                        dict(request_id=request_id, method=method,
                             params={'task_id': task['task_id']}),
                        dict(request_id=request_id + 1, method='list_tasks',
                             params={'survey_id': self.survey['survey_id']}),
                    ])
                self.assertEqual([r['request_id'] for r in replies],
                                 [request_id, request_id + 1])
                self.assertFalse(replies[0]['result']['ok'])
                self.assertIn('start blocked', replies[0]['result']['error']['message'])
                self.assertTrue(replies[1]['result']['ok'])
                history = self.app.dispatch('list_analysis_history', {'task_id': task['task_id']})
                self.assertEqual(len(history), 1)
                failed = history[0]
                self.assertEqual(failed['status'], 'FAILED')
                self.assertEqual(failed['module_states'][module], 'FAILED')
                self.assertIsNotNone(failed['finished_at'])
                self.assertTrue(any(n['code'] == 'ANALYSIS_START_ERROR'
                                    for n in failed['notes']))
                self.assertNotIn(failed['analysis_id'], self.app.cancels)

    def test_start_failure_marks_pending_pose_unprocessed(self):
        self.add_target()
        self.app.dispatch('set_analysis_scope', {
            'task_id': self.task['task_id'],
            'scope': dict(judgment=True, pose=True, tags=False, reba=False),
        })
        with patch('threading.Thread.start', side_effect=RuntimeError('start blocked')):
            with self.assertRaisesRegex(RuntimeError, 'start blocked'):
                self.app.dispatch('start_analysis', {'task_id': self.task['task_id']})
        failed = self.app.dispatch('list_analysis_history', {'task_id': self.task['task_id']})[0]
        self.assertEqual(failed['status'], 'FAILED')
        self.assertEqual(failed['module_states']['pose'], 'FAILED')
        self.assertEqual(failed['pose']['status'], 'FAILED')
        self.assertEqual(failed['pose']['slots'][0]['status'], 'NOT_PROCESSED')
        self.assertEqual(failed['pose']['slots'][0]['points'], [])
        self.assertEqual(self.app.cancels, {})

    def test_start_failure_releases_handle_even_if_failure_write_fails(self):
        with patch('threading.Thread.start', side_effect=RuntimeError('start blocked')), \
                patch.object(self.app, 'persist_analysis', side_effect=sqlite3.DatabaseError('write blocked')):
            replies = self.handle_lines([
                dict(request_id=201, method='recalculate_judgments',
                     params={'task_id': self.task['task_id']}),
                dict(request_id=202, method='list_tasks',
                     params={'survey_id': self.survey['survey_id']}),
            ])
        self.assertEqual([r['request_id'] for r in replies], [201, 202])
        self.assertFalse(replies[0]['result']['ok'])
        self.assertEqual(replies[0]['result']['error']['code'], 'DB_ERROR')
        self.assertTrue(replies[1]['result']['ok'])
        self.assertEqual(self.app.cancels, {})
        # A failed database write cannot promise a persisted FAILED record.
        history = self.app.dispatch('list_analysis_history', {'task_id': self.task['task_id']})
        self.assertEqual(history[0]['status'], 'RUNNING')

    def test_gpt_start_failure_keeps_existing_analysis_and_accepts_next_request(self):
        a = self.app.dispatch('recalculate_judgments', {'task_id': self.task['task_id']})
        before = copy.deepcopy(self.app.require('analysis', a['analysis_id']))
        with patch('threading.Thread.start', side_effect=RuntimeError('start blocked')):
            replies = self.handle_lines([
                dict(request_id=301, method='generate_ai_text',
                     params={'analysis_id': a['analysis_id'], 'purpose': 'TASK_EXPLANATION'}),
                dict(request_id=302, method='list_tasks',
                     params={'survey_id': self.survey['survey_id']}),
            ])
        self.assertEqual([r['request_id'] for r in replies], [301, 302])
        self.assertFalse(replies[0]['result']['ok'])
        self.assertTrue(replies[1]['result']['ok'])
        self.assertEqual(self.app.require('analysis', a['analysis_id']), before)
        self.assertEqual(self.app.cancels, {})

    def test_later_module_failure_preserves_reused_pose(self):
        original = self.seed_pose()
        for method, function in [('recalculate_tags', 'calculate_tags'),
                                 ('recalculate_reba', 'calculate_reba')]:
            with self.subTest(method=method), \
                    patch.object(analysis_jobs, function, side_effect=RuntimeError('later module blocked')), \
                    contextlib.redirect_stderr(io.StringIO()):
                failed = self.app.dispatch(method, {'task_id': self.task['task_id']})
                self.assertEqual(failed['status'], 'FAILED')
                self.assertEqual(failed['pose'], original['pose'])
                self.assertEqual(failed['module_states']['pose'], 'COMPLETE')
                module = 'tags' if method == 'recalculate_tags' else 'reba'
                self.assertEqual(failed['module_states'][module], 'FAILED')
                self.assertEqual(self.app.analysis(original['analysis_id'])['pose'], original['pose'])
                self.assertEqual(self.app.cancels, {})

    def test_later_module_failure_preserves_pose_completed_in_same_run(self):
        pose_slot = self.add_target()
        modules = ['pose', 'tags', 'reba']
        a = self.app.new_analysis(self.task, modules)
        with patch.object(analysis_jobs.pose, 'process', return_value=pose_slot), \
                patch.object(analysis_jobs, 'calculate_reba', side_effect=RuntimeError('reba blocked')), \
                contextlib.redirect_stderr(io.StringIO()):
            self.app.run(a, modules, threading.Event(), self.app.analysis_token(a['analysis_id']))
        failed = self.app.analysis(a['analysis_id'])
        self.assertEqual(failed['status'], 'FAILED')
        self.assertEqual(failed['module_states']['pose'], 'COMPLETE')
        self.assertEqual(failed['module_states']['reba'], 'FAILED')
        self.assertEqual(failed['pose']['status'], 'DONE')
        self.assertIsNone(failed['pose']['terminal_error'])
        self.assertEqual(failed['pose']['slots'], [pose_slot])

    def test_prepared_recalculation_uses_the_registered_cancel_event(self):
        operation = self.app.prepare_dispatch('recalculate_judgments', {'task_id': self.task['task_id']})
        identity = self.app.require('task', self.task['task_id'])['latest_analysis_id']
        cancel = self.app.cancels[identity]
        self.app.dispatch('cancel_analysis', {'analysis_id': identity})
        self.assertTrue(cancel.is_set())
        finished = operation()
        self.assertEqual(finished['status'], 'CANCELED')
        self.assertEqual(finished['module_states']['judgment'], 'CANCELED')
        self.assertIsNone(finished['judgment'])
        self.assertNotIn(identity, self.app.cancels)

    def test_deleted_id_reuse_blocks_old_calculation_and_keeps_new_cancel_handle(self):
        old_a, old_modules, old_cancel, old_token = analysis_jobs.prepare_recalculation(
            self.app, 'recalculate_judgments', {'task_id': self.task['task_id']})
        self.app.dispatch('delete_task', {'task_id': self.task['task_id']})
        self.assertTrue(old_cancel.is_set())
        replacement = self.new_task()
        new_a, _, new_cancel, _ = analysis_jobs.prepare_recalculation(
            self.app, 'recalculate_judgments', {'task_id': replacement['task_id']})
        self.assertEqual(new_a['analysis_id'], old_a['analysis_id'], 'Fixture must exercise actual SQLite ID reuse')
        before = copy.deepcopy(self.app.require('analysis', new_a['analysis_id']))
        with self.assertRaises(LookupError):
            analysis_jobs.finish_recalculation(self.app, old_a, old_modules, old_cancel, old_token)
        self.assertEqual(self.app.require('analysis', new_a['analysis_id']), before)
        self.assertIs(self.app.cancels[new_a['analysis_id']], new_cancel)
        self.assertFalse(new_cancel.is_set())

    def test_deleted_id_reuse_blocks_old_gpt_save(self):
        old = self.app.dispatch('recalculate_judgments', {'task_id': self.task['task_id']})
        operation = self.app.prepare_dispatch('generate_ai_text', {
            'analysis_id': old['analysis_id'], 'purpose': 'TASK_EXPLANATION',
        })
        self.app.dispatch('delete_task', {'task_id': self.task['task_id']})
        replacement = self.new_task()
        new = self.app.dispatch('recalculate_judgments', {'task_id': replacement['task_id']})
        self.assertEqual(new['analysis_id'], old['analysis_id'], 'Fixture must exercise actual SQLite ID reuse')
        before = copy.deepcopy(self.app.require('analysis', new['analysis_id']))
        with self.assertRaises(LookupError):
            operation()
        self.assertEqual(self.app.require('analysis', new['analysis_id']), before)
        self.assertEqual(before['ai'], [])


if __name__ == '__main__':
    unittest.main()
