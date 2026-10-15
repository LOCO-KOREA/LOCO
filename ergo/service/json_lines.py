"""UTF-8 JSON Lines entrypoint for Electron's LOCO_SERVICE_ENTRY.

Run from the repository root: python -m ergo.service.json_lines
Or pass this file's absolute path to frontend/start.ps1 -ServiceEntry.
"""
import json
import sqlite3
import sys
import threading
import traceback
from pathlib import Path

sys.dont_write_bytecode = True
if __package__ in (None, ''):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from ergo.service.application import dispatch

_write_lock = threading.Lock()

def respond(request):
    try:
        result = dict(ok=True, value=dispatch(request['method'], request.get('params', {})))
    except Exception as error:
        traceback.print_exc(file=sys.stderr)
        code = ('DB_ERROR' if isinstance(error, sqlite3.Error) else
                'NOT_FOUND' if isinstance(error, LookupError) else
                'EXPORT_ERROR' if request.get('method') == 'export_excel' else
                'MODEL_ERROR' if request.get('method') == 'start_analysis' else 'FILE_ERROR')
        result = dict(ok=False, error=dict(code=code, message=str(error)))
    with _write_lock:
        print(json.dumps(dict(request_id=request.get('request_id'), result=result),
                         ensure_ascii=False, allow_nan=False), flush=True)


def handle(request):
    """Keep network-backed explanations from blocking subsequent IPC requests."""
    if request.get('method') == 'generate_ai_text':
        threading.Thread(target=respond, args=(request,), daemon=True).start()
    else:
        respond(request)


def main():
    sys.stdin.reconfigure(encoding='utf-8')
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')
    for line in sys.stdin:
        try:
            request = json.loads(line)
        except json.JSONDecodeError:
            traceback.print_exc(file=sys.stderr)
            continue
        handle(request)

if __name__ == '__main__':
    main()
