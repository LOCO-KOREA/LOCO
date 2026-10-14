"""엑셀 보고서 (기능정의서 F06-01, API 계약서 7.1절).

- 시트 4개. 확정되지 않은 칸은 '초안'으로 표시하고 연노랑 배경을 칠한다.
- 모든 시트 아래에 책임 문구: "부담작업 해당 여부 결정과 조사 결과의 책임은 사업주와 조사자에게 있습니다."
- 이미지는 대표 사진만 넣는다.
- 파일 이름: 유해요인조사_{조사일}_{작업공정명}.xlsx. 같은 이름이 있으면 _2, _3을 붙인다.
"""
from __future__ import annotations

from pathlib import Path

from .. import contracts as C

SHEET_NAMES = ("요약", "작업별 결과", "경고 기록", "판정 초안")
RESPONSIBILITY_NOTE = "부담작업 해당 여부 결정과 조사 결과의 책임은 사업주와 조사자에게 있습니다."


def write_workbook(survey: C.SurveyDetail, results: dict, path: Path) -> int:
    """조사와 단위작업별 결과 → 엑셀 파일. 돌려주는 값은 '초안'으로 표시한 칸의 수.
    수용 기준: AC-29 (엑셀에서 열리고 시트가 4개, 확정되지 않은 칸에 '초안')."""
    raise NotImplementedError("WP3")
