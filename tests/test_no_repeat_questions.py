"""Independent catalogue-wide assertions, plus the actual reported 20kg journey."""
import copy
import unittest
from itertools import product
from ergo.engine.task_defaults import task_input
from ergo.intake import contract, facts, planner
from ergo.intake.photo_load import photo_load
import test_adaptive_intake as fixtures
from test_adaptive_intake import answer, model


class QuestionCatalogue(unittest.TestCase):
    def test_weight_connection_override_and_photo_combinations(self):
        # 4 weight sets x 3 connection states x 4 explicit answers x 3 photo sets.
        for weights,link,override,views in product([[],[0],[20],[5,30]],['YES','NO',None],
                ['unset','unloaded','measured','unknown'],[{},dict(LEFT=1),dict(LEFT=1,RIGHT=2)]):
            answers=[answer('work_type.lift','YES'),answer('context','YES')]
            answers += [answer('card.lift.load_mass_kg',v,f'물건 {i}') for i,v in enumerate(weights)]
            if link is not None:answers.append(answer('load_link',link))
            if override=='unloaded':answers.append(answer('load','UNLOADED'))
            if override=='measured':answers += [answer('load','MEASURED'),answer('load_kg',30)]
            if override=='unknown':answers.append(answer('load',None))
            saved=facts.apply_answers({},answers);before=copy.deepcopy(saved)
            if override=='unloaded':expected=('UNLOADED',None)
            elif override=='measured':expected=('MEASURED',30)
            elif override=='unset' and link=='YES' and len(weights)==1:expected=('MEASURED',weights[0])
            else:expected=('UNKNOWN',None)
            with self.subTest(weights=weights,link=link,override=override,views=views):
                self.assertEqual(photo_load(saved),expected)
                task=facts.project(task_input({}),saved,views,dict(views={}))
                candidates=planner.assess(task,saved,views)['candidates']
                targets={q['target'] for q in candidates}
                if expected[0]!='UNKNOWN':self.assertNotIn('load',targets)
                if expected[1] is not None:self.assertNotIn('load_kg',targets)
                if not views:self.assertFalse({'load','load_kg','load_link'} & targets)
                if expected in [('UNLOADED',None),('MEASURED',0)]:
                    self.assertFalse(any(q['target'].endswith('.coupling') for q in candidates))
                self.assertEqual(saved,before)

    def test_each_field_in_an_otherwise_incomplete_task_is_not_reasked(self):
        catalogue = contract.fields(); views = dict(LEFT=1, RIGHT=2, FRONT=3)
        seed = facts.apply_answers({}, [answer(f['target'],'YES') for f in catalogue if f['destination']['type']=='work_type'] + [answer('context','YES'),answer('load','MEASURED')])
        for field in catalogue:
            for source,state in [('USER','KNOWN'),('AI','KNOWN'),('POSE','KNOWN'),('SAVED','KNOWN'),('USER','UNKNOWN')]:
                saved=copy.deepcopy(seed)
                value=(field['choices'][0]['value'] if field['kind']=='choice' else min(20,field['maximum'] or 20) if field['kind']=='number' else '입력한 작업')
                identity=contract.key(field['target'])
                saved[identity]=facts.fact(field,None if state=='UNKNOWN' else value,source)
                task=facts.project(task_input({}),saved,views,dict(views={}))
                candidates=planner.assess(task,saved,views)['candidates']
                with self.subTest(target=field['target'],source=source,state=state):
                    self.assertNotIn(identity,{c['identity'] for c in candidates})
                    for q in planner.choose(candidates):
                        group=planner.with_answer_questions(planner.with_paired_question(q,candidates),candidates,saved)
                        self.assertNotIn(identity,{f['identity'] for f in group.get('answer_questions',[])})
                        self.assertNotEqual(identity,(group.get('paired_question') or {}).get('identity'))

    def test_every_handled_identity_stays_out_of_candidates_for_each_source(self):
        catalogue = contract.fields()
        views = dict(LEFT=1, RIGHT=2, FRONT=3)
        for source, state in [('USER','KNOWN'), ('AI','KNOWN'), ('POSE','KNOWN'), ('SAVED','KNOWN'), ('USER','UNKNOWN')]:
            saved = {}
            for field in catalogue:
                value = (field['choices'][0]['value'] if field['kind']=='choice' else
                         min(20, field['maximum'] or 20) if field['kind']=='number' else '작업 이름')
                row = facts.fact(field, None if state=='UNKNOWN' else value, source)
                saved[contract.key(field['target'])] = row
            task = facts.project(task_input({}), saved, views, dict(views={}))
            before = copy.deepcopy((task, saved))
            candidates = planner.assess(task, saved, views)['candidates']
            with self.subTest(source=source, state=state):
                self.assertEqual(candidates, [], 'handled values, including unknown, must never be asked again')
                self.assertEqual((task, saved), before)

    def test_zero_no_and_different_conditions_do_not_invent_answers(self):
        saved = facts.apply_answers({}, [answer('work_type.lift','YES'), answer('complete.lift','YES'),
            answer('card.lift.load_mass_kg',0,'빈 상자'), answer('card.lift.load_mass_kg',30,'큰 상자'),
            answer('card.lift.lift_count_day',0,'빈 상자'), answer('one_off','NO')])
        task = facts.project(task_input({}), saved, {}, {})
        candidates = planner.assess(task, saved, {})['candidates']
        identities = {q['identity'] for q in candidates}
        self.assertNotIn('card.lift.load_mass_kg@빈 상자',identities)
        self.assertNotIn('card.lift.lift_count_day@빈 상자',identities)
        self.assertIn('card.lift.lift_count_day@큰 상자',identities)
        self.assertNotIn('one_off@default',identities)

    def test_shared_load_never_guesses_across_conditions_or_explicit_unknowns(self):
        saved = facts.apply_answers({}, [answer('load_link','YES'),answer('card.lift.load_mass_kg',20,'상자')])
        self.assertEqual(photo_load(saved),('MEASURED',20))
        for target,value in [('load',None),('load','UNLOADED'),('load_kg',None)]:
            probe = facts.apply_answers(saved,[answer(target,value)])
            self.assertNotEqual(photo_load(probe),('MEASURED',20))
        self.assertEqual(photo_load(facts.apply_answers(saved,[answer('card.lift.load_mass_kg',30,'다른 상자')])),('UNKNOWN',None))
        self.assertEqual(photo_load(facts.apply_answers(saved,[answer('load_link','NO')])),('UNKNOWN',None))

    def test_measured_load_without_kg_still_offers_the_single_weight_link(self):
        saved=facts.apply_answers({},[answer('context','YES'),answer('load','MEASURED'),
            answer('card.lift.load_mass_kg',20,'상자')])
        views=dict(LEFT=1)
        task=facts.project(task_input({}),saved,views,{})
        before=copy.deepcopy((task,saved))
        link=next((q for q in planner.assess(task,saved,views)['candidates'] if q['target']=='load_link'),None)
        self.assertIsNotNone(link,'knowing that an object is held must not hide its missing weight connection')
        self.assertIn('20',link['text'])
        self.assertEqual(photo_load(saved),('MEASURED',None),'a stated work weight is not yet a photo load')
        self.assertIsNone(task['capture']['slots'][0]['observation']['measured_load_kg'])
        self.assertEqual((task,saved),before,'offering a connection must not save or guess it')
        confirmed=facts.apply_answers(saved,[answer('load_link','YES')])
        self.assertEqual(photo_load(confirmed),('MEASURED',20))
        after=facts.project(task,confirmed,views,{})
        self.assertEqual(after['capture']['slots'][0]['observation']['measured_load_kg'],20)
        self.assertNotIn('load_kg',{q['target'] for q in planner.assess(after,confirmed,views)['candidates']})

    def test_weight_link_does_not_bypass_unknown_conflicting_or_explicit_photo_loads(self):
        saved=facts.apply_answers({},[answer('context','YES'),answer('load','MEASURED'),
            answer('card.lift.load_mass_kg',20,'상자')])
        probes=[facts.apply_answers(saved,[answer(target,value)]) for target,value in
                [('load',None),('load','UNLOADED'),('load_kg',None),('load_kg',30),('load_link',None),('load_link','NO')]]
        conflicting_load=copy.deepcopy(saved)
        conflicting_load[contract.key('load')]['state']='CONFLICT'
        probes.append(conflicting_load)
        conflicting_mass=copy.deepcopy(saved)
        conflicting_mass['card.lift.load_mass_kg@다른 상자']=dict(
            conflicting_mass['card.lift.load_mass_kg@상자'],condition='다른 상자',state='CONFLICT',conflict=dict(value=30))
        probes.append(conflicting_mass)
        probes.append(facts.apply_answers(saved,[answer('card.lift.load_mass_kg',30,'다른 상자')]))
        for index,probe in enumerate(probes):
            with self.subTest(index=index):
                before=copy.deepcopy(probe)
                task=facts.project(task_input({}),probe,dict(LEFT=1),{})
                self.assertNotIn('load_link',{q['target'] for q in planner.assess(task,probe,dict(LEFT=1))['candidates']})
                self.assertEqual(probe,before)


