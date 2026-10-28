"""Successful AI text retains the server's available current score, without retrying."""
import copy
import json
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from backend.gpt import client,payload
from test_v2_gpt import summary_fixture,content_fixture


class CurrentRebaExplanation(unittest.TestCase):
    def summary(self,*,provisional=True):
        value=summary_fixture()
        value['reba']=dict(current_score=dict(total=8,risk='HIGH',kind='WITH_ASSUMPTIONS',assumed_count=23))
        if provisional:value['provisional_reba']=dict(initial_total=7,initial_risk='MEDIUM',analysis_currentness='CURRENT',final_complete=False)
        return value

    def test_current_eight_is_distinct_from_first_seven_and_incomplete_final(self):
        value=self.summary();before=copy.deepcopy(value);text=payload.reba_comparison_text(value)
        self.assertIn('현재 REBA는 8점',text);self.assertIn('가정 포함',text);self.assertIn('미확인 23개',text)
        self.assertIn('실제 점수는 이 점수보다 높거나 낮을 수 있습니다',text)
        self.assertIn('1차 가정 REBA는 7점',text);self.assertIn('점수 차이를 비교하지 않습니다',text)
        self.assertNotIn('+1점',text);self.assertEqual(value,before)

    def test_without_a_first_pass_the_current_score_is_still_in_the_same_field(self):
        value=self.summary(provisional=False);text=payload.reba_comparison_text(value)
        self.assertIn('현재 REBA는 8점',text);self.assertNotIn('1차',text)
        self.assertTrue(payload.validate_content(content_fixture(value),value))

    def test_positive_yes_basis_allows_nonbinding_applicable_proposal_when_calculation_needs_input(self):
        value=self.summary(provisional=False)
        value['criteria'][0].update(computed_status='NEEDS_INPUT',basis=[
            dict(item_code='C01-B01',value='YES',unit='BOOLEAN',operator='EQ',threshold=None)])
        content=content_fixture(value)
        content['criteria'][0].update(proposed_status='APPLICABLE',basis_refs=['C01-B01'])

        self.assertTrue(payload.validate_content(content,value))
        self.assertEqual(value['criteria'][0]['computed_status'],'NEEDS_INPUT',
                         'the AI proposal is only a review hint and must not change the computed result')

    def test_confirmed_assumed_reference_and_score_so_far_keep_different_meanings(self):
        value=self.summary(provisional=False)
        value['reba']['current_score']['kind']='CONFIRMED'
        self.assertIn('완성 계산 점수',payload.reba_comparison_text(value))
        self.assertNotIn('가정 포함',payload.reba_comparison_text(value))
        value['reba']['current_score']=dict(total=1,risk='NEGLIGIBLE',kind='ASSUMED_REFERENCE')
        text=payload.reba_comparison_text(value)
        self.assertIn('참조값은 1점',text);self.assertIn('측정값이나 확정 점수가 아닙니다',text)
        value['reba']=dict(score_so_far=dict(total=8,risk='HIGH',assumed_count=23))
        text=payload.reba_comparison_text(value)
        self.assertIn('현재 REBA는 8점',text)
        self.assertIn('가정 포함',text)
        self.assertIn('실제 점수는 이 점수보다 높거나 낮을 수 있습니다',text)

    def test_no_available_score_retains_the_previous_comparison_behavior(self):
        value=self.summary();value['reba']={}
        self.assertEqual(payload.reba_comparison_text(value),'1차 가정 REBA는 7점(보통)입니다. 최종 REBA 계산이 미완성이라 점수 차이를 비교하지 않습니다.')
        value.pop('provisional_reba')
        self.assertEqual(payload.reba_comparison_text(value),'')

    def test_stale_context_is_not_called_the_current_input_score(self):
        value=self.summary();value['provisional_reba']['analysis_currentness']='STALE'
        text=payload.reba_comparison_text(value)
        self.assertIn('저장 당시 REBA는 8점',text);self.assertNotIn('현재 REBA는 8점',text)

    def test_existing_server_owned_comparison_adds_score_to_successful_generation(self):
        for provisional in (False,True):
            with self.subTest(provisional=provisional):
                value=self.summary(provisional=provisional);before=copy.deepcopy(value)
                original=content_fixture(value);original['summary']='최종 완성 점수는 아직 없습니다.';original['reba_comparison']=''
                frozen=copy.deepcopy(original)
                response=SimpleNamespace(status='completed',output_text=json.dumps(original),id='replay_only',model='fixture-model',reasoning=None)
                with patch.object(client,'create_response',return_value=response) as transport:
                    content,reason=client.generate(value,'fixture-model','replay-key')
                self.assertIsNone(reason);self.assertEqual(transport.call_count,1)
                self.assertEqual(content['summary'],frozen['summary'])
                self.assertIn('현재 REBA는 8점',client.content_text(content))
                self.assertEqual(original,frozen);self.assertEqual(value,before)


if __name__=='__main__':unittest.main()
