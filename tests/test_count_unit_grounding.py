"""Recorded mixed daily/rate quantities must keep their own period and identity."""
import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from ergo.intake.grounding import number_grounded
from ergo.service.application import create_service
from ergo.gpt.payload import build_numeric_summary


FIXTURE=Path(__file__).parent/'fixtures/intake-recorded-mixed-count-units-20261027.json'
MIXED='20kg 상자를 하루 120회, 1분에 2회씩, 하루 총 60분 들어 옮깁니다.'


class CountUnitGrounding(unittest.TestCase):
    def test_each_count_is_bound_to_its_own_daily_or_minute_period(self):
        for quote in (MIXED,'하루 120회이고 분당 2회입니다.','1분에 2회, 하루 120회',
                      '20kg 상자는 하루 120회, 10kg 상자는 분당 2회입니다.'):
            for value,unit,expected in [(120,'회/일',True),(2,'회/분',True),
                                        (120,'회/분',False),(2,'회/일',False)]:
                with self.subTest(quote=quote,value=value,unit=unit):
                    self.assertEqual(number_grounded(value,quote,unit),expected)

    def test_hourly_and_suffix_units_cannot_borrow_another_occurrence(self):
        for quote in ('하루 120회, 한 시간에 10번, 매분 2회',
                      '120회/일, 10회/시간, 2회/분'):
            for value,unit in [(120,'회/일'),(10,'회/시간'),(2,'회/분')]:
                with self.subTest(quote=quote,value=value,unit=unit):
                    self.assertTrue(number_grounded(value,quote,unit))
            for value,unit in [(120,'회/분'),(120,'회/시간'),(10,'회/일'),(2,'회/시간')]:
                with self.subTest(quote=quote,value=value,unit=unit):
                    self.assertFalse(number_grounded(value,quote,unit))

    def test_other_denominators_and_unstated_conversion_stay_rejected(self):
        for value,quote,unit in [(120,'분당 120회','회/일'),(120,'매시간 120회','회/일'),
                                 (120,'분당 2회씩 하루 60분','회/일'),
                                 (60,'1분에 1회','회/시간'),(1,'2분에 1번','회/분'),
                                 (1,'1회/2분','회/분'),(30,'매주 30회','회/일'),
                                 (30,'2일에 30회','회/일'),(20,'20kg 상자를 하루 120회','회/일')]:
            for bare in (False,True):
                with self.subTest(value=value,quote=quote,unit=unit,bare=bare):
                    self.assertFalse(number_grounded(value,quote,unit,bare=bare))

    def test_focused_bare_answers_and_other_units_keep_their_existing_meaning(self):
        self.assertTrue(number_grounded(120,'120','회/일',bare=True))
        self.assertTrue(number_grounded(2,'2번','회/분',bare=True))
        self.assertFalse(number_grounded(2,'2번','회/분'))
        self.assertTrue(number_grounded(20,MIXED,'kg'))
        self.assertFalse(number_grounded(120,MIXED,'kg'))

    def test_actual_recorded_api_answers_survive_projection_reopen_and_ai_summary(self):
        recorded=json.loads(FIXTURE.read_text(encoding='utf-8'))
        self.assertEqual(len(recorded['responses']),2)
        first=recorded['responses'][0]['answers']
        daily=next(row for row in first if row['target']=='card.lift.lift_count_day')
        rate=next(row for row in first if row['target']=='card.lift.lift_rate_min')
        self.assertEqual((daily['number'],rate['number']),(120,2))
        self.assertEqual(daily['quote'],rate['quote'])
        with tempfile.TemporaryDirectory() as directory:
            db=Path(directory)/'recorded-counts.db';ctx=create_service(str(db))
            survey=ctx.dispatch('create_survey',dict(draft=dict(title='Mixed-unit recorded replay')))
            task=ctx.dispatch('create_task',dict(survey_id=survey['survey_id'],draft=dict(task_name='20kg 상자')))
            settings=ctx.settings();settings.update(gpt_enabled=True,gpt_model='fixture-only')
            ctx.dispatch('update_settings',dict(settings=settings))
            replies=[(copy.deepcopy(response),None) for response in recorded['responses']]
            with patch('ergo.gpt.client.adaptive_intake',side_effect=replies) as provider:
                state=ctx.dispatch('intake_turn',dict(task_id=task['task_id'],text=recorded['text']))
            self.assertEqual(provider.call_count,2,'replay extraction and source cross-check without a provider request')
            stored=state['task'];rows={row['criterion_no']:row for row in stored['legal']['criteria']}
            self.assertEqual(rows[8]['rows'][0]['row_id'],daily['condition'])
            self.assertEqual(rows[8]['rows'][0]['lift_count_day'],120)
            self.assertEqual(rows[10]['rows'][0]['row_id'],rate['condition'])
            self.assertEqual(rows[10]['rows'][0]['lift_rate_min'],2)
            self.assertEqual(rows[10]['rows'][0]['minutes'],60)
            self.assertEqual(rows[8]['rows'][0]['load_mass_kg'],20)
            targets={row['target'] for row in state['questions']}
            self.assertNotIn(daily['target'],targets);self.assertNotIn(rate['target'],targets)
            restored=create_service(str(db)).dispatch('intake_session',dict(task_id=task['task_id']))
            self.assertEqual(restored['task']['legal'],stored['legal'])
            self.assertEqual(restored['task']['input_revision'],stored['input_revision'])
            analysis=ctx.dispatch('recalculate_judgments',dict(task_id=task['task_id']))
            summary=build_numeric_summary(analysis)['recorded_work_inputs']
            for field,value in [(daily['target'],120),(rate['target'],2)]:
                self.assertTrue(any(row['field']==field and row['value']==value for row in summary))
            self.assertEqual(analysis['snapshot']['legal'],stored['legal'])


if __name__=='__main__':unittest.main()
