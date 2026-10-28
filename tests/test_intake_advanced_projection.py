"""Advanced criterion edits must survive reopening the shared intake form."""
import copy
import unittest

from backend.engine.task_defaults import task_input
from backend.intake import contract, facts
from backend.intake.photo_load import photo_load
from backend.service.task_inputs import validate_task_input_shape
from tests import test_adaptive_intake as fixtures


def advanced_task():
    task=task_input(dict(task_name='기준별로 편집한 작업'))
    for number,mass,present,complete in ((8,20,'YES','YES'),(9,30,'NO','NO'),(10,40,'YES','YES')):
        criterion=task['legal']['criteria'][number-1]
        criterion.update(condition_present=present,rows_complete=complete,
                         rows=[dict(row_id='shared',label='현장에 적은 조건',load_mass_kg=mass,
                                    evidence=dict(source='DOCUMENT',text='기준별 직접 기록',observed_at=None))])
    task['legal']['criteria'][7]['rows'][0]['lift_count_day']=120
    task['legal']['criteria'][8]['rows'][0].update(union_evidence='독립 합집합 근거',below_knee_count_day=5)
    task['legal']['criteria'][9]['rows'][0].update(lift_rate_min=2,minutes=60)
    return task


class AdvancedProjection(unittest.TestCase):
    def test_mixed_saved_mass_presence_completeness_and_metadata_survive_roundtrip(self):
        task=advanced_task();before=copy.deepcopy(task)
        validate_task_input_shape(None,task)
        restored=facts.read_values(task)
        shared=restored[contract.key('card.lift.load_mass_kg','shared')]
        self.assertEqual(shared['state'],'CONFLICT')
        self.assertEqual(shared['saved_criteria'],{'8':20,'9':30,'10':40})
        self.assertEqual(restored[contract.key('work_type.lift')]['saved_criteria'],{'8':'YES','9':'NO','10':'YES'})
        self.assertEqual(restored[contract.key('complete.lift')]['saved_criteria'],{'8':'YES','9':'NO','10':'YES'})
        projected=facts.project(task,restored,{},dict(views={}))
        self.assertEqual(projected['legal'],before['legal'])
        self.assertEqual(task,before,'projection must not change its source or a frozen snapshot')
        linked=dict(restored)
        linked= facts.apply_answers(linked,[fixtures.answer('load_link','YES')])
        self.assertEqual(photo_load(linked),('UNKNOWN',None),'conflicting criteria cannot select the last photo weight')

    def test_restoring_a_partial_advanced_row_does_not_create_other_criterion_rows(self):
        task=task_input(dict(task_name='8호에만 기록한 작업'))
        criterion=task['legal']['criteria'][7]
        criterion.update(condition_present='YES',rows=[dict(row_id='shared',label='독립 조건',load_mass_kg=20,lift_count_day=30)])
        before=copy.deepcopy(task['legal'])
        restored=facts.read_values(task)
        projected=facts.project(task,restored,{},dict(views={}))
        self.assertEqual(projected['legal'],before)

    def test_a_new_explicit_shared_edit_changes_its_condition_and_preserves_other_values(self):
        task=advanced_task()
        for number in (8,9,10):
            task['legal']['criteria'][number-1]['rows'].append(dict(row_id='other',label='다른 작업',load_mass_kg=5))
        restored=facts.read_values(task)
        edited=facts.apply_answers(restored,[fixtures.answer('card.lift.load_mass_kg',25,'shared')])
        projected=facts.project(task,edited,{},dict(views={}))
        for number in (8,9,10):
            rows={row['row_id']:row for row in projected['legal']['criteria'][number-1]['rows']}
            self.assertEqual(rows['shared']['load_mass_kg'],25)
            self.assertEqual(rows['shared']['label'],'현장에 적은 조건')
            self.assertEqual(rows['other']['load_mass_kg'],5)
        self.assertEqual(projected['legal']['criteria'][8]['rows'][0]['union_evidence'],'독립 합집합 근거')
        self.assertEqual([projected['legal']['criteria'][n-1]['condition_present'] for n in (8,9,10)],['YES','NO','YES'])
        self.assertEqual([projected['legal']['criteria'][n-1]['rows_complete'] for n in (8,9,10)],['YES','NO','YES'])

    def test_all_catalogue_values_still_roundtrip_including_zero_and_choice_boundaries(self):
        catalogue=contract.fields();self.assertEqual(len(catalogue),90)
        seed=[fixtures.answer('context','YES'),fixtures.answer('load','MEASURED'),fixtures.answer('load_kg',20)]
        views=dict(LEFT=101,RIGHT=102,FRONT=103)
        for field in catalogue:
            if field['destination']['type'] in ('load_link','other_work'):continue
            candidates=[choice['value'] for choice in field['choices']] if field['kind']=='choice' else [0,min(20,field['maximum']) if field['maximum'] is not None else 20] if field['kind']=='number' else ['현장 작업']
            for candidate in candidates:
                with self.subTest(target=field['target'],value=candidate):
                    condition='case' if field['conditioned'] else 'default'
                    entered=facts.apply_answers({},seed+[fixtures.answer(field['target'],candidate,condition)])
                    projected=facts.project(task_input(dict(task_name='현장 작업')),entered,views,dict(views={}))
                    saved=facts.read_values(projected).get(contract.key(field['target'],condition))
                    self.assertIsNotNone(saved)
                    self.assertEqual(saved['value'],candidate)


