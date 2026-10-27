"""Tests for the strict, identifier-free GPT explanation boundary."""
import json
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from ergo.gpt import client, payload
from ergo.service import analysis_records


def summary_fixture():
    return {'criteria': [
        {'criterion_no': n, 'basis': [{'item_code': f'C{n:02d}-B01', 'value': n * 10,
                                      'unit': 'MIN_DAY', 'operator': 'GE', 'threshold': 120}]}
        for n in range(1, 12)]}


def content_fixture(summary):
    comparison=summary.get('provisional_reba')
    reba_comparison=payload.reba_comparison_text(summary)
    return {'summary': '입력 근거를 기준별로 확인하세요.', 'reba_comparison': reba_comparison, 'posture_explanations': [
            {'photo_ref': item['photo_ref'], 'explanation': '사진 결과를 확인하세요.'}
            for item in summary.get('posture_results', [])],
        'criteria': [{'criterion_no': n, 'explanation': '입력값을 다시 확인하세요.',
                      'basis_refs': [item['item_code'] for item in summary['criteria'][n-1]['basis'][:1]]} for n in range(1, 12)],
        'check_items': ['현장 조건을 확인하세요.'],
        'improvement_options': [{'proposal': '작업 조건을 조사자와 함께 검토하세요.',
                                 'basis_refs': ([summary['criteria'][0]['basis'][0]['item_code']] if summary['criteria'][0]['basis'] else []), 'needs_confirmation': True}]}


