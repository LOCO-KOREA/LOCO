"""Work inputs reach AI context as recorded facts without changing REBA semantics."""
import copy
import json
import unittest

from backend.engine.task_defaults import task_input
from backend.gpt import client, payload


def analysis():
    snapshot=task_input({})
    snapshot['conditions'].update(daily_work_min=60,annual_work_days=200,one_off='NO',
        worker_code='private-worker',method_description='private-description')
    snapshot['legal']['criteria'][7]['rows']=[dict(row_id='private-A',label='private label A',
        load_mass_kg=20,lift_count_day=120,evidence=dict(source='INTERVIEW',text='private quote'))]
    snapshot['legal']['criteria'][9]['rows']=[dict(row_id='private-A',label='private label A',
        load_mass_kg=20,lift_rate_min=2,minutes=60,evidence=dict(source='INTERVIEW',text='private quote'))]
    return dict(snapshot=snapshot,judgment=dict(judgments=[]),pose=None,reba=None,tags=[],currentness='CURRENT')


class AiAllInputPropagation(unittest.TestCase):
    def test_actual_worktime_days_counts_and_rates_are_explicit_ai_inputs(self):
        source=analysis();before=copy.deepcopy(source)
        rows=payload.build_numeric_summary(source)['recorded_work_inputs']
        common={row['field']:row for row in rows if row['condition_ref'] is None}
        self.assertEqual(common['daily_work_min']['value'],60)
        self.assertEqual(common['annual_work_days']['value'],200)
        self.assertEqual(common['one_off']['value'],'NO')
        self.assertTrue(any(r['field']=='card.lift.lift_count_day' and r['value']==120 and r['unit']=='회/일' for r in rows))
        self.assertTrue(any(r['field']=='card.lift.lift_rate_min' and r['value']==2 and r['unit']=='회/분' for r in rows))
        self.assertTrue(any(r['field']=='card.lift.minutes' and r['value']==60 and r['unit']=='분/일' for r in rows))
        self.assertEqual(source,before)

    def test_distinct_conditions_and_zero_stay_separate_with_anonymous_references(self):
        source=analysis()
        source['snapshot']['legal']['criteria'][7]['rows'].append(dict(row_id='private-B',label='other private label',
            load_mass_kg=30,lift_count_day=0,evidence=dict(source='DIRECT_OBSERVATION',text='private observation')))
        rows=payload.build_numeric_summary(source)['recorded_work_inputs']
        counts=[row for row in rows if row['field']=='card.lift.lift_count_day']
        self.assertEqual({row['value'] for row in counts},{120,0})
        self.assertEqual(len({row['condition_ref'] for row in counts}),2)
        encoded=json.dumps(rows,ensure_ascii=False)
        for secret in ('private-A','private-B','private label','private quote','private-worker','private-description','private observation'):
            self.assertNotIn(secret,encoded)

    def test_canonical_saved_values_win_over_stale_session_and_invalid_values_are_not_facts(self):
        source=analysis()
        source['snapshot']['conditions']['intake_session']=dict(facts={
            'daily_work_min@default':dict(value=480,state='KNOWN',source='AI',quote='private stale text')})
        source['snapshot']['conditions']['annual_work_days']=True
        source['snapshot']['conditions']['planned_duration_months']=float('nan')
        rows=payload.build_numeric_summary(source)['recorded_work_inputs']
        self.assertEqual(next(row for row in rows if row['field']=='daily_work_min')['value'],60)
        self.assertFalse(any(row['field'] in ('annual_work_days','planned_duration_months') for row in rows))
        self.assertNotIn('private stale text',json.dumps(rows,ensure_ascii=False))

    def test_prompt_distinguishes_work_context_from_reba_activity(self):
        self.assertIn('recorded_work_inputs',client.SYSTEM_PROMPT)
        self.assertIn('전체 작업시간',client.SYSTEM_PROMPT)
        self.assertIn('연간 작업일수',client.SYSTEM_PROMPT)
        self.assertIn('다시 환산하지',client.SYSTEM_PROMPT)

    def test_explicit_unknown_work_and_photo_answers_are_retained_without_zero_or_private_data(self):
        source=analysis();snapshot=source['snapshot'];snapshot['input_revision']=9
        snapshot['conditions']['daily_work_min']=None
        snapshot['capture']['slots']=[dict(slot_no=1,photo_id=7811,analysis_target=True,observation=dict(load_state='MEASURED',measured_load_kg=20))]
        snapshot['analysis_scope'].update(pose=True,reba=True)
        snapshot['conditions']['intake_session']=dict(projected_revision=9,views=dict(LEFT=7811),facts={
            'daily_work_min@default':dict(target='daily_work_min',condition='default',value=None,state='UNKNOWN',source='USER',quote='private answer'),
            'manual.COMMON.seated@photo:7811':dict(target='manual.COMMON.seated',condition='photo:7811',photo_id=7811,value=None,state='UNKNOWN',source='USER',quote='private answer')})
        summary=payload.build_numeric_summary(source)
        self.assertEqual(summary['unknown_work_inputs'][0]['value'],None)
        self.assertEqual(summary['unknown_work_inputs'][0]['state'],'UNKNOWN')
        self.assertEqual(summary['posture_results'][0]['unknown_inputs'],[dict(scope='COMMON',field='seated',value=None,state='UNKNOWN',source='USER')])
        text=client.fallback_text(summary)
        for value in ('200일','120회/일','2회/분','모름으로 응답'):self.assertIn(value,text)
        for private in ('7811','private answer','daily_work_min','manual.COMMON','UNKNOWN'):self.assertNotIn(private,text)
        snapshot['conditions']['intake_session']['projected_revision']=8
        stale=payload.build_numeric_summary(source)
        self.assertEqual(stale['unknown_work_inputs'],[])
        self.assertEqual(stale['posture_results'][0]['unknown_inputs'],[])

    def test_fallback_describes_known_work_values_without_exposing_input_codes(self):
        text=client.fallback_text(payload.build_numeric_summary(analysis()))
        for value in ('입력한 작업 정보','60분','200일','120회/일','2회/분','20kg'):self.assertIn(value,text)
        self.assertNotIn('card.lift.',text)
        self.assertNotIn('daily_work_min',text)
        self.assertNotIn('몇 분인가요',text)
        self.assertNotIn('몇 번쯤',text)
        self.assertIn('하루 총 작업시간: 60분',text)

    def test_every_work_numeric_and_enum_catalogue_destination_has_a_summary_consumer(self):
        from backend.intake.contract import fields,LIFT_FIELDS
        source=analysis();snapshot=source['snapshot'];expected=set()
        for field in fields():
            destination=field['destination'];kind=destination['type']
            if kind not in ('conditions','criterion','work_type','complete'):continue
            expected.add(field['target'])
            value=min(5,field.get('maximum') or 5) if field['kind']=='number' else field['choices'][0]['value']
            if kind=='conditions':snapshot['conditions'][destination['field']]=value
            elif kind in ('work_type','complete'):
                for n in destination['criteria']:snapshot['legal']['criteria'][n-1]['condition_present' if kind=='work_type' else 'rows_complete']=value
            else:
                mapping=destination['mapping']
                if 'exposure' in mapping:
                    next(item for item in snapshot['legal']['exposures'] if item['condition_code']==mapping['exposure'])['minutes']=value
                elif 'criterion' in mapping:
                    for n in destination['criteria']:snapshot['legal']['criteria'][n-1][mapping['criterion']]=value
                else:
                    column=mapping.get('lift') or mapping.get('row')
                    for n in destination['criteria']:
                        if 'lift' in mapping and column not in LIFT_FIELDS[n]:continue
                        rows=snapshot['legal']['criteria'][n-1]['rows']
                        if not rows:rows.append(dict(row_id='private catalogue row'))
                        rows[0][column]=value
        actual={item['field'] for item in payload.build_numeric_summary(source)['recorded_work_inputs']}
        self.assertEqual(actual,expected)


if __name__=='__main__':unittest.main()
