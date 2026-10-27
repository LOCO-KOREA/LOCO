"""Actual encoded image transport, photo ownership, cache and safe reuse."""
import base64
import copy
import hashlib
import io
import json
import threading
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from PIL import Image
from ergo import ai_config
from ergo.intake import contract as intake_contract, facts
from ergo.service.application import create_service
from ergo.service import photo_vision
from ergo.vision import client,contract,images
from tests import test_adaptive_intake as fixtures

def response():
    observations={key:dict(status='OBSERVED',value=label+'를 확인했어요.',evidence=label+'의 윤곽이 보여요.',confidence=.97,reason='') for key,label in contract.CATALOGUE}
    observations['wrist_right'].update(status='NOT_VISIBLE',value='손목이 가려졌어요.',confidence=None,reason='손이 물건 뒤에 있어요.')
    return dict(summary='몸통을 숙여 작업하는 모습이 보여요.',observations=observations,
        manual_candidates=[dict(scope='COMMON',field='trunk_twisted',observation='trunk',value='YES',status='OBSERVED',confidence=.97,evidence=observations['trunk']['evidence'])],
        work_candidates=[dict(target='work_type.trunk_neck',observation='trunk',value='YES',status='OBSERVED',confidence=.97,evidence=observations['trunk']['evidence'])],
        _connection=dict(response_id='controlled_vision',model='gpt-6-luna',reasoning_effort='xhigh'))


class ImageTransport(unittest.TestCase):
    def test_exif_transpose_resize_jpeg_and_hashes_are_real(self):
        import tempfile
        with tempfile.TemporaryDirectory() as folder:
            image=Image.new('RGB',(1600,800),'orange');exif=image.getexif();exif[274]=6
            file=Path(folder)/'source.jpg';image.save(file,exif=exif)
            before=file.read_bytes();policy=dict(contract.policy(),max_edge=640)
            metadata,data=images.prepare(file,policy)
            encoded=base64.b64decode(data.split(',',1)[1])
            with Image.open(io.BytesIO(encoded)) as actual:
                self.assertEqual(actual.size,(320,640));self.assertFalse(actual.getexif());self.assertEqual(actual.format,'JPEG')
            self.assertEqual(file.read_bytes(),before)
            self.assertEqual(metadata['source_sha256'],hashlib.sha256(before).hexdigest())
            self.assertEqual(metadata['encoded_sha256'],hashlib.sha256(encoded).hexdigest())

    def test_responses_receives_actual_image_with_shared_model_and_effort(self):
        captured=[];raw=response();raw.pop('_connection')
        def create(**kwargs):
            captured.append(kwargs)
            return SimpleNamespace(id='actual_transport_test',status='completed',model='gpt-6-luna',reasoning=dict(effort='xhigh'),output_text=json.dumps(raw))
        settings=ai_config.values(dict(gpt_enabled=True,gpt_model='gpt-6-luna',gpt_reasoning_effort='xhigh'))
        with patch('openai.OpenAI') as factory:
            factory.return_value.responses.create.side_effect=create
            result,reason=client.observe('data:image/jpeg;base64,AAEC',dict(photo_id=1),'gpt-6-luna','controlled-key',settings)
        self.assertIsNone(reason);self.assertEqual(result['_connection']['response_id'],'actual_transport_test')
        image=captured[0]['input'][1]['content'][1]
        self.assertEqual(image,dict(type='input_image',image_url='data:image/jpeg;base64,AAEC',detail=contract.policy()['detail']))
        self.assertEqual(captured[0]['model'],'gpt-6-luna');self.assertEqual(captured[0]['reasoning'],dict(effort='xhigh'))
        self.assertEqual(captured[0]['text']['format']['name'],contract.RESPONSE_FORMAT_NAME)


