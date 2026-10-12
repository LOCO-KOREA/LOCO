"""REBA 점수와 대표 장면 (WP1 · 기능정의서 F04-06, F04-07).

원본은 Hignett & McAtamney (2000)의 워크시트 (Cornell 대학 Alan Hedge의 REBA Employee Assessment Worksheet).
저작권이 있는 자료라 저장소에는 넣지 않았다. 정욱님 PC의 REBA_워크시트.png/.txt를 받아 쓴다.
REBA는 위험 정도만 보여 준다. 판정과 경고에는 쓰지 않는다 (BR-15).
"""
from __future__ import annotations

from typing import Sequence

from .. import contracts as C
from .types import FrameAngles


def reba_for_frame(angles: FrameAngles, reba_inputs: C.RebaInputs) -> C.RebaScore:
    """프레임 하나의 각도 + 사람 입력 → REBA 단계별 점수와 합계 (1~15).

    사람 입력이 비어 있으면 그 칸을 needs_review_items에 넣고 빈 칸을 0으로 둔 임시 점수(provisional_yn)를 낸다.
    좌우 중 점수가 높은 쪽을 쓴다 (TP-10).
    수용 기준: AC-18 (KOSHA 지침 '휠 들어올리기' 예시 8점), AC-19 (손목을 입력하면 표시가 바뀐다).
    """
    raise NotImplementedError("WP1")


def pick_key_frame(scores: Sequence[C.RebaScore]) -> int:
    """프레임별 REBA 점수 → 대표 장면 번호. 가장 높은 점수, 같으면 먼저 나온 프레임 (F04-07 규칙 1).

    수용 기준: AC-20 (대표 장면을 바꾸면 점수가 다시 계산되고 이력에 한 줄이 남는다).
    """
    raise NotImplementedError("WP1")
