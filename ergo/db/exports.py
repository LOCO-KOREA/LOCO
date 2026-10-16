"""Exports rows in the existing SQLite schema."""
from __future__ import annotations
import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from threading import local
from typing import Any, Callable, Iterator, Mapping
from .connection import open_db
from .storage_common import _transaction, _dump, _load, JsonObject


def create_export_log(survey_id: int, file_path: str, snapshot: JsonObject, receipt: JsonObject, created_at: str, *, db_path: str | None=None) -> int:
    with _transaction(db_path) as connection:
        cursor = connection.execute('INSERT INTO EXPORT_LOG (survey_id, file_path, snapshot_json, receipt_json, created_at) VALUES (?, ?, ?, ?, ?)', (survey_id, file_path, _dump(snapshot), _dump(receipt), created_at))
        return int(cursor.lastrowid)

def list_export_logs(survey_id: int, *, db_path: str | None=None) -> list[dict[str, Any]]:
    with _transaction(db_path) as connection:
        rows = connection.execute('SELECT * FROM EXPORT_LOG WHERE survey_id = ? ORDER BY export_id', (survey_id,)).fetchall()
        return [{'export_id': row['export_id'], 'survey_id': row['survey_id'], 'file_path': row['file_path'], 'snapshot': _load(row['snapshot_json']), 'receipt': _load(row['receipt_json']), 'created_at': row['created_at']} for row in rows]
