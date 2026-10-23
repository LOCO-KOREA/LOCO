"""Independent counterexamples for photo identity, provenance, questions and compatibility."""
import copy
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch
from PIL import Image
from ergo.engine import quick_assess
from ergo.engine.task_defaults import task_input
from ergo.intake import contract,facts,planner,photo_facts
from ergo.report.input_trace import InputTrace
from ergo.report.plain import _manual_rows
from ergo.service.application import create_service

def observation(view,scope,field,value,angle):
    return dict(view=view,scope=scope,field=field,value=value,low_confidence=False,boundary_review=False,angles=[dict(side=scope,angle_code='TRUNK_TILT_VERT',value_deg=angle)])

def preview(rows,views):
    return dict(views={view:dict(photo_id=owner,engine=dict(provider='mediapipe'),guess=dict(orientation='SIDE',camera_side=view,forward_direction='SCREEN_RIGHT'),measured=[row for row in rows if row['view']==view],signals={}) for view,owner in views.items()},measured=quick_assess.merge_measured(*[[row] for row in rows]),measurement_issues=[],signals={})

class PhotoOwnership(unittest.TestCase):
    def seed(self):return facts.apply_answers({},[dict(target='context',value='YES'),dict(target='load',value='UNLOADED')])

    def test_secondary_measurements_are_saved_at_their_own_photo_without_filling_primary(self):
        views=dict(LEFT=101,RIGHT=102)
        data=preview([observation('LEFT','LEFT','upper_arm_base',2,25),observation('RIGHT','COMMON','trunk_base',3,40),observation('RIGHT','RIGHT','upper_arm_base',3,60)],views)
        saved=facts.add_photo_facts(self.seed(),data,views);task=facts.project(task_input({}),saved,views,data)
        self.assertEqual(saved['manual.COMMON.trunk_base@photo:102']['photo_id'],102)
        self.assertNotIn('manual.COMMON.trunk_base@default',saved)
        self.assertEqual({(row['photo_id'],row['scope'],row['field'],row['value']) for row in task['manual'] if row['field']!='coupling'}, {(101,'LEFT','upper_arm_base',2),(102,'COMMON','trunk_base',3),(102,'RIGHT','upper_arm_base',3)})
        assessment=planner.assess(task,saved,views);pending={row['identity'] for row in assessment['candidates']}
        self.assertIn('manual.COMMON.trunk_base@photo:101',pending)
        self.assertNotIn('manual.COMMON.trunk_base@photo:102',pending)
        self.assertEqual([slot['photo_id'] for slot in task['capture']['slots'] if slot['analysis_target']],[101])

    def test_identical_values_from_different_photos_keep_their_own_quote_in_the_report(self):
        views=dict(LEFT=101,RIGHT=102);data=preview([observation('LEFT','COMMON','trunk_base',3,35),observation('RIGHT','COMMON','trunk_base',3,50)],views)
        saved=facts.add_photo_facts(self.seed(),data,views);task=facts.project(task_input({}),saved,views,data);task['conditions'][contract.SESSION_KEY]=dict(facts=saved)
        trace=InputTrace(task)
        self.assertEqual(trace.lookup('manual',3,scope='COMMON',field='trunk_base',photo_id=101)[1],'사진 자동 측정: 35°')
        self.assertEqual(trace.lookup('manual',3,scope='COMMON',field='trunk_base',photo_id=102)[1],'사진 자동 측정: 50°')
        rows=_manual_rows('작업',task)
        self.assertTrue(any('35°' in str(row) for row in rows));self.assertTrue(any('50°' in str(row) for row in rows))

    def test_legacy_pose_alias_cannot_overwrite_canonical_user_value_or_unknown(self):
        field=next(field for field in contract.fields() if field['target']=='manual.COMMON.trunk_base')
        for value in (None,2):
            canonical=facts.fact(field,value,'USER','사람이 확인한 답',photo_facts.condition(101));canonical['updated_at']='2026-10-23T00:00:00+00:00'
            legacy=facts.fact(field,4,'POSE','예전 사진 추정');legacy['updated_at']='2026-10-24T00:00:00+00:00'
            saved=photo_facts.bind_aliases({contract.key(field['target']):legacy,contract.key(field['target'],canonical['condition']):canonical},dict(LEFT=101))
            current=saved[contract.key(field['target'],canonical['condition'])]
            self.assertEqual({key:current[key] for key in canonical},canonical)

    def test_explicit_new_default_user_edit_updates_only_the_current_primary(self):
        views=dict(LEFT=101,RIGHT=102);data=preview([observation('LEFT','COMMON','trunk_base',3,40),observation('RIGHT','COMMON','trunk_base',4,70)],views)
        saved=facts.add_photo_facts(self.seed(),data,views);edited=facts.apply_answers(saved,[dict(target='manual.COMMON.trunk_base',value=None)])
        saved=photo_facts.bind_aliases(edited,views)
        self.assertEqual(saved['manual.COMMON.trunk_base@photo:101']['source'],'USER')
        self.assertIsNone(saved['manual.COMMON.trunk_base@photo:101']['value']);self.assertEqual(saved['manual.COMMON.trunk_base@photo:102']['value'],4)

    def test_replacing_the_primary_never_reuses_an_old_user_answer(self):
        saved=facts.apply_answers(self.seed(),[dict(target='manual.COMMON.trunk_base',value=2)])
        saved=photo_facts.bind_aliases(saved,dict(LEFT=101));original=copy.deepcopy(saved['manual.COMMON.trunk_base@photo:101'])
        views=dict(LEFT=103);data=preview([observation('LEFT','COMMON','trunk_base',4,70)],views)
        saved=facts.add_photo_facts(saved,data,views)
        self.assertFalse(saved['manual.COMMON.trunk_base@photo:101']['photo_active'])
        self.assertEqual(saved['manual.COMMON.trunk_base@photo:101']['value'],original['value'])
        self.assertEqual(saved['manual.COMMON.trunk_base@default']['photo_id'],103)
        self.assertEqual(saved['manual.COMMON.trunk_base@photo:103']['value'],4)

    def test_failed_measurement_has_a_truthful_quote_and_repeated_reads_are_identical(self):
        views=dict(LEFT=101);data=preview([],views)
        data['measurement_issues']=[dict(scope='LEFT',field='wrist_base',view='LEFT',code='WRIST_POINTS_LOW_CONFIDENCE',reason='사진에서 손 관절이 가려져 손목 각도를 읽지 못했어요.',angle=dict(side='LEFT',angle_code='WRIST_FLEX_2D',value_deg=None))]
        saved=facts.add_photo_facts(self.seed(),data,views);initial=copy.deepcopy(saved)
        for _ in range(3):saved=facts.add_photo_facts(saved,data,views)
        self.assertEqual(saved,initial);item=saved['manual.LEFT.wrist_base@photo:101']
        self.assertNotIn('앉은',item['quote']);self.assertIn('가려져',item['quote'])

    def test_seated_signal_from_a_secondary_photo_is_not_assigned_to_primary(self):
        views=dict(LEFT=101,RIGHT=102);data=preview([],views);data['signals']['seated']=True;data['views']['RIGHT']['signals']['seated']=True
        saved=facts.add_photo_facts(self.seed(),data,views)
        self.assertNotIn('manual.COMMON.seated@photo:101',saved);self.assertEqual(saved['manual.COMMON.seated@photo:102']['value'],'YES')

    def test_front_arm_positive_is_per_body_side_and_small_angles_never_become_no(self):
        xy=dict(left_hip=(0,100),right_hip=(20,100),left_shoulder=(0,50),right_shoulder=(20,50),left_elbow=(-50,50),right_elbow=(20,80),nose=(10,20))
        points=[dict(name=name,x_px=x,y_px=y,confidence=.9) for name,(x,y) in xy.items()]
        rows=quick_assess.front_observations(points)
        arm={row['scope']:row['value'] for row in rows if row['field']=='arm_abducted_or_rotated'}
        self.assertEqual(arm,dict(LEFT='YES',RIGHT=None));self.assertFalse(any(row['value']=='NO' for row in rows))

    def test_known_photo_field_is_not_pending_and_remaining_question_names_its_photo(self):
        views=dict(LEFT=101);data=preview([observation('LEFT','COMMON','trunk_base',3,40)],views)
        saved=facts.add_photo_facts(self.seed(),data,views);task=facts.project(task_input({}),saved,views,data);assessment=planner.assess(task,saved,views)
        self.assertNotIn('manual.COMMON.trunk_base@photo:101',{row['identity'] for row in assessment['candidates']})
        question=next(row for row in assessment['candidates'] if row['target']=='manual.LEFT.wrist_base')
        self.assertIn('왼쪽에서 찍은 사진',question['text']);self.assertNotIn('photo:',question['text'])
        chosen=planner.choose(assessment['candidates'],[dict(target=question['target'],condition='default',text='손목은 어떤가요?',reason='확인이 필요해요.')])[0]
        self.assertIn('왼쪽에서 찍은 사진',chosen['text']);self.assertEqual(chosen['condition'],'photo:101')


