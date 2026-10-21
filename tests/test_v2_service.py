"""Application boundary, revision, photo reconciliation, and cancellation checks."""
import copy
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

from ergo.db import storage
from ergo.engine.task_defaults import default_settings, evidence, task_input
from tests.fixtures.v13 import EXPOSURES, capture as legacy_capture
from ergo.service import application


class AppCase(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.db = str(Path(self.temp.name) / 'test.db')
        self.db_patch = patch.object(application, 'DB', self.db)
        self.db_patch.start()
        self.survey = application.dispatch('create_survey', {'draft': {
            'survey_type': 'REGULAR', 'survey_date': '2026-10-23', 'investigator': '조사자',
            'department': '팀', 'process': '공정', 'title': '검증 조사', 'occasional_reason': None}})
        self.task = application.dispatch('create_task', {'survey_id': self.survey['survey_id'], 'draft': task_input({})})

    def tearDown(self):
        self.db_patch.stop()
        self.temp.cleanup()

    def photo(self, task_id, name):
        return storage.create_photo(task_id, {'file_path': name, 'file_name': name,
            'width_px': 640, 'height_px': 480, 'consent': 'UNKNOWN', 'notes': []}, db_path=self.db)

    def test_new_work_is_general_v2_and_has_eleven_unknown_criteria(self):
        saved = application.dispatch('get_task', {'task_id': self.task['task_id']})['task']
        self.assertEqual(saved['schema_version'], '2.0')
        self.assertEqual(saved['task_kind'], 'GENERAL_TASK')
        self.assertEqual(len(saved['legal']['criteria']), 11)
        self.assertTrue(all(x['condition_present']=='UNKNOWN' for x in saved['legal']['criteria']))
        self.assertEqual(saved['capture']['slots'], [])

    def test_bad_criterion_order_is_rejected_before_revision_changes(self):
        task = application.dispatch('get_task', {'task_id': self.task['task_id']})['task']
        incoming = application.task_input(task)
        incoming['legal']['criteria'][0]['criterion_no'] = 2
        with self.assertRaises(ValueError):
            application.dispatch('save_task_input', {'task_id': task['task_id'], 'input': incoming})
        after = application.dispatch('get_task', {'task_id': task['task_id']})['task']
        self.assertEqual(after['input_revision'], task['input_revision'])
        self.assertEqual(after['legal'], task['legal'])

    def test_full_task_save_updates_revision_once(self):
        task = application.dispatch('get_task', {'task_id': self.task['task_id']})['task']
        incoming = application.task_input(task)
        incoming['task_name'] = '조립 작업'
        saved = application.dispatch('save_task_input', {'task_id': task['task_id'], 'input': incoming})
        self.assertEqual(saved['input_revision'], task['input_revision'] + 1)
        self.assertEqual(saved['task_name'], '조립 작업')

    def test_legacy_v13_task_is_read_without_write_and_keeps_snapshot_on_explicit_edit(self):
        criteria = [dict(criterion_no=n, condition_present='UNKNOWN',
                         posture_interpretation_pending=False, evidence=evidence())
                    for n in range(1, 12)]
        criteria[3].update(unsupported='UNKNOWN', posture_restricted='UNKNOWN')
        criteria[5].update(unsupported='UNKNOWN', pinch_mass_kg=None, pinch_force_kg_equiv=None)
        criteria[6].update(unsupported='UNKNOWN', single_hand_mass_kg=None, grip_force_kg_equiv=None)
        criteria[8].update(below_knee_count_day=None, above_shoulder_count_day=None,
                            extended_arm_count_day=None, union_count_day=None)
        criteria[9].update(lift_rate_min=None)
        criteria[10].update(impact_rate_hour=None)
        legacy = {
            'schema_version': '1.3', 'task_kind': 'BOX_LIFT', 'task_name': '기존 상자 작업',
            'worker_count': 2,
            'conditions': {'worker_code': '기존코드', 'method_description': '기존 방법',
                'shelf_height_cm': 120, 'daily_work_min': 480, 'one_off': 'NO',
                'planned_duration_months': 12, 'annual_work_days': 220, 'box_mass_kg': 30,
                'evidence': evidence()},
            'legal': {'criteria': criteria, 'exposures': [
                dict(condition_code=code, minutes=None, evidence=evidence()) for code in EXPOSURES],
                'lift_count_day': 10},
            'capture': legacy_capture(), 'manual': [],
        }
        task_id = storage.create_task(self.survey['survey_id'], legacy, 'created', 'updated', db_path=self.db)
        old_snapshot = {
            'schema_version': '1.3', 'task_id': task_id, 'input_revision': 0,
            'task_name': legacy['task_name'], 'conditions': copy.deepcopy(legacy['conditions']),
            'legal': copy.deepcopy(legacy['legal']), 'capture': copy.deepcopy(legacy['capture']),
            'manual': [], 'photos': [], 'settings': default_settings()['analysis'],
        }
        old_analysis_id = storage.create_analysis(task_id, 0, 'FINISHED', old_snapshot, 'created',
            result={'pose': None, 'slot_tags': [], 'tags': [], 'reba': None,
                    'judgment': {'judgments': []}, 'ai': [], 'notes': []}, db_path=self.db)

        opened = application.dispatch('get_task', {'task_id': task_id})
        self.assertEqual(opened['source_schema_version'], '1.3')
        self.assertEqual(opened['task']['schema_version'], '2.0')
        self.assertEqual(opened['task']['capture']['protocol'], 'GENERAL_STILLS_V1')
        raw_after_read = storage.get_task(task_id, db_path=self.db)
        self.assertEqual({key: raw_after_read[key] for key in legacy}, legacy)
        history = application.dispatch('list_analysis_history', {'task_id': task_id})
        self.assertEqual(history[0]['snapshot']['schema_version'], '1.3')

        edited = application.dispatch('rename_task', {'task_id': task_id, 'task_name': '수정한 기존 작업'})
        self.assertEqual(edited['schema_version'], '2.0')
        self.assertEqual(edited['input_revision'], 1)
        self.assertEqual(edited['legacy_input'], legacy)
        self.assertEqual(storage.get_analysis(old_analysis_id, db_path=self.db)['snapshot'], old_snapshot)

    def test_photo_label_change_preserves_observation_but_camera_change_clears_it(self):
        photo_id = self.photo(self.task['task_id'], 'one.jpg')
        task = application.dispatch('get_task', {'task_id': self.task['task_id']})['task']
        slot = {'slot_no': 7, 'photo_id': photo_id, 'analysis_target': True, 'label': '첫 사진',
                'camera_side': 'LEFT', 'forward_direction': 'SCREEN_RIGHT', 'side_view_verified': 'YES',
                'observation': {'load_state': 'MEASURED', 'measured_load_kg': 5.0, 'single_person': 'YES',
                    'full_frame': 'YES', 'normal_work': 'YES', 'evidence': {'source': 'DIRECT_OBSERVATION'}}}
        task['capture'] = {'protocol': 'GENERAL_STILLS_V1', 'slots': [slot]}
        task['manual'] = [{'slot_no': 7, 'photo_id': photo_id, 'scope': 'COMMON', 'field': 'trunk_base'}]
        application.save_task(task, force=True)
        edited = copy.deepcopy(task['capture']); edited['slots'][0]['label'] = '표시명만 수정'
        application.reconcile_capture(task, edited)
        self.assertEqual(task['capture']['slots'][0]['observation']['measured_load_kg'], 5.0)
        self.assertEqual(len(task['manual']), 1)
        observed = copy.deepcopy(task['capture']); observed['slots'][0]['observation']['measured_load_kg'] = 8.0
        application.reconcile_capture(task, observed)
        self.assertEqual(task['capture']['slots'][0]['observation']['measured_load_kg'], 8.0)
        moved = copy.deepcopy(task['capture']); moved['slots'][0]['camera_side'] = 'RIGHT'
        application.reconcile_capture(task, moved)
        self.assertEqual(task['capture']['slots'][0]['observation']['load_state'], 'UNKNOWN')
        self.assertEqual(task['capture']['slots'][0]['side_view_verified'], 'UNKNOWN')
        self.assertEqual(task['manual'], [])

    def test_photo_from_another_task_cannot_be_attached(self):
        other_task = application.dispatch('create_task', {'survey_id': self.survey['survey_id'], 'draft': task_input({})})
        photo_id = self.photo(other_task['task_id'], 'foreign.jpg')
        task = application.dispatch('get_task', {'task_id': self.task['task_id']})['task']
        slot = {'slot_no': 1, 'photo_id': photo_id, 'analysis_target': True, 'label': 'x',
                'camera_side': None, 'forward_direction': None, 'side_view_verified': 'UNKNOWN',
                'observation': {'load_state': 'UNKNOWN'}}
        with self.assertRaisesRegex(ValueError, '속하지 않습니다'):
            application.reconcile_capture(task, {'protocol': 'GENERAL_STILLS_V1', 'slots': [slot]})

    def test_cancellation_stops_remaining_modules_after_current_pose(self):
        photo_ids = [self.photo(self.task['task_id'], f'{n}.jpg') for n in range(2)]
        task = application.dispatch('get_task', {'task_id': self.task['task_id']})['task']
        task['capture'] = {'protocol': 'GENERAL_STILLS_V1', 'slots': [
            {'slot_no': i+1, 'photo_id': photo_id, 'analysis_target': True, 'label': f'사진 {i+1}',
             'camera_side': 'LEFT', 'forward_direction': 'SCREEN_RIGHT', 'side_view_verified': 'YES',
             'observation': {'load_state': 'UNKNOWN', 'single_person': 'YES', 'full_frame': 'YES', 'normal_work': 'YES'}}
            for i, photo_id in enumerate(photo_ids)]}
        task = application.save_task(task, force=True)
        modules = ['pose', 'tags', 'reba', 'judgment']
        analysis = application.new_analysis(task, modules)
        cancel = threading.Event(); calls = []
        def process(slot, snapshot):
            calls.append(slot['slot_no']); cancel.set()
            return {'slot_no': slot['slot_no'], 'photo_id': slot['photo_id'], 'status': 'VALID',
                    'diagnostics': [], 'points': [], 'angles': []}
        with patch.object(application.pose, 'process', side_effect=process):
            application.run(analysis, modules, cancel, application._context.analysis_token(analysis['analysis_id']))
        result = application.analysis(analysis['analysis_id'])
        self.assertEqual(calls, [1])
        self.assertEqual(result['status'], 'CANCELED')
        self.assertEqual(result['module_states'], {key: 'CANCELED' for key in modules})
        self.assertEqual([x['status'] for x in result['pose']['slots']], ['VALID', 'CANCELED'])


if __name__ == '__main__':
    unittest.main()
