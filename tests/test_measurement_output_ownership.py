"""Foreign/malformed saved measurement rows are not relabelled as current photos."""
import copy
import unittest

from ergo.gpt.payload import _posture_results
from ergo.report.plain import _measurement_text,_posture,_estimated_rows
from ergo.intake.photo_facts import estimated_photo_inputs


def analysis():
    slot=dict(slot_no=1,photo_id=7,label='LEFT',analysis_target=True)
    pose=dict(slot_no=1,photo_id=7,status='VALID',points=[dict(name='nose',x_px=1,y_px=2)],
        angles=[dict(side='LEFT',angle_code='TRUNK_TILT_VERT',value_deg=33.3,min_confidence=.9)],world_angles=[])
    return dict(snapshot=dict(schema_version='2.0',capture=dict(slots=[slot]),settings=dict(pose_model=dict(confidence_min=.5))),
        pose=dict(slots=[pose]),reba=dict(slots=[]),measurement_quality=dict(slots=[
            dict(slot_no=1,photo_id=7,measured_points=27,total_points=33,mean_confidence=.79,confidence_level='HIGH')]))


def cells(sheet):
    return [cell for table in (sheet or {}).get('tables',[]) for row in table['rows'] for cell in row]


class MeasurementOutputOwnership(unittest.TestCase):
    def estimated(self):
        value=analysis();snapshot=value['snapshot'];snapshot['input_revision']=3
        fact=dict(target='manual.COMMON.neck_base',condition='photo:7',photo_id=7,photo_active=True,state='ESTIMATED',source='VISION',value=2,
            estimated=True,measurement_method='AI_PHOTO_CATEGORY',vision_confidence=.75,
            vision_proof=dict(scope='COMMON',field='neck_base',value='NECK_OVER_20',status='OBSERVED',confidence=.75,evidence='PRIVATE_VISIBLE_EVIDENCE'))
        snapshot['conditions']=dict(intake_session=dict(projected_revision=3,views=dict(LEFT=7),facts=dict(estimate=fact)))
        value['reba']['slots']=[dict(slot_no=1,photo_id=7,current_score=dict(total=6,risk='MEDIUM',kind='WITH_ASSUMPTIONS',measurement_refs=[
            dict(scope='COMMON',field='neck_base',value=2,measurement_method='AI_PHOTO_CATEGORY',estimated=True)]))]
        return value,fact

    def test_estimated_vision_input_is_anonymous_in_ai_and_visible_with_basis_in_excel(self):
        import json
        value,fact=self.estimated();before=copy.deepcopy(value);slot=value['snapshot']['capture']['slots'][0]
        result=_posture_results(value,[slot])[0]['estimated_inputs']
        self.assertEqual(result,[dict(scope='COMMON',field='neck_base',value=2,source='VISION',state='ESTIMATED',measurement_method='AI_PHOTO_CATEGORY',confidence=.75,display_confidence_percent=75,used_for_reba=True)])
        self.assertNotIn('PRIVATE_VISIBLE_EVIDENCE',json.dumps(result))
        rows=_estimated_rows('작업',value['snapshot'],value)
        self.assertEqual(rows[0][1],'사진 자세 추정')
        self.assertIn('사진 관찰 확신도 75%',rows[0][-1]);self.assertIn('현재 REBA 초안에 사용',rows[0][-1])
        self.assertIn('PRIVATE_VISIBLE_EVIDENCE',rows[0][-1],'local output preserves visible-photo evidence without sending it to explanation AI')
        self.assertEqual(value,before,'output must not promote an estimate into snapshot.manual')

    def test_estimated_input_rejects_stale_foreign_alias_duplicate_and_unusable_proof(self):
        mutations=(lambda v,f:v['snapshot']['conditions']['intake_session'].update(projected_revision=2),
            lambda v,f:f.update(photo_id=999),lambda v,f:f.update(condition='photo:999'),lambda v,f:f.update(photo_active=False),
            lambda v,f:f.update(alias_of='other'),lambda v,f:f.update(reask=True),
            lambda v,f:f['vision_proof'].update(status='UNCERTAIN'),lambda v,f:f['vision_proof'].update(confidence=.49),
            lambda v,f:v['snapshot']['conditions']['intake_session']['facts'].update(duplicate=copy.deepcopy(f)))
        for index,mutate in enumerate(mutations):
            with self.subTest(case=index):
                value,fact=self.estimated();mutate(value,fact)
                self.assertEqual(estimated_photo_inputs(value['snapshot'],value['snapshot']['capture']['slots'][0]),[])

    def test_user_manual_or_unknown_answers_take_priority_over_vision_estimate(self):
        for unknown in (False,True):
            value,fact=self.estimated();snapshot=value['snapshot']
            if unknown:snapshot['conditions']['intake_session']['facts']['answer']=dict(fact,source='USER',state='UNKNOWN',value=None)
            else:snapshot['manual']=[dict(slot_no=1,photo_id=7,scope='COMMON',field='neck_base',value=1,source='INTERVIEW')]
            self.assertEqual(estimated_photo_inputs(snapshot,snapshot['capture']['slots'][0]),[])

    def test_estimate_use_requires_the_actual_selected_measurement_method(self):
        value,fact=self.estimated();row=value['reba']['slots'][0]
        row['current_score']['measurement_refs'][0]['measurement_method']='INFERRED_WORLD_3D'
        self.assertFalse(_posture_results(value,value['snapshot']['capture']['slots'])[0]['estimated_inputs'][0]['used_for_reba'])

    def test_ai_rejects_a_different_photo_even_if_the_slot_number_matches(self):
        value=analysis();value['pose']['slots'][0]['photo_id']=999
        value['measurement_quality']['slots'][0]['photo_id']=999
        before=copy.deepcopy(value)
        result=_posture_results(value,value['snapshot']['capture']['slots'])[0]
        self.assertEqual(result['angles'],[])
        self.assertIsNone(result['landmark_count'],'missing ownership must not be represented as measured zero points')
        self.assertIn('PHOTO_OWNER_MISMATCH',result['pose_diagnostic_codes'])
        self.assertIsNone(result['measurement_quality']['mean_confidence'])
        self.assertEqual(value,before)

    def test_valid_exact_owner_wins_and_an_unambiguous_legacy_row_can_be_read(self):
        value=analysis();value['pose']['slots'].append(dict(value['pose']['slots'][0],photo_id=999,angles=[]))
        result=_posture_results(value,value['snapshot']['capture']['slots'])[0]
        self.assertEqual(result['angles'][0]['value_deg'],33.3)
        value=analysis();value['pose']['slots'][0].pop('photo_id')
        self.assertEqual(_posture_results(value,value['snapshot']['capture']['slots'])[0]['angles'][0]['value_deg'],33.3)

    def test_duplicate_owned_pose_rows_are_not_arbitrarily_selected(self):
        value=analysis();value['pose']['slots'].append(copy.deepcopy(value['pose']['slots'][0]))
        result=_posture_results(value,value['snapshot']['capture']['slots'])[0]
        self.assertEqual(result['angles'],[])
        self.assertIn('PHOTO_OWNER_MISMATCH',result['pose_diagnostic_codes'])

    def test_excel_rejects_foreign_and_orphan_angles_and_keeps_valid_angles(self):
        for kind in ('foreign','orphan'):
            with self.subTest(kind=kind):
                value=analysis()
                bad=dict(slot_no=1 if kind=='foreign' else 777,photo_id=999,status='VALID',points=[],world_angles=[],
                    angles=[dict(side='LEFT',angle_code='TRUNK_TILT_VERT',value_deg=111.1,min_confidence=.9)])
                if kind=='foreign':value['pose']['slots']=[bad]
                else:value['pose']['slots'].append(bad)
                sheet=_posture(dict(tasks=[dict(name='합성 작업',analysis=value,source=value['snapshot'])]))
                values=cells(sheet)
                self.assertNotIn(111.1,values)
                self.assertTrue(any('사진 연결' in str(item) for item in values))
                if kind=='orphan':self.assertIn(33.3,values)

    def test_a_foreign_reba_row_is_not_printed_under_a_valid_photo_label(self):
        value=analysis();value['reba']['slots']=[dict(slot_no=1,photo_id=999,total=14,risk='VERY_HIGH')]
        sheet=_posture(dict(tasks=[dict(name='합성 작업',analysis=value,source=value['snapshot'])]))
        self.assertNotIn('14점',cells(sheet))

    def test_quality_never_falls_back_to_an_explicitly_different_photo(self):
        value=analysis();value['measurement_quality']['slots'][0]['photo_id']=999
        self.assertEqual(_measurement_text(value,1),'')
        value['measurement_quality']['slots'][0]['photo_id']=7
        self.assertIn('27/33',_measurement_text(value,1))

    def test_3d_usage_follows_current_draft_refs_rather_than_candidate_presence(self):
        value=analysis()
        angle=dict(side='LEFT',angle_code='ELBOW_FLEX_3D',value_deg=57.2,min_confidence=.9)
        value['pose']['slots'][0]['world_angles']=[angle]
        ref=dict(angle,coordinate_space='INFERRED_WORLD_3D',used_for_reba=True)
        candidate=dict(scope='LEFT',field='lower_arm_base',proposed_value=2,angles=[ref],estimated=True,measurement_method='INFERRED_WORLD_3D')
        row=dict(slot_no=1,photo_id=7,status='INCOMPLETE',candidates=[candidate],current_score=dict(total=6,risk='MEDIUM',kind='WITH_ASSUMPTIONS'))
        value['reba']['slots']=[row]
        result=lambda:_posture_results(value,value['snapshot']['capture']['slots'])[0]
        self.assertFalse(result()['inferred_world_angles'][0]['used_for_reba'],'an available candidate is not proof that it was applied')
        row['current_score']['measurement_refs']=[dict(scope='LEFT',field='lower_arm_base',angles=[ref],estimated=True,measurement_method='INFERRED_WORLD_3D')]
        self.assertTrue(result()['inferred_world_angles'][0]['used_for_reba'])
        self.assertEqual(result()['candidates'][0]['angle_refs'][0]['coordinate_space'],'INFERRED_WORLD_3D')
        sheet=lambda:_posture(dict(tasks=[dict(name='작업',analysis=value,source=value['snapshot'])]))
        self.assertTrue(any('현재 REBA 초안에 사용' in str(item) for item in cells(sheet())))
        self.assertIn('3D 추정 팔꿈치 굽힘',cells(sheet()),'a missing optional legacy angle label must not break export')
        row['current_score'].pop('measurement_refs')  # The selected manual value won instead.
        self.assertFalse(result()['inferred_world_angles'][0]['used_for_reba'])
        self.assertTrue(any('현재 REBA 점수에 사용하지 않음' in str(item) for item in cells(sheet())))

    def test_3d_usage_requires_exact_side_code_value_and_not_a_confirmed_score(self):
        value=analysis();angle=dict(side='LEFT',angle_code='ELBOW_FLEX_3D',value_deg=57.2,min_confidence=.9)
        value['pose']['slots'][0]['world_angles']=[angle]
        ref=dict(angle,coordinate_space='INFERRED_WORLD_3D',used_for_reba=True)
        row=dict(slot_no=1,photo_id=7,current_score=dict(kind='WITH_ASSUMPTIONS',measurement_refs=[dict(angles=[ref])]))
        value['reba']['slots']=[row]
        used=lambda:_posture_results(value,value['snapshot']['capture']['slots'])[0]['inferred_world_angles'][0]['used_for_reba']
        for key,replacement in (('side','RIGHT'),('angle_code','KNEE_FLEX_3D'),('value_deg',57.3),('coordinate_space','IMAGE_2D'),('used_for_reba',False)):
            previous=ref[key];ref[key]=replacement
            self.assertFalse(used(),key);ref[key]=previous
        row['current_score']['kind']='CONFIRMED'
        self.assertFalse(used(),'estimated measurements must not imply a human confirmed score')

    def test_null_and_weak_3d_results_keep_their_diagnostics_in_ai_and_excel(self):
        value=analysis();value['pose']['slots'][0]['world_angles']=[
            dict(side='LEFT',angle_code='ELBOW_FLEX_3D',value_deg=None,min_confidence=.2,diagnostic='팔꿈치가 가려짐'),
            dict(side='LEFT',angle_code='KNEE_FLEX_3D',value_deg=66.8,min_confidence=.2)]
        output=_posture_results(value,value['snapshot']['capture']['slots'])[0]['inferred_world_angles']
        self.assertEqual(output[0]['diagnostic'],'팔꿈치가 가려짐')
        self.assertFalse(output[0]['used_for_reba'])
        values=cells(_posture(dict(tasks=[dict(name='작업',analysis=value,source=value['snapshot'])])))
        self.assertIn('측정 불가',values)
        self.assertTrue(any('팔꿈치가 가려짐' in str(item) for item in values))
        self.assertTrue(any('관절이 잘 안 보여 참고용' in str(item) for item in values))


if __name__=='__main__':unittest.main()
