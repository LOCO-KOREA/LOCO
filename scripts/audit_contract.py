"""Offline audit of the 2.0 document, dispatch and actual renderer call graph."""
import ast
import json
import re
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from backend.contracts import CONTRACT_VERSION, SERVICE_METHODS
from backend.intake.contract import METHODS as INTAKE_METHODS


def audit():
    text=(ROOT/'docs/API_계약서.md').read_text(encoding='utf-8')
    table=text.split('## 7. 서비스 호출',1)[1].split('## 8.',1)[0]
    documented={name.strip() for row in re.findall(r'^\| ([a-z][a-z_ /]+) \|',table,re.M) for name in row.split('/')}
    documented.discard('method')
    tree=ast.parse((ROOT/'backend/service/application.py').read_text(encoding='utf-8'))
    routes=next(n.value for n in tree.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='_HANDLERS' for t in n.targets))
    implemented={key.value for key in routes.keys}
    if documented!=set(SERVICE_METHODS) or implemented!=documented:
        raise AssertionError({'document_only':sorted(documented-implemented),'dispatch_only':sorted(implemented-documented),'registry_diff':sorted(documented^set(SERVICE_METHODS))})
    calls=set()
    for path in (ROOT/'frontend').rglob('*.js'):
        if any(part in ('node_modules','.local') for part in path.parts): continue
        calls.update(re.findall(r"\b(?:api|call)\(['\"]([a-z_]+)['\"]",path.read_text(encoding='utf-8')))
    adaptive=(ROOT/'frontend/intake/client.js').read_text(encoding='utf-8')
    bootstrap=re.search(r"INTAKE_CONTRACT_METHOD\s*=\s*['\"]([a-z_]+)['\"]",adaptive).group(1)
    if bootstrap!=INTAKE_METHODS['contract']: raise AssertionError('Intake bootstrap differs from the service contract')
    calls.add(bootstrap)
    for name in re.findall(r'\bcontract\.methods\.([a-z_]+)',adaptive):
        if name not in INTAKE_METHODS: raise AssertionError('Unknown intake contract method '+name)
        calls.add(INTAKE_METHODS[name])
    if calls-set(SERVICE_METHODS): raise AssertionError('Undocumented renderer calls: '+str(calls-set(SERVICE_METHODS)))
    obsolete=['backend/service/stub.py','backend/report/excel.py','frontend/service/survey_service.py','samples/desktop/backend/server.py','tests/contract_suite.py','frontend/app.js']
    if any((ROOT/p).exists() for p in obsolete): raise AssertionError('Obsolete runtime remains')
    return {'contract_version':CONTRACT_VERSION,'documented_methods':len(documented),'implemented_methods':len(implemented),'renderer_methods':len(calls),'obsolete_entrypoints_removed':True}


if __name__=='__main__': print(json.dumps(audit(),ensure_ascii=False,indent=2))