class PhotoVision(unittest.TestCase):
    setUp=fixtures.AdaptiveIntake.setUp
    get=fixtures.AdaptiveIntake.get
    photo_session=fixtures.PairedAdaptiveIntake.photo_session

    def enable(self,sides=('RIGHT',)):
        self.photo_session(sides=sides)
        for index,side in enumerate(sides):Image.new('RGB',(80,100),(index*70,120,150)).save(Path(self.temp.name)/(side+'.fixture'),format='PNG')
        settings=self.ctx.dispatch('get_settings',{});settings.update(gpt_enabled=True,gpt_model='gpt-6-luna',gpt_reasoning_effort='xhigh')
        self.ctx.dispatch('update_settings',dict(settings=settings))

    def turn(self,text='사진을 보고 작업 모습을 정리해 주세요.'):
        return self.ctx.dispatch('intake_turn',dict(task_id=self.identity,text=text))

    def test_real_image_cache_persistence_and_no_api_on_read_direct_or_same_image(self):
        self.enable();calls=[];payloads=[]
        def vision(image,context,*args):
            calls.append((image,context));self.assertTrue(image.startswith('data:image/jpeg;base64,'));return response(),None
        def text(payload,*args):
            payloads.append(payload)
            return dict(answers=[dict(target='context',condition='default',number=None,text='YES',quote='사진은 한 사람의 전신이 나온 평소 작업 모습입니다.')],questions=[]),None
        with patch('ergo.vision.client.observe',side_effect=vision),patch('ergo.gpt.client.adaptive_intake',side_effect=text):
            first=self.turn('사진은 한 사람의 전신이 나온 평소 작업 모습입니다.')
            self.assertEqual(len(calls),1)
            record=first['photo_vision']['photos'][0]
            self.assertEqual(record['raw_response'],response())
            self.assertEqual(record['source_sha256'],hashlib.sha256((Path(self.temp.name)/'RIGHT.fixture').read_bytes()).hexdigest())
            self.assertTrue(record['encoded_sha256']);self.assertEqual(record['owner']['task_id'],self.identity)
            self.assertFalse(payloads[0]['known_visual_observations'],'new photo observations finish after the concurrent text extraction starts')
            self.assertTrue(payloads[1]['known_visual_observations'],'source coverage must see the newly saved photo observation')
            before=copy.deepcopy(first['task'])
            for _ in range(3):self.assertEqual(self.get()['task'],before)
            self.ctx=create_service(self.db);self.assertEqual(self.get()['task'],before)
            self.ctx.dispatch('intake_turn',dict(task_id=self.identity,answers=[dict(target='daily_work_min',value=300)],plan=False))
            self.ctx.dispatch('intake_turn',dict(task_id=self.identity,answers=[dict(target='annual_work_days',value=220)]))
            self.turn('다른 설명을 덧붙여요.');self.assertEqual(len(calls),1)
        data=Path(self.db).read_bytes();self.assertNotIn(b'data:image',data)
        final=self.get();self.assertEqual(final['task']['conditions']['daily_work_min'],300)
        self.assertTrue(any(item['source']=='VISION' and item['target']=='work_type.trunk_neck' for item in final['facts']))
        self.assertFalse(any(item['target']=='manual.RIGHT.wrist_base' and item['source']=='VISION' for item in final['facts']))

    def test_not_visible_wrong_target_no_and_bad_confidence_never_become_facts(self):
        self.enable();raw=response()
        raw['manual_candidates'] += [dict(scope='RIGHT',field='wrist_deviated_or_twisted',observation='wrist_right',value='NO',status='OBSERVED',confidence=.99,evidence=raw['observations']['wrist_right']['evidence']),
            dict(scope='COMMON',field='trunk_base',observation='trunk',value=4,status='OBSERVED',confidence=.99,evidence=raw['observations']['trunk']['evidence'])]
        raw['work_candidates'] += [dict(target='work_type.lift',observation='holding',value='YES',status='OBSERVED',confidence=.99,evidence=raw['observations']['holding']['evidence']),
            dict(target='work_type.knee',observation='knees',value='NO',status='OBSERVED',confidence=.99,evidence=raw['observations']['knees']['evidence']),
            dict(target='work_type.keyboard',observation='activity',value='YES',status='OBSERVED',confidence=float('inf'),evidence=raw['observations']['activity']['evidence'])]
        with patch('ergo.vision.client.observe',return_value=(raw,None)),patch('ergo.gpt.client.adaptive_intake',return_value=(dict(answers=[],questions=[]),None)):
            state=self.turn()
        accepted={item['target'] for item in state['facts'] if item['source']=='VISION'}
        self.assertEqual(accepted,{'manual.COMMON.trunk_twisted','work_type.trunk_neck'})
        self.assertIsNone(state['task']['conditions']['daily_work_min'])
        self.assertTrue(state['photo_vision']['photos'][0]['diagnostics'])
        json.dumps(self.get(),allow_nan=False)

    def test_user_unknown_explicit_ai_saved_and_pose_known_keep_priority(self):
        for source,value in [('USER',None),('USER','NO'),('AI','NO'),('SAVED','NO'),('POSE','NO')]:
            with self.subTest(source=source,value=value):
                field=next(field for field in intake_contract.fields() if field['target']=='manual.COMMON.trunk_twisted')
                previous=facts.fact(field,value,source,'앞선 근거','photo:1')
                record=dict(photo_id=1,view='RIGHT',photo_label='오른쪽 사진',signature='signature',status='OBSERVED',raw_response=response(),diagnostics=[])
                session=dict(facts={intake_contract.key(field['target'],'photo:1'):copy.deepcopy(previous)},photo_vision=dict(photos=[record]))
                photo_vision._merge_candidates(session,record)
                self.assertEqual(session['facts'][intake_contract.key(field['target'],'photo:1')],previous)

    def test_three_photo_requests_start_concurrently_and_keep_each_owner(self):
        self.enable(('LEFT','RIGHT','FRONT'));barrier=threading.Barrier(3);seen=[]
        def vision(image,context,*args):
            seen.append(context['photo_id']);barrier.wait(5)
            time.sleep({'RIGHT':0,'FRONT':.02,'LEFT':.04}[context['photo_view']])
            return response(),None
        with patch('ergo.vision.client.observe',side_effect=vision),patch('ergo.gpt.client.adaptive_intake',return_value=(dict(answers=[],questions=[]),None)):
            state=self.turn()
        self.assertEqual(len(seen),3);self.assertEqual(len(set(seen)),3)
        self.assertEqual({record['photo_id'] for record in state['photo_vision']['photos']},set(seen))
        for record in state['photo_vision']['photos']:self.assertEqual(record['owner']['photo_id'],record['photo_id'])
        analysis=self.ctx.dispatch('recalculate_judgments',dict(task_id=self.identity))
        before=self.ctx.require('task',self.identity)
        order=[record['request_id'] for record in before['conditions']['intake_session']['photo_vision']['photos']]
        for _ in range(2):
            reopened=self.get()['task']
            self.assertEqual(reopened['input_revision'],before['input_revision'],'a read must not stale an analysis by sorting completion-order receipts')
            self.assertEqual([record['request_id'] for record in reopened['conditions']['intake_session']['photo_vision']['photos']],order)
            self.assertEqual(self.ctx.analysis(analysis['analysis_id'])['currentness'],'CURRENT')

    def test_late_photo_replacement_keeps_old_result_in_history_only(self):
        self.enable();old=self.get()['task']['capture']['slots'][0]['photo_id']
        file=Path(self.temp.name)/'new.png';Image.new('RGB',(80,100),'white').save(file)
        new=self.ctx.store('create_photo',self.identity,dict(file_path=str(file),file_name=file.name,width_px=80,height_px=100,consent='UNKNOWN',notes=[]))
        entered=threading.Event();release=threading.Event();results=[]
        def vision(*args):entered.set();self.assertTrue(release.wait(5));return response(),None
        with patch('ergo.vision.client.observe',side_effect=vision),patch('ergo.gpt.client.adaptive_intake',return_value=(dict(answers=[],questions=[]),None)):
            worker=threading.Thread(target=lambda:results.append(self.turn()));worker.start()
            try:
                self.assertTrue(entered.wait(5))
                self.ctx.dispatch('intake_session',dict(task_id=self.identity,views=dict(RIGHT=new)))
                self.ctx.dispatch('intake_turn',dict(task_id=self.identity,answers=[dict(target='daily_work_min',value=420)],plan=False))
            finally:release.set();worker.join(5)
        self.assertFalse(worker.is_alive());state=results[0]
        self.assertEqual(state['task']['conditions']['daily_work_min'],420)
        self.assertFalse(state['photo_vision']['photos'])
        self.assertTrue(any(item['photo_id']==old and item['status']=='STALE' for item in state['photo_vision']['history']))
        self.assertFalse(any(item['source']=='VISION' for item in state['facts']))

    def test_removing_a_photo_reuses_other_current_positive_work_evidence(self):
        self.enable(('LEFT','RIGHT'))
        with patch('ergo.vision.client.observe',return_value=(response(),None)),patch('ergo.gpt.client.adaptive_intake',return_value=(dict(answers=[],questions=[]),None)):
            state=self.turn()
        owner=next(item for item in state['facts'] if item['target']=='work_type.trunk_neck')['photo_id']
        other=next(slot['photo_id'] for slot in state['task']['capture']['slots'] if slot['photo_id']!=owner)
        view=next(slot['label'] for slot in state['task']['capture']['slots'] if slot['photo_id']==other)
        state=self.ctx.dispatch('intake_session',dict(task_id=self.identity,views={view:other}))
        self.assertEqual(next(item for item in state['facts'] if item['target']=='work_type.trunk_neck')['photo_id'],other)
        # Removing all pictures cannot preserve a global feature asserted only by an old picture.
        state=self.ctx.dispatch('intake_session',dict(task_id=self.identity,views={}))
        self.assertFalse(any(item['source']=='VISION' and item['state']=='KNOWN' for item in state['facts']))
        self.assertEqual(state['task']['legal']['criteria'][3]['condition_present'],'UNKNOWN')
        self.assertEqual(self.get()['task'],state['task'])

    def test_model_change_invalidates_owned_values_without_reviving_saved_projection(self):
        self.enable()
        with patch('ergo.vision.client.observe',return_value=(response(),None)),patch('ergo.gpt.client.adaptive_intake',return_value=(dict(answers=[],questions=[]),None)):
            state=self.turn()
        self.assertTrue(any(item['field']=='trunk_twisted' for item in state['task']['manual']))
        settings=self.ctx.dispatch('get_settings',{});settings['gpt_model']='changed-model';self.ctx.dispatch('update_settings',dict(settings=settings))
        with patch('ergo.vision.client.observe',side_effect=AssertionError('read must not call AI')):
            state=self.get();self.assertFalse(state['photo_vision']['photos'])
            self.assertFalse(any(item['field']=='trunk_twisted' for item in state['task']['manual']))
            self.assertEqual(state['task']['legal']['criteria'][3]['condition_present'],'UNKNOWN')
            self.assertEqual(self.get()['task'],state['task'])

    def test_late_user_unknown_keeps_ownership(self):
        self.enable();entered=threading.Event();release=threading.Event();results=[]
        def vision(*args):entered.set();self.assertTrue(release.wait(5));return response(),None
        with patch('ergo.vision.client.observe',side_effect=vision),patch('ergo.gpt.client.adaptive_intake',return_value=(dict(answers=[],questions=[]),None)):
            worker=threading.Thread(target=lambda:results.append(self.turn()));worker.start()
            try:
                self.assertTrue(entered.wait(5))
                self.ctx.dispatch('intake_turn',dict(task_id=self.identity,answers=[dict(target='manual.COMMON.trunk_twisted',value=None)],plan=False))
            finally:release.set();worker.join(5)
        saved=next(item for item in results[0]['facts'] if item['target']=='manual.COMMON.trunk_twisted' and not item.get('alias_of'))
        self.assertEqual((saved['value'],saved['source'],saved['state']),(None,'USER','UNKNOWN'))

    def test_deleted_task_or_reused_id_is_never_changed_by_late_image_response(self):
        self.enable();entered=threading.Event();release=threading.Event();errors=[]
        def vision(*args):entered.set();self.assertTrue(release.wait(5));return response(),None
        def run():
            try:self.turn()
            except Exception as error:errors.append(error)
        with patch('ergo.vision.client.observe',side_effect=vision),patch('ergo.gpt.client.adaptive_intake',return_value=(dict(answers=[],questions=[]),None)):
            worker=threading.Thread(target=run);worker.start()
            try:
                self.assertTrue(entered.wait(5))
                self.ctx.dispatch('delete_task',dict(task_id=self.identity))
                replacement=self.ctx.dispatch('create_task',dict(survey_id=self.survey['survey_id'],draft=dict(task_name='새 소유 작업')))
                before=self.ctx.require('task',replacement['task_id'])
            finally:release.set();worker.join(5)
        self.assertFalse(worker.is_alive());self.assertTrue(errors);self.assertIsInstance(errors[0],LookupError)
        self.assertEqual(self.ctx.require('task',replacement['task_id']),before)

    def test_deleted_photo_implicit_restore_keeps_late_receipt_without_restoring_photo(self):
        self.enable();owner=self.get()['task']['capture']['slots'][0]['photo_id']
        entered=threading.Event();release=threading.Event();results=[]
        def vision(*args):entered.set();self.assertTrue(release.wait(5));return response(),None
        with patch('ergo.vision.client.observe',side_effect=vision),patch('ergo.gpt.client.adaptive_intake',return_value=(dict(answers=[],questions=[]),None)):
            worker=threading.Thread(target=lambda:results.append(self.turn()));worker.start()
            try:
                self.assertTrue(entered.wait(5));self.ctx.dispatch('delete_photo',dict(photo_id=owner))
                self.assertFalse(self.get()['task']['capture']['slots'])
            finally:release.set();worker.join(5)
        self.assertFalse(worker.is_alive());self.assertFalse(results[0]['photo_vision']['photos'])
        self.assertTrue(any(item['photo_id']==owner and item['status']=='STALE' for item in results[0]['photo_vision']['history']))
        with self.assertRaises(ValueError):self.ctx.dispatch('intake_session',dict(task_id=self.identity,views=dict(RIGHT=owner)))

    def test_explicit_negative_context_blocks_inputs_and_yes_reuses_same_image_without_api(self):
        self.enable();payloads=[]
        def text(payload,*args):
            payloads.append(copy.deepcopy(payload))
            return dict(answers=[dict(target='context',condition='default',text='NO',number=None,quote='이 사진은 평소 작업이 아니에요.')],questions=[]),None
        with patch('ergo.vision.client.observe',return_value=(response(),None)) as vision,patch('ergo.gpt.client.adaptive_intake',side_effect=text):
            state=self.turn('이 사진은 평소 작업이 아니에요.')
            self.assertEqual(vision.call_count,1)
            self.assertTrue(state['photo_vision']['photos']);self.assertTrue(state['photo_vision']['application_reason'])
            self.assertFalse(any(item['source']=='VISION' and item['value'] is not None for item in state['facts']))
            self.assertEqual(state['task']['legal']['criteria'][3]['condition_present'],'UNKNOWN')
            self.assertFalse(any(item['field']=='trunk_twisted' for item in state['task']['manual']))
            self.assertEqual(photo_vision.known(state['task']['conditions'][intake_contract.SESSION_KEY]),[])
            self.assertEqual(payloads[-1]['known_visual_observations'],[])
            self.assertEqual(self.get()['task'],state['task'])
            state=self.ctx.dispatch('intake_turn',dict(task_id=self.identity,answers=[dict(target='context',value='YES')],plan=False))
            self.assertEqual(vision.call_count,1)
        self.assertTrue(any(item['source']=='VISION' and item['value']=='YES' for item in state['facts']))
        self.assertEqual(state['task']['legal']['criteria'][3]['condition_present'],'YES')
        self.assertTrue(photo_vision.known(state['task']['conditions'][intake_contract.SESSION_KEY]))


if __name__=='__main__':unittest.main()
