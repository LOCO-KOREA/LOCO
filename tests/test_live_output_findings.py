"""Minimal regressions extracted from the ten live output ledgers."""
import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch
from openpyxl import load_workbook
from backend.service.application import create_service
from backend.intake.grounding import stated_duration_sum,DURATION_SUM

def answer(target,value,quote,condition='default'):
    return dict(target=target,condition=condition,number=value if type(value) in (int,float) else None,
                text=value if isinstance(value,str) else None,quote=quote)

class LiveOutputFindings(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.directory=Path(self.temp.name)
        self.ctx=create_service(self.directory/'loco.db');self.survey=self.ctx.dispatch('create_survey',dict(draft=dict(title='출력 경로 반례')))
        self.task=self.ctx.dispatch('create_task',dict(survey_id=self.survey['survey_id'],draft=dict(task_name='기록 대조')))
        settings=self.ctx.dispatch('get_settings',{});settings.update(gpt_enabled=True,gpt_model='controlled');self.ctx.dispatch('update_settings',dict(settings=settings))
    def turn(self,text,answers):
        def provider(payload,*args):return dict(answers=answers if payload['phase']=='EXTRACT_AND_PLAN' else [],questions=[]),None
        with patch('backend.gpt.client.adaptive_intake',side_effect=provider):return self.ctx.dispatch('intake_turn',dict(task_id=self.task['task_id'],text=text))
    def rows(self):
        a=self.ctx.dispatch('recalculate_judgments',dict(task_id=self.task['task_id']))
        p=self.directory/'report.xlsx';self.ctx.dispatch('export_excel',dict(survey_id=self.survey['survey_id'],spec=dict(destination=str(p),analysis_ids=[a['analysis_id']],include_representative=False,comparisons=[])))
        book=load_workbook(p);rows=list(book['입력한 값'].values);book.close();return rows
    def test_novel_grounded_followup_answer_is_applied_and_not_reasked(self):
        def provider(payload,*args):
            if payload['phase']=='EXTRACT_AND_PLAN':return dict(answers=[answer('card.lift.load_mass_kg',20,'20kg'),answer('card.lift.lift_count_day',30,'하루 30회')],questions=[]),None
            return dict(answers=[answer('complete.lift','YES','이 조건이 모든 들기 조건입니다')],questions=[dict(target='complete.lift',condition='default',text='모든 조건인가요?',reason='확인')]),None
        with patch('backend.gpt.client.adaptive_intake',side_effect=provider):state=self.ctx.dispatch('intake_turn',dict(task_id=self.task['task_id'],text='20kg 상자를 하루 30회 들어요. 이 조건이 모든 들기 조건입니다'))
        self.assertEqual(state['task']['legal']['criteria'][7]['rows_complete'],'YES')
        self.assertFalse(any(q['target']=='complete.lift' for q in state['questions']))
        self.assertEqual(state['history'][-1]['decisions'][-1]['outcome'],'ACCEPTED')
    def test_explicit_non_overlap_does_not_reject_correct_compound_sum(self):
        quote='손·팔을 높이 드는 작업 1시간 30분. 키보드·마우스 집중 작업 4시간 30분. 두 작업 시간은 겹치지 않아요.'
        calculation=dict(operation=DURATION_SUM,terms=[dict(quote='손·팔을 높이 드는 작업 1시간 30분.',minutes=90),dict(quote='키보드·마우스 집중 작업 4시간 30분.',minutes=270)])
        result=stated_duration_sum(quote,quote,calculation)
        self.assertIsNotNone(result);self.assertEqual(result['value'],360)
        self.assertIsNone(stated_duration_sum(quote,quote+' 하지만 30분은 겹쳐요.',calculation))
    def test_condition_values_keep_own_source_and_quote_in_xlsx(self):
        self.turn('하루 전체 8시간 연 220일 일해요',[answer('daily_work_min',480,'하루 전체 8시간'),answer('annual_work_days',220,'연 220일')])
        self.ctx.dispatch('intake_turn',dict(task_id=self.task['task_id'],answers=[dict(target='daily_work_min',value=421)],plan=False))
        rows=self.rows();daily=next(r for r in rows if len(r)>3 and r[2]=='하루 실제 작업시간');annual=next(r for r in rows if len(r)>3 and r[2]=='1년에 작업하는 날 수')
        self.assertIn('421 분/일 · 직접 입력',daily[3]);self.assertIn('연 220일',annual[3])
    def test_each_condition_row_field_keeps_its_own_quote(self):
        self.turn('20kg 상자를 하루 30회 들어요',[answer('card.lift.load_mass_kg',20,'20kg'),answer('card.lift.lift_count_day',30,'하루 30회')])
        self.turn('20kg 상자를 1분에 1번씩 하루 30분 들어요',[answer('card.lift.lift_rate_min',1,'1분에 1번씩'),answer('card.lift.minutes',30,'하루 30분')])
        rows=self.rows();rate=next(r for r in rows if len(r)>3 and '분당 들기' in str(r[2]));duration=next(r for r in rows if len(r)>3 and '하루 노출시간' in str(r[2]))
        self.assertIn('1분에 1번씩',rate[3]);self.assertIn('하루 30분',duration[3])
    def test_explicit_zero_exposure_is_visible_even_when_work_type_is_no(self):
        self.ctx.dispatch('intake_turn',dict(task_id=self.task['task_id'],answers=[dict(target='work_type.keyboard',value='NO'),dict(target='card.keyboard.C1_KEYBOARD_FOCUSED',value=0)],plan=False))
        self.assertTrue(any(len(r)>3 and '키보드' in str(r[2]) and str(r[3]).startswith('0 분/일') for r in self.rows()))
    def test_recorded_condition_completeness_has_an_output_row(self):
        self.ctx.dispatch('intake_turn',dict(task_id=self.task['task_id'],answers=[dict(target='card.lift.load_mass_kg',value=20),dict(target='card.lift.lift_count_day',value=30),dict(target='complete.lift',value='YES')],plan=False))
        self.assertTrue(any(len(r)>3 and '조건' in str(r[2]) and ('모든' in str(r[2]) or '전체' in str(r[2])) and str(r[3]).startswith('예') for r in self.rows()))
    def test_followup_replay_keeps_conflict_until_a_new_user_statement(self):
        self.turn('20kg',[answer('card.lift.load_mass_kg',20,'20kg')])
        state=self.turn('30kg',[answer('card.lift.load_mass_kg',30,'30kg')])
        fact=next(f for f in state['facts'] if f['target']=='card.lift.load_mass_kg')
        self.assertEqual((fact['value'],fact['state'],fact['conflict']['value']),(20,'CONFLICT',30))
        fixed=self.turn('20kg가 맞아요',[answer('card.lift.load_mass_kg',20,'20kg')])
        self.assertEqual(next(f for f in fixed['facts'] if f['target']=='card.lift.load_mass_kg')['state'],'KNOWN')
    def test_explicit_unknown_and_explicit_no_keep_display_provenance(self):
        self.ctx.dispatch('intake_turn',dict(task_id=self.task['task_id'],answers=[dict(target='annual_work_days',value=None),dict(target='work_type.keyboard',value='NO')],plan=False))
        rows=self.rows();annual=next(r for r in rows if len(r)>3 and r[2]=='1년에 작업하는 날 수')
        self.assertIn('모름 · 직접 입력',annual[3])
        keyboard=next(r for r in rows if len(r)>3 and '키보드' in str(r[2]) and '이 작업을 한다' in str(r[2]))
        self.assertIn('아니오 · 직접 입력',keyboard[3])
    def test_old_fact_metadata_cannot_claim_a_later_advanced_edit(self):
        from backend.report.input_trace import InputTrace
        source=dict(input_revision=6,conditions=dict(intake_session=dict(projected_revision=5,facts={
            'daily_work_min@default':dict(target='daily_work_min',condition='default',value=480,source='AI',quote='과거 8시간')})))
        self.assertIsNone(InputTrace(source).lookup('conditions',480,field='daily_work_min'))
        source['input_revision']=5
        self.assertIn('과거 8시간',InputTrace(source).lookup('conditions',480,field='daily_work_min')[1])
    def test_read_of_projected_photo_load_does_not_stale_the_next_reply(self):
        from PIL import Image
        image=self.directory/'white.png';Image.new('RGB',(32,32),'white').save(image)
        photo=self.ctx.dispatch('import_photos',dict(task_id=self.task['task_id'],file_paths=[str(image)]))['added'][0]['photo_id']
        preview=dict(views={'RIGHT':dict(guess={})},measured=[],front=[],signals={},score=None,questions=[],diagnostics=[])
        with patch('backend.service.intake.handle_quick_preview',return_value=preview):
            self.ctx.dispatch('intake_session',dict(task_id=self.task['task_id'],views={'RIGHT':photo}))
            first=self.turn('사진 속 물건은 12.5kg입니다',[answer('load_kg',12.5,'12.5kg')])
            restored=self.ctx.dispatch('intake_session',dict(task_id=self.task['task_id']))
        self.assertEqual(first['task']['input_revision'],restored['task']['input_revision'])
    def test_unloaded_coupling_evidence_does_not_change_on_a_read(self):
        from PIL import Image
        image=self.directory/'white.png';Image.new('RGB',(32,32),'white').save(image)
        photo=self.ctx.dispatch('import_photos',dict(task_id=self.task['task_id'],file_paths=[str(image)]))['added'][0]['photo_id']
        preview=dict(views={'RIGHT':dict(guess={})},measured=[],front=[],signals={},score=None,questions=[],diagnostics=[])
        with patch('backend.service.intake.handle_quick_preview',return_value=preview):
            self.ctx.dispatch('intake_session',dict(task_id=self.task['task_id'],views={'RIGHT':photo}))
            first=self.turn('손에 물건이 없고 미는 힘도 없습니다',[answer('load','UNLOADED','손에 물건이 없고 미는 힘도 없습니다')])
            second=self.ctx.dispatch('intake_session',dict(task_id=self.task['task_id']))
        self.assertEqual(first['task']['input_revision'],second['task']['input_revision'])
        self.assertEqual(first['task']['manual'],second['task']['manual'])
    def test_stale_natural_reply_is_saved_and_rebased_without_overwriting_user(self):
        old=self.ctx.require('task',self.task['task_id'])['input_revision']
        self.ctx.dispatch('intake_turn',dict(task_id=self.task['task_id'],answers=[dict(target='daily_work_min',value=421)],plan=False))
        with patch('backend.gpt.client.adaptive_intake',return_value=(dict(answers=[answer('annual_work_days',220,'연 220일')],questions=[]),None)):
            state=self.ctx.dispatch('intake_turn',dict(task_id=self.task['task_id'],text='연 220일 일해요',expected_revision=old))
        self.assertTrue(any(m['text']=='연 220일 일해요' for m in state['messages']))
        self.assertEqual(state['task']['conditions']['annual_work_days'],220)
        self.assertEqual(state['task']['conditions']['daily_work_min'],421)
    def test_a_racing_direct_save_is_not_acknowledged_as_saved(self):
        from backend.service import intake
        original=intake._save;first=True
        def race(ctx,task,session,preview):
            nonlocal first
            if first:first=False;return ctx.require('task',task['task_id']),False
            return original(ctx,task,session,preview)
        with patch('backend.service.intake._save',side_effect=race):
            state=self.ctx.dispatch('intake_turn',dict(task_id=self.task['task_id'],answers=[dict(target='daily_work_min',value=421)],plan=False))
        self.assertEqual(state['reason'],'INPUT_CHANGED')
        self.assertNotEqual(state['task']['conditions']['daily_work_min'],421)
    def test_decimal_in_initial_title_is_not_a_sentence_boundary(self):
        from backend.intake.facts import initial_title
        self.assertEqual(initial_title('12.5kg 상자를 들어요. 하루 40회입니다.'),'12.5kg 상자를 들어요')
        self.assertEqual(initial_title('일합니다.다음 문장'),'일합니다')
    def test_stale_photo_proposal_is_retained_without_binding_to_a_changed_photo(self):
        old=self.ctx.require('task',self.task['task_id'])['input_revision']
        self.ctx.dispatch('intake_turn',dict(task_id=self.task['task_id'],answers=[dict(target='daily_work_min',value=421)],plan=False))
        with patch('backend.gpt.client.adaptive_intake',return_value=(dict(answers=[answer('load_kg',12.5,'12.5kg')],questions=[]),None)):
            state=self.ctx.dispatch('intake_turn',dict(task_id=self.task['task_id'],text='12.5kg입니다',expected_revision=old))
        self.assertTrue(any(m['text']=='12.5kg입니다' for m in state['messages']))
        self.assertEqual(state['history'][-1]['requests'][0]['answers'][0]['number'],12.5)
        self.assertTrue(any(d['reason']=='PHOTO_CONTEXT_CONFIRMATION_REQUIRED' for d in state['diagnostics']))
        self.assertFalse(any(f['target']=='load_kg' and f['value']==12.5 for f in state['facts']))
    def test_racing_natural_save_retries_and_keeps_exactly_one_message(self):
        from backend.service import intake
        original=intake._save;first=True
        def race(ctx,task,session,preview):
            nonlocal first
            if first:first=False;return ctx.require('task',task['task_id']),False
            return original(ctx,task,session,preview)
        with patch('backend.service.intake._save',side_effect=race),patch('backend.gpt.client.adaptive_intake',return_value=(dict(answers=[answer('annual_work_days',220,'연 220일')],questions=[]),None)):
            state=self.ctx.dispatch('intake_turn',dict(task_id=self.task['task_id'],text='연 220일 일해요'))
        self.assertEqual(sum(m['text']=='연 220일 일해요' for m in state['messages']),1)
        self.assertEqual(state['task']['conditions']['annual_work_days'],220)
    def delayed_load(self,change_photo):
        import threading
        from PIL import Image
        image=self.directory/'white.png';Image.new('RGB',(32,32),'white').save(image)
        photos=self.ctx.dispatch('import_photos',dict(task_id=self.task['task_id'],file_paths=[str(image),str(image)]))['added']
        preview=dict(views={'RIGHT':dict(guess={})},measured=[],front=[],signals={},score=None,questions=[],diagnostics=[])
        entered=threading.Event();release=threading.Event();result=[]
        def provider(payload,*args):
            if payload['phase']=='EXTRACT_AND_PLAN':
                entered.set()
                if not release.wait(10):raise AssertionError('test coordinator did not release response')
                return dict(answers=[answer('load_kg',12.5,'12.5kg')],questions=[]),None
            return dict(answers=[],questions=[]),None
        with patch('backend.service.intake.handle_quick_preview',return_value=preview),patch('backend.gpt.client.adaptive_intake',side_effect=provider):
            self.ctx.dispatch('intake_session',dict(task_id=self.task['task_id'],views={'RIGHT':photos[0]['photo_id']}))
            worker=threading.Thread(target=lambda:result.append(self.ctx.dispatch('intake_turn',dict(task_id=self.task['task_id'],text='사진 속 물건은 12.5kg입니다'))))
            worker.start()
            try:
                self.assertTrue(entered.wait(10))
                self.ctx.dispatch('intake_turn',dict(task_id=self.task['task_id'],answers=[dict(target='daily_work_min',value=421)],plan=False))
                if change_photo:self.ctx.dispatch('intake_session',dict(task_id=self.task['task_id'],views={'RIGHT':photos[1]['photo_id']}))
            finally:release.set();worker.join(10)
        self.assertFalse(worker.is_alive());self.assertEqual(len(result),1)
        return result[0]
    def test_late_photo_value_survives_an_unrelated_edit_when_photo_is_unchanged(self):
        state=self.delayed_load(False)
        self.assertEqual(next(f['value'] for f in state['facts'] if f['target']=='load_kg'),12.5)
        self.assertEqual(state['task']['conditions']['daily_work_min'],421)
    def test_late_photo_value_keeps_its_proposal_after_the_photo_changes(self):
        state=self.delayed_load(True)
        self.assertFalse(any(f['target']=='load_kg' and f['value']==12.5 for f in state['facts']))
        self.assertTrue(any(d['reason']=='PHOTO_CONTEXT_CONFIRMATION_REQUIRED' for d in state['diagnostics']))
        self.assertTrue(any(r['answers'] and r['answers'][0]['number']==12.5 for t in state['history'] for r in t['requests']))

if __name__=='__main__':unittest.main()
