"""Duration language, independent evidence checks and durable task projection."""
import copy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from backend.intake import contract, facts
from backend.intake.grounding import DURATION_SUM, number_grounded, number_proof
from backend.service.application import create_service


def calculation(*terms):
    return dict(operation=DURATION_SUM, terms=[dict(quote=quote, minutes=minutes) for quote, minutes in terms])


class DurationGrounding(unittest.TestCase):
    def setUp(self):
        self.daily = next(field for field in contract.fields() if field['target'] == 'daily_work_min')
        self.exposure = next(field for field in contract.fields() if field['target'] == 'card.keyboard.C1_KEYBOARD_FOCUSED')

    def test_daily_list_does_not_depend_on_a_connector_whitelist(self):
        cases = (
            '손·팔 들기 2시간 및 키보드 작업 6시간',
            '손·팔 들기 2시간 키보드 작업 6시간',
            '손·팔 들기 2시간과 키보드 작업 6시간',
            '손·팔 들기 2시간. 키보드 작업 6시간.',
            '총 작업은 손·팔 들기 2시간 하고 키보드 작업 6시간',
            '하루 전체 작업은 손·팔 들기 2시간, 키보드 작업 6시간',
        )
        for text in cases:
            with self.subTest(text=text):
                proof = number_proof(self.daily, 480, text, context=text)
                self.assertIsNotNone(proof)
                self.assertEqual([term['minutes'] for term in proof['terms']], [120, 360])
                self.assertIsNone(number_proof(self.daily, 360, text, context=text))

    def test_compound_duration_is_one_quantity_for_every_time_field(self):
        for text, minutes in [('1시간 30분', 90), ('한 시간 삼십분', 90),
                              ('1시간 반', 90), ('1시간반', 90), ('2시간 15분 30초', 135.5)]:
            with self.subTest(text=text):
                self.assertTrue(number_grounded(minutes, text, '분'))
                self.assertIsNotNone(number_proof(self.daily, minutes, '하루 전체 '+text, context='하루 전체 '+text))
                self.assertIsNotNone(number_proof(self.exposure, minutes, text, context=text))
        self.assertFalse(number_grounded(30, '1시간 30분', '분'))
        self.assertFalse(number_grounded(60, '1시간 30분', '분'))

    def test_structured_operands_can_exclude_a_repeated_total_and_unit_annotation(self):
        text = '총 8시간이고 팔 들기 2시간(120분), 키보드 작업 6시간(360분)이 전부예요.'
        proof = number_proof(self.daily, 480, text, context=text,
                             calculation=calculation(('팔 들기 2시간',120),('키보드 작업 6시간',360)))
        self.assertIsNotNone(proof)
        self.assertEqual((proof['value'], proof['operation']), (480, DURATION_SUM))
        self.assertEqual([term['minutes'] for term in proof['terms']], [120,360])
        self.assertIsNone(number_proof(self.daily, 960, text, context=text))

    def test_structured_terms_are_checked_against_original_quantities_and_arithmetic(self):
        text = '팔 들기 2시간 및 키보드 6시간'
        good = calculation(('팔 들기 2시간',120),('키보드 6시간',360))
        bad = []
        value = copy.deepcopy(good); value['terms'][0]['minutes']=180; bad.append(value)
        value = copy.deepcopy(good); value['terms'][0]['quote']='팔 들기 3시간'; bad.append(value)
        value = copy.deepcopy(good); value['terms'][1]=copy.deepcopy(value['terms'][0]); bad.append(value)
        value = copy.deepcopy(good); value['terms'][0]['minutes']=True; bad.append(value)
        value = copy.deepcopy(good); value['terms'][0]['minutes']=float('nan'); bad.append(value)
        value = copy.deepcopy(good); value['operation']='MULTIPLY'; bad.append(value)
        for value in bad:
            with self.subTest(value=value):
                self.assertIsNone(number_proof(self.daily,480,text,context=text,calculation=value))
        self.assertIsNone(number_proof(self.daily,420,text,context=text,calculation=good))
        self.assertIsNone(number_proof(self.exposure,480,text,context=text,calculation=good))

    def test_structured_operand_can_quote_an_equivalent_parenthetical_unit(self):
        text='총 작업은 팔 들기 2시간(120분), 키보드 6시간(360분)이 전부예요'
        value=calculation(('팔 들기 2시간(120분)',120),('키보드 6시간(360분)',360))
        self.assertIsNotNone(number_proof(self.daily,480,text,context=text,calculation=value))
        mismatch=text.replace('(120분)','(180분)')
        bad=calculation(('팔 들기 2시간(180분)',120),('키보드 6시간(360분)',360))
        self.assertIsNone(number_proof(self.daily,480,mismatch,context=mismatch,calculation=bad))

    def test_compound_operand_cannot_be_split_or_reused_as_two_work_periods(self):
        text='하루 전체 팔 들기 1시간 30분 및 키보드 6시간'
        good=calculation(('팔 들기 1시간 30분',90),('키보드 6시간',360))
        self.assertIsNotNone(number_proof(self.daily,450,text,context=text,calculation=good))
        split=calculation(('1시간',60),('30분',30),('키보드 6시간',360))
        self.assertIsNone(number_proof(self.daily,450,text,context=text,calculation=split))
        for quote,minutes in [('1시간',60),('30분',30)]:
            self.assertIsNone(number_proof(self.daily,minutes,quote,context=text,source=text))

    def test_same_duration_can_be_used_twice_only_at_distinct_source_occurrences(self):
        text='팔 들기 2시간 및 키보드 2시간'
        proof=number_proof(self.daily,240,text,context=text,
                           calculation=calculation(('2시간',120),('2시간',120)))
        self.assertIsNotNone(proof)
        one='팔 들기 2시간'
        self.assertIsNone(number_proof(self.daily,240,one,context=one,
                                      calculation=calculation(('2시간',120),('2시간',120))))

    def test_overlap_break_range_partial_and_other_period_still_require_clarification(self):
        base='팔 들기 2시간 및 키보드 6시간'
        proof=calculation(('팔 들기 2시간',120),('키보드 6시간',360))
        for suffix in ['동시에 해요','두 시간은 여섯 시간에 포함돼요','휴식도 들어 있어요',
                       '주당 시간이에요','일부 작업이고 다른 작업이 더 있어요','둘 중 하나만 해요']:
            text=base+'. '+suffix
            with self.subTest(text=text):
                self.assertIsNone(number_proof(self.daily,480,base,context=text))
                self.assertIsNone(number_proof(self.daily,480,base,context=text,calculation=proof))
        for text in ['팔 들기 2~3시간 및 키보드 6시간','팔 들기 -2시간 및 키보드 6시간',
                     '팔 들기 2시간(120분) 및 키보드 6시간','총 8시간이고 팔 2시간 키보드 6시간']:
            with self.subTest(text=text):self.assertIsNone(number_proof(self.daily,480,text,context=text))

    def test_schema_exposes_arithmetic_only_for_fields_that_allow_it(self):
        variants=contract.response_schema()['properties']['answers']['items']['anyOf']
        by_target={variant['properties']['target']['enum'][0]:variant for variant in variants}
        self.assertIn('calculation',by_target['daily_work_min']['properties'])
        self.assertNotIn('calculation',by_target[self.exposure['target']]['properties'])
        schema=by_target['daily_work_min']['properties']['calculation']
        structured=next(item for item in schema['anyOf'] if item['type']=='object')
        self.assertFalse(structured['additionalProperties'])
        self.assertEqual(set(structured['required']),set(structured['properties']))

    def test_direct_units_bare_replies_and_other_numeric_units_remain_compatible(self):
        for value,quote,unit in [(480,'8시간','분'),(90,'90분','분'),(0,'0분','분'),
                                 (5,'5kg','kg'),(1,'1분에 1번씩 하루 30분','회/분')]:
            self.assertTrue(number_grounded(value,quote,unit))
        self.assertTrue(number_grounded(90,'90','분',bare=True))
        self.assertFalse(number_grounded(90,'90','분'))
        self.assertFalse(number_grounded(1,'2분에 1번','회/분'))

    def test_unrelated_uncertain_period_does_not_drop_an_explicit_daily_total(self):
        source='하루 전체 실제 작업은 8시간이고 팔 들기는 2~3시간 정도예요.'
        self.assertIsNotNone(number_proof(self.daily,480,'하루 전체 실제 작업은 8시간',context=source,source=source))
        self.assertIsNone(number_proof(self.daily,180,'3시간',context=source,source=source))
        self.assertIsNone(number_proof(self.daily,90,'90',bare=True,context='190',source='190'))


