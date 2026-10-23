"""Manually declared semantic expectations, independent of the campaign's numeric oracle.

Only explicit statements or clear unit conversions are listed. 'No additional work'
does not declare every unmentioned burden feature absent (adaptive-intake.md).
"""
import hashlib
import json
from pathlib import Path
import sys

BASE={
 '01-lifting':(480,220),'02-duration-and':(480,218),'03-duration-list':(360,210),'04-duration-annotations':(480,225),
 '05-compound-korean':(90,180),'06-decimal-load':(450,230),'07-two-load-conditions':(480,200),'08-zero-and-absent':(240,180),
 '09-unknown-then-correction':(None,221),'10-pinch-grip-impact':(390,240),'11-preparation-posture':(480,220),'12-cleaning-knees':(480,220)}
EXPLICIT={
 '01-lifting':{'work_type.lift':'YES','card.lift.load_mass_kg':[20],'card.lift.lift_count_day':[30],'load_kg':20,'load_link':'YES','manual.LEFT.coupling':'GOOD','manual.RIGHT.coupling':'GOOD'},
 '02-duration-and':{'work_type.arm_over':'YES','work_type.keyboard':'YES','card.arm_over.C3_UNION':120,'card.keyboard.C1_KEYBOARD_FOCUSED':360},
 '03-duration-list':{'work_type.arm_over':'YES','work_type.keyboard':'YES','card.arm_over.C3_UNION':90,'card.keyboard.C1_KEYBOARD_FOCUSED':270},
 '04-duration-annotations':{'work_type.arm_over':'YES','work_type.keyboard':'YES','card.arm_over.C3_UNION':120,'card.keyboard.C1_KEYBOARD_FOCUSED':360},
 '05-compound-korean':{'work_type.keyboard':'YES','card.keyboard.C1_KEYBOARD_FOCUSED':40},
 '06-decimal-load':{'work_type.lift':'YES','card.lift.load_mass_kg':[12.5],'card.lift.lift_count_day':[40],'load_kg':12.5,'load_link':'YES','manual.LEFT.coupling':'GOOD','manual.RIGHT.coupling':'GOOD'},
 '07-two-load-conditions':{'work_type.lift':'YES','card.lift.load_mass_kg':[5,30],'card.lift.lift_count_day':[99,1],'load_link':None},
 '08-zero-and-absent':{'work_type.keyboard':'NO','work_type.lift':'NO','card.keyboard.C1_KEYBOARD_FOCUSED':0,'load':'UNLOADED'},
 '09-unknown-then-correction':{'work_type.keyboard':'YES','card.keyboard.C1_KEYBOARD_FOCUSED':120},
 '10-pinch-grip-impact':{'work_type.repeat':'YES','work_type.pinch':'YES','work_type.grip':'YES','work_type.impact':'YES','card.pinch.unsupported':['YES'],'card.pinch.pinch_mass_kg':[1.5],'card.pinch.minutes':[75],'card.grip.unsupported':['YES'],'card.grip.single_hand_mass_kg':[5],'card.grip.minutes':[65],'card.impact.impact_verified':['YES'],'card.impact.impact_rate_hour':[12],'card.impact.minutes':[125],'complete.pinch':'YES','complete.grip':'YES','complete.impact':'YES'},
 '11-preparation-posture':{'work_type.repeat':'YES','work_type.trunk_neck':'YES','card.repeat.C2_WRIST':180,'card.repeat.C2_HAND':180,'card.trunk_neck.C4_NECK_FLEX':120,'card.trunk_neck.C4_TRUNK_FLEX':60,'card.trunk_neck.C4_UNION':150,'card.trunk_neck.unsupported':'YES','card.trunk_neck.posture_restricted':'NO'},
 '12-cleaning-knees':{'work_type.knee':'YES','card.knee.C5_SQUAT':60,'card.knee.C5_KNEEL':60,'card.knee.C5_UNION':90}}
FOLLOWUP={
 '01-lifting':{'complete.lift':'YES','card.lift.lift_rate_min':[1],'card.lift.minutes':[30]},
 '06-decimal-load':{'complete.lift':'YES','card.lift.lift_rate_min':[2],'card.lift.minutes':[20]},
 '07-two-load-conditions':{'complete.lift':'YES'},
}

def read(path):return json.loads(path.read_text(encoding='utf-8'))
def equivalent(left,right):
    if type(left) in (int,float) and type(right) in (int,float):return left==right
    if type(left) is not type(right):return False
    if isinstance(left,list):return len(left)==len(right) and all(equivalent(a,b) for a,b in zip(left,right))
    if isinstance(left,dict):return left.keys()==right.keys() and all(equivalent(value,right[key]) for key,value in left.items())
    return left==right

def ledger(case):
    daily,annual=BASE[case['id']]
    expected=dict(daily_work_min=daily,annual_work_days=annual,one_off='NO',context='YES',**EXPLICIT[case['id']])
    return [dict(target=target,expected=value,source_quote=case['statement'].strip(),evidence='explicit statement or exact unit conversion') for target,value in expected.items()]


