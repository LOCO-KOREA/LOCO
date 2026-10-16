"""Shared SQLite transactions and JSON row codecs; no rule calculations."""
from __future__ import annotations
import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from threading import local
from typing import Any, Callable, Iterator, Mapping
from .connection import open_db
JsonObject = Mapping[str, Any]
_read_context = local()

@contextmanager
def _transaction(db_path: str | None=None) -> Iterator[sqlite3.Connection]:
    active = getattr(_read_context, 'active', None)
    if active is not None and active[0] == db_path:
        yield active[1]
        return
    connection = open_db(db_path)
    try:
        with connection:
            yield connection
    finally:
        connection.close()

def _archive_review(previous, updated, at, reason):
    old = {key: value for key, value in previous.items() if key != 'history'}
    new = {key: value for key, value in updated.items() if key != 'history'}
    history = list(previous.get('history') or [])
    if old != new and (old.get('reviewed_at') or old.get('reviewed') or old.get('reviewed_analysis_ids')):
        history.append(dict(old, archived_at=at, reason=reason))
    return dict(new, history=history)

def _invalidate_review(connection, survey_id, at, reason):
    row = connection.execute('SELECT review_json FROM SURVEY WHERE survey_id = ?', (survey_id,)).fetchone()
    if row is None:
        return
    previous = _load(row['review_json']) or {}
    if previous.get('reviewed'):
        review = _archive_review(previous, dict(previous, reviewed=False), at, reason)
        connection.execute('UPDATE SURVEY SET review_json = ?, updated_at = ? WHERE survey_id = ?', (_dump(review), at, survey_id))

def _dump(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(',', ':'))

def _load(value: str | None) -> Any:
    return json.loads(value) if value is not None else None

def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec='seconds').replace('+00:00', 'Z')

def _survey(row: sqlite3.Row | None) -> dict[str, Any] | None:
    if row is None:
        return None
    return {**_load(row['metadata_json']), 'survey_id': row['survey_id'], 'metadata_revision': row['metadata_revision'], 'review': _load(row['review_json']), 'created_at': row['created_at'], 'updated_at': row['updated_at']}

def _task(row: sqlite3.Row | None) -> dict[str, Any] | None:
    if row is None:
        return None
    return {**_load(row['input_json']), 'task_id': row['task_id'], 'survey_id': row['survey_id'], 'input_revision': row['input_revision'], 'latest_analysis_id': row['latest_analysis_id'], 'created_at': row['created_at'], 'updated_at': row['updated_at']}

def _photo(row: sqlite3.Row | None) -> dict[str, Any] | None:
    if row is None:
        return None
    return {'photo_id': row['photo_id'], 'task_id': row['task_id'], **_load(row['metadata_json'])}

def _analysis(row: sqlite3.Row | None) -> dict[str, Any] | None:
    if row is None:
        return None
    result = _load(row['result_json']) or {}
    return {'analysis_id': row['analysis_id'], 'task_id': row['task_id'], 'input_revision': row['input_revision'], 'snapshot': _load(row['snapshot_json']), **result, 'status': row['status'], 'created_at': row['created_at'], 'finished_at': row['finished_at']}

def _delete_task_rows(connection: sqlite3.Connection, task_id: int) -> None:
    connection.execute('DELETE FROM PHOTO WHERE task_id = ?', (task_id,))
    connection.execute('DELETE FROM ANALYSIS WHERE task_id = ?', (task_id,))
    connection.execute('DELETE FROM TASK WHERE task_id = ?', (task_id,))

@contextmanager
def read_snapshot(db_path: str | None=None):
    """Reuse one SQLite read transaction for a multi-query export snapshot."""
    if getattr(_read_context, 'active', None) is not None:
        raise RuntimeError('A read snapshot is already active')
    connection = open_db(db_path)
    connection.execute('PRAGMA query_only = ON')
    connection.execute('BEGIN')
    _read_context.active = (db_path, connection)
    try:
        yield
    finally:
        _read_context.active = None
        connection.rollback()
        connection.close()
