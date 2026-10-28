"""A valid question must not suppress the second check of the user's statement."""
import copy
import json
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

from tests import test_adaptive_intake as fixtures
from backend.intake import source_coverage
from backend.service.application import create_service

FIXTURES=Path(__file__).parent/'fixtures'
BILATERAL=json.loads((FIXTURES/'intake-recorded-bilateral-omission-20261023.json').read_text(encoding='utf-8'))
COMPLETENESS=json.loads((FIXTURES/'intake-recorded-completeness-omission-20261023.json').read_text(encoding='utf-8'))


def answer(target,value,quote,condition='default'):
    return dict(target=target,condition=condition,number=value if type(value) in (int,float) else None,
                text=value if isinstance(value,str) else None,quote=quote)


def raw_request(request):
    return dict(answers=copy.deepcopy(request['answers']),questions=copy.deepcopy(request['questions']),_connection=copy.deepcopy(request['connection']))


class SourceCoverage(unittest.TestCase):
    setUp=fixtures.AdaptiveIntake.setUp
    get=fixtures.AdaptiveIntake.get
    turn=fixtures.AdaptiveIntake.turn
    photo_session=fixtures.PairedAdaptiveIntake.photo_session

    def enable(self):
        settings=self.ctx.dispatch('get_settings',{});settings.update(gpt_enabled=True,gpt_model='controlled-provider')
        self.ctx.dispatch('update_settings',dict(settings=settings))

    def test_bilateral_omission_is_checked_again_even_with_a_valid_next_question(self):
        self.photo_session(sides=('RIGHT',));self.enable()
        original=BILATERAL['checkpoint']['session']['history'][0]['requests'][0]
        first=raw_request(original)
        first['questions']=[dict(target='other_work',condition='default',text='다른 작업도 있나요?',reason='종류 확인')]
        before=copy.deepcopy(first);payloads=[]
        def provider(payload,*args):
            payloads.append(copy.deepcopy(payload))
            if payload['phase']=='EXTRACT_AND_PLAN':return copy.deepcopy(first),None
            self.assertEqual(payload['purpose'],source_coverage.PURPOSE)
            self.assertIn('other_work',{item['target'] for item in payload['missing']})
            self.assertEqual(payload['previous_proposals'][0]['answers'],original['answers'])
            self.assertTrue(any(item['target']=='manual.RIGHT.coupling' and item['reason']=='EMPTY_VALUE' for item in payload['previous_decisions']))
            self.assertEqual(payload['source_photo_scope']['views'][0]['photo_id'],self.get()['task']['capture']['slots'][0]['photo_id'])
            return dict(answers=[answer('manual.RIGHT.coupling','GOOD','양손 손잡이는 잡기 좋아요.')],questions=[]),None
        with patch('backend.gpt.client.adaptive_intake',side_effect=provider):
            state=self.ctx.dispatch('intake_turn',dict(task_id=self.identity,text=BILATERAL['case']['statement']))
        self.assertEqual([payload['phase'] for payload in payloads],['EXTRACT_AND_PLAN','FOLLOWUP'])
        self.assertEqual(first,before)
        known={item['target']:item for item in state['facts']}
        self.assertEqual(known['manual.LEFT.coupling']['value'],'GOOD');self.assertEqual(known['manual.RIGHT.coupling']['value'],'GOOD')
        self.assertFalse(any(question['target']=='manual.RIGHT.coupling' for question in state['questions']))
        self.assertEqual(state['history'][-1]['requests'][0]['answers'],original['answers'])
        restored=create_service(self.db).dispatch('intake_session',dict(task_id=self.identity))
        self.assertEqual(restored['history'],state['history'])

    def test_recorded_all_conditions_followup_is_saved_even_with_a_valid_question(self):
        self.photo_session(sides=('RIGHT',));self.enable()
        first_turn=COMPLETENESS['checkpoints']['01-first-ai']['session']['history'][0]['requests'][0]
        followup_turn=COMPLETENESS['checkpoints']['02-followup-ai']['session']['history'][-1]['requests'][0]
        phases=[]
        def provider(payload,*args):
            phases.append(payload['phase'])
            if payload['phase']=='EXTRACT_AND_PLAN':
                return raw_request(followup_turn if '모든 들기 조건' in payload['text'] else first_turn),None
            if '모든 들기 조건' in payload['text']:
                return dict(answers=[answer('complete.lift','YES','이 20kg 조건이 모든 들기 조건입니다.')],questions=[]),None
            return dict(answers=[],questions=[]),None
        with patch('backend.gpt.client.adaptive_intake',side_effect=provider):
            self.ctx.dispatch('intake_turn',dict(task_id=self.identity,text=COMPLETENESS['case']['statement']))
            state=self.ctx.dispatch('intake_turn',dict(task_id=self.identity,text=COMPLETENESS['case']['followup']))
        self.assertEqual(phases,['EXTRACT_AND_PLAN','FOLLOWUP','EXTRACT_AND_PLAN','FOLLOWUP'])
        self.assertEqual(next(item['value'] for item in state['facts'] if item['target']=='complete.lift'),'YES')
        self.assertEqual(state['history'][-1]['requests'][0]['answers'],followup_turn['answers'])

    def test_reads_structured_only_and_nonplanning_saves_never_call_the_provider(self):
        self.enable()
        with patch('backend.gpt.client.adaptive_intake',side_effect=AssertionError('no automatic AI')) as provider:
            self.get();self.get()
            self.ctx.dispatch('intake_turn',dict(task_id=self.identity,answers=[dict(target='daily_work_min',value=480)]))
            self.ctx.dispatch('intake_turn',dict(task_id=self.identity,text='미리 저장한 설명',plan=False))
        provider.assert_not_called()

    def test_a_failed_first_request_still_gets_only_one_source_check(self):
        self.enable();phases=[]
        def provider(payload,*args):
            phases.append(payload['phase'])
            if payload['phase']=='EXTRACT_AND_PLAN':return None,'API_ERROR'
            return dict(answers=[answer('daily_work_min',480,'하루 전체 8시간')],questions=[]),None
        with patch('backend.gpt.client.adaptive_intake',side_effect=provider):
            state=self.ctx.dispatch('intake_turn',dict(task_id=self.identity,text='하루 전체 8시간'))
        self.assertEqual(phases,['EXTRACT_AND_PLAN','FOLLOWUP'])
        self.assertEqual(state['task']['conditions']['daily_work_min'],480)
        self.assertEqual(state['history'][-1]['requests'][0]['reason'],'API_ERROR')

    def test_first_response_revision_race_still_checks_source_and_keeps_direct_owner(self):
        self.enable();entered=threading.Event();release=threading.Event();result=[];phases=[]
        def provider(payload,*args):
            phases.append(payload['phase'])
            if payload['phase']=='EXTRACT_AND_PLAN':
                entered.set();self.assertTrue(release.wait(10))
                return dict(answers=[answer('daily_work_min',480,'하루 8시간')],questions=[]),None
            self.assertEqual(next(item['value'] for item in payload['known'] if item['target']=='daily_work_min'),420)
            return dict(answers=[answer('annual_work_days',220,'연 220일')],questions=[]),None
        with patch('backend.gpt.client.adaptive_intake',side_effect=provider):
            worker=threading.Thread(target=lambda:result.append(self.ctx.dispatch('intake_turn',dict(task_id=self.identity,text='하루 8시간 연 220일'))))
            worker.start()
            try:
                self.assertTrue(entered.wait(10))
                self.ctx.dispatch('intake_turn',dict(task_id=self.identity,answers=[dict(target='daily_work_min',value=420)],plan=False))
            finally:release.set();worker.join(10)
        self.assertFalse(worker.is_alive());self.assertEqual(phases,['EXTRACT_AND_PLAN','FOLLOWUP'])
        self.assertEqual(result[0]['task']['conditions']['daily_work_min'],420)
        self.assertEqual(result[0]['task']['conditions']['annual_work_days'],220)
        receipt=next(turn for turn in result[0]['history'] if turn['requests'])
        self.assertEqual(receipt['status'],'RECONCILED');self.assertEqual(len(receipt['requests']),2)

    def test_inactive_photo_values_and_compatibility_aliases_are_not_model_known_facts(self):
        session=dict(views={'RIGHT':2},facts={
            'alias':dict(target='manual.RIGHT.coupling',condition='default',value='GOOD',state='KNOWN',source='AI',alias_of='canonical'),
            'old':dict(target='manual.RIGHT.coupling',condition='photo:1',photo_id=1,value='GOOD',state='KNOWN',source='AI'),
            'new':dict(target='manual.RIGHT.coupling',condition='photo:2',photo_id=2,value='POOR',state='KNOWN',source='USER')})
        known=source_coverage.known_values(session)
        self.assertEqual([(item['condition'],item['value']) for item in known],[('photo:2','POOR')])

    def test_photo_replacement_during_extraction_keeps_source_scope_and_nonphoto_information(self):
        self.photo_session(sides=('RIGHT',));self.enable()
        old=self.get()['task']['capture']['slots'][0]['photo_id']
        path=Path(self.temp.name)/'replacement.fixture';path.write_bytes(b'synthetic replacement')
        replacement=self.ctx.store('create_photo',self.identity,dict(file_path=str(path),file_name=path.name,width_px=1,height_px=1,consent='UNKNOWN',notes=[]))
        entered=threading.Event();release=threading.Event();result=[]
        def provider(payload,*args):
            if payload['phase']=='EXTRACT_AND_PLAN':
                entered.set();self.assertTrue(release.wait(10));return dict(answers=[],questions=[]),None
            self.assertEqual(payload['source_photo_scope']['views'][0]['photo_id'],old)
            self.assertEqual(payload['current_photo_scope']['views'][0]['photo_id'],replacement)
            return dict(answers=[answer('manual.RIGHT.coupling','GOOD','양손 손잡이는 잡기 좋아요.'),answer('annual_work_days',220,'연 220일')],questions=[]),None
        with patch('backend.gpt.client.adaptive_intake',side_effect=provider):
            worker=threading.Thread(target=lambda:result.append(self.ctx.dispatch('intake_turn',dict(task_id=self.identity,text='양손 손잡이는 잡기 좋아요. 연 220일 일해요.'))))
            worker.start()
            try:
                self.assertTrue(entered.wait(10))
                self.ctx.dispatch('intake_session',dict(task_id=self.identity,views={'RIGHT':replacement}))
            finally:release.set();worker.join(10)
        self.assertFalse(worker.is_alive())
        self.assertEqual(result[0]['task']['conditions']['annual_work_days'],220)
        self.assertFalse(any(item['target']=='manual.RIGHT.coupling' and item['value']=='GOOD' for item in result[0]['facts']))
        self.assertTrue(any(item['reason']=='PHOTO_CONTEXT_CONFIRMATION_REQUIRED' for item in result[0]['diagnostics']))
        self.assertTrue(any(answer['target']=='manual.RIGHT.coupling' for turn in result[0]['history'] for request in turn['requests'] for answer in request['answers']))

    def test_a_stated_single_hand_is_never_broadcast_to_the_other_hand(self):
        self.photo_session(sides=('RIGHT',));self.enable();phases=[]
        def provider(payload,*args):
            phases.append(payload['phase'])
            return dict(answers=[answer('manual.LEFT.coupling','GOOD','왼손 손잡이는 잡기 좋아요.')] if payload['phase']=='FOLLOWUP' else [],questions=[]),None
        with patch('backend.gpt.client.adaptive_intake',side_effect=provider):
            state=self.ctx.dispatch('intake_turn',dict(task_id=self.identity,text='왼손 손잡이는 잡기 좋아요.'))
        self.assertEqual(phases,['EXTRACT_AND_PLAN','FOLLOWUP'])
        self.assertTrue(any(item['target']=='manual.LEFT.coupling' and item['value']=='GOOD' for item in state['facts']))
        self.assertFalse(any(item['target']=='manual.RIGHT.coupling' and item['value']=='GOOD' for item in state['facts']))


if __name__=='__main__':unittest.main()
