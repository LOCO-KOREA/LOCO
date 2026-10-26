"""One-click form shortcuts fill answers the user then confirms; they never answer for the user."""
import json
import unittest
from pathlib import Path
from unittest.mock import patch
from ergo.engine.task_defaults import task_input
from ergo.intake import contract, facts, planner
from ergo.report.plain import _manual_rows
import test_adaptive_intake as fixtures
from test_photo_fact_ownership import observation, preview

MOTION = ('shock_force', 'static_over_1min', 'small_repeat_over_4min', 'rapid_change_or_unstable')
CONFIRM = [dict(target='context', value='YES'), dict(target='load', value='UNLOADED')]
SIDE_ROWS = [observation('RIGHT', 'COMMON', 'trunk_base', 3, 40)]
TRUNK = 'manual.COMMON.trunk_side_bent@photo:101'


def front_row(field='trunk_side_bent', scope='COMMON', value='YES', degrees=12.3, **changes):
    return dict(dict(view='FRONT', scope=scope, field=field, value=value, low_confidence=False, boundary_review=False,
                     angles=[dict(side=scope, angle_code='FRONT_TRUNK_TURN', value_deg=degrees)],
                     measurement_reason='사진에서 읽은 옆 기울임을 확인해 주세요.'), **changes)


def build(front_rows, views=None, answers=CONFIRM):
    """A side photo (101, the reference) and a front photo (103) whose readings are saved at their own photo."""
    views = views or dict(RIGHT=101, FRONT=103)
    data = preview([row for row in SIDE_ROWS if row['view'] in views], {view: owner for view, owner in views.items() if view != 'FRONT'})
    if 'FRONT' in views:
        data['views']['FRONT'] = dict(photo_id=views['FRONT'], engine=dict(provider='mediapipe'), guess=dict(orientation='FRONT', camera_side='FRONT'),
                                      measured=[], front_measurements=front_rows, signals={})
    saved = facts.add_photo_facts(facts.apply_answers({}, answers), data, views)
    return facts.project(task_input({}), saved, views, data), saved, views


def candidate(task, saved, views, identity=TRUNK):
    return next((row for row in planner.assess(task, saved, views)['candidates'] if row['identity'] == identity), None)


FLAGS = {'COMMON': ('trunk_twisted', 'trunk_side_bent', 'neck_twisted', 'neck_side_bent', 'legs_support', 'seated', *MOTION),
         'ARM': ('shoulder_raised', 'arm_abducted_or_rotated', 'arm_supported_or_gravity_assisted', 'wrist_deviated_or_twisted')}


