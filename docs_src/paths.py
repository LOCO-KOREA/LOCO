"""레거시 계약·스키마 검증 스크립트가 참조하는 프로토타입 코드 경로."""
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
ERGO = PROJECT / "ergo"
SCHEMA_FILE = ERGO / "db" / "schema_v1.sql"
SEED_FILE = ERGO / "db" / "seed_v1.sql"
CONTRACTS_FILE = ERGO / "contracts.py"
