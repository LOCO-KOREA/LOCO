"""Reusable SQLite IDs must not transfer a prior registration's observations."""
import copy
import json
import sqlite3
import threading
import unittest
from contextlib import closing
from unittest.mock import patch
from backend import photo_identity
from backend.intake import contract
from tests import test_photo_vision as fixtures


class PhotoRegistration(unittest.TestCase):
    setUp=fixtures.PhotoVision.setUp
    get=fixtures.PhotoVision.get
    photo_session=fixtures.PhotoVision.photo_session
    enable=fixtures.PhotoVision.enable
    turn=fixtures.PhotoVision.turn

    def test_create_always_assigns_fresh_generation_and_update_cannot_replace_it(self):
        self.enable();first=self.ctx.store('list_photos',self.identity)[0]
        token=first[photo_identity.REGISTRATION_KEY]
        metadata={key:value for key,value in first.items() if key not in ('photo_id','task_id')}
        metadata[photo_identity.REGISTRATION_KEY]='forged'
        self.ctx.store('update_photo',first['photo_id'],metadata)
        self.assertEqual(self.ctx.require('photo',first['photo_id'])[photo_identity.REGISTRATION_KEY],token)
        self.ctx.dispatch('delete_photo',dict(photo_id=first['photo_id']))
        identity=self.ctx.store('create_photo',self.identity,metadata)
        self.assertEqual(identity,first['photo_id'])
        self.assertNotIn(self.ctx.require('photo',identity)[photo_identity.REGISTRATION_KEY],(token,'forged'))

    def test_same_id_path_bytes_and_view_replacement_rejects_late_image_and_text_photo_values(self):
        self.enable();photo=self.ctx.store('list_photos',self.identity)[0]
        old_token=photo[photo_identity.REGISTRATION_KEY];entered=threading.Event();release=threading.Event();results=[];payloads=[]
        def vision(*args):entered.set();self.assertTrue(release.wait(5));return fixtures.response(),None
        def text(payload,*args):
            payloads.append(copy.deepcopy(payload))
            return dict(answers=[dict(target='annual_work_days',condition='default',number=220,text=None,quote='연 220일'),
                dict(target='manual.COMMON.trunk_twisted',condition='default',number=None,text='YES',quote='몸통을 비틀어요.')],questions=[]),None
        with patch('backend.vision.client.observe',side_effect=vision),patch('backend.gpt.client.adaptive_intake',side_effect=text):
            worker=threading.Thread(target=lambda:results.append(self.turn('이 사진에서는 몸통을 비틀어요. 연 220일 작업해요.')));worker.start()
            try:
                self.assertTrue(entered.wait(5));self.ctx.dispatch('delete_photo',dict(photo_id=photo['photo_id']))
                identity=self.ctx.store('create_photo',self.identity,{key:value for key,value in photo.items() if key not in ('photo_id','task_id')})
                self.assertEqual(identity,photo['photo_id'])
                self.ctx.dispatch('intake_session',dict(task_id=self.identity,views=dict(RIGHT=identity)))
            finally:release.set();worker.join(5)
        self.assertFalse(worker.is_alive());state=results[0]
        current_token=self.ctx.require('photo',identity)[photo_identity.REGISTRATION_KEY]
        self.assertNotEqual(current_token,old_token)
        self.assertFalse(state['photo_vision']['photos'])
        old=next(record for record in state['photo_vision']['history'] if record['status']=='STALE')
        self.assertEqual(old['owner']['photo_generation'],old_token)
        self.assertEqual(state['task']['conditions']['annual_work_days'],220)
        self.assertFalse(any(item['target']=='manual.COMMON.trunk_twisted' and item['state']=='KNOWN' for item in state['facts']))
        self.assertNotEqual(payloads[0]['source_photo_scope']['photo_signature'],state['task']['conditions'][contract.SESSION_KEY]['photo_signature'])

    def test_legacy_triple_signature_does_not_clear_user_values_or_write_photo_metadata(self):
        self.enable()
        state=self.ctx.dispatch('intake_turn',dict(task_id=self.identity,answers=[dict(target='manual.COMMON.trunk_twisted',value='YES')],plan=False))
        with closing(sqlite3.connect(self.db)) as db:
            owner,raw=db.execute('SELECT photo_id,metadata_json FROM PHOTO').fetchone()
            metadata=json.loads(raw);metadata.pop(photo_identity.REGISTRATION_KEY)
            db.execute('UPDATE PHOTO SET metadata_json=? WHERE photo_id=?',(json.dumps(metadata,ensure_ascii=False),owner))
            task=json.loads(db.execute('SELECT input_json FROM TASK WHERE task_id=?',(self.identity,)).fetchone()[0])
            session=task['conditions'][contract.SESSION_KEY]
            session['photo_signature']=json.dumps([entry[:3] for entry in json.loads(session['photo_signature'])],ensure_ascii=False,sort_keys=True)
            session['photo_vision']['owners']={}
            db.execute('UPDATE TASK SET input_json=? WHERE task_id=?',(json.dumps(task,ensure_ascii=False),self.identity));db.commit()
            before=db.execute('SELECT metadata_json FROM PHOTO').fetchone()[0]
        with patch('backend.vision.client.observe',side_effect=AssertionError('legacy read must not call AI')):
            state=self.get()
            item=next(item for item in state['facts'] if item['target']=='manual.COMMON.trunk_twisted' and not item.get('alias_of'))
            self.assertEqual((item['source'],item['value']),('USER','YES'))
            self.assertEqual(self.get()['task'],state['task'])
        with closing(sqlite3.connect(self.db)) as db:self.assertEqual(db.execute('SELECT metadata_json FROM PHOTO').fetchone()[0],before)


if __name__=='__main__':unittest.main()
