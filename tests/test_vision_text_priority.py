"""Grounded current text can correct VISION without revising the raw observation."""
import copy
import unittest
from unittest.mock import patch
from ergo.intake import contract,facts
from tests import test_photo_vision as fixtures

QUOTE='무릎은 굽히지 않아요.'

def prior(source='VISION',target='work_type.knee',value='YES',condition='default',state=None):
    field=next(field for field in contract.fields() if field['target']==target)
    item=facts.fact(field,value,source,'사진에서 무릎 굽힘 관찰',condition)
    if source=='VISION':item.update(photo_id=1,vision_signature='photo-signature')
    if state:item.update(state=state,conflict=dict(value='NO',quote='이전 충돌'))
    return {contract.key(target,condition):item}

def proposal(target='work_type.knee',quote=QUOTE,condition='default'):
    return dict(target=target,condition=condition,text='NO',number=None,quote=quote)


class VisionTextPriority(unittest.TestCase):
    def test_explicit_current_quote_overrides_only_vision_and_keeps_original_proposal(self):
        existing=prior();original=copy.deepcopy(existing);raw=proposal();before=copy.deepcopy(raw);outcomes=[]
        saved,dropped=facts.merge_model(existing,[raw],QUOTE,outcomes=outcomes)
        item=saved['work_type.knee@default']
        self.assertEqual((item['value'],item['state'],item['source'],item['quote']),('NO','KNOWN','AI',QUOTE))
        self.assertIsNone(item['conflict']);self.assertFalse(dropped);self.assertEqual(outcomes[0]['outcome'],'ACCEPTED')
        self.assertEqual(existing,original);self.assertEqual(raw,before)

    def test_current_text_resolves_vision_conflict_even_in_followup_or_late_reconcile(self):
        for options in [dict(preserve_conflicts=True),dict(reconcile=True),dict(preserve_conflicts=True,reconcile=True)]:
            with self.subTest(options=options):
                existing=prior(state='CONFLICT')
                saved,dropped=facts.merge_model(existing,[proposal()],QUOTE,**options)
                self.assertFalse(dropped)
                self.assertEqual((saved['work_type.knee@default']['source'],saved['work_type.knee@default']['state']),('AI','KNOWN'))

    def test_direct_user_unknown_and_other_established_sources_keep_existing_priority(self):
        for source,value in [('USER',None),('USER','YES'),('AI','YES'),('SAVED','YES'),('POSE','YES')]:
            with self.subTest(source=source,value=value):
                existing=prior(source=source,value=value)
                saved,dropped=facts.merge_model(existing,[proposal()],QUOTE)
                item=saved['work_type.knee@default']
                self.assertEqual((item['value'],item['source']),(value,source))
                self.assertTrue(dropped)
                if source=='USER':self.assertEqual(saved,existing)

    def test_prior_or_invented_quote_cannot_correct_a_current_vision_value(self):
        existing=prior()
        for text,prior_texts,reason in [('다음 질문으로 진행해요.',[QUOTE],'STALE_QUOTE'),('다음 질문으로 진행해요.',[],'QUOTE_NOT_IN_TEXT')]:
            with self.subTest(reason=reason):
                saved,dropped=facts.merge_model(existing,[proposal()],text,prior_texts=prior_texts,reconcile=True)
                self.assertEqual(saved,existing);self.assertEqual(dropped[0]['reason'],reason)

    def test_changed_photo_protects_owned_manual_and_global_vision_candidates(self):
        for target,condition,quote in [('work_type.knee','default',QUOTE),('manual.COMMON.trunk_twisted','photo:1','몸통은 비틀지 않아요.')]:
            with self.subTest(target=target):
                existing=prior(target=target,condition=condition)
                saved,dropped=facts.merge_model(existing,[proposal(target,quote,condition)],quote,protect_photo_context=True,reconcile=True)
                self.assertEqual(saved,existing);self.assertEqual(dropped[0]['reason'],'PHOTO_CONTEXT_CONFIRMATION_REQUIRED')

    def test_numeric_units_still_require_source_grounding_before_source_priority(self):
        existing=prior(target='daily_work_min',value=300)
        raw=dict(target='daily_work_min',condition='default',number=400,text=None,quote='400kg')
        saved,dropped=facts.merge_model(existing,[raw],'400kg')
        self.assertEqual(saved,existing);self.assertEqual(dropped[0]['reason'],'UNIT_OR_NUMBER_NOT_GROUNDED')

    def test_same_current_value_promotes_provenance_but_prior_quote_alone_does_not(self):
        quote='무릎을 굽혀요.';raw=dict(proposal(quote=quote),text='YES')
        for reconcile in (False,True):
            with self.subTest(reconcile=reconcile):
                saved,dropped=facts.merge_model(prior(),[raw],quote,reconcile=reconcile)
                self.assertFalse(dropped);self.assertEqual(saved['work_type.knee@default']['source'],'AI')
                before=prior();saved,dropped=facts.merge_model(before,[raw],'다음 작업 설명이에요.',prior_texts=[quote],reconcile=reconcile)
                self.assertEqual(saved,before);self.assertFalse(dropped)


