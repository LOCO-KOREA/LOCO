"""An unfinished REBA still reports the score of the answers so far, never as a final score."""
import copy
import time
import unittest
from pathlib import Path
from unittest.mock import patch
from ergo.engine import quick_assess
from ergo.engine.reba_scoring import NO_BURDEN, calculate_reba
from ergo.engine.task_defaults import ARM, COMMON, task_input
from ergo.gpt import client, payload
from ergo.intake import contract, facts
import test_adaptive_intake as fixtures
from test_photo_fact_ownership import observation, preview

VIEWS = dict(RIGHT=101)
BASE = [observation('RIGHT', 'COMMON', 'trunk_base', 3, 40), observation('RIGHT', 'RIGHT', 'upper_arm_base', 3, 60)]
READ = [*BASE, observation('RIGHT', 'RIGHT', 'lower_arm_base', 1, 80)]


def task_with(rows, answers=(), context='YES'):
    data = preview(rows, VIEWS)
    saved = facts.apply_answers({}, [dict(target='context', value=context), dict(target='load', value='UNLOADED'), *answers])
    return facts.project(task_input({}), facts.add_photo_facts(saved, data, VIEWS), VIEWS, data)


def unconfirmed_task(rows=READ, *answers):
    """The photo was read but its confirmation is not answered: the task does not project the readings, the intake session still holds them."""
    data = preview(rows, VIEWS)
    saved = facts.add_photo_facts(facts.apply_answers({}, [dict(target='load', value='UNLOADED'), *answers]), data, VIEWS)
    task = facts.project(task_input({}), saved, VIEWS, data)
    task['conditions'][contract.SESSION_KEY] = dict(facts=saved, views=VIEWS)
    return task


def filled_rows(task, **overrides):
    """Every REBA input answered: what is known stays, the rest takes its no-burden option."""
    slot = task['capture']['slots'][0]
    known = {(m['scope'], m['field']): m['value'] for m in task['manual']}
    rows = []
    for scope, fields in (('COMMON', COMMON), ('LEFT', ARM), ('RIGHT', ARM)):
        for field in fields:
            value = known.get((scope, field))
            rows.append(dict(slot_no=slot['slot_no'], photo_id=slot['photo_id'], scope=scope, field=field, source='INTERVIEW',
                             value=overrides.get(field, value if value not in (None, 'UNKNOWN') else NO_BURDEN[field])))
    return rows


def so_far_of(task):
    return calculate_reba(task, None)['slots'][0].get('score_so_far')


