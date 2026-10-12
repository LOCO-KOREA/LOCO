"""SQLite 연결 열기 (ERD 설계서 6.1, 6.7절). 연결 규칙은 이 한 곳에서만 적용한다.

- 연결마다 PRAGMA foreign_keys = ON  (SQLite는 기본이 꺼져 있다)
- 연결마다 PRAGMA busy_timeout = 3000
- 파일을 새로 만들 때 journal_mode = WAL, 스키마와 기준 정보(시드)를 넣고 user_version을 맞춘다
- 스레드마다 연결을 따로 연다. sqlite3 연결은 만든 스레드에서만 쓴다 (분석 스레드와 화면 스레드는 서로 다른 연결)

DB 담당(한정욱)이 이 파일을 다듬는다. 저장소(Repository) 계층은 아직 없다 — README의 '해야 할 것' 참고.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

MIN_SQLITE = (3, 38, 0)                  # STRICT 테이블은 3.37, JSON 함수 내장은 3.38부터
SCHEMA_VERSION = 1                       # schema_version 테이블의 마지막 번호와 PRAGMA user_version이 같아야 한다
_HERE = Path(__file__).parent
SCHEMA_FILE = _HERE / "schema_v1.sql"
SEED_FILE = _HERE / "seed_v1.sql"


def open_db(path: str | Path = ":memory:") -> sqlite3.Connection:
    """DB 연결을 연다. ':memory:'이거나 파일이 없으면 새로 만든다."""
    if sqlite3.sqlite_version_info < MIN_SQLITE:
        raise RuntimeError(f"SQLite {sqlite3.sqlite_version}은(는) 너무 낮다. {'.'.join(map(str, MIN_SQLITE))} 이상이 필요하다 "
                           "(STRICT 테이블, JSON 함수). Python 3.11 이상의 공식 설치본을 쓰면 충분하다.")
    memory = str(path) == ":memory:"
    is_new = memory or not Path(path).exists()
    con = sqlite3.connect(str(path), timeout=3.0)
    con.execute("PRAGMA foreign_keys = ON")
    con.execute("PRAGMA busy_timeout = 3000")
    if is_new:
        if not memory:
            con.execute("PRAGMA journal_mode = WAL")
        con.executescript(SCHEMA_FILE.read_text(encoding="utf-8"))
        con.executescript(SEED_FILE.read_text(encoding="utf-8"))
        con.execute(f"PRAGMA user_version = {int(SCHEMA_VERSION)}")      # PRAGMA는 매개변수를 못 쓴다
        con.commit()
    else:
        version = con.execute("PRAGMA user_version").fetchone()[0]
        if version != SCHEMA_VERSION:
            con.close()
            # 마이그레이션 (ERD 6.7절): 변경 전 백업 → 순서대로 .sql 실행 → user_version 갱신. DB 담당이 채운다.
            raise RuntimeError(f"스키마 버전 {version}을(를) 열 수 없음 (이 프로그램은 {SCHEMA_VERSION}). 마이그레이션이 필요함")
    return con
