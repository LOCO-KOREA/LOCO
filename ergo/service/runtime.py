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

    @property
    def db_path(self): return self.db_provider()

    def store(self,name,*args,**kwargs):
        with self.db_lock:return getattr(storage,name)(*args,db_path=self.db_path,**kwargs)

    def require(self,name,identity):
        result=self.store('get_'+name,identity)
        if result is None:raise LookupError(f'{name} {identity}를 찾을 수 없습니다')
        return upgrade_task(result) if name=='task' else result
