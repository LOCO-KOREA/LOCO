"""The displayed draft exposes its actual deterministic A/B/C calculation, without changing the score or source."""
import copy
import unittest

from ergo.engine import reba_scoring as reba
from ergo.engine.task_defaults import COMMON, ARM
from ergo.gpt import payload
from ergo.report.plain import _posture
from tests import test_reba_score_continuity as fixtures


def eight_point_snapshot():
    rows=[]
    common=dict(trunk_base=3,neck_base=2)
    left=dict(upper_arm_base=3,lower_arm_base=2,wrist_base=2,coupling='GOOD')
    for scope,fields in (('COMMON',COMMON),('LEFT',ARM),('RIGHT',ARM)):
        for field in fields:
            if field=='static_over_1min':continue
            value=('GOOD' if field=='coupling' else reba.NO_BURDEN[field])
            value=(common if scope=='COMMON' else left if scope=='LEFT' else {}).get(field,value)
            rows.append(dict(scope=scope,field=field,value=value))
    return fixtures.make_snapshot(answers=rows,rows=[],load_state='MEASURED',load_kg=20)


class CurrentComponents(unittest.TestCase):
    def test_unconfirmed_arm_support_can_make_assumed_score_higher_than_completed_score(self):
        common={field:reba.NO_BURDEN[field] for field in COMMON}
        common.update(trunk_base=1,neck_base=1,legs_support='BILATERAL_STABLE',seated='NO',knee_band='OVER_60')
        arm={field:reba.NO_BURDEN[field] for field in ARM if field!='arm_supported_or_gravity_assisted'}
        arm.update(upper_arm_base=2,lower_arm_base=2,wrist_base=1,coupling='GOOD')
        answers=[dict(scope='COMMON',field=field,value=value) for field,value in common.items()]
        for side in ('LEFT','RIGHT'):
            answers.extend(dict(scope=side,field=field,value=value) for field,value in arm.items())
        snapshot=fixtures.make_snapshot(rows=[],answers=answers,load_state='MEASURED',load_kg=5)

        assumed=reba.calculate_reba(snapshot,None)['slots'][0]['score_so_far']
        complete_snapshot=copy.deepcopy(snapshot)
        complete_snapshot['manual'].extend(dict(slot_no=1,photo_id=7,scope=side,field='arm_supported_or_gravity_assisted',
            value='YES',source='INTERVIEW') for side in ('LEFT','RIGHT'))
        complete=reba.calculate_reba(complete_snapshot,None)['slots'][0]

        self.assertEqual(assumed['total'],4)
        self.assertEqual(assumed['assumed'],['left.arm_supported_or_gravity_assisted','right.arm_supported_or_gravity_assisted'])
        self.assertEqual((complete['total'],complete['left']['total'],complete['right']['total']),(3,3,3))
        self.assertIn('높거나 낮을 수',assumed['assumption'])

    def test_exact_table_values_and_load_keep_eight_point_draft_immutable(self):
        snapshot=eight_point_snapshot();before=copy.deepcopy(snapshot)
        result=reba.calculate_reba(snapshot,None);slot=result['slots'][0];draft=slot['score_so_far']
        self.assertEqual((draft['total'],draft['left'],draft['right'],draft['selected_side']),(8,8,6,'LEFT'))
        self.assertEqual(draft['assumed'],['common.static_over_1min'])
        self.assertEqual(draft['components']['left'],dict(trunk=3,neck=2,legs=1,table_a=4,load_score=2,score_a=6,
            upper_arm=3,lower_arm=2,wrist=2,table_b=5,coupling_score=0,score_b=5,table_c=8,activity_score=0,total=8))
        self.assertEqual(draft['components']['right']['table_b'],1)
        self.assertEqual(draft['components']['right']['table_c'],6)
        for side in ('left','right'):
            values=draft['components'][side]
            self.assertEqual(set(values),set(reba.COMPONENT_FIELDS))
            self.assertTrue(all(type(value)is int for value in values.values()))
            self.assertEqual(values['score_a'],values['table_a']+values['load_score'])
            self.assertEqual(values['score_b'],values['table_b']+values['coupling_score'])
            self.assertEqual(values['total'],values['table_c']+values['activity_score'])
            self.assertEqual(values['total'],draft[side])
        self.assertIsNone(slot['total']);self.assertIsNone(result['summary']['full_max'])
        self.assertEqual(snapshot,before,'no-burden filling and component projection must remain private')

    def test_legacy_saved_draft_gets_current_components_without_rewriting_old_draft(self):
        source=fixtures.analysis(eight_point_snapshot())
        source['reba']['slots'][0]['score_so_far'].pop('components')
        source['reba']['summary']['score_so_far'].pop('components')
        before=copy.deepcopy(source)
        projected=reba.project_score_continuity(source)
        current=projected['reba']['summary']['current_score']
        self.assertEqual(current['total'],8)
        self.assertEqual(current['components']['left']['total'],8)
        self.assertEqual(projected['reba']['slots'][0]['current_score']['components'],current['components'])
        self.assertNotIn('components',projected['reba']['slots'][0]['score_so_far'],'the older saved draft is not overwritten')
        current['components']['left']['total']=15
        self.assertEqual(projected['reba']['slots'][0]['current_score']['components']['left']['total'],8,'summary and row must not alias mutable component dictionaries')
        self.assertEqual(source,before)

    def test_current_components_reach_ai_summary_and_excel_when_saved_slot_is_incomplete(self):
        projected=reba.project_score_continuity(fixtures.analysis(eight_point_snapshot()))
        expected=projected['reba']['slots'][0]['current_score']['components']
        numeric=payload.build_numeric_summary(projected)
        photo=numeric['posture_results'][0]
        component_fields=reba.COMPONENT_FIELDS
        for side in ('left','right'):
            self.assertEqual({field:photo[side][field] for field in component_fields},expected[side],
                f'AI receives every exact current score component for {side}, even when the saved slot fields are blank')

        workbook=_posture({'tasks':[dict(name='상자',analysis=projected,source=projected['snapshot'],task={'input_revision':9})]})
        detail=next(table for table in workbook['tables'] if table['heading'].startswith('사진별 REBA 점수'))
        for side in ('left','right'):
            row=next(row for row in detail['rows'] if row[2]==('왼쪽' if side=='left' else '오른쪽'))
            self.assertEqual(row[3:12],[expected[side][field] for field in ('trunk','neck','legs','upper_arm','lower_arm','wrist','load_score','coupling_score','activity_score')],
                f'Excel retains the current measured/calculated components for {side}')
            self.assertEqual(row[12],expected[side]['total'])

    def test_unknown_load_and_grip_keep_their_existing_calculation_and_assumptions(self):
        snapshot=eight_point_snapshot();snapshot['capture']['slots'][0]['observation'].update(load_state='UNKNOWN',measured_load_kg=None)
        for row in snapshot['manual']:
            if row['field']=='coupling':row['value']='POOR'
        before=copy.deepcopy(snapshot)
        projected=reba.project_score_continuity(fixtures.analysis(snapshot))
        current=projected['reba']['summary']['current_score'];left=current['components']['left']
        self.assertEqual(left['load_score'],0)
        self.assertEqual(left['coupling_score'],2,'unknown mass does not erase an actual grip answer')
        self.assertIn('observation.load_state',current['assumed'])
        self.assertEqual(left['total'],current['total']);self.assertEqual(snapshot,before)


if __name__=='__main__':unittest.main()