class ScoreSoFar(unittest.TestCase):
    def test_answers_so_far_score_with_the_rest_at_no_burden(self):
        task = task_with(BASE)
        reba = calculate_reba(task, None)
        slot = reba['slots'][0]
        self.assertIsNone(slot['total'])
        so_far = slot['score_so_far']
        self.assertEqual((so_far['total'], so_far['risk'], so_far['left'], so_far['right'], so_far['selected_side']), (2, 'LOW', 1, 2, 'RIGHT'))
        self.assertEqual(so_far['assumed'], sorted(p for p in slot['missing_fields'] if p.split('.')[0] in ('common', 'left', 'right')))
        self.assertNotIn('common.trunk_base', so_far['assumed'])
        self.assertIn('left.upper_arm_base', so_far['assumed'])
        self.assertIn('확정 점수가 아닙니다', so_far['assumption'])
        self.assertIn('실제 점수는 더 높을 수 있고', so_far['assumption'])
        self.assertEqual(reba['summary']['score_so_far'], dict(so_far, slot_no=slot['slot_no']))
        self.assertIsNone(reba['summary']['full_max'])
        self.assertIsNone(reba['summary']['available_max'])

    def test_it_is_exactly_the_final_score_of_the_same_task_with_every_open_item_at_no_burden(self):
        task = task_with(BASE)
        expected = calculate_reba(dict(task, manual=filled_rows(task)), None)['slots'][0]
        self.assertEqual(so_far_of(task)['total'], expected['total'])

    def test_it_agrees_with_the_first_pass_score_when_nothing_else_was_answered(self):
        settings = dict(pose_model=dict(confidence_min=0.5))
        measured = [dict(scope='COMMON', field='trunk_base', value=3), dict(scope='RIGHT', field='upper_arm_base', value=3)]
        first_pass = quick_assess.provisional(measured, [], settings)
        so_far = so_far_of(task_with(BASE))
        self.assertEqual((so_far['total'], so_far['risk']), (first_pass['total'], first_pass['risk']))

    def test_answers_given_after_the_photo_change_the_score(self):
        task = task_with(BASE, [dict(target='manual.COMMON.static_over_1min', value='YES', condition='photo:101')])
        self.assertEqual(so_far_of(task)['total'], 3)

    def test_a_finished_reba_has_no_score_so_far(self):
        task = task_with(BASE)
        reba = calculate_reba(dict(task, manual=filled_rows(task)), None)
        self.assertEqual(reba['status'], 'COMPLETE')
        self.assertNotIn('score_so_far', reba['slots'][0])
        self.assertNotIn('score_so_far', reba['summary'])

    def test_nothing_read_or_answered_gives_no_score(self):
        data = preview([], VIEWS)
        saved = facts.add_photo_facts(facts.apply_answers({}, [dict(target='load', value='UNLOADED')]), data, VIEWS)
        reba = calculate_reba(facts.project(task_input({}), saved, VIEWS, data), None)
        self.assertNotIn('score_so_far', reba['slots'][0])
        self.assertNotIn('score_so_far', reba['summary'])

    def test_an_answered_flag_alone_never_makes_a_reassuring_score(self):
        task = task_with([], [dict(target='manual.COMMON.static_over_1min', value='NO', condition='photo:101')])
        self.assertIsNone(so_far_of(task))

    def test_one_answer_that_is_itself_the_lowest_option_never_makes_a_score(self):
        for rows in ([observation('RIGHT', 'COMMON', 'trunk_base', 1, 5)], [observation('RIGHT', 'COMMON', 'neck_base', 1, 5)],
                     [observation('RIGHT', 'COMMON', 'knee_band', 'UNDER_30', 5)], [observation('RIGHT', 'RIGHT', 'wrist_base', 1, 5)],
                     [observation('RIGHT', 'RIGHT', 'upper_arm_base', 1, 5)]):
            with self.subTest(field=rows[0]['field']):
                self.assertIsNone(so_far_of(task_with(rows)))

    def test_the_trunk_and_one_upper_arm_are_enough(self):
        both = [observation('RIGHT', 'COMMON', 'trunk_base', 1, 5), observation('RIGHT', 'LEFT', 'upper_arm_base', 1, 5)]
        self.assertEqual((so_far_of(task_with(both)) or {}).get('total'), 1)

    def test_unknown_load_is_assumed_empty_listed_and_said_so(self):
        data = preview(BASE, VIEWS)
        saved = facts.add_photo_facts(facts.apply_answers({}, [dict(target='context', value='YES')]), data, VIEWS)
        so_far = so_far_of(facts.project(task_input({}), saved, VIEWS, data))
        self.assertIn('observation.load_state', so_far['assumed'])
        self.assertIn('들고 있는 물건이 있는지 몰라 없는 것으로 계산했어요', so_far['assumption'])

    def test_a_carried_load_assumes_the_best_grip_and_a_stated_weight_is_never_replaced(self):
        data = preview(BASE, VIEWS)
        answers = [dict(target='context', value='YES'), dict(target='load', value='MEASURED'), dict(target='load_kg', value=12)]
        task = facts.project(task_input({}), facts.add_photo_facts(facts.apply_answers({}, answers), data, VIEWS), VIEWS, data)
        so_far = so_far_of(task)
        expected = calculate_reba(dict(task, manual=filled_rows(task, coupling='GOOD')), None)['slots'][0]
        self.assertEqual(so_far['total'], expected['total'])
        self.assertNotIn('observation.load_state', so_far['assumed'])
        self.assertNotIn('들고 있는 물건', so_far['assumption'])

    def test_a_stated_load_without_its_weight_gives_no_score(self):
        data = preview(BASE, VIEWS)
        answers = [dict(target='context', value='YES'), dict(target='load', value='MEASURED')]
        task = facts.project(task_input({}), facts.add_photo_facts(facts.apply_answers({}, answers), data, VIEWS), VIEWS, data)
        self.assertIsNone(so_far_of(task))

    def test_a_weight_with_an_unknown_load_state_is_a_conflict_not_a_silent_zero(self):
        task = task_with(BASE)
        task['capture']['slots'][0]['observation'].update(load_state='UNKNOWN', measured_load_kg=12)
        self.assertIsNone(so_far_of(task))

    def test_conflicting_inputs_give_no_score(self):
        task = task_with(BASE)
        slot = task['capture']['slots'][0]
        task['manual'] = [*task['manual'], dict(slot_no=slot['slot_no'], photo_id=slot['photo_id'], scope='LEFT', field='upper_arm_base', value=9, source='INTERVIEW')]
        self.assertIsNone(so_far_of(task))

    def test_calculation_leaves_the_task_untouched(self):
        task = task_with(BASE)
        before = copy.deepcopy(task)
        calculate_reba(task, None)
        self.assertEqual(task, before)

    def test_a_photo_used_twice_is_not_scored(self):
        task = task_with(BASE)
        slot = dict(task['capture']['slots'][0], slot_no=2)
        task['capture'] = dict(task['capture'], slots=[*task['capture']['slots'], slot])
        reba = calculate_reba(task, None)
        self.assertTrue(all('score_so_far' not in item for item in reba['slots']))


