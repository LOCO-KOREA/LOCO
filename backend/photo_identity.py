"""A registration generation independent of SQLite's reusable integer IDs."""
import hashlib
import json
from uuid import uuid4

REGISTRATION_KEY='photo_registration_id'
LEGACY_PREFIX='legacy:'

def registered(metadata):return dict(metadata,**{REGISTRATION_KEY:uuid4().hex})

def identity(photo):
    token=photo.get(REGISTRATION_KEY)
    if isinstance(token,str) and token:return token
    # Old rows remain untouched; path/id are enough for a stable legacy identity.
    value={key:photo.get(key) for key in ('task_id','photo_id','file_path')}
    return LEGACY_PREFIX+hashlib.sha256(json.dumps(value,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