class GptBoundary(unittest.TestCase):
    def test_numeric_summary_does_not_send_names_paths_or_photo_ids(self):
        analysis = {'snapshot': {
            'schema_version': '2.0', 'task_id': 8181, 'task_name': '비밀 작업명',
            'conditions': {'worker_code': '비밀 작업자 코드', 'method_description': '비밀 자유 문장'},
            'analysis_scope': {'judgment': True, 'pose': True, 'tags': True, 'reba': True},
            'capture': {'slots': [{'slot_no': 7, 'photo_id': 9191, 'label': '민감한 사진 이름',
                                  'analysis_target': True}], 'protocol': 'GENERAL_STILLS_V1'},
            'settings': {'burden_rule': 'MOEL_2020_12_GENERAL_V2', 'reba_rule': 'REBA_TABLE_2000_V2',
                         'posture_profile': {'version': 'POSTURE_TECH_V1'}}},
            'judgment': {'judgments': [{'criterion_no': 1, 'basis': [{'item_code': 'criteria.1.minutes',
                'value': 240, 'unit': 'MIN_DAY', 'operator': 'GE', 'threshold': 240}],
                'computed_status': 'APPLICABLE', 'investigator': {'status': None}, 'effective_status': 'APPLICABLE'}]},
            'pose': {'valid_count': 1}, 'reba': {'summary': {'complete_count': 1, 'available_max': 5, 'full_max': 5}},
            'tags': [], 'module_states': {}}
        encoded = json.dumps(payload.build_numeric_summary(analysis), ensure_ascii=False)
        for private in ('비밀 작업명', '비밀 작업자 코드', '비밀 자유 문장', '민감한 사진 이름', '8181', '9191', 'criteria.1.minutes'):
            self.assertNotIn(private, encoded)
        self.assertIn('C01-B01', encoded)

    def test_posture_summary_contains_every_target_but_never_ids_or_coordinates(self):
        analysis = {
            'snapshot': {'schema_version':'2.0','analysis_scope':{'pose':True,'reba':True},
                'capture':{'slots':[{'slot_no':7,'photo_id':9901,'label':'민감한 사진명','analysis_target':True},
                                   {'slot_no':11,'photo_id':9902,'label':'다른 사진명','analysis_target':True}]},
                'settings':{'burden_rule':'B','reba_rule':'R','posture_profile':{'version':'P'}}},
            'judgment': {'judgments': []}, 'module_states': {'pose':'COMPLETE','reba':'INCOMPLETE'},
            'pose': {'valid_count':1,'slots':[
                {'slot_no':7,'status':'VALID','engine':{'model_id':'mediapipe-heavy','version':'v2','actual_model_sha256':'secret-hash'},
                 'points':[{'name':'left_shoulder','x_px':123.4,'y_px':456.7,'confidence':.93}],
                 'angles':[{'side':'LEFT','angle_code':'TRUNK_TILT_VERT','value_deg':22.5,'min_confidence':.91,'diagnostic':None}],
                 'world_angles':[{'side':'LEFT','angle_code':'UPPER_ARM_WORLD','value_deg':43.2,'min_confidence':.88}]},
                {'slot_no':11,'status':'ERROR','diagnostics':[{'code':'MODEL_ERROR','message':r'C:\private\photo.jpg'}], 'points':[], 'angles':[]}]},
            'reba': {'summary':{'complete_count':0,'available_max':4,'full_max':None},'slots':[
                {'slot_no':7,'status':'INCOMPLETE','effective_load_kg':3.5,'selected_side':None,'total':None,'risk':None,
                 'left':{'trunk':2,'neck':1,'legs':2,'table_a':3,'load_score':0,'score_a':3,'upper_arm':2,'lower_arm':1,
                         'wrist':1,'table_b':2,'coupling_score':0,'score_b':2,'table_c':4,'activity_score':0,'total':4,
                         'risk':'MEDIUM','missing_fields':['common.neck_base'],'review_reasons':['INPUT_CONFLICT']},
                 'right':{'total':4,'risk':'MEDIUM','missing_fields':[],'review_reasons':[]},'missing_fields':['common.neck_base'],
                 'candidates':[{'scope':'COMMON','field':'trunk_base','proposed_value':2,'angles':[{'value_deg':22.5}],
                                'min_confidence':.91,'review_reasons':['BOUNDARY_REVIEW']}]}
            ]}, 'tags':[],
        }
        summary=payload.build_numeric_summary(analysis)
        encoded=json.dumps(summary,ensure_ascii=False)
        self.assertEqual([row['photo_ref'] for row in summary['posture_results']],['사진 1','사진 2'])
        self.assertEqual(summary['posture_results'][0]['angles'][0]['value_deg'],22.5)
        self.assertEqual(summary['posture_results'][0]['inferred_world_angles'][0]['used_for_reba'],False)
        self.assertEqual(summary['posture_results'][0]['left']['table_c'],4)
        content=content_fixture(summary)
        self.assertTrue(payload.validate_content(content,summary))
        content['posture_explanations'].pop()
        self.assertFalse(payload.validate_content(content,summary),'every target photo needs a matching explanation')
        content=content_fixture(summary);content['posture_explanations'][0]['photo_ref']='사진 9'
        self.assertFalse(payload.validate_content(content,summary),'photo refs must remain exact and ordered')
        content=content_fixture(summary);content['posture_explanations'][0]['photo_ref']=None
        self.assertFalse(payload.validate_content(content,summary),'photo refs must be strings')
        duplicate_summary={**summary,'posture_results':[summary['posture_results'][0],{**summary['posture_results'][1],'photo_ref':'사진 1'}]}
        self.assertFalse(payload.validate_content(content_fixture(duplicate_summary),duplicate_summary),'expected photo refs must be unique')
        for private in ('9901','9902','민감한 사진명','123.4','456.7','secret-hash','C:\\private'):
            self.assertNotIn(private,encoded)
        self.assertNotIn('x_px',encoded)

    def test_provisional_reba_is_validated_scoped_and_linked_without_photo_ids(self):
        def analysis(slots, complete_count, full_max):
            return {'currentness':'CURRENT','snapshot': {'schema_version':'2.0','analysis_scope':{'pose':True,'reba':True},
                'capture':{'slots':slots},'settings':{'burden_rule':'B','reba_rule':'R','posture_profile':{'version':'P'}}},
                'judgment':{'judgments':[]},'pose':{'valid_count':len(slots),'slots':[]},'tags':[],
                'module_states':{'pose':'COMPLETE','reba':'COMPLETE' if complete_count==len([x for x in slots if x['analysis_target']]) else 'INCOMPLETE'},
                'reba':{'summary':{'complete_count':complete_count,'available_max':full_max,'full_max':full_max}}}
        one=[{'slot_no':4,'photo_id':31,'analysis_target':True}]
        saved=analysis(one,1,5)
        first={'total':7,'risk':'MEDIUM','photo_ids':[31]}
        summary=payload.build_numeric_summary(saved,provisional_reba=first)
        comparison=summary['provisional_reba']
        self.assertTrue(comparison['same_photo_scope'])
        self.assertTrue(comparison['comparable'])
        self.assertEqual(comparison['score_delta'],-2)
        self.assertEqual(comparison['final_risk'],'MEDIUM')
        encoded=json.dumps(summary,ensure_ascii=False)
        self.assertNotIn('31',encoded,'raw photo IDs must not enter the model summary')
        self.assertTrue(payload.validate_content(content_fixture(summary),summary))
        content=content_fixture(summary);content['reba_comparison']=''
        self.assertFalse(payload.validate_content(content,summary),'comparison context requires an explanation')
        self.assertIn('REBA 현재 점수와 계산 설명',client.content_text(content_fixture(summary)))

        stored=payload.normalize_provisional_reba_input(saved,first)
        self.assertEqual(payload.build_numeric_summary(saved,provisional_reba=stored),summary)
        changed=analysis([{'slot_no':4,'photo_id':32,'analysis_target':True}],1,5)
        self.assertNotEqual(payload.build_numeric_summary(changed,provisional_reba=stored),summary,
                            'changing the final photo scope makes the saved comparison stale')

        two_slots=[{'slot_no':4,'photo_id':31,'analysis_target':True},
                   {'slot_no':8,'photo_id':32,'analysis_target':True}]
        multi=payload.build_numeric_summary(analysis(two_slots,2,8),provisional_reba={'total':7,'risk':'MEDIUM','photo_ids':[31,32]})['provisional_reba']
        self.assertTrue(multi['same_photo_scope'])
        self.assertFalse(multi['comparable'],'the provisional score combines views; multi-photo scores are not directly comparable')
        self.assertIsNone(multi['score_delta'])
        mismatch=payload.build_numeric_summary(analysis([
            {'slot_no':4,'photo_id':31,'analysis_target':True},
            {'slot_no':8,'photo_id':32,'analysis_target':False}],1,5),
            provisional_reba={'total':7,'risk':'MEDIUM','photo_ids':[32]})['provisional_reba']
        self.assertFalse(mismatch['same_photo_scope'])
        self.assertEqual(mismatch['comparison_status'],'DIFFERENT_PHOTO_SCOPE')
        self.assertIsNone(mismatch['score_delta'])
        stale=analysis(one,1,5)
        stale['currentness']='STALE'
        stale_comparison=payload.build_numeric_summary(stale,provisional_reba=first)['provisional_reba']
        self.assertEqual(stale_comparison['analysis_currentness'],'STALE')
        self.assertEqual(stale_comparison['comparison_status'],'STALE_ANALYSIS')
        self.assertFalse(stale_comparison['comparable'])
        self.assertIsNone(stale_comparison['score_delta'])
        self.assertIn('현재 작업 입력에 대한 결과가 아닙니다.',client.fallback_text({'provisional_reba':stale_comparison}))
        unverified=analysis(one,1,5)
        del unverified['currentness']
        unverified_comparison=payload.build_numeric_summary(unverified,provisional_reba=first)['provisional_reba']
        self.assertEqual(unverified_comparison['analysis_currentness'],'UNKNOWN')
        self.assertEqual(unverified_comparison['comparison_status'],'CURRENTNESS_UNVERIFIED')
        self.assertFalse(unverified_comparison['comparable'])
        self.assertIsNone(unverified_comparison['score_delta'])

        persisted=analysis(one,1,5)
        persisted.update(analysis_id=71,task_id=8,input_revision=3,ai=[])
        saved_scope=payload.normalize_provisional_reba_input(persisted,first)
        persisted['ai'].append({'purpose':'TASK_EXPLANATION','provisional_reba_input':saved_scope,
            'input_summary':payload.build_numeric_summary(persisted,provisional_reba=saved_scope,analysis_currentness='CURRENT')})
        class ReadContext:
            def require(self, kind, identity):
                if kind=='analysis':
                    return persisted
                if kind=='task':
                    return {'input_revision':4,'latest_analysis_id':72}
                raise AssertionError(kind)
        with patch.object(analysis_records.gpt_payload,'build_numeric_summary',wraps=payload.build_numeric_summary) as build:
            saved_record=analysis_records.analysis(ReadContext(),71)
        self.assertEqual(saved_record['currentness'],'STALE')
        self.assertFalse(saved_record['ai'][0]['source_current'])
        self.assertEqual(build.call_args.kwargs['analysis_currentness'],'STALE')
        incomplete=payload.build_numeric_summary(analysis(one,0,None),provisional_reba=first)['provisional_reba']
        self.assertFalse(incomplete['final_complete'])
        self.assertIsNone(incomplete['final_total'])
        self.assertIsNone(incomplete['score_delta'])
        with self.assertRaises(ValueError): payload.build_numeric_summary(saved,provisional_reba={'total':7,'risk':'LOW','photo_ids':[31]})
        with self.assertRaises(ValueError): payload.build_numeric_summary(saved,provisional_reba={'total':7,'risk':'MEDIUM','photo_ids':[999]})

    def test_generated_reba_comparison_is_server_owned_not_model_direction(self):
        summary = summary_fixture()
        summary['posture_results'] = []
        summary['provisional_reba'] = {
            'initial_total': 7, 'initial_risk': 'MEDIUM', 'initial_photo_count': 1,
            'final_photo_count': 1, 'same_photo_scope': True, 'final_complete': True,
            'final_total': 5, 'final_risk': 'MEDIUM', 'analysis_currentness': 'CURRENT',
            'comparable': True, 'comparison_status': 'COMPARABLE', 'score_delta': -2,
        }
        content = content_fixture(summary)
        content['reba_comparison'] = '1차 7점, 최종 5점으로 2점 올랐습니다.'
        response = SimpleNamespace(status='completed', output_text=json.dumps(content), id='response-test', model='test-model')
        class FakeResponses:
            def create(self, **kwargs):
                return response
        class FakeOpenAI:
            def __init__(self, **kwargs):
                self.responses = FakeResponses()
        fake_module = SimpleNamespace(OpenAI=FakeOpenAI)
        settings = {'gpt_timeout_seconds': 1, 'gpt_max_output_tokens': 100, 'gpt_reasoning_effort': ''}
        with patch.dict('sys.modules', {'openai': fake_module}), patch.object(client.config, 'connection', return_value={}):
            generated, reason = client.generate(summary, 'test-model', 'test-key', settings)
        self.assertIsNone(reason)
        self.assertEqual(generated['reba_comparison'], payload.reba_comparison_text(summary))
        self.assertIn('-2점(낮아짐)', generated['reba_comparison'])
        self.assertNotIn('올랐습니다', generated['reba_comparison'])

    def test_structured_content_must_reference_its_own_criterion(self):
        summary = summary_fixture(); content = content_fixture(summary)
        self.assertTrue(payload.validate_content(content, summary))
        content['criteria'][0]['basis_refs'] = ['C02-B01']
        self.assertFalse(payload.validate_content(content, summary))

    def test_extra_criteria_and_unsent_numbers_are_rejected(self):
        summary = summary_fixture(); content = content_fixture(summary)
        content['criteria'].append({'criterion_no': 12, 'explanation': '추가', 'basis_refs': []})
        self.assertFalse(payload.validate_content(content, summary))
        content = content_fixture(summary)
        content['criteria'][0]['explanation'] = '999분이 확인됐습니다.'
        self.assertFalse(payload.validate_content(content, summary))

    def test_numbers_quoted_from_the_summarys_own_criterion_text_are_allowed(self):
        summary = summary_fixture(); content = content_fixture(summary)
        summary['public_criteria'] = ['7호: 한 손 중량이 4.5kg 이상, 하루 120분 이상인지 확인한다.']
        content['criteria'][0]['explanation'] = '4.5kg 이상이고 120분 이상인지 확인하세요.'
        self.assertTrue(payload.validate_content(content, summary))
        content['criteria'][0]['explanation'] = '4.6kg 이상이고 120분 이상인지 확인하세요.'
        self.assertFalse(payload.validate_content(content, summary))

    def test_prompt_demands_all_eleven_criteria_and_bare_basis_codes(self):
        self.assertIn('1호부터 11호까지 11개', client.SYSTEM_PROMPT)
        self.assertIn('근거 코드', client.SYSTEM_PROMPT)
        self.assertIn('초안', client.SYSTEM_PROMPT)
        self.assertIn('단정하지', client.SYSTEM_PROMPT)
        self.assertIn('posture_results', client.SYSTEM_PROMPT)
        self.assertIn('3D 추정각은 used_for_reba', client.SYSTEM_PROMPT)
        self.assertIn('posture_explanations', client.SYSTEM_PROMPT)
        self.assertIn('빠짐없이 한 번씩', client.SYSTEM_PROMPT)
        self.assertIn('provisional_reba',client.SYSTEM_PROMPT)
        self.assertIn('답변만의 효과',client.SYSTEM_PROMPT)

    def test_missing_key_returns_fallback_without_creating_an_api_client(self):
        content, reason = client.generate({}, 'test-model', None)
        self.assertIsNone(content)
        self.assertEqual(reason, 'NO_API_KEY')



class WarmUp(unittest.TestCase):
    def test_warm_up_loads_the_sdk_in_the_background_without_blocking_or_failing(self):
        import sys
        thread = client.warm_up()
        self.assertTrue(thread.daemon)
        thread.join(120)
        self.assertIn('openai', sys.modules)

if __name__ == '__main__':
    unittest.main()
