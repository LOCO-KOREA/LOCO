"""Recorded Luna failures, copied sentence boundaries and durable evidence ownership."""
import copy
import json
import sqlite3
import threading
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

from openpyxl import load_workbook
from PIL import Image

from tests import test_adaptive_intake as fixtures
from backend.intake import contract, facts, history
from backend.intake.grounding import evidence_quote, number_proof
from backend.report.input_trace import InputTrace
from backend.service.application import create_service

RECORDED=json.loads((Path(__file__).parent/'fixtures'/'intake-recorded-grounding-20261023.json').read_text(encoding='utf-8'))
ABSENT=RECORDED['08-zero-and-absent']
JOINED=next(answer['quote'] for answer in ABSENT['response']['answers'] if answer['target']=='load')
RESOLVED='드는 물건은 없어요. 사진은 한 사람의 전신이 나온 평소 작업 모습입니다. 손으로 밀거나 당기는 힘도 전혀 없어요.'


def proposal(target,value,quote):
    return dict(target=target,condition='default',number=value if isinstance(value,(int,float)) else None,
                text=value if isinstance(value,str) else None,quote=quote)


class CopiedEvidence(unittest.TestCase):
    def test_exact_excerpt_and_whitespace_keep_the_existing_quote(self):
        for quote in ['20kg','20 kg','물건은 없어요.']:
            with self.subTest(quote=quote):
                self.assertEqual(evidence_quote(quote,'무게는 20 kg이고 물건은 없어요.'),quote)
        self.assertIsNone(evidence_quote('',ABSENT['statement']))
        self.assertIsNone(evidence_quote(None,ABSENT['statement']))

    def test_recorded_nonadjacent_sentences_resolve_to_one_actual_source_span(self):
        self.assertNotIn(JOINED,ABSENT['statement'])
        self.assertEqual(evidence_quote(JOINED,ABSENT['statement']),RESOLVED)
        normalized=JOINED.replace(' ', '\n ')
        self.assertEqual(evidence_quote(normalized,ABSENT['statement']),RESOLVED)
        session=dict(messages=[dict(message_id='saved-original',text=ABSENT['statement'])])
        self.assertEqual(history.source_ids(session,JOINED),['saved-original'])
        self.assertEqual(history.source_ids(session,RESOLVED),['saved-original'])

    def test_join_cannot_copy_partial_negated_paraphrased_reversed_or_reused_sentences(self):
        for quote in [
            '물건은 없어요. 손으로 밀거나 당기는 힘도 전혀 없어요.',
            '드는 물건은 있어요. 손으로 밀거나 당기는 힘도 전혀 없어요.',
            '물건을 들지 않아요. 손으로 밀거나 당기는 힘도 전혀 없어요.',
            '손으로 밀거나 당기는 힘도 전혀 없어요. 드는 물건은 없어요.',
            '드는 물건은 없어요. 드는 물건은 없어요.',
            '드는 물건은 없어요 손으로 밀거나 당기는 힘도 전혀 없어요.',
            '드는 물건은 없어요. 손으로 밀거나 당기는 힘도 전혀',
        ]:
            with self.subTest(quote=quote):self.assertIsNone(evidence_quote(quote,ABSENT['statement']))
        negated='드는 물건은 없지 않아요. 사진 설명이에요. 미는 힘도 없지 않아요.'
        self.assertIsNone(evidence_quote('드는 물건은 없어요. 미는 힘도 없어요.',negated))

    def test_sentence_boundaries_keep_decimal_units_and_final_unterminated_sentences(self):
        source='물건은 12.5kg입니다. 사진 설명이에요! 하루 3시간 일해요'
        quote='물건은 12.5kg입니다. 하루 3시간 일해요'
        self.assertEqual(evidence_quote(quote,source),source)
        self.assertIsNone(evidence_quote('5kg입니다. 하루 3시간 일해요',source))
        self.assertIsNone(evidence_quote('물건은 125kg입니다. 하루 3시간 일해요',source))
        self.assertIsNone(evidence_quote('물건은 12.5g입니다. 하루 3시간 일해요',source))

    def test_join_cannot_cross_messages_or_authorize_uncited_intermediate_numbers(self):
        pieces=JOINED.split('. ')
        session=dict(messages=[dict(message_id='one',text=pieces[0]+'.'),dict(message_id='two',text=pieces[1])])
        self.assertEqual(history.source_ids(session,JOINED),[])
        state,dropped=facts.merge_model({},[proposal('load','UNLOADED',JOINED)],pieces[0]+'.',prior_texts=[pieces[1]])
        self.assertFalse(state);self.assertEqual(dropped[0]['reason'],'QUOTE_NOT_IN_TEXT')
        source='키보드는 하루 10분입니다. 물건은 20kg입니다. 허리는 하루 30분입니다.'
        quote='키보드는 하루 10분입니다. 허리는 하루 30분입니다.'
        state,dropped=facts.merge_model({},[proposal('card.lift.load_mass_kg',20,quote)],source)
        self.assertFalse(state);self.assertEqual(dropped[0]['reason'],'UNIT_OR_NUMBER_NOT_GROUNDED')
        for value in [20,25]:
            state,dropped=facts.merge_model({},[proposal('card.keyboard.C1_KEYBOARD_FOCUSED',value,quote)],source)
            self.assertFalse(state);self.assertEqual(dropped[0]['reason'],'UNIT_OR_NUMBER_NOT_GROUNDED')

    def test_original_proposals_and_decisions_stay_verbatim_while_fact_uses_actual_source(self):
        raw=[proposal('load','UNLOADED',JOINED)];original=copy.deepcopy(raw);decisions=[]
        state,dropped=facts.merge_model({},raw,ABSENT['statement'],outcomes=decisions)
        self.assertFalse(dropped);self.assertEqual(raw,original)
        self.assertEqual(state['load@default']['quote'],RESOLVED)
        self.assertEqual(decisions[0]['quote'],JOINED)
        self.assertEqual(decisions[0]['outcome'],'ACCEPTED')

    def test_intermediate_context_neither_authorizes_unknown_nor_invalidates_uncited_time(self):
        source='손목은 하루 3시간 반복해요. 다른 작업은 2~3시간인지 모르겠어요. 물건은 없어요.'
        quote='손목은 하루 3시간 반복해요. 물건은 없어요.'
        state,dropped=facts.merge_model({},[proposal('card.repeat.C2_WRIST',180,quote)],source)
        self.assertFalse(dropped);self.assertEqual(state['card.repeat.C2_WRIST@default']['value'],180)
        state,dropped=facts.merge_model({},[proposal('card.repeat.C2_WRIST','UNKNOWN',quote)],source)
        self.assertFalse(state);self.assertEqual(dropped[0]['reason'],'EMPTY_VALUE')

    def test_prior_sentences_user_ownership_and_late_reconciliation_keep_their_rules(self):
        raw=[proposal('load','UNLOADED',JOINED)]
        state,dropped=facts.merge_model({},raw,'계속 확인해 주세요.',prior_texts=[ABSENT['statement']],reconcile=True)
        self.assertFalse(dropped);self.assertEqual(state['load@default']['value'],'UNLOADED')
        user=facts.apply_answers({},[dict(target='load',value='MEASURED')])
        state,dropped=facts.merge_model(user,raw,ABSENT['statement'],reconcile=True)
        self.assertEqual(state,user);self.assertEqual(dropped[0]['reason'],'USER_VALUE_KEPT')
        ai,_=facts.merge_model({},[proposal('load','MEASURED','20kg 상자예요.')],'20kg 상자예요.')
        state,dropped=facts.merge_model(ai,raw,'계속 확인해 주세요.',prior_texts=[ABSENT['statement']],reconcile=True)
        self.assertEqual(state,ai);self.assertEqual(dropped[0]['reason'],'STALE_QUOTE')
        state,dropped=facts.merge_model({},raw,ABSENT['statement'],protect_photo_context=True)
        self.assertFalse(state);self.assertEqual(dropped[0]['reason'],'PHOTO_CONTEXT_CONFIRMATION_REQUIRED')