class DurableVisionTextPriority(unittest.TestCase):
    setUp=fixtures.PhotoVision.setUp
    get=fixtures.PhotoVision.get
    photo_session=fixtures.PhotoVision.photo_session
    enable=fixtures.PhotoVision.enable
    turn=fixtures.PhotoVision.turn

    def test_text_no_is_saved_without_reasking_and_photo_raw_cache_is_unchanged(self):
        self.enable();raw=fixtures.response()
        raw['work_candidates']=[dict(target='work_type.knee',observation='knees',value='YES',status='OBSERVED',confidence=.97,evidence=raw['observations']['knees']['evidence'])]
        def text(payload,*args):return dict(answers=[proposal()] if payload['text']==QUOTE else [],questions=[]),None
        with patch('ergo.vision.client.observe',return_value=(raw,None)) as vision,patch('ergo.gpt.client.adaptive_intake',side_effect=text):
            first=self.turn('사진의 작업 모습을 정리해 주세요.');original=copy.deepcopy(first['photo_vision'])
            self.assertEqual(next(item for item in first['facts'] if item['target']=='work_type.knee')['source'],'VISION')
            state=self.turn(QUOTE)
            self.assertEqual(vision.call_count,1)
        item=next(item for item in state['facts'] if item['target']=='work_type.knee')
        self.assertEqual((item['source'],item['state'],item['value']),('AI','KNOWN','NO'))
        self.assertFalse(any(q['target']=='work_type.knee' for q in state['questions']))
        self.assertEqual(state['photo_vision'],original)
        self.assertEqual(state['task']['legal']['criteria'][4]['condition_present'],'NO')
        self.assertEqual(self.get()['task'],state['task'])

    def test_same_value_text_outlives_photo_and_manual_alias_keeps_the_same_owner(self):
        self.enable();raw=fixtures.response()
        raw['work_candidates']=[dict(target='work_type.knee',observation='knees',value='YES',status='OBSERVED',confidence=.97,evidence=raw['observations']['knees']['evidence'])]
        quote='무릎을 굽히고 몸통을 비틀어요.'
        def text(payload,*args):
            return dict(answers=[dict(target=target,condition='default',number=None,text='YES',quote=quote)
                for target in ('work_type.knee','manual.COMMON.trunk_twisted')] if payload['text']==quote else [],questions=[]),None
        with patch('ergo.vision.client.observe',return_value=(raw,None)) as vision,patch('ergo.gpt.client.adaptive_intake',side_effect=text):
            first=self.turn('사진을 정리해 주세요.');owner=first['task']['capture']['slots'][0]['photo_id']
            original=copy.deepcopy(first['photo_vision']['photos'][0]['raw_response'])
            state=self.turn(quote);self.assertEqual(vision.call_count,1)
        for identity in ('work_type.knee@default',f'manual.COMMON.trunk_twisted@photo:{owner}','manual.COMMON.trunk_twisted@default'):
            item=next(item for item in state['facts'] if item['identity']==identity)
            self.assertEqual((item['source'],item['state'],item['value'],item['quote']),('AI','KNOWN','YES',quote))
            if item['target'].startswith('manual.'):self.assertEqual(item['photo_id'],owner)
        self.assertEqual(state['photo_vision']['photos'][0]['raw_response'],original)
        self.ctx.dispatch('delete_photo',dict(photo_id=owner));state=self.get()
        item=next(item for item in state['facts'] if item['target']=='work_type.knee')
        self.assertEqual((item['source'],item['value']),('AI','YES'))
        self.assertEqual(state['task']['legal']['criteria'][4]['condition_present'],'YES')
        self.assertEqual(next(item for item in state['photo_vision']['history'] if item['photo_id']==owner)['raw_response'],original)


if __name__=='__main__':unittest.main()
