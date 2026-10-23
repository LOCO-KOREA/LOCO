"""Provider contracts, configuration, provenance and real Heavy/Full integration."""
import copy
import hashlib
import json
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from PIL import Image
from ergo import pose_contract as contract
from ergo.pose import engine
from ergo.pose.providers import mediapipe as mp_provider
from ergo.service.application import create_service

ROOT=Path(__file__).resolve().parents[1]
PHOTO=ROOT/'.local/fixtures/tensorflow-movenet-example.jpeg'
HAVE_MODELS=all((ROOT/contract.MODELS[x]['model_path']).is_file() for x in ('mediapipe-heavy','mediapipe-full'))


class PoseContract(unittest.TestCase):
    def test_default_heavy_full_choice_and_topology_are_the_same_shared_contract(self):
        public=contract.public_contract();self.assertEqual(public['defaults']['model_id'],'mediapipe-heavy')
        self.assertEqual(public['models']['mediapipe-full']['point_count'],len(public['landmarks']['mediapipe']))
        self.assertEqual(len(set(contract.MEDIAPIPE_NAMES)),33)
        self.assertTrue(set(contract.COCO_NAMES)<=set(contract.MEDIAPIPE_NAMES))
        self.assertIn(('left_heel','left_foot_index'),contract.topology('mediapipe')[1])

    def test_environment_parameters_select_the_same_model_and_preserve_custom_values(self):
        with patch.dict(os.environ,dict(LOCO_POSE_MODEL_ID='mediapipe-full',LOCO_POSE_CONFIDENCE_MIN='0.72',LOCO_POSE_MODEL_PATH='custom.task',LOCO_POSE_MODEL_SHA256='')):
            selected=contract.defaults()
        self.assertEqual(selected['variant'],'full');self.assertEqual(selected['model_path'],'custom.task');self.assertEqual(selected['confidence_min'],0.72)

    def test_old_movenet_settings_keep_their_engine_and_do_not_become_heavy(self):
        old={k:contract.MODELS['movenet-lightning'][k] for k in ('name','version','preprocess_version','input_size','point_count')};old['confidence_min']=0.61
        self.assertEqual(contract.normalize(old)['model_id'],'movenet-lightning')
        old['preprocess_version']='historical-preprocess'
        self.assertEqual(contract.normalize(old,reading=True)['model_id'],'movenet-lightning')
        with self.assertRaises(ValueError):contract.normalize(old)

    def test_invalid_metadata_probability_path_and_provider_do_not_silently_fall_back(self):
        for change in [dict(model_id='unknown'),dict(point_count=17),dict(confidence_min=True),dict(presence_min=float('nan')),dict(detection_min=1.1),dict(model_path=''),dict(model_sha256='bad')]:
            with self.subTest(change=change),self.assertRaises(ValueError):contract.normalize(dict(contract.for_model('mediapipe-heavy'),**change))

    def test_world_angle_geometry_is_separate_and_never_used_for_reba(self):
        points=[dict(name='left_'+name,x_m=x,y_m=y,z_m=0,confidence=1) for name,x,y in [('shoulder',0,1),('elbow',0,0),('wrist',1,0)]]
        result=engine.world_angles(points,0.5)
        self.assertEqual(result[0]['value_deg'],90);self.assertFalse(result[0]['used_for_reba'])
        points[-1]['confidence']=0.1;self.assertIsNone(engine.world_angles(points,0.5)[0]['value_deg'])


