"""Input-consumption regressions for posture, activity and work-quantity boundaries."""
import copy
import unittest
from unittest.mock import patch

from backend.engine import reba_scoring as reba
from backend.engine.task_defaults import COMMON, ARM
from tests import test_reba_score_continuity as fixtures


def complete_snapshot(**overrides):
    rows=[]
    for scope,fields in (('COMMON',COMMON),('LEFT',ARM),('RIGHT',ARM)):
        for field in fields:
            value='GOOD' if field=='coupling' else reba.NO_BURDEN[field]
            rows.append(dict(scope=scope,field=field,value=overrides.get(field,value)))
    return fixtures.make_snapshot(answers=rows,rows=[],load_state='MEASURED',load_kg=20)


class RebaAllInputPropagation(unittest.TestCase):
    def test_every_actual_posture_answer_reaches_the_private_current_calculation(self):
        snapshot=complete_snapshot(trunk_base=3,neck_base=2,legs_support='UNILATERAL_OR_UNSTABLE',
            knee_band='OVER_60',upper_arm_base=4,lower_arm_base=2,wrist_base=2,coupling='UNACCEPTABLE',
            trunk_twisted='YES',trunk_side_bent='YES',neck_twisted='YES',neck_side_bent='YES',
            shock_force='YES',static_over_1min='YES',small_repeat_over_4min='YES',
            arm_abducted_or_rotated='YES',shoulder_raised='YES',arm_supported_or_gravity_assisted='YES',
            wrist_deviated_or_twisted='YES')
        snapshot['manual']=[row for row in snapshot['manual'] if row['field']!='rapid_change_or_unstable']
        source=fixtures.analysis(snapshot);before=copy.deepcopy(source)
        actual={(row['scope'],row['field']):row['value'] for row in snapshot['manual']}
        native=reba.calculate_reba;seen=[]
        def record(snap,pose,*args,**kwargs):
            if kwargs.get('with_score_so_far') is False:
                seen.append(copy.deepcopy(snap))
            return native(snap,pose,*args,**kwargs)
        with patch.object(reba,'calculate_reba',side_effect=record):
            projected=reba.project_score_continuity(source)
        self.assertTrue(seen,'the current score must be calculated from a fully materialized private copy')
        consumed={(row['scope'],row['field']):row['value'] for row in seen[-1]['manual']}
        for identity,value in actual.items():
            with self.subTest(identity=identity):self.assertEqual(consumed[identity],value)
        self.assertEqual(projected['reba']['summary']['current_score']['assumed'],['common.rapid_change_or_unstable'])
        self.assertEqual(source,before,'calculating the current score must not rewrite real answers')

    def test_each_activity_answer_adds_one_and_the_three_answers_add_three(self):
        base=complete_snapshot();plain=reba.calculate_reba(base,None)['slots'][0]
        for field in ('static_over_1min','small_repeat_over_4min','rapid_change_or_unstable'):
            changed=complete_snapshot(**{field:'YES'})
            value=reba.calculate_reba(changed,None)['slots'][0]
            with self.subTest(field=field):
                self.assertEqual(value['left']['activity_score'],1)
                self.assertEqual(value['total'],plain['total']+1)
        all_three=reba.calculate_reba(complete_snapshot(static_over_1min='YES',small_repeat_over_4min='YES',rapid_change_or_unstable='YES'),None)['slots'][0]
        self.assertEqual(all_three['left']['activity_score'],3)
        self.assertEqual(all_three['total'],plain['total']+3)

    def test_shock_and_grip_answers_change_their_own_component_scores(self):
        base=reba.calculate_reba(complete_snapshot(),None)['slots'][0]
        shock=reba.calculate_reba(complete_snapshot(shock_force='YES'),None)['slots'][0]
        bad_grip=reba.calculate_reba(complete_snapshot(coupling='UNACCEPTABLE'),None)['slots'][0]
        self.assertEqual((base['left']['load_score'],shock['left']['load_score']),(2,3))
        self.assertEqual((base['left']['coupling_score'],bad_grip['left']['coupling_score']),(0,3))
        self.assertNotEqual(base['total'],bad_grip['total'])

    def test_work_duration_day_count_and_lift_rate_are_not_guessed_into_reba_activity(self):
        before=complete_snapshot();after=copy.deepcopy(before)
        before['conditions'].update(daily_work_min=60,annual_work_days=200)
        after['conditions'].update(daily_work_min=480,annual_work_days=365)
        before['legal']=dict(criteria=[dict(criterion_no=10,rows=[dict(load_mass_kg=20,lift_rate_min=2,minutes=60,lift_count_day=120)])])
        after['legal']=dict(criteria=[dict(criterion_no=10,rows=[dict(load_mass_kg=20,lift_rate_min=10,minutes=480,lift_count_day=4800)])])
        expected=reba.calculate_reba(before,None)
        self.assertEqual(reba.calculate_reba(after,None),expected,
            'whole-day exposure and lifting counts are retained for their own criteria, not treated as posture-hold duration or small-motion repetition')
        self.assertEqual(after['conditions']['daily_work_min'],480)
        self.assertEqual(after['legal']['criteria'][0]['rows'][0]['lift_count_day'],4800)

    def test_explicit_posture_correction_wins_over_the_same_photo_candidate(self):
        snapshot=fixtures.make_snapshot(answers=[dict(scope='LEFT',field='upper_arm_base',value=1)],
            rows=[dict(photo_id=7,scope='COMMON',field='trunk_base',value=3),
                  dict(photo_id=7,scope='LEFT',field='upper_arm_base',value=4)],load_state='MEASURED',load_kg=20)
        source=fixtures.analysis(snapshot);seen=[];native=reba.calculate_reba
        def record(snap,pose,*args,**kwargs):
            if kwargs.get('with_score_so_far') is False:seen.append(copy.deepcopy(snap))
            return native(snap,pose,*args,**kwargs)
        with patch.object(reba,'calculate_reba',side_effect=record):reba.project_score_continuity(source)
        correction=next(row for row in seen[-1]['manual'] if row['scope']=='LEFT' and row['field']=='upper_arm_base')
        self.assertEqual(correction['value'],1)

    def test_other_photo_answers_are_never_consumed_by_the_current_photo(self):
        snapshot=fixtures.make_snapshot(rows=[],load_state='MEASURED',load_kg=20)
        snapshot['manual']=[dict(slot_no=1,photo_id=999,scope='COMMON',field='trunk_base',value=4,source='INTERVIEW'),
                            dict(slot_no=1,photo_id=999,scope='LEFT',field='upper_arm_base',value=4,source='INTERVIEW')]
        current=reba.project_score_continuity(fixtures.analysis(snapshot))['reba']['summary']['current_score']
        self.assertEqual(current['total'],2)
        self.assertIn('common.trunk_base',current['assumed'])
        self.assertIn('left.upper_arm_base',current['assumed'])


if __name__=='__main__':unittest.main()
