"""Independent immutable-row and exact-workbook audit for a stored-evidence replay."""
import json
import copy
from pathlib import Path
import sqlite3
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from openpyxl import load_workbook
from ergo.intake.contract import public_contract
from tests.live_output_audit import audit_source,audit_preview,json_equal,user_text

def read(path):return json.loads(path.read_text(encoding='utf-8'))
def write(path,value):path.write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8')
def rows(path):
    with sqlite3.connect('file:'+path.as_posix()+'?mode=ro',uri=True) as db:
        db.row_factory=sqlite3.Row
        return {table:[dict(row) for row in db.execute('SELECT * FROM '+table)] for table in ('SURVEY','TASK','PHOTO','ANALYSIS','APP_SETTINGS','EXPORT_LOG')}

def backup(source,directory):
    destination=directory/'loco.db'
    if destination.exists():raise ValueError('Refusing to overwrite an existing replay database')
    with sqlite3.connect('file:'+(source/'loco.db').as_posix()+'?mode=ro',uri=True) as original,sqlite3.connect(destination) as copied:original.backup(copied)
    original=rows(source/'loco.db');copied=rows(destination)
    if original!=copied:raise AssertionError('SQLite backup differs from source rows')
    write(directory/'source-rows.json',original)
    receipt=read(source/'receipt.json')
    result=dict(survey_id=receipt['survey_id'],task_id=receipt['task_id'],analysis_id=receipt['final_analysis_id'],source=str(source),source_baseline=receipt['baseline'])
    print(json.dumps(result));return result

def checkpoint(source,directory):
    write(directory/'same-worktree-rows.json',rows(directory/'loco.db'));print('{}')

def relocation_task_semantics(row):
    result=copy.deepcopy(row);result.pop('updated_at',None);result.pop('input_revision',None)
    value=json.loads(result['input_json']);session=value['conditions']['intake_session']
    session.pop('fingerprint',None);session.pop('projected_revision',None)
    for fact in session['facts'].values():
        if fact['source'] in ('POSE','PHOTO'):fact.pop('updated_at',None)
    for manual in value['manual']:
        if manual['source']=='AUTO_ACCEPTED':manual['evidence'].pop('observed_at',None)
    result['input_json']=value;return result

def verify(source,directory):
    initial=read(directory/'source-rows.json');current=rows(directory/'loco.db');original=rows(source/'loco.db');receipt=read(directory/'replay-receipt.json');checks=[];defects=[];ledger=[]
    def check(name,expected,actual,**context):
        row=dict(name=name,expected=expected,actual=actual,pass_=json_equal(expected,actual),**context);checks.append(row)
        if not row['pass_']:defects.append(row)
    check('source database rows remain unchanged',initial,original)
    for table in initial:
        if table not in ('EXPORT_LOG','TASK'):check('stored rows remain immutable: '+table,initial[table],current[table])
    # Moving the database to another model root intentionally changes its absolute-path
    # fingerprint and refreshes automatic observations once. USER text/values and all
    # other semantics must survive; another open in the same worktree must be exact.
    same_worktree=read(directory/'same-worktree-rows.json')
    check('relocation preserves typed inputs and all user-owned evidence',[relocation_task_semantics(row) for row in initial['TASK']],[relocation_task_semantics(row) for row in current['TASK']])
    check('same-worktree repeated open leaves task revision and every byte stable',same_worktree['TASK'],current['TASK'])
    catalogue={field['target']:field for field in public_contract()['fields']}
    for export in receipt['exports']:
        physical=next(row for row in current['EXPORT_LOG'] if row['export_id']==export['export_id'])
        snap=json.loads(physical['snapshot_json']);analysis=snap['analyses'][0];source_task=analysis['snapshot'];stored=next(row for row in initial['ANALYSIS'] if row['analysis_id']==analysis['analysis_id'])
        check('export uses selected final analysis',receipt['analysis_id'],analysis['analysis_id'],mode=export['mode'])
        check('export snapshot is the unchanged stored input',json.loads(stored['snapshot_json']),source_task,mode=export['mode'])
        book=load_workbook(export['file_path'],data_only=False);cells={sheet.title:[dict(cell=cell.coordinate,value=cell.value,type=cell.data_type) for row in sheet for cell in row if cell.value is not None] for sheet in book}
        write(directory/(export['mode']+'-cells.json'),cells)
        audit_source(directory,export['mode'],source_task,catalogue,cells,checks,defects,ledger)
        audit_preview(export['mode'],read(directory/(export['mode']+'-preview.json'))['sheets'],book,checks,defects)
        for ai in analysis.get('ai',[]):
            if ai.get('is_active'):check('applied explanation reaches exact workbook cell',True,any(cell['value']==user_text(ai['applied_text']) for cell in cells.get('쉬운 설명',[])),mode=export['mode'])
        representative=(analysis.get('reba') or {}).get('summary',{}).get('representative_slot_no')
        check('representative image matches the selected analysis availability',snap.get('include_representative') and representative is not None,any(sheet._images for sheet in book),mode=export['mode'])
        check('cropped photo provenance survives export',json.loads(stored['snapshot_json']).get('photos',[]),source_task.get('photos',[]),mode=export['mode'])
        book.close()
    trace=directory/'openai.jsonl'
    check('no new external SDK request',[],[json.loads(line) for line in trace.read_text(encoding='utf-8').splitlines() if json.loads(line)['kind']=='REQUEST'] if trace.exists() else [])
    result=dict(checks=checks,defects=defects,ledger=ledger);write(directory/'replay-audit.json',result);print(json.dumps(dict(checks=len(checks),defects=len(defects)),ensure_ascii=False));return result

if __name__=='__main__':
    mode,source,directory=sys.argv[1:];globals()[mode](Path(source).resolve(),Path(directory).resolve())
