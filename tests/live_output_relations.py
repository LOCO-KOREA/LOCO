"""Additional source-grounded oracles for relations that a bag of values cannot prove."""
import json
from pathlib import Path
import re
import sys

from openpyxl import load_workbook

def read(path):return json.loads(path.read_text(encoding='utf-8'))

def lifting_pairs(facts):
    conditions={}
    for fact in facts:
        if fact['target'] in ('card.lift.load_mass_kg','card.lift.lift_count_day'):
            conditions.setdefault(fact['condition'],{})[fact['target']]=fact['value']
    return sorted([[values.get('card.lift.load_mass_kg'),values.get('card.lift.lift_count_day')] for values in conditions.values()],key=lambda pair:str(pair))

def workbook_lifting_pairs(book):
    conditions={}
    for row in book['입력한 값']:
        if len(row)<4:continue
        label=row[2].value;value=row[3].value
        match=re.fullmatch(r'25kg 이상 들기: (물체 중량|하루 들기 횟수) \(조건 (\d+)\)',str(label))
        if match:conditions.setdefault(match[2],{})[match[1]]=float(str(value).split()[0])
    return sorted([[values.get('물체 중량'),values.get('하루 들기 횟수')] for values in conditions.values()],key=lambda pair:str(pair))

def verify_case(directory):
    receipt=read(directory/'receipt.json');checks=[]
    def check(name,expected,actual,**context):checks.append(dict(name=name,expected=expected,actual=actual,pass_=expected==actual,**context))
    for stage in receipt['stages']:
        if stage=='00-before-ai':continue
        state=read(directory/(stage+'.json'));facts=state['session']['facts'];task=state['bundle']['task']
        if receipt['id']=='07-two-load-conditions':
            check('mass and count retain their condition pairing',[[30,1],[5,99]],lifting_pairs(facts),stage=stage)
            fact=next((fact for fact in facts if fact['target']=='load_link'),None)
            check('explicit unknown photo relation is retained as the user answer',dict(state='UNKNOWN',source='USER'),{key:fact[key] for key in ('state','source')} if fact else None,stage=stage)
            slot=next(slot for slot in task['capture']['slots'] if slot['analysis_target'])
            check('ambiguous photo mass is not taken from either unrelated condition',None,slot['observation']['measured_load_kg'],stage=stage)
        if receipt['id'] in ('01-lifting','06-decimal-load'):
            mass=20 if receipt['id']=='01-lifting' else 12.5
            for target,expected in [('load_kg',mass),('load_link','YES')]:
                fact=next((fact for fact in facts if fact['target']==target),None)
                check('explicit photo connection is retained: '+target,expected,fact['value'] if fact else None,stage=stage)
            slot=next(slot for slot in task['capture']['slots'] if slot['analysis_target'])
            check('known photo mass reaches the typed observation',dict(load_state='MEASURED',measured_load_kg=mass),{key:slot['observation'][key] for key in ('load_state','measured_load_kg')},stage=stage)
    if receipt['id']=='07-two-load-conditions' and receipt['stages']:
        raw=read(directory/(receipt['stages'][-1]+'-db.json'))
        for export in raw['tables']['EXPORT_LOG']:
            source=export['snapshot_json']['analyses'][0]['snapshot'];rows=source['legal']['criteria'][7]['rows']
            check('stored export keeps paired lifting rows',[[30,1],[5,99]],sorted([[row['load_mass_kg'],row['lift_count_day']] for row in rows],key=lambda pair:str(pair)),export=export['file_path'])
            book=load_workbook(export['file_path'],data_only=False)
            try:check('workbook conditions keep the actual mass/count pair',[[30,1],[5,99]],workbook_lifting_pairs(book),export=export['file_path'])
            finally:book.close()
    return dict(id=receipt['id'],checks=checks,defects=[check for check in checks if not check['pass_']])

if __name__=='__main__':
    directory=Path(sys.argv[1]).resolve();result=verify_case(directory);destination=Path(sys.argv[2]).resolve();destination.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(dict(id=result['id'],checks=len(result['checks']),defects=len(result['defects'])),ensure_ascii=False))
