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

    def test_facing_follows_nose_and_near_side_follows_the_facing_direction(self):
        self.assertEqual(quick_assess.guess_view(self.body(0.4, 0.9, 120)), {'forward_direction': 'SCREEN_RIGHT', 'camera_side': 'RIGHT', 'orientation': 'SIDE'})
        self.assertEqual(quick_assess.guess_view(self.body(0.9, 0.4, 80)), {'forward_direction': 'SCREEN_LEFT', 'camera_side': 'LEFT', 'orientation': 'SIDE'})

    def test_equal_confidence_uses_facing_geometry(self):
        # Facing the right edge of the picture shows the worker's right body to the camera; facing left shows the left.
        self.assertEqual(quick_assess.guess_view(self.body(0.8, 0.8, 120))['camera_side'], 'RIGHT')
        self.assertEqual(quick_assess.guess_view(self.body(0.8, 0.8, 80))['camera_side'], 'LEFT')

    def test_a_small_confidence_edge_for_the_far_side_does_not_flip_the_near_side(self):
        # Real photos: the far body was 0.05-0.11 more "confident" in total, and the near side used to be guessed wrong.
        self.assertEqual(quick_assess.guess_view(self.body(0.50, 0.55, 80))['camera_side'], 'LEFT')
        self.assertEqual(quick_assess.guess_view(self.body(0.55, 0.50, 120))['camera_side'], 'RIGHT')

    def test_a_clearly_hidden_facing_side_overrides_the_facing_direction(self):
        self.assertEqual(quick_assess.guess_view(self.body(0.2, 0.9, 80))['camera_side'], 'RIGHT', 'the left body is barely visible, so the right one faces the camera')

    def pose(self, shoulder_width, hip_width):
        return [point('nose', 100, 10, 0.9), point('left_ear', 95, 10, 0.9), point('right_ear', 105, 10, 0.9),
                point('left_shoulder', 100 + shoulder_width / 2, 50, 0.9), point('right_shoulder', 100 - shoulder_width / 2, 50, 0.9),
                point('left_hip', 100 + hip_width / 2, 150, 0.9), point('right_hip', 100 - hip_width / 2, 150, 0.9),
                point('left_wrist', 130, 120, 0.9), point('right_wrist', 70, 120, 0.9)]

    def test_wide_shoulders_and_hips_read_as_front_or_back(self):
        self.assertEqual(quick_assess.guess_view(self.pose(80, 60))['orientation'], 'FRONT')

    def test_a_worker_who_is_not_perfectly_square_to_the_camera_is_oblique_not_side(self):
        # Shoulder/hip width over torso length: the real "slightly turned" front photos measured 0.54/0.40 and 0.45/0.27.
        self.assertEqual(quick_assess.guess_view(self.pose(54, 40))['orientation'], 'OBLIQUE')
        self.assertEqual(quick_assess.guess_view(self.pose(45, 27))['orientation'], 'OBLIQUE')

    def test_overlapping_shoulders_or_hips_still_read_as_side(self):
        self.assertEqual(quick_assess.guess_view(self.pose(32, 27))['orientation'], 'SIDE')
        self.assertEqual(quick_assess.guess_view(self.pose(46, 13))['orientation'], 'SIDE', 'a raised arm can turn the shoulders, the hips still overlap')


