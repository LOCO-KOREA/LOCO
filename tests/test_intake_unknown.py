"""Explicit Korean unknowns retain user ownership, including recorded formal replies."""
import copy
import json
import sqlite3
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

from tests import test_adaptive_intake as fixtures
from backend.intake import contract, facts, planner
from backend.intake.grounding import unknown_evidence
from backend.intake.photo_load import photo_load
from backend.service.application import create_service

RECORDED=json.loads((Path(__file__).parent/'fixtures'/'intake-recorded-unknown-20261023.json').read_text(encoding='utf-8'))
FORMAL='사진 물건과 두 중량의 연결은 모릅니다.'


def unknown(target,quote):
    return dict(target=target,condition='default',number=None,text='UNKNOWN',quote=quote)


class UnknownEvidence(unittest.TestCase):
    def test_common_explicit_forms_are_recognized_without_inventing_a_numeric_zero(self):
        for quote in ['잘 모르겠어요.','모르겠습니다.','연결은 모릅니다.','잘 몰라요.','모름','모름입니다.',
                      '모른다','아직 모르는데요.','무게를 모르고 있어요.','잘 모르는 상태입니다.',
                      '알 수 없어요.','알 수가 없습니다.','알지 못합니다.','아직 미확인입니다.',
                      '미측정입니다.','확인 불가','확인할 수 없어요.','확인을 못했어요.',
                      '측정할 수 없습니다.','기억이 안 나요.','기억나지 않아요.','확인되지 않았어요.',
                      '기억이 없어요.','모르는 중이에요.','모르는 거예요.','모름으로 기록해 주세요.',
                      '잘 모르네요.','모르긴 해요.','확인 방안 모릅니다.']:
            with self.subTest(quote=quote):
                self.assertTrue(unknown_evidence(quote))
                merged,dropped=facts.merge_model({},[unknown('daily_work_min',quote)],quote)
                self.assertFalse(dropped)
                item=merged['daily_work_min@default']
                self.assertEqual((item['value'],item['state'],item['source'],item['origin']),(None,'UNKNOWN','USER','AI'))

    def test_denial_of_unknown_and_unrelated_words_do_not_authorize_unknown(self):
        for quote in ['모르지 않아요.','모르는 것은 아니에요.','모름이 아닙니다.','안 모릅니다.',
                      '미확인인 것은 아니에요.','미확인이 아닙니다.','미확인 항목은 없어요.',
                      '알 수 없는 건 아니에요.','알 수 없는 건 아닙니다.','알 수 없지 않아요.',
                      '알지 못하는 것은 아니에요.','확인 불가는 아니에요.','확인 불가능은 아닙니다.',
                      '기억이 안 나는 것은 아니에요.','기억나지 않는 건 아닙니다.',
                      '모릅니다라는 뜻은 아니에요.','모르겠어요라는 답변은 아니에요.',
                      '확인되지 않은 건 아니에요.','모르겠다는 뜻은 아니에요.',
                      '알 수 없다는 뜻은 아니에요.','미확인이라는 뜻은 아닙니다.',
                      '모름이라는 뜻은 아니에요.','확인 불가라는 뜻은 아니에요.',
                      '잘 모르는 것 같지는 않아요.','기억이 없다는 뜻은 아니에요.','양손 손잡이는 잡기 좋아요.',
                      '물건이 없어요.','모르는 사람이 옆에 있어요.','확인을 마쳤어요.']:
            with self.subTest(quote=quote):
                self.assertFalse(unknown_evidence(quote))
                merged,dropped=facts.merge_model({},[unknown('load_link',quote)],quote)
                self.assertFalse(merged);self.assertEqual(dropped[0]['reason'],'EMPTY_VALUE')

    def test_original_quote_must_exist_and_unknown_in_uncited_context_is_not_enough(self):
        for source in ['사진 물건과 두 중량은 같습니다.','사진에 한 사람이 나와요.']:
            state,dropped=facts.merge_model({},[unknown('load_link',FORMAL)],source)
            self.assertFalse(state);self.assertEqual(dropped[0]['reason'],'QUOTE_NOT_IN_TEXT')
        state,dropped=facts.merge_model({},[unknown('load_link','사진의 물건을 확인해요.')],
            '무게는 모릅니다. 사진의 물건을 확인해요.')
        self.assertFalse(state);self.assertEqual(dropped[0]['reason'],'EMPTY_VALUE')

    def test_current_formal_unknown_can_replace_ai_but_never_a_direct_value(self):
        yes=dict(target='load_link',condition='default',number=None,text='YES',quote='사진 물건도 같은 20kg이에요.')
        ai,_=facts.merge_model({},[yes],yes['quote'])
        state,dropped=facts.merge_model(ai,[unknown('load_link',FORMAL)],FORMAL)
        self.assertFalse(dropped);self.assertIsNone(state['load_link@default']['value'])
        direct=facts.apply_answers({},[dict(target='load_link',value='YES')])
        state,dropped=facts.merge_model(direct,[unknown('load_link',FORMAL)],FORMAL)
        self.assertEqual(state,direct);self.assertEqual(dropped[0]['reason'],'USER_VALUE_KEPT')

    def test_prior_and_late_unknown_follow_stale_user_and_photo_ownership_rules(self):
        state,dropped=facts.merge_model({},[unknown('load_link',FORMAL)],'다음으로',prior_texts=[FORMAL],reconcile=True)
        self.assertFalse(dropped);self.assertEqual(state['load_link@default']['source'],'USER')
        direct=facts.apply_answers({},[dict(target='load_link',value='YES')])
        direct['load_link@default']['updated_at']='2000-01-01T00:00:00Z'
        state,dropped=facts.merge_model(direct,[unknown('load_link',FORMAL)],'다음으로',prior_texts=[FORMAL],reconcile=True)
        self.assertEqual(state,direct);self.assertEqual(dropped[0]['reason'],'STALE_QUOTE')
        state,dropped=facts.merge_model({},[unknown('load_link',FORMAL)],FORMAL,protect_photo_context=True)
        self.assertFalse(state);self.assertEqual(dropped[0]['reason'],'PHOTO_CONTEXT_CONFIRMATION_REQUIRED')

    def test_explicit_photo_link_unknown_never_derives_zero_or_reasks_the_same_link(self):
        source='사진과 같은 무게인지는 몰라요.'
        state,dropped=facts.merge_model({},[unknown('load_link',source)],source)
        self.assertFalse(dropped)
        state=facts.apply_answers(state,[dict(target='card.lift.load_mass_kg',value=20),dict(target='work_type.lift',value='YES')])
        self.assertEqual(photo_load(state),('UNKNOWN',None))
        from backend.engine.task_defaults import task_input
        task=facts.project(task_input({}),state,dict(RIGHT=1),{})
        candidates=planner.assess(task,state,dict(RIGHT=1))['candidates']
        self.assertNotIn('load_link',{item['target'] for item in candidates})
        self.assertEqual(task['capture']['slots'][0]['observation']['load_state'],'UNKNOWN')
        self.assertIsNone(task['capture']['slots'][0]['observation']['measured_load_kg'])


