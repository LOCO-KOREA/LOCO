"""Independently compare persisted SQLite export snapshots with actual XLSX cells."""
import json
import sqlite3
import sys
from pathlib import Path
from openpyxl import load_workbook

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

MARK = {'APPLICABLE': '○', 'NOT_APPLICABLE': 'X', 'NEEDS_INPUT': '입력 필요', 'NEEDS_REVIEW': '검토 필요', 'EXCLUDED': '제외'}


def expected_sheets(snap):
    """The sheet list a snapshot must have produced: the sheets that follow the official forms (the symptom sheet only with responses), the supporting ones, the optional ones."""
    names = ['유해요인조사표', '부담작업 해당 여부', '체크리스트']
    if (snap['survey'].get('symptom_survey') or {}).get('responses'):
        names.append('증상조사표')
    names += ['자세 분석(REBA)', '입력한 값', '확인사항']
    if any(ai.get('is_active') and ai.get('applied_text') for a in snap.get('analyses', []) for ai in a.get('ai') or []):
        names.append('쉬운 설명')
    if snap.get('comparison_specs'):
        names.append('개선 전후 비교')
    return names


def checklist_marks(workbook, task_name):
    """The 11 marks the checklist sheet shows for one task (columns 1 to 11 of its row)."""
    rows = list(workbook['체크리스트'].iter_rows(values_only=True))
    header = next(i for i, row in enumerate(rows) if row[0] == '작업\n(단위작업)')
    matches = [row for row in rows[header + 2:] if row[0] == task_name]
    assert len(matches) == 1, (task_name, len(matches))
    return {number: matches[0][number] for number in range(1, 12)}


def conclusion_row(workbook, task_name, many_tasks, number):
    """The 조사자 결론 row under one rule's block of the 부담작업 해당 여부 sheet (None when the block has none)."""
    from ergo.report.labels import criterion_name
    rows = list(workbook['부담작업 해당 여부'].iter_rows(values_only=True))
    heading = (f'[{task_name}] ' if many_tasks else '') + criterion_name(number) + ' → 최종 판단: '
    start = next(i for i, row in enumerate(rows) if isinstance(row[0], str) and row[0].startswith(heading))
    for row in rows[start + 2:]:
        if all(value in (None, '') for value in row):
            return None
        if row[0] == '조사자 결론':
            return row
    return None


def verify(directory):
    from ergo.report.form import FINAL
    from ergo.report.plain import change_label, change_value
    directory = Path(directory).resolve()
    db = sqlite3.connect('file:' + (directory/'loco.db').as_posix() + '?mode=ro', uri=True)
    db.row_factory = sqlite3.Row
    tables = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")}
    assert tables == {'SURVEY','TASK','PHOTO','ANALYSIS','APP_SETTINGS','EXPORT_LOG'}, tables
    outputs=[]
    for log in db.execute('SELECT * FROM EXPORT_LOG ORDER BY export_id'):
        snap=json.loads(log['snapshot_json']); receipt=json.loads(log['receipt_json'])
        workbook=load_workbook(log['file_path'], data_only=False)
        expected=expected_sheets(snap)
        assert workbook.sheetnames==expected==receipt['sheets'], (workbook.sheetnames, expected, receipt['sheets'])
        comparison_analyses={a['analysis_id']:a for a in snap.get('comparison_analyses',[])}
        for analysis in comparison_analyses.values():
            stored=json.loads(db.execute('SELECT snapshot_json FROM ANALYSIS WHERE analysis_id=?',(analysis['analysis_id'],)).fetchone()[0])
            assert analysis['snapshot']==stored
        comparison_checks=[]
        for spec in snap.get('comparison_specs',[]):
            before=comparison_analyses[spec['before_analysis_id']];after=comparison_analyses[spec['after_analysis_id']]
            bmax=(before.get('reba') or {}).get('summary',{}).get('full_max');amax=(after.get('reba') or {}).get('summary',{}).get('full_max')
            if bmax is not None and amax is not None:
                delta=amax-bmax
                cells={str(cell.value) for row in workbook['개선 전후 비교'].iter_rows() for cell in row if cell.value is not None}
                assert (f'+{delta}' if delta>0 else str(delta)) in cells, 'the score change is missing from the before/after sheet'
                bm={(m['slot_no'],m['scope'],m['field']):m.get('value') for m in before['snapshot']['manual']}
                am={(m['slot_no'],m['scope'],m['field']):m.get('value') for m in after['snapshot']['manual']}
                for key in bm.keys()&am.keys():
                    if bm[key]!=am[key]:
                        path=f'manual.{key[0]}.{key[1]}.{key[2]}.value'
                        assert change_label(path) in cells and change_value(path,bm[key]) in cells and change_value(path,am[key]) in cells, path
                comparison_checks.append(dict(before_analysis_id=before['analysis_id'],after_analysis_id=after['analysis_id'],before_max=bmax,after_max=amax,delta=delta))
        for analysis in snap['analyses']:
            stored=json.loads(db.execute('SELECT snapshot_json FROM ANALYSIS WHERE analysis_id=?',(analysis['analysis_id'],)).fetchone()[0])
            assert analysis['snapshot']==stored
            task_name=analysis['snapshot']['task_name']
            judgments=(analysis.get('judgment') or {}).get('judgments',[])
            marks=checklist_marks(workbook,task_name) if judgments else {}
            for judgment in judgments:
                number=judgment['criterion_no']
                assert marks[number]==MARK[judgment['effective_status']], (task_name, number, marks[number], judgment['effective_status'])
                investigator=judgment['investigator'].get('status')
                found=conclusion_row(workbook,task_name,len(snap['tasks'])>1,number)
                if investigator:
                    assert found is not None, (task_name, number, 'the investigator conclusion is missing from the sheet')
                    assert found[1].startswith(FINAL[investigator]) and f"계산 초안은 {FINAL[judgment['computed_status']]}" in found[1], (task_name, number, found[1])
                else:
                    assert found is None, (task_name, number, 'a conclusion appears that was never saved')
        for sheet in workbook:
            assert all(cell.data_type!='f' for row in sheet for cell in row), 'Unexpected Excel formula'
        outputs.append(dict(export_id=log['export_id'],file=log['file_path'],sheets=expected,
                            analysis_count=len(snap['analyses']),metadata_revision=snap['survey']['metadata_revision'],comparisons=comparison_checks))
        workbook.close()
    assert len(outputs)>=5, 'The UI run did not produce every survey-type workbook'
    models=[]
    for row in db.execute('SELECT analysis_id,result_json FROM ANALYSIS'):
        result=json.loads(row['result_json'])
        for pose in (result.get('pose') or {}).get('slots',[]):
            if pose['status']!='ERROR':
                assert len(pose['points'])==17
                models.append(dict(analysis_id=row['analysis_id'],slot=pose['slot_no'],status=pose['status']))
    assert models
    records={table:db.execute('SELECT COUNT(*) FROM '+table).fetchone()[0] for table in sorted(tables)}
    db.close()
    result=dict(kind='read-only independent SQLite/XLSX comparison',records=records,exports=outputs,model_results=models)
    (directory/'artifact-receipt.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(dict(directory=str(directory),records=records,workbooks=len(outputs),model_results=len(models),verdict='PASS'),ensure_ascii=False))


if __name__=='__main__':
    verify(sys.argv[1])