class HalfHourBoundaries(unittest.TestCase):
    def setUp(self):
        self.field=next(field for field in contract.fields() if field['target']=='card.repeat.C2_WRIST')

    def test_half_hour_grammar_keeps_normal_spaces_particles_and_endings(self):
        for text in ['한 시간 반이에요','한 시간 반 동안','1시간반씩','2시간반을 일해요',
                     '1시간 반 정도예요','한 시간 반이요','1시간반입니다','1시간 반은 반복해요']:
            with self.subTest(text=text):
                minutes=150 if text.startswith('2') else 90
                self.assertIsNotNone(number_proof(self.field,minutes,text,source=text))
                self.assertIsNone(number_proof(self.field,minutes-30,text,source=text))

    def test_words_beginning_with_half_syllable_are_not_an_extra_half_hour(self):
        for suffix in ['반복해요','반대로 움직여요','반드시 해요','반품을 검사해요','반도체를 조립해요','반응을 살펴요']:
            for space in [' ','']:
                text='손목을 하루 3시간'+space+suffix
                with self.subTest(text=text):
                    self.assertIsNotNone(number_proof(self.field,180,text,source=text))
                    self.assertIsNone(number_proof(self.field,210,text,source=text))

    def test_half_hour_quote_cannot_be_cut_to_the_whole_hour_or_other_unit(self):
        for source in ['하루 1시간 반씩 일해요.','하루 1시간반을 일해요.']:
            self.assertIsNone(number_proof(self.field,60,'1시간',source=source))
        source='손목과 손의 같은 동작을 각각 하루 3시간 반복해요.'
        for target in ['card.repeat.C2_WRIST','card.repeat.C2_HAND']:
            field=next(field for field in contract.fields() if field['target']==target)
            self.assertIsNotNone(number_proof(field,180,source,source=source))
            self.assertIsNone(number_proof(field,210,source,source=source))


