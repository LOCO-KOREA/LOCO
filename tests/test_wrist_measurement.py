"""Wrist image-plane proxy boundaries, abstention, ownership and question reasons."""
import copy
import math
import unittest
from unittest.mock import patch
from ergo.engine.wrist_angles import angles
from ergo.engine.joint_angles import angles as body_angles
from ergo.engine.reba_scoring import candidates
from ergo.engine.quick_assess import _confirmed_slot, side_measure
from ergo.engine.task_defaults import task_input, default_settings
from ergo.pose_contract import MEDIAPIPE_NAMES, COCO_NAMES, WRIST_POLICY, WRIST_REASONS
from ergo.intake import facts, planner, contract


def points(degrees=0,spread=2,hand=80,forearm=200):
    result={name:dict(name=name,x_px=100,y_px=100,confidence=.99,visibility=.99,presence=.99) for name in MEDIAPIPE_NAMES}
    radians=math.radians(degrees)
    for side in ('left','right'):
        result[side+'_elbow'].update(x_px=300-forearm,y_px=300)
        result[side+'_wrist'].update(x_px=300,y_px=300)
        for joint,length,offset in [('index',hand,spread),('pinky',hand*.94,-spread),('thumb',hand*.6,0)]:
            result[side+'_'+joint].update(x_px=300+length*math.cos(radians)-offset*math.sin(radians),y_px=300+length*math.sin(radians)+offset*math.cos(radians))
    return list(result.values())


def measure(value=0,**kwargs):
    return angles(points(value),800,800,camera_side='LEFT',orientation='SIDE',**kwargs)[0]


