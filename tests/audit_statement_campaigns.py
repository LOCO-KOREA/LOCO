"""Read original first-AI evidence; write the independent coverage audit elsewhere."""
import argparse
import hashlib
import json
from pathlib import Path
from tests.live_statement_ledger import verify_first


def audit(cases,campaigns):
    result={}
    for name,roots in campaigns.items():
        entries=[]
        for case in cases:
            directories=[root/case['id'] for root in roots]
            directory=next((path for path in directories if (path/'01-first-ai.json').is_file()),directories[0])
            entry=verify_first(directory,case)
            if not entry.get('pending'):
                entry['checkpoint']=str(directory/'01-first-ai.json')
                entry['checkpoint_sha256']=hashlib.sha256((directory/'01-first-ai.json').read_bytes()).hexdigest()
            entries.append(entry)
        result[name]=dict(declared_count=sum(len(entry['ledger']) for entry in entries),
            checked_declared_count=sum(len(entry['ledger']) for entry in entries if not entry.get('pending',False)),
            checked_cases=sum(not entry.get('pending',False) for entry in entries),
            pending=[entry['id'] for entry in entries if entry.get('pending')],
            checks=sum(len(entry['checks']) for entry in entries),
            defects=[dict(case=entry['id'],**defect) for entry in entries for defect in entry['defects']],cases=entries)
    return result


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--cases',required=True);parser.add_argument('--campaign',action='append',required=True);parser.add_argument('--output',required=True)
    args=parser.parse_args();cases=json.loads(Path(args.cases).read_text(encoding='utf-8'));campaigns={}
    for declaration in args.campaign:
        name,path=declaration.split('=',1);campaigns.setdefault(name,[]).append(Path(path).resolve())
    result=audit(cases,campaigns);destination=Path(args.output).resolve();destination.parent.mkdir(parents=True,exist_ok=True)
    destination.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({name:{key:value[key] for key in ('declared_count','checked_declared_count','checked_cases','pending','checks')}|dict(defects=len(value['defects'])) for name,value in result.items()},ensure_ascii=False))


if __name__=='__main__':main()
