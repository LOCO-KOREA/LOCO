"""Adversarial checks for REBA display projection and immutable photo baselines."""
import copy
import unittest

from ergo.engine.reba_scoring import NO_BURDEN, calculate_reba, project_current_score, project_score_continuity
from ergo.engine.task_defaults import ARM, COMMON
from ergo.gpt import payload
from ergo.gpt.client import fallback_text


PHOTO_ROWS = [
    dict(photo_id=7, scope='COMMON', field='trunk_base', value=4),
    dict(photo_id=7, scope='RIGHT', field='upper_arm_base', value=4),
]


def make_snapshot(*, answers=(), rows=PHOTO_ROWS, ids=(7,), load_state='UNKNOWN', load_kg=None):
    slots = [dict(slot_no=index, photo_id=photo_id, analysis_target=True, camera_side='RIGHT',
                  forward_direction='SCREEN_LEFT', side_view_verified='YES',
                  observation=dict(load_state=load_state, measured_load_kg=load_kg))
             for index, photo_id in enumerate(ids, 1)]
    manual = [dict(slot_no=1, photo_id=7, scope=row['scope'], field=row['field'],
                   value=row['value'], source='INTERVIEW') for row in answers]
    return dict(schema_version='2.0', task_id=3, input_revision=9,
        settings=dict(pose_model=dict(model_id='mediapipe-heavy', provider='mediapipe', confidence_min=0.5),
                      reba_rule='REBA_TABLE_2000_V2'),
        conditions=dict(intake_session=dict(photo_observations=dict(observations=copy.deepcopy(list(rows)),
            views={'7':dict(photo_id=7,front=[],signals={})}))),
        capture=dict(slots=slots), manual=manual, photos=[])


def analysis(snapshot, pose=None):
    return dict(analysis_id=11, task_id=3, status='FINISHED', snapshot=snapshot, pose=pose,
                reba=calculate_reba(snapshot, pose), currentness='CURRENT')


def point(name='nose', x=10.0, y=20.0, confidence=0.8):
    return dict(name=name, x_px=x, y_px=y, confidence=confidence)


