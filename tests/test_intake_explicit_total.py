"""A verified stated total does not depend on redundant model arithmetic."""
import copy
import json
import sqlite3
import threading
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch
from openpyxl import load_workbook

from ergo.intake import contract, facts
from ergo.intake.grounding import number_proof
from ergo.service.application import create_service
from tests import test_adaptive_intake as fixtures
from tests.test_intake_grounding import calculation

RECORDED=json.loads((Path(__file__).parent/'fixtures'/'intake-recorded-explicit-total-20261023.json').read_text(encoding='utf-8'))


class ExplicitTotal(unittest.TestCase):
    def setUp(self):
        self.field=next(field for field in contract.fields() if field['target']=='daily_work_min')

    def test_recorded_redundant_calculation_does_not_veto_copied_total(self):
        for phase,response in RECORDED['responses'].items():
            proposal=next(answer for answer in response['answers'] if answer['target']=='daily_work_min')
            original=copy.deepcopy(proposal)
            state,dropped=facts.merge_model({},[proposal],RECORDED['statement'])
            self.assertFalse(dropped,phase)
            self.assertEqual(state['daily_work_min@default']['value'],300)
            self.assertNotIn('calculation',state['daily_work_min@default'])
            self.assertEqual(proposal,original)

    def test_redundant_untrusted_terms_are_not_used_as_stored_proof(self):
        quote='하루 전체 실제 작업시간은 5시간입니다.'
        metadata=calculation(('없는 작업 999시간',59940),('없는 작업 888시간',53280))
        original=copy.deepcopy(metadata)
        self.assertEqual(number_proof(self.field,300,quote,source=quote,calculation=metadata),dict(quote=quote))
        self.assertEqual(metadata,original)
        compound='하루 전체 작업시간은 1시간 30분이에요.'
        self.assertIsNotNone(number_proof(self.field,90,compound,source=compound,calculation=metadata))
        annotated='하루 총 작업시간은 5시간(300분)입니다.'
        self.assertIsNotNone(number_proof(self.field,300,annotated,source=annotated,calculation=metadata))

    def test_wrong_total_units_partial_or_absent_source_still_reject(self):
        metadata=calculation(('키보드 2시간',120),('팔 들기 3시간',180))
        for value,quote,source in [
            (240,'하루 전체 실제 작업시간은 5시간입니다.','하루 전체 실제 작업시간은 5시간입니다.'),
            (300,'하루 전체 실제 작업시간은 5분입니다.','하루 전체 실제 작업시간은 5분입니다.'),
            (300,'하루 전체 실제 작업시간은 5초입니다.','하루 전체 실제 작업시간은 5초입니다.'),
            (300,'하루 전체 실제 작업시간은 5kg입니다.','하루 전체 실제 작업시간은 5kg입니다.'),
            (300,'하루 총 작업시간은 5시간(400분)입니다.','하루 총 작업시간은 5시간(400분)입니다.'),
            (300,'하루 전체 실제 작업시간은 5시간입니다.','하루 전체 실제 작업시간은 4시간입니다.'),
            (60,'1시간','하루 전체 실제 작업시간은 1시간 30분입니다.'),
            (300,'하루 총 작업시간은 4~5시간입니다.','하루 총 작업시간은 4~5시간입니다.'),
            (300,'하루 총 작업시간은 5시간이 아닙니다.','하루 총 작업시간은 5시간이 아닙니다.'),
            (300,'하루 총 작업시간은 5시간 이상입니다.','하루 총 작업시간은 5시간 이상입니다.'),
            (300,'하루 총 작업시간은 5시간 정도입니다.','하루 총 작업시간은 5시간 정도입니다.'),
            (300,'하루 총 작업시간은 5시간인지 모르겠습니다.','하루 총 작업시간은 5시간인지 모르겠습니다.'),
        ]:
            with self.subTest(value=value,quote=quote):
                self.assertIsNone(number_proof(self.field,value,quote,source=source,context=source,calculation=metadata))

    def test_a_sum_without_a_direct_total_still_requires_true_source_terms(self):
        quote='키보드 2시간 및 팔 들기 3시간'
        for metadata in [calculation(('없는 작업 2시간',120),('팔 들기 3시간',180)),
                         calculation(('키보드 2시간',180),('팔 들기 3시간',120)),
                         calculation(('키보드 2시간',120),('키보드 2시간',120))]:
            with self.subTest(metadata=metadata):
                self.assertIsNone(number_proof(self.field,300,quote,source=quote,context=quote,calculation=metadata))
        self.assertIsNotNone(number_proof(self.field,300,quote,source=quote,context=quote,
            calculation=calculation(('키보드 2시간',120),('팔 들기 3시간',180))))


