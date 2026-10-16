"""Independent counterexamples for the 2.0 local implementation review."""
import copy
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

from ergo.db import storage
from ergo.engine.burden_rules import calculate_v2
from ergo.gpt.payload import build_numeric_summary
from ergo.engine.task_defaults import evidence, task_input
from ergo.service import application as app
from tests.test_v2_rules import qualifying_case


class RuleRegressions(unittest.TestCase):
    def test_c9_unknown_mass_cannot_be_promoted_by_a_position_count(self):
        conditions, legal = qualifying_case(9)
        criterion = legal['criteria'][8]
        criterion['rows'][0]['load_mass_kg'] = None
        criterion['totals'].update(row_ids=[], below_knee_count_day=None,
                                  above_shoulder_count_day=None, extended_arm_count_day=None,
                                  union_count_day=None)
        result = calculate_v2(conditions, legal)['judgments'][8]
        self.assertEqual(result['computed_status'], 'NEEDS_INPUT')
        self.assertIn('criteria.9.rows.r9.load_mass_kg', result['missing_fields'])

    def test_all_time_unions_are_bounded_by_the_daily_work_duration(self):
        for number in (6, 7, 10, 11):
            with self.subTest(number=number):
                conditions, legal = qualifying_case(number)
                conditions['daily_work_min'] = 60
                criterion = legal['criteria'][number-1]
                row = criterion['rows'][0]
                row['minutes'] = 60
                other = copy.deepcopy(row); other['row_id'] = 'second'
                criterion['rows'].append(other)
                criterion['union'].update(row_ids=[row['row_id'], 'second'], value=120)
                result = calculate_v2(conditions, legal)['judgments'][number-1]
                self.assertEqual(result['computed_status'], 'NEEDS_REVIEW')
                self.assertIn('INPUT_CONFLICT', result['review_reasons'])


