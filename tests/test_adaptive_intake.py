"""Independent regressions for duplicate questions, ownership, conditions and persistence."""
import copy
import json
import sqlite3
import tempfile
import threading
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch
from ergo.service.application import create_service
from ergo.intake import contract, facts, planner


def answer(target,value,condition='default'):
    return dict(target=target,value=value,condition=condition)


def model(target,*,number=None,text=None,quote='',condition='default'):
    return dict(target=target,number=number,text=text,quote=quote,condition=condition)


class AdaptiveIntake(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.db=str(Path(self.temp.name)/'실제 입력.db'); self.ctx=create_service(self.db)
        self.survey=self.ctx.dispatch('create_survey',dict(draft=dict(survey_type='REGULAR',survey_date='2026-10-22',title='합성 작업')))
        self.task=self.ctx.dispatch('create_task',dict(survey_id=self.survey['survey_id'],draft=dict(task_name='사진 분석 작업')))
        self.identity=self.task['task_id']
        self.session=self.ctx.dispatch('intake_session',dict(task_id=self.identity,views={}))

    def get(self): return self.ctx.dispatch('intake_session',dict(task_id=self.identity))
    def turn(self,answers=(),text='',raw=None,**extra):
        if raw is not None:
            setting=self.ctx.dispatch('get_settings',{}); setting.pop('gpt_key_present',None)
            setting.update(gpt_enabled=True,gpt_model='fixture'); self.ctx.dispatch('update_settings',dict(settings=setting))
        with patch('ergo.gpt.client.adaptive_intake',return_value=(raw,None)):
            return self.ctx.dispatch('intake_turn',dict(task_id=self.identity,text=text,answers=list(answers),**extra))

    def candidates(self,state):
        return planner.assess(state['task'],state['task']['conditions'][contract.SESSION_KEY]['facts'],state['task']['conditions'][contract.SESSION_KEY]['views'])['candidates']

    def test_contract_is_shared_strict_unique_and_has_no_judgment_targets(self):
        catalogue=contract.fields(); targets={f['target'] for f in catalogue}
        self.assertEqual(len(catalogue),len(targets)); self.assertNotIn('risk',targets)
        self.assertIn('manual.LEFT.coupling',targets); self.assertIn('manual.COMMON.static_over_1min',targets)
        schema=contract.response_schema(); self.assertFalse(schema['additionalProperties'])
        self.assertEqual(set(schema['required']),set(schema['properties']))

    def test_reads_do_not_change_revisions_and_restarting_restores_facts(self):
        first=self.get(); second=self.get(); self.assertEqual(first['task']['input_revision'],second['task']['input_revision'])
        saved=self.turn([answer('daily_work_min',480),answer('one_off','NO')],plan=False)
        self.ctx=create_service(self.db); restored=self.get()
        self.assertEqual(restored['task']['conditions']['daily_work_min'],480)
        self.assertEqual(restored['task']['input_revision'],saved['task']['input_revision'])
        self.assertNotIn('daily_work_min',{c['target'] for c in self.candidates(restored)})

    def test_partial_lifting_card_never_reasks_the_known_weight_and_count(self):
        state=self.turn(text='20kg 상자를 하루 30번 들어요',raw=dict(answers=[
            model('card.lift.load_mass_kg',number=20,quote='20kg'),model('card.lift.lift_count_day',number=30,quote='하루 30번')],questions=[
            dict(target='card.lift.load_mass_kg',condition='default',text='무게가 몇 kg인가요?',reason='다시 확인')]))
        targets={c['target'] for c in self.candidates(state)}
        self.assertNotIn('card.lift.load_mass_kg',targets); self.assertNotIn('card.lift.lift_count_day',targets)
        self.assertNotIn('card.lift.load_mass_kg',{q['target'] for q in state['questions']})
        self.assertTrue(any(t.startswith('card.lift.') for t in targets))

    def test_absent_work_types_remain_unknown_not_false(self):
        state=self.turn(text='20kg 상자를 들어요',raw=dict(answers=[model('card.lift.load_mass_kg',number=20,quote='20kg')],questions=[]))
        criteria=state['task']['legal']['criteria']
        self.assertEqual(criteria[0]['condition_present'],'UNKNOWN')
        self.assertEqual(criteria[7]['condition_present'],'YES')

    def test_other_work_is_explicit_and_does_not_claim_row_completeness(self):
        state=self.turn([answer('work_type.lift','YES'),answer('other_work','NO')],plan=False)
        self.assertEqual(state['task']['legal']['criteria'][0]['condition_present'],'NO')
        self.assertEqual(state['task']['legal']['criteria'][7]['rows_complete'],'UNKNOWN')

    def test_unknown_is_saved_not_reasked_and_does_not_become_zero(self):
        state=self.turn([answer('daily_work_min',None)],plan=False)
        self.assertIsNone(state['task']['conditions']['daily_work_min'])
        self.assertNotIn('daily_work_min',{c['target'] for c in self.candidates(state)})
        self.assertTrue(any(j['computed_status']=='NEEDS_INPUT' for j in state['judgments']))

    def test_zero_is_a_real_value_and_user_edit_wins_over_ai(self):
        self.turn([answer('card.lift.lift_count_day',0)],plan=False)
        state=self.turn(text='하루 30번',raw=dict(answers=[model('card.lift.lift_count_day',number=30,quote='30번')],questions=[]))
        value=next(f for f in state['facts'] if f['target']=='card.lift.lift_count_day')
        self.assertEqual(value['value'],0); self.assertEqual(value['source'],'USER')
        self.assertIn('USER_VALUE_KEPT',{d['reason'] for d in state['dropped']})

    def test_conflicting_ai_values_keep_the_saved_value_and_request_resolution(self):
        self.turn(text='20kg',raw=dict(answers=[model('card.lift.load_mass_kg',number=20,quote='20kg')],questions=[]))
        state=self.turn(text='30kg',raw=dict(answers=[model('card.lift.load_mass_kg',number=30,quote='30kg')],questions=[]))
        value=next(f for f in state['facts'] if f['target']=='card.lift.load_mass_kg')
        self.assertEqual((value['value'],value['state'],value['conflict']['value']),(20,'CONFLICT',30))
        self.assertEqual(state['questions'][0]['target'],'card.lift.load_mass_kg')

    def test_different_conditions_keep_their_own_weight_and_count(self):
        text='5kg 99번, 30kg 1번이 전부예요'
        raw=dict(answers=[model('card.lift.load_mass_kg',number=5,quote='5kg',condition='가벼운 상자'),model('card.lift.lift_count_day',number=99,quote='99번',condition='가벼운 상자'),
            model('card.lift.load_mass_kg',number=30,quote='30kg',condition='무거운 상자'),model('card.lift.lift_count_day',number=1,quote='1번',condition='무거운 상자'),
            model('complete.lift',text='YES',quote='전부예요')],questions=[])
        state=self.turn(text=text,raw=raw)
        rows=state['task']['legal']['criteria'][7]['rows']
        self.assertEqual({(r['load_mass_kg'],r['lift_count_day']) for r in rows},{(5,99),(30,1)})
        self.assertEqual(state['judgments'][7]['computed_status'],'NOT_APPLICABLE')

    def test_wrong_unit_and_fabricated_number_are_dropped(self):
        state=self.turn(text='20kg를 하루 30번',raw=dict(answers=[model('daily_work_min',number=30,quote='하루 30번'),model('card.lift.load_mass_kg',number=25,quote='20kg')],questions=[]))
        self.assertEqual({d['reason'] for d in state['dropped']},{'UNIT_OR_NUMBER_NOT_GROUNDED'})
        self.assertIsNone(state['task']['conditions']['daily_work_min'])

    def test_daily_count_cannot_turn_into_a_per_minute_rate(self):
        state=self.turn(text='하루 30번 들어요',raw=dict(answers=[model('card.lift.lift_rate_min',number=30,quote='하루 30번')],questions=[]))
        self.assertNotIn('card.lift.lift_rate_min',{f['target'] for f in state['facts']})
        self.assertIn('UNIT_OR_NUMBER_NOT_GROUNDED',{d['reason'] for d in state['dropped']})
        self.assertTrue(facts.number_grounded(1,'1분에 1번씩 하루 30분','회/분'))
        self.assertFalse(facts.number_grounded(1,'2분에 1번씩','회/분'))

    def test_label_answers_and_global_scope_are_normalized_by_the_catalogue(self):
        state=self.turn(text='일회성은 아니오, 하루 전체 8시간',raw=dict(answers=[
            model('one_off',text='아니오',quote='일회성은 아니오',condition='상자'),
            model('daily_work_min',number=480,quote='하루 전체 8시간',condition='상자')],questions=[]))
        self.assertEqual(state['task']['conditions']['one_off'],'NO')
        self.assertNotIn('one_off',{q['target'] for q in state['questions']})
        self.assertNotIn('daily_work_min',{q['target'] for q in state['questions']})

    def test_natural_unknown_is_recorded_and_not_reasked(self):
        state=self.turn(text='작업시간은 모르겠어요',raw=dict(answers=[model('daily_work_min',text='UNKNOWN',quote='작업시간은 모르겠어요')],questions=[]))
        self.assertNotIn('daily_work_min',{c['target'] for c in self.candidates(state)})
        self.assertIsNone(state['task']['conditions']['daily_work_min'])

    def test_integer_days_are_normalized_and_generic_other_work_does_not_exclude_features(self):
        state=self.turn(text='연 220일이고 다른 작업은 없어요',raw=dict(answers=[
            model('annual_work_days',number=220.0,quote='연 220일'),model('other_work',text='NO',quote='다른 작업은 없어요')],questions=[]))
        self.assertIs(type(state['task']['conditions']['annual_work_days']),int)
        self.assertTrue(all(c['condition_present']=='UNKNOWN' for c in state['task']['legal']['criteria']))

    def test_prior_statement_can_fill_a_missed_fact_without_replacing_current_values(self):
        self.turn(text='하루 전체 8시간, 연 220일',raw=dict(answers=[],questions=[]))
        state=self.turn(text='계속해 주세요',raw=dict(answers=[model('daily_work_min',number=480,quote='하루 전체 8시간')],questions=[]))
        self.assertEqual(state['task']['conditions']['daily_work_min'],480)
        self.turn([answer('daily_work_min',360)],plan=False)
        state=self.turn(text='다음 질문',raw=dict(answers=[model('daily_work_min',number=480,quote='하루 전체 8시간')],questions=[]))
        self.assertEqual(state['task']['conditions']['daily_work_min'],360)
        self.assertIn('STALE_QUOTE',{d['reason'] for d in state['dropped']})

    def test_backend_rejects_out_of_range_direct_values_before_saving(self):
        before=self.get()['task']
        with self.assertRaises(ValueError): self.turn([answer('daily_work_min',1441)],plan=False)
        self.assertEqual(self.get()['task']['input_revision'],before['input_revision'])

    def test_external_editor_values_are_not_overwritten_by_session_replay(self):
        self.turn([answer('daily_work_min',480)],plan=False)
        task=self.ctx.require('task',self.identity); task['conditions']['daily_work_min']=360; self.ctx.save_task(task)
        restored=self.get(); self.assertEqual(restored['task']['conditions']['daily_work_min'],360)
        self.assertEqual(next(f for f in restored['facts'] if f['target']=='daily_work_min')['source'],'USER')

    def test_ai_failure_keeps_direct_answers_and_provides_editable_questions(self):
        settings=self.ctx.dispatch('get_settings',{}); settings.pop('gpt_key_present',None); settings.update(gpt_enabled=True,gpt_model='fixture'); self.ctx.dispatch('update_settings',dict(settings=settings))
        with patch('ergo.gpt.client.adaptive_intake',return_value=(None,'TIMEOUT')):
            state=self.ctx.dispatch('intake_turn',dict(task_id=self.identity,answers=[answer('daily_work_min',480)]))
        self.assertEqual(state['reason'],'TIMEOUT'); self.assertEqual(state['task']['conditions']['daily_work_min'],480)
        self.assertTrue(state['questions'])
        self.assertEqual(state['ai']['status'],'ERROR')
        self.assertEqual(self.get()['ai']['reason'],'TIMEOUT')

    def test_connection_requires_an_actual_model_response_and_survives_restart(self):
        self.assertEqual(self.get()['ai']['status'],'NOT_REQUESTED')
        state=self.turn(text='하루 8시간',raw=dict(answers=[model('daily_work_min',number=480,quote='8시간')],
            questions=[dict(target='annual_work_days',condition='default',text='1년에 며칠 일하나요?',reason='하루 정보만 알아요.')],
            _connection=dict(response_id='resp_verified')))
        self.assertEqual(state['ai']['status'],'CONNECTED');self.assertEqual(state['ai']['response_id'],'resp_verified')
        self.assertEqual(len(state['questions']),1)
        self.ctx=create_service(self.db)
        self.assertEqual(self.get()['ai']['response_id'],'resp_verified')

    def test_ai_plans_from_the_remaining_gaps_after_extraction_is_saved(self):
        settings=self.ctx.dispatch('get_settings',{});settings.pop('gpt_key_present',None);settings.update(gpt_enabled=True,gpt_model='fixture');self.ctx.dispatch('update_settings',dict(settings=settings))
        phases=[]
        def respond(payload,*args):
            phases.append(payload['phase'])
            if payload['phase']=='EXTRACT_AND_PLAN':
                return dict(answers=[model('daily_work_min',number=480,quote='8시간')],questions=[dict(target='daily_work_min',condition='default',text='작업시간?',reason='중복')]),None
            self.assertEqual(self.ctx.require('task',self.identity)['conditions']['daily_work_min'],480)
            self.assertNotIn('daily_work_min',{q['target'] for q in payload['missing']})
            return dict(answers=[],questions=[dict(target='annual_work_days',condition='default',text='1년에 며칠 작업하나요?',reason='연간 일수만 몰라요.')]),None
        with patch('ergo.gpt.client.adaptive_intake',side_effect=respond):
            state=self.ctx.dispatch('intake_turn',dict(task_id=self.identity,text='하루 8시간'))
        self.assertEqual(phases,['EXTRACT_AND_PLAN','FOLLOWUP'])
        self.assertEqual(state['questions'][0]['text'],'1년에 며칠 작업하나요?')

    def test_empty_retry_keeps_the_last_saved_statement_in_ai_context(self):
        self.turn(text='하루 전체 8시간',raw=dict(answers=[],questions=[]))
        seen=[]
        def respond(payload,*args):
            seen.append(payload['prior_user_text'])
            return dict(answers=[model('daily_work_min',number=480,quote='8시간')],questions=[dict(target='annual_work_days',condition='default',text='연간 작업일수?',reason='누락')]),None
        with patch('ergo.gpt.client.adaptive_intake',side_effect=respond):
            state=self.ctx.dispatch('intake_turn',dict(task_id=self.identity,text=''))
        self.assertIn('하루 전체 8시간',seen[0]);self.assertEqual(state['task']['conditions']['daily_work_min'],480)

    def test_late_ai_response_cannot_overwrite_another_turn(self):
        settings=self.ctx.dispatch('get_settings',{}); settings.pop('gpt_key_present',None); settings.update(gpt_enabled=True,gpt_model='fixture'); self.ctx.dispatch('update_settings',dict(settings=settings))
        entered=threading.Event(); release=threading.Event(); result=[]
        def slow(*args):
            entered.set(); release.wait(10)
            return dict(answers=[model('daily_work_min',number=480,quote='8시간')],questions=[]),None
        with patch('ergo.gpt.client.adaptive_intake',side_effect=slow):
            thread=threading.Thread(target=lambda:result.append(self.ctx.dispatch('intake_turn',dict(task_id=self.identity,text='하루 8시간'))))
            thread.start(); self.assertTrue(entered.wait(5))
            self.ctx.dispatch('intake_turn',dict(task_id=self.identity,answers=[answer('daily_work_min',360)],plan=False))
            release.set(); thread.join(10)
        self.assertFalse(thread.is_alive()); self.assertEqual(self.get()['task']['conditions']['daily_work_min'],360)
        self.assertEqual(result[0]['reason'],'INPUT_CHANGED')

    def test_six_tables_and_previous_snapshots_remain_unchanged(self):
        analysis=self.ctx.dispatch('recalculate_judgments',dict(task_id=self.identity))
        before=copy.deepcopy(self.ctx.require('analysis',analysis['analysis_id']))
        self.turn([answer('daily_work_min',480)],plan=False)
        self.assertEqual(self.ctx.require('analysis',analysis['analysis_id']),before)
        with closing(sqlite3.connect(self.db)) as conn:
            tables=[r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")]
        self.assertEqual(len(tables),6)


class PhotoIntake(unittest.TestCase):
    turn=AdaptiveIntake.turn
    candidates=AdaptiveIntake.candidates
    def setUp(self):
        AdaptiveIntake.setUp(self)
        self.photo=Path(__file__).resolve().parents[1]/'.local/fixtures/tensorflow-movenet-example.jpeg'

    def test_photo_measurements_auto_save_without_inventing_context_or_load(self):
        if not self.photo.is_file(): self.skipTest('public photo fixture required')
        imported=self.ctx.dispatch('import_photos',dict(task_id=self.identity,file_paths=[str(self.photo)]))
        identity=imported['added'][0]['photo_id']
        state=self.ctx.dispatch('intake_session',dict(task_id=self.identity,views=dict(RIGHT=identity)))
        automatic=[f for f in state['facts'] if f['source']=='MOVENET' and f['state'] in ('KNOWN','ESTIMATED')]
        self.assertTrue(automatic)
        self.assertNotIn('context',{f['target'] for f in automatic}); self.assertNotIn('load_kg',{f['target'] for f in automatic})
        self.assertTrue(any(f['target'].startswith('manual.') for f in automatic))
        state=self.turn([answer('context','YES')],plan=False)
        for item in automatic:
            if item['state']=='ESTIMATED':
                state=self.turn([answer(item['target'],item['value'])],plan=False)
        self.assertTrue(state['task']['manual'])
        next_targets={c['target'] for c in self.candidates(state)}
        self.assertFalse({f['target'] for f in automatic} & next_targets)


if __name__=='__main__': unittest.main()