class ReportedWeight(unittest.TestCase):
    setUp = fixtures.AdaptiveIntake.setUp
    turn = fixtures.AdaptiveIntake.turn
    get = fixtures.AdaptiveIntake.get
    photo_session = fixtures.PairedAdaptiveIntake.photo_session

    def test_held_photo_object_can_link_the_stated_weight_without_reentering_it(self):
        self.photo_session(sides=('LEFT',))
        state=self.turn([answer('context','YES'),answer('load','MEASURED'),answer('manual.LEFT.coupling','UNACCEPTABLE')],
            text='20kg 상자를 옮겨요.',raw=dict(answers=[model('card.lift.load_mass_kg',number=20,quote='20kg 상자',condition='상자')],questions=[]))
        self.assertIsNone(state['task']['capture']['slots'][0]['observation']['measured_load_kg'])
        self.assertIn('load_link',{q['target'] for q in state['form_fields']},'a usable explicit connection must remain available')
        linked=self.turn([answer('load_link','YES')],plan=False)
        observation=linked['task']['capture']['slots'][0]['observation']
        self.assertEqual((observation['load_state'],observation['measured_load_kg']),('MEASURED',20))
        manual=next(row for row in linked['task']['manual'] if row['scope']=='LEFT' and row['field']=='coupling')
        self.assertEqual(manual['value'],'UNACCEPTABLE','the load connection must preserve the actual grip answer')
        revision=linked['task']['input_revision']
        restored=self.get()
        self.assertEqual(restored['task']['input_revision'],revision)
        self.assertEqual(restored['task']['capture']['slots'][0]['observation']['measured_load_kg'],20)
        self.assertFalse({'load','load_kg'} & {q['target'] for q in restored['form_fields']})
        session=restored['task']['conditions'][contract.SESSION_KEY]
        self.assertNotIn('load_link',{q['target'] for q in planner.assess(restored['task'],session['facts'],session['views'])['candidates']})

    def test_ai_weight_confirmed_for_photo_is_not_asked_again_and_reads_stay_stable(self):
        self.photo_session()
        state = self.turn([answer('context','YES'),answer('load_link','YES')],
            text='20kg 상자를 옮겨요.',raw=dict(answers=[model('card.lift.load_mass_kg',number=20,quote='20kg 상자',condition='상자')],questions=[]))
        session = state['task']['conditions'][contract.SESSION_KEY]
        candidates = planner.assess(state['task'],session['facts'],session['views'])['candidates']
        self.assertFalse({'load','load_kg'} & {q['target'] for q in candidates})
        self.assertEqual(state['task']['capture']['slots'][0]['observation']['measured_load_kg'],20)
        restored = self.get()
        self.assertEqual(restored['task']['input_revision'],state['task']['input_revision'])
        self.assertFalse({'load','load_kg'} & {q['target'] for q in restored['form_fields']})


if __name__ == '__main__':
    unittest.main()
