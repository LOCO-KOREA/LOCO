"""Completed calculator scopes must not generate new work-feature interviews."""
import copy
import unittest
from ergo.engine.task_defaults import task_input
from ergo.intake import contract, facts, planner


class QuestionMinimization(unittest.TestCase):
    def test_completed_global_scope_needs_zero_work_questions_even_with_optional_photos(self):
        for conditions in [dict(annual_work_days=30,one_off='NO'),dict(one_off='YES',planned_duration_months=1)]:
            for views in [{},dict(LEFT=101)]:
                with self.subTest(conditions=conditions,views=views):
                    saved=facts.apply_answers({},[dict(target=target,value=value) for target,value in conditions.items()])
                    before=copy.deepcopy(saved)
                    task=facts.project(task_input({}),saved,views,dict(views={}))
                    assessment=planner.assess(task,saved,views)
                    form=planner.form_fields(task,saved,views,assessment['candidates'])
                    self.assertFalse(any(f['destination']['type'] in ('work_type','other_work') for f in assessment['candidates']))
                    self.assertFalse(any(f['destination']['type']=='work_type' for f in form))
                    self.assertTrue(all(row['computed_status']=='NOT_APPLICABLE' for row in assessment['judgments']))
                    self.assertEqual(saved,before,'skipping questions must not fabricate NO facts')

    def test_unknown_duration_does_not_skip_work_feature_questions(self):
        saved=facts.apply_answers({},[dict(target='annual_work_days',value=None),dict(target='one_off',value='NO')])
        task=facts.project(task_input({}),saved,{},dict(views={}))
        assessment=planner.assess(task,saved,{})
        self.assertTrue(any(f['destination']['type']=='work_type' for f in assessment['candidates']))
        self.assertTrue(any(f['destination']['type']=='work_type' for f in planner.form_fields(task,saved,{},assessment['candidates'])))


if __name__=='__main__':unittest.main()
