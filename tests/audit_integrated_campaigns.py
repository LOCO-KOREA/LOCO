"""Independent, read-only snapshots of first inputs and completed real campaign cases."""
import argparse
import importlib
import json
from pathlib import Path
import shutil
import sqlite3
import sys

def read(path):return json.loads(path.read_text(encoding='utf-8'))
def write(path,value):path.write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8')
def main(root,output,campaigns):
    if output.exists():raise ValueError('Fresh independent evidence directory required')
    output.mkdir(parents=True);sys.path.insert(0,str(root))
    statement=importlib.import_module('tests.live_statement_ledger');relations=importlib.import_module('tests.live_output_relations');audit=importlib.import_module('tests.live_output_audit');summary=[]
    for campaign in campaigns:
        group=output/campaign.name;group.mkdir();shutil.copy2(campaign/'baseline-intake-contract.json',group/'baseline-intake-contract.json')
        for source in sorted(campaign.iterdir()):
            if not (source/'receipt.json').is_file():continue
            receipt=read(source/'receipt.json');case=read(source/'case.json');destination=group/source.name;destination.mkdir();row=dict(id=case['id'],completed=bool(receipt.get('completed')),stages=receipt.get('stages',[]))
            for name in ('case.json','receipt.json','01-first-ai.json','01-first-ai-db.json'):
                if (source/name).exists():shutil.copy2(source/name,destination/name)
            first=statement.verify_first(destination,case);write(destination/'first-expanded-audit.json',first)
            row.update(first_checks=len(first['checks']),first_declared=len(first['ledger']),first_defects=first['defects'],first_pending=first.get('pending',False))
            if row['completed']:
                for item in source.iterdir():
                    if item.is_file() and item.suffix in ('.json','.jsonl','.xlsx') and item.name!='audit.json':shutil.copy2(item,destination/item.name)
                with sqlite3.connect('file:'+(source/'loco.db').as_posix()+'?mode=ro',uri=True) as a,sqlite3.connect(destination/'readonly-final.db') as b:a.backup(b)
                audit.verify(destination);base=read(destination/'audit.json');expanded=statement.verify(destination);paired=relations.verify_case(destination)
                write(destination/'expanded-ledger-audit.json',expanded);write(destination/'relations-audit.json',paired)
                final=read(destination/(row['stages'][-1]+'-db.json'))
                with sqlite3.connect('file:'+(destination/'readonly-final.db').as_posix()+'?mode=ro',uri=True) as db:
                    physical=db.execute('SELECT input_json,input_revision FROM TASK WHERE task_id=?',(receipt['task_id'],)).fetchone()
                    captured=next(task for task in final['tables']['TASK'] if task['task_id']==receipt['task_id'])
                    physical_same=json.loads(physical[0])==captured['input_json'] and physical[1]==captured['input_revision']
                    immutable={}
                    for table in ('ANALYSIS','EXPORT_LOG'):
                        identity='analysis_id' if table=='ANALYSIS' else 'export_id'
                        actual={row[0]:json.loads(row[1]) for row in db.execute('SELECT '+identity+',snapshot_json FROM '+table)}
                        immutable[table]=actual=={item[identity]:item['snapshot_json'] for item in final['tables'][table]}
                row.update(audit_checks=len(base['checks']),audit_defects=base['defects'],expanded_checks=len(expanded['checks']),expanded_defects=expanded['defects'],relation_checks=len(paired['checks']),relation_defects=paired['defects'],physical_final_task_matches=physical_same,physical_immutable_snapshots_match=immutable)
            summary.append(row)
    result=dict(cases=summary,attempted_seen=len(summary),completed=sum(row['completed'] for row in summary),first_declared=sum(row['first_declared'] for row in summary if not row['first_pending']),first_checks=sum(row['first_checks'] for row in summary),first_defects=sum(len(row['first_defects']) for row in summary),audit_checks=sum(row.get('audit_checks',0) for row in summary),audit_defects=sum(len(row.get('audit_defects',[])) for row in summary),expanded_checks=sum(row.get('expanded_checks',0) for row in summary),expanded_defects=sum(len(row.get('expanded_defects',[])) for row in summary),relation_checks=sum(row.get('relation_checks',0) for row in summary),relation_defects=sum(len(row.get('relation_defects',[])) for row in summary))
    write(output/'independent-summary.json',result);print(json.dumps({key:value for key,value in result.items() if key!='cases'}))
    for row in summary:
        defects=row['first_defects']+row.get('audit_defects',[])+row.get('expanded_defects',[])+row.get('relation_defects',[])
        if defects:print(json.dumps(dict(id=row['id'],defects=defects),ensure_ascii=False))

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('root',type=Path);parser.add_argument('output',type=Path);parser.add_argument('campaigns',type=Path,nargs='+');args=parser.parse_args();main(args.root.resolve(),args.output.resolve(),[path.resolve() for path in args.campaigns])
