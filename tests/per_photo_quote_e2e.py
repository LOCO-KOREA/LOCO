"""Real isolated SQLite/analysis/Excel: equal categories must retain different photo quotes.

Pose execution is not patched. Corrections are synthetic direct USER test answers,
not claims that the real pictures measured those angles. No external AI is used.
"""
import argparse
import json
from pathlib import Path
import sqlite3
import sys
import threading
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from openpyxl import load_workbook
from ergo.intake import contract,photo_facts
from ergo.service.application import create_service

def rows(path,table):
    with sqlite3.connect('file:'+path.as_posix()+'?mode=ro',uri=True) as db:return db.execute('SELECT * FROM '+table).fetchall()

def run(source,directory):
    if directory.exists():raise ValueError('Fresh directory required')
    directory.mkdir(parents=True);database=directory/'loco.db'
    originals={table:rows(source,table) for table in ('TASK','ANALYSIS','EXPORT_LOG')}
    with sqlite3.connect('file:'+source.as_posix()+'?mode=ro',uri=True) as a,sqlite3.connect(database) as b:a.backup(b)
    with sqlite3.connect(database) as db:task_id,survey_id=db.execute('SELECT task_id,survey_id FROM TASK ORDER BY task_id LIMIT 1').fetchone()
    ctx=create_service(str(database));settings=ctx.dispatch('get_settings',{});settings.pop('gpt_key_present',None);settings['gpt_enabled']=False;ctx.dispatch('update_settings',dict(settings=settings))
    state=ctx.dispatch('intake_session',dict(task_id=task_id));views=state['task']['conditions'][contract.SESSION_KEY]['views'];left,right=views['LEFT'],views['RIGHT']
    quotes={left:'왼쪽에서 찍은 사진의 몸통은 35도로 직접 확인했어요.',right:'오른쪽에서 찍은 사진의 몸통은 50도로 직접 확인했어요.'}
    answers=[dict(target='manual.COMMON.trunk_base',condition=photo_facts.condition(owner),value=3,quote=quote) for owner,quote in quotes.items()]
    state=ctx.dispatch('intake_turn',dict(task_id=task_id,answers=answers,plan=False));task=state['task']
    selected=[row for row in task['manual'] if row['field']=='trunk_base' and row['photo_id'] in quotes]
    assert len(selected)==2 and all(row['value']==3 for row in selected)
    handle=ctx.dispatch('start_analysis',dict(task_id=task_id))
    while True:
        analysis=ctx.dispatch('get_analysis',dict(analysis_id=handle['analysis_id']))
        if analysis['status']!='RUNNING':break
        threading.Event().wait(.02)
    assert analysis['status']=='FINISHED',analysis
    workbook=directory/'distinct-photo-quotes.xlsx'
    ctx.dispatch('export_excel',dict(survey_id=survey_id,spec=dict(destination=str(workbook),analysis_ids=[analysis['analysis_id']],include_representative=False,comparisons=[])))
    book=load_workbook(workbook,data_only=False);sheet=book['입력한 값'];excel=[]
    for row in sheet:
        values=[cell.value for cell in row]
        for owner,quote in quotes.items():
            if 'USER: '+quote in values:
                assert any(photo_facts.VIEW_LABELS['LEFT' if owner==left else 'RIGHT'] in str(value) for value in values),values
                assert not any(other in str(values) for other in quotes.values() if other!=quote),values
                excel.append(dict(photo_id=owner,quote=quote,cells={cell.coordinate:cell.value for cell in row if cell.value is not None}))
    book.close();assert len(excel)==2,excel
    old=rows(database,'ANALYSIS');ctx=create_service(str(database))
    restored=ctx.dispatch('intake_session',dict(task_id=task_id))
    for owner,quote in quotes.items():
        fact=next(row for row in restored['facts'] if row['identity']=='manual.COMMON.trunk_base@'+photo_facts.condition(owner))
        assert fact['value']==3 and fact['source']=='USER' and fact['quote']==quote
    assert rows(database,'ANALYSIS')==old
    assert all(rows(source,table)==data for table,data in originals.items())
    receipt=dict(scope='unpatched real service/model/SQLite/Excel; two synthetic direct USER correction answers; no external AI',source=str(source),source_unchanged=True,analysis_id=analysis['analysis_id'],workbook=str(workbook),same_category=3,rows=excel,checks=['distinct canonical photo IDs and USER quotes in DB after restart','actual workbook row uses exact corresponding photo label and its quote','same category never copies the first photo quote to the other','source database and immutable analysis rows unchanged'])
    (directory/'receipt.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(receipt,ensure_ascii=False))

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('source',type=Path);parser.add_argument('directory',type=Path);args=parser.parse_args();run(args.source.resolve(),args.directory.resolve())
