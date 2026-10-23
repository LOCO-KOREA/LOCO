"""Test-only transparent SDK recording. No response or application value is changed."""
import os
if os.environ.get('LOCO_LIVE_TRACE'):
    import json
    import threading
    from pathlib import Path
    from uuid import uuid4
    from openai.resources.responses.responses import Responses
    _original=Responses.create
    _lock=threading.Lock()
    def _write(event):
        with _lock:
            with Path(os.environ['LOCO_LIVE_TRACE']).open('a',encoding='utf-8') as handle:
                handle.write(json.dumps(event,ensure_ascii=False,default=str)+'\n')
                handle.flush()
    def _record(self,*args,**kwargs):
        identity=uuid4().hex
        # SDK request options contain model/input/schema, never client credentials/headers.
        _write(dict(kind='REQUEST',trace_id=identity,request=kwargs))
        try:
            response=_original(self,*args,**kwargs)
            _write(dict(kind='RESPONSE',trace_id=identity,response=response.model_dump(mode='json')))
            return response
        except Exception as error:
            _write(dict(kind='ERROR',trace_id=identity,error_type=type(error).__name__))
            raise
    Responses.create=_record
    # Observe the real JSON Lines transport, including rejected turns. Forward bytes unchanged.
    import builtins
    import sys
    _stdin=sys.stdin
    _print=builtins.print
    def _ipc(kind,packet):
        with _lock:
            with Path(os.environ['LOCO_LIVE_TRACE']).with_name('ipc.jsonl').open('a',encoding='utf-8') as handle:
                handle.write(json.dumps(dict(kind=kind,pid=os.getpid(),packet=packet),ensure_ascii=False)+'\n')
    class _Input:
        def __getattr__(self,name):return getattr(_stdin,name)
        def __iter__(self):return self
        def __next__(self):
            line=next(_stdin)
            try:_ipc('REQUEST',json.loads(line))
            except (ValueError,TypeError):pass
            return line
    def _output(*args,**kwargs):
        if kwargs.get('file',sys.stdout) is sys.stdout and len(args)==1 and isinstance(args[0],str):
            try:
                packet=json.loads(args[0])
                if isinstance(packet,dict) and 'request_id' in packet and 'result' in packet:_ipc('RESPONSE',packet)
            except (ValueError,TypeError):pass
        return _print(*args,**kwargs)
    sys.stdin=_Input()
    builtins.print=_output
