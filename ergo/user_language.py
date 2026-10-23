"""Presentation only; stored facts, quotations and historical snapshots stay intact."""
import json
import re
import sys
from pathlib import Path

RESOURCE = (Path(sys._MEIPASS) / 'user-language.json' if getattr(sys, 'frozen', False)
            else Path(__file__).resolve().parents[1] / 'frontend' / 'user-language.json')
TERMS = json.loads(RESOURCE.read_text(encoding='utf-8'))
TOKEN = re.compile(r'(?<![A-Za-z0-9_])(' + '|'.join(re.escape(k) for k in sorted(TERMS, key=len, reverse=True)) + r')(?![A-Za-z0-9_])')


def user_text(value):
    return TOKEN.sub(lambda m: TERMS[m[0]], value) if isinstance(value, str) else value
