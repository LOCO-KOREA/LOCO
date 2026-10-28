"""Measured values feed the draft once; uncertainty is kept for result editing."""
import copy
import unittest
from unittest.mock import patch

from backend.engine import quick_assess
from backend.engine.reba_scoring import calculate_reba, candidates
from backend.engine.task_defaults import default_settings, task_input
from backend.intake import contract, facts, photo_facts, planner
from test_photo_fact_ownership import observation, preview


class PoseDraftReuse(unittest.TestCase):
    views = dict(LEFT=101)

    def saved(self, rows, answers=()):
        data=preview(rows,self.views)
        seed=facts.apply_answers({},[dict(target='context',value='YES'),dict(target='load',value='UNLOADED'),*answers])
        saved=facts.add_photo_facts(seed,data,self.views)
        task=facts.project(task_input({}),saved,self.views,data)
        task['conditions'][contract.SESSION_KEY]=dict(facts=saved,views=self.views,photo_observations=photo_facts.snapshot(data,self.views))
        return task,saved,data

    def test_identical_fresh_proof_restores_invalidated_values_and_stays_idempotent(self):
        rows=[observation('LEFT','COMMON','trunk_base',3,40),observation('LEFT','LEFT','lower_arm_base',2,50)]
        _,saved,data=self.saved(rows)
        for f in saved.values():
            if f.get('source')=='POSE':f.update(value=None,state='UNKNOWN',reask=True)
        restored=facts.add_photo_facts(saved,data,self.views)
        for target,value in [('manual.COMMON.trunk_base',3),('manual.LEFT.lower_arm_base',2)]:
            item=restored[target+'@photo:101']
            self.assertEqual((item['value'],item['state']),(value,'KNOWN'))
            self.assertNotIn('reask',item)
        self.assertEqual(facts.add_photo_facts(restored,data,self.views),restored)

    def test_boundary_and_low_confidence_values_feed_only_draft_without_reasking(self):
        fields=[('COMMON','trunk_base',3,40),('COMMON','neck_base',2,25),('COMMON','knee_band','OVER_60',70),
                ('LEFT','upper_arm_base',3,60),('LEFT','lower_arm_base',2,50),('LEFT','wrist_base',2,20)]
        rows=[dict(observation('LEFT',scope,field,value,angle),boundary_review=True) for scope,field,value,angle in fields]
        rows[1].update(estimated=True,measurement_method='NECK_FLEX_TRUNK_PROXY')
        rows[4].update(boundary_review=False,low_confidence=True)
        task,saved,_=self.saved(rows)
        assessment=planner.assess(task,saved,self.views)
        pending={q['identity'] for q in assessment['candidates']}
        forms={q['identity']:q for q in planner.form_fields(task,saved,self.views,assessment['candidates'])}
        for scope,field,_,_ in fields:
            identity=f'manual.{scope}.{field}@photo:101'
            self.assertEqual(saved[identity]['state'],'ESTIMATED')
            self.assertNotIn(identity,pending)
            self.assertTrue(forms[identity]['measurement_applied'])
        self.assertFalse(any(row['field'] in {f[1] for f in fields} for row in task['manual']))
        result=calculate_reba(task,None)['slots'][0]
        self.assertEqual(result['status'],'INCOMPLETE')
        self.assertGreater(result['score_so_far']['total'],1)
        self.assertNotIn('common.neck_base',result['score_so_far']['assumed'])

    def test_missing_wrist_value_stays_unknown_and_user_answer_keeps_priority(self):
        rows=[observation('LEFT','LEFT','upper_arm_base',3,60)]
        task,saved,data=self.saved(rows,[dict(target='manual.LEFT.upper_arm_base',value=1)])
        self.assertEqual(saved['manual.LEFT.upper_arm_base@photo:101']['source'],'USER')
        self.assertEqual(saved['manual.LEFT.upper_arm_base@photo:101']['value'],1)
        self.assertIn('manual.LEFT.wrist_base@photo:101',{q['identity'] for q in planner.assess(task,saved,self.views)['candidates']})
        forged=dict(saved['manual.LEFT.upper_arm_base@photo:101'],source='POSE',state='ESTIMATED')
        forged['photo_proof']=dict(rows[0],photo_id=102)
        self.assertFalse(photo_facts.is_measured_candidate(forged))

    def test_neck_proxy_is_near_side_estimate_with_original_angle(self):
        settings=default_settings()['analysis']
        for value,expected in [(10,1),(20,1),(30,2),(-10,'2_EXTENSION')]:
            rows=[dict(side='LEFT',angle_code='NECK_FLEX_TRUNK_PROXY',value_deg=value,min_confidence=.95),
                  dict(side='RIGHT',angle_code='NECK_FLEX_TRUNK_PROXY',value_deg=60,min_confidence=.99)]
            with self.subTest(value=value),patch('backend.engine.quick_assess.joint_angles',return_value=rows):
                _,measurements=quick_assess.side_measure([],800,800,settings,'LEFT','SCREEN_RIGHT')
                reading=next(m for m in measurements if m['field']=='neck_base')
                self.assertEqual(reading['value'],expected)
                self.assertTrue(reading['estimated'])
                self.assertEqual(reading['measurement_method'],'NECK_FLEX_TRUNK_PROXY')
                self.assertEqual(reading['angles'][0]['value_deg'],value)
                self.assertEqual(reading['angles'][0]['side'],'LEFT')
                _,saved,_=self.saved([reading|dict(view='LEFT')])
                self.assertEqual(saved['manual.COMMON.neck_base@photo:101']['state'],'ESTIMATED')

    def test_foreign_pose_same_slot_number_cannot_supply_any_candidate(self):
        task,_,_=self.saved([])
        foreign=dict(slots=[dict(slot_no=1,photo_id=102,angles=[dict(side='LEFT',angle_code='TRUNK_TILT_VERT',value_deg=80,min_confidence=.99)])])
        result=calculate_reba(task,foreign)['slots'][0]
        self.assertTrue(all(c['proposed_value'] is None for c in result['candidates']))
        self.assertNotIn('score_so_far',result)


if __name__=='__main__':unittest.main()
