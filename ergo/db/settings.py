"""Settings rows in the existing SQLite schema."""
from __future__ import annotations
import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from threading import local
from typing import Any, Callable, Iterator, Mapping
from .connection import open_db
from .storage_common import _transaction, _invalidate_review, _dump, _load, _utc_now, JsonObject


def get_settings(*, db_path: str | None=None) -> dict[str, Any] | None:
    with _transaction(db_path) as connection:
        row = connection.execute('SELECT settings_json FROM APP_SETTINGS WHERE settings_id = 1').fetchone()
        return _load(row['settings_json']) if row is not None else None

def update_settings(settings: JsonObject, *, task_inputs: Mapping[int, JsonObject] | None=None, db_path: str | None=None) -> None:
    persisted = {'analysis': settings['analysis'], 'gpt_enabled': settings['gpt_enabled'], 'gpt_model': settings['gpt_model'], 'ui': settings['ui']}
    with _transaction(db_path) as connection:
        connection.execute('BEGIN IMMEDIATE')
        connection.execute('INSERT INTO APP_SETTINGS (settings_id, settings_json) VALUES (1, ?) ON CONFLICT(settings_id) DO UPDATE SET settings_json = excluded.settings_json', (_dump(persisted),))
        for task_id, value in (task_inputs or {}).items():
            connection.execute('UPDATE TASK SET input_json = ?, input_revision = input_revision + 1, updated_at = ? WHERE task_id = ?', (_dump(value), _utc_now(), task_id))
            owner = connection.execute('SELECT survey_id FROM TASK WHERE task_id = ?', (task_id,)).fetchone()
            if owner is not None:
                _invalidate_review(connection, owner['survey_id'], _utc_now(), 'ANALYSIS_SETTINGS_CHANGED')
