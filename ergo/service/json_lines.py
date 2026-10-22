"""Single UTF-8 JSON Lines entrypoint for the LOCO 2.0 Electron application."""
import json
import os
import sqlite3
import sys
import threading
import traceback
from pathlib import Path

sys.dont_write_bytecode = True
if __package__ in (None, ''):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from ergo.gpt import client as gpt_client
from ergo.service.application import dispatch, prepare_dispatch, RECALCULATION_METHODS

_write_lock = threading.Lock()

def respond(request, operation=None, preparation_error=None):
    try:
        if preparation_error is not None:
            raise preparation_error
        value = operation() if operation is not None else dispatch(request['method'], request.get('params', {}))
        result = dict(ok=True, value=value)
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
    """Capture background request targets in IPC order before running workers."""
    method = request.get('method')
    if isinstance(method, str) and (method in RECALCULATION_METHODS or method in ('generate_ai_text', 'quick_interpret', 'intake_turn')):
        try:
            operation = prepare_dispatch(method, request.get('params', {}))
        except Exception as error:
            respond(request, preparation_error=error)
            return
        try:
            threading.Thread(target=respond, args=(request, operation), daemon=True).start()
        except Exception as error:
            try:
                operation.start_failed(error)
            except Exception as save_error:
                respond(request, preparation_error=save_error)
                return
            respond(request, preparation_error=error)
    else:
        respond(request)


def main():
    if os.environ.get('OPENAI_API_KEY'): gpt_client.warm_up()
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
