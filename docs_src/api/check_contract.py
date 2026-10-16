"""Validate the current JSON contract, not retired relational SQL views."""
import runpy
from pathlib import Path
runpy.run_path(str(Path(__file__).resolve().parents[2]/'scripts/audit_contract.py'),run_name='__main__')
