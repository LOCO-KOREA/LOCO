"""Optional null evidence must not become an invented additional input request."""
import copy
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from backend.gpt import client,payload
from backend.service.application import create_service


def summary_fixture():
    criteria=[dict(criterion_no=number,computed_status='NEEDS_INPUT',effective_status='NEEDS_INPUT',
                   missing_fields=[f'criteria.{number}.input_needed'],review_reasons=[],basis=[])
              for number in range(1,12)]
    criteria[7].update(computed_status='NOT_APPLICABLE',effective_status='NOT_APPLICABLE',missing_fields=[],basis=[
        dict(item_code='C08-B01',value='YES',unit='BOOLEAN',operator='EQ',threshold=None),
        dict(item_code='C08-B02',value='NO',unit='BOOLEAN',operator='EQ',threshold=None),
        dict(item_code='C08-B03',value=20,unit='KG',operator='GE',threshold=25),
        dict(item_code='C08-B04',value=120,unit='COUNT_DAY',operator='GE',threshold=10),
        dict(item_code='C08-B05',value=None,unit='COUNT_DAY',operator='GE',threshold=10),
        dict(item_code='C08-B06',value=0,unit='COUNT_DAY',operator='GE',threshold=10),
        dict(item_code='C08-B07',value='UNKNOWN',unit='BOOLEAN',operator='EQ',threshold=None)])
    criteria[8]['basis']=[dict(item_code='C09-B05',value=None,unit='COUNT_DAY',operator='GE',threshold=25)]
    criteria[0].update(investigator_status='NOT_APPLICABLE',effective_status='NOT_APPLICABLE',
                       effective_source='INVESTIGATOR',basis=[dict(item_code='C01-B01',value=None,unit='MIN_DAY')])
    return dict(criteria=criteria,recorded_work_inputs=[dict(field='card.lift.lift_count_day',value=120,condition_ref='작업 조건 1')])


def content_fixture(summary):
    return dict(summary='기록된 입력과 계산 초안을 설명합니다.',reba_comparison=payload.reba_comparison_text(summary),
                posture_explanations=[dict(photo_ref=row['photo_ref'],explanation='사진의 측정 결과입니다.')
                                      for row in summary.get('posture_results',[])],
                criteria=[dict(criterion_no=number,explanation='기록된 계산 초안입니다.',basis_refs=[],proposed_status='UNDETERMINED')
                          for number in range(1,12)],check_items=[],improvement_options=[])


def response_fixture(summary):
    return SimpleNamespace(status='completed',output_text=json.dumps(content_fixture(summary),ensure_ascii=False),
                           id='fixture-response',model='fixture-model',reasoning=dict(effort='high'))


class ExplanationConfirmationView(unittest.TestCase):
    def test_resolved_optional_nulls_are_removed_without_renumbering_or_changing_known_values(self):
        summary=summary_fixture();before=copy.deepcopy(summary)
        request=client.explanation_request_summary(summary)
        self.assertEqual([row['item_code'] for row in request['criteria'][7]['basis']],
                         ['C08-B01','C08-B02','C08-B03','C08-B04','C08-B06'])
        self.assertEqual([row['value'] for row in request['criteria'][7]['basis']],['YES','NO',20,120,0])
        self.assertIsNone(request['criteria'][7]['basis'][0]['threshold'])
        self.assertEqual(request['recorded_work_inputs'],summary['recorded_work_inputs'])
        self.assertEqual(summary,before)
        request['criteria'][7]['basis'][0]['value']='NO'
        self.assertEqual(summary,before,'the model view must be a deep copy')

    def test_real_missing_location_values_and_incomplete_calculation_under_human_override_remain(self):
        summary=summary_fixture();request=client.explanation_request_summary(summary)
        self.assertEqual(request['criteria'][8],summary['criteria'][8])
        self.assertEqual(request['criteria'][0],summary['criteria'][0])

    def test_review_or_missing_evidence_and_unspecified_legacy_status_are_not_suppressed(self):
        for change in [dict(computed_status='NEEDS_REVIEW'),dict(missing_fields=['criteria.8.input_needed']),
                       dict(review_reasons=['UNION_REVIEW']),dict(computed_status=None),
                       dict(missing_fields=None),dict(review_reasons=None)]:
            with self.subTest(change=change):
                summary=summary_fixture();summary['criteria'][7].update(change)
                request=client.explanation_request_summary(summary)
                self.assertEqual(request['criteria'][7],summary['criteria'][7])

    def test_generate_sends_only_the_model_view_and_preserves_original_summary(self):
        summary=summary_fixture();before=copy.deepcopy(summary)
        with patch('backend.gpt.client.create_response',return_value=response_fixture(summary)) as provider:
            content,reason=client.generate(summary,'fixture-model','fixture-key',dict(gpt_reasoning_effort='high'))
        self.assertIsNone(reason);self.assertIsNotNone(content)
        sent=json.loads(provider.call_args.kwargs['input'][1]['content'])
        self.assertEqual(sent,client.explanation_request_summary(summary))
        self.assertNotIn('C08-B05',[row['item_code'] for row in sent['criteria'][7]['basis']])
        self.assertEqual(summary,before)

    def test_saved_summary_snapshot_and_existing_currentness_are_unchanged_by_request_projection(self):
        with tempfile.TemporaryDirectory() as directory:
            ctx=create_service(str(Path(directory)/'confirmation.db'))
            survey=ctx.dispatch('create_survey',dict(draft=dict(title='Confirmation view')))
            task=ctx.dispatch('create_task',dict(survey_id=survey['survey_id'],draft=dict(task_name='20kg 상자')))
            ctx.dispatch('intake_turn',dict(task_id=task['task_id'],plan=False,answers=[
                dict(target='work_type.lift',condition='default',value='YES'),
                dict(target='card.lift.load_mass_kg',condition='상자',value=20),
                dict(target='card.lift.lift_count_day',condition='상자',value=120),
                dict(target='complete.lift',condition='default',value='YES')]))
            analysis=ctx.dispatch('recalculate_judgments',dict(task_id=task['task_id']))
            original_snapshot=copy.deepcopy(analysis['snapshot'])
            summary=payload.build_numeric_summary(analysis);before=copy.deepcopy(summary)
            settings=ctx.settings();settings.update(gpt_enabled=True,gpt_model='fixture-model')
            ctx.dispatch('update_settings',dict(settings=settings))
            with patch.dict('os.environ',OPENAI_API_KEY='fixture-key'),patch('backend.gpt.client.create_response',return_value=response_fixture(summary)):
                created=ctx.dispatch('generate_ai_text',dict(analysis_id=analysis['analysis_id']))
            self.assertEqual(created['text']['result'],'GENERATED',created['text'].get('fallback_reason'))
            self.assertEqual(created['text']['input_summary'],before)
            reopened=ctx.dispatch('get_analysis',dict(analysis_id=analysis['analysis_id']))
            self.assertTrue(reopened['ai'][-1]['source_current'])
            client.explanation_request_summary(reopened['ai'][-1]['input_summary'])
            after=ctx.dispatch('get_analysis',dict(analysis_id=analysis['analysis_id']))
            self.assertTrue(after['ai'][-1]['source_current'])
            self.assertEqual(after['snapshot'],original_snapshot)
            self.assertEqual(after['ai'][-1]['input_summary'],before)


if __name__=='__main__':unittest.main()
