"""DTO persistence for the six-table SQLite schema.

This module only maps DTO fields to rows and JSON text. Application services
own calculations, currentness, summaries, validation, and user-facing errors.
"""
from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Iterator, Mapping

from .connection import open_db

JsonObject = Mapping[str, Any]


@contextmanager
def _transaction(db_path: str | None = None) -> Iterator[sqlite3.Connection]:
    connection = open_db(db_path)
    try:
        with connection:
            yield connection
    finally:
        connection.close()


def _dump(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _load(value: str | None) -> Any:
    return json.loads(value) if value is not None else None


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _survey(row: sqlite3.Row | None) -> dict[str, Any] | None:
    if row is None:
        return None
    return {
        **_load(row["metadata_json"]),
        "survey_id": row["survey_id"],
        "metadata_revision": row["metadata_revision"],
        "review": _load(row["review_json"]),
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def _task(row: sqlite3.Row | None) -> dict[str, Any] | None:
    if row is None:
        return None
    return {
        **_load(row["input_json"]),
        "task_id": row["task_id"],
        "survey_id": row["survey_id"],
        "input_revision": row["input_revision"],
        "latest_analysis_id": row["latest_analysis_id"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def _photo(row: sqlite3.Row | None) -> dict[str, Any] | None:
    if row is None:
        return None
    return {
        "photo_id": row["photo_id"],
        "task_id": row["task_id"],
        **_load(row["metadata_json"]),
    }


def _analysis(row: sqlite3.Row | None) -> dict[str, Any] | None:
    if row is None:
        return None
    result = _load(row["result_json"]) or {}
    return {
        "analysis_id": row["analysis_id"],
        "task_id": row["task_id"],
        "input_revision": row["input_revision"],
        "snapshot": _load(row["snapshot_json"]),
        **result,
        "status": row["status"],
        "created_at": row["created_at"],
        "finished_at": row["finished_at"],
    }


def create_survey(
    draft: JsonObject,
    review: JsonObject,
    created_at: str,
    updated_at: str,
    *,
    db_path: str | None = None,
) -> int:
    with _transaction(db_path) as connection:
        cursor = connection.execute(
            "INSERT INTO SURVEY "
            "(metadata_revision, metadata_json, review_json, created_at, updated_at) "
            "VALUES (0, ?, ?, ?, ?)",
            (_dump(draft), _dump(review), created_at, updated_at),
        )
        return int(cursor.lastrowid)


def get_survey(survey_id: int, *, db_path: str | None = None) -> dict[str, Any] | None:
    with _transaction(db_path) as connection:
        row = connection.execute(
            "SELECT * FROM SURVEY WHERE survey_id = ?", (survey_id,)
        ).fetchone()
        return _survey(row)


def list_surveys(*, db_path: str | None = None) -> list[dict[str, Any]]:
    with _transaction(db_path) as connection:
        rows = connection.execute("SELECT * FROM SURVEY ORDER BY survey_id").fetchall()
        return [_survey(row) for row in rows]


def update_survey_metadata(
    survey_id: int,
    draft: JsonObject,
    updated_at: str,
    *,
    db_path: str | None = None,
) -> int | None:
    with _transaction(db_path) as connection:
        row = connection.execute(
            "SELECT metadata_revision FROM SURVEY WHERE survey_id = ?", (survey_id,)
        ).fetchone()
        if row is None:
            return None
        revision = (row["metadata_revision"] or 0) + 1
        connection.execute(
            "UPDATE SURVEY SET metadata_json = ?, metadata_revision = ?, updated_at = ? "
            "WHERE survey_id = ?",
            (_dump(draft), revision, updated_at, survey_id),
        )
        return int(revision)


def set_survey_review(
    survey_id: int,
    review: JsonObject,
    updated_at: str,
    *,
    db_path: str | None = None,
) -> None:
    with _transaction(db_path) as connection:
        connection.execute(
            "UPDATE SURVEY SET review_json = ?, updated_at = ? WHERE survey_id = ?",
            (_dump(review), updated_at, survey_id),
        )


def create_task(
    survey_id: int,
    input_data: JsonObject,
    created_at: str,
    updated_at: str,
    *,
    db_path: str | None = None,
) -> int:
    with _transaction(db_path) as connection:
        cursor = connection.execute(
            "INSERT INTO TASK "
            "(survey_id, input_revision, latest_analysis_id, input_json, created_at, updated_at) "
            "VALUES (?, 0, NULL, ?, ?, ?)",
            (survey_id, _dump(input_data), created_at, updated_at),
        )
        return int(cursor.lastrowid)


def get_task(task_id: int, *, db_path: str | None = None) -> dict[str, Any] | None:
    with _transaction(db_path) as connection:
        row = connection.execute("SELECT * FROM TASK WHERE task_id = ?", (task_id,)).fetchone()
        return _task(row)


def list_tasks(survey_id: int, *, db_path: str | None = None) -> list[dict[str, Any]]:
    with _transaction(db_path) as connection:
        rows = connection.execute(
            "SELECT * FROM TASK WHERE survey_id = ? ORDER BY task_id", (survey_id,)
        ).fetchall()
        return [_task(row) for row in rows]


def update_task_input(
    task_id: int,
    input_data: JsonObject,
    updated_at: str,
    *,
    db_path: str | None = None,
) -> int | None:
    with _transaction(db_path) as connection:
        row = connection.execute(
            "SELECT input_revision FROM TASK WHERE task_id = ?", (task_id,)
        ).fetchone()
        if row is None:
            return None
        revision = (row["input_revision"] or 0) + 1
        connection.execute(
            "UPDATE TASK SET input_json = ?, input_revision = ?, updated_at = ? "
            "WHERE task_id = ?",
            (_dump(input_data), revision, updated_at, task_id),
        )
        return int(revision)


def set_latest_analysis(
    task_id: int,
    analysis_id: int | None,
    *,
    db_path: str | None = None,
) -> None:
    with _transaction(db_path) as connection:
        connection.execute(
            "UPDATE TASK SET latest_analysis_id = ? WHERE task_id = ?",
            (analysis_id, task_id),
        )


def create_photo(
    task_id: int,
    metadata: JsonObject,
    *,
    db_path: str | None = None,
) -> int:
    with _transaction(db_path) as connection:
        cursor = connection.execute(
            "INSERT INTO PHOTO (task_id, metadata_json) VALUES (?, ?)",
            (task_id, _dump(metadata)),
        )
        return int(cursor.lastrowid)


def get_photo(photo_id: int, *, db_path: str | None = None) -> dict[str, Any] | None:
    with _transaction(db_path) as connection:
        row = connection.execute("SELECT * FROM PHOTO WHERE photo_id = ?", (photo_id,)).fetchone()
        return _photo(row)


def list_photos(task_id: int, *, db_path: str | None = None) -> list[dict[str, Any]]:
    with _transaction(db_path) as connection:
        rows = connection.execute(
            "SELECT * FROM PHOTO WHERE task_id = ? ORDER BY photo_id", (task_id,)
        ).fetchall()
        return [_photo(row) for row in rows]


def update_photo(
    photo_id: int,
    metadata: JsonObject,
    *,
    db_path: str | None = None,
) -> None:
    with _transaction(db_path) as connection:
        connection.execute(
            "UPDATE PHOTO SET metadata_json = ? WHERE photo_id = ?",
            (_dump(metadata), photo_id),
        )


def delete_photo(photo_id: int, *, db_path: str | None = None) -> None:
    with _transaction(db_path) as connection:
        photo = connection.execute(
            "SELECT task_id FROM PHOTO WHERE photo_id = ?", (photo_id,)
        ).fetchone()
        if photo is None:
            return

        task = connection.execute(
            "SELECT input_revision, input_json FROM TASK WHERE task_id = ?",
            (photo["task_id"],),
        ).fetchone()
        if task is not None:
            input_data = _load(task["input_json"])
            changed = False
            for slot in input_data["capture"]["slots"]:
                if slot["photo_id"] == photo_id:
                    slot["photo_id"] = None
                    if input_data.get("schema_version") == "2.0":
                        slot["analysis_target"] = False
                        slot["observation"] = {
                            "load_state": "UNKNOWN", "measured_load_kg": None,
                            "single_person": "UNKNOWN", "full_frame": "UNKNOWN",
                            "normal_work": "UNKNOWN",
                            "evidence": {"source": None, "text": None, "observed_at": None},
                        }
                    else:
                        slot["observation"] = {
                            "phase_verified": "UNKNOWN", "load_state": "UNKNOWN",
                            "single_person": "UNKNOWN", "full_frame": "UNKNOWN",
                            "camera_fixed": "UNKNOWN", "normal_cycle": "UNKNOWN",
                            "evidence": {"source": None, "text": None, "observed_at": None},
                        }
                    changed = True

            remaining_manual = [
                value for value in input_data["manual"] if value["photo_id"] != photo_id
            ]
            if len(remaining_manual) != len(input_data["manual"]):
                input_data["manual"] = remaining_manual
                changed = True

            if changed:
                connection.execute(
                    "UPDATE TASK SET input_json = ?, input_revision = ?, updated_at = ? "
                    "WHERE task_id = ?",
                    (
                        _dump(input_data),
                        (task["input_revision"] or 0) + 1,
                        _utc_now(),
                        photo["task_id"],
                    ),
                )

        connection.execute("DELETE FROM PHOTO WHERE photo_id = ?", (photo_id,))


def create_analysis(
    task_id: int,
    input_revision: int,
    status: str,
    snapshot: JsonObject,
    created_at: str,
    *,
    result: JsonObject | None = None,
    db_path: str | None = None,
) -> int:
    initial_result = result if result is not None else {
        "pose": None,
        "slot_tags": [],
        "tags": [],
        "reba": None,
        "judgment": None,
        "ai": [],
        "notes": [],
    }
    with _transaction(db_path) as connection:
        cursor = connection.execute(
            "INSERT INTO ANALYSIS "
            "(task_id, input_revision, status, snapshot_json, result_json, created_at, finished_at) "
            "VALUES (?, ?, ?, ?, ?, ?, NULL)",
            (task_id, input_revision, status, _dump(snapshot), _dump(initial_result), created_at),
        )
        analysis_id = int(cursor.lastrowid)
        connection.execute(
            "UPDATE TASK SET latest_analysis_id = ? WHERE task_id = ?",
            (analysis_id, task_id),
        )
        return analysis_id


def get_analysis(analysis_id: int, *, db_path: str | None = None) -> dict[str, Any] | None:
    with _transaction(db_path) as connection:
        row = connection.execute(
            "SELECT * FROM ANALYSIS WHERE analysis_id = ?", (analysis_id,)
        ).fetchone()
        return _analysis(row)


def list_analyses(task_id: int, *, db_path: str | None = None) -> list[dict[str, Any]]:
    with _transaction(db_path) as connection:
        rows = connection.execute(
            "SELECT * FROM ANALYSIS WHERE task_id = ? ORDER BY analysis_id", (task_id,)
        ).fetchall()
        return [_analysis(row) for row in rows]


def update_analysis(
    analysis_id: int,
    status: str,
    result: JsonObject,
    finished_at: str | None,
    *,
    db_path: str | None = None,
) -> None:
    with _transaction(db_path) as connection:
        connection.execute(
            "UPDATE ANALYSIS SET status = ?, result_json = ?, finished_at = ? "
            "WHERE analysis_id = ?",
            (status, _dump(result), finished_at, analysis_id),
        )


def get_settings(*, db_path: str | None = None) -> dict[str, Any] | None:
    with _transaction(db_path) as connection:
        row = connection.execute(
            "SELECT settings_json FROM APP_SETTINGS WHERE settings_id = 1"
        ).fetchone()
        return _load(row["settings_json"]) if row is not None else None


def update_settings(settings: JsonObject, *, db_path: str | None = None) -> None:
    persisted = {
        "analysis": settings["analysis"],
        "gpt_enabled": settings["gpt_enabled"],
        "gpt_model": settings["gpt_model"],
        "ui": settings["ui"],
    }
    with _transaction(db_path) as connection:
        connection.execute(
            "INSERT INTO APP_SETTINGS (settings_id, settings_json) VALUES (1, ?) "
            "ON CONFLICT(settings_id) DO UPDATE SET settings_json = excluded.settings_json",
            (_dump(persisted),),
        )


def create_export_log(
    survey_id: int,
    file_path: str,
    snapshot: JsonObject,
    receipt: JsonObject,
    created_at: str,
    *,
    db_path: str | None = None,
) -> int:
    with _transaction(db_path) as connection:
        cursor = connection.execute(
            "INSERT INTO EXPORT_LOG "
            "(survey_id, file_path, snapshot_json, receipt_json, created_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (survey_id, file_path, _dump(snapshot), _dump(receipt), created_at),
        )
        return int(cursor.lastrowid)


def list_export_logs(survey_id: int, *, db_path: str | None = None) -> list[dict[str, Any]]:
    with _transaction(db_path) as connection:
        rows = connection.execute(
            "SELECT * FROM EXPORT_LOG WHERE survey_id = ? ORDER BY export_id", (survey_id,)
        ).fetchall()
        return [
            {
                "export_id": row["export_id"],
                "survey_id": row["survey_id"],
                "file_path": row["file_path"],
                "snapshot": _load(row["snapshot_json"]),
                "receipt": _load(row["receipt_json"]),
                "created_at": row["created_at"],
            }
            for row in rows
        ]


def _delete_task_rows(connection: sqlite3.Connection, task_id: int) -> None:
    connection.execute("DELETE FROM PHOTO WHERE task_id = ?", (task_id,))
    connection.execute("DELETE FROM ANALYSIS WHERE task_id = ?", (task_id,))
    connection.execute("DELETE FROM TASK WHERE task_id = ?", (task_id,))


def delete_task(task_id: int, *, db_path: str | None = None) -> None:
    with _transaction(db_path) as connection:
        _delete_task_rows(connection, task_id)


def delete_survey(survey_id: int, *, db_path: str | None = None) -> None:
    with _transaction(db_path) as connection:
        task_rows = connection.execute(
            "SELECT task_id FROM TASK WHERE survey_id = ?", (survey_id,)
        ).fetchall()
        for row in task_rows:
            _delete_task_rows(connection, row["task_id"])
        connection.execute("DELETE FROM EXPORT_LOG WHERE survey_id = ?", (survey_id,))
        connection.execute("DELETE FROM SURVEY WHERE survey_id = ?", (survey_id,))
