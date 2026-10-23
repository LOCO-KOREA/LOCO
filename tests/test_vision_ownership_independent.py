"""Synthetic provider only: actual service/SQLite late-response ownership counterexamples."""
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch
from PIL import Image
from ergo.service.application import create_service
from ergo.vision import contract

def response(marker='원래 사진'):
    observations={key:dict(status='OBSERVED',value=marker+'의 '+label,evidence=marker+'에서 해당 부분이 보여요.',confidence=.99,reason='') for key,label in contract.CATALOGUE}
    return dict(summary=marker+'의 관찰 결과',observations=observations,manual_candidates=[dict(scope='COMMON',field='trunk_twisted',observation='trunk',value='YES',status='OBSERVED',confidence=.99,evidence=observations['trunk']['evidence'])],work_candidates=[],_connection=dict(response_id='synthetic-'+marker,model='fixture'))

class VisionOwnership(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.directory=Path(self.temp.name);self.db=self.directory/'loco.db';self.ctx=create_service(str(self.db))
        survey=self.ctx.dispatch('create_survey',dict(draft=dict(survey_type='REGULAR',survey_date='2026-10-23',title='사진 응답 소유권 시험')));task=self.ctx.dispatch('create_task',dict(survey_id=survey['survey_id'],draft=dict(task_name='사진 시험')));self.task_id=task['task_id']
        self.original=self.directory/'original.png';Image.new('RGB',(80,100),'navy').save(self.original)
        self.photo=self.ctx.dispatch('import_photos',dict(task_id=self.task_id,file_paths=[str(self.original)]))['added'][0];self.owner=self.photo['photo_id'];self.condition='photo:'+str(self.owner)
        inference=patch('ergo.service.intake.handle_quick_preview',return_value=dict(views={},measured=[],signals={},measurement_issues=[],diagnostics=[]));inference.start();self.addCleanup(inference.stop)
        self.ctx.dispatch('intake_session',dict(task_id=self.task_id,views=dict(RIGHT=self.owner)))
        settings=self.ctx.dispatch('get_settings',{});settings.pop('gpt_key_present',None);settings.update(gpt_enabled=True,gpt_model='fixture',gpt_reasoning_effort='xhigh');self.ctx.dispatch('update_settings',dict(settings=settings))
        text=patch('ergo.gpt.client.adaptive_intake',return_value=(dict(answers=[],questions=[]),None));text.start();self.addCleanup(text.stop)

    def get(self):return self.ctx.dispatch('intake_session',dict(task_id=self.task_id))
    def turn(self):return self.ctx.dispatch('intake_turn',dict(task_id=self.task_id,text='사진을 보고 자세를 확인해 주세요.'))
    def pending(self,change):
        entered=threading.Event();release=threading.Event();results=[];errors=[];calls=[]
        def vision(image,*args):calls.append(image);entered.set();release.wait();return response(),None
        def work():
            try:results.append(self.turn())
            except Exception as error:errors.append(error)
        with patch('ergo.vision.client.observe',side_effect=vision):
            thread=threading.Thread(target=work);thread.start()
            try:self.assertTrue(entered.wait(5));change()
            finally:release.set();thread.join(10)
        self.assertFalse(thread.is_alive());self.assertEqual(errors,[]);self.assertEqual(len(calls),1);self.assertTrue(calls[0].startswith('data:image/jpeg;base64,'));return results[0]

    def test_direct_user_unknown_during_actual_pending_request_keeps_exact_fact_and_raw_late_observation(self):
        before=[]
        def edit():
            self.ctx.dispatch('intake_turn',dict(task_id=self.task_id,answers=[dict(target='manual.COMMON.trunk_twisted',condition=self.condition,value=None,quote='직접 확인해도 아직 모르겠어요.')],plan=False))
            before.append(copy.deepcopy(next(row for row in self.get()['facts'] if row['identity']=='manual.COMMON.trunk_twisted@'+self.condition)))
        state=self.pending(edit);after=next(row for row in state['facts'] if row['identity']==before[0]['identity'])
        self.assertEqual({key:after[key] for key in ('value','source','state','quote','updated_at')},{key:before[0][key] for key in ('value','source','state','quote','updated_at')})
        record=state['photo_vision']['photos'][0];self.assertEqual(record['raw_response']['manual_candidates'][0]['value'],'YES');self.assertEqual(after['source'],'USER');self.assertIsNone(after['value'])
        stable=self.get();self.ctx=create_service(str(self.db));self.assertEqual(self.get()['task'],stable['task']);json.dumps(self.get(),allow_nan=False)

    def test_replacing_file_at_the_same_photo_id_preserves_old_result_only_as_history(self):
        replacement=self.directory/'replacement.png';Image.new('RGB',(80,100),'gold').save(replacement)
        def replace():self.ctx.dispatch('update_photo',dict(photo_id=self.owner,file_path=str(replacement),consent='UNKNOWN'));self.get()
        state=self.pending(replace);self.assertFalse(state['photo_vision']['photos']);self.assertFalse(any(row['source']=='VISION' for row in state['facts']))
        old=next(row for row in state['photo_vision']['history'] if row['photo_id']==self.owner);self.assertEqual(old['status'],'STALE');self.assertEqual(old['source_sha256'],hashlib.sha256(self.original.read_bytes()).hexdigest());self.assertEqual(old['raw_response']['summary'],response()['summary'])
        with patch('ergo.vision.client.observe',return_value=(response('새 사진'),None)) as call:current=self.turn()
        self.assertEqual(call.call_count,1);self.assertEqual(current['photo_vision']['photos'][0]['source_sha256'],hashlib.sha256(replacement.read_bytes()).hexdigest());self.assertEqual(current['photo_vision']['photos'][0]['summary'],response('새 사진')['summary']);self.assertTrue(current['photo_vision']['history'])

    def test_photo_deleted_during_pending_observation_is_never_resurrected(self):
        def remove():
            self.ctx.dispatch('delete_photo',dict(photo_id=self.owner));self.get()
            self.ctx.dispatch('intake_turn',dict(task_id=self.task_id,answers=[dict(target='daily_work_min',value=420)],plan=False))
        state=self.pending(remove);self.assertEqual(self.ctx.dispatch('get_task',dict(task_id=self.task_id))['photos'],[]);self.assertFalse(state['photo_vision']['photos']);self.assertFalse(any(row['source']=='VISION' for row in state['facts']));self.assertEqual(state['task']['conditions']['daily_work_min'],420)
        self.assertTrue(any(row['photo_id']==self.owner and row['status']=='STALE' and row['raw_response']['summary']==response()['summary'] for row in state['photo_vision']['history']))

if __name__=='__main__':unittest.main()
