"""All AI paths wait for one request; no local deadline or duplicate submission."""
import json
import os
import tempfile
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from ergo import ai_config as config
from ergo.gpt import client, intake, client_pool
from ergo.service.application import create_service
from ergo.vision import client as vision_client
from tests.test_v2_gpt import summary_fixture,content_fixture


class APITimeoutError(Exception):
    """A provider/transport timeout can still arrive with local timeouts disabled."""


class ServerBusy(Exception):
    pass


def completed(data=None):
    return SimpleNamespace(id='resp_ok',status='completed',model='m',reasoning=SimpleNamespace(effort='high'),
        output_text=json.dumps(data if data is not None else dict(answers=[],questions=[])))


class RequestResend(unittest.TestCase):
    def setUp(self):
        client_pool.close_clients()
        self.settings=config.values(dict(gpt_model='m'))

    def tearDown(self):
        client_pool.close_clients()

    def test_policy_has_no_deadline_and_disables_both_sdk_and_application_resends(self):
        self.assertIsNone(config.REQUEST_TIMEOUT_SECONDS)
        self.assertEqual(config.REQUEST_ATTEMPTS,1)
        self.assertEqual(config.REQUEST_POLICY,dict(timeout=None,max_retries=0))
        with patch('openai.OpenAI') as factory:
            client_pool.get_client('policy-key')
        self.assertEqual(factory.call_args.kwargs,dict(api_key='policy-key',timeout=None,max_retries=0))

    def test_real_sdk_disables_connect_read_write_and_pool_timeouts_without_network(self):
        with patch('httpx.Client.send',side_effect=AssertionError('this test must never send a request')):
            sdk=client_pool.get_client('offline-sdk-test-key')
            self.assertIsNone(sdk.timeout)
            self.assertEqual(sdk.max_retries,0)
            expected=dict(connect=None,read=None,write=None,pool=None)
            self.assertEqual(sdk._client.timeout.as_dict(),expected)
            built=sdk._client.build_request('POST','https://offline.invalid/responses')
            self.assertEqual(built.extensions['timeout'],expected)

    def test_provider_timeout_reports_once_in_every_ai_path_without_resubmitting(self):
        calls=dict(adaptive=lambda:intake.request({}, {},'m','k',self.settings),
            interpret=lambda:client.interpret('진술',[],{},'m','k',self.settings),
            explanation=lambda:client.generate(summary_fixture(),'m','k',self.settings),
            photo=lambda:vision_client.observe('data:image/jpeg;base64,AAEC',{},'m','k',self.settings))
        for name,call in calls.items():
            with self.subTest(path=name),patch('openai.OpenAI') as factory:
                factory.return_value.responses.create.side_effect=[APITimeoutError('provider timeout'),completed()]
                raw,reason=call()
                self.assertIsNone(raw);self.assertEqual(reason,'TIMEOUT')
                self.assertEqual(factory.return_value.responses.create.call_count,1)
            client_pool.close_clients()

    def test_other_provider_errors_are_returned_once(self):
        with patch('openai.OpenAI') as factory:
            factory.return_value.responses.create.side_effect=[ServerBusy('503'),completed()]
            raw,reason=intake.request({}, {},'m','k',self.settings)
        self.assertIsNone(raw);self.assertEqual(reason,'API_ERROR')
        self.assertEqual(factory.return_value.responses.create.call_count,1)

    def test_incomplete_response_is_reported_once_without_a_second_request(self):
        with patch('openai.OpenAI') as factory:
            factory.return_value.responses.create.side_effect=[SimpleNamespace(status='incomplete',output_text=''),completed()]
            raw,reason=intake.request({}, {},'m','k',self.settings)
        self.assertIsNone(raw);self.assertEqual(reason,'INCOMPLETE_RESPONSE')
        self.assertEqual(factory.return_value.responses.create.call_count,1)

    def test_late_single_response_is_saved_while_other_service_requests_remain_responsive(self):
        entered=threading.Event();release=threading.Event();read_done=threading.Event()
        outcomes=[];errors=[];sends=[]
        with tempfile.TemporaryDirectory() as folder:
            ctx=create_service(str(Path(folder)/'loco.db'))
            survey=ctx.dispatch('create_survey',dict(draft=dict(survey_type='REGULAR',survey_date='2026-10-27')))
            task=ctx.dispatch('create_task',dict(survey_id=survey['survey_id'],draft=dict(task_name='지연 응답 시험')))
            analysis=ctx.dispatch('recalculate_judgments',dict(task_id=task['task_id']))
            settings=ctx.dispatch('get_settings',{});settings.update(gpt_enabled=True,gpt_model='m')
            ctx.dispatch('update_settings',dict(settings=settings))
            operation=ctx.prepare_dispatch('generate_ai_text',dict(analysis_id=analysis['analysis_id']))
            def create(**request):
                sends.append(request);entered.set()
                if not release.wait(5):raise AssertionError('test watchdog expired')
                summary=json.loads(request['input'][1]['content'])
                return completed(content_fixture(summary))
            def generate():
                try:outcomes.append(operation())
                except Exception as error:errors.append(error)
            def read():
                try:ctx.dispatch('get_task',dict(task_id=task['task_id']));read_done.set()
                except Exception as error:errors.append(error)
            with patch.dict(os.environ,dict(OPENAI_API_KEY='offline-delayed-test-key')),patch('openai.OpenAI') as factory:
                factory.return_value.responses.create.side_effect=create
                worker=threading.Thread(target=generate,daemon=True);reader=threading.Thread(target=read,daemon=True)
                worker.start()
                try:
                    self.assertTrue(entered.wait(2))
                    reader.start()
                    self.assertTrue(read_done.wait(1),'waiting for AI must not hold the service DB lock')
                    self.assertTrue(worker.is_alive(),'the original request must still be waiting')
                    self.assertEqual(len(sends),1)
                    self.assertFalse(outcomes,'do not manufacture a fallback while the same request is pending')
                finally:
                    release.set();worker.join(3)
                    if reader.ident is not None:reader.join(3)
                self.assertEqual(factory.return_value.responses.create.call_count,1)
            self.assertFalse(worker.is_alive());self.assertFalse(errors,errors)
            self.assertEqual(outcomes[0]['text']['result'],'GENERATED')
            self.assertTrue(outcomes[0]['source_current'])
            saved=ctx.analysis(analysis['analysis_id'])['ai']
            self.assertEqual(len(saved),1);self.assertEqual(saved[0]['connection']['response_id'],'resp_ok')
            self.assertIsNone(saved[0]['fallback_reason'])


if __name__=='__main__':unittest.main()
