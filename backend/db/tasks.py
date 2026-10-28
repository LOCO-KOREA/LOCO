"""Tasks rows in the existing SQLite schema."""
from __future__ import annotations
import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from threading import local
from typing import Any, Callable, Iterator, Mapping
from .connection import open_db
from .storage_common import _transaction, _invalidate_review, _dump, _task, _delete_task_rows, JsonObject


def create_task(survey_id: int, input_data: JsonObject, created_at: str, updated_at: str, *, db_path: str | None=None) -> int:
    with _transaction(db_path) as connection:
        cursor = connection.execute('INSERT INTO TASK (survey_id, input_revision, latest_analysis_id, input_json, created_at, updated_at) VALUES (?, 0, NULL, ?, ?, ?)', (survey_id, _dump(input_data), created_at, updated_at))
        return int(cursor.lastrowid)

def get_task(task_id: int, *, db_path: str | None=None) -> dict[str, Any] | None:
    with _transaction(db_path) as connection:
        row = connection.execute('SELECT * FROM TASK WHERE task_id = ?', (task_id,)).fetchone()
        return _task(row)

def list_tasks(survey_id: int, *, db_path: str | None=None) -> list[dict[str, Any]]:
    with _transaction(db_path) as connection:
        rows = connection.execute('SELECT * FROM TASK WHERE survey_id = ? ORDER BY task_id', (survey_id,)).fetchall()
        return [_task(row) for row in rows]

def update_task_input(task_id: int, input_data: JsonObject, updated_at: str, *, db_path: str | None=None) -> int | None:
    with _transaction(db_path) as connection:
        row = connection.execute('SELECT input_revision FROM TASK WHERE task_id = ?', (task_id,)).fetchone()
        if row is None:
            return None
        revision = (row['input_revision'] or 0) + 1
        connection.execute('UPDATE TASK SET input_json = ?, input_revision = ?, updated_at = ? WHERE task_id = ?', (_dump(input_data), revision, updated_at, task_id))
        owner = connection.execute('SELECT survey_id FROM TASK WHERE task_id = ?', (task_id,)).fetchone()
        _invalidate_review(connection, owner['survey_id'], updated_at, 'TASK_INPUT_CHANGED')
        return int(revision)


def delete_task(task_id: int, *, db_path: str | None=None) -> None:
    with _transaction(db_path) as connection:
        _delete_task_rows(connection, task_id)
