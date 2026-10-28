"""Read-only, actual UI E2E DB / accepted facts / snapshot / XLSX comparison."""
import json
from pathlib import Path
import sys
from openpyxl import load_workbook
from live_output_audit import read, write, json_equal, audit_source, audit_preview
from backend.intake.contract import fields

directory = Path(sys.argv[1]).resolve()
receipt = read(directory/'receipt.json')
checks, defects, ledger = [], [], []

def check(name, expected, actual, **context):
    row = dict(name=name, expected=expected, actual=actual, pass_=json_equal(expected, actual), **context)
    checks.append(row)
    if not row['pass_']:
        defects.append(row)

check('journey finished via actual UI', True, receipt.get('completed', False))
stages = []
for stage in receipt['stages']:
    api = read(directory/(stage+'.json'))
    db = read(directory/(stage+'-db.json'))
    stages.append((stage, api, db))
    task = next(t for t in db['tables']['TASK'] if t['task_id'] == receipt['task_id'])
    for key, value in task['input_json'].items():
        check('API equals serialized TaskInput', value, api['bundle']['task'].get(key), stage=stage, path=key)
    check('fact values and provenance serialized exactly', task['input_json']['conditions']['intake_session']['facts'],
          {f['identity']: {k: v for k, v in f.items() if k not in ('identity', 'label', 'unit')} for f in api['session']['facts']}, stage=stage)
if stages:
    db = stages[-1][2]
    catalogue = {f['target']: f for f in fields()}
    for export in db['tables']['EXPORT_LOG']:
        selected = export['snapshot_json']['analyses'][0]
        analysis = next(a for a in db['tables']['ANALYSIS'] if a['analysis_id'] == selected['analysis_id'])
        task = next(t for t in db['tables']['TASK'] if t['task_id'] == receipt['task_id'])
        check('export uses selected immutable snapshot', analysis['snapshot_json'], selected['snapshot'])
        check('same TaskInput schema in DB and output', task['input_json']['schema_version'], selected['snapshot']['schema_version'])
        for key, value in task['input_json'].items():
            check('final DB value equals analysis snapshot', value, analysis['snapshot_json'].get(key), path=key)
        book = load_workbook(export['file_path'], data_only=False)
        cells = {sheet.title: [dict(cell=c.coordinate, value=c.value, type=c.data_type) for row in sheet for c in row if c.value is not None] for sheet in book}
        write(directory/'final-output-cells.json', cells)
        audit_source(directory, 'final-output', selected['snapshot'], catalogue, cells, checks, defects, ledger)
        audit_preview('final-output', read(directory/'final-output-preview.json')['sheets'], book, checks, defects)
        book.close()
trace = [json.loads(line) for line in (directory/'openai.jsonl').read_text(encoding='utf-8').splitlines()] if (directory/'openai.jsonl').exists() else []
requests = [e for e in trace if e['kind'] == 'REQUEST']
responses = [e for e in trace if e['kind'] == 'RESPONSE']
check('real external response exists', True, bool(responses))
vision_format = (stages[-1][1]['session'].get('contract', {}).get('photo_vision', {}).get('response_format_name')) if stages else None
vision_requests = []
for event in requests:
    check('external requested model', 'gpt-6-luna', event['request'].get('model'))
    check('external requested effort', 'xhigh', event['request'].get('reasoning', {}).get('effort'))
    request = event['request']
    name = request.get('text', {}).get('format', {}).get('name')
    if vision_format and name == vision_format:
        vision_requests.append(event)
        images = [item for message in request.get('input', []) if isinstance(message.get('content'), list) for item in message['content'] if item.get('type') == 'input_image']
        check('vision receives one actual image', 1, len(images))
        check('vision actual image bytes exist', True, bool(images and images[0].get('image_url', '').startswith('data:image/')))
    else:
        check('text-only request has no image bytes', False, 'data:image' in json.dumps(request))
if receipt.get('expect_photo_vision'):
    check('public vision request format is configured', True, bool(vision_format))
    case = read(directory/'case.json')
    check('one vision call per registered photo and no calls for reads/direct answer saves', 1 if case.get('photo') else 0, len(vision_requests))
for event in responses:
    check('actual response model', 'gpt-6-luna', event['response'].get('model'))
write(directory/'audit.json', dict(checks=checks, defects=defects, ledger=ledger, counts=dict(checks=len(checks), defects=len(defects), fields=len(ledger)),
      scope='Read-only physical SQLite, real Luna receipts and output workbook; no DB answers injected.'))