class PoseValidation(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.folder=Path(self.temp.name);photo=self.folder/'photo.png';Image.new('RGB',(200,100),'white').save(photo)
        self.model=self.folder/'model.task';self.model.write_bytes(b'local-contract-fixture')
        self.selected=contract.for_model('mediapipe-heavy');self.selected.update(model_path=str(self.model),model_sha256=hashlib.sha256(self.model.read_bytes()).hexdigest())
        self.slot=dict(slot_no=1,photo_id=1,camera_side='RIGHT',forward_direction='SCREEN_RIGHT',side_view_verified='YES',observation=dict(single_person='YES',full_frame='YES',normal_work='YES'))
        self.snapshot=dict(photos=[dict(photo_id=1,file_path=str(photo))],settings=dict(pose_model=self.selected))

    def output(self):
        return dict(points=[dict(point_no=i,name=n,x_px=20+i,y_px=20+i%3,confidence=0.9) for i,n in enumerate(contract.MEDIAPIPE_NAMES)],
                    world_points=[dict(point_no=i,name=n,x_m=float(i),y_m=float(i%3),z_m=0.0,confidence=0.9) for i,n in enumerate(contract.MEDIAPIPE_NAMES)],quality=dict(detected=True))

    def test_bad_points_world_outputs_and_names_are_errors_with_no_partial_fake_pose(self):
        for change in ('nan','names','world','visibility'):
            output=self.output()
            if change=='nan':output['points'][0]['x_px']=float('nan')
            if change=='names':output['points'][0]['name']='left_wrist'
            if change=='world':output['world_points'].pop()
            if change=='visibility':output['points'][0]['visibility']=2
            with self.subTest(change=change),patch('ergo.pose.engine._provider',return_value=SimpleNamespace(infer=lambda *args:output)):
                result=engine.process(self.slot,self.snapshot)
            self.assertEqual(result['status'],'ERROR');self.assertFalse(result['points']);self.assertFalse(result['world_points'])

    def test_file_change_after_snapshot_cannot_be_mistaken_for_the_frozen_model(self):
        self.snapshot['pose_artifact']=engine.fingerprint(self.selected)
        self.model.write_bytes(b'changed-file');self.selected['model_sha256']=''
        with patch('ergo.pose.engine._provider') as load:
            result=engine.process(self.slot,self.snapshot)
        self.assertEqual(result['status'],'ERROR');load.assert_not_called()

    def test_missing_model_and_checksum_mismatch_have_no_provider_fallback(self):
        for path in (str(self.folder/'missing.task'),str(self.model)):
            self.selected.update(model_path=path,model_sha256='a'*64)
            with patch('ergo.pose.engine._provider') as load:result=engine.process(self.slot,self.snapshot)
            self.assertEqual(result['diagnostics'][0]['code'],'MODEL_ERROR');load.assert_not_called()

    def test_selected_full_configuration_reaches_provider_and_provenance(self):
        selected=contract.for_model('mediapipe-full')
        selected.update(model_path=str(self.model),model_sha256=hashlib.sha256(self.model.read_bytes()).hexdigest())
        self.snapshot['settings']['pose_model']=selected
        calls=[]
        def infer(image,data,settings,digest):calls.append((data,settings,digest));return self.output()
        with patch('ergo.pose.engine._provider',return_value=SimpleNamespace(infer=infer)):
            result=engine.process(self.slot,self.snapshot)
        self.assertNotEqual(result['status'],'ERROR',result['diagnostics'])
        self.assertEqual(result['engine']['model_id'],'mediapipe-full')
        self.assertEqual(calls[0][1]['variant'],'full');self.assertEqual(calls[0][0],b'local-contract-fixture')

    def test_mediapipe_presence_is_not_replaced_by_visibility_or_movenet_score(self):
        landmarks=[SimpleNamespace(x=0.25+i*.01,y=0.5,z=0.1,visibility=0.99,presence=0.2) for i in range(33)]
        world=[SimpleNamespace(x=0.1+i,y=0.2,z=0.3) for i in range(33)]
        task=SimpleNamespace(detect=lambda image:SimpleNamespace(pose_landmarks=[landmarks],pose_world_landmarks=[world]),close=lambda:None)
        fake=SimpleNamespace(Image=lambda **kw:kw,ImageFormat=SimpleNamespace(SRGB=1),tasks=SimpleNamespace(BaseOptions=lambda **kw:kw,vision=SimpleNamespace(
            PoseLandmarkerOptions=lambda **kw:kw,RunningMode=SimpleNamespace(IMAGE='IMAGE'),PoseLandmarker=SimpleNamespace(create_from_options=lambda options:task))))
        with patch.object(mp_provider,'_sdk',return_value=fake),patch.object(mp_provider,'_instances',{}):
            result=mp_provider.infer(Image.new('RGB',(200,100)),b'fixture',self.selected,'fixture-sha')
        self.assertEqual(result['points'][0]['x_px'],50);self.assertEqual(result['points'][0]['y_px'],50)
        self.assertEqual(result['points'][0]['confidence'],0.2)
        self.assertEqual(result['points'][0]['confidence_kind'],'MIN_VISIBILITY_PRESENCE')
        self.assertEqual(result['world_points'][0]['x_m'],0.1)
        self.assertEqual(result['points'][11]['name'],'left_shoulder');self.assertAlmostEqual(result['points'][11]['x_px'],72)
        self.assertEqual(result['world_points'][23]['name'],'left_hip');self.assertAlmostEqual(result['world_points'][23]['x_m'],23.1)


@unittest.skipUnless(HAVE_MODELS and PHOTO.is_file(),'download both official models and public fixture')
class RealPoseIntegration(unittest.TestCase):
    def test_both_models_return_native_33_points_and_distinct_artifacts(self):
        hashes=set()
        for identity in ('mediapipe-heavy','mediapipe-full'):
            snapshot=dict(photos=[dict(photo_id=1,file_path=str(PHOTO))],settings=dict(pose_model=contract.for_model(identity)))
            result=engine.process(dict(slot_no=1,photo_id=1),snapshot)
            self.assertNotEqual(result['status'],'ERROR',result['diagnostics'])
            self.assertEqual(len(result['points']),33);self.assertEqual(len(result['world_points']),33)
            self.assertEqual(result['points'][11]['name'],'left_shoulder')
            self.assertEqual(result['engine']['model_id'],identity);hashes.add(result['engine']['actual_model_sha256'])
        self.assertEqual(len(hashes),2)

    def test_blank_image_is_no_person_and_never_a_complete_pose(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'blank.png';Image.new('RGB',(300,200),'white').save(path)
            result=engine.process(dict(slot_no=1,photo_id=1),dict(photos=[dict(photo_id=1,file_path=str(path))],settings=dict(pose_model=contract.for_model('mediapipe-heavy'))))
            self.assertEqual(result['status'],'INVALID');self.assertFalse(result['points']);self.assertEqual(result['diagnostics'][0]['code'],'NO_PERSON')

    def test_model_switch_preserves_user_facts_old_snapshots_and_six_tables(self):
        with tempfile.TemporaryDirectory() as folder:
            ctx=create_service(str(Path(folder)/'loco.db'))
            survey=ctx.dispatch('create_survey',dict(draft=dict(survey_type='REGULAR',survey_date='2026-10-22')))
            task=ctx.dispatch('create_task',dict(survey_id=survey['survey_id'],draft=dict(task_name='pose integration')))
            photo=ctx.dispatch('import_photos',dict(task_id=task['task_id'],file_paths=[str(PHOTO)]))['added'][0]
            state=ctx.dispatch('intake_session',dict(task_id=task['task_id'],views=dict(RIGHT=photo['photo_id'])))
            field=next(f for f in state['facts'] if f['target'].startswith('manual.') and f['value'] is not None)
            state=ctx.dispatch('intake_turn',dict(task_id=task['task_id'],plan=False,answers=[dict(target=field['target'],value=field['value'])]))
            record=ctx.dispatch('recalculate_judgments',dict(task_id=task['task_id']));original=copy.deepcopy(ctx.store('get_analysis',record['analysis_id']))
            settings=ctx.settings();settings['analysis']['pose_model']=contract.for_model('mediapipe-full')
            ctx.dispatch('update_settings',dict(settings=settings))
            restored=create_service(ctx.db_path);self.assertEqual(restored.settings()['analysis']['pose_model']['model_id'],'mediapipe-full')
            state=restored.dispatch('intake_session',dict(task_id=task['task_id']))
            retained=next(f for f in state['facts'] if f['identity']==field['identity'])
            self.assertEqual(retained['source'],'USER');self.assertEqual(retained['value'],field['value'])
            self.assertEqual(state['preview']['views']['RIGHT']['engine']['model_id'],'mediapipe-full')
            self.assertEqual(restored.store('get_analysis',record['analysis_id']),original)
            self.assertEqual(len(restored.store('get_settings')['analysis']['pose_model']),len(contract.for_model('mediapipe-full')))


if __name__=='__main__':unittest.main()
