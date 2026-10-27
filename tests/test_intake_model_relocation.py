"""Installing identical pose-model bytes elsewhere must not stale saved work."""
import copy
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from ergo.service.intake import _fingerprint
from ergo import pose_contract
from tests import test_adaptive_intake as fixtures
from tests import test_photo_fact_ownership as photo_fixtures


def legacy_digest(signature,settings,artifact):
    return hashlib.sha256((signature+json.dumps(dict(settings=settings,model=artifact),sort_keys=True)).encode()).hexdigest()


class ModelIdentityBoundaries(unittest.TestCase):
    def seed(self):
        settings=dict(pose_model=dict(model_id='mediapipe-heavy',model_path='models/model.task',confidence_min=.5),reba_rule='R')
        artifact=dict(settings=copy.deepcopy(settings['pose_model']),path='C:/old/resources/models/model.task',
                      sha256='a'*64,wrist_policy=dict(version='W1'))
        signature='unchanged-photo-content-and-ownership'
        previous=legacy_digest(signature,settings,artifact)
        snapshot=dict(settings=copy.deepcopy(settings),pose_artifact=copy.deepcopy(artifact))
        context=SimpleNamespace(store=lambda method,identity:dict(snapshot=snapshot))
        return settings,artifact,signature,previous,context

    def test_verified_identical_content_ignores_only_the_resolved_install_path(self):
        settings,artifact,signature,previous,context=self.seed()
        new_settings=copy.deepcopy(settings)
        moved=copy.deepcopy(artifact);moved['path']='D:/new/resources/models/model.task'
        before=copy.deepcopy((settings,artifact,new_settings,moved))
        with patch('ergo.service.intake.pose_engine.fingerprint',return_value=moved):
            result=_fingerprint(context,dict(latest_analysis_id=7),dict(fingerprint=previous),signature,new_settings)
        self.assertEqual(result,previous,'a proven legacy fingerprint must survive installation-path relocation')
        self.assertEqual((settings,artifact,new_settings,moved),before)

    def test_actual_content_threshold_policy_or_photo_change_cannot_reuse_legacy_identity(self):
        for fault in ('sha','confidence','policy','photos','configured_path','unverified'):
            with self.subTest(fault=fault):
                settings,artifact,signature,previous,context=self.seed();changed=copy.deepcopy(artifact)
                if fault=='sha':changed['sha256']='b'*64
                elif fault=='confidence':settings['pose_model']['confidence_min']=.7;changed['settings']['confidence_min']=.7
                elif fault=='policy':changed['wrist_policy']['version']='W2'
                elif fault=='photos':signature='changed-photo-content'
                elif fault=='configured_path':settings['pose_model']['model_path']='models/user-selected.task';changed['settings']['model_path']='models/user-selected.task'
                else:changed.pop('sha256');changed.pop('path');changed['artifact_error']='model is missing or has wrong hash'
                with patch('ergo.service.intake.pose_engine.fingerprint',return_value=changed):
                    result=_fingerprint(context,dict(latest_analysis_id=7),dict(fingerprint=previous),signature,settings)
                self.assertNotEqual(result,previous)

    def test_unproven_legacy_digest_is_not_retained_even_if_model_content_is_the_same(self):
        settings,artifact,signature,previous,context=self.seed()
        with patch('ergo.service.intake.pose_engine.fingerprint',return_value=artifact):
            result=_fingerprint(context,dict(latest_analysis_id=7),dict(fingerprint='not-the-recorded-snapshot-hash'),signature,settings)
        self.assertNotEqual(result,'not-the-recorded-snapshot-hash')
        self.assertNotEqual(result,previous,'without legacy proof the stable semantic digest is used')


