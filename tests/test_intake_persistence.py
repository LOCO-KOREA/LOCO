"""Independent storage regressions: stale unknowns, context and per-turn receipts."""
import copy
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch

from ergo.intake import contract
from ergo.service.application import create_service


def proposal(value,quote,*,unknown=False):
    return dict(target='daily_work_min',condition='default',number=None if unknown else value,
                text='UNKNOWN' if unknown else None,quote=quote)


class IntakePersistence(unittest.TestCase):
    def setUp(self):
        self.folder=tempfile.TemporaryDirectory();self.addCleanup(self.folder.cleanup)
        self.db=Path(self.folder.name)/'loco.db';self.ctx=create_service(self.db)
        survey=self.ctx.dispatch('create_survey',dict(draft=dict(title='저장 반례')))
        self.task=self.ctx.dispatch('create_task',dict(survey_id=survey['survey_id'],draft=dict(task_name='작업')))
        settings=self.ctx.dispatch('get_settings',{});settings.update(gpt_enabled=True,gpt_model='controlled-provider')
        self.ctx.dispatch('update_settings',dict(settings=settings))

    def turn(self,text='',answers=(),raw=(),**kw):
        response=dict(answers=list(raw),questions=[],_connection=dict(model='controlled-provider',response_id='extract-id'))
        with patch('ergo.gpt.client.adaptive_intake',return_value=(response,None)):
            return self.ctx.dispatch('intake_turn',dict(task_id=self.task['task_id'],text=text,answers=list(answers),**kw))

    def test_old_unknown_never_clears_a_later_confirmed_value(self):
        old='하루 작업시간은 모르겠어요'
        self.turn(old)
        self.turn('하루 전체 8시간이에요',raw=[proposal(480,'하루 전체 8시간')])
        result=self.turn('다음으로',raw=[proposal(None,old,unknown=True)])
        self.assertEqual(result['task']['conditions']['daily_work_min'],480)
        self.assertIn('STALE_QUOTE',{item['reason'] for item in result['dropped']})
        restored=create_service(self.db).dispatch('intake_session',dict(task_id=self.task['task_id']))
        self.assertEqual(restored['task']['conditions']['daily_work_min'],480)

    def test_current_explicit_unknown_and_direct_user_priority_are_distinct(self):
        self.turn('하루 전체 8시간',raw=[proposal(480,'하루 전체 8시간')])
        result=self.turn('지금 작업시간은 모르겠어요',raw=[proposal(None,'지금 작업시간은 모르겠어요',unknown=True)])
        self.assertIsNone(result['task']['conditions']['daily_work_min'])
        self.turn(answers=[dict(target='daily_work_min',value=420)],plan=False)
        result=self.turn('지금 작업시간은 모르겠어요',raw=[proposal(None,'지금 작업시간은 모르겠어요',unknown=True)])
        self.assertEqual(result['task']['conditions']['daily_work_min'],420)
        self.assertIn('USER_VALUE_KEPT',{item['reason'] for item in result['dropped']})

    def test_structured_edits_do_not_evict_the_saved_description_from_ai_context(self):
        original='하루 전체 8시간 일해요'
        self.turn(original)
        for i in range(12):
            self.turn(answers=[dict(target='task_name',value='직접 수정 '+str(i))],plan=False)
        payloads=[]
        def provider(payload,*args):
            payloads.append(copy.deepcopy(payload))
            return dict(answers=[proposal(480,original)],questions=[]),None
        with patch('ergo.gpt.client.adaptive_intake',side_effect=provider):
            result=self.ctx.dispatch('intake_turn',dict(task_id=self.task['task_id'],text=''))
        self.assertTrue(any(original in payload['prior_user_text'] for payload in payloads))
        self.assertEqual(result['task']['conditions']['daily_work_min'],480)

    def test_unprocessed_older_text_has_priority_over_recent_successful_texts(self):
        original='하루 전체 8시간 일해요'
        self.turn(original)
        for i in range(12):
            text='이름은 합성 작업 '+str(i)
            self.turn(text,raw=[dict(target='task_name',condition='default',number=None,text='작업 '+str(i),quote=text)])
        payloads=[]
        def provider(payload,*args):
            payloads.append(copy.deepcopy(payload));return dict(answers=[proposal(480,original)],questions=[]),None
        with patch('ergo.gpt.client.adaptive_intake',side_effect=provider):
            result=self.ctx.dispatch('intake_turn',dict(task_id=self.task['task_id'],text=''))
        self.assertTrue(any(original in payload['prior_user_text'] for payload in payloads))
        self.assertEqual(result['task']['conditions']['daily_work_min'],480)

    def test_partial_extraction_does_not_expire_the_rest_of_the_same_sentence(self):
        source='작업 이름은 조립이고 하루 전체 8시간 일해요'
        self.turn(source,raw=[dict(target='task_name',condition='default',number=None,text='조립',quote='작업 이름은 조립')])
        for i in range(12):self.turn('이후 설명 '+str(i)+'가'*2300)
        from ergo.intake.history import context
        session=self.ctx.require('task',self.task['task_id'])['conditions'][contract.SESSION_KEY]
        selected=context(session)
        self.assertIn(source,selected['texts'])
        self.assertEqual(selected['omitted_message_ids'],[])
        self.assertGreater(selected['char_count'],24000)

    def test_rejection_survives_later_turns_and_restores_with_its_response_ids(self):
        source='하루 작업은 손을 쓰는 2시간입니다'
        self.turn(source,raw=[proposal(480,source)])
        later=self.turn('계속 확인해요')
        self.assertTrue(any(item['target']=='daily_work_min' for item in later['diagnostics']))
        restored=create_service(self.db).dispatch('intake_session',dict(task_id=self.task['task_id']))
        history=restored['history']
        first=next(turn for turn in history if turn.get('message_id')==restored['messages'][0]['message_id'])
        self.assertEqual(first['requests'][0]['connection']['response_id'],'extract-id')
        self.assertEqual(first['requests'][0]['answers'][0]['number'],480)
        self.assertEqual(first['decisions'][0]['reason'],'UNIT_OR_NUMBER_NOT_GROUNDED')
        self.assertEqual(first['decisions'][0]['proposal_index'],0)
        self.assertEqual(first['decisions'][0]['request_index'],0)
        self.assertEqual(first['decisions'][0]['outcome'],'REJECTED')

    def test_extract_and_followup_are_separate_receipts_and_direct_edit_resolves_notice(self):
        count=0
        def provider(payload,*args):
            nonlocal count;count+=1
            return dict(answers=[proposal(480,'하루 2시간')] if count==1 else [],questions=[],
                        _connection=dict(model='controlled-provider',response_id=payload['phase'])),None
        with patch('ergo.gpt.client.adaptive_intake',side_effect=provider):
            first=self.ctx.dispatch('intake_turn',dict(task_id=self.task['task_id'],text='하루 2시간'))
        turn=first['history'][-1]
        self.assertEqual([request['phase'] for request in turn['requests']],['EXTRACT_AND_PLAN','FOLLOWUP'])
        self.assertEqual([request['connection']['response_id'] for request in turn['requests']],['EXTRACT_AND_PLAN','FOLLOWUP'])
        self.assertTrue(first['diagnostics'])
        fixed=self.turn(answers=[dict(target='daily_work_min',value=120)],plan=False)
        self.assertFalse(any(item['target']=='daily_work_min' for item in fixed['diagnostics']))
        self.assertEqual(fixed['history'][-1]['decisions'][0]['outcome'],'USER_SAVED')
        self.assertEqual(fixed['history'][-2],turn)

    def test_late_response_retains_conflict_and_applies_unrelated_information(self):
        entered=threading.Event();release=threading.Event();result=[]
        def provider(payload,*args):
            entered.set();release.wait(10)
            return dict(answers=[proposal(480,'하루 8시간'),dict(target='annual_work_days',condition='default',
                number=220,text=None,quote='연 220일')],questions=[],_connection=dict(response_id='late-id')),None
        with patch('ergo.gpt.client.adaptive_intake',side_effect=provider):
            thread=threading.Thread(target=lambda:result.append(self.ctx.dispatch('intake_turn',dict(
                task_id=self.task['task_id'],text='하루 8시간 연 220일 일해요'))))
            thread.start();self.assertTrue(entered.wait(5))
            self.turn(answers=[dict(target='daily_work_min',value=360)],plan=False)
            release.set();thread.join(10)
        self.assertFalse(thread.is_alive());self.assertTrue(result)
        restored=create_service(self.db).dispatch('intake_session',dict(task_id=self.task['task_id']))
        self.assertEqual(restored['task']['conditions']['daily_work_min'],360)
        self.assertEqual(restored['task']['conditions']['annual_work_days'],220)
        receipt=next(turn for turn in restored['history'] if turn['requests'])
        self.assertEqual(receipt['status'],'RECONCILED')
        self.assertEqual(receipt['requests'][0]['connection']['response_id'],'late-id')
        self.assertEqual([d['outcome'] for d in receipt['decisions'] if d['request_index']==0],['REJECTED','ACCEPTED'])
        self.assertEqual([request['phase'] for request in receipt['requests']],['EXTRACT_AND_PLAN','FOLLOWUP'])
        self.assertEqual([d['outcome'] for d in receipt['decisions'] if d['request_index']==1],['REJECTED','UNCHANGED'])
        self.assertTrue(any(d['target']=='daily_work_min' for d in restored['diagnostics']))

    def test_followup_proposals_remain_visible_without_resolving_extract_rejections(self):
        def provider(payload,*args):
            return dict(answers=[proposal(480,'하루 2시간')],questions=[],
                _connection=dict(response_id=payload['phase'])),None
        with patch('ergo.gpt.client.adaptive_intake',side_effect=provider):
            state=self.ctx.dispatch('intake_turn',dict(task_id=self.task['task_id'],text='하루 2시간'))
        turn=state['history'][-1]
        self.assertEqual(turn['decisions'][-1]['request_index'],1)
        self.assertEqual(turn['decisions'][-1]['outcome'],'REJECTED')
        self.assertEqual(state['diagnostics'][0]['reason'],'UNIT_OR_NUMBER_NOT_GROUNDED')

    def test_reconciliation_keeps_the_original_bare_reply_context(self):
        from ergo.intake import facts
        field=next(f for f in contract.fields() if f['target']=='daily_work_min')
        result,dropped=facts.merge_model({},[proposal(420,'420')],'420',focus=[dict(field,condition='default')],reconcile=True)
        self.assertFalse(dropped)
        self.assertEqual(result['daily_work_min@default']['value'],420)
        original=result['daily_work_min@default']
        newer={**original,'quote':'새로운 근거'}
        result,dropped=facts.merge_model({'daily_work_min@default':newer},[proposal(420,'420')],'420',focus=[dict(field,condition='default')],reconcile=True)
        self.assertEqual(result['daily_work_min@default'],newer)
        result,dropped=facts.merge_model(result,[proposal(None,'모르겠어요',unknown=True)],'모르겠어요',reconcile=True)
        self.assertEqual(result['daily_work_min@default'],newer)
        self.assertEqual(dropped[0]['reason'],'STALE_QUOTE')

    def test_direct_fix_resolves_the_normalized_global_diagnostic(self):
        self.turn('하루 2시간',raw=[proposal(480,'하루 2시간')])
        fixed=self.turn(answers=[dict(target='daily_work_min',condition='non-global-row',value=120)],plan=False)
        self.assertFalse(fixed['diagnostics'])
        self.assertEqual(fixed['history'][-1]['decisions'][0]['condition'],'default')


if __name__=='__main__':unittest.main()