class PhotoProjection(unittest.TestCase):
    def seed(self):
        views=dict(LEFT=101,RIGHT=102,FRONT=103)
        entered=facts.apply_answers({},[fixtures.answer('context','YES'),fixtures.answer('load','MEASURED'),
                                       fixtures.answer('load_kg',20),fixtures.answer('view_RIGHT','SCREEN_RIGHT')])
        task=facts.project(task_input(dict(task_name='사진별 입력')),entered,views,dict(views={}))
        task['conditions']['intake_session']=dict(facts=copy.deepcopy(entered))
        task['capture']['slots'][0]['analysis_target']=False
        side=task['capture']['slots'][1]
        side.update(analysis_target=True,camera_side='OTHER',side_view_verified='NO')
        side['observation'].update(measured_load_kg=10,full_frame='NO',normal_work='NO',
                                   evidence=dict(source='INTERVIEW',text='이 사진은 별도 10kg 물건이며 전신이 아님',observed_at=None))
        return task,views

    def test_reopening_preserves_photo_specific_observations_directions_and_selected_target(self):
        task,views=self.seed();before=copy.deepcopy(task)
        projected=facts.project(task,facts.read_values(task),views,dict(views={}))
        self.assertEqual(projected['capture'],before['capture'])
        self.assertEqual(task,before)

    def test_unchanged_user_facts_are_not_new_common_edit_commands(self):
        task,views=self.seed();before=copy.deepcopy(task['capture'])
        projected=facts.project(task,task['conditions']['intake_session']['facts'],views,dict(views={}))
        self.assertEqual(projected['capture'],before)

    def test_explicit_common_edits_apply_without_changing_photo_selection_or_camera(self):
        task,views=self.seed()
        restored=facts.read_values(task)
        edited=facts.apply_answers(restored,[fixtures.answer('load_kg',15),fixtures.answer('context','NO'),
                                            fixtures.answer('view_RIGHT','SCREEN_LEFT')])
        projected=facts.project(task,edited,views,dict(views={}))
        for slot in projected['capture']['slots']:
            self.assertEqual(slot['observation']['measured_load_kg'],15)
            self.assertEqual(slot['observation']['normal_work'],'NO')
        self.assertEqual([slot['analysis_target'] for slot in projected['capture']['slots']],[False,True,False])
        self.assertEqual(projected['capture']['slots'][1]['forward_direction'],'SCREEN_LEFT')
        self.assertEqual(projected['capture']['slots'][1]['camera_side'],'OTHER')

    def test_new_photo_receives_common_values_while_existing_photo_retains_its_own(self):
        task,views=self.seed()
        old=copy.deepcopy(task['capture']['slots'][1])
        task['capture']['slots'].pop()
        projected=facts.project(task,task['conditions']['intake_session']['facts'],views,dict(views={}))
        self.assertEqual(projected['capture']['slots'][1],old)
        self.assertEqual(projected['capture']['slots'][2]['observation']['measured_load_kg'],20)
        self.assertEqual(projected['capture']['slots'][2]['observation']['normal_work'],'YES')

    def test_stable_slot_numbers_custom_labels_and_user_answers_survive_reopen(self):
        task,views=self.seed()
        for index,slot in enumerate(task['capture']['slots'],1):
            slot['slot_no']=index*10;slot['label']='현장 사진 '+str(index)
            task['manual'].append(dict(slot_no=index*10,photo_id=slot['photo_id'],scope='COMMON',
                                       field='trunk_base',value=index,source='INTERVIEW'))
        before=copy.deepcopy(task)
        projected=facts.project(task,facts.read_values(task),views,dict(views={}))
        self.assertEqual(projected['capture'],before['capture'])
        self.assertEqual({(m['slot_no'],m['photo_id'],m['field'],m['value']) for m in projected['manual']},
                         {(m['slot_no'],m['photo_id'],m['field'],m['value']) for m in before['manual']})
        validate_task_input_shape(None,projected)

    def test_removed_photo_does_not_renumber_survivor_or_reuse_its_slot_for_a_new_photo(self):
        task,views=self.seed()
        for index,slot in enumerate(task['capture']['slots'],1):slot['slot_no']=index*10
        survivor=task['capture']['slots'][1]
        task['manual']=[dict(slot_no=20,photo_id=102,scope='COMMON',field='trunk_base',value=3,source='INTERVIEW')]
        restored=facts.read_values(task)
        projected=facts.project(task,restored,dict(RIGHT=102,FRONT=104),dict(views={}))
        by_photo={slot['photo_id']:slot for slot in projected['capture']['slots']}
        self.assertEqual(by_photo[102]['slot_no'],20)
        self.assertGreater(by_photo[104]['slot_no'],30)
        self.assertEqual(next(m for m in projected['manual'] if m['photo_id']==102)['slot_no'],20)
        unloaded=facts.apply_answers(restored,[fixtures.answer('load','UNLOADED')])
        without_load=facts.project(task,unloaded,dict(RIGHT=102),dict(views={}))
        self.assertTrue(all(m['slot_no']==20 for m in without_load['manual']))
        validate_task_input_shape(None,without_load)


