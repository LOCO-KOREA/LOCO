"""3D elbow/knee inputs replace the corresponding 2D draft reading once."""
import copy
import unittest
from unittest.mock import patch

from ergo.engine import quick_assess
from ergo.engine.angle_selection import selected_angle
from ergo.engine.reba_scoring import calculate_reba,candidates,project_score_continuity
from ergo.engine.task_defaults import task_input,default_settings
from ergo.intake import contract,facts,photo_facts
from test_photo_fact_ownership import preview


def row(code,value,side='LEFT',**extra):
    return dict(side=side,angle_code=code,value_deg=value,min_confidence=.95,**extra)


def pose():
    image=[row(code,value,side) for side in ('LEFT','RIGHT') for code,value in [('TRUNK_TILT_VERT',40),('UPPER_ARM_FLEX_TRUNK',60),('ELBOW_FLEX',40),('KNEE_FLEX',15)]]
    world=[row(code,value,side,coordinate_space='INFERRED_WORLD_3D',used_for_reba=False) for side in ('LEFT','RIGHT') for code,value in [('ELBOW_FLEX_3D',90),('KNEE_FLEX_3D',75)]]
    return dict(slot_no=1,photo_id=101,angles=image,world_angles=world)


class WorldDraftSelection(unittest.TestCase):
    def measured_task(self,answers=()):
        raw=pose()
        with patch('ergo.engine.quick_assess.joint_angles',return_value=raw['angles']):
            _,measured=quick_assess.side_measure([],800,800,default_settings()['analysis'],'LEFT','SCREEN_RIGHT',world_angles=raw['world_angles'])
        views=dict(LEFT=101);data=preview(measured,views)
        saved=facts.apply_answers({},[dict(target='context',value='YES'),dict(target='load',value='UNLOADED'),*answers])
        saved=facts.add_photo_facts(saved,data,views);task=facts.project(task_input({}),saved,views,data)
        task['conditions'][contract.SESSION_KEY]=dict(facts=saved,views=views,photo_observations=photo_facts.snapshot(data,views))
        return raw,measured,saved,task

    def test_valid_3d_is_selected_once_and_original_pose_is_unchanged(self):
        raw=pose();original=copy.deepcopy(raw)
        result=candidates(quick_assess._confirmed_slot('LEFT','SCREEN_RIGHT'),raw,'LEFT')
        lower=next(r for r in result if r['scope']=='LEFT' and r['field']=='lower_arm_base')
        knee=next(r for r in result if r['field']=='knee_band')
        self.assertEqual(lower['proposed_value'],1);self.assertEqual(knee['proposed_value'],'OVER_60')
        for candidate in (lower,knee):
            self.assertTrue(candidate['estimated'])
            self.assertEqual(candidate['measurement_method'],'INFERRED_WORLD_3D')
            self.assertTrue(all(a['used_for_reba'] for a in candidate['angles']))
            self.assertTrue(all(a['angle_code'].endswith('_3D') for a in candidate['angles']))
        self.assertEqual(raw,original)

    def test_invalid_or_missing_3d_falls_back_to_2d_without_zero(self):
        for changes in [dict(value_deg=None),dict(value_deg=float('nan')),dict(value_deg=10**1000),dict(value_deg=181),dict(min_confidence=.1),dict(coordinate_space='OTHER')]:
            with self.subTest(changes=list(changes)):
                raw=pose();raw['world_angles'][0].update(changes)
                chosen=selected_angle(raw,'LEFT','ELBOW_FLEX',.5)
                self.assertEqual(chosen['angle_code'],'ELBOW_FLEX');self.assertEqual(chosen['value_deg'],40)
        self.assertIsNone(selected_angle(dict(world_angles=[]),'LEFT','ELBOW_FLEX'))

    def test_quick_saved_observation_and_current_draft_share_selected_3d_refs(self):
        raw,measured,saved,task=self.measured_task()
        for field in ('lower_arm_base','knee_band'):
            scope='LEFT' if field=='lower_arm_base' else 'COMMON';identity=f'manual.{scope}.{field}@photo:101'
            item=saved[identity]
            self.assertEqual(item['state'],'ESTIMATED')
            self.assertEqual(item['photo_proof']['measurement_method'],'INFERRED_WORLD_3D')
            self.assertFalse(any(m['field']==field for m in task['manual']))
        reba=calculate_reba(task,dict(slots=[raw]));draft=reba['slots'][0]['score_so_far']
        refs={r['field']:r for r in draft['measurement_refs']}
        for field in ('lower_arm_base','knee_band'):
            self.assertEqual(refs[field]['measurement_method'],'INFERRED_WORLD_3D')
            self.assertTrue(all(a['coordinate_space']=='INFERRED_WORLD_3D' for a in refs[field]['angles']))
        projected=project_score_continuity(dict(snapshot=task,pose=dict(slots=[raw]),reba=reba))
        self.assertEqual(projected['reba']['slots'][0]['current_score']['measurement_refs'],draft['measurement_refs'])

    def test_user_answer_overrides_3d_and_is_not_listed_as_a_used_measurement(self):
        raw,_,saved,task=self.measured_task([dict(target='manual.LEFT.lower_arm_base',value=2)])
        self.assertEqual(saved['manual.LEFT.lower_arm_base@photo:101']['source'],'USER')
        draft=calculate_reba(task,dict(slots=[raw]))['slots'][0]['score_so_far']
        self.assertFalse(any(r['field']=='lower_arm_base' and r['scope']=='LEFT' for r in draft.get('measurement_refs',[])))

    def test_previously_saved_2d_automatic_value_yields_to_estimated_3d(self):
        _,measured,_,_=self.measured_task()
        old=[dict(m,estimated=False,measurement_method='ORIGINAL_IMAGE_2D',value=2,
            angles=[row('ELBOW_FLEX',40)]) if m['field']=='lower_arm_base' else m for m in measured]
        views=dict(LEFT=101)
        seed=facts.apply_answers({},[dict(target='context',value='YES')])
        saved=facts.add_photo_facts(seed,preview(old,views),views)
        self.assertEqual(saved['manual.LEFT.lower_arm_base@photo:101']['state'],'KNOWN')
        refreshed=facts.add_photo_facts(saved,preview(measured,views),views)
        item=refreshed['manual.LEFT.lower_arm_base@photo:101']
        self.assertEqual((item['state'],item['value']),('ESTIMATED',1))
        self.assertEqual(item['photo_proof']['measurement_method'],'INFERRED_WORLD_3D')

    def test_vision_category_enters_same_photo_draft_and_keeps_original_proof(self):
        raw,_,saved,task=self.measured_task()
        definitions={f['target']:f for f in contract.fields()}
        for field,category,value in [('wrist_base','WRIST_OVER_15',2),('coupling','POOR','POOR')]:
            target='manual.LEFT.'+field
            item=facts.fact(definitions[target],value,'VISION','사진 관찰',condition='photo:101')
            item.update(state='ESTIMATED',photo_id=101,measurement_method='AI_PHOTO_CATEGORY',vision_signature='same-photo',vision_confidence=.75,
                vision_proof=dict(scope='LEFT',field=field,value=category,status='OBSERVED',confidence=.75,evidence='실제 사진 관찰'))
            saved[target+'@photo:101']=item
        task['conditions'][contract.SESSION_KEY]['facts']=saved
        task['manual']=[m for m in task['manual'] if m['field']!='coupling']
        slot=task['capture']['slots'][0];slot['observation'].update(load_state='MEASURED',measured_load_kg=20)
        result=project_score_continuity(dict(snapshot=task,pose=dict(slots=[raw]),reba=calculate_reba(task,dict(slots=[raw]))))
        refs=result['reba']['slots'][0]['current_score']['measurement_refs']
        for field in ('wrist_base','coupling'):
            used=next(r for r in refs if r['scope']=='LEFT' and r['field']==field)
            self.assertEqual(used['source'],'VISION');self.assertEqual(used['measurement_method'],'AI_PHOTO_CATEGORY')
            self.assertEqual(used['vision_proof'],saved['manual.LEFT.'+field+'@photo:101']['vision_proof'])
        answered=copy.deepcopy(task)
        answered['manual'].append(dict(slot_no=1,photo_id=101,scope='LEFT',field='wrist_base',value=1,source='INTERVIEW'))
        draft=calculate_reba(answered,dict(slots=[raw]))['slots'][0]['score_so_far']
        self.assertFalse(any(r['field']=='wrist_base' and r['scope']=='LEFT' for r in draft['measurement_refs']))

    def test_photo_specific_refusal_blocks_saved_and_world_readings(self):
        raw,_,_,task=self.measured_task()
        task['manual']=[]
        for field in ('single_person','full_frame','normal_work'):
            refused=copy.deepcopy(task);refused['capture']['slots'][0]['observation'][field]='NO'
            result=calculate_reba(refused,dict(slots=[raw]))['slots'][0]
            self.assertNotIn('score_so_far',result)
            current=project_score_continuity(dict(snapshot=refused,pose=dict(slots=[raw]),reba=dict(slots=[result],summary={})))['reba']['slots'][0]['current_score']
            self.assertEqual(current['total'],1)
            self.assertFalse(current.get('measurement_refs'))


if __name__=='__main__':unittest.main()
