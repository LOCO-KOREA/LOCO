"""Unpatched MediaPipe Heavy -> actual service/SQLite/restart/analysis/Excel.

The optional legacy database is opened read-only and backed up. Source photos and
all pre-existing analysis/export rows remain byte-identical. No external AI calls.
"""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import sqlite3
import sys
import threading

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from openpyxl import load_workbook
from backend.service.application import create_service
from backend.intake import contract,planner,photo_facts

def write(path,value):path.write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8')
def rows(path,table):
    with sqlite3.connect('file:'+path.as_posix()+'?mode=ro',uri=True) as db:return db.execute('SELECT * FROM '+table).fetchall()
def task_bytes(path):
    with sqlite3.connect('file:'+path.as_posix()+'?mode=ro',uri=True) as db:return db.execute('SELECT input_revision,input_json FROM TASK ORDER BY task_id').fetchall()

def reopen(db,task_id):
    ctx=create_service(str(db));before=task_bytes(db)
    for _ in range(3):state=ctx.dispatch('intake_session',dict(task_id=task_id));assert task_bytes(db)==before,'same-path read changed task bytes/revision'
    return ctx,state

def run(directory,photos,legacy):
    if directory.exists():raise ValueError('Fresh evidence directory required')
    directory.mkdir(parents=True);receipt=dict(scope='actual unpatched MediaPipe Heavy, service/SQLite/restart/Excel; no external AI',checks=[])
    hashes={str(photo):hashlib.sha256(photo.read_bytes()).hexdigest() for photo in photos}
    db=directory/'loco.db';ctx=create_service(str(db))
    settings=ctx.dispatch('get_settings',{});settings.pop('gpt_key_present',None);settings['gpt_enabled']=False;ctx.dispatch('update_settings',dict(settings=settings))
    survey=ctx.dispatch('create_survey',dict(draft=dict(survey_type='REGULAR',survey_date='2026-10-23',title='사진별 관측값 저장 검증')))
    task=ctx.dispatch('create_task',dict(survey_id=survey['survey_id'],draft=dict(task_name='사진별 자세 관측')))
    added=ctx.dispatch('import_photos',dict(task_id=task['task_id'],file_paths=[str(photo) for photo in photos]))['added'];assert len(added)==len(photos)
    views=dict(zip(('LEFT','RIGHT','FRONT'),[photo['photo_id'] for photo in added]))
    state=ctx.dispatch('intake_session',dict(task_id=task['task_id'],views=views))
    state=ctx.dispatch('intake_turn',dict(task_id=task['task_id'],answers=[dict(target='context',value='YES')],plan=False))
    original=copy.deepcopy(state);write(directory/'first-state.json',state)
    canonical={identity:fact for identity,fact in state['task']['conditions'][contract.SESSION_KEY]['facts'].items() if fact['target'].startswith('manual.') and not fact.get('alias_of')}
    observed={fact['photo_id'] for fact in canonical.values()};assert set(views.values())<=observed,(views,observed)
    manual=state['task']['manual'];assert manual,'at least one usable actual photo observation required'
    for row in manual:
        if row['source']!='AUTO_ACCEPTED':continue
        fact=canonical[contract.key('manual.'+row['scope']+'.'+row['field'],photo_facts.condition(row['photo_id']))]
        assert fact['value']==row['value'] and fact['photo_id']==row['photo_id'];assert fact['state']=='KNOWN'
    assessment=planner.assess(state['task'],state['task']['conditions'][contract.SESSION_KEY]['facts'],views)
    handled={identity for identity,fact in canonical.items() if fact['state']=='KNOWN' or fact['state']=='UNKNOWN' and fact['source']=='USER'}
    assert not handled & {candidate['identity'] for candidate in assessment['candidates']}
    ctx,state=reopen(db,task['task_id']);assert state['task']['manual']==manual
    receipt['checks'].append('all actual photo observations retain source photo/body/angles; manual rows match the same photo; same-photo known identities are not asked again; 3 reads and restart preserve exact TASK bytes')
    ctx.dispatch('set_analysis_scope',dict(task_id=task['task_id'],scope=dict(pose=True,tags=False,reba=True,judgment=True)))
    handle=ctx.dispatch('start_analysis',dict(task_id=task['task_id']))
    while True:
        analysis=ctx.dispatch('get_analysis',dict(analysis_id=handle['analysis_id']))
        if analysis['status']!='RUNNING':break
        threading.Event().wait(.02)
    assert analysis['status']=='FINISHED';before_analysis=rows(db,'ANALYSIS')
    workbook=directory/'photos.xlsx';ctx.dispatch('export_excel',dict(survey_id=survey['survey_id'],spec=dict(destination=str(workbook),analysis_ids=[analysis['analysis_id']],include_representative=False,comparisons=[])))
    exported=ctx.store('list_export_logs',survey['survey_id'])[-1]['snapshot'];assert exported['analyses'][0]['snapshot']['manual']==manual
    book=load_workbook(workbook,data_only=False);cells={sheet.title:[dict(cell=cell.coordinate,value=cell.value) for row in sheet for cell in row if cell.value is not None] for sheet in book};book.close();write(directory/'excel-cells.json',cells)
    write(directory/'final-state.json',state);write(directory/'analysis.json',analysis)
    receipt['photos']=dict(views=views,hashes=hashes,engines={view:data.get('engine') for view,data in state['preview']['views'].items()},facts=canonical,manual=manual,workbook=str(workbook),analysis_id=analysis['analysis_id'],excel_manual_rows=[cell for cell in cells['입력한 값'] if isinstance(cell['value'],str) and any(token in cell['value'] for token in ('몸통','위팔','아래팔','무릎','손목','POSE:'))])
    # A direct edit after export cannot change the old immutable analysis/export.
    chosen=next((identity,fact) for identity,fact in canonical.items() if fact['state']=='KNOWN')
    state=ctx.dispatch('intake_turn',dict(task_id=task['task_id'],answers=[dict(target=chosen[1]['target'],condition=chosen[1]['condition'],value=None)],plan=False));assert rows(db,'ANALYSIS')==before_analysis
    assert next(fact for fact in state['facts'] if fact['identity']==chosen[0])['source']=='USER'
    receipt['checks'].append('actual Excel export uses unchanged analysis manual and original per-photo source evidence; later explicit unknown keeps USER ownership and old analysis rows byte-identical')
    if legacy:
        legacy_db=directory/'legacy-copy.db'
        with sqlite3.connect('file:'+legacy.as_posix()+'?mode=ro',uri=True) as source,sqlite3.connect(legacy_db) as target:source.backup(target)
        source_analysis=rows(legacy,'ANALYSIS');source_exports=rows(legacy,'EXPORT_LOG');source_tasks=rows(legacy,'TASK')
        old=create_service(str(legacy_db));old_settings=old.dispatch('get_settings',{});old_settings.pop('gpt_key_present',None);old_settings['gpt_enabled']=False;old.dispatch('update_settings',dict(settings=old_settings))
        task_id=rows(legacy_db,'TASK')[0][0];bundle=old.dispatch('get_task',dict(task_id=task_id));views={slot['label']:slot['photo_id'] for slot in bundle['task']['capture']['slots'] if slot.get('photo_id') is not None}
        legacy_state=old.dispatch('intake_session',dict(task_id=task_id,views=views));old,legacy_state=reopen(legacy_db,task_id)
        assert rows(legacy_db,'ANALYSIS')==source_analysis;assert rows(legacy_db,'EXPORT_LOG')==source_exports
        assert rows(legacy,'ANALYSIS')==source_analysis and rows(legacy,'EXPORT_LOG')==source_exports and rows(legacy,'TASK')==source_tasks
        write(directory/'legacy-state.json',legacy_state);receipt['legacy']=dict(source=str(legacy),copy=str(legacy_db),old_analysis_rows=len(source_analysis),old_export_rows=len(source_exports),source_unchanged=True,old_snapshots_unchanged=True,same_path_restart_stable=True)
        receipt['checks'].append('read-only backup of existing 3-photo data preserves source TASK and every byte of old ANALYSIS/EXPORT_LOG; fresh canonical ownership then 3 reads/restart stable')
    assert hashes=={str(photo):hashlib.sha256(photo.read_bytes()).hexdigest() for photo in photos}
    receipt['checks'].append('all source photo bytes unchanged; no external AI calls')
    write(directory/'receipt.json',receipt);print(json.dumps(dict(checks=receipt['checks'],canonical_facts=len(canonical),manual_rows=len(manual),photo_ids=sorted(observed),workbook=str(workbook)),ensure_ascii=False))

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--directory',type=Path,required=True);parser.add_argument('--photos',type=Path,nargs='+',required=True);parser.add_argument('--legacy',type=Path);args=parser.parse_args()
    run(args.directory.resolve(),[photo.resolve() for photo in args.photos],args.legacy.resolve() if args.legacy else None)
