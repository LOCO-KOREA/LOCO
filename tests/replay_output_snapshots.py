"""Render original live export snapshots to new files; never rewrite their DB or snapshots."""
import copy
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from openpyxl import load_workbook
from backend.report.workbook import render
from tests.live_output_audit import audit_source

def main(campaign,destination):
    destination.mkdir(parents=True,exist_ok=True);results=[]
    for folder in sorted(p for p in campaign.iterdir() if p.is_dir()):
        stage=folder/'11-final-restart-db.json'
        if not stage.exists():continue
        db=json.loads(stage.read_text(encoding='utf-8'));session=json.loads((folder/'11-final-restart.json').read_text(encoding='utf-8'))['session'];catalogue={f['target']:f for f in session['contract']['fields']}
        out=destination/folder.name;out.mkdir(exist_ok=True)
        for item in db['tables']['EXPORT_LOG']:
            snapshot=item['snapshot_json'];before=copy.deepcopy(snapshot);label=Path(item['file_path']).stem
            path=out/(label+'.xlsx');render(snapshot,path);assert snapshot==before,'renderer mutated a frozen snapshot'
            workbook=load_workbook(path);cells={s.title:[dict(cell=c.coordinate,value=c.value,type=c.data_type) for row in s for c in row if c.value is not None] for s in workbook};workbook.close()
            checks=[];defects=[];ledger=[];audit_source(out,label,snapshot['analyses'][0]['snapshot'],catalogue,cells,checks,defects,ledger)
            record=dict(case=folder.name,export=label,source_export_id=item['export_id'],source_snapshot_unchanged=True,checks=checks,defects=defects,ledger=ledger)
            (out/(label+'-audit.json')).write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding='utf-8');results.append(record)
    summary=dict(kind='original captured live snapshots rendered again; no new AI, UI or DB writes',workbooks=len(results),defects=sum(len(r['defects']) for r in results),results=[{k:v for k,v in r.items() if k not in ('checks','ledger')} for r in results])
    (destination/'receipt.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(dict(workbooks=len(results),defects=summary['defects'])))
if __name__=='__main__':main(Path(sys.argv[1]).resolve(),Path(sys.argv[2]).resolve())
