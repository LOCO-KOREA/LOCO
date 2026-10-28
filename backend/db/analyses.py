"""Analyses rows in the existing SQLite schema."""
from __future__ import annotations
import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from threading import local
from typing import Any, Callable, Iterator, Mapping
from .connection import open_db
from .storage_common import _transaction, _invalidate_review, _dump, _load, _utc_now, _analysis, JsonObject


def create_analysis(task_id: int, input_revision: int, status: str, snapshot: JsonObject, created_at: str, *, result: JsonObject | None=None, db_path: str | None=None) -> int:
    initial_result = result if result is not None else {'pose': None, 'slot_tags': [], 'tags': [], 'reba': None, 'judgment': None, 'ai': [], 'notes': []}
    with _transaction(db_path) as connection:
        cursor = connection.execute('INSERT INTO ANALYSIS (task_id, input_revision, status, snapshot_json, result_json, created_at, finished_at) VALUES (?, ?, ?, ?, ?, ?, NULL)', (task_id, input_revision, status, _dump(snapshot), _dump(initial_result), created_at))
        analysis_id = int(cursor.lastrowid)
        connection.execute('UPDATE TASK SET latest_analysis_id = ? WHERE task_id = ?', (analysis_id, task_id))
        return analysis_id

def get_analysis(analysis_id: int, *, db_path: str | None=None) -> dict[str, Any] | None:
    with _transaction(db_path) as connection:
        row = connection.execute('SELECT * FROM ANALYSIS WHERE analysis_id = ?', (analysis_id,)).fetchone()
        return _analysis(row)

def list_analyses(task_id: int, *, db_path: str | None=None) -> list[dict[str, Any]]:
    with _transaction(db_path) as connection:
        rows = connection.execute('SELECT * FROM ANALYSIS WHERE task_id = ? ORDER BY analysis_id', (task_id,)).fetchall()
        return [_analysis(row) for row in rows]


def update_analysis_result(analysis_id: int, update: Callable[[dict[str, Any]], None], *, job: tuple[str, str | None] | None=None, invalidate_review: bool=False, db_path: str | None=None) -> bool:
    """Apply application-owned edits to the latest JSON in one write transaction.

    The callback owns field selection; storage does not calculate domain values.
    A deleted analysis is never inserted again by a delayed completion.
    """
    with _transaction(db_path) as connection:
        connection.execute('BEGIN IMMEDIATE')
        row = connection.execute('SELECT * FROM ANALYSIS WHERE analysis_id = ?', (analysis_id,)).fetchone()
        if row is None:
            return False
        if job is not None and (row['status'] in ('FAILED', 'CANCELED') and job[0] != row['status'] or (row['status'] == 'FINISHED' and job[0] != 'FINISHED')):
            return False
        result = _load(row['result_json']) or {}
        update(result)
        status, finished = job if job is not None else (row['status'], row['finished_at'])
        connection.execute('UPDATE ANALYSIS SET result_json = ?, status = ?, finished_at = ? WHERE analysis_id = ?', (_dump(result), status, finished, analysis_id))
        if invalidate_review:
            owner = connection.execute('SELECT survey_id FROM TASK WHERE task_id = ?', (row['task_id'],)).fetchone()
            if owner is not None:
                _invalidate_review(connection, owner['survey_id'], _utc_now(), 'CONCLUSION_CHANGED')
        return True