def first_checkpoint(case,checkpoint):
    """An independently declared first-input oracle; never reuse case.expected."""
    state=checkpoint['session'];rows=state['facts'];declared=ledger(case);checks=[]
    def check(name,expected,actual,**context):checks.append(dict(name=name,expected=expected,actual=actual,pass_=equivalent(expected,actual),**context))
    check('complete original statement is archived',True,any(message['text']==case['statement'].strip() for message in state['messages']))
    for expected in declared:
        target=expected['target'];wanted=expected['expected'];selected=[row for row in rows if row['target']==target]
        actual=sorted([row['value'] for row in selected],key=str) if isinstance(wanted,list) else selected[0]['value'] if selected else 'MISSING'
        check('explicit input is retained',sorted(wanted,key=str) if isinstance(wanted,list) else wanted,actual,target=target)
        if wanted is None:
            check('explicit unknown retains user ownership',dict(state='UNKNOWN',source='USER'),
                  {key:selected[0][key] for key in ('state','source')} if selected else None,target=target)
    if case['id']=='07-two-load-conditions':
        from tests.live_output_relations import lifting_pairs
        check('mass and count retain their condition pairing',[[30,1],[5,99]],lifting_pairs(rows))
    task=(checkpoint.get('bundle') or {}).get('task') or state.get('task')
    if task is not None:
        primary=next((slot for slot in task['capture']['slots'] if slot.get('analysis_target')),None)
        observation=(primary or {}).get('observation') or {}
        check('explicit photo context reaches the typed observation',dict(single_person='YES',full_frame='YES',normal_work='YES'),
              {key:observation.get(key) for key in ('single_person','full_frame','normal_work')})
        if case['id'] in ('01-lifting','06-decimal-load'):
            mass=20 if case['id']=='01-lifting' else 12.5
            check('explicit photo mass reaches the typed observation',dict(load_state='MEASURED',measured_load_kg=mass),
                  {key:observation.get(key) for key in ('load_state','measured_load_kg')})
        elif case['id']=='07-two-load-conditions':
            check('unknown photo relation does not invent a mass',None,observation.get('measured_load_kg'))
        elif case['id']=='08-zero-and-absent':
            check('explicit unloaded observation is retained','UNLOADED',observation.get('load_state'))
    defects=[check for check in checks if not check['pass_']]
    for defect in defects:
        target=defect.get('target')
        if target:
            defect['proposals']=[answer for turn in state.get('history',[]) for request in turn.get('requests',[])
                                 for answer in request.get('answers',[]) if answer.get('target')==target]
            defect['decisions']=[decision for turn in state.get('history',[]) for decision in turn.get('decisions',[]) if decision.get('target')==target]
    return dict(id=case['id'],statement_sha256=hashlib.sha256(case['statement'].strip().encode()).hexdigest(),ledger=declared,checks=checks,defects=defects)


def verify_first(directory,case=None):
    case=case or read(directory/'case.json')
    if not (directory/'01-first-ai.json').is_file():return dict(id=case['id'],pending=True,reason='FIRST_AI_CHECKPOINT_NOT_PRESENT',ledger=ledger(case),checks=[],defects=[])
    checkpoint=read(directory/'01-first-ai.json');result=first_checkpoint(case,checkpoint)
    physical=directory/'01-first-ai-db.json'
    if not physical.is_file():result['physical_checkpoint_pending']=True;return result
    raw=read(physical);identity=(checkpoint.get('bundle') or {}).get('task',checkpoint['session'].get('task',{})).get('task_id')
    task=next((task for task in raw['tables']['TASK'] if task['task_id']==identity),None)
    declared={row['target'] for row in result['ledger']}
    def selected(rows):
        return sorted([{key:row.get(key) for key in ('target','condition','value','state','source')} for row in rows if row['target'] in declared],key=lambda row:(row['target'],row['condition']))
    api=selected(checkpoint['session']['facts'])
    db=selected(task['input_json']['conditions']['intake_session']['facts'].values()) if task else None
    check=dict(name='declared fact metadata matches physical first-input JSON',expected=api,actual=db,pass_=equivalent(api,db))
    result['checks'].append(check)
    if not check['pass_']:result['defects'].append(check)
    return result

def verify(directory):
    case=read(directory/'case.json');receipt=read(directory/'receipt.json');declared=ledger(case);checks=[]
    def check(name,expected,actual,**context):checks.append(dict(name=name,expected=expected,actual=actual,pass_=expected==actual,**context))
    check('first AI checkpoint exists',True,'01-first-ai' in receipt['stages'])
    for stage in receipt['stages']:
        if stage=='00-before-ai':continue
        state=read(directory/(stage+'.json'))['session'];rows=state['facts'];targets={row['target']:row for row in rows}
        check('complete original statement is archived',True,any(message['text']==case['statement'].strip() for message in state['messages']),stage=stage)
        expected={row['target']:row['expected'] for row in declared}
        if stage not in ('01-first-ai',):expected.update(FOLLOWUP.get(case['id'],{}))
        if receipt['stages'].index(stage)>=receipt['stages'].index('04-direct-edits') if '04-direct-edits' in receipt['stages'] else False:expected.update(case['edits'])
        for target,value in expected.items():
            selected=[row for row in rows if row['target']==target]
            actual=sorted([row['value'] for row in selected],key=str) if isinstance(value,list) else selected[0]['value'] if selected else 'MISSING'
            check('explicit input is retained',sorted(value,key=str) if isinstance(value,list) else value,actual,stage=stage,target=target)
            if target=='load_link' and case['id']=='07-two-load-conditions':check('explicit unknown retains user ownership',dict(state='UNKNOWN',source='USER'),{key:selected[0][key] for key in ('state','source')} if selected else None,stage=stage,target=target)
        if stage=='01-first-ai' and case['id']=='09-unknown-then-correction':check('explicit unknown duration retains user ownership',dict(state='UNKNOWN',source='USER'),{key:targets['daily_work_min'][key] for key in ('state','source')},stage=stage)
    return dict(id=case['id'],ledger=declared,checks=checks,defects=[check for check in checks if not check['pass_']])

if __name__=='__main__':
    directory=Path(sys.argv[1]).resolve();result=verify(directory);Path(sys.argv[2]).write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(dict(id=result['id'],declared=len(result['ledger']),checks=len(result['checks']),defects=len(result['defects'])),ensure_ascii=False))
