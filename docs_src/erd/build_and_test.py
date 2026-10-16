"""Validate the unchanged six-table physical schema in memory."""
import sqlite3
from pathlib import Path
root=Path(__file__).resolve().parents[2]
db=sqlite3.connect(':memory:')
try:
    db.executescript((root/'ergo/db/schema_v1.sql').read_text(encoding='utf-8'))
    tables={r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")}
    assert tables=={'SURVEY','TASK','PHOTO','ANALYSIS','APP_SETTINGS','EXPORT_LOG'},tables
    assert db.execute("SELECT count(*) FROM sqlite_master WHERE type IN ('view','trigger')").fetchone()[0]==0
    print('PASS six JSON tables; no calculation views, triggers or migration')
finally: db.close()
