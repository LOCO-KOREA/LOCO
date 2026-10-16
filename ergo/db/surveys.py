"""Surveys rows in the existing SQLite schema."""
from __future__ import annotations
import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from threading import local
from typing import Any, Callable, Iterator, Mapping
from .connection import open_db
from .storage_common import _transaction, _archive_review, _invalidate_review, _dump, _load, _survey, _delete_task_rows, JsonObject


def create_survey(draft: JsonObject, review: JsonObject, created_at: str, updated_at: str, *, db_path: str | None=None) -> int:
    with _transaction(db_path) as connection:
        cursor = connection.execute('INSERT INTO SURVEY (metadata_revision, metadata_json, review_json, created_at, updated_at) VALUES (0, ?, ?, ?, ?)', (_dump(draft), _dump(review), created_at, updated_at))
        return int(cursor.lastrowid)

def get_survey(survey_id: int, *, db_path: str | None=None) -> dict[str, Any] | None:
    with _transaction(db_path) as connection:
        row = connection.execute('SELECT * FROM SURVEY WHERE survey_id = ?', (survey_id,)).fetchone()
        return _survey(row)

def list_surveys(*, db_path: str | None=None) -> list[dict[str, Any]]:
    with _transaction(db_path) as connection:
        rows = connection.execute('SELECT * FROM SURVEY ORDER BY survey_id').fetchall()
        return [_survey(row) for row in rows]

def update_survey_metadata(survey_id: int, draft: JsonObject, updated_at: str, *, db_path: str | None=None) -> int | None:
    with _transaction(db_path) as connection:
        row = connection.execute('SELECT metadata_revision FROM SURVEY WHERE survey_id = ?', (survey_id,)).fetchone()
        if row is None:
            return None
        revision = (row['metadata_revision'] or 0) + 1
        connection.execute('UPDATE SURVEY SET metadata_json = ?, metadata_revision = ?, updated_at = ? WHERE survey_id = ?', (_dump(draft), revision, updated_at, survey_id))
        _invalidate_review(connection, survey_id, updated_at, 'METADATA_CHANGED')
        return int(revision)

def set_survey_review(survey_id: int, review: JsonObject, updated_at: str, *, db_path: str | None=None) -> None:
    with _transaction(db_path) as connection:
        connection.execute('BEGIN IMMEDIATE')
        row = connection.execute('SELECT review_json FROM SURVEY WHERE survey_id = ?', (survey_id,)).fetchone()
        if row is None:
            return
        review = _archive_review(_load(row['review_json']) or {}, dict(review), updated_at, 'REVIEW_CHANGED')
        connection.execute('UPDATE SURVEY SET review_json = ?, updated_at = ? WHERE survey_id = ?', (_dump(review), updated_at, survey_id))

def delete_survey(survey_id: int, *, db_path: str | None=None) -> None:
    with _transaction(db_path) as connection:
        task_rows = connection.execute('SELECT task_id FROM TASK WHERE survey_id = ?', (survey_id,)).fetchall()
        for row in task_rows:
            _delete_task_rows(connection, row['task_id'])
        connection.execute('DELETE FROM EXPORT_LOG WHERE survey_id = ?', (survey_id,))
        connection.execute('DELETE FROM SURVEY WHERE survey_id = ?', (survey_id,))
