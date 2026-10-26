"""A refused or unknown photo confirmation must not leave the final REBA unreachable."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from ergo.engine.task_defaults import task_input
from ergo.intake import contract, facts, planner
import test_adaptive_intake as fixtures
from test_photo_fact_ownership import observation, preview

VIEWS = dict(RIGHT=101)
ROWS = [observation('RIGHT', 'COMMON', 'trunk_base', 3, 40), observation('RIGHT', 'RIGHT', 'upper_arm_base', 3, 60)]


def seeded(context):
    saved = facts.apply_answers({}, [dict(target='context', value=context), dict(target='load', value='UNLOADED')])
    data = preview(ROWS, VIEWS)
    saved = facts.add_photo_facts(saved, data, VIEWS)
    return saved, facts.project(task_input({}), saved, VIEWS, data)


def reba_gaps(assessment):
    """REBA inputs the final calculation still lacks, spelled as catalogue targets."""
    slot = assessment['reba']['slots'][0]
    return {'manual.' + path.split('.')[0].upper() + '.' + path.split('.')[1] for path in slot['missing_fields'] if not path.endswith('effective_load_kg')}


class PlannerAfterRefusal(unittest.TestCase):
    def test_photo_values_the_user_refused_are_asked_by_hand(self):
        for context in ('NO', None):
            with self.subTest(context=context):
                saved, task = seeded(context)
                pending = {row['identity'] for row in planner.assess(task, saved, VIEWS)['candidates']}
                self.assertIn('manual.COMMON.trunk_base@photo:101', pending)
                self.assertIn('manual.RIGHT.upper_arm_base@photo:101', pending)

    def test_a_refusal_wins_over_a_photo_change_in_the_reason_shown(self):
        saved, task = seeded('NO')
        identity = 'manual.COMMON.trunk_base@photo:101'
        saved[identity] = dict(saved[identity], value=None, state='UNKNOWN', source='POSE', reask=True)
        row = next(row for row in planner.assess(task, saved, VIEWS)['candidates'] if row['identity'] == identity)
        self.assertEqual(row['reason'], '사진 측정값은 쓰지 않기로 해서 직접 확인해 주세요.')
        self.assertTrue(row['reask'] and row['photo_unused'])

    def test_every_reba_gap_has_a_question_after_a_refusal(self):
        for context in ('NO', None):
            with self.subTest(context=context):
                saved, task = seeded(context)
                assessment = planner.assess(task, saved, VIEWS)
                asked = {row['target'] for row in assessment['candidates'] if row['destination']['type'] == 'manual'}
                self.assertTrue(reba_gaps(assessment))
                self.assertEqual(reba_gaps(assessment) - asked, set())

    def test_unanswered_context_still_waits_and_confirmed_context_keeps_photo_values(self):
        data = preview(ROWS, VIEWS)
        waiting = facts.add_photo_facts(facts.apply_answers({}, [dict(target='load', value='UNLOADED')]), data, VIEWS)
        task = facts.project(task_input({}), waiting, VIEWS, data)
        self.assertFalse([row for row in planner.assess(task, waiting, VIEWS)['candidates'] if row['destination']['type'] == 'manual'])
        saved, task = seeded('YES')
        pending = {row['identity'] for row in planner.assess(task, saved, VIEWS)['candidates']}
        self.assertNotIn('manual.COMMON.trunk_base@photo:101', pending)
        self.assertNotIn('manual.RIGHT.upper_arm_base@photo:101', pending)

    def test_unusable_photo_values_are_not_counted_as_handled_in_progress(self):
        saved, task = seeded('NO')
        candidates = planner.assess(task, saved, VIEWS)['candidates']
        progress = planner.progress(task, saved, VIEWS, candidates)
        self.assertEqual(progress['total_count'], progress['completed_count'] + progress['remaining_count'])
        bare = facts.apply_answers({}, [dict(target='context', value='NO'), dict(target='load', value='UNLOADED')])
        bare = facts.add_photo_facts(bare, preview([], VIEWS), VIEWS)
        bare_task = facts.project(task_input({}), bare, VIEWS, preview([], VIEWS))
        baseline = planner.progress(bare_task, bare, VIEWS, planner.assess(bare_task, bare, VIEWS)['candidates'])
        self.assertEqual(progress['completed_count'], baseline['completed_count'])


class ServiceAfterRefusal(unittest.TestCase):
    setUp = fixtures.AdaptiveIntake.setUp
    turn = fixtures.AdaptiveIntake.turn

    def start(self):
        photo = Path(self.temp.name) / 'RIGHT.fixture'
        photo.write_bytes(b'synthetic photo RIGHT')
        identity = self.ctx.store('create_photo', self.identity, dict(file_path=str(photo), file_name=photo.name,
            width_px=1, height_px=1, consent='UNKNOWN', notes=[]))
        inference = patch('ergo.service.intake.handle_quick_preview', return_value=preview(ROWS, dict(RIGHT=identity)))
        inference.start(); self.addCleanup(inference.stop)
        return self.ctx.dispatch('intake_session', dict(task_id=self.identity, views=dict(RIGHT=identity)))

    @staticmethod
    def least_burden(question):
        fields = [question, *(question.get('answer_questions') or [])]
        if question.get('paired_question'):
            fields.append(question['paired_question'])
        answers, seen = [], set()
        for field in fields:
            if field['identity'] in seen:
                continue
            seen.add(field['identity'])
            if field['kind'] == 'number':
                value = 10
            else:
                choices = [c['value'] for c in field['choices']]
                value = next((v for v in ('NO', 'UNLOADED', 'BILATERAL_STABLE') if v in choices), choices[0])
            answers.append(dict(target=field['target'], condition=field['condition'], value=value))
        return answers

    def finish_interview(self, context):
        self.start()
        state = self.turn([dict(target='context', value=context, condition='default')])
        for _ in range(80):
            if not state['questions']:
                break
            state = self.turn(self.least_burden(state['questions'][0]))
        return state

    def assert_reba_complete(self, state):
        self.assertFalse(state['questions'])
        self.assertEqual(state['reba']['status'], 'COMPLETE')
        self.assertTrue(state['complete'])

    def test_the_form_asks_the_refused_photo_values_instead_of_listing_them_as_confirmed(self):
        self.start()
        refused = {row['target']: row for row in self.turn([dict(target='context', value='NO', condition='default')])['form_fields']}
        for target in ('manual.COMMON.trunk_base', 'manual.RIGHT.upper_arm_base'):
            self.assertTrue(refused[target]['photo_unused'], target)
            self.assertEqual(refused[target]['reason'], '사진 측정값은 쓰지 않기로 해서 직접 확인해 주세요.')
        kept = {row['target']: row for row in self.turn([dict(target='context', value='YES', condition='default')])['form_fields']}
        self.assertFalse(any(row.get('photo_unused') for row in kept.values()))

    def test_refusing_the_photo_still_ends_with_a_complete_reba(self):
        self.assert_reba_complete(self.finish_interview('NO'))

    def test_answering_unknown_to_the_photo_still_ends_with_a_complete_reba(self):
        self.assert_reba_complete(self.finish_interview(None))


if __name__ == '__main__':
    unittest.main()
