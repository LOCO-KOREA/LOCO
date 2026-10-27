"""Replacing the photo re-asks only what belongs to the photo, and says why."""
import unittest
from pathlib import Path
from unittest.mock import patch
from ergo.engine.task_defaults import task_input
from ergo.intake import facts, planner
import test_adaptive_intake as fixtures
import test_context_refusal_path as refusal
from test_photo_fact_ownership import observation, preview

ROWS = [observation('RIGHT', 'COMMON', 'trunk_base', 3, 40), observation('RIGHT', 'RIGHT', 'upper_arm_base', 3, 60)]
CONFIRM = [dict(target='context', value='YES', condition='default'), dict(target='load', value='UNLOADED', condition='default')]


class PhotoReplacement(unittest.TestCase):
    setUp = fixtures.AdaptiveIntake.setUp
    turn = fixtures.AdaptiveIntake.turn

    def open_photo(self, name):
        photo = Path(self.temp.name) / name
        photo.write_bytes(name.encode())
        identity = self.ctx.store('create_photo', self.identity, dict(file_path=str(photo), file_name=name, width_px=1, height_px=1, consent='UNKNOWN', notes=[]))
        inference = patch('ergo.service.intake.handle_quick_preview', return_value=preview(ROWS, dict(RIGHT=identity)))
        inference.start(); self.addCleanup(inference.stop)
        return self.ctx.dispatch('intake_session', dict(task_id=self.identity, views=dict(RIGHT=identity)))

    def finish_interview(self):
        state = self.turn(CONFIRM[:1])
        for _ in range(80):
            if not state['questions']:
                return state
            state = self.turn(refusal.ServiceAfterRefusal.least_burden(state['questions'][0]))
        self.fail('the interview did not end')

    def pending(self, state):
        session = state['task']['conditions']['intake_session']
        return planner.assess(state['task'], session['facts'], session['views'])['candidates']

    def test_a_first_ask_is_not_presented_as_a_repeat(self):
        state = self.open_photo('first.fixture')
        question = state['questions'][0]
        self.assertEqual(question['target'], 'context')
        self.assertFalse(question.get('reask'))
        self.assertEqual(question['reason'], '결과 계산에 필요한 정보가 아직 없어요.')
        self.assertFalse(any(row.get('reask') for row in state['form_fields']))

    def test_only_photo_bound_answers_come_back_after_a_replacement(self):
        self.open_photo('first.fixture')
        self.finish_interview()
        reopened = self.open_photo('second.fixture')
        answered = self.turn(CONFIRM)
        targets = {row['target'] for state in (reopened, answered) for row in self.pending(state)}
        self.assertIn('context', targets)
        self.assertTrue(any(target.startswith('manual.') for target in targets))
        photo_bound = {target for target in targets if target in ('context', 'load') or target.startswith('manual.')}
        self.assertEqual(targets - photo_bound, set(), 'work types, times and counts the user gave must stay answered')

    def test_each_returning_question_says_it_is_a_repeat_and_why(self):
        self.open_photo('first.fixture')
        self.finish_interview()
        reopened = self.open_photo('second.fixture')
        first = {row['target']: row for row in reopened['form_fields']}
        self.assertTrue(first['context']['reask'])
        self.assertEqual(first['context']['reason'], '사진 또는 측정 설정이 바뀌어 이전 확인을 쓸 수 없어요. 다시 확인해 주세요.')
        self.assertTrue(first['load']['reask'])
        rows = {row['target']: row for row in self.turn(CONFIRM)['form_fields']}
        flag = rows['manual.COMMON.static_over_1min']
        self.assertTrue(flag['reask'])
        self.assertEqual(flag['reason'], '이전 사진에서 답한 항목이에요. 새 사진 기준으로 다시 확인해 주세요.')
        activity = ('static_over_1min', 'shock_force', 'small_repeat_over_4min', 'rapid_change_or_unstable', 'legs_support', 'neck_base')
        self.assertTrue(all(row.get('reask') for target, row in rows.items() if target.startswith('manual.') and target.split('.')[-1] in activity))


class EstimatedReading(unittest.TestCase):
    def test_an_estimated_photo_reading_is_asked_but_not_as_a_repeat(self):
        views = dict(RIGHT=101)
        shaky = dict(observation('RIGHT', 'COMMON', 'trunk_base', 3, 40), low_confidence=True)
        data = preview([shaky], views)
        saved = facts.add_photo_facts(facts.apply_answers({}, [dict(target='context', value='YES'), dict(target='load', value='UNLOADED')]), data, views)
        task = facts.project(task_input({}), saved, views, data)
        row = next(row for row in planner.assess(task, saved, views)['candidates'] if row['identity'] == 'manual.COMMON.trunk_base@photo:101')
        self.assertFalse(row.get('reask'))
        self.assertEqual(row['reason'], '결과 계산에 필요한 정보가 아직 없어요.')


if __name__ == '__main__':
    unittest.main()