class WristGeometry(unittest.TestCase):
    def test_both_categories_and_extension_are_original_image_2d_only(self):
        for degree,category in [(0,1),(5,1),(30,2),(-30,2),(70,2)]:
            with self.subTest(degree=degree):
                row=measure(degree)
                self.assertTrue(row['measurement']['auto_eligible'],row)
                self.assertAlmostEqual(row['value_deg'],abs(degree),delta=2)
                candidate=next(item for item in candidates(_confirmed_slot('LEFT','SCREEN_RIGHT'),dict(angles=[row]),'LEFT') if item['field']=='wrist_base' and item['scope']=='LEFT')
                self.assertEqual(candidate['proposed_value'],category)
                self.assertFalse(candidate['review_reasons'])
                self.assertFalse(row['measurement']['used_world_coordinates'])
        original=points(30);changed=copy.deepcopy(original)
        for point in changed:point.update(z_normalized=9999,x_m=-999,y_m=222,z_m=333)
        self.assertEqual(angles(original,800,800,camera_side='LEFT',orientation='SIDE'),angles(changed,800,800,camera_side='LEFT',orientation='SIDE'))

    def test_fifteen_degree_category_and_five_degree_margin_are_unchanged(self):
        for degree,category in [(14.9,1),(15,1),(15.1,2),(10,1),(20,2)]:
            row=measure(degree)
            self.assertEqual(row['diagnostic_code'],'WRIST_BOUNDARY',row)
            candidate=next(item for item in candidates(_confirmed_slot('LEFT','SCREEN_RIGHT'),dict(angles=[row]),'LEFT') if item['field']=='wrist_base' and item['scope']=='LEFT')
            self.assertEqual(candidate['proposed_value'],category)
            self.assertIn('BOUNDARY_REVIEW',candidate['review_reasons'])
            self.assertFalse(row['measurement']['auto_eligible'])

    def test_occluded_missing_outside_short_and_palm_front_abstain(self):
        cases=[]
        low=points(30);next(p for p in low if p['name']=='left_index')['visibility']=.2;cases.append((low,'WRIST_POINTS_LOW_CONFIDENCE'))
        absent=[p for p in points(30) if p['name']!='left_thumb'];cases.append((absent,'WRIST_MISSING_POINTS'))
        outside=points(30);next(p for p in outside if p['name']=='left_pinky')['x_px']=800;cases.append((outside,'WRIST_HAND_OUT_OF_FRAME'))
        cases.append((points(30,hand=8),'WRIST_PROJECTION_SHORT'))
        cases.append((points(30,spread=25),'WRIST_PLANE_UNCLEAR'))
        cases.append((points(30,hand=24,forearm=40),'WRIST_UNSTABLE'))
        for sample,code in cases:
            with self.subTest(code=code):
                row=angles(sample,800,800,camera_side='LEFT',orientation='SIDE')[0]
                self.assertIsNone(row['value_deg']);self.assertEqual(row['diagnostic_code'],code)
                self.assertFalse(row['measurement']['auto_eligible'])
        self.assertEqual(angles(points(),800,800,camera_side='LEFT',orientation='FRONT')[0]['diagnostic_code'],'WRIST_DIRECTION_UNCONFIRMED')
        self.assertIsNone(angles(points(),800,800,camera_side='RIGHT',orientation='SIDE')[0]['value_deg'],'the far hand is never copied from the near hand')

    def test_movenet_does_not_gain_fabricated_hand_points_or_candidates(self):
        coco=[p for p in points() if p['name'] in COCO_NAMES]
        self.assertEqual(angles(coco,800,800,camera_side='LEFT',orientation='SIDE'),[])
        rows=body_angles(coco,'SCREEN_RIGHT',800,800)
        self.assertEqual(len(rows),14)
        self.assertEqual(len(candidates(_confirmed_slot('LEFT','SCREEN_RIGHT'),dict(angles=rows),'LEFT')),6)

    def test_angle_without_observability_proof_or_from_world_space_is_not_a_candidate(self):
        for proof in ({},dict(coordinate_space='INFERRED_WORLD_3D',auto_eligible=True,used_world_coordinates=True)):
            row=dict(side='LEFT',angle_code='WRIST_FLEX_2D',value_deg=30,min_confidence=.99,measurement=proof)
            candidate=next(item for item in candidates(_confirmed_slot('LEFT','SCREEN_RIGHT'),dict(angles=[row]),'LEFT') if item['field']=='wrist_base' and item['scope']=='LEFT')
            self.assertIsNone(candidate['proposed_value'])

    def test_singular_and_nonfinite_perturbations_abstain_without_losing_other_body_angles(self):
        sample=points(30,spread=.1,hand=20,forearm=24)
        row=angles(sample,12000,12000,camera_side='LEFT',orientation='SIDE')[0]
        self.assertIsNone(row['value_deg']);self.assertEqual(row['diagnostic_code'],'WRIST_UNSTABLE')
        rows=body_angles(sample,'SCREEN_RIGHT',12000,12000,camera_side='LEFT',orientation='SIDE')
        self.assertEqual(len(rows),16)
        self.assertIsNotNone(next(row for row in rows if row['angle_code']=='ELBOW_FLEX' and row['side']=='LEFT')['value_deg'])
        for values in ([float('nan')],[30,float('inf')]):
            with patch('ergo.engine.wrist_angles._bend',side_effect=values):
                row=angles(points(30),800,800,camera_side='LEFT',orientation='SIDE')[0]
                self.assertIsNone(row['value_deg']);self.assertEqual(row['diagnostic_code'],'WRIST_UNSTABLE')


