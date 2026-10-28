"""SQLite receipts for stated work inputs reaching photo scoring and explanation."""
import copy
from pathlib import Path
from unittest.mock import patch
import unittest

import test_adaptive_intake as fixtures
from test_photo_fact_ownership import observation, preview
import test_score_so_far as score_fixtures
from backend.gpt.payload import build_numeric_summary


TEXT=('사진은 한 사람의 전신이 나온 평소의 같은 작업입니다. 상자 1개당 20kg을 옮깁니다. '
      '연간 200일, 하루 총 60분, 분당 2회, 하루 120회입니다. 충격은 없고 1분 이상 유지하지 않습니다.')


class InputLinkageService(unittest.TestCase):
    setUp=fixtures.AdaptiveIntake.setUp
    turn=fixtures.AdaptiveIntake.turn
    finish_analysis=score_fixtures.ScoreSoFarInOutputs.finish_analysis

    def prepare(self):
        photo=Path(self.temp.name)/'RIGHT.fixture';photo.write_bytes(b'synthetic photo')
        identity=self.ctx.store('create_photo',self.identity,dict(file_path=str(photo),file_name=photo.name,
            width_px=1,height_px=1,consent='UNKNOWN',notes=[]))
        views=dict(RIGHT=identity)
        rows=[observation('RIGHT','COMMON','trunk_base',3,40),observation('RIGHT','RIGHT','upper_arm_base',3,60)]
        inference=patch('backend.service.intake.handle_quick_preview',return_value=preview(rows,views))
        inference.start();self.addCleanup(inference.stop)
        self.ctx.dispatch('intake_session',dict(task_id=self.identity,views=views))
        self.turn([fixtures.answer('context','YES'),fixtures.answer('load','MEASURED')],plan=False)
        raw=dict(answers=[
            fixtures.model('card.lift.load_mass_kg',number=20,condition='상자',quote='상자 1개당 20kg'),
            fixtures.model('card.lift.lift_count_day',number=120,condition='상자',quote='하루 120회'),
            fixtures.model('card.lift.lift_rate_min',number=2,condition='상자',quote='분당 2회'),
            fixtures.model('card.lift.minutes',number=60,condition='상자',quote='하루 총 60분'),
            fixtures.model('daily_work_min',number=60,quote='하루 총 60분'),
            fixtures.model('annual_work_days',number=200,quote='연간 200일'),
        ],questions=[])
        return self.turn(text=TEXT,raw=raw),identity

    def test_stated_inputs_survive_save_reopen_scoring_and_explanation(self):
        state,photo_id=self.prepare();task=state['task']
        self.assertEqual(task['capture']['slots'][0]['observation']['measured_load_kg'],20)
        self.assertEqual(task['conditions']['daily_work_min'],60)
        self.assertEqual(task['conditions']['annual_work_days'],200)
        self.assertEqual(task['legal']['criteria'][7]['rows'][0]['load_mass_kg'],20)
        self.assertEqual(task['legal']['criteria'][7]['rows'][0]['lift_count_day'],120)
        self.assertEqual(task['legal']['criteria'][9]['rows'][0]['lift_rate_min'],2)
        self.assertEqual(task['legal']['criteria'][9]['rows'][0]['minutes'],60)
        self.assertFalse({'load_kg','load_link'} & {q['target'] for q in state['questions']})
        reopened=self.ctx.dispatch('intake_session',dict(task_id=self.identity))
        self.assertEqual(reopened['task']['input_revision'],task['input_revision'])
        self.assertEqual(reopened['task']['capture'],task['capture'])
        analysis=self.finish_analysis();before=copy.deepcopy(analysis['snapshot'])
        self.assertEqual(analysis['reba']['slots'][0]['effective_load_kg'],20)
        self.assertNotIn('observation.measured_load_kg',analysis['reba']['summary']['current_score']['assumed'])
        summary=build_numeric_summary(analysis)
        self.assertEqual(summary['posture_results'][0]['effective_load_kg'],20)
        self.assertEqual(summary['posture_results'][0]['current_score']['total'],analysis['reba']['summary']['current_score']['total'])
        self.assertEqual(analysis['snapshot'],before)

    def test_direct_work_weight_edit_updates_only_the_link_and_keeps_old_analysis(self):
        state,_=self.prepare();old=self.finish_analysis();snapshot=copy.deepcopy(old['snapshot'])
        updated=self.turn([fixtures.answer('card.lift.load_mass_kg',30,'상자')],plan=False)['task']
        self.assertEqual(updated['capture']['slots'][0]['observation']['measured_load_kg'],30)
        restored=self.ctx.dispatch('get_analysis',dict(analysis_id=old['analysis_id']))
        self.assertEqual(restored['snapshot'],snapshot)
        self.assertEqual(restored['snapshot']['capture']['slots'][0]['observation']['measured_load_kg'],20)

    def test_a_photo_specific_weight_is_not_replaced_by_the_shared_work_weight(self):
        from test_input_linkage import session
        from backend.intake import facts,input_links
        from backend.engine.task_defaults import task_input
        source=session()
        prior=facts.project(task_input({}),source['facts'],source['views'],dict(views={}))
        specific=next(slot for slot in prior['capture']['slots'] if slot['photo_id']==10)
        specific['observation'].update(load_state='MEASURED',measured_load_kg=7,
            evidence=dict(source='DIRECT_OBSERVATION',text='이 사진의 물건은 7kg',observed_at=None))
        linked=input_links.synchronize(source)
        projected=facts.project(prior,linked,source['views'],dict(views={}))
        self.assertEqual({s['photo_id']:s['observation']['measured_load_kg'] for s in projected['capture']['slots']},{9:20,10:7,11:20})
        self.assertEqual(next(s for s in projected['capture']['slots'] if s['photo_id']==10)['observation']['evidence']['text'],'이 사진의 물건은 7kg')


if __name__=='__main__':unittest.main()