class PostureChecklist(unittest.TestCase):
    def test_exactly_the_yes_no_posture_items_belong_to_the_checklist(self):
        listed = {field['target']: field['checklist'] for field in contract.fields() if field.get('checklist')}
        expected = {f'manual.COMMON.{name}' for name in FLAGS['COMMON']} | {f'manual.{side}.{name}' for side in ('LEFT', 'RIGHT') for name in FLAGS['ARM']}
        self.assertEqual(set(listed), expected)
        self.assertEqual(len(listed), 18)
        for field in contract.fields():
            if field['destination']['type'] != 'manual':
                continue
            flag = [(choice['value'], choice['label']) for choice in field['choices']]
            looks_like_a_flag = [label for _, label in flag] == ['예', '아니오']
            self.assertEqual(bool(field.get('checklist')), looks_like_a_flag, f"{field['target']}: a posture box with levels is not a checklist item")
            if field.get('checklist'):
                self.assertEqual((field['checklist']['yes'], field['checklist']['no']), (flag[0][0], flag[1][0]))

    def test_the_boxes_come_in_four_groups_in_a_fixed_order(self):
        rows = sorted((field['checklist']['order'], field['checklist']['group'], field['destination']['scope'], field['checklist']['label'])
                      for field in contract.fields() if field.get('checklist'))
        groups = []
        for _, group, _, _ in rows:
            if group not in groups:
                groups.append(group)
        self.assertEqual(groups, ['몸통·목', '어깨·팔·손목', '다리', '작업 중 움직임과 힘'])
        self.assertEqual(len({order for order, *_ in rows}), 14, 'an arm item is one line with a left and a right box')
        for order in {order for order, *_ in rows}:
            same = [row for row in rows if row[0] == order]
            self.assertEqual(len({label for *_, label in same}), 1)
            self.assertIn(len(same), (1, 2))

    def test_the_four_twist_and_bend_boxes_no_longer_share_one_label(self):
        labels = {field['target']: field['checklist']['label'] for field in contract.fields() if field.get('checklist') and field['destination']['scope'] == 'COMMON'}
        twins = [labels[f'manual.COMMON.{name}'] for name in ('trunk_twisted', 'trunk_side_bent', 'neck_twisted', 'neck_side_bent')]
        self.assertEqual(len(set(twins)), 4)
        self.assertEqual(twins[1], '몸통을 옆으로 기울여 작업함')
        by_target = {field['target']: field for field in contract.fields()}
        self.assertEqual(by_target['manual.COMMON.trunk_side_bent']['label'], twins[1], 'the plain box reads the same way')

    def test_the_leg_box_keeps_its_own_values(self):
        legs = next(field for field in contract.fields() if field['target'] == 'manual.COMMON.legs_support')
        self.assertEqual((legs['checklist']['yes'], legs['checklist']['no']), ('UNILATERAL_OR_UNSTABLE', 'BILATERAL_STABLE'))

    def test_the_popup_group_and_the_motion_flags_name_the_same_boxes(self):
        views = dict(RIGHT=101)
        task, saved, _ = build([], views)
        candidates = planner.assess(task, saved, views)['candidates']
        question = next(row for row in candidates if row['destination'].get('field') == 'shock_force')
        group = planner.with_answer_questions(question, candidates, saved)
        self.assertEqual({row['destination']['field'] for row in group['answer_questions']}, set(MOTION))


