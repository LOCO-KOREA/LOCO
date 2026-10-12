"""문서 생성 도구가 쓰는 경로를 한 곳에 모은다.

원본(스키마, 시드, 계약)은 ergo/ 아래에 하나씩만 둔다. 문서 생성 도구는 거기서 읽는다.
문서가 나가는 곳(DOCS)은 저장소의 docs/ 이다. 환경 변수 ERGO_DOCS로 바꿀 수 있다 (손으로 쓴 문서는 그 폴더에 있어야 한다).
"""
import os
from pathlib import Path

SRC = Path(__file__).resolve().parent
PROJECT = SRC.parent
ERGO = PROJECT / "ergo"
SCHEMA_FILE = ERGO / "db" / "schema_v1.sql"
SEED_FILE = ERGO / "db" / "seed_v1.sql"
CONTRACTS_FILE = ERGO / "contracts.py"
DOCS = Path(os.environ.get("ERGO_DOCS") or (PROJECT / "docs"))
WORK = SRC / ".work"
WORK.mkdir(exist_ok=True)


def write_text(path, text):
    """LF로 쓴다. Windows 기본(CRLF)으로 쓰면 줄마다 다른 것으로 보여 변경 내역이 지저분해진다."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
