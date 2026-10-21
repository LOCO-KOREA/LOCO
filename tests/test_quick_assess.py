import os
import tempfile
import unittest
from pathlib import Path

from ergo.engine import quick_assess
from ergo.engine.task_defaults import task_input
from ergo.service.application import create_service

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / '.local' / 'fixtures' / 'tensorflow-movenet-example.jpeg'
MODEL = ROOT / 'models' / 'movenet_lightning.tflite'


def point(name, x, y, confidence):
    return {'name': name, 'x_px': x, 'y_px': y, 'confidence': confidence}


class GuessView(unittest.TestCase):
    def body(self, left, right, nose_x):
        names = ['shoulder', 'elbow', 'wrist', 'hip', 'knee', 'ankle']
        pts = [point('nose', nose_x, 10, 0.9), point('left_ear', 100, 10, 0.9), point('right_ear', 100, 10, 0.9)]
        pts += [point(f'left_{n}', 100, 50, left) for n in names] + [point(f'right_{n}', 100, 50, right) for n in names]
        return pts

    def test_facing_follows_nose_and_near_side_follows_confidence(self):
        self.assertEqual(quick_assess.guess_view(self.body(0.4, 0.9, 120)), {'forward_direction': 'SCREEN_RIGHT', 'camera_side': 'RIGHT', 'orientation': 'SIDE'})
        self.assertEqual(quick_assess.guess_view(self.body(0.9, 0.4, 80)), {'forward_direction': 'SCREEN_LEFT', 'camera_side': 'LEFT', 'orientation': 'SIDE'})

    def test_equal_confidence_uses_facing_geometry(self):
        self.assertEqual(quick_assess.guess_view(self.body(0.8, 0.8, 120))['camera_side'], 'LEFT')

    def test_wide_shoulders_and_hips_read_as_front_or_back(self):
        pts = [point('nose', 100, 10, 0.9), point('left_ear', 95, 10, 0.9), point('right_ear', 105, 10, 0.9),
               point('left_shoulder', 140, 50, 0.9), point('right_shoulder', 60, 50, 0.9), point('left_hip', 130, 150, 0.9),
               point('right_hip', 70, 150, 0.9), point('left_wrist', 140, 120, 0.9), point('right_wrist', 60, 120, 0.9)]
        self.assertEqual(quick_assess.guess_view(pts)['orientation'], 'FRONT')

    def test_no_head_or_hands_gives_no_guess(self):
        self.assertIsNone(quick_assess.guess_view([point('left_hip', 1, 1, 0.9)]))


class Questions(unittest.TestCase):
    def test_measured_fields_are_not_asked_and_hidden_arm_offers_visible_value(self):
        measured = [{'scope': 'COMMON', 'field': 'trunk_base', 'value': 3}, {'scope': 'RIGHT', 'field': 'upper_arm_base', 'value': 3}]
        ids = {q['id']: q for q in quick_assess.questions({}, measured, {})}
        self.assertEqual(ids['trunk_base']['show_if'], {'context': ['NO']}, 'measured values are asked only if the photo is unusable')
        self.assertIsNone(ids['knee_band']['show_if'])
        hidden = ids['upper_arm_base_left']
        self.assertEqual(hidden['target'], {'type': 'manual', 'scope': 'LEFT', 'field': 'upper_arm_base'})
        self.assertEqual(hidden['choices'][0]['value'], 3)
        self.assertEqual(hidden['show_if'], {'context': ['YES']})
        self.assertEqual(len({c['value'] for c in hidden['choices']}), len(hidden['choices']))

    def test_all_eleven_criteria_are_asked_and_photo_signals_only_add_a_hint(self):
        from ergo.engine.task_defaults import EXPOSURE_V2
        plain = {q['criterion']: q for q in quick_assess.questions({}, [], {}) if q['kind'] == 'criterion'}
        self.assertEqual(sorted(plain), list(range(1, 12)))
        self.assertFalse(any(q['hint'] for q in plain.values()))
        hinted = {q['criterion']: q for q in quick_assess.questions({}, [], {'arm_raised': True, 'trunk_flexed': True, 'knee_bent': True}) if q['kind'] == 'criterion'}
        self.assertEqual({n for n, q in hinted.items() if q['hint']}, {3, 4, 5})
        codes = {f['to']['exposure'] for q in plain.values() for f in q['fields'] if 'exposure' in f['to']}
        self.assertEqual(codes, set(EXPOSURE_V2), 'every daily-exposure input must be reachable')
        for q in plain.values():
            self.assertIsNone(q.get('suggested'))
            self.assertTrue(all('value' not in f for f in q['fields']), 'criterion cards never carry prefilled values')

    def test_work_info_has_no_defaults_and_conditional_participation_method(self):
        qs = {q['id']: q for q in quick_assess.questions({}, [], {})}
        self.assertTrue(qs['task_name']['required'])
        self.assertEqual(qs['participation_method']['show_if'], {'participation': ['YES']})
        for key in ('situation_equipment', 'participation', 'symptom'):
            self.assertIsNone(qs[key].get('suggested'))

    def test_every_rebar_item_is_reachable_from_some_question(self):
        reachable = set()
        for q in quick_assess.questions({}, [], {}):
            target = q['target']
            if target['type'] == 'manual':
                reachable.add(target['field'])
            for item in q.get('items', []):
                reachable.update(s['field'] for s in item['sets'])
        missing = set(quick_assess.NO_BURDEN) - reachable
        self.assertEqual(missing, set())