class ScoreSoFarBeforePhotoConfirmation(unittest.TestCase):
    def test_readings_the_task_does_not_project_yet_are_borrowed_and_named(self):
        so_far = so_far_of(unconfirmed_task())
        self.assertEqual((so_far['total'], so_far['risk']), (2, 'LOW'))
        self.assertEqual(so_far['unconfirmed_photo'], ['common.trunk_base', 'right.lower_arm_base', 'right.upper_arm_base'])
        self.assertFalse(set(so_far['unconfirmed_photo']) & set(so_far['assumed']))
        self.assertIn('left.upper_arm_base', so_far['assumed'], 'the far arm is never read from this photo')

    def test_a_refused_photo_is_never_borrowed(self):
        self.assertIsNone(so_far_of(unconfirmed_task(READ, dict(target='context', value='NO'))))

    def test_a_users_own_unknown_means_the_photo_is_not_used_either(self):
        self.assertIsNone(so_far_of(unconfirmed_task(READ, dict(target='context', value=None))))

    def test_a_confirmed_photo_uses_only_accepted_values_and_borrows_nothing(self):
        so_far = so_far_of(unconfirmed_task(READ, dict(target='context', value='YES')))
        self.assertNotIn('unconfirmed_photo', so_far)
        self.assertEqual(so_far['total'], 2)

    def test_without_an_intake_session_there_is_nothing_to_borrow(self):
        task = unconfirmed_task()
        task['conditions'].pop(contract.SESSION_KEY)
        self.assertIsNone(so_far_of(task))

    def test_a_borrowed_reading_never_overrides_an_answer(self):
        task = unconfirmed_task()
        slot = task['capture']['slots'][0]
        task['manual'] = [*task['manual'], dict(slot_no=slot['slot_no'], photo_id=slot['photo_id'], scope='COMMON', field='trunk_base', value=4, source='INTERVIEW')]
        so_far = so_far_of(task)
        self.assertEqual(so_far['total'], 3, 'trunk 4 scores 3; the photo reading 3 would have scored 2')
        self.assertNotIn('common.trunk_base', so_far['unconfirmed_photo'])

    def test_readings_of_another_photo_are_never_borrowed(self):
        views = dict(LEFT=102, RIGHT=101)
        rows = [observation('LEFT', 'COMMON', 'trunk_base', 3, 40), observation('LEFT', 'LEFT', 'upper_arm_base', 3, 60), observation('RIGHT', 'RIGHT', 'lower_arm_base', 2, 120)]
        data = preview(rows, views)
        saved = facts.add_photo_facts(facts.apply_answers({}, [dict(target='load', value='UNLOADED')]), data, views)
        task = facts.project(task_input({}), saved, views, data)
        task['conditions'][contract.SESSION_KEY] = dict(facts=saved, views=views)
        self.assertEqual(task['capture']['slots'][0]['photo_id'], 102)
        self.assertEqual(so_far_of(task)['unconfirmed_photo'], ['common.trunk_base', 'left.upper_arm_base'])

    def test_low_confidence_readings_are_not_borrowed(self):
        shaky = dict(observation('RIGHT', 'COMMON', 'trunk_base', 3, 40), low_confidence=True)
        self.assertIsNone(so_far_of(unconfirmed_task([shaky, *BASE[1:]])))

    def test_the_excel_sentence_names_what_was_borrowed_and_assumed(self):
        from ergo.report.plain import _reba_text
        base = dict(total=3, risk='LOW', assumed=['a'] * 25)
        text = lambda extra: _reba_text(dict(reba=dict(summary=dict(full_max=None, available_max=None, score_so_far=dict(base, **extra)))))
        self.assertEqual(text({}), '현재 3점 (낮음)\n확인 전 25항목은 부담 없음으로 가정')
        self.assertEqual(text(dict(unconfirmed_photo=['b'] * 4, assumed=['a'] * 24 + ['observation.load_state'])),
                         '현재 3점 (낮음)\n확인 전 25항목은 부담 없음으로 가정 · 사진 확인 전 값 4개 포함 · 들고 있는 물건 없음으로 가정')

    def test_the_ai_summary_counts_what_was_borrowed_and_assumed(self):
        so_far = dict(total=3, risk='LOW', assumed=['a'] * 24 + ['observation.load_state'], unconfirmed_photo=['b'] * 4)
        overview = lambda: payload._reba_overview(dict(summary=dict(complete_count=0, available_max=None, full_max=None, score_so_far=so_far)))
        self.assertEqual(overview()['score_so_far'], dict(total=3, risk='LOW', assumed_count=25, unconfirmed_photo_count=4, load_assumed=True))
        sentence = client.fallback_text(dict(reba=overview()))
        self.assertIn('사진 확인 전 값 4개', sentence)
        self.assertIn('확인하지 못한 25개 항목', sentence)
        self.assertIn('확정 점수가 아닙니다', sentence)
        self.assertIn('하중 가산점을 0으로 가정했으며', sentence)
        self.assertIn('실제 점수는 더 높을 수 있습니다', sentence)
        for name in ('unconfirmed_photo_count', 'load_assumed', '실제 점수는 더 높을 수 있다고'):
            self.assertIn(name, client.SYSTEM_PROMPT)
        so_far.pop('unconfirmed_photo')
        so_far['assumed'] = ['a'] * 25
        self.assertEqual(overview()['score_so_far'], dict(total=3, risk='LOW', assumed_count=25))


