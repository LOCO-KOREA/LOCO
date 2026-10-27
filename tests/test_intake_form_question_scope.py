"""A correction catalogue is not a new questionnaire or a source of invented answers."""
import copy
import unittest

from ergo.engine.task_defaults import task_input
from ergo.intake import contract,facts,photo_facts,planner
from test_photo_fact_ownership import observation,preview


def build(answers,rows=(),views=None):
    views=views or {}
    data=preview(list(rows),views) if views else dict(views={})
    saved=facts.apply_answers({},answers,photo_views=views)
    saved=facts.add_photo_facts(saved,data,views)
    task=facts.project(task_input({}),saved,views,data)
    candidates=planner.assess(task,saved,views)['candidates']
    return task,saved,views,candidates


class IntakeFormQuestionScope(unittest.TestCase):
    def test_photo_followup_does_not_erase_or_expand_the_remaining_work_question_list(self):
        task,saved,views,candidates=build([dict(target='work_type.lift',value='YES')],views=dict(LEFT=101))
        before=copy.deepcopy((task,saved,candidates))
        self.assertIn(planner.choose(candidates)[0]['destination']['type'],contract.PHOTO_DESTINATIONS)
        chosen=planner.choose_questions(candidates)
        self.assertEqual(len(chosen),1,'the guided flow still presents one question at a time')
        self.assertTrue(any(row['destination']['type'] not in contract.PHOTO_DESTINATIONS for row in candidates),
                        'the photo question cannot erase the real missing work question')
        self.assertEqual((task,saved,candidates),before)

    def test_photo_only_candidates_stay_in_the_optional_form_without_opening_a_question(self):
        work=[field for field in contract.fields() if field['destination']['type']=='work_type']
        answers=[dict(target=field['target'],value='NO') for field in work]
        answers.extend([dict(target='annual_work_days',value=220),dict(target='one_off',value='NO'),dict(target='context',value='YES'),
                        dict(target='view_LEFT',value='SCREEN_LEFT'),dict(target='load',value='UNLOADED')])
        task,saved,views,candidates=build(answers,views=dict(LEFT=101))
        self.assertTrue(candidates)
        self.assertTrue(any(row['destination']['type']=='manual' for row in candidates))
        self.assertEqual(planner.choose_questions(candidates,photo_context='YES'),[])
        fields=planner.form_fields(task,saved,views,candidates)
        self.assertTrue(any(row['pending_input'] and row['destination']['type'] in contract.PHOTO_DESTINATIONS for row in fields))

    def test_unknown_other_work_stays_one_question_until_the_user_opens_its_choices(self):
        task,saved,views,candidates=build([dict(target='work_type.lift',value='YES')])
        before=copy.deepcopy((task,saved,candidates))
        fields=planner.form_fields(task,saved,views,candidates)
        self.assertEqual([row['target'] for row in fields if row['destination']['type']=='work_type'],['work_type.lift'])
        other=[row for row in fields if row['target']=='other_work']
        self.assertEqual(len(other),1);self.assertTrue(other[0]['pending_input'])
        self.assertFalse(next(row for row in fields if row['target']=='work_type.lift')['pending_input'])
        self.assertEqual((task,saved,candidates),before,'planning must not fill unknown work types with NO')
        self.assertEqual(task['legal']['criteria'][0]['condition_present'],'UNKNOWN')

        task,saved,views,candidates=build([dict(target='work_type.lift',value='YES'),dict(target='other_work',value='YES')])
        opened=planner.form_fields(task,saved,views,candidates)
        unknown=[row for row in opened if row['destination']['type']=='work_type' and row['target']!='work_type.lift']
        self.assertEqual(len(unknown),8)
        self.assertTrue(all(row['pending_input'] for row in unknown))

    def test_saved_pose_estimate_and_user_value_are_editable_metadata_not_pending_questions(self):
        rows=[dict(observation('LEFT','COMMON','neck_base',1,19.8),estimated=True,
                   measurement_method='NECK_FLEX_TRUNK_PROXY'),
              dict(observation('LEFT','LEFT','upper_arm_base',3,47.5),boundary_review=True)]
        task,saved,views,candidates=build([
            dict(target='context',value='YES'),dict(target='load',value='MEASURED'),dict(target='load_kg',value=20),
            dict(target='manual.RIGHT.upper_arm_base',condition='photo:101',value=3)],rows,dict(LEFT=101))
        before=copy.deepcopy((task,saved,candidates))
        fields={row['identity']:row for row in planner.form_fields(task,saved,views,candidates)}
        for identity in ('manual.COMMON.neck_base@photo:101','manual.LEFT.upper_arm_base@photo:101',
                         'manual.RIGHT.upper_arm_base@photo:101'):
            with self.subTest(identity=identity):
                self.assertIn(identity,fields)
                self.assertFalse(fields[identity]['pending_input'])
                self.assertNotIn(identity,{row['identity'] for row in candidates})
        self.assertTrue(fields['manual.COMMON.neck_base@photo:101']['measurement_applied'])
        self.assertTrue(fields['manual.LEFT.upper_arm_base@photo:101']['measurement_applied'])
        self.assertEqual(fields['manual.RIGHT.upper_arm_base@photo:101']['photo_id'],101)
        self.assertEqual(saved['manual.RIGHT.upper_arm_base@photo:101']['value'],3)
        self.assertEqual((task,saved,candidates),before)

    def test_user_unknown_remains_unknown_in_correction_metadata_without_reasking(self):
        task,saved,views,candidates=build([dict(target='work_type.lift',value='YES'),
                                         dict(target='complete.lift',value='YES'),
                                         dict(target='card.lift.load_mass_kg',value=30),
                                         dict(target='card.lift.lift_count_day',value=None)])
        fields={row['identity']:row for row in planner.form_fields(task,saved,views,candidates)}
        identity='card.lift.lift_count_day@default'
        self.assertIn(identity,fields)
        self.assertFalse(fields[identity]['pending_input'])
        self.assertIsNone(saved[identity]['value'])
        self.assertEqual(saved[identity]['source'],'USER')
        self.assertIsNone(task['legal']['criteria'][7]['rows'][0]['lift_count_day'])

    def test_unresolved_photo_value_stays_unknown_and_owned_instead_of_inventing_a_reading(self):
        task,saved,views,candidates=build([dict(target='context',value='YES'),dict(target='load',value='MEASURED'),
                                         dict(target='load_kg',value=20)],views=dict(LEFT=101))
        fields={row['identity']:row for row in planner.form_fields(task,saved,views,candidates)}
        identity='manual.RIGHT.wrist_base@photo:101'
        self.assertIn(identity,fields);self.assertTrue(fields[identity]['pending_input'])
        self.assertEqual(fields[identity]['photo_id'],101)
        self.assertNotIn(identity,saved)
        self.assertFalse(any(row['field']=='wrist_base' and row['scope']=='RIGHT' for row in task['manual']))

    def test_pending_metadata_tracks_real_candidates_and_keeps_their_conflict_reason(self):
        task,saved,views,candidates=build([dict(target='work_type.lift',value='YES')])
        candidate=next(row for row in candidates if row['target']=='other_work')
        marked=dict(candidate,reason='이전 설명과 다른 값을 확인해 주세요.',priority=0)
        rows=planner.form_fields(task,saved,views,[marked])
        question=next(row for row in rows if row['identity']==marked['identity'])
        self.assertEqual(question['reason'],marked['reason'])
        self.assertEqual(question['priority'],0)
        self.assertTrue(question['pending_input'])
        self.assertTrue(all(row['pending_input']==(row['identity']==marked['identity']) for row in rows))


if __name__=='__main__':unittest.main()