class MultiView(unittest.TestCase):
    def test_side_photos_keep_each_arm_and_the_heavier_trunk(self):
        left = [{'scope': 'COMMON', 'field': 'trunk_base', 'value': 2, 'view': 'LEFT'}, {'scope': 'LEFT', 'field': 'upper_arm_base', 'value': 2, 'view': 'LEFT'}]
        right = [{'scope': 'COMMON', 'field': 'trunk_base', 'value': 3, 'view': 'RIGHT'}, {'scope': 'RIGHT', 'field': 'upper_arm_base', 'value': 4, 'view': 'RIGHT'}]
        merged = {(m['scope'], m['field']): m for m in quick_assess.merge_measured(left, right)}
        self.assertEqual(merged[('COMMON', 'trunk_base')]['value'], 3)
        self.assertEqual(merged[('COMMON', 'trunk_base')]['alternatives'][0]['value'], 2)
        self.assertEqual((merged[('LEFT', 'upper_arm_base')]['value'], merged[('RIGHT', 'upper_arm_base')]['value']), (2, 4))

    def front(self, tilt_x, elbow_x):
        return [point('left_shoulder', 120 + tilt_x, 100, 0.9), point('right_shoulder', 80 + tilt_x, 100, 0.9),
                point('left_hip', 115, 200, 0.9), point('right_hip', 85, 200, 0.9), point('nose', 100 + tilt_x, 70, 0.9),
                point('left_elbow', 120 + tilt_x + elbow_x, 150, 0.9), point('right_elbow', 80 + tilt_x, 150, 0.9)]

    def test_front_photo_suggests_side_bend_and_abduction_only_beyond_thresholds(self):
        upright = {f['key']: f for f in quick_assess.front_measure(self.front(0, 0))}
        self.assertFalse(any(f['suggested'] for f in upright.values()))
        bent = {f['key']: f for f in quick_assess.front_measure(self.front(30, 60))}
        self.assertTrue(bent['trunk_turn']['suggested'])
        self.assertTrue(bent['arm_abducted']['suggested'])

    def test_frontal_suggestions_mark_checklist_items_without_answering_them(self):
        front = [{'key': 'arm_abducted', 'label': '팔 옆으로 벌림', 'value_deg': 40.0, 'suggested': True}]
        flags = next(q for q in quick_assess.questions({'FRONT': None}, [], {}, front) if q['id'] == 'posture_flags')
        item = next(i for i in flags['items'] if i['key'] == 'arm_abducted')
        self.assertTrue(item['suggested'])
        self.assertIn('40.0', item['evidence'])
        self.assertFalse(next(i for i in flags['items'] if i['key'] == 'seated')['suggested'])

    def test_contract_accepts_only_known_views(self):
        from ergo.contracts import validate_request
        validate_request('quick_preview', {'task_id': 1, 'views': {'LEFT': 1, 'FRONT': 2}})
        for bad in ({}, {'BACK': 1}, {'LEFT': 0}, {'LEFT': '1'}):
            with self.assertRaises(ValueError):
                validate_request('quick_preview', {'task_id': 1, 'views': bad})


@unittest.skipUnless(FIXTURE.is_file() and MODEL.is_file(), 'public example photo and official model required')
class QuickPreviewService(unittest.TestCase):
    def setUp(self):
        self.ctx = create_service(os.path.join(tempfile.mkdtemp(), 'quick.db'))
        survey = self.ctx.dispatch('create_survey', {'draft': {'survey_type': 'REGULAR', 'title': 'quick'}})
        self.task = self.ctx.dispatch('create_task', {'survey_id': survey['survey_id'], 'draft': task_input({'task_name': 'quick'})})
        self.other = self.ctx.dispatch('create_task', {'survey_id': survey['survey_id'], 'draft': task_input({'task_name': 'other'})})
        self.photo = self.ctx.dispatch('import_photos', {'task_id': self.task['task_id'], 'file_paths': [str(FIXTURE)]})['added'][0]

    def test_preview_scores_photo_without_saving_anything(self):
        before = self.ctx.dispatch('get_task', {'task_id': self.task['task_id']})['task']
        result = self.ctx.dispatch('quick_preview', {'task_id': self.task['task_id'], 'views': {'RIGHT': self.photo['photo_id']}})
        self.assertEqual(len(result['views']['RIGHT']['points']), 17)
        self.assertIsNotNone(result['score']['total'])
        self.assertTrue(result['measured'])
        self.assertEqual(self.ctx.dispatch('list_analysis_history', {'task_id': self.task['task_id']}), [])
        self.assertEqual(self.ctx.dispatch('get_task', {'task_id': self.task['task_id']})['task'], before)

    def test_photo_from_another_task_is_rejected(self):
        with self.assertRaises(ValueError):
            self.ctx.dispatch('quick_preview', {'task_id': self.other['task_id'], 'views': {'LEFT': self.photo['photo_id']}})


if __name__ == '__main__':
    unittest.main()
