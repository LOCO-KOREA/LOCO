"""Audit copied receipts of a finished real campaign without changing its evidence."""
import json
from pathlib import Path
import shutil
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from tests.live_output_audit import read,write,verify

def main(output,campaigns):
    output=Path(output).resolve()
    if output.exists():raise ValueError('Use a new output directory so existing evidence is never overwritten')
    output.mkdir(parents=True);summary=[]
    for campaign in map(lambda path:Path(path).resolve(),campaigns):
        copied=output/campaign.name;copied.mkdir()
        contract=campaign/'baseline-intake-contract.json'
        if contract.exists():shutil.copy2(contract,copied/contract.name)
        for source in sorted(campaign.iterdir()):
            if not (source/'receipt.json').exists():continue
            destination=copied/source.name;destination.mkdir()
            for item in source.iterdir():
                if item.is_file() and item.suffix in ('.json','.jsonl') and item.name!='audit.json' and not item.name.endswith('-cells.json'):shutil.copy2(item,destination/item.name)
            verify(destination);receipt=read(destination/'receipt.json');audit=read(destination/'audit.json')
            initial=[check for check in audit['checks'] if check['name']=='declared input expectation survives this checkpoint' and check.get('stage')=='01-first-ai']
            trace=destination/'openai.jsonl';packets=[json.loads(line) for line in trace.read_text(encoding='utf-8').splitlines()] if trace.exists() else []
            row=dict(id=source.name,baseline=receipt['baseline'],completed=bool(receipt.get('completed')),ui_defects=len(receipt['defects']),ui_errors=len(receipt['errors']),audit_checks=len(audit['checks']),audit_defects=len(audit['defects']),initial_expectations=len(initial),initial_expectations_passed=sum(check['pass_'] for check in initial),external_requests=sum(packet['kind']=='REQUEST' for packet in packets),external_responses=sum(packet['kind']=='RESPONSE' for packet in packets),source=str(source),copied_audit=str(destination/'audit.json'),defects=[dict(name=check['name'],stage=check.get('stage'),target=check.get('target'),expected=check.get('expected'),actual=check.get('actual')) for check in audit['defects']])
            summary.append(row);print(json.dumps({key:value for key,value in row.items() if key not in ('defects','source','copied_audit')},ensure_ascii=False))
    result=dict(cases=summary,total=len(summary),completed=sum(row['completed'] for row in summary),audit_pass=sum(row['audit_defects']==0 for row in summary),audit_checks=sum(row['audit_checks'] for row in summary),initial_expectations=sum(row['initial_expectations'] for row in summary),initial_expectations_passed=sum(row['initial_expectations_passed'] for row in summary),external_requests=sum(row['external_requests'] for row in summary),external_responses=sum(row['external_responses'] for row in summary))
    write(output/'independent-summary.json',result);print(json.dumps({key:value for key,value in result.items() if key!='cases'}))

if __name__=='__main__':main(sys.argv[1],sys.argv[2:])