class PhotoContext(unittest.TestCase):
    """What a photo shows beyond angles: sitting, and a hand above the shoulder (vertical cues survive a turned body)."""

    def legs(self, hip, knee, ankle, confidence=0.6, side='right'):
        return [point(f'{side}_hip', *hip, 0.6), point(f'{side}_knee', *knee, 0.6), point(f'{side}_ankle', *ankle, confidence)]

    def test_thigh_flat_and_hip_well_above_the_ankle_is_sitting(self):
        chair = self.legs((100, 100), (160, 102), (165, 170))
        self.assertTrue(quick_assess.seated_signal(chair, 'RIGHT'))

    def test_deep_squat_standing_and_unseen_feet_are_not_called_sitting(self):
        squat = self.legs((100, 135), (160, 112), (150, 165))
        standing = self.legs((100, 100), (104, 160), (100, 220))
        unseen = self.legs((100, 100), (160, 102), (165, 170), confidence=0.05)
        for legs in (squat, standing, unseen):
            self.assertFalse(quick_assess.seated_signal(legs, 'RIGHT'))

    def test_only_the_near_side_counts(self):
        chair = self.legs((100, 100), (160, 102), (165, 170), side='left')
        self.assertFalse(quick_assess.seated_signal(chair, 'RIGHT'))

    def torso(self, **extra):
        pts = [point('nose', 100, 10, 0.9), point('left_shoulder', 120, 50, 0.9), point('right_shoulder', 80, 50, 0.9),
               point('left_hip', 115, 150, 0.9), point('right_hip', 85, 150, 0.9)]
        arm = {'left_elbow': (125, 100), 'right_elbow': (75, 100), 'left_wrist': (125, 150), 'right_wrist': (75, 150)}
        arm.update(extra)
        return pts + [point(name, x, y, 0.8) for name, (x, y) in arm.items()]

    def test_a_hand_clearly_above_the_shoulder_is_an_overhead_arm_whichever_arm_it_is(self):
        self.assertFalse(quick_assess.arm_overhead_signal(self.torso()))
        self.assertTrue(quick_assess.arm_overhead_signal(self.torso(right_wrist=(75, 20))), 'wrist above the shoulder by ~30% of the torso')
        self.assertTrue(quick_assess.arm_overhead_signal(self.torso(left_elbow=(125, 40))), 'elbow above the shoulder')
        self.assertFalse(quick_assess.arm_overhead_signal(self.torso(left_wrist=(125, 80))), 'hand only at chest height')

    def test_an_arm_the_model_is_unsure_about_is_not_called_overhead(self):
        pts = [p if p['name'] != 'right_wrist' else dict(p, y_px=20, confidence=0.1) for p in self.torso()]
        self.assertFalse(quick_assess.arm_overhead_signal(pts))

    def test_reaching_to_a_keyboard_is_not_an_overhead_arm_but_a_raised_one_is(self):
        # The REBA posture tag fires from 45 degrees; the "hand over the head / elbow above the shoulder" work type needs ~90.
        profile = {'upper_arm_raise_deg': 45, 'trunk_flex_deg': 20, 'neck_forward_deg': 20}
        rows = lambda deg: {'RIGHT': [{'side': 'RIGHT', 'angle_code': 'UPPER_ARM_RAISE_VERT', 'value_deg': deg}]}
        self.assertFalse(quick_assess.posture_signals(rows(58), profile)['arm_raised'])
        self.assertTrue(quick_assess.posture_signals(rows(101), profile)['arm_raised'])

    def test_sitting_pre_checks_seated_and_never_knee_work(self):
        qs = {q['id']: q for q in quick_assess.questions({}, [], {'seated': True, 'knee_bent': True})}
        seated = next(i for i in qs['posture_flags']['items'] if i['key'] == 'seated')
        self.assertTrue(seated['suggested'])
        self.assertIn('앉', seated['evidence'])
        knee = next(i for i in qs['work_types']['items'] if i['key'] == 'knee')
        self.assertFalse(knee['suggested'], 'a person sitting on a chair is not crouching')
        plain = {q['id']: q for q in quick_assess.questions({}, [], {})}
        self.assertFalse(next(i for i in plain['posture_flags']['items'] if i['key'] == 'seated')['suggested'])

    def test_provisional_score_counts_a_seated_photo_as_seated(self):
        settings = create_service(os.path.join(tempfile.mkdtemp(), 's.db')).settings()['analysis']
        knee = [{'scope': 'COMMON', 'field': 'knee_band', 'value': 'OVER_60', 'low_confidence': False, 'angles': []}]
        standing = quick_assess.provisional(knee, [], settings)
        sitting = quick_assess.provisional(knee, [], settings, seated=True)
        self.assertLess(sitting['total'], standing['total'], 'bent knees on a chair must not add the legs penalty')
        self.assertNotIn('COMMON.seated', sitting['assumed'])
        self.assertIn('COMMON.seated', standing['assumed'])

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

    def test_one_checklist_replaces_eleven_cards_and_the_photo_pre_checks_what_it_shows(self):
        import re
        from ergo.engine.task_defaults import EXPOSURE_V2
        plain = quick_assess.questions({}, [], {})
        checklist = next(q for q in plain if q['id'] == 'work_types')
        self.assertFalse(any(i['suggested'] for i in checklist['items']))
        hinted = next(q for q in quick_assess.questions({}, [], {'arm_raised': True, 'trunk_flexed': True, 'knee_bent': True}) if q['id'] == 'work_types')
        self.assertEqual({i['key'] for i in hinted['items'] if i['suggested']}, {'arm_over', 'trunk_neck', 'knee'})
        self.assertTrue(all(i['evidence'] for i in hinted['items'] if i['suggested']))
        cards = [q for q in plain if q['kind'] == 'criterion']
        gates = {c['gate'] for c in cards}
        self.assertEqual(gates, {i['key'] for i in checklist['items']}, 'every work type has its follow-up card')
        for card in cards:
            self.assertEqual(card['show_if'], {'work_types': [card['gate']]}, 'a card shows only when its work type is ticked')
            self.assertTrue(card['implicit'])
            self.assertTrue(all('value' not in f for f in card['fields']), 'cards never carry prefilled values')
        codes = {f['to']['exposure'] for c in cards for f in c['fields'] if 'exposure' in f['to']}
        self.assertEqual(codes, set(EXPOSURE_V2), 'every daily-exposure input is reachable')
        covered = {c['criterion'] for c in cards if c['criterion']} | set(next(c for c in cards if c['gate'] == 'lift')['criteria'])
        self.assertEqual(covered, set(range(1, 12)), 'all eleven statutory criteria are fed by some follow-up')
        shown = ' '.join(q['text'] + ' ' + q.get('ask', '') + ' ' + ' '.join(i['label'] for i in q.get('items', [])) for q in plain if q['group'] in ('이 작업의 특징', '하루 시간·횟수'))
        self.assertIsNone(re.search(r'\d+호', shown), 'criterion numbers never appear in what the person reads')

    def test_low_confidence_angle_is_used_without_a_repeated_selection(self):
        low = {'scope': 'COMMON', 'field': 'trunk_base', 'value': 3, 'low_confidence': True, 'angles': [{'value_deg': 33.0}]}
        sure = {'scope': 'COMMON', 'field': 'knee_band', 'value': 'OVER_60', 'low_confidence': False, 'angles': [{'value_deg': 71.0}]}
        ids = {q['id']: q for q in quick_assess.questions({}, [low, sure], {})}
        self.assertEqual(ids['trunk_base']['suggested'], 3)
        self.assertEqual(ids['trunk_base']['show_if'], {'context': ['NO']})
        self.assertEqual(ids['knee_band']['show_if'], {'context': ['NO']}, 'a reliable value is not asked at all')

    def test_work_info_has_no_defaults(self):
        qs = {q['id']: q for q in quick_assess.questions({}, [], {})}
        self.assertTrue(qs['task_name']['required'])
        for key in ('investigator', 'department', 'process'):
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
        self.assertEqual(len(result['views']['RIGHT']['points']), self.ctx.settings()['analysis']['pose_model']['point_count'])
        self.assertEqual(result['views']['RIGHT']['engine']['provider'],'mediapipe')
        self.assertIsNotNone(result['score']['total'])
        self.assertTrue(result['measured'])
        self.assertEqual(self.ctx.dispatch('list_analysis_history', {'task_id': self.task['task_id']}), [])
        self.assertEqual(self.ctx.dispatch('get_task', {'task_id': self.task['task_id']})['task'], before)

    def test_photo_in_the_wrong_slot_is_still_measured_on_its_visible_side(self):
        # The public example faces right and shows the worker's RIGHT body; putting it in the LEFT slot used to give nothing.
        right = self.ctx.dispatch('quick_preview', {'task_id': self.task['task_id'], 'views': {'RIGHT': self.photo['photo_id']}})
        wrong = self.ctx.dispatch('quick_preview', {'task_id': self.task['task_id'], 'views': {'LEFT': self.photo['photo_id']}})
        keys = lambda r: {(m['scope'], m['field'], m['value']) for m in r['measured']}
        self.assertTrue(keys(right))
        self.assertEqual(keys(wrong), keys(right), 'same photo, same measurements regardless of the slot')
        self.assertIn('OTHER_SIDE', [d['code'] for d in wrong['diagnostics']])
        self.assertEqual({m['view'] for m in wrong['measured']}, {'LEFT'}, 'measurements stay labelled with the slot the user chose')
        self.assertIsNotNone(wrong['score'])

    def test_photo_from_another_task_is_rejected(self):
        with self.assertRaises(ValueError):
            self.ctx.dispatch('quick_preview', {'task_id': self.other['task_id'], 'views': {'LEFT': self.photo['photo_id']}})


if __name__ == '__main__':
    unittest.main()