class ReopenAdvancedInput(unittest.TestCase):
    def setUp(self):fixtures.AdaptiveIntake.setUp(self)

    def test_reopen_detects_split_values_even_when_the_prior_shared_number_is_unchanged(self):
        self.ctx.dispatch('intake_turn',dict(task_id=self.identity,plan=False,answers=[
            fixtures.answer('work_type.lift','YES'),fixtures.answer('complete.lift','YES'),
            fixtures.answer('card.lift.load_mass_kg',20,'shared')]))
        current=self.ctx.require('task',self.identity)
        edited=copy.deepcopy(current)
        replacement=advanced_task()
        edited['legal']=replacement['legal']
        self.ctx.dispatch('save_task_input',dict(task_id=self.identity,input=self.ctx.task_input(edited),expected_revision=current['input_revision']))
        analysis=self.ctx.dispatch('recalculate_judgments',dict(task_id=self.identity))
        frozen=copy.deepcopy(self.ctx.store('get_analysis',analysis['analysis_id'])['snapshot'])
        reopened=self.ctx.dispatch('intake_session',dict(task_id=self.identity))
        self.assertEqual(reopened['task']['legal'],replacement['legal'])
        mass=reopened['task']['conditions']['intake_session']['facts'][contract.key('card.lift.load_mass_kg','shared')]
        self.assertEqual((mass['value'],mass['state']),(20,'CONFLICT'))
        again=self.ctx.dispatch('intake_session',dict(task_id=self.identity))
        self.assertEqual(again['task']['input_revision'],reopened['task']['input_revision'])
        self.assertEqual(self.ctx.store('get_analysis',analysis['analysis_id'])['snapshot'],frozen)


if __name__=='__main__':unittest.main()
