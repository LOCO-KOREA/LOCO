"""Adversarial checks for the investigation context and conditional appendix export."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from openpyxl import load_workbook

from ergo.engine.survey_defaults import blank_response, normalize_survey
from ergo.report import workbook
from ergo.service import application


def base_survey(**updates):
    value={
        'survey_type':'REGULAR','survey_date':'2026-10-23','investigator':'조사자',
        'department':'팀','process':'공정','title':'설문 검증','occasional_reason':None,
    }
    value.update(updates)
    return value


class SurveyIntakeTests(unittest.TestCase):
    def test_new_occasional_survey_requires_a_cause_but_legacy_read_remains_possible(self):
        with self.assertRaisesRegex(ValueError,'사유 유형'):
            normalize_survey(base_survey(survey_type='OCCASIONAL'),require_occasional_cause=True)
        legacy=normalize_survey(base_survey(survey_type='OCCASIONAL'))
        self.assertIsNone(legacy['occasional_cause'])

    def test_health_questionnaire_rejects_duplicate_codes_and_invalid_region_values(self):
        first=blank_response(1)
        second=blank_response(2)
        survey=base_survey(symptom_survey={'responses':[first,second]})
        survey['symptom_survey']['responses'][1]['response_code']=first['response_code']
        with self.assertRaisesRegex(ValueError,'중복'):
            normalize_survey(survey)
        survey=base_survey(symptom_survey={'responses':[blank_response(1)]})
        survey['symptom_survey']['responses'][0]['regions']['neck']['severity']='DIAGNOSIS'
        with self.assertRaisesRegex(ValueError,'severity'):
            normalize_survey(survey)

    def test_only_disease_trigger_adds_form_based_sheets(self):
        for cause,expected in [('NEW_TASK_OR_EQUIPMENT',4),('DISEASE_CASE',6)]:
            with self.subTest(cause=cause), tempfile.TemporaryDirectory() as folder:
                survey=normalize_survey(base_survey(survey_type='OCCASIONAL',occasional_cause=cause))
                survey['participation']={'status':'YES','role':'AFFECTED_WORKER','participant_code':'W-1','method':'INTERVIEW','date':'2026-10-23','notes':'작업 방법 의견'}
                survey['workplace_situation']={
                    'equipment_status':'NO','equipment_notes':'','workload_status':'YES','workload_notes':'물량 증가',
                    'speed_status':'NO','speed_notes':'','work_pattern_status':'UNKNOWN','work_pattern_notes':'',
                }
                response=blank_response(1)
                response.update(work_related_symptoms_last_year='YES')
                response['regions']['neck'].update(side='BOTH',duration='WEEK_TO_MONTH',severity='MODERATE',last_week='YES')
                survey['symptom_survey']={'method':'QUESTIONNAIRE','date':'2026-10-23','respondent_count':1,'summary':'익명 설문 1건','responses':[response]}
                survey.update(survey_id=1,metadata_revision=0,review={'reviewed':False})
                destination=str(Path(folder)/'report.xlsx')
                snapshot={'survey':survey,'tasks':[],'analyses':[],'unanalysed_task_ids':[],
                          'include_representative':False,'comparison_specs':[],'comparison_analyses':[],
                          'exported_at':'2026-10-23T00:00:00+00:00'}
                rendered=workbook.render(snapshot,destination)
                self.assertEqual(len(rendered['sheets']),expected)
                book=load_workbook(destination,data_only=False)
                try:
                    self.assertEqual(len(book.sheetnames),expected)
                    if cause=='DISEASE_CASE':
                        self.assertEqual(book.sheetnames[-2:],['별지1 유해요인조사표','별지2 증상조사표'])
                        form=book['별지1 유해요인조사표']
                        form_values=[cell.value for row in form.iter_rows() for cell in row]
                        self.assertIn('W-1',form_values)
                        self.assertIn('작업 방법 의견',form_values)
                        self.assertIn('물량 증가',form_values)
                        self.assertIn('익명 설문 1건',form_values)
                        symptoms=book['별지2 증상조사표']
                        self.assertIn('목 통증정도', [cell.value for cell in symptoms[3]])
                        self.assertEqual(symptoms.cell(4,1).value,'익명-001')
                        self.assertIsNone(symptoms.cell(4,2).value)
                        self.assertIn('BOTH',[cell.value for cell in symptoms[4]])
                        self.assertIn('WEEK_TO_MONTH',[cell.value for cell in symptoms[4]])
                finally:
                    book.close()

    def test_incomplete_survey_context_is_reported_instead_of_silent_completion(self):
        survey=normalize_survey(base_survey())
        snapshot={'survey':survey,'tasks':[],'analyses':[],'unanalysed_task_ids':[],
                  'include_representative':False,'comparison_specs':[],'comparison_analyses':[],
                  'exported_at':'2026-10-23T00:00:00+00:00'}
        result=workbook.overview(snapshot)
        self.assertFalse(result['state']['survey_input_complete'])
        self.assertGreaterEqual(len(result['survey_followups']),6)


if __name__=='__main__':
    unittest.main()