class FrontSuggestion(unittest.TestCase):
    def test_a_front_reading_is_offered_on_the_reference_photo_question(self):
        task, saved, views = build([front_row()])
        row = candidate(task, saved, views)
        self.assertEqual(row['suggestion'], dict(value='YES', estimated=False, quote='12.3°', photo_label='정면·후면 사진', reading='몸통이 옆으로 기울어 보여요'))

    def test_offering_is_not_answering(self):
        task, saved, views = build([front_row()])
        self.assertNotIn(TRUNK, saved, 'the reference photo has no fact of its own yet')
        self.assertEqual(saved['manual.COMMON.trunk_side_bent@photo:103']['source'], 'POSE', 'the reading stays owned by the front photo')
        self.assertFalse([row for row in task['manual'] if row['photo_id'] == 101 and row['field'] == 'trunk_side_bent'])
        self.assertIsNotNone(candidate(task, saved, views), 'the question is still open')

    def test_an_estimated_reading_says_it_is_an_estimate(self):
        task, saved, views = build([front_row(low_confidence=True)])
        self.assertTrue(candidate(task, saved, views)['suggestion']['estimated'])

    def test_each_arm_is_suggested_on_its_own_side_only(self):
        task, saved, views = build([front_row('arm_abducted_or_rotated', 'LEFT', degrees=35)])
        left = candidate(task, saved, views, 'manual.LEFT.arm_abducted_or_rotated@photo:101')['suggestion']
        self.assertEqual((left['quote'], left['reading']), ('35°', '팔이 옆으로 벌어져 보여요'))
        self.assertNotIn('suggestion', candidate(task, saved, views, 'manual.RIGHT.arm_abducted_or_rotated@photo:101'))

    def test_nothing_is_offered_without_a_usable_positive_reading(self):
        offered = lambda *args, **kwargs: (candidate(*build(*args, **kwargs)) or {}).get('suggestion')
        self.assertIsNone(offered([front_row(value=None)]), 'a small angle cannot establish anything')
        self.assertIsNone(offered([], dict(RIGHT=101)), 'no front photo')
        self.assertIsNone(offered([front_row()], answers=[dict(target='context', value='NO'), dict(target='load', value='UNLOADED')]), 'a refused photo set is not used for suggestions either')
        self.assertIsNone(offered([front_row()], dict(FRONT=101)), 'a photo never suggests to itself')
        self.assertIsNone(offered([front_row(low_confidence=True)], dict(FRONT=101)), 'not even while its own estimate is still unconfirmed')
        self.assertIsNone(offered([front_row(value=None, boundary_review=True)]), 'a near-threshold miss is an estimate of nothing, not a suggestion')
        self.assertIsNotNone(offered([front_row()]), 'the same reading is offered once all of that is fine')

    def test_only_a_photo_reading_is_offered_never_a_typed_answer_about_the_other_photo(self):
        task, saved, views = build([front_row()])
        saved = facts.apply_answers(saved, [dict(target='manual.COMMON.trunk_side_bent', condition='photo:103', value='NO')], photo_views=views)
        self.assertEqual(saved['manual.COMMON.trunk_side_bent@photo:103']['source'], 'USER')
        self.assertNotIn('suggestion', candidate(facts.project(task_input({}), saved, views, dict(views={})), saved, views))

    def test_the_form_gets_the_suggestion_with_the_question(self):
        task, saved, views = build([front_row()])
        assessment = planner.assess(task, saved, views)
        row = next(item for item in planner.form_fields(task, saved, views, assessment['candidates']) if item['identity'] == TRUNK)
        self.assertEqual(row['suggestion']['photo_label'], '정면·후면 사진')
        self.assertEqual(row['suggestion']['reading'], '몸통이 옆으로 기울어 보여요')

    def test_an_answered_question_is_not_asked_or_suggested(self):
        task, saved, views = build([front_row()], answers=CONFIRM + [dict(target='manual.COMMON.trunk_side_bent', condition='photo:101', value='NO')])
        self.assertIsNone(candidate(task, saved, views))

    def test_confirming_saves_a_user_answer_that_says_how_it_was_chosen(self):
        task, saved, views = build([front_row()])
        quote = '정면·후면 사진에서 읽은 값(12.3°)을 확인해 직접 선택'
        saved = facts.apply_answers(saved, [dict(target='manual.COMMON.trunk_side_bent', condition='photo:101', value='YES', quote=quote)], photo_views=views)
        item = saved[TRUNK]
        self.assertEqual((item['source'], item['state'], item['value'], item['quote']), ('USER', 'KNOWN', 'YES', quote))
        self.assertEqual(saved['manual.COMMON.trunk_side_bent@photo:103']['source'], 'POSE', 'the front reading is left as it was')
        projected = facts.project(task_input({}), saved, views, dict(views={}))
        row = next(row for row in projected['manual'] if row['photo_id'] == 101 and row['field'] == 'trunk_side_bent')
        self.assertEqual((row['value'], row['source']), ('YES', 'INTERVIEW'))
        self.assertEqual(row['evidence']['text'], 'USER: ' + quote, 'the trace shows the choice, not a measurement')