class DurableFormalUnknown(unittest.TestCase):
    setUp=fixtures.AdaptiveIntake.setUp
    get=fixtures.AdaptiveIntake.get
    photo_session=fixtures.PairedAdaptiveIntake.photo_session

    def test_recorded_two_condition_reply_saves_unknown_receipts_source_ids_and_snapshot(self):
        self.photo_session(sides=('RIGHT',))
        settings=self.ctx.dispatch('get_settings',{});settings.update(gpt_enabled=True,gpt_model='recorded-provider')
        self.ctx.dispatch('update_settings',dict(settings=settings))
        calls=[]
        def provider(payload,*args):
            calls.append(payload['phase'])
            return copy.deepcopy(RECORDED['responses'][payload['phase']]),None
        with patch('backend.gpt.client.adaptive_intake',side_effect=provider):
            state=self.ctx.dispatch('intake_turn',dict(task_id=self.identity,text=RECORDED['statement']))
        item=next(item for item in state['facts'] if item['target']=='load_link')
        self.assertEqual((item['value'],item['state'],item['source'],item['origin'],item['quote']),
                         (None,'UNKNOWN','USER','AI',FORMAL))
        self.assertFalse(any(item['target']=='load_link' for item in state['dropped']))
        decisions=[item for turn in state['history'] for item in turn['decisions'] if item['target']=='load_link']
        self.assertTrue(decisions)
        self.assertEqual(decisions[0]['outcome'],'ACCEPTED')
        self.assertTrue(all(item['outcome'] in ('ACCEPTED','UNCHANGED') for item in decisions))
        self.assertTrue(all(item['source_message_ids']==[state['messages'][0]['message_id']] for item in decisions))
        for turn in state['history']:
            for request in turn['requests']:
                self.assertEqual(request['answers'],RECORDED['responses'][request['phase']]['answers'])
        masses={item['condition']:item['value'] for item in state['facts'] if item['target']=='card.lift.load_mass_kg'}
        self.assertEqual(set(masses.values()),{5,30});self.assertEqual(len(masses),2)
        with closing(sqlite3.connect(self.db)) as db:
            saved=json.loads(db.execute('SELECT input_json FROM TASK WHERE task_id=?',(self.identity,)).fetchone()[0])
        session=saved['conditions'][contract.SESSION_KEY]
        self.assertIsNone(session['facts']['load_link@default']['value'])
        self.assertEqual(photo_load(session['facts']),('UNKNOWN',None))
        self.ctx=create_service(self.db)
        restored=self.get()
        self.assertEqual(restored['history'],state['history'])
        self.assertEqual(restored['task']['input_revision'],state['task']['input_revision'])
        self.assertEqual(self.get()['task']['input_revision'],restored['task']['input_revision'])
        analysis=self.ctx.new_analysis(self.ctx.require('task',self.identity),['judgment'])
        before=copy.deepcopy(analysis['snapshot'])
        self.assertEqual(before['conditions'][contract.SESSION_KEY]['facts']['load_link@default']['state'],'UNKNOWN')
        self.ctx.dispatch('intake_turn',dict(task_id=self.identity,answers=[dict(target='load_link',value='YES')],plan=False))
        self.assertEqual(self.ctx.require('analysis',analysis['analysis_id'])['snapshot'],before)


if __name__=='__main__':unittest.main()
