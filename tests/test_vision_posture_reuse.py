"""Visible API posture categories are inputs, never generated REBA totals."""
import copy
import unittest
from unittest.mock import patch
from ergo.vision import contract
from ergo.service import photo_vision
from tests import test_photo_vision as fixtures


class VisionPostureReuse(unittest.TestCase):
    def record(self, candidates):
        raw=fixtures.response()
        raw['observations']['wrist_right'].update(status='OBSERVED',confidence=.97,reason='')
        raw['manual_candidates']=[]
        for scope,field,value in candidates:
            observation=contract.MANUAL_FIELDS[(scope,field)]
            raw['manual_candidates'].append(dict(scope=scope,field=field,value=value,observation=observation,
                status='OBSERVED',confidence=.97,evidence=raw['observations'][observation]['evidence']))
        return dict(status='OBSERVED',raw_response=raw,photo_id=1,view='LEFT',photo_label='왼쪽 사진',signature='fixture')

    def test_neck_both_arms_wrists_and_grips_are_reused_as_typed_inputs(self):
        rows=[('COMMON','neck_base','NECK_OVER_20')]
        for side in ('LEFT','RIGHT'):
            rows.extend([(side,'upper_arm_base','UPPER_45_90'),(side,'lower_arm_base','ELBOW_60_100'),
                         (side,'wrist_base','WRIST_OVER_15'),(side,'coupling','POOR')])
        state=dict(facts={});record=self.record(rows)
        photo_vision._merge_candidates(state,record)
        for scope,field,value in rows:
            item=state['facts'][f'manual.{scope}.{field}@photo:1']
            self.assertEqual(item['value'],contract.manual_value(scope,field,value))
            self.assertEqual((item['source'],item['photo_id']),('VISION',1))
            self.assertEqual(item['state'],'ESTIMATED')
            self.assertEqual(item['vision_proof']['value'],value)
        self.assertFalse(any('total' in key for key in state['facts']))

    def test_moderate_visible_category_and_paraphrased_evidence_remain_estimates(self):
        record=self.record([('LEFT','coupling','FAIR')]);item=record['raw_response']['manual_candidates'][0]
        item.update(confidence=.77,evidence='보이는 왼손이 상자 앞면을 감싸고 있습니다.')
        record['raw_response']['observations']['holding']['confidence']=.94
        state=dict(facts={});photo_vision._merge_candidates(state,record)
        saved=state['facts']['manual.LEFT.coupling@photo:1']
        self.assertEqual((saved['state'],saved['value']),('ESTIMATED','FAIR'))
        self.assertEqual(saved['vision_proof']['evidence'],item['evidence'])
        self.assertNotEqual(saved['vision_observation_evidence'],item['evidence'])
        item['confidence']=.49;state=dict(facts={});photo_vision._merge_candidates(state,record)
        self.assertNotIn('manual.LEFT.coupling@photo:1',state['facts'])

    def test_wrong_body_category_hidden_joint_and_duplicate_values_are_rejected(self):
        for fault in ('wrong_category','hidden','conflicting','no_evidence'):
            record=self.record([('LEFT','wrist_base','WRIST_OVER_15')]);raw=record['raw_response'];item=raw['manual_candidates'][0]
            if fault=='wrong_category':item['value']='UPPER_45_90'
            elif fault=='hidden':raw['observations']['wrist_left'].update(status='NOT_VISIBLE',confidence=None)
            elif fault=='no_evidence':item['evidence']=''
            else:raw['manual_candidates'].append(dict(item,value='WRIST_UP_TO_15'))
            state=dict(facts={});photo_vision._merge_candidates(state,record)
            with self.subTest(fault=fault):self.assertNotIn('manual.LEFT.wrist_base@photo:1',state['facts'])

    def test_whole_object_holding_does_not_invent_the_hidden_other_hand_grip(self):
        record=self.record([('RIGHT','coupling','FAIR')])
        record['raw_response']['observations']['wrist_right'].update(status='NOT_VISIBLE',confidence=None)
        state=dict(facts={});photo_vision._merge_candidates(state,record)
        self.assertNotIn('manual.RIGHT.coupling@photo:1',state['facts'])

    def test_existing_person_answer_and_mediapipe_known_value_take_priority(self):
        record=self.record([('LEFT','upper_arm_base','UPPER_45_90')])
        for source,value in [('USER',1),('POSE',2)]:
            old=dict(source=source,state='KNOWN',value=value);state=dict(facts={'manual.LEFT.upper_arm_base@photo:1':old})
            photo_vision._merge_candidates(state,copy.deepcopy(record))
            self.assertEqual(state['facts']['manual.LEFT.upper_arm_base@photo:1'],old)

    def test_strict_schema_and_prompt_allow_posture_categories_without_score_field(self):
        schema=contract.response_schema();candidate=schema['properties']['manual_candidates']['items']['properties']
        self.assertIn('coupling',candidate['field']['enum']);self.assertIn('WRIST_OVER_15',candidate['value']['enum'])
        self.assertNotIn('score',schema['properties']);self.assertNotIn('total',candidate)


if __name__=='__main__':unittest.main()
