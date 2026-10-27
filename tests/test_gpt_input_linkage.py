"""Stored photo inputs and projected scores reach explanations without private data."""
import copy
import json
import unittest

from ergo.engine.reba_scoring import calculate_reba, project_score_continuity
from ergo.gpt import client, payload


def source_analysis(manual=()):
    slots=[dict(slot_no=slot_no,photo_id=photo_id,analysis_target=True,camera_side='LEFT',
        forward_direction='SCREEN_LEFT',side_view_verified='YES',
        observation=dict(load_state='MEASURED',measured_load_kg=20)) for slot_no,photo_id in ((17,7711),(28,8822))]
    rows=[dict(slot_no=17,photo_id=7711,scope=scope,field=field,value=value,source='INTERVIEW',
        evidence=dict(source='INTERVIEW',text='private-entered-text',observed_at='private-time'))
        for scope,field,value in manual]
    snapshot=dict(schema_version='2.0',task_id=3311,task_name='private-task-name',
        settings=dict(pose_model=dict(provider='mediapipe'),burden_rule='B',reba_rule='R',posture_profile=dict(version='P')),
        conditions=dict(intake_session=dict(photo_observations=dict(observations=[
            dict(photo_id=7711,scope='COMMON',field='trunk_base',value=3),
            dict(photo_id=7711,scope='LEFT',field='upper_arm_base',value=3)]))),
        manual=rows,capture=dict(slots=slots),photos=[])
    return dict(snapshot=snapshot,reba=calculate_reba(snapshot,None),judgment=dict(judgments=[]),
        currentness='CURRENT',pose=None,tags=[],module_states=dict(reba='INCOMPLETE'))


class GptInputLinkage(unittest.TestCase):
    def test_each_photo_gets_its_engine_score_and_actual_grip_activity_answers(self):
        source=source_analysis([
            ('LEFT','coupling','UNACCEPTABLE'),('RIGHT','coupling','UNACCEPTABLE'),
            ('COMMON','static_over_1min','NO'),('COMMON','shock_force','NO'),
            ('COMMON','small_repeat_over_4min','YES')])
        before=copy.deepcopy(source)
        expected=project_score_continuity(source)
        summary=payload.build_numeric_summary(source)
        first,second=summary['posture_results']
        self.assertEqual(first['current_score']['total'],expected['reba']['slots'][0]['current_score']['total'])
        self.assertEqual(second['current_score']['total'],2)
        self.assertGreater(first['current_score']['total'],second['current_score']['total'])
        self.assertEqual(first['current_score']['kind'],'WITH_ASSUMPTIONS')
        recorded={(item['scope'],item['field']):item['value'] for item in first['recorded_inputs']}
        self.assertEqual(recorded[('LEFT','coupling')],'UNACCEPTABLE')
        self.assertEqual(recorded[('RIGHT','coupling')],'UNACCEPTABLE')
        self.assertEqual(recorded[('COMMON','shock_force')],'NO')
        self.assertEqual(recorded[('COMMON','static_over_1min')],'NO')
        self.assertEqual(recorded[('COMMON','small_repeat_over_4min')],'YES')
        self.assertEqual(second['recorded_inputs'],[],'another photo cannot borrow the first photo answers')
        self.assertEqual(source,before)

    def test_known_inputs_do_not_send_ids_quotes_paths_or_invalid_values(self):
        source=source_analysis([('LEFT','coupling','UNACCEPTABLE')])
        source['snapshot']['manual'] += [
            dict(slot_no=17,photo_id=7711,scope='COMMON',field='seated',value='NO',source=r'C:\private-source'),
            dict(slot_no=17,photo_id=7711,scope='COMMON',field='neck_base',value=None,source='INTERVIEW'),
            dict(slot_no=17,photo_id=7711,scope='COMMON',field='trunk_base',value=True,source='INTERVIEW'),
            dict(slot_no=17,photo_id=7711,scope='LEFT',field='wrist_base',value=99,source='INTERVIEW'),
            dict(slot_no=17,photo_id=7711,scope='LEFT',field='worker_code',value='private-worker',source='INTERVIEW'),
            dict(slot_no=99,photo_id=7711,scope='RIGHT',field='coupling',value='FAIR',source='INTERVIEW'),
            dict(slot_no=17,photo_id=9900,scope='RIGHT',field='coupling',value='GOOD',source='INTERVIEW')]
        summary=payload.build_numeric_summary(source)
        recorded=summary['posture_results'][0]['recorded_inputs']
        self.assertEqual([(r['scope'],r['field'],r['value']) for r in recorded],[
            ('LEFT','coupling','UNACCEPTABLE'),('COMMON','seated','NO')])
        self.assertIsNone(recorded[1]['source'])
        encoded=json.dumps(summary,ensure_ascii=False)
        for secret in ('7711','8822','9900','3311','private-entered-text','private-time','private-task-name','private-worker','private-source'):
            self.assertNotIn(secret,encoded)
        self.assertNotIn('photo_id',encoded)
        self.assertNotIn('slot_no',encoded)

    def test_conflicting_duplicate_inputs_are_not_arbitrarily_chosen(self):
        source=source_analysis([('LEFT','coupling','UNACCEPTABLE'),('LEFT','coupling','GOOD')])
        summary=payload.build_numeric_summary(source)
        self.assertEqual(summary['posture_results'][0]['recorded_inputs'],[])

    def test_prompt_explains_recorded_inputs_without_owning_the_score(self):
        self.assertIn('recorded_inputs',client.SYSTEM_PROMPT)
        self.assertIn('current_score',client.SYSTEM_PROMPT)
        self.assertIn('다시 계산',client.SYSTEM_PROMPT)


if __name__=='__main__':unittest.main()