class QuotedAnswers(unittest.TestCase):
    def test_the_exported_posture_rows_show_how_each_value_was_chosen(self):
        task, saved, views = build([front_row()])
        confirm, mirror, suggest = ('자세 체크리스트에서 체크하지 않은 항목을 해당 없음으로 직접 확인', '왼쪽은 오른쪽과 같다고 직접 선택 (선택한 때의 값)', '정면·후면 사진에서 읽은 값(12.3°)을 확인해 직접 선택')
        answers = [dict(target=f'manual.COMMON.{name}', condition='photo:101', value='NO', quote=confirm) for name in MOTION]
        answers += [dict(target='manual.COMMON.trunk_side_bent', condition='photo:101', value='YES', quote=suggest),
                    dict(target='manual.LEFT.shoulder_raised', condition='photo:101', value='NO', quote=mirror)]
        saved = facts.apply_answers(saved, answers, photo_views=views)
        rows = _manual_rows('작업', facts.project(task_input({}), saved, views, dict(views={})))
        memo = {row[5]: row for row in rows}
        self.assertEqual(memo['USER: ' + suggest][3], '예')
        self.assertIn('갑작스러운 큰 힘·충격', memo['USER: ' + confirm][3])
        self.assertIn('왼쪽 어깨를 으쓱 듦', memo['USER: ' + mirror][3])
        self.assertEqual(memo['사진에서 잰 각도 12.3°'][2], '정면·후면 사진 · 몸통 옆으로 기울임', 'the front photo keeps its own measured row')

    def test_a_checklist_answer_keeps_its_quote_and_a_plain_answer_keeps_the_default(self):
        views = dict(RIGHT=101)
        task, saved, _ = build([], views)
        quote = '자세 체크리스트에서 체크하지 않은 항목을 해당 없음으로 직접 확인'
        saved = facts.apply_answers(saved, [dict(target='manual.COMMON.shock_force', condition='photo:101', value='NO', quote=quote),
                                            dict(target='manual.COMMON.static_over_1min', condition='photo:101', value='NO')], photo_views=views)
        self.assertEqual(saved['manual.COMMON.shock_force@photo:101']['quote'], quote)
        self.assertEqual(saved['manual.COMMON.static_over_1min@photo:101']['quote'], '직접 입력')
        self.assertEqual({saved[f'manual.COMMON.{name}@photo:101']['source'] for name in ('shock_force', 'static_over_1min')}, {'USER'})


