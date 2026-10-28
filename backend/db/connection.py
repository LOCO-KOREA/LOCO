"""SQLite connection setup for the six-table demo schema."""
from __future__ import annotations

import os
import sqlite3
from pathlib import Path

_HERE = Path(__file__).parent
SCHEMA_FILE = _HERE / "schema_v1.sql"


def default_db_path() -> Path:
    """Return the local app database path defined by the DB architecture."""
    local_app_data = os.environ.get("LOCALAPPDATA")
    root = Path(local_app_data) if local_app_data else Path.home() / "AppData" / "Local"
    return root / "LOCO" / "loco_demo.db"


def open_db(path: str | Path | None = None) -> sqlite3.Connection:
    """Open the demo database and ensure its six tables exist."""
    target = Path(path) if path is not None and str(path) != ":memory:" else None
    if path is None:
        target = default_db_path()

    db_name = ":memory:" if target is None else str(target)
    if target is not None:
        target.parent.mkdir(parents=True, exist_ok=True)

    connection = sqlite3.connect(db_name)
    connection.row_factory = sqlite3.Row
    try:
        existing={row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")}
        expected={'SURVEY','TASK','PHOTO','ANALYSIS','APP_SETTINGS','EXPORT_LOG'}
        if existing and existing!=expected:
            raise sqlite3.DatabaseError('지원하지 않는 DB 구조입니다. 기존 파일을 변경하지 않았습니다. LOCO 1.3/2.0의 여섯 JSON 테이블이 필요합니다.')
        connection.executescript(SCHEMA_FILE.read_text(encoding="utf-8"))
    except Exception:
        connection.close()
        raise
    return connection
