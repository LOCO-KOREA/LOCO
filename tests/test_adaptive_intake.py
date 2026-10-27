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

    def test_form_has_all_work_features_and_only_active_conditions(self):
        work=[f for f in self.session['form_fields'] if f['destination']['type']=='work_type']
        self.assertEqual(len(work),9)
        lift=next(f for f in work if f['target']=='work_type.lift')
        saved=self.turn([answer(lift['target'],'YES')])
        self.assertTrue(any(f.get('gate')=='lift' for f in saved['form_fields']))
        no=self.turn([answer(lift['target'],'NO')])
        self.assertFalse(any(f.get('gate')=='lift' for f in no['form_fields']))
        self.assertIn(lift['identity'],[f['identity'] for f in no['form_fields']])
        self.assertFalse(no['complete'])

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

    def test_ai_can_ground_daily_total_in_two_stated_work_durations(self):
        text='손을 이미지대로 높이 드는 걸 한 2시간 하고 키보드 작업 6시간 해.'
        state=self.turn(text=text,raw=dict(answers=[
            model('card.arm_over.C3_UNION',number=120,quote='한 2시간'),
            model('card.keyboard.C1_KEYBOARD_FOCUSED',number=360,quote='키보드 작업 6시간'),
            model('daily_work_min',number=480,quote=text)],questions=[
                dict(target='daily_work_min',condition='default',text='하루 총시간?',reason='누락')]))
        self.assertEqual(state['task']['conditions']['daily_work_min'],480)
        self.assertNotIn('daily_work_min',{q['target'] for q in state['questions']})
        saved=next(f for f in state['facts'] if f['target']=='daily_work_min')
        self.assertEqual(saved['source'],'AI')
        self.assertEqual([t['minutes'] for t in saved['calculation']['terms']],[120,360])
        self.ctx=create_service(self.db)
        self.assertEqual(self.get()['task']['conditions']['daily_work_min'],480)

    def test_daily_sum_checks_arithmetic_and_accepts_compound_units(self):
        from ergo.intake.grounding import number_proof
        field=next(f for f in contract.fields() if f['target']=='daily_work_min')
        text='팔 드는 작업 1시간 30분 하고 키보드 작업 여섯시간 해요'
        proof=number_proof(field,450,text,context=text)
        self.assertEqual([t['minutes'] for t in proof['terms']],[90,360])
        self.assertEqual(proof['terms'][0]['quote'],'1시간 30분')
        self.assertIsNone(number_proof(field,360,text,context=text))
        self.assertIsNone(number_proof(field,480,text,context=text))

    def test_daily_sum_does_not_add_overlaps_breaks_ranges_or_other_periods(self):
        from ergo.intake.grounding import number_proof
        field=next(f for f in contract.fields() if f['target']=='daily_work_min')
        quote='팔 들기 2시간 하고 키보드 작업 6시간'
        for qualifier in ('두 작업은 동시에 해요','두 시간은 여섯 시간에 포함돼요','그중 두 시간은 쉬는 시간이야',
                          '주당 시간이에요','키보드는 매주 하는 시간이에요','하루 일부 작업이고 다른 작업이 더 있어요'):
            with self.subTest(qualifier=qualifier):
                self.assertIsNone(number_proof(field,480,quote,context=quote+' '+qualifier))
        for text in ('팔 들기 2~3시간 하고 키보드 6시간','휴식 2시간 하고 키보드 6시간',
                     '팔 들기 -2시간 하고 키보드 6시간','팔 들기 2시간(120분) 하고 키보드 6시간'):
            with self.subTest(text=text):self.assertIsNone(number_proof(field,480,text,context=text))
        exposure=next(f for f in contract.fields() if f['target']=='card.arm_over.C3_UNION')
        self.assertIsNone(number_proof(exposure,480,quote,context=quote))

    def test_daily_total_can_be_recovered_from_prior_text_without_overwriting_user(self):
        text='팔 드는 작업 2시간 하고 키보드 작업 6시간 해요'
        self.turn(text=text,raw=dict(answers=[],questions=[]))
        proposal=dict(answers=[model('daily_work_min',number=480,quote=text)],questions=[])
        state=self.turn(text='',raw=proposal)
        self.assertEqual(state['task']['conditions']['daily_work_min'],480)
        self.assertNotIn('daily_work_min',{q['target'] for q in state['questions']})
        self.turn([answer('daily_work_min',420)],plan=False)
        state=self.turn(text=text,raw=proposal)
        saved=next(f for f in state['facts'] if f['target']=='daily_work_min')
        self.assertEqual((saved['value'],saved['source']),(420,'USER'))

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
            state=self.ctx.dispatch('intake_turn',dict(task_id=self.identity,text='하루 전체 8시간입니다.',answers=[answer('daily_work_min',480)]))
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

    def test_natural_language_extraction_overlaps_requested_photo_observation(self):
        settings=self.ctx.dispatch('get_settings',{});settings.pop('gpt_key_present',None);settings.update(gpt_enabled=True,gpt_model='fixture');self.ctx.dispatch('update_settings',dict(settings=settings))
        model_started=threading.Event();photo_started=threading.Event()

        def request(ctx,task,session,preview):
            photo_started.set()
            self.assertTrue(model_started.wait(3),'text extraction must start while photo observation is in flight')
            return task,session,preview,session.get('photo_signature'),[]

        def respond(payload,*args):
            if payload['phase']=='EXTRACT_AND_PLAN':
                model_started.set()
                self.assertTrue(photo_started.wait(3),'photo observation must start while text extraction is in flight')
            return dict(answers=[],questions=[]),None

        with patch('ergo.service.intake.photo_vision.request_turn',side_effect=request), \
             patch('ergo.gpt.client.adaptive_intake',side_effect=respond):
            result=self.ctx.dispatch('intake_turn',dict(task_id=self.identity,text='하루 전체 8시간입니다.'))
        self.assertEqual(result['history'][0]['requests'][0]['phase'],'EXTRACT_AND_PLAN')

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

    def test_progress_counts_all_remaining_fields_not_just_the_single_question(self):
        state = self.get()
        progress = state['progress']
        self.assertEqual(progress['completed_count'], 0)
        self.assertEqual(progress['remaining_count'], state['remaining_count'])
        self.assertEqual(progress['total_count'], state['remaining_count'])
        self.assertGreater(progress['remaining_count'], len(state['questions']))
        self.assertEqual(progress['percent'], 0)
        self.assertTrue(progress['dynamic'])

    def test_progress_known_and_unknown_are_handled_without_claiming_calculation_complete(self):
        state = self.turn([answer('annual_work_days', 220), answer('one_off', None)], plan=False)
        progress = state['progress']
        self.assertEqual(progress['completed_count'], 2)
        self.assertEqual(progress['total_count'], progress['completed_count'] + state['remaining_count'])
        self.assertEqual(progress['percent'], progress['completed_count'] * 100 // progress['total_count'])
        self.assertFalse(state['complete'])
        self.ctx = create_service(self.db)
        self.assertEqual(self.get()['progress'], progress)

    def test_progress_uses_relevant_ai_and_saved_inputs(self):
        state = self.turn(text='1년에 220일', raw=dict(answers=[model('annual_work_days', number=220, quote='220일')], questions=[]))
        self.assertEqual(state['progress']['completed_count'], 1)
        other = self.ctx.dispatch('create_task', dict(survey_id=self.survey['survey_id'], draft=dict(task_name='저장된 작업', conditions=dict(annual_work_days=220, one_off='NO'))))
        restored = self.ctx.dispatch('intake_session', dict(task_id=other['task_id'], views={}))
        self.assertEqual(restored['progress']['completed_count'], 2)
        self.assertEqual({f['source'] for f in restored['facts'] if f['target'] in ('annual_work_days', 'one_off')}, {'SAVED'})

    def test_progress_does_not_count_inactive_conditions_or_unselected_photo_values(self):
        baseline = self.turn([answer('annual_work_days', 220), answer('one_off', 'NO'), answer('work_type.lift', 'NO')], plan=False)
        state = self.turn([answer('card.lift.load_mass_kg', 20, '이전 물건'), answer('manual.COMMON.trunk_base', 2), answer('view_RIGHT', 'SCREEN_LEFT')], plan=False)
        self.assertEqual(state['progress'], baseline['progress'])
        planned = self.turn([answer('planned_duration_months', 6)], plan=False)
        self.assertEqual(planned['remaining_count'], baseline['remaining_count'])
        self.assertLessEqual(planned['progress']['completed_count'], baseline['progress']['completed_count'])

    def test_progress_denominator_expands_for_new_work_and_condition_rows(self):
        baseline = self.turn([answer('annual_work_days', 220), answer('one_off', 'NO')], plan=False)
        lifted = self.turn([answer('work_type.lift', 'YES')], plan=False)
        self.assertGreater(lifted['progress']['total_count'], baseline['progress']['total_count'])
        first = self.turn([answer('card.lift.load_mass_kg', 20, '상자 A')], plan=False)
        second = self.turn([answer('card.lift.load_mass_kg', 30, '상자 B')], plan=False)
        self.assertGreater(second['progress']['total_count'], first['progress']['total_count'])
        self.assertGreater(second['remaining_count'], first['remaining_count'])
        self.assertLess(second['progress']['percent'], 100)

    def test_progress_can_finish_question_handling_with_unknowns_and_incomplete_results(self):
        state = self.get()
        state = self.turn([answer(q['target'], None, q['condition']) for q in self.candidates(state)], plan=False)
        self.assertEqual(state['remaining_count'], 0)
        self.assertFalse(state['questions'])
        self.assertEqual(state['progress']['percent'], 100)
        self.assertEqual(state['progress']['completed_count'], state['progress']['total_count'])
        self.assertFalse(state['complete'])
        self.assertTrue(any(j['computed_status'] == 'NEEDS_INPUT' for j in state['judgments']))

    def test_progress_clears_actual_inputs_for_relevance_probes_without_mutating_them(self):
        state = self.turn([answer('annual_work_days', 220), answer('one_off', 'NO'), answer('work_type.lift', 'YES'), answer('card.lift.load_mass_kg', 20)], plan=False)
        task = state['task']; session = task['conditions'][contract.SESSION_KEY]
        before = copy.deepcopy((task, session['facts']))
        assessment = planner.assess(task, session['facts'], session['views'])
        progress = planner.progress(task, session['facts'], session['views'], assessment['candidates'])
        # annual days, one-off, work type and the row weight are all relevant.
        # Keeping the saved values in the probe would lose the first two counts.
        self.assertEqual(progress['completed_count'], 4)
        self.assertEqual((task, session['facts']), before)

    def test_progress_counts_only_usable_photo_fields_and_keeps_review_items_pending(self):
        from ergo.engine.task_defaults import task_input
        views = dict(LEFT=1)
        known = facts.apply_answers({}, [answer('context', 'YES'), answer('view_LEFT', 'SCREEN_LEFT'), answer('load', 'UNLOADED'), answer('manual.COMMON.trunk_base', 2)])
        results = {}
        for state in ('KNOWN', 'ESTIMATED', 'CONFLICT'):
            probe = copy.deepcopy(known)
            probe[contract.key('manual.COMMON.trunk_base')]['state'] = state
            task = facts.project(task_input({}), probe, views, dict(views={}))
            before = copy.deepcopy((task, probe))
            assessment = planner.assess(task, probe, views)
            results[state] = planner.progress(task, probe, views, assessment['candidates'])
            self.assertEqual((task, probe), before)
        self.assertEqual(results['KNOWN']['completed_count'], 4)
        for state in ('ESTIMATED', 'CONFLICT'):
            self.assertEqual(results[state]['completed_count'], 3)
            self.assertEqual(results[state]['remaining_count'], results['KNOWN']['remaining_count'] + 1)
            self.assertEqual(results[state]['total_count'], results['KNOWN']['total_count'])

    def test_progress_keeps_known_work_features_when_other_features_are_grouped(self):
        state = self.turn([answer('work_type.lift', 'YES'), answer('work_type.keyboard', 'YES')], plan=False)
        self.assertEqual(state['progress']['completed_count'], 2)
        self.assertIn('other_work', {q['target'] for q in self.candidates(state)})

    def test_progress_photo_probe_follows_contract_primary_when_capture_order_changes(self):
        from ergo.engine.task_defaults import task_input
        views = dict(RIGHT=2, LEFT=1)
        values = facts.apply_answers({}, [answer('context', 'YES'), answer('manual.COMMON.trunk_base', 2)])
        task = facts.project(task_input({}), values, views, dict(views={}))
        task['capture']['slots'].reverse()
        # Additional analysis targets may be present in an older saved task.
        for slot in task['capture']['slots']: slot['analysis_target'] = True
        right = dict(task['manual'][0], slot_no=2, photo_id=2)
        task['manual'].append(right)
        field = next(f for f in contract.fields() if f['target'] == 'manual.COMMON.trunk_base')
        before = copy.deepcopy((task, values))
        cleared = planner._without_value(task, field, 'default', views)
        results = {slot['photo_id']: slot for slot in planner.calculate_reba(cleared, None)['slots']}
        self.assertIn('common.trunk_base', results[1]['missing_fields'])
        self.assertNotIn('common.trunk_base', results[2]['missing_fields'])
        self.assertEqual((task, values), before)

    def test_six_tables_and_previous_snapshots_remain_unchanged(self):
        analysis=self.ctx.dispatch('recalculate_judgments',dict(task_id=self.identity))
        before=copy.deepcopy(self.ctx.require('analysis',analysis['analysis_id']))
        self.turn([answer('daily_work_min',480)],plan=False)
        self.assertEqual(self.ctx.require('analysis',analysis['analysis_id']),before)
        with closing(sqlite3.connect(self.db)) as conn:
            tables=[r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")]
        self.assertEqual(len(tables),6)


class PairedAdaptiveIntake(unittest.TestCase):
    setUp = AdaptiveIntake.setUp
    get = AdaptiveIntake.get
    turn = AdaptiveIntake.turn
    candidates = AdaptiveIntake.candidates

    def photo_session(self, sides=('LEFT', 'RIGHT')):
        # Real SQLite/capture ownership; photo inference alone is an empty fixture.
        preview = dict(views={}, measured=[], front=[], signals={}, score=None, questions=[], diagnostics=[])
        inference = patch('ergo.service.intake.handle_quick_preview', return_value=preview)
        inference.start(); self.addCleanup(inference.stop)
        views = {}
        for side in sides:
            photo = Path(self.temp.name) / (side + '.fixture')
            photo.write_bytes(('synthetic photo ' + side).encode())
            views[side] = self.ctx.store('create_photo', self.identity, dict(file_path=str(photo),
                file_name=photo.name, width_px=1, height_px=1, consent='UNKNOWN', notes=[]))
        return self.ctx.dispatch('intake_session', dict(task_id=self.identity, views=views))

    def propose(self, target, answers=(), text='', model_answers=()):
        return self.turn(answers, text=text or '다음 정보를 확인해 주세요.', raw=dict(answers=list(model_answers), questions=[
            dict(target=target, condition='default', text='이쪽 정보를 확인해 주세요.', reason='아직 확인하지 않았어요.')]))

    def test_manual_sides_stay_editable_without_a_default_photo_question(self):
        self.photo_session()
        state = self.propose('manual.RIGHT.shoulder_raised', [answer('context', 'YES')])
        self.assertFalse(any(q['destination']['type']=='manual' for q in state['questions']))
        self.assertTrue(any(f['target']=='manual.RIGHT.shoulder_raised' and f['pending_input'] for f in state['form_fields']))
        session = state['task']['conditions'][contract.SESSION_KEY]
        self.assertTrue(all(set(suggestion) == {'target', 'condition', 'text', 'reason'} for suggestion in session['suggestions']))
        self.assertEqual(state['remaining_count'], len(self.candidates(state)))
        self.assertEqual(state['progress']['remaining_count'], state['remaining_count'])
        self.ctx = create_service(self.db)
        restored = self.get()
        self.assertFalse(any(q['destination']['type']=='manual' for q in restored['questions']))
        self.assertTrue(any(f['target']=='manual.RIGHT.shoulder_raised' for f in restored['form_fields']))

    def test_view_directions_pair_only_when_both_registered_views_are_unanswered(self):
        self.photo_session()
        state = self.propose('view_RIGHT')
        self.assertEqual(state['questions'][0]['target'],'view_RIGHT')
        self.assertEqual(state['questions'][0]['paired_question']['target'],'view_LEFT')
        saved = self.turn([answer('view_LEFT', 'SCREEN_LEFT'), answer('view_RIGHT', 'SCREEN_RIGHT')], plan=False)
        slots = {slot['camera_side']: slot for slot in saved['task']['capture']['slots']}
        self.assertEqual(slots['LEFT']['forward_direction'], 'SCREEN_LEFT')
        self.assertEqual(slots['RIGHT']['forward_direction'], 'SCREEN_RIGHT')
        self.assertFalse({'view_LEFT', 'view_RIGHT'} & {candidate['target'] for candidate in self.candidates(saved)})
        single = self.ctx.dispatch('intake_session', dict(task_id=self.identity, views=dict(LEFT=slots['LEFT']['photo_id'])))
        self.assertFalse(any(question['target'] in ('view_LEFT','view_RIGHT') for question in single['questions']))
        self.assertNotIn('view_RIGHT', {candidate['target'] for candidate in self.candidates(single)})

    def test_known_or_user_unknown_opposite_side_is_not_reasked(self):
        self.photo_session()
        for value in ('YES', None):
            with self.subTest(value=value):
                state = self.propose('manual.RIGHT.shoulder_raised', [answer('context', 'YES'), answer('manual.LEFT.shoulder_raised', value)])
                self.assertFalse(any(question['target'].startswith('manual.') for question in state['questions']))
                self.assertNotIn('manual.LEFT.shoulder_raised', {candidate['target'] for candidate in self.candidates(state)})
                fact = next(item for item in state['facts'] if item['target'] == 'manual.LEFT.shoulder_raised')
                self.assertEqual(fact['value'], value)
                self.assertEqual(fact['source'], 'USER')

    def test_conflict_does_not_pull_a_known_opposite_side_back_into_the_question(self):
        self.photo_session()
        self.propose('manual.LEFT.shoulder_raised', [answer('context', 'YES')], text='왼쪽 어깨는 아니오, 오른쪽 어깨는 예', model_answers=[
            model('manual.LEFT.shoulder_raised', text='NO', quote='왼쪽 어깨는 아니오'),
            model('manual.RIGHT.shoulder_raised', text='YES', quote='오른쪽 어깨는 예')])
        state = self.propose('manual.LEFT.shoulder_raised', text='왼쪽 어깨는 예', model_answers=[
            model('manual.LEFT.shoulder_raised', text='YES', quote='왼쪽 어깨는 예')])
        self.assertFalse(any(question['target'].startswith('manual.') for question in state['questions']))
        conflict = next(candidate for candidate in self.candidates(state) if candidate['target']=='manual.LEFT.shoulder_raised')
        self.assertEqual(conflict['priority'], 0)
        self.assertEqual(next(item for item in state['facts'] if item['target']=='manual.LEFT.shoulder_raised')['state'],'CONFLICT')
        self.assertNotIn('manual.RIGHT.shoulder_raised', {candidate['target'] for candidate in self.candidates(state)})

    def test_one_answer_turn_saves_two_independent_sides_and_resolves_two_fields(self):
        self.photo_session()
        state = self.propose('manual.LEFT.shoulder_raised', [answer('context', 'YES')])
        self.assertFalse(any(question['target'].startswith('manual.') for question in state['questions']))
        before = copy.deepcopy(state['progress'])
        messages = len(state['messages'])
        saved = self.turn([answer('manual.LEFT.shoulder_raised', 'YES'), answer('manual.RIGHT.shoulder_raised', 'NO')], raw=dict(answers=[], questions=[]))
        values = {(row['scope'], row['field']): row['value'] for row in saved['task']['manual']}
        self.assertEqual(values[('LEFT', 'shoulder_raised')], 'YES')
        self.assertEqual(values[('RIGHT', 'shoulder_raised')], 'NO')
        self.assertEqual(len(saved['messages']), messages + 1)
        self.assertEqual(saved['remaining_count'], state['remaining_count'] - 2)
        self.assertEqual(saved['progress']['completed_count'], before['completed_count'] + 2)
        self.assertEqual(saved['progress']['total_count'], before['total_count'])
        self.assertFalse({'manual.LEFT.shoulder_raised', 'manual.RIGHT.shoulder_raised'} & {candidate['target'] for candidate in self.candidates(saved)})
        self.ctx = create_service(self.db)
        restored = {item['target']: item['value'] for item in self.get()['facts']}
        self.assertEqual(restored['manual.LEFT.shoulder_raised'], 'YES')
        self.assertEqual(restored['manual.RIGHT.shoulder_raised'], 'NO')

    def test_unknown_answer_on_one_side_does_not_copy_the_other_sides_value(self):
        self.photo_session()
        self.propose('manual.LEFT.shoulder_raised', [answer('context', 'YES')])
        saved = self.turn([answer('manual.LEFT.shoulder_raised', None), answer('manual.RIGHT.shoulder_raised', 'NO')], plan=False)
        values = {item['target']: item for item in saved['facts']}
        self.assertIsNone(values['manual.LEFT.shoulder_raised']['value'])
        self.assertEqual(values['manual.LEFT.shoulder_raised']['state'], 'UNKNOWN')
        self.assertEqual(values['manual.LEFT.shoulder_raised']['source'], 'USER')
        self.assertEqual(values['manual.RIGHT.shoulder_raised']['value'], 'NO')
        self.assertIn('left.shoulder_raised', saved['reba']['slots'][0]['missing_fields'])
        self.assertNotIn('manual.LEFT.shoulder_raised', {candidate['target'] for candidate in self.candidates(saved)})

    def test_pair_helper_excludes_unrelated_fields_conditions_and_stale_primary_without_mutation(self):
        catalogue = {field['target']: field for field in contract.fields()}
        def candidate(target, condition='default'):
            return dict(catalogue[target], identity=contract.key(target, condition), condition=condition, text=target, reason='fixture')
        left = candidate('manual.LEFT.shoulder_raised')
        right = candidate('manual.RIGHT.shoulder_raised')
        original = copy.deepcopy((left, right))
        paired = planner.with_paired_question(left, [left, right])
        self.assertEqual(paired['paired_question']['identity'], right['identity'])
        self.assertEqual((left, right), original)
        right['paired_question'] = left
        left['paired_question'] = right
        paired = planner.with_paired_question(left, [left, right])
        self.assertNotIn('paired_question', paired['paired_question'])
        json.dumps(paired)  # Never return a nested pair/cycle from a reused question.
        for alternatives in ([left], [left, candidate('manual.RIGHT.wrist_base')],
                             [left, candidate('manual.RIGHT.shoulder_raised', 'different')], [right]):
            self.assertNotIn('paired_question', planner.with_paired_question(left, alternatives))
        common = candidate('manual.COMMON.neck_base')
        self.assertNotIn('paired_question', planner.with_paired_question(common, [common, right]))


class GroupedAdaptiveIntake(unittest.TestCase):
    setUp = AdaptiveIntake.setUp
    get = AdaptiveIntake.get
    turn = AdaptiveIntake.turn
    candidates = AdaptiveIntake.candidates
    photo_session = PairedAdaptiveIntake.photo_session
    propose = PairedAdaptiveIntake.propose

    def test_related_manual_inputs_remain_optional_editable_fields_without_default_questions(self):
        self.photo_session()
        self.turn([answer('context', 'YES')], plan=False)
        targets = ('manual.COMMON.trunk_base','manual.COMMON.legs_support','manual.COMMON.static_over_1min','manual.RIGHT.shoulder_raised')
        for target in targets:
            with self.subTest(target=target):
                state = self.propose(target)
                self.assertFalse(any(q['destination']['type']=='manual' for q in state['questions']))
                self.assertTrue(any(field['target']==target and field['pending_input'] for field in state['form_fields']))
                self.assertEqual(state['remaining_count'], len(self.candidates(state)))
                self.assertEqual(state['progress']['remaining_count'], state['remaining_count'])
        state = self.propose('manual.RIGHT.upper_arm_base')
        self.assertFalse(any(q['destination']['type']=='manual' for q in state['questions']))
        self.assertTrue(any(field['target']=='manual.RIGHT.upper_arm_base' and field['pending_input'] for field in state['form_fields']))

    def test_groups_exclude_known_and_user_unknown_but_keep_conflicts_recoverable(self):
        self.photo_session()
        self.turn([answer('context', 'YES'), answer('manual.COMMON.static_over_1min', None), answer('manual.COMMON.small_repeat_over_4min', 'NO')], plan=False)
        self.propose('manual.COMMON.shock_force', text='충격은 없어요.', model_answers=[model('manual.COMMON.shock_force', text='NO', quote='충격은 없어요')])
        state = self.propose('manual.COMMON.shock_force', text='충격이 있어요.', model_answers=[model('manual.COMMON.shock_force', text='YES', quote='충격이 있어요')])
        self.assertFalse(any(q['destination']['type']=='manual' for q in state['questions']))
        pending = {item['target']: item for item in state['facts']}
        self.assertEqual(pending['manual.COMMON.shock_force']['state'], 'CONFLICT')
        self.assertIsNone(pending['manual.COMMON.static_over_1min']['value'])

    def test_work_feature_group_uses_real_fields_including_virtual_other_work(self):
        initial = self.propose('work_type.keyboard')
        self.assertEqual(len(initial['questions'][0]['answer_questions']), 9)
        self.turn([answer('work_type.lift', 'YES'), answer('work_type.keyboard', 'NO'), answer('work_type.repeat', None)], plan=False)
        state = self.propose('other_work')
        question = state['questions'][0]
        self.assertEqual(question['target'], 'other_work')
        members = question['answer_questions']
        self.assertEqual(len(members), 6)
        self.assertTrue(all(member['destination']['type'] == 'work_type' for member in members))
        self.assertFalse({'other_work', 'work_type.lift', 'work_type.keyboard', 'work_type.repeat'} & {member['target'] for member in members})
        self.assertEqual(state['remaining_count'], len(self.candidates(state)))
        # Only submitted selections become facts; no synthetic other_work answer or unchecked NO values.
        saved = self.turn([answer(members[0]['target'], 'YES'), answer(members[1]['target'], 'NO')])
        stored = saved['task']['conditions'][contract.SESSION_KEY]['facts']
        self.assertEqual(stored[contract.key(members[0]['target'])]['value'], 'YES')
        self.assertEqual(stored[contract.key(members[1]['target'])]['value'], 'NO')
        self.assertNotIn(contract.key('other_work'), stored)
        self.assertTrue(all(contract.key(member['target']) not in stored for member in members[2:]))
        self.assertFalse(saved['complete'])

    def test_partial_group_save_preserves_blank_inputs_and_skips_external_ai(self):
        self.photo_session()
        self.turn([answer('context', 'YES')], plan=False)
        before = self.propose('manual.COMMON.shock_force')
        last_ai = copy.deepcopy(before['task']['conditions'][contract.SESSION_KEY]['last_ai'])
        with patch('ergo.gpt.client.adaptive_intake', side_effect=AssertionError('structured answers must not call AI')) as ai:
            saved = self.ctx.dispatch('intake_turn', dict(task_id=self.identity, answers=[answer('manual.COMMON.shock_force', 'YES')]))
        ai.assert_not_called()
        self.assertIsNone(saved['reason'])
        self.assertEqual(saved['ai']['status'], 'NOT_REQUESTED')
        session = saved['task']['conditions'][contract.SESSION_KEY]
        self.assertEqual(session['suggestions'], [])
        self.assertEqual(session['last_ai'], last_ai)
        self.assertEqual(saved['remaining_count'], before['remaining_count'] - 1)
        self.assertNotIn(contract.key('manual.COMMON.static_over_1min'), session['facts'])
        self.assertIn('common.static_over_1min', saved['reba']['slots'][0]['missing_fields'])
        self.assertFalse(saved['complete'])
        self.assertNotIn('manual.COMMON.shock_force', {candidate['target'] for candidate in self.candidates(saved)})

    def test_local_save_after_ai_error_clears_current_error_but_preserves_history_and_retry(self):
        settings = self.ctx.dispatch('get_settings', {}); settings.pop('gpt_key_present', None)
        settings.update(gpt_enabled=True, gpt_model='fixture'); self.ctx.dispatch('update_settings', dict(settings=settings))
        with patch('ergo.gpt.client.adaptive_intake', return_value=(None, 'TIMEOUT')):
            failed = self.ctx.dispatch('intake_turn', dict(task_id=self.identity, text='하루 전체 8시간입니다.'))
        old_ai = copy.deepcopy(failed['task']['conditions'][contract.SESSION_KEY]['last_ai'])
        self.assertEqual(failed['ai']['status'], 'ERROR')
        with patch('ergo.gpt.client.adaptive_intake', side_effect=AssertionError('local save must not use AI')) as ai:
            saved = self.ctx.dispatch('intake_turn', dict(task_id=self.identity, answers=[answer('one_off', 'NO')]))
        ai.assert_not_called()
        self.assertIsNone(saved['reason'])
        self.assertEqual(saved['ai'], dict(status='NOT_REQUESTED', model=None, reason=None))
        self.assertEqual(saved['task']['conditions'][contract.SESSION_KEY]['last_ai'], old_ai)
        self.ctx = create_service(self.db)
        self.assertEqual(self.get()['ai']['status'], 'NOT_REQUESTED')
        # A blank retry still sends saved text to the model and restores actual connection reporting.
        raw = dict(answers=[model('daily_work_min', number=480, quote='8시간')], questions=[dict(target='annual_work_days', condition='default', text='연간 일수?', reason='누락')])
        with patch('ergo.gpt.client.adaptive_intake', return_value=(raw, None)) as ai:
            retried = self.ctx.dispatch('intake_turn', dict(task_id=self.identity, text=''))
        self.assertEqual(ai.call_count, 1)
        self.assertIn('하루 전체 8시간입니다.', ai.call_args.args[0]['prior_user_text'])
        self.assertEqual(retried['task']['conditions']['daily_work_min'], 480)
        self.assertEqual(retried['ai']['status'], 'CONNECTED')
        self.assertNotIn('local_answers_only', retried['task']['conditions'][contract.SESSION_KEY])

    def test_text_with_structured_answers_still_uses_ai_and_respects_each_explicit_value(self):
        self.photo_session()
        self.turn([answer('context', 'YES')], plan=False)
        settings = self.ctx.dispatch('get_settings', {}); settings.pop('gpt_key_present', None)
        settings.update(gpt_enabled=True, gpt_model='fixture'); self.ctx.dispatch('update_settings', dict(settings=settings))
        raw = dict(answers=[model('manual.LEFT.shoulder_raised', text='NO', quote='양쪽 어깨를 올리지 않아요')], questions=[dict(target='annual_work_days', condition='default', text='연간 일수?', reason='누락')])
        with patch('ergo.gpt.client.adaptive_intake', return_value=(raw, None)) as ai:
            saved = self.ctx.dispatch('intake_turn', dict(task_id=self.identity, text='양쪽 어깨를 올리지 않아요.', answers=[answer('manual.LEFT.shoulder_raised', 'YES'), answer('manual.RIGHT.shoulder_raised', 'NO')]))
        ai.assert_called()
        stored = saved['task']['conditions'][contract.SESSION_KEY]['facts']
        self.assertEqual(stored[contract.key('manual.LEFT.shoulder_raised')]['value'], 'YES')
        self.assertEqual(stored[contract.key('manual.RIGHT.shoulder_raised')]['value'], 'NO')
        self.assertEqual(saved['ai']['status'], 'CONNECTED')
        self.assertIn('USER_VALUE_KEPT', {item['reason'] for item in saved['dropped']})

    def test_group_helper_keeps_conditions_separate_without_mutating_candidates(self):
        catalogue = {field['target']: field for field in contract.fields()}
        def candidate(target, condition='default'):
            return dict(catalogue[target], condition=condition, identity=contract.key(target, condition), text=target, reason='fixture')
        primary = candidate('manual.COMMON.trunk_base')
        same = candidate('manual.COMMON.neck_base')
        different = candidate('manual.COMMON.trunk_twisted', 'other condition')
        unrelated = candidate('manual.LEFT.upper_arm_base')
        candidates = [primary, same, different, unrelated]
        before = copy.deepcopy(candidates)
        question = planner.with_answer_questions(primary, candidates, {})
        self.assertEqual({member['identity'] for member in question['answer_questions']}, {primary['identity'], same['identity']})
        self.assertEqual(candidates, before)
        known = facts.apply_answers({}, [answer(same['target'], None)])
        self.assertNotIn('answer_questions', planner.with_answer_questions(primary, candidates, known))
        self.assertNotIn('answer_questions', planner.with_answer_questions(primary, [different, unrelated], {}))

    def test_grouped_panels_reduce_screen_rounds_while_retaining_all_43_fields(self):
        from ergo.engine.task_defaults import task_input
        known = facts.apply_answers({}, [answer('context', 'YES')])
        views = dict(LEFT=1, RIGHT=2)
        task = facts.project(task_input({}), known, views, {})
        candidates = planner.assess(task, known, views)['candidates']
        self.assertEqual(len(candidates), 43)
        def screens(grouped):
            pending = list(candidates); handled = set(); count = 0
            while pending:
                question = planner.with_paired_question(planner.choose(pending)[0], pending)
                if grouped: question = planner.with_answer_questions(question, pending, known)
                members = question.get('answer_questions') or [question] + ([question['paired_question']] if question.get('paired_question') else [])
                identities = {member['identity'] for member in members}
                self.assertFalse(handled & identities)
                handled.update(identities)
                pending = [candidate for candidate in pending if candidate['identity'] not in identities]
                count += 1
            self.assertEqual(handled, {candidate['identity'] for candidate in candidates})
            return count
        self.assertEqual(screens(False), 34)
        self.assertEqual(screens(True), 13)


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
        automatic=[f for f in state['facts'] if f['source'] in ('POSE','MOVENET') and f['state'] in ('KNOWN','ESTIMATED')]
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