class RebaScoreContinuity(unittest.TestCase):
    def test_missing_photo_mass_and_answered_coupling_preserve_other_pose_answers(self):
        snapshot=make_snapshot(load_state='MEASURED',answers=[
            dict(scope='COMMON',field='neck_base',value=2),
            dict(scope='LEFT',field='coupling',value='UNACCEPTABLE'),
            dict(scope='RIGHT',field='coupling',value='UNACCEPTABLE')])
        source=analysis(snapshot)
        before=copy.deepcopy(source)
        comparison=copy.deepcopy(snapshot)
        comparison['manual']=[m for m in comparison['manual'] if m['field']!='coupling']
        expected=project_score_continuity(analysis(comparison))['reba']['summary']['current_score']['total']

        current=project_score_continuity(source)['reba']['summary']['current_score']

        self.assertGreater(expected,1)
        self.assertGreater(current['total'],expected,'missing mass must preserve measured posture, answered neck, and the actual poor coupling')
        self.assertEqual(current['kind'],'WITH_ASSUMPTIONS')
        self.assertIn('observation.measured_load_kg',current['assumed'])
        self.assertNotIn('left.coupling',current['assumed'])
        self.assertIn('무게',current['assumption'])
        self.assertIsNone(project_score_continuity(source)['reba']['summary']['full_max'])
        self.assertEqual(project_score_continuity(source)['reba']['summary']['complete_count'],0)
        self.assertEqual(source,before,'unknown mass and the actual coupling answers remain unchanged in the snapshot')

    def test_known_mass_keeps_the_answered_coupling_in_the_score(self):
        answers=[dict(scope=side,field='coupling',value='UNACCEPTABLE') for side in ('LEFT','RIGHT')]
        snapshot=make_snapshot(load_state='MEASURED',load_kg=20,answers=answers)
        bad=project_score_continuity(analysis(snapshot))['reba']['summary']['current_score']
        good_snapshot=copy.deepcopy(snapshot)
        for item in good_snapshot['manual']:item['value']='GOOD'
        good=project_score_continuity(analysis(good_snapshot))['reba']['summary']['current_score']
        self.assertGreater(bad['total'],good['total'])
        self.assertNotIn('left.coupling',bad['assumed'])

    def test_each_photo_gets_its_own_current_score_without_borrowing_the_summary_max(self):
        projected=project_score_continuity(analysis(make_snapshot(ids=(7,8),load_state='MEASURED',load_kg=20)))
        slots=projected['reba']['slots']
        self.assertGreater(slots[0]['current_score']['total'],slots[1]['current_score']['total'])
        self.assertEqual(slots[1]['current_score']['total'],2)
        self.assertEqual(projected['reba']['summary']['current_score'],slots[0]['current_score'])

    def test_saved_slot_without_photo_id_keeps_its_components_without_duplicate_rows(self):
        source=analysis(make_snapshot())
        source['reba']['slots'][0].pop('photo_id')
        source['reba']['slots'][0]['left']['table_c']=4
        before=copy.deepcopy(source)
        projected=project_score_continuity(source)
        self.assertEqual(len(projected['reba']['slots']),1)
        self.assertEqual(projected['reba']['slots'][0]['left']['table_c'],4)
        self.assertIsInstance(projected['reba']['slots'][0]['current_score']['total'],int)
        self.assertEqual(source,before)

    def test_photo_baseline_is_carried_forward_but_actual_answer_replaces_same_field(self):
        snapshot=make_snapshot(answers=[dict(scope='COMMON',field='trunk_base',value=1)])
        source=analysis(snapshot,dict(status='PARTIAL_REVIEW',valid_count=1,slots=[dict(slot_no=1,photo_id=7,status='INVALID',points=[point()])]))
        before=copy.deepcopy(source)

        projected=project_score_continuity(source)
        summary=projected['reba']['summary']

        self.assertIn('first_pass',summary)
        self.assertEqual(summary['first_pass']['slot_no'],1)
        self.assertEqual(summary['current_score']['source'],'ANSWERS_SO_FAR')
        self.assertEqual(summary['current_score']['kind'],'WITH_ASSUMPTIONS')
        self.assertNotEqual(summary['first_pass']['total'],summary['current_score']['total'],
                            'the higher pre-answer value must not overwrite a lower score after a seated/position answer')
        self.assertEqual(summary['current_score']['slot_no'],1)
        self.assertEqual(projected['measurement_quality']['slots'][0]['measured_points'],1)
        self.assertEqual(projected['measurement_quality']['slots'][0]['total_points'],33)
        self.assertEqual(source,before,'projection must not mutate the stored result or snapshot')

    def test_registered_photo_without_pose_still_has_explicit_reference_and_zero_of_topology_quality(self):
        source=analysis(make_snapshot(rows=[],load_state='UNKNOWN'))
        projected=project_score_continuity(source)
        score=projected['reba']['summary']['current_score']

        self.assertIsInstance(score['total'],int)
        self.assertEqual(score['kind'],'ASSUMED_REFERENCE')
        self.assertEqual(score['source'],'ASSUMED_REFERENCE')
        self.assertIn('측정·확정 점수가 아닙니다',score['assumption'])
        self.assertEqual(projected['measurement_quality']['measured_points'],0)
        self.assertEqual(projected['measurement_quality']['total_points'],33)
        self.assertEqual(projected['measurement_quality']['confidence_level'],'MISSING')
        self.assertNotIn('first_pass',projected['reba']['summary'])

    def test_existing_complete_full_max_is_unchanged_and_wins_equal_score_tie(self):
        snapshot=make_snapshot(rows=[],load_state='UNLOADED')
        slot=snapshot['capture']['slots'][0]
        snapshot['manual']=[dict(slot_no=1,photo_id=7,scope=scope,field=field,value=NO_BURDEN[field],source='INTERVIEW')
                          for scope,fields in (('COMMON',COMMON),('LEFT',ARM),('RIGHT',ARM)) for field in fields]
        source=analysis(snapshot)
        original_full=source['reba']['summary']['full_max']
        projected=project_score_continuity(source)

        self.assertEqual(projected['reba']['summary']['full_max'],original_full)
        self.assertEqual(projected['reba']['summary']['current_score']['kind'],'CONFIRMED')
        self.assertEqual(projected['reba']['summary']['current_score']['source'],'COMPLETE')
        self.assertEqual(projected['reba']['summary']['current_score']['total'],original_full)

    def test_duplicate_target_photo_keeps_official_total_null_and_uses_reference_kind(self):
        source=analysis(make_snapshot(rows=PHOTO_ROWS,ids=(7,7)))
        projected=project_score_continuity(source)

        self.assertIsNone(projected['reba']['summary']['full_max'])
        self.assertEqual(projected['reba']['summary']['complete_count'],0)
        self.assertEqual(projected['reba']['summary']['current_score']['kind'],'ASSUMED_REFERENCE')
        self.assertIn('중복',projected['reba']['summary']['current_score']['assumption'])

    def test_legacy_saved_analysis_without_score_so_far_is_read_projected_without_source_mutation(self):
        snapshot=make_snapshot(rows=PHOTO_ROWS)
        source=analysis(snapshot,dict(status='INVALID',valid_count=0,slots=[]))
        source['reba']['summary'].pop('score_so_far',None)
        for slot in source['reba']['slots']:
            slot.pop('score_so_far',None)
        before=copy.deepcopy(source)

        projected=project_score_continuity(source)

        self.assertIsInstance(projected['reba']['summary']['current_score']['total'],int)
        self.assertIn('first_pass',projected['reba']['summary'])
        self.assertEqual(source,before)

    def test_public_selector_preserves_assumed_reference_provenance(self):
        reba=dict(summary=dict(total_slot_count=1,complete_count=0),slots=[dict(slot_no=1,status='INCOMPLETE',
            score_so_far=dict(total=1,risk='NEGLIGIBLE',kind='ASSUMED_REFERENCE',source='ASSUMED_REFERENCE',assumed=[],assumption='참조값'))])
        score=project_current_score(reba)
        self.assertEqual((score['kind'],score['source']),('ASSUMED_REFERENCE','ASSUMED_REFERENCE'))
        self.assertEqual(score['assumption'],'참조값')

    def test_gpt_summary_receives_current_score_and_measurement_quality_without_photo_ids(self):
        source=analysis(make_snapshot(rows=PHOTO_ROWS),dict(status='INVALID',valid_count=0,slots=[dict(slot_no=1,photo_id=7,status='INVALID',points=[])]))
        result=payload.build_numeric_summary(source)
        self.assertEqual(result['reba']['current_score']['kind'],'WITH_ASSUMPTIONS')
        self.assertIn('first_pass',result['reba'])
        self.assertNotIn('slot_no',result['reba']['current_score'])
        self.assertNotIn('slot_no',result['reba']['first_pass'])
        self.assertEqual(result['pose_quality']['total_points'],33)
        self.assertNotIn('photo_id',str(result))

    def test_fallback_keeps_borrowed_photo_and_load_provenance_and_localizes_quality(self):
        text=fallback_text(dict(reba=dict(current_score=dict(total=3,risk='LOW',kind='WITH_ASSUMPTIONS',source='ANSWERS_SO_FAR',assumed_count=25),
            score_so_far=dict(total=3,risk='LOW',assumed_count=25,unconfirmed_photo_count=4,load_assumed=True)),
            pose_quality=dict(measured_points=0,total_points=33,confidence_level='MISSING')))
        self.assertIn('사진 확인 전 값 4개를 포함하고',text)
        self.assertIn('하중 가산점을 0으로 가정했으며',text)
        self.assertNotIn('물건이 없다고',text)
        self.assertIn('측정 없음',text)
        self.assertNotIn('MISSING',text)


if __name__ == '__main__':
    unittest.main()