class DurableExplicitTotal(unittest.TestCase):
    setUp=fixtures.AdaptiveIntake.setUp
    get=fixtures.AdaptiveIntake.get

    def test_recorded_service_sqlite_restart_snapshot_and_excel_keep_direct_total(self):
        settings=self.ctx.dispatch('get_settings',{});settings.update(gpt_enabled=True,gpt_model='recorded-provider')
        self.ctx.dispatch('update_settings',dict(settings=settings))
        def provider(payload,*args):return copy.deepcopy(RECORDED['responses'][payload['phase']]),None
        with patch('ergo.gpt.client.adaptive_intake',side_effect=provider):
            state=self.ctx.dispatch('intake_turn',dict(task_id=self.identity,text=RECORDED['statement']))
        self.assertEqual(state['task']['conditions']['daily_work_min'],300)
        self.assertNotIn('daily_work_min',{question['target'] for question in state['questions']})
        for request in state['history'][-1]['requests']:
            self.assertEqual(request['answers'],RECORDED['responses'][request['phase']]['answers'])
        decisions=[item for item in state['history'][-1]['decisions'] if item['target']=='daily_work_min']
        self.assertEqual(len(decisions),2)
        self.assertEqual(decisions[0]['outcome'],'ACCEPTED')
        self.assertTrue(all(item['outcome'] in ('ACCEPTED','UNCHANGED') for item in decisions))
        self.assertTrue(all(item['source_message_ids']==[state['messages'][0]['message_id']] for item in decisions))
        with closing(sqlite3.connect(self.db)) as db:
            stored=json.loads(db.execute('SELECT input_json FROM TASK WHERE task_id=?',(self.identity,)).fetchone()[0])
        self.assertEqual(stored['conditions']['daily_work_min'],300)
        self.ctx=create_service(self.db);restored=self.get()
        self.assertEqual(restored['history'],state['history'])
        self.assertEqual(restored['task']['input_revision'],state['task']['input_revision'])
        analysis=self.ctx.new_analysis(self.ctx.require('task',self.identity),['judgment'])
        self.ctx.run(analysis,['judgment'],threading.Event(),self.ctx.analysis_token(analysis['analysis_id']))
        selected=self.ctx.require('analysis',analysis['analysis_id']);snapshot=copy.deepcopy(selected['snapshot'])
        self.assertEqual(snapshot['conditions']['daily_work_min'],300)
        destination=str(Path(self.temp.name)/'explicit-total.xlsx')
        self.ctx.dispatch('export_excel',dict(survey_id=self.survey['survey_id'],spec=dict(
            analysis_ids=[],include_representative=False,comparisons=[],destination=destination)))
        book=load_workbook(destination,data_only=True)
        try:cells=[cell.value for sheet in book for row in sheet for cell in row if cell.value is not None]
        finally:book.close()
        self.assertTrue(any(cell.endswith('AI: 하루 전체 실제 작업시간은 5시간입니다.') for cell in cells))
        self.assertTrue(any(isinstance(cell,str) and cell.startswith('300 분/일') for cell in cells))
        self.ctx.dispatch('intake_turn',dict(task_id=self.identity,answers=[dict(target='daily_work_min',value=420)],plan=False))
        with patch('ergo.gpt.client.adaptive_intake',side_effect=provider):
            state=self.ctx.dispatch('intake_turn',dict(task_id=self.identity,text=RECORDED['statement']))
        self.assertEqual(state['task']['conditions']['daily_work_min'],420)
        self.assertEqual(self.ctx.require('analysis',analysis['analysis_id'])['snapshot'],snapshot)


if __name__=='__main__':unittest.main()