class WristProjection(unittest.TestCase):
    def preview(self,degree=30):
        rows,measured=side_measure(points(degree),800,800,default_settings()['analysis'],'LEFT','SCREEN_RIGHT','LEFT')
        return dict(views=dict(LEFT=dict(guess=dict(orientation='SIDE',camera_side='LEFT'),engine=dict(provider='mediapipe'))),measured=measured,signals={}),rows

    def test_success_persists_existing_manual_field_and_excludes_only_flexion_question(self):
        preview,_=self.preview();known=facts.apply_answers({},[dict(target='context',value='YES')])
        saved=facts.add_photo_facts(known,preview,dict(LEFT=7))
        item=saved[contract.key('manual.LEFT.wrist_base')]
        self.assertEqual(item['value'],2);self.assertEqual(item['state'],'KNOWN');self.assertEqual(item['source'],'POSE')
        projected=facts.project(task_input({}),saved,dict(LEFT=7),preview)
        row=next(row for row in projected['manual'] if row['scope']=='LEFT' and row['field']=='wrist_base')
        self.assertEqual(row['value'],2);self.assertEqual(row['photo_id'],7);self.assertEqual(row['source'],'AUTO_ACCEPTED')
        targets={item['target'] for item in planner.assess(projected,saved,dict(LEFT=7))['candidates']}
        self.assertNotIn('manual.LEFT.wrist_base',targets)
        self.assertIn('manual.LEFT.wrist_deviated_or_twisted',targets)
        self.assertFalse(any(item['target'].endswith('wrist_deviated_or_twisted') for item in saved.values()))
        self.assertIn('measurement',item['angles'][0])

    def test_direct_values_and_direct_unknown_always_take_precedence(self):
        preview,_=self.preview()
        for value in (1,None):
            initial=facts.apply_answers({},[dict(target='context',value='YES'),dict(target='manual.LEFT.wrist_base',value=value)])
            saved=facts.add_photo_facts(initial,preview,dict(LEFT=7))
            original=initial[contract.key('manual.LEFT.wrist_base')];bound=saved[contract.key('manual.LEFT.wrist_base')]
            self.assertEqual({key:bound[key] for key in original},original)
            self.assertEqual(bound['photo_id'],7)

    def test_failed_measurement_and_boundary_retain_specific_reason_in_plan_and_form(self):
        for code in ('WRIST_PLANE_UNCLEAR','WRIST_HAND_OUT_OF_FRAME','WRIST_POINTS_LOW_CONFIDENCE','WRIST_BOUNDARY'):
            preview,rows=self.preview(15 if code=='WRIST_BOUNDARY' else 30)
            if code!='WRIST_BOUNDARY':
                preview['measured']=[item for item in preview['measured'] if item['field']!='wrist_base']
                preview['measurement_issues']=[dict(scope='LEFT',field='wrist_base',view='LEFT',code=code,reason=WRIST_REASONS[code],angle=dict(side='LEFT',angle_code=WRIST_POLICY['angle_code'],value_deg=None))]
            saved=facts.add_photo_facts(facts.apply_answers({},[dict(target='context',value='YES')]),preview,dict(LEFT=7))
            projected=facts.project(task_input({}),saved,dict(LEFT=7),preview)
            candidates_=planner.assess(projected,saved,dict(LEFT=7))['candidates']
            target='manual.LEFT.wrist_base';candidate=next(item for item in candidates_ if item['target']==target)
            self.assertEqual(candidate['reason'],WRIST_REASONS[code])
            chosen=planner.choose([candidate],[dict(target=target,reason='결과 계산 정보 없음')])
            self.assertEqual(chosen[0]['reason'],WRIST_REASONS[code])
            form=next(item for item in planner.form_fields(projected,saved,dict(LEFT=7),candidates_) if item['target']==target)
            self.assertEqual(form['reason'],WRIST_REASONS[code])
            self.assertFalse(any(item['field']=='wrist_base' for item in projected['manual']))

    def test_unchanged_unknown_photo_evidence_is_idempotent_but_owner_and_policy_changes_are_new(self):
        preview,_=self.preview();preview['measured']=[]
        issue=dict(scope='LEFT',field='wrist_base',view='LEFT',code='WRIST_PLANE_UNCLEAR',reason=WRIST_REASONS['WRIST_PLANE_UNCLEAR'],angle=dict(side='LEFT',angle_code='WRIST_FLEX_2D',value_deg=None,measurement=dict(policy_version='WRIST_IMAGE_2D_V1')))
        preview['measurement_issues']=[issue]
        saved=facts.add_photo_facts({},preview,dict(LEFT=7))
        for _ in range(3):self.assertEqual(facts.add_photo_facts(saved,preview,dict(LEFT=7)),saved)
        for changed,views in [(copy.deepcopy(preview),dict(LEFT=8)),(copy.deepcopy(preview),dict(LEFT=7))]:
            if views['LEFT']==7:changed['measurement_issues'][0]['angle']['measurement']['policy_version']='new-policy'
            fresh=facts.add_photo_facts(saved,changed,views)
            self.assertNotEqual(fresh[contract.key('manual.LEFT.wrist_base')],saved[contract.key('manual.LEFT.wrist_base')])


if __name__=='__main__': unittest.main()
