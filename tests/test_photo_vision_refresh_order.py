"""Active observation order is presentation metadata; changed observations remain changes."""
import copy
import unittest
from unittest.mock import patch
from backend.service import photo_vision
from backend.service import intake
from backend.vision import contract
import test_intake_model_relocation as relocation


def record(identity,status='ERROR',summary=''):
    return dict(request_id='request-'+str(identity),signature='signature-'+str(identity),photo_id=identity,
        status=status,summary=summary,observations={},raw_response=None,diagnostics=[])


class PhotoVisionRefreshOrder(unittest.TestCase):
    def session(self,records,history=()):
        return dict(facts={},views={},photo_vision=dict(version=contract.VERSION,photos=copy.deepcopy(records),history=copy.deepcopy(list(history)),catalogue=contract.public_contract()['catalogue']))

    def refresh(self,session,identities):
        with patch('backend.service.photo_vision._descriptors',return_value=[dict(signature='signature-'+str(i)) for i in identities]):
            return photo_vision.refresh({},session,{})

    def test_identical_records_keep_completion_order_not_descriptor_order(self):
        session=self.session([record(10),record(11),record(9)])
        before=copy.deepcopy(session)
        self.refresh(session,[10,9,11])
        self.assertEqual(session,before)
        self.refresh(session,[11,10,9])
        self.assertEqual(session,before)

    def test_removed_membership_and_new_signature_still_invalidate(self):
        session=self.session([record(11),record(9)])
        self.refresh(session,[9])
        self.assertEqual([r['photo_id'] for r in session['photo_vision']['photos']],[9])
        self.assertEqual([r['photo_id'] for r in session['photo_vision']['history']],[11])
        self.refresh(session,[99])
        self.assertFalse(session['photo_vision']['photos'])

    def test_same_request_id_with_changed_content_is_not_treated_as_identical(self):
        old=record(9);updated=record(9,'OBSERVED','새 사진 관찰 결과')
        session=self.session([old],[updated])
        self.refresh(session,[9])
        self.assertEqual(session['photo_vision']['photos'],[updated])
        self.assertNotEqual(session['photo_vision']['photos'],[old])


class PhotoVisionRevision(unittest.TestCase):
    setUp=relocation.ModelRelocationSqlite.setUp
    artifact=relocation.ModelRelocationSqlite.artifact
    analyse=relocation.ModelRelocationSqlite.analyse

    def test_changed_observation_content_still_increments_revision_and_stales_analysis(self):
        task=self.ctx.require('task',self.identity)
        session=task['conditions']['intake_session']
        descriptor=photo_vision._descriptors(task,session,self.ctx.settings())[0]
        session['photo_vision']['photos']=[dict(record(self.photo_id),**descriptor)]
        session['projected_revision']=task['input_revision']+1
        self.ctx.save_task(task)
        analysis=self.analyse();before=self.ctx.require('task',self.identity)
        changed=copy.deepcopy(before['conditions']['intake_session'])
        changed['photo_vision']['photos'][0]['summary']='새로 확인된 실제 사진 관찰 내용'
        saved,ok=intake._save(self.ctx,before,changed,self.ctx.intake_previews[self.identity][1])
        self.assertTrue(ok)
        self.assertEqual(saved['input_revision'],before['input_revision']+1)
        self.assertEqual(self.ctx.analysis(analysis['analysis_id'])['currentness'],'STALE')
        self.assertEqual(saved['conditions']['intake_session']['facts'],before['conditions']['intake_session']['facts'])


if __name__=='__main__':unittest.main()
