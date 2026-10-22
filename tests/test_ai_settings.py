"""Configuration must survive storage and reach all three actual SDK boundaries."""
import json
import os
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from ergo.gpt import client, intake
from ergo import ai_config as config
from ergo.service.application import create_service
from tests.test_v2_gpt import summary_fixture, content_fixture


class AiSettings(unittest.TestCase):
    def test_each_sdk_path_uses_the_same_selected_model_effort_timeout_and_tokens(self):
        selected=config.values(dict(gpt_model='custom-provider-model',gpt_reasoning_effort='high',
                                    gpt_timeout_seconds=43.5,gpt_max_output_tokens=12567))
        captured=[]
        def create(**kwargs):
            captured.append(kwargs)
            name=kwargs['text']['format']['name']
            data=content_fixture(summary_fixture()) if name=='loco_explanation' else dict(answers=[],questions=[])
            return SimpleNamespace(id='resp_verified',status='completed',model=selected['gpt_model'],
                                   reasoning=SimpleNamespace(effort='high'),output_text=json.dumps(data))
        with patch('openai.OpenAI') as factory:
            factory.return_value.responses.create.side_effect=create
            self.assertIsNone(client.interpret('진술',[],{},selected['gpt_model'],'test-key',selected)[1])
            raw,reason=intake.request({}, {},selected['gpt_model'],'test-key',selected)
            self.assertIsNone(reason);self.assertEqual(raw['_connection']['reasoning_effort'],'high')
            raw,reason=client.generate(summary_fixture(),selected['gpt_model'],'test-key',selected)
            self.assertIsNone(reason);self.assertEqual(raw['_connection']['response_id'],'resp_verified')
        self.assertEqual(factory.call_count,3)
        for call in factory.call_args_list:
            self.assertEqual(call.kwargs,dict(api_key='test-key',timeout=43.5,max_retries=0))
        self.assertEqual(len(captured),3)
        for request in captured:
            self.assertEqual(request['model'],'custom-provider-model')
            self.assertEqual(request['reasoning'],dict(effort='high'))
            self.assertEqual(request['max_output_tokens'],12567)

    def test_environment_defaults_and_saved_override_are_distinct(self):
        with patch.dict(os.environ,dict(LOCO_AI_MODEL='env-model',LOCO_AI_REASONING_EFFORT='low',
                                      LOCO_AI_TIMEOUT_SECONDS='72',LOCO_AI_MAX_OUTPUT_TOKENS='18000')):
            default=config.public_contract()['defaults']
            self.assertEqual(default['gpt_model'],'env-model')
            self.assertEqual(default['gpt_timeout_seconds'],72)
            saved=config.values(dict(gpt_model='saved-model',gpt_reasoning_effort='xhigh'))
            self.assertEqual(saved['gpt_model'],'saved-model');self.assertEqual(saved['gpt_reasoning_effort'],'xhigh')
            self.assertEqual(saved['gpt_max_output_tokens'],18000)

    def test_omitting_reasoning_is_explicit_and_does_not_substitute_a_model(self):
        _,options=config.request_options('existing-model',dict(gpt_reasoning_effort=''))
        self.assertEqual(options['model'],'existing-model');self.assertNotIn('reasoning',options)

    def test_invalid_configuration_is_rejected_instead_of_silently_defaulted(self):
        for setting in [dict(gpt_reasoning_effort='extra-high'),dict(gpt_timeout_seconds=0),
                        dict(gpt_timeout_seconds=float('nan')),dict(gpt_max_output_tokens=True),
                        dict(gpt_max_output_tokens=1.5),dict(gpt_model=None),dict(gpt_enabled='YES')]:
            with self.subTest(setting=setting),self.assertRaises(ValueError): config.values(setting)

    def test_all_fields_persist_but_read_only_contract_and_key_presence_do_not(self):
        with tempfile.TemporaryDirectory() as folder:
            db=str(Path(folder)/'loco.db');ctx=create_service(db)
            selected=ctx.dispatch('get_settings',{})
            selected.update(gpt_enabled=True,gpt_model='saved-model',gpt_reasoning_effort='max',
                            gpt_timeout_seconds=91,gpt_max_output_tokens=19456)
            ctx.dispatch('update_settings',dict(settings=selected))
            restored=create_service(db).dispatch('get_settings',{})
            self.assertEqual(config.values(restored),config.values(selected))
            raw=ctx.store('get_settings')
            self.assertNotIn('gpt_contract',raw);self.assertNotIn('gpt_key_present',raw)

    def test_older_settings_read_with_new_fields_without_rewriting_the_record(self):
        with tempfile.TemporaryDirectory() as folder:
            ctx=create_service(str(Path(folder)/'loco.db'))
            selected=ctx.dispatch('get_settings',{})
            # Store an old JSON row directly to represent a pre-upgrade installation.
            import sqlite3
            with closing(sqlite3.connect(ctx.db_path)) as db:
                old={k:selected[k] for k in ('analysis','gpt_enabled','gpt_model','ui')}
                old['gpt_model']='previous-explicit-model'
                db.execute('UPDATE APP_SETTINGS SET settings_json=?',(json.dumps(old),))
                db.commit()
            restored=ctx.dispatch('get_settings',{})
            self.assertEqual(restored['gpt_model'],'previous-explicit-model')
            self.assertEqual(restored['gpt_reasoning_effort'],config.defaults()['gpt_reasoning_effort'])
            self.assertNotIn('gpt_reasoning_effort',ctx.store('get_settings'))

    def test_changing_config_cannot_reuse_a_previous_connection_badge(self):
        with tempfile.TemporaryDirectory() as folder:
            ctx=create_service(str(Path(folder)/'loco.db'))
            selected=ctx.dispatch('get_settings',{});selected['gpt_enabled']=True
            ctx.dispatch('update_settings',dict(settings=selected))
            survey=ctx.dispatch('create_survey',dict(draft=dict(survey_type='REGULAR',survey_date='2026-10-22')))
            task=ctx.dispatch('create_task',dict(survey_id=survey['survey_id'],draft=dict(task_name='합성 작업')))
            raw=dict(answers=[],questions=[],_connection=dict(model=selected['gpt_model'],reasoning_effort='xhigh',response_id='resp_old'))
            with patch('ergo.gpt.client.adaptive_intake',return_value=(raw,None)):
                result=ctx.dispatch('intake_turn',dict(task_id=task['task_id']))
            self.assertEqual(result['ai']['status'],'CONNECTED')
            selected['gpt_reasoning_effort']='low';ctx.dispatch('update_settings',dict(settings=selected))
            self.assertEqual(ctx.dispatch('intake_session',dict(task_id=task['task_id']))['ai']['status'],'NOT_REQUESTED')


if __name__=='__main__': unittest.main()