class ScoreSoFarInOutputs(unittest.TestCase):
    setUp = fixtures.AdaptiveIntake.setUp
    turn = fixtures.AdaptiveIntake.turn

    def analyse(self):
        photo = Path(self.temp.name) / 'RIGHT.fixture'
        photo.write_bytes(b'synthetic photo RIGHT')
        identity = self.ctx.store('create_photo', self.identity, dict(file_path=str(photo), file_name=photo.name,
            width_px=1, height_px=1, consent='UNKNOWN', notes=[]))
        inference = patch('ergo.service.intake.handle_quick_preview', return_value=preview(BASE, dict(RIGHT=identity)))
        inference.start(); self.addCleanup(inference.stop)
        self.ctx.dispatch('intake_session', dict(task_id=self.identity, views=dict(RIGHT=identity)))
        self.turn([dict(target='context', value='YES', condition='default'), dict(target='load', value='UNLOADED', condition='default')])
        return self.finish_analysis()

    def finish_analysis(self):
        handle = self.ctx.dispatch('start_analysis', dict(task_id=self.identity))
        for _ in range(200):
            analysis = self.ctx.dispatch('get_analysis', dict(analysis_id=handle['analysis_id']))
            if analysis['status'] != 'RUNNING':
                return analysis
            time.sleep(0.05)
        self.fail('analysis did not finish')

    def reba_rows(self, analysis):
        sheets = self.ctx.dispatch('preview_excel_sheets', dict(survey_id=self.survey['survey_id'], analysis_ids=[analysis['analysis_id']], comparisons=[]))
        return [row for sheet in sheets['sheets'] if sheet['name'] == '조사 결과' for table in sheet['tables'] for row in table['rows']]

    def test_excel_shows_the_score_so_far_instead_of_not_calculated(self):
        analysis = self.analyse()
        self.assertEqual(analysis['reba']['status'], 'INCOMPLETE')
        rows = [' | '.join(str(cell) for cell in row) for row in self.reba_rows(analysis)]
        reba = [row for row in rows if 'REBA 자세 점수' in row or 'REBA(전신 자세 평가)' in row]
        self.assertTrue(reba)
        self.assertTrue(all('현재 2점 (낮음)' in row for row in reba), reba)
        self.assertFalse(any('계산하지 못했어요' in row for row in reba), reba)
        self.assertIn('분석 사진 1장 기준', ' '.join(row for row in rows if 'REBA(전신 자세 평가)' in row))

    def test_the_report_marks_assumed_score_separately_from_confirmed_score(self):
        evaluation = [row for row in self.reba_rows(self.analyse()) if row and row[0] == 'REBA(전신 자세 평가)']
        self.assertEqual(len(evaluation), 1)
        self.assertEqual(evaluation[0][2], '확인 전 항목 포함')

    def test_one_click_without_answering_the_photo_still_shows_what_the_photo_read(self):
        photo = Path(self.temp.name) / 'RIGHT.fixture'
        photo.write_bytes(b'synthetic photo RIGHT')
        identity = self.ctx.store('create_photo', self.identity, dict(file_path=str(photo), file_name=photo.name, width_px=1, height_px=1, consent='UNKNOWN', notes=[]))
        inference = patch('ergo.service.intake.handle_quick_preview', return_value=preview(READ, dict(RIGHT=identity)))
        inference.start(); self.addCleanup(inference.stop)
        self.ctx.dispatch('intake_session', dict(task_id=self.identity, views=dict(RIGHT=identity)))
        analysis = self.finish_analysis()
        so_far = analysis['reba']['summary']['score_so_far']
        self.assertEqual((so_far['total'], so_far['unconfirmed_photo']), (2, ['common.trunk_base', 'right.lower_arm_base', 'right.upper_arm_base']))
        rows = [' | '.join(str(cell) for cell in row) for row in self.reba_rows(analysis)]
        self.assertTrue(any('현재 2점 (낮음)' in row and '사진 확인 전 값 3개 포함' in row for row in rows), rows)

    def test_legacy_summary_without_score_so_far_keeps_the_current_score_and_official_values(self):
        analysis = self.analyse()
        analysis['reba']['summary'].pop('score_so_far')
        summary = payload.build_numeric_summary(analysis)['reba']
        for key in ('complete_count', 'available_max', 'full_max'):
            self.assertEqual(summary[key], analysis['reba']['summary'][key])
        self.assertEqual(summary['current_score']['total'], 2)

    def test_the_ai_summary_carries_the_numbers_of_a_real_analysis(self):
        analysis = self.analyse()
        summary = payload.build_numeric_summary(analysis)
        self.assertEqual(summary['reba']['score_so_far'], dict(total=2, risk='LOW', assumed_count=len(analysis['reba']['summary']['score_so_far']['assumed'])))
        sentence = ['지금까지 확인한 값 기준 13점이며 확정 전입니다']
        self.assertTrue(payload.numbers_in_text_are_allowed(sentence, dict(reba=dict(score_so_far=dict(total=13, risk='VERY_HIGH', assumed_count=7)))))
        self.assertFalse(payload.numbers_in_text_are_allowed(sentence, dict(reba=dict())))
        self.assertIn('확정 점수가 아닙니다', client.fallback_text(summary))

    def test_explanation_generation_and_apply_preserve_the_current_score_and_snapshot(self):
        analysis=self.analyse()
        identity=analysis['analysis_id']
        before=copy.deepcopy(analysis)
        settings=self.ctx.dispatch('get_settings',{})
        settings.pop('gpt_key_present',None)
        settings.update(gpt_enabled=True,gpt_model='fixture')
        self.ctx.dispatch('update_settings',dict(settings=settings))
        with patch('ergo.gpt.client.generate',return_value=(None,'NO_API_KEY')):
            generated=self.ctx.dispatch('generate_ai_text',dict(analysis_id=identity))
        self.ctx.dispatch('apply_ai_text',dict(analysis_id=identity,text_id=generated['text']['text_id'],use_edited=False))
        after=self.ctx.dispatch('get_analysis',dict(analysis_id=identity))
        self.assertEqual(after['snapshot'],before['snapshot'])
        self.assertEqual(after['reba'],before['reba'])
        self.assertEqual(generated['text']['input_summary']['reba']['current_score']['total'],before['reba']['summary']['current_score']['total'])


if __name__ == '__main__':
    unittest.main()