class DurableDurationGrounding(unittest.TestCase):
    def test_alternate_expressions_persist_and_no_longer_ask_for_daily_total(self):
        for text,total,proof in [
            ('팔 들기 2시간 및 키보드 6시간',480,None),
            ('팔 들기 2시간 키보드 6시간',480,None),
            ('총 작업은 팔 들기 2시간 하고 키보드 6시간',480,None),
            ('하루 전체 작업시간은 1시간 30분이에요',90,None),
            ('전체 작업은 팔 들기 1시간 30분과 키보드 6시간',450,
             calculation(('팔 들기 1시간 30분',90),('키보드 6시간',360))),
            ('하루 총 작업은 팔 들기 2시간(120분), 키보드 6시간(360분)이 전부예요.',480,
             calculation(('하루 총 작업은 팔 들기 2시간(120분)',120),('키보드 6시간(360분)이 전부예요.',360))),
        ]:
            with self.subTest(text=text), tempfile.TemporaryDirectory() as folder:
                db=Path(folder)/'case.db';ctx=create_service(db)
                survey=ctx.dispatch('create_survey',dict(draft=dict(title='시간 표현 회귀')))
                task=ctx.dispatch('create_task',dict(survey_id=survey['survey_id'],draft=dict(task_name='시간 작업')))
                settings=ctx.dispatch('get_settings',{});settings.update(gpt_enabled=True,gpt_model='controlled-provider')
                ctx.dispatch('update_settings',dict(settings=settings))
                proposal=dict(target='daily_work_min',condition='default',number=total,text=None,quote=text)
                if proof is not None:proposal['calculation']=proof
                raw=dict(answers=[proposal],questions=[])
                with patch('backend.gpt.client.adaptive_intake',return_value=(raw,None)):
                    state=ctx.dispatch('intake_turn',dict(task_id=task['task_id'],text=text))
                self.assertEqual(state['task']['conditions']['daily_work_min'],total)
                self.assertNotIn('daily_work_min',{question['target'] for question in state['questions']})
                restored=create_service(db).dispatch('intake_session',dict(task_id=task['task_id']))
                self.assertEqual(restored['task']['conditions']['daily_work_min'],total)
                self.assertIn(text,[message['text'] for message in restored['messages']])
                analysis=ctx.new_analysis(ctx.require('task',task['task_id']),['judgment'])
                self.assertEqual(analysis['snapshot']['conditions']['daily_work_min'],total)
                state=ctx.dispatch('intake_turn',dict(task_id=task['task_id'],answers=[dict(target='daily_work_min',value=420)],plan=False))
                with patch('backend.gpt.client.adaptive_intake',return_value=(raw,None)):
                    state=ctx.dispatch('intake_turn',dict(task_id=task['task_id'],text=text))
                self.assertEqual(state['task']['conditions']['daily_work_min'],420)
                self.assertEqual(analysis['snapshot']['conditions']['daily_work_min'],total)


if __name__ == '__main__':
    unittest.main()