class ModelRelocationSqlite(unittest.TestCase):
    def setUp(self):
        fixtures.AdaptiveIntake.setUp(self)
        self.model_root='C:/old-install/resources'
        self.model_sha='a'*64
        self.wrist_policy=copy.deepcopy(pose_contract.WRIST_POLICY)
        model=patch('ergo.service.intake.pose_engine.fingerprint',side_effect=self.artifact)
        model.start();self.addCleanup(model.stop)
        photo=Path(self.temp.name)/'LEFT.fixture';photo.write_bytes(b'synthetic photo bytes')
        self.photo_id=self.ctx.store('create_photo',self.identity,dict(file_path=str(photo),file_name=photo.name,
            width_px=1,height_px=1,consent='UNKNOWN',notes=[]))
        views=dict(LEFT=self.photo_id)
        data=photo_fixtures.preview([photo_fixtures.observation('LEFT','COMMON','trunk_base',3,40)],views)
        inference=patch('ergo.service.intake.handle_quick_preview',return_value=data)
        inference.start();self.addCleanup(inference.stop)
        self.ctx.dispatch('intake_session',dict(task_id=self.identity,views=views))
        self.ctx.dispatch('intake_turn',dict(task_id=self.identity,plan=False,answers=[
            fixtures.answer('context','YES'),fixtures.answer('load','MEASURED'),fixtures.answer('load_kg',20),
            fixtures.answer('manual.LEFT.coupling','UNACCEPTABLE')]))

    def artifact(self,settings):
        return dict(settings=copy.deepcopy(settings),path=self.model_root+'/models/model.task',
                    sha256=self.model_sha,wrist_policy=copy.deepcopy(self.wrist_policy))

    def analyse(self):
        return self.ctx.dispatch('recalculate_judgments',dict(task_id=self.identity))

    def test_clean_reopen_after_model_relocation_keeps_revision_facts_and_analysis_current(self):
        analysis=self.analyse();before=self.ctx.require('task',self.identity)
        self.model_root='D:/new-install/resources'
        reopened=self.ctx.dispatch('intake_session',dict(task_id=self.identity))['task']
        self.assertEqual(reopened['input_revision'],before['input_revision'])
        self.assertEqual(reopened['conditions']['intake_session'],before['conditions']['intake_session'])
        self.assertEqual(self.ctx.analysis(analysis['analysis_id'])['currentness'],'CURRENT')

    def test_legacy_path_inclusive_fingerprint_survives_move_without_metadata_only_revision(self):
        task=self.ctx.require('task',self.identity);settings=self.ctx.settings()['analysis']
        session=task['conditions']['intake_session']
        session['fingerprint']=legacy_digest(session['photo_signature'],settings,self.artifact(settings['pose_model']))
        session['projected_revision']=task['input_revision']+1
        before=self.ctx.save_task(task)
        analysis=self.analyse()
        self.model_root='D:/new-install/resources'
        reopened=self.ctx.dispatch('intake_session',dict(task_id=self.identity))['task']
        self.assertEqual(reopened['input_revision'],before['input_revision'])
        self.assertEqual(reopened['conditions']['intake_session'],before['conditions']['intake_session'])
        self.assertEqual(self.ctx.analysis(analysis['analysis_id'])['currentness'],'CURRENT')

    def test_actual_model_content_change_invalidates_pose_facts_but_preserves_user_answers(self):
        analysis=self.analyse();before=self.ctx.require('task',self.identity)
        known=copy.deepcopy(before['conditions']['intake_session']['facts'])
        self.model_sha='b'*64
        reopened=self.ctx.dispatch('intake_session',dict(task_id=self.identity))['task']
        self.assertGreater(reopened['input_revision'],before['input_revision'])
        session=reopened['conditions']['intake_session']
        self.assertTrue(session.get('invalidated_photo_facts'))
        for identity,item in known.items():
            if item['source']=='USER':
                with self.subTest(identity=identity):self.assertEqual(session['facts'][identity]['value'],item['value'])
        self.assertEqual(self.ctx.analysis(analysis['analysis_id'])['currentness'],'STALE')


if __name__=='__main__':unittest.main()