class PersistenceRegressions(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='loco-review-')
        self.db = str(Path(self.temp.name) / 'isolated.db')
        self.db_patch = patch.object(app, 'DB', self.db)
        self.db_patch.start()
        self.survey = app.dispatch('create_survey', {'draft': {
            'survey_type': 'REGULAR', 'survey_date': '2026-10-16', 'title': 'isolated'}})
        self.task = app.dispatch('create_task', {'survey_id': self.survey['survey_id'], 'draft': task_input({})})

    def tearDown(self):
        self.db_patch.stop()
        self.temp.cleanup()

    def calculate(self):
        return app.dispatch('recalculate_judgments', {'task_id': self.task['task_id']})

    def test_conclusion_can_be_changed_and_cleared_without_stale_worker_resurrection(self):
        a = self.calculate()
        snapshot = copy.deepcopy(a['snapshot'])
        for status in ('APPLICABLE', 'NOT_APPLICABLE', None):
            conclusion = dict(criterion_no=1, status=status, reason=str(status), evidence=evidence(),
                              reviewer='review', reviewed_at='2026-10-16T00:00:00Z')
            saved = app.dispatch('set_investigator_conclusion', {'analysis_id': a['analysis_id'], 'conclusion': conclusion})
            self.assertEqual(saved['judgment']['judgments'][0]['investigator'], conclusion)
            self.assertEqual(saved['judgment']['judgments'][0]['effective_status'], status or 'NEEDS_INPUT')
            app.persist_analysis(a)
            self.assertEqual(app.analysis(a['analysis_id'])['judgment']['judgments'][0]['investigator'], conclusion)
        self.assertEqual(app.analysis(a['analysis_id'])['snapshot'], snapshot)

    def test_display_edit_and_review_invalidation_roll_back_together(self):
        a = self.calculate()
        survey = app.require('survey', self.survey['survey_id'])
        review = dict(survey['review'], reviewed=True, reviewed_analysis_ids=[a['analysis_id']],
                      reviewed_metadata_revision=survey['metadata_revision'])
        app.dispatch('set_survey_review', {'survey_id': survey['survey_id'], 'review': review})
        def fail(result):
            result['judgment'] = None
            raise RuntimeError('injected write failure')
        with self.assertRaises(RuntimeError):
            app.edit_result(a['analysis_id'], fail, invalidate_review=True)
        self.assertIsNotNone(app.analysis(a['analysis_id'])['judgment'])
        self.assertTrue(app.require('survey', survey['survey_id'])['review']['reviewed'])

    def test_late_gpt_response_does_not_restore_running_or_erase_finished_calculation(self):
        config = app.settings(); config['gpt_enabled'] = True
        app.dispatch('update_settings', {'settings': config})
        a = app.new_analysis(self.task, ['judgment'])
        entered, release = threading.Event(), threading.Event()
        errors, response = [], []
        def delayed(*args):
            entered.set()
            if not release.wait(5): raise RuntimeError('test synchronization timeout')
            return None, 'INJECTED_API_FAILURE'
        def generate():
            try: response.append(app.dispatch('generate_ai_text', {'analysis_id': a['analysis_id']}))
            except BaseException as error: errors.append(error)
        with patch.object(app.gpt_client, 'generate', delayed):
            worker = threading.Thread(target=generate)
            worker.start()
            try:
                self.assertTrue(entered.wait(5))
                app.run(a, ['judgment'], threading.Event())
            finally:
                release.set(); worker.join(5)
        self.assertFalse(worker.is_alive())
        self.assertEqual(errors, [])
        saved = app.analysis(a['analysis_id'])
        self.assertEqual(saved['status'], 'FINISHED')
        self.assertEqual(len(saved['judgment']['judgments']), 11)
        self.assertEqual(saved['module_states']['judgment'], 'INCOMPLETE')
        self.assertFalse(response[0]['source_current'])
        self.assertEqual(saved['ai'][0]['fallback_reason'], 'INJECTED_API_FAILURE')

    def test_ai_edits_and_activation_survive_a_calculation_write(self):
        a = self.calculate()
        config = app.settings(); config['gpt_enabled'] = True
        app.dispatch('update_settings', {'settings': config})
        with patch.object(app.gpt_client, 'generate', return_value=(None, 'MISSING_KEY')):
            text = app.dispatch('generate_ai_text', {'analysis_id': a['analysis_id']})['text']
        app.dispatch('edit_ai_text', {'analysis_id': a['analysis_id'], 'text_id': text['text_id'], 'text': 'reviewed explanation'})
        app.dispatch('apply_ai_text', {'analysis_id': a['analysis_id'], 'text_id': text['text_id'], 'use_edited': True})
        app.persist_analysis(a)
        saved = app.analysis(a['analysis_id'])['ai'][0]
        self.assertEqual(saved['edited_text'], 'reviewed explanation')
        self.assertEqual(saved['applied_text'], 'reviewed explanation')
        self.assertTrue(saved['is_active'])

    def test_deleted_analysis_is_not_recreated_by_late_calculation_or_ai(self):
        a = self.calculate()
        app.dispatch('delete_task', {'task_id': self.task['task_id']})
        app.persist_analysis(a)
        self.assertIsNone(storage.get_analysis(a['analysis_id'], db_path=self.db))
        with self.assertRaises(LookupError):
            app.edit_result(a['analysis_id'], lambda result: result.update(ai=[]))

    def test_related_analysis_settings_increment_once_and_ui_settings_do_not(self):
        scope = dict(judgment=True, pose=False, tags=True, reba=False)
        app.dispatch('set_analysis_scope', {'task_id': self.task['task_id'], 'scope': scope})
        a = self.calculate(); before = app.require('task', self.task['task_id'])
        config = app.settings(); config['analysis']['posture_profile']['trunk_flex_deg'] = 40
        app.dispatch('update_settings', {'settings': config})
        after = app.require('task', self.task['task_id'])
        self.assertEqual(after['input_revision'], before['input_revision']+1)
        self.assertEqual(app.analysis(a['analysis_id'])['currentness'], 'STALE')
        config['ui']['loco_mode'] = 'quiet'
        app.dispatch('update_settings', {'settings': config})
        self.assertEqual(app.require('task', self.task['task_id'])['input_revision'], after['input_revision'])
        self.assertEqual(app.analysis(a['analysis_id'])['snapshot'], a['snapshot'])

    def test_stale_task_save_is_rejected_before_overwriting_newer_inputs(self):
        old = app.require('task', self.task['task_id'])
        app.dispatch('rename_task', {'task_id': old['task_id'], 'task_name': 'newer'})
        with self.assertRaisesRegex(ValueError, '다른 화면'):
            app.dispatch('save_task_input', {'task_id': old['task_id'], 'input': app.task_input(old),
                                             'expected_revision': old['input_revision']})
        self.assertEqual(app.require('task', old['task_id'])['task_name'], 'newer')

    def test_reused_judgment_keeps_its_module_state(self):
        a = self.calculate()
        b = app.dispatch('recalculate_tags', {'task_id': self.task['task_id']})
        self.assertEqual(b['judgment'], a['judgment'])
        self.assertEqual(b['module_states']['judgment'], 'INCOMPLETE')

    def test_review_history_survives_input_invalidation_and_rereview(self):
        a = self.calculate()
        mark = dict(reviewed=True, reviewed_analysis_ids=[a['analysis_id']], reviewed_metadata_revision=0,
                    reviewer='first reviewer', reviewed_at='2026-10-16T00:00:00Z', note='first review')
        app.dispatch('set_survey_review', {'survey_id': self.survey['survey_id'], 'review': mark})
        app.dispatch('rename_task', {'task_id': self.task['task_id'], 'task_name': 'edited input'})
        survey = app.require('survey', self.survey['survey_id'])
        self.assertFalse(survey['review']['reviewed'])
        previous = survey['review']['history'][0]
        self.assertEqual(previous['reviewed_analysis_ids'], [a['analysis_id']])
        self.assertEqual(previous['note'], 'first review')
        self.assertEqual(previous['reason'], 'TASK_INPUT_CHANGED')
        mark['reviewer'] = 'second reviewer'
        app.dispatch('set_survey_review', {'survey_id': self.survey['survey_id'], 'review': mark})
        self.assertEqual(app.require('survey', self.survey['survey_id'])['review']['history'][0], previous)

    def test_stale_metadata_review_is_rejected_without_rebinding_it(self):
        survey = app.require('survey', self.survey['survey_id'])
        app.dispatch('update_survey', {'survey_id': survey['survey_id'], 'draft': dict(survey, title='new metadata')})
        mark = dict(survey['review'], reviewed=True, reviewed_metadata_revision=0)
        with self.assertRaisesRegex(ValueError, '조사 정보가 변경'):
            app.dispatch('set_survey_review', {'survey_id': survey['survey_id'], 'review': mark})
        self.assertFalse(app.require('survey', survey['survey_id'])['review']['reviewed'])

    def test_export_uses_one_read_only_sqlite_transaction_for_all_rows(self):
        a = self.calculate()
        with patch('ergo.db.storage_common.open_db', wraps=storage.open_db) as opened:
            exported = app.export_snapshot(self.survey['survey_id'], [])
        self.assertEqual(opened.call_count, 1)
        self.assertEqual(exported['analyses'][0]['snapshot'], a['snapshot'])

    def test_export_receipt_and_log_expose_the_actual_version_and_sheets(self):
        self.calculate()
        destination=str(Path(self.temp.name)/'report.xlsx')
        receipt=app.dispatch('export_excel',{'survey_id':self.survey['survey_id'],'spec':{
            'destination':destination,'analysis_ids':[],'comparisons':[],'include_representative':False}})
        self.assertEqual(receipt['report_version'],'2.0')
        logs=app.dispatch('list_export_logs',{'survey_id':self.survey['survey_id']})
        self.assertEqual(logs[0]['receipt'],receipt)
        self.assertEqual(receipt['sheets'],['요약','작업별 결과','확인사항','판정 근거'])

    def test_recalculate_is_an_explicit_scope_request(self):
        before=app.require('task',self.task['task_id'])
        a=app.dispatch('recalculate_reba',{'task_id':self.task['task_id']})
        after=app.require('task',self.task['task_id'])
        self.assertTrue(after['analysis_scope']['reba'])
        self.assertEqual(after['input_revision'],before['input_revision']+1)
        self.assertEqual(a['module_states']['reba'],'INCOMPLETE')
        app.dispatch('create_task',{'survey_id':self.survey['survey_id'],'draft':task_input({})})
        preview=app.dispatch('preview_excel',{'survey_id':self.survey['survey_id'],'analysis_ids':[]})
        self.assertEqual(preview['counts']['incomplete_reba_count'],0)
        self.assertTrue(preview['state']['has_incomplete'])

    def test_malformed_numeric_input_is_never_forwarded_as_private_free_text(self):
        task=app.require('task',self.task['task_id'])
        task['legal']['exposures'][0]['minutes']='private free text in a numeric input'
        app.dispatch('set_legal_inputs',{'task_id':task['task_id'],'legal':task['legal']})
        result=self.calculate()
        self.assertEqual(result['judgment']['judgments'][0]['computed_status'],'NEEDS_REVIEW')
        self.assertNotIn('private free text',str(build_numeric_summary(result)))

    def test_deleting_an_absent_photo_is_an_idempotent_ack(self):
        self.assertIn('message',app.dispatch('delete_photo',{'photo_id':99999}))


if __name__ == '__main__':
    unittest.main()
