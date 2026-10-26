"""What the checklist's save order and the one-dialog flow rely on, through the real service and planner.
The frontend sends "확인 끝" after the typed sentence and shows the checklist in the dialog that asked the photo question (tests/frontend-checklist-flow.cjs)."""
import unittest
from pathlib import Path
from unittest.mock import patch
import test_adaptive_intake as fixtures
from test_photo_fact_ownership import observation, preview

CONFIRM_QUOTE = '자세 체크리스트에서 체크하지 않은 항목을 해당 없음으로 직접 확인'
SENTENCE = '허리를 계속 비틀어서 작업해요.'


class ChecklistFlow(unittest.TestCase):
    setUp = fixtures.AdaptiveIntake.setUp
    turn = fixtures.AdaptiveIntake.turn

    def open_photo(self):
        photo = Path(self.temp.name) / 'RIGHT.fixture'
        photo.write_bytes(b'R')
        pid = self.ctx.store('create_photo', self.identity, dict(file_path=str(photo), file_name=photo.name, width_px=1, height_px=1, consent='UNKNOWN', notes=[]))
        data = preview([observation('RIGHT', 'COMMON', 'trunk_base', 3, 40)], dict(RIGHT=pid))
        inference = patch('ergo.service.intake.handle_quick_preview', return_value=data)
        inference.start()
        self.addCleanup(inference.stop)
        self.session = self.ctx.dispatch('intake_session', dict(task_id=self.identity, views=dict(RIGHT=pid)))
        return pid

    def checklist(self, state):
        return [row for row in state['form_fields'] if row.get('checklist')]

    def save(self, together):
        """The sentence says the trunk is twisted; "확인 끝" fills every box that is still blank with "does not apply"."""
        pid = self.open_photo()
        condition = f'photo:{pid}'
        state = self.turn([dict(target='context', value='YES'), dict(target='load', value='UNLOADED')], plan=False)
        confirm = [dict(target=row['target'], condition=row['condition'], value=row['checklist']['no'], quote=CONFIRM_QUOTE) for row in self.checklist(state)]
        model = dict(answers=[dict(target='manual.COMMON.trunk_twisted', condition=condition, number=None, text='YES', quote='허리를 계속 비틀어서')], questions=[])
        if together:
            out = self.turn(confirm, text=SENTENCE, raw=model, plan=True)
        else:
            out = self.turn([], text=SENTENCE, raw=model, plan=True)
            blank = [a for a in confirm if not any(f['identity'] == a['target'] + '@' + a['condition'] and f['state'] == 'KNOWN' for f in out['facts'])]
            self.assertEqual(len(blank), len(confirm) - 1, 'only the box the sentence answered is left out')
            out = self.turn(blank, plan=False)
        return next(f for f in out['facts'] if f['identity'] == f'manual.COMMON.trunk_twisted@{condition}'), out

    def test_a_sentence_saved_before_the_confirmation_keeps_what_it_says(self):
        trunk, out = self.save(together=False)
        self.assertEqual((trunk['value'], trunk['source']), ('YES', 'AI'))
        seated = next(f for f in out['facts'] if f['identity'].startswith('manual.COMMON.seated@'))
        self.assertEqual((seated['value'], seated['source'], seated['quote']), ('NO', 'USER', CONFIRM_QUOTE), 'every other blank box is confirmed')

    def test_the_same_confirmation_sent_with_the_sentence_would_beat_it(self):
        """The reason the frontend sends the sentence first: a user answer in the same request wins over the model."""
        trunk, _ = self.save(together=True)
        self.assertEqual((trunk['value'], trunk['source']), ('NO', 'USER'))

    def test_answering_the_photo_situation_returns_the_checklist_in_the_same_response(self):
        self.open_photo()
        self.assertFalse([row for row in self.session['form_fields'] if row['destination']['type'] == 'manual'], 'before the answer the form has no photo rows')
        state = self.turn([dict(target='context', value='YES')], plan=False)
        self.assertEqual(len(self.checklist(state)), 18)
        angles = [row for row in state['form_fields'] if row['destination']['type'] == 'manual' and not row.get('checklist')]
        self.assertTrue(angles, 'the angles the photo could not read come with it')

    def test_a_refused_photo_still_returns_the_boxes_to_answer_by_hand(self):
        self.open_photo()
        state = self.turn([dict(target='context', value='NO')], plan=False)
        self.assertEqual(len(self.checklist(state)), 18, 'the posture is then described by hand, so the checklist comes back too')
        self.assertTrue(any(row['destination']['type'] == 'manual' and not row.get('checklist') for row in state['form_fields']))


if __name__ == '__main__':
    unittest.main()
