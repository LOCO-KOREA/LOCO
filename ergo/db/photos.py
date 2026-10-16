"""Photos rows in the existing SQLite schema."""
from __future__ import annotations
import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from threading import local
from typing import Any, Callable, Iterator, Mapping
from .connection import open_db
from .storage_common import _transaction, _dump, _load, _utc_now, _photo, JsonObject


def create_photo(task_id: int, metadata: JsonObject, *, db_path: str | None=None) -> int:
    with _transaction(db_path) as connection:
        cursor = connection.execute('INSERT INTO PHOTO (task_id, metadata_json) VALUES (?, ?)', (task_id, _dump(metadata)))
        return int(cursor.lastrowid)

def get_photo(photo_id: int, *, db_path: str | None=None) -> dict[str, Any] | None:
    with _transaction(db_path) as connection:
        row = connection.execute('SELECT * FROM PHOTO WHERE photo_id = ?', (photo_id,)).fetchone()
        return _photo(row)

def list_photos(task_id: int, *, db_path: str | None=None) -> list[dict[str, Any]]:
    with _transaction(db_path) as connection:
        rows = connection.execute('SELECT * FROM PHOTO WHERE task_id = ? ORDER BY photo_id', (task_id,)).fetchall()
        return [_photo(row) for row in rows]

def update_photo(photo_id: int, metadata: JsonObject, *, db_path: str | None=None) -> None:
    with _transaction(db_path) as connection:
        connection.execute('UPDATE PHOTO SET metadata_json = ? WHERE photo_id = ?', (_dump(metadata), photo_id))

def delete_photo(photo_id: int, *, db_path: str | None=None) -> None:
    with _transaction(db_path) as connection:
        photo = connection.execute('SELECT task_id FROM PHOTO WHERE photo_id = ?', (photo_id,)).fetchone()
        if photo is None:
            return
        task = connection.execute('SELECT input_revision, input_json FROM TASK WHERE task_id = ?', (photo['task_id'],)).fetchone()
        if task is not None:
            input_data = _load(task['input_json'])
            changed = False
            for slot in input_data['capture']['slots']:
                if slot['photo_id'] == photo_id:
                    slot['photo_id'] = None
                    if input_data.get('schema_version') == '2.0':
                        slot['analysis_target'] = False
                        slot['observation'] = {'load_state': 'UNKNOWN', 'measured_load_kg': None, 'single_person': 'UNKNOWN', 'full_frame': 'UNKNOWN', 'normal_work': 'UNKNOWN', 'evidence': {'source': None, 'text': None, 'observed_at': None}}
                    else:
                        slot['observation'] = {'phase_verified': 'UNKNOWN', 'load_state': 'UNKNOWN', 'single_person': 'UNKNOWN', 'full_frame': 'UNKNOWN', 'camera_fixed': 'UNKNOWN', 'normal_cycle': 'UNKNOWN', 'evidence': {'source': None, 'text': None, 'observed_at': None}}
                    changed = True
            remaining_manual = [value for value in input_data['manual'] if value['photo_id'] != photo_id]
            if len(remaining_manual) != len(input_data['manual']):
                input_data['manual'] = remaining_manual
                changed = True
            if changed:
                connection.execute('UPDATE TASK SET input_json = ?, input_revision = ?, updated_at = ? WHERE task_id = ?', (_dump(input_data), (task['input_revision'] or 0) + 1, _utc_now(), photo['task_id']))
        connection.execute('DELETE FROM PHOTO WHERE photo_id = ?', (photo_id,))