class PhotoServiceOwnership(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.directory=Path(self.temp.name)
        self.ctx=create_service(str(self.directory/'loco.db'))
        self.survey=self.ctx.dispatch('create_survey',dict(draft=dict(survey_type='REGULAR',survey_date='2026-10-23',title='사진 소유권 반례')))
        self.task=self.ctx.dispatch('create_task',dict(survey_id=self.survey['survey_id'],draft=dict(task_name='사진 소유권')))
        files=[]
        for name in ('left','right'):
            file=self.directory/(name+'.png');Image.new('RGB',(10,10),'white').save(file);files.append(str(file))
        imported=self.ctx.dispatch('import_photos',dict(task_id=self.task['task_id'],file_paths=files))['added'];self.views=dict(zip(('LEFT','RIGHT'),[row['photo_id'] for row in imported]))
        self.data=preview([observation('LEFT','COMMON','trunk_base',3,35),observation('RIGHT','COMMON','trunk_base',3,50)],self.views)
        self.inference=patch('ergo.service.intake.handle_quick_preview',return_value=self.data);self.inference.start();self.addCleanup(self.inference.stop)
        self.state=self.ctx.dispatch('intake_session',dict(task_id=self.task['task_id'],views=self.views))
        self.state=self.turn([dict(target='context',value='YES')])

    def turn(self,answers):return self.ctx.dispatch('intake_turn',dict(task_id=self.task['task_id'],answers=answers,plan=False))

    def test_late_ai_cannot_overwrite_the_new_user_answer_at_the_same_photo(self):
        owner=self.views['LEFT'];condition=photo_facts.condition(owner);started=threading.Event();release=threading.Event();result=[]
        settings=self.ctx.dispatch('get_settings',{});settings.pop('gpt_key_present',None);settings.update(gpt_enabled=True,gpt_model='fixture');self.ctx.dispatch('update_settings',dict(settings=settings))
        def delayed(*args,**kwargs):
            started.set();release.wait();return dict(answers=[dict(target='manual.COMMON.trunk_base',condition=condition,number=None,text='4',quote='이 사진은 몸통이 크게 굽었어요.')],questions=[]),None
        with patch('ergo.gpt.client.adaptive_intake',side_effect=delayed):
            thread=threading.Thread(target=lambda:result.append(self.ctx.dispatch('intake_turn',dict(task_id=self.task['task_id'],text='이 사진은 몸통이 크게 굽었어요.'))));thread.start();self.assertTrue(started.wait(3))
            saved=self.turn([dict(target='manual.COMMON.trunk_base',condition=condition,value=None)])
            release.set();thread.join(5);self.assertFalse(thread.is_alive())
        current=self.ctx.dispatch('intake_session',dict(task_id=self.task['task_id']))
        fact=next(row for row in current['facts'] if row['identity']=='manual.COMMON.trunk_base@'+condition)
        self.assertIsNone(fact['value']);self.assertEqual(fact['source'],'USER');self.assertEqual(result[0]['reason'],'INPUT_CHANGED')

    def test_removing_another_photo_keeps_the_remaining_users_exact_answer(self):
        owner=self.views['RIGHT'];condition=photo_facts.condition(owner)
        self.turn([dict(target='manual.RIGHT.shoulder_raised',condition=condition,value=None)])
        before=next(row for row in self.ctx.dispatch('intake_session',dict(task_id=self.task['task_id']))['facts'] if row['identity']=='manual.RIGHT.shoulder_raised@'+condition)
        self.ctx.dispatch('delete_photo',dict(photo_id=self.views['LEFT']))
        self.data['views'].pop('LEFT');self.data['measured']=[]
        state=self.ctx.dispatch('intake_session',dict(task_id=self.task['task_id'],views=dict(RIGHT=owner)))
        after=next(row for row in state['facts'] if row['identity']==before['identity'])
        self.assertEqual({key:after[key] for key in ('value','state','source','quote','updated_at')},{key:before[key] for key in ('value','state','source','quote','updated_at')})
        self.assertFalse(any(row['photo_id']==self.views['LEFT'] for row in state['task']['manual']))

if __name__=='__main__':unittest.main()
