"""Independent statement coverage must fail when omitted facts evade the old oracle."""
import json
import tempfile
import unittest
from pathlib import Path
from tests.live_statement_ledger import first_checkpoint,ledger,equivalent,verify_first,verify


def fixture(identity='01-lifting'):
    case=dict(id=identity,statement='A deliberately independent statement.',expected={})
    facts=[]
    for item in ledger(case):
        values=item['expected'] if isinstance(item['expected'],list) else [item['expected']]
        for index,value in enumerate(values):facts.append(dict(target=item['target'],condition='condition'+str(index),value=value,
            state='UNKNOWN' if value is None else 'KNOWN',source='USER' if value is None else 'AI'))
    return case,dict(session=dict(facts=facts,messages=[dict(text=case['statement'])],history=[]))


class StatementCoverageOracle(unittest.TestCase):
    def test_recorded_original_bilateral_omission_remains_a_failure(self):
        recorded=json.loads((Path(__file__).parent/'fixtures'/'intake-recorded-bilateral-omission-20261023.json').read_text(encoding='utf-8'))
        defects=first_checkpoint(recorded['case'],recorded['checkpoint'])['defects']
        self.assertEqual([item['target'] for item in defects],['manual.RIGHT.coupling'])
        self.assertEqual(defects[0]['expected'],'GOOD');self.assertEqual(defects[0]['actual'],'MISSING')
        self.assertTrue(any(answer['text']=='UNKNOWN' for answer in defects[0]['proposals']))
        self.assertTrue(any(decision['reason']=='EMPTY_VALUE' for decision in defects[0]['decisions']))

    def test_recorded_explicit_all_conditions_omission_remains_a_failure(self):
        recorded=json.loads((Path(__file__).parent/'fixtures'/'intake-recorded-completeness-omission-20261023.json').read_text(encoding='utf-8'))
        with tempfile.TemporaryDirectory() as folder:
            directory=Path(folder)
            (directory/'case.json').write_text(json.dumps(recorded['case']),encoding='utf-8')
            (directory/'receipt.json').write_text(json.dumps(dict(stages=list(recorded['checkpoints']))),encoding='utf-8')
            for phase,checkpoint in recorded['checkpoints'].items():(directory/(phase+'.json')).write_text(json.dumps(checkpoint),encoding='utf-8')
            defects=verify(directory)['defects']
        self.assertEqual([(defect.get('stage'),defect.get('target'),defect.get('expected')) for defect in defects],
                         [('02-followup-ai','complete.lift','YES')])

    def test_empty_old_expectations_do_not_hide_a_missing_bilateral_fact(self):
        case,state=fixture();self.assertFalse(case['expected'])
        self.assertFalse(first_checkpoint(case,state)['defects'])
        state['session']['facts']=[fact for fact in state['session']['facts'] if fact['target']!='manual.RIGHT.coupling']
        errors=first_checkpoint(case,state)['defects']
        self.assertEqual([error['target'] for error in errors],['manual.RIGHT.coupling'])

    def test_explicit_unknown_needs_a_saved_fact_and_user_ownership(self):
        case,state=fixture('09-unknown-then-correction')
        self.assertFalse(first_checkpoint(case,state)['defects'])
        unknown=next(fact for fact in state['session']['facts'] if fact['target']=='daily_work_min')
        unknown['source']='AI'
        self.assertEqual([error['name'] for error in first_checkpoint(case,state)['defects']],['explicit unknown retains user ownership'])
        state['session']['facts'].remove(unknown)
        self.assertEqual(len(first_checkpoint(case,state)['defects']),2)

    def test_unmentioned_work_types_are_never_filled_with_no(self):
        case,_=fixture('02-duration-and');expected={item['target']:item['expected'] for item in ledger(case)}
        self.assertEqual(expected['work_type.arm_over'],'YES')
        self.assertEqual(expected['work_type.keyboard'],'YES')
        self.assertNotIn('work_type.trunk_neck',expected);self.assertNotIn('other_work',expected)

    def test_source_archive_and_boolean_type_are_not_lossy_comparisons(self):
        case,state=fixture();state['session']['messages'][0]['text']='truncated'
        self.assertTrue(any(error['name']=='complete original statement is archived' for error in first_checkpoint(case,state)['defects']))
        self.assertTrue(equivalent(1,1.0));self.assertFalse(equivalent(1,True));self.assertFalse(equivalent([1],[True]))

    def test_unknown_and_zero_are_distinct(self):
        case,state=fixture('09-unknown-then-correction')
        next(fact for fact in state['session']['facts'] if fact['target']=='daily_work_min')['value']=0
        self.assertTrue(any(error.get('target')=='daily_work_min' for error in first_checkpoint(case,state)['defects']))

    def test_api_success_cannot_hide_a_different_physical_unknown_owner(self):
        case,state=fixture('09-unknown-then-correction')
        state['bundle']=dict(task=dict(task_id=1,capture=dict(slots=[dict(analysis_target=True,observation=dict(single_person='YES',full_frame='YES',normal_work='YES'))])))
        rows=state['session']['facts'];stored={str(index):dict(row) for index,row in enumerate(rows)}
        physical=dict(tables=dict(TASK=[dict(task_id=1,input_json=dict(conditions=dict(intake_session=dict(facts=stored))))]))
        with tempfile.TemporaryDirectory() as folder:
            directory=Path(folder)
            (directory/'01-first-ai.json').write_text(json.dumps(state),encoding='utf-8')
            path=directory/'01-first-ai-db.json';path.write_text(json.dumps(physical),encoding='utf-8')
            self.assertFalse(verify_first(directory,case)['defects'])
            next(row for row in stored.values() if row['target']=='daily_work_min')['source']='AI'
            path.write_text(json.dumps(physical),encoding='utf-8')
            self.assertEqual([error['name'] for error in verify_first(directory,case)['defects']],['declared fact metadata matches physical first-input JSON'])


if __name__=='__main__':unittest.main()