class ThroughTheService(unittest.TestCase):
    setUp = fixtures.AdaptiveIntake.setUp
    turn = fixtures.AdaptiveIntake.turn
    get = fixtures.AdaptiveIntake.get
    candidates = fixtures.AdaptiveIntake.candidates

    def open_photos(self):
        ids = {}
        for view in ('RIGHT', 'FRONT'):
            photo = Path(self.temp.name) / (view + '.fixture')
            photo.write_bytes(view.encode())
            ids[view] = self.ctx.store('create_photo', self.identity, dict(file_path=str(photo), file_name=photo.name, width_px=1, height_px=1, consent='UNKNOWN', notes=[]))
        data = preview(SIDE_ROWS, dict(RIGHT=ids['RIGHT']))
        data['views']['FRONT'] = dict(photo_id=ids['FRONT'], engine=dict(provider='mediapipe'), guess=dict(orientation='FRONT', camera_side='FRONT'),
                                      measured=[], front_measurements=[front_row()], signals={})
        inference = patch('ergo.service.intake.handle_quick_preview', return_value=data)
        inference.start()
        self.addCleanup(inference.stop)
        self.ctx.dispatch('intake_session', dict(task_id=self.identity, views=ids))
        return ids

    def test_the_model_never_sees_the_front_reading_or_the_form_only_hints(self):
        ids = self.open_photos()
        self.turn(CONFIRM, plan=False)
        setting = self.ctx.dispatch('get_settings', {})
        setting.pop('gpt_key_present', None)
        setting.update(gpt_enabled=True, gpt_model='fixture')
        self.ctx.dispatch('update_settings', dict(settings=setting))
        asked = [dict(target='manual.COMMON.shock_force', condition=f"photo:{ids['RIGHT']}")]
        with patch('ergo.gpt.client.adaptive_intake', return_value=(dict(answers=[], questions=[]), None)) as call:
            self.ctx.dispatch('intake_turn', dict(task_id=self.identity, text='하루 4시간 일해요.', answers=[], focus=asked))
        sent = [item.args[0] for item in call.call_args_list]
        self.assertGreaterEqual(len(sent), 1, 'the text turn reached the (patched) model')
        self.assertEqual([item['target'] for item in sent[0]['asked']], ['manual.COMMON.shock_force'], 'the question being asked is still sent')
        for payload in sent:
            self.assertTrue(payload['missing'], 'the questions themselves are still sent')
            self.assertTrue(payload['targets'])
            text = json.dumps(payload, ensure_ascii=False)
            self.assertNotIn('"suggestion"', text)
            self.assertNotIn('"checklist"', text)

    def test_the_form_gets_the_suggestion_and_the_checklist_and_a_confirmed_answer_keeps_its_quote(self):
        ids = self.open_photos()
        state = self.turn(CONFIRM, plan=False)
        identity = f"manual.COMMON.trunk_side_bent@photo:{ids['RIGHT']}"
        row = next(item for item in state['form_fields'] if item['identity'] == identity)
        self.assertEqual((row['suggestion']['photo_label'], row['suggestion']['quote'], row['suggestion']['reading']), ('정면·후면 사진', '12.3°', '몸통이 옆으로 기울어 보여요'))
        listed = {item['target'] for item in state['form_fields'] if item.get('checklist')}
        self.assertEqual(listed, {f'manual.COMMON.{name}' for name in FLAGS['COMMON']} | {f'manual.{side}.{name}' for side in ('LEFT', 'RIGHT') for name in FLAGS['ARM']})
        quote = '정면·후면 사진에서 읽은 값(12.3°)을 확인해 직접 선택'
        saved = self.turn([dict(target='manual.COMMON.trunk_side_bent', condition=f"photo:{ids['RIGHT']}", value='YES', quote=quote)], plan=False)
        fact = next(item for item in saved['facts'] if item['identity'] == identity)
        self.assertEqual((fact['source'], fact['state'], fact['quote']), ('USER', 'KNOWN', quote))
        front = next(item for item in saved['facts'] if item['identity'] == f"manual.COMMON.trunk_side_bent@photo:{ids['FRONT']}")
        self.assertEqual((front['source'], front['value']), ('POSE', 'YES'), 'the front photo keeps its own reading')
        self.assertNotIn(identity, {item['identity'] for item in self.candidates(saved)})
        self.assertEqual(self.get()['task']['input_revision'], saved['task']['input_revision'], 'reading the session again saves nothing')

    def test_ticking_what_applies_and_confirming_the_rest_finishes_the_score_and_shows_in_the_export(self):
        ids = self.open_photos()
        rid = ids['RIGHT']
        state = self.turn(CONFIRM, plan=False)
        flags = [item for item in state['form_fields'] if item.get('checklist') and item['condition'] == f'photo:{rid}']
        self.assertEqual(len(flags), 18)
        ticked_quote, confirm_quote = '자세 체크리스트에서 해당한다고 직접 체크', '자세 체크리스트에서 체크하지 않은 항목을 해당 없음으로 직접 확인'
        answers = []
        for item in flags:
            ticked = item['target'] == 'manual.COMMON.trunk_side_bent'
            answers.append(dict(target=item['target'], condition=item['condition'], value=item['checklist']['yes' if ticked else 'no'], quote=ticked_quote if ticked else confirm_quote))
        angles = [item for item in state['form_fields'] if item['destination']['type'] == 'manual' and not item.get('checklist') and item['identity'] not in {a['target'] + '@' + a['condition'] for a in answers}]
        self.assertTrue(angles, 'the angles the photo could not read are still asked')
        self.assertTrue(all(item['destination']['field'].endswith('_base') or item['destination']['field'] in ('knee_band',) for item in angles))
        answers += [dict(target=item['target'], condition=item['condition'], value=item['choices'][0]['value']) for item in angles]
        before = self.get()['reba']['status']
        self.assertEqual(before, 'INCOMPLETE')
        done = self.turn(answers, plan=False)
        self.assertEqual(done['reba']['status'], 'COMPLETE', 'one tick, the confirmation and the unread angles are enough for a full score')
        by_identity = {item['identity']: item for item in done['facts']}
        self.assertEqual(by_identity[f'manual.COMMON.trunk_side_bent@photo:{rid}']['quote'], ticked_quote)
        self.assertEqual(by_identity[f'manual.COMMON.static_over_1min@photo:{rid}']['value'], 'NO')
        self.assertEqual(by_identity[f'manual.COMMON.legs_support@photo:{rid}']['value'], 'BILATERAL_STABLE')
        rows = _manual_rows('작업', done['task'])
        memos = {row[5] for row in rows}
        self.assertIn('직접 입력: ' + confirm_quote, memos, 'the export says the user confirmed the unticked boxes')
        self.assertIn('직접 입력: ' + ticked_quote, memos)
        self.assertEqual(self.get()['task']['input_revision'], done['task']['input_revision'])


if __name__ == '__main__':
    unittest.main()
