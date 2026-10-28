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
from backend.service.application import create_service
from backend import photo_identity
from backend.vision import contract

def response(marker='원래 사진'):
    observations={key:dict(status='OBSERVED',value=marker+'의 '+label,evidence=marker+'에서 해당 부분이 보여요.',confidence=.99,reason='') for key,label in contract.CATALOGUE}
    return dict(summary=marker+'의 관찰 결과',observations=observations,manual_candidates=[dict(scope='COMMON',field='trunk_twisted',observation='trunk',value='YES',status='OBSERVED',confidence=.99,evidence=observations['trunk']['evidence'])],work_candidates=[],_connection=dict(response_id='synthetic-'+marker,model='fixture'))

class VisionOwnership(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.directory=Path(self.temp.name);self.db=self.directory/'loco.db';self.ctx=create_service(str(self.db))
        survey=self.ctx.dispatch('create_survey',dict(draft=dict(survey_type='REGULAR',survey_date='2026-10-23',title='사진 응답 소유권 시험')));task=self.ctx.dispatch('create_task',dict(survey_id=survey['survey_id'],draft=dict(task_name='사진 시험')));self.task_id=task['task_id']
        self.original=self.directory/'original.png';Image.new('RGB',(80,100),'navy').save(self.original)
        self.photo=self.ctx.dispatch('import_photos',dict(task_id=self.task_id,file_paths=[str(self.original)]))['added'][0];self.owner=self.photo['photo_id'];self.condition='photo:'+str(self.owner)
        inference=patch('backend.service.intake.handle_quick_preview',return_value=dict(views={},measured=[],signals={},measurement_issues=[],diagnostics=[]));inference.start();self.addCleanup(inference.stop)
        self.ctx.dispatch('intake_session',dict(task_id=self.task_id,views=dict(RIGHT=self.owner)))
        settings=self.ctx.dispatch('get_settings',{});settings.pop('gpt_key_present',None);settings.update(gpt_enabled=True,gpt_model='fixture',gpt_reasoning_effort='xhigh');self.ctx.dispatch('update_settings',dict(settings=settings))
        text=patch('backend.gpt.client.adaptive_intake',return_value=(dict(answers=[],questions=[]),None));text.start();self.addCleanup(text.stop)

    def get(self):return self.ctx.dispatch('intake_session',dict(task_id=self.task_id))
    def turn(self):return self.ctx.dispatch('intake_turn',dict(task_id=self.task_id,text='사진을 보고 자세를 확인해 주세요.'))
    def pending(self,change):
        entered=threading.Event();release=threading.Event();results=[];errors=[];calls=[]
        def vision(image,*args):calls.append(image);entered.set();release.wait();return response(),None
        def work():
            try:results.append(self.turn())
            except Exception as error:errors.append(error)
        with patch('backend.vision.client.observe',side_effect=vision):
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

    def test_completed_text_waits_for_photo_then_replacement_and_user_save_win(self):
        from concurrent.futures import ThreadPoolExecutor as BaseExecutor

        replacement=self.directory/'replacement-after-text.png';Image.new('RGB',(80,100),'gold').save(replacement)
        text_finished=threading.Event();photo_started=threading.Event();release_photo=threading.Event()
        results=[];errors=[];payloads=[];initial_revision=self.get()['task']['input_revision']
        class CompletionObservedExecutor(BaseExecutor):
            def submit(self,*args,**kwargs):
                future=super().submit(*args,**kwargs)
                future.add_done_callback(lambda _future:text_finished.set())
                return future
        def respond(payload,*args):
            payloads.append(copy.deepcopy(payload))
            if payload.get('phase')=='EXTRACT_AND_PLAN':
                return dict(answers=[dict(target='manual.COMMON.trunk_base',condition=self.condition,
                    number=None,text='4',quote='이 사진은 몸통이 크게 굽었어요.')],questions=[]),None
            return dict(answers=[],questions=[]),None
        def vision(*args,**kwargs):
            photo_started.set()
            if not release_photo.wait(10):raise TimeoutError('photo fixture was not released')
            return response('교체 전 사진'),None
        def work():
            try:results.append(self.ctx.dispatch('intake_turn',dict(task_id=self.task_id,text='이 사진은 몸통이 크게 굽었어요.')))
            except Exception as error:errors.append(error)
        with patch('backend.service.intake.ThreadPoolExecutor',CompletionObservedExecutor), \
             patch('backend.gpt.client.adaptive_intake',side_effect=respond), \
             patch('backend.vision.client.observe',side_effect=vision):
            thread=threading.Thread(target=work);thread.start()
            try:
                self.assertTrue(photo_started.wait(5),'photo request did not start')
                self.assertTrue(text_finished.wait(5),'text response did not finish while photo request was pending')
                self.assertTrue(thread.is_alive(),'service must still be waiting for the pending photo response')
                self.ctx.dispatch('update_photo',dict(photo_id=self.owner,file_path=str(replacement),consent='UNKNOWN'))
                saved=self.ctx.dispatch('intake_turn',dict(task_id=self.task_id,answers=[dict(
                    target='manual.COMMON.trunk_twisted',condition=self.condition,value=None,
                    quote='직접 확인해도 아직 모르겠어요.')],plan=False))
                user_revision=saved['task']['input_revision']
                user_before=next(row for row in saved['facts'] if row['identity']=='manual.COMMON.trunk_twisted@'+self.condition)
                self.assertEqual((user_before['source'],user_before['state'],user_before['value']),('USER','UNKNOWN',None))
            finally:
                release_photo.set();thread.join(10)
        self.assertFalse(thread.is_alive());self.assertEqual(errors,[]);self.assertEqual(len(results),1)
        current=self.get();final_revision=current['task']['input_revision']
        self.assertGreater(user_revision,initial_revision)
        self.assertGreaterEqual(final_revision,user_revision)
        user_after=next(row for row in current['facts'] if row['identity']==user_before['identity'])
        self.assertEqual({key:user_after[key] for key in ('source','state','value','quote','updated_at')},
            {key:user_before[key] for key in ('source','state','value','quote','updated_at')})
        text_target=next((row for row in current['facts'] if row['identity']=='manual.COMMON.trunk_base@'+self.condition),None)
        self.assertTrue(text_target is None or (text_target['source'],text_target['value'])!=('AI','4'))
        self.assertFalse(current['photo_vision']['photos'])
        stale=next(row for row in current['photo_vision']['history'] if row['photo_id']==self.owner and row['raw_response']['summary']=='교체 전 사진의 관찰 결과')
        self.assertEqual(stale['status'],'STALE')
        followup=next(payload for payload in payloads if payload.get('phase')=='FOLLOWUP')
        self.assertNotEqual(followup['source_photo_scope']['photo_signature'],followup['current_photo_scope']['photo_signature'])
        self.assertEqual(results[0]['reason'],'INPUT_CHANGED')

    def test_replacing_file_at_the_same_photo_id_preserves_old_result_only_as_history(self):
        replacement=self.directory/'replacement.png';Image.new('RGB',(80,100),'gold').save(replacement)
        def replace():self.ctx.dispatch('update_photo',dict(photo_id=self.owner,file_path=str(replacement),consent='UNKNOWN'));self.get()
        state=self.pending(replace);self.assertFalse(state['photo_vision']['photos']);self.assertFalse(any(row['source']=='VISION' for row in state['facts']))
        old=next(row for row in state['photo_vision']['history'] if row['photo_id']==self.owner);self.assertEqual(old['status'],'STALE');self.assertEqual(old['source_sha256'],hashlib.sha256(self.original.read_bytes()).hexdigest());self.assertEqual(old['raw_response']['summary'],response()['summary'])
        with patch('backend.vision.client.observe',return_value=(response('새 사진'),None)) as call:current=self.turn()
        self.assertEqual(call.call_count,1);self.assertEqual(current['photo_vision']['photos'][0]['source_sha256'],hashlib.sha256(replacement.read_bytes()).hexdigest());self.assertEqual(current['photo_vision']['photos'][0]['summary'],response('새 사진')['summary']);self.assertTrue(current['photo_vision']['history'])

    def test_photo_deleted_during_pending_observation_is_never_resurrected(self):
        def remove():
            self.ctx.dispatch('delete_photo',dict(photo_id=self.owner));self.get()
            self.ctx.dispatch('intake_turn',dict(task_id=self.task_id,answers=[dict(target='daily_work_min',value=420)],plan=False))
        state=self.pending(remove);self.assertEqual(self.ctx.dispatch('get_task',dict(task_id=self.task_id))['photos'],[]);self.assertFalse(state['photo_vision']['photos']);self.assertFalse(any(row['source']=='VISION' for row in state['facts']));self.assertEqual(state['task']['conditions']['daily_work_min'],420)
        self.assertTrue(any(row['photo_id']==self.owner and row['status']=='STALE' and row['raw_response']['summary']==response()['summary'] for row in state['photo_vision']['history']))

    def test_deleted_and_reimported_identical_bytes_reused_id_cannot_adopt_the_old_response(self):
        old_token=self.photo[photo_identity.REGISTRATION_KEY];created=[]
        def replace():
            self.ctx.dispatch('delete_photo',dict(photo_id=self.owner))
            photo=self.ctx.dispatch('import_photos',dict(task_id=self.task_id,file_paths=[str(self.original)]))['added'][0];created.append(photo)
            self.assertEqual(photo['photo_id'],self.owner);self.assertNotEqual(photo[photo_identity.REGISTRATION_KEY],old_token)
            self.ctx.dispatch('intake_session',dict(task_id=self.task_id,views=dict(RIGHT=self.owner)))
        state=self.pending(replace);self.assertFalse(state['photo_vision']['photos']);self.assertFalse(any(row['source']=='VISION' for row in state['facts']))
        self.assertTrue(any(row['photo_id']==self.owner and row['status']=='STALE' for row in state['photo_vision']['history']))
        with patch('backend.vision.client.observe',return_value=(response('재등록 사진'),None)) as call:current=self.turn()
        self.assertEqual(call.call_count,1);self.assertEqual(current['photo_vision']['photos'][0]['summary'],response('재등록 사진')['summary'])
        self.assertEqual(current['photo_vision']['photos'][0]['owner']['photo_generation'],created[0][photo_identity.REGISTRATION_KEY])

    def test_negative_context_clears_projection_but_yes_reuses_cache_and_preserves_user_unknown(self):
        with patch('backend.vision.client.observe',return_value=(response(),None)) as call:
            initial=self.turn();self.assertTrue(any(row['source']=='VISION' for row in initial['facts']))
            negative=self.ctx.dispatch('intake_turn',dict(task_id=self.task_id,answers=[dict(target='context',value='NO')],plan=False))
            self.assertFalse(any(row['source']=='VISION' and row['state']=='KNOWN' for row in negative['facts']));self.assertFalse(negative['task']['manual'])
            self.assertEqual(negative['photo_vision']['photos'][0]['raw_response'],initial['photo_vision']['photos'][0]['raw_response'])
            self.ctx.dispatch('intake_turn',dict(task_id=self.task_id,answers=[dict(target='manual.COMMON.trunk_twisted',condition=self.condition,value=None,quote='사람이 모름으로 확인했어요.')],plan=False))
            restored=self.ctx.dispatch('intake_turn',dict(task_id=self.task_id,answers=[dict(target='context',value='YES')],plan=False))
            saved=next(row for row in restored['facts'] if row['identity']=='manual.COMMON.trunk_twisted@'+self.condition)
            self.assertEqual((saved['source'],saved['state'],saved['value']),('USER','UNKNOWN',None));self.assertEqual(call.call_count,1)
            json.dumps(restored,allow_nan=False)

if __name__=='__main__':unittest.main()
