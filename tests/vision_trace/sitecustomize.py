"""Test-only real SDK observation. Image bytes go unchanged to SDK, never into logs."""
import base64
import hashlib
import json
import os
from pathlib import Path
import threading
from uuid import uuid4

def safe_record(value):
    if isinstance(value,dict):return {key:safe_record(item) for key,item in value.items() if key.lower() not in ('authorization','api_key','headers','extra_headers')}
    if isinstance(value,(list,tuple)):return [safe_record(item) for item in value]
    if isinstance(value,str) and value.startswith('data:image/') and ';base64,' in value:
        prefix,encoded=value.split(';base64,',1)
        raw=base64.b64decode(encoded,validate=True)
        return dict(kind='data_uri',mime=prefix[5:],raw_bytes=len(raw),raw_sha256=hashlib.sha256(raw).hexdigest(),data_uri_characters=len(value),data_uri_sha256=hashlib.sha256(value.encode()).hexdigest())
    return value

if os.environ.get('LOCO_VISION_TRACE'):
    from openai.resources.responses.responses import Responses
    _original=Responses.create
    _lock=threading.Lock()
    def _write(event):
        try:
            with _lock:
                with Path(os.environ['LOCO_VISION_TRACE']).open('a',encoding='utf-8') as handle:handle.write(json.dumps(event,ensure_ascii=False,default=str)+'\n')
        except OSError as error:
            # The evidence run must fail if recording is incomplete, but a test
            # observer must never discard/interrupt an actual late user response.
            import sys
            sys.__stderr__.write('VISION_TRACE_WRITE_ERROR: '+type(error).__name__+'\n')
    def _record(self,*args,**kwargs):
        identity=uuid4().hex
        _write(dict(kind='REQUEST',trace_id=identity,request=safe_record(kwargs)))
        try:
            response=_original(self,*args,**kwargs)
        except Exception as error:
            _write(dict(kind='ERROR',trace_id=identity,error_type=type(error).__name__,status_code=getattr(error,'status_code',None)))
            raise
        _write(dict(kind='RESPONSE',trace_id=identity,response=safe_record(response.model_dump(mode='json'))))
        return response
    Responses.create=_record