class DurableRecordedEvidence(unittest.TestCase):
    setUp=fixtures.AdaptiveIntake.setUp
    get=fixtures.AdaptiveIntake.get
    turn=fixtures.AdaptiveIntake.turn
    candidates=fixtures.AdaptiveIntake.candidates
    photo_session=fixtures.PairedAdaptiveIntake.photo_session

    def test_recorded_absence_replay_saves_original_receipt_canonical_evidence_and_excel(self):
        self.photo_session()
        for side in ['LEFT','RIGHT']:
            Image.new('RGB',(2,2),'white').save(Path(self.temp.name)/(side+'.fixture'),format='PNG')
        state=self.turn(text=ABSENT['statement'],raw=copy.deepcopy(ABSENT['response']))
        self.assertFalse(state['dropped'])
        self.assertEqual(state['task']['conditions']['daily_work_min'],240)
        load=next(fact for fact in state['facts'] if fact['target']=='load')
        self.assertEqual((load['value'],load['source'],load['quote']),('UNLOADED','AI',RESOLVED))
        self.assertFalse({'load','load_kg'} & {item['target'] for item in self.candidates(state)})
        self.assertFalse({'load','load_kg'} & {item['target'] for item in state['questions']})
        receipt=state['history'][0]
        self.assertEqual(receipt['requests'][0]['answers'],ABSENT['response']['answers'])
        decision=next(item for item in receipt['decisions'] if item['target']=='load')
        self.assertEqual((decision['quote'],decision['outcome']),(JOINED,'ACCEPTED'))
        self.assertEqual(decision['source_message_ids'],[state['messages'][0]['message_id']])
        with closing(sqlite3.connect(self.db)) as db:
            saved=json.loads(db.execute('SELECT input_json FROM TASK WHERE task_id=?',(self.identity,)).fetchone()[0])
        self.assertEqual(saved['conditions'][contract.SESSION_KEY]['facts']['load@default']['quote'],RESOLVED)
        self.ctx=create_service(self.db)
        restored=self.get()
        self.assertEqual(restored['history'],state['history'])
        self.assertEqual(restored['task']['input_revision'],state['task']['input_revision'])
        repeated=self.get()
        self.assertEqual(repeated['facts'],restored['facts'])
        self.assertEqual(repeated['task']['input_revision'],restored['task']['input_revision'])
        analysis=self.ctx.new_analysis(self.ctx.require('task',self.identity),['judgment'])
        self.ctx.run(analysis,['judgment'],threading.Event(),self.ctx.analysis_token(analysis['analysis_id']))
        selected=self.ctx.require('analysis',analysis['analysis_id'])
        trace=InputTrace(selected['snapshot']).lookup('load','UNLOADED')
        self.assertEqual(trace,('작업 설명(AI 정리)','AI: '+RESOLVED))
        destination=str(Path(self.temp.name)/'recorded-absence.xlsx')
        self.ctx.dispatch('export_excel',dict(survey_id=self.survey['survey_id'],spec=dict(
            analysis_ids=[],include_representative=False,comparisons=[],destination=destination)))
        book=load_workbook(destination,data_only=True)
        cells=[cell.value for sheet in book for row in sheet for cell in row if cell.value is not None]
        book.close()
        self.assertTrue(any(cell.endswith('AI: '+RESOLVED) for cell in cells))
        snapshot=copy.deepcopy(selected['snapshot'])
        edited=self.turn([dict(target='load',value='MEASURED')],plan=False)
        reread=self.get()
        self.assertEqual(reread['task']['input_revision'],edited['task']['input_revision'])
        self.assertEqual(next(fact for fact in reread['facts'] if fact['target']=='load')['source'],'USER')
        self.assertEqual(self.ctx.require('analysis',analysis['analysis_id'])['snapshot'],snapshot)

    def test_recorded_repeated_work_replay_keeps_both_180_minute_fields_and_output(self):
        case=RECORDED['11-preparation-posture']
        state=self.turn(text=case['statement'],raw=copy.deepcopy(case['response']))
        self.assertFalse(state['dropped'])
        self.assertEqual(state['task']['conditions']['daily_work_min'],480)
        known={fact['target']:fact for fact in state['facts']}
        targets={'card.repeat.C2_WRIST','card.repeat.C2_HAND'}
        for target in targets:self.assertEqual(known[target]['value'],180)
        self.assertFalse(targets & {item['target'] for item in self.candidates(state)})
        restored=create_service(self.db).dispatch('intake_session',dict(task_id=self.identity))
        self.assertEqual(restored['history'],state['history'])
        analysis=self.ctx.new_analysis(self.ctx.require('task',self.identity),['judgment'])
        for code in ['C2_WRIST','C2_HAND']:
            exposure=next(row for row in analysis['snapshot']['legal']['exposures'] if row['condition_code']==code)
            self.assertEqual(exposure['minutes'],180)
            self.assertEqual(InputTrace(analysis['snapshot']).lookup('criterion',180,field=code),
                             ('작업 설명(AI 정리)','AI: 손목과 손의 같은 동작을 각각 하루 3시간 반복해요.'))


if __name__=='__main__':unittest.main()
