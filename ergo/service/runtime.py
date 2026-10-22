"""Per-application storage and worker state. No domain calculations in storage."""
import threading
from ergo.db import storage
from ergo.legacy.v13 import upgrade_task

class Runtime:
    def __init__(self, db_provider):
        self.db_provider=db_provider
        self.db_lock=threading.RLock()
        self.analysis_lock=threading.Lock()
        self.cancels={}
        self.analysis_tokens={}
        self.intake_previews={}

    def analysis_token(self, identity, *, renew=False):
        """Identify one analysis lifetime without adding fields to stored JSON."""
        with self.db_lock:
            self.require('analysis', identity)
            key = (str(self.db_path), identity)
            if renew or key not in self.analysis_tokens:
                self.analysis_tokens[key] = object()
            return self.analysis_tokens[key]

    def analysis_is_current(self, identity, token):
        with self.db_lock:
            return self.analysis_tokens.get((str(self.db_path), identity)) is token

    def require_analysis_token(self, identity, token):
        if not self.analysis_is_current(identity, token):
            raise LookupError('요청한 분석이 삭제되었거나 다른 기록으로 바뀌었습니다.')

    def forget_analysis(self, identity):
        with self.db_lock:
            self.analysis_tokens.pop((str(self.db_path), identity), None)

    @property
    def db_path(self): return self.db_provider()

    def store(self,name,*args,**kwargs):
        with self.db_lock:return getattr(storage,name)(*args,db_path=self.db_path,**kwargs)

    def require(self,name,identity):
        result=self.store('get_'+name,identity)
        if result is None:raise LookupError(f'{name} {identity}를 찾을 수 없습니다')
        return upgrade_task(result) if name=='task' else result
