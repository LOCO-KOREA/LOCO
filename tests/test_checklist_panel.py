"""What the form receives for the posture checklist: the flags the panel relies on to say why a row is asked, and to say nothing when there is nothing special."""
import unittest
from pathlib import Path
from unittest.mock import patch
from ergo.intake import planner
import test_adaptive_intake as fixtures
from test_form_shortcuts import build, FLAGS
from test_photo_fact_ownership import observation, preview

GENERIC = '결과 계산에 필요한 정보가 아직 없어요.'
REFUSED = [dict(target='context', value='NO'), dict(target='load', value='UNLOADED')]
CONFIRMED = [dict(target='context', value='YES'), dict(target='load', value='UNLOADED')]
SPECIAL = ('reask', 'photo_unused', 'photo_measurement_reason')


def form_rows(task, saved, views):
    return {row['identity']: row for row in planner.form_fields(task, saved, views, planner.assess(task, saved, views)['candidates'])}


class RowReasons(unittest.TestCase):
    def test_an_ordinary_checklist_row_carries_only_the_generic_reason(self):
        task, saved, views = build([], dict(RIGHT=101), CONFIRMED)
        rows = form_rows(task, saved, views)
        flag = rows['manual.COMMON.seated@photo:101']
        self.assertEqual(flag['reason'], GENERIC)
        self.assertFalse([name for name in SPECIAL if flag.get(name)], 'nothing special: the panel does not repeat the generic sentence on 18 boxes')

    def test_a_refused_photo_marks_the_rows_it_would_have_measured_with_their_own_reason(self):
        task, saved, views = build([], dict(RIGHT=101), REFUSED)
        rows = form_rows(task, saved, views)
        measured = rows['manual.COMMON.trunk_base@photo:101']
        self.assertTrue(measured['photo_unused'])
        self.assertTrue(measured['photo_measurement_reason'])
        self.assertEqual(measured['reason'], '사진 측정값은 쓰지 않기로 해서 직접 확인해 주세요.')
        listed = {name for name, row in rows.items() if row.get('checklist')}
        self.assertEqual(len(listed), 18, 'the checklist is still asked by hand')
        self.assertTrue(all(rows[name]['reason'] for name in listed), 'every row has a reason to show or to hide')

    def test_the_context_answer_is_the_fact_the_panel_reads_to_stop_claiming_what_the_photo_measured(self):
        for answers, used in ((CONFIRMED, 'YES'), (REFUSED, 'NO')):
            task, saved, views = build([], dict(RIGHT=101), answers)
            self.assertEqual(saved['context@default']['value'], used)
            self.assertEqual(saved['context@default']['state'], 'KNOWN')


class ThroughTheService(unittest.TestCase):
    setUp = fixtures.AdaptiveIntake.setUp
    turn = fixtures.AdaptiveIntake.turn

    def test_a_replaced_photo_asks_every_old_checklist_answer_again_and_says_why(self):
        photo = Path(self.temp.name) / 'RIGHT.fixture'
        photo.write_bytes(b'RIGHT-v1')
        pid = self.ctx.store('create_photo', self.identity, dict(file_path=str(photo), file_name=photo.name, width_px=1, height_px=1, consent='UNKNOWN', notes=[]))
        data = preview([observation('RIGHT', 'COMMON', 'trunk_base', 3, 40)], dict(RIGHT=pid))
        with patch('ergo.service.intake.handle_quick_preview', return_value=data):
            self.ctx.dispatch('intake_session', dict(task_id=self.identity, views=dict(RIGHT=pid)))
            state = self.turn(CONFIRMED, plan=False)
            quote = '자세 체크리스트에서 체크하지 않은 항목을 해당 없음으로 직접 확인'
            state = self.turn([dict(target=f['target'], condition=f['condition'], value=f['checklist']['no'], quote=quote) for f in state['form_fields'] if f.get('checklist')], plan=False)
            self.assertTrue(all(f['condition'] == f'photo:{pid}' for f in state['form_fields'] if f.get('checklist')))
            photo.write_bytes(b'RIGHT-v2-a-different-picture')
            again = self.ctx.dispatch('intake_session', dict(task_id=self.identity, views=dict(RIGHT=pid)))
            again = self.turn(CONFIRMED, plan=False)
        rows = [f for f in again['form_fields'] if f.get('checklist')]
        self.assertEqual(len(rows), len({t for t in (f['target'] for f in rows)}), 'one row per box')
        self.assertEqual(len(rows), len({f'manual.COMMON.{n}' for n in FLAGS['COMMON']} | {f'manual.{s}.{n}' for s in ('LEFT', 'RIGHT') for n in FLAGS['ARM']}))
        for row in rows:
            self.assertTrue(row['reask'], row['identity'])
            self.assertTrue(row['photo_measurement_reason'], row['identity'])
            self.assertEqual(row['reason'], '사진 또는 측정 설정이 바뀌어 이전 확인을 쓸 수 없어요. 다시 확인해 주세요.')


if __name__ == '__main__':
    unittest.main()
