"""REBA 점수와 대표 사진 (WP1 · 기능정의서 F04-06, F04-07).

원본은 Hignett & McAtamney (2000)의 워크시트 (Cornell 대학 Alan Hedge의 REBA Employee Assessment Worksheet).
저작권이 있는 자료라 저장소에는 넣지 않았다. 정욱님 PC의 REBA_워크시트.png/.txt를 받아 쓴다.
REBA는 위험 정도만 보여 준다. 판정과 경고에는 쓰지 않는다 (BR-15).

REBA의 목·몸통·위팔은 20°와 45° 구간 경계를 쓴다. 비틂은 각도 없이 '비틀면 +1'이다.
MoveNet에는 손 점이 없어 손목 칸은 조사자 입력이다 (F04-06).
"""
from __future__ import annotations

from typing import Sequence

from .. import contracts as C
from .types import StillAngles


def reba_for_still(angles: StillAngles, reba_inputs: C.RebaInputs) -> C.RebaScore:
    """사진 한 장의 각도 + 사람 입력 → REBA 단계별 점수와 합계 (1~15).

    사람 입력이 비어 있으면 그 칸을 needs_review_items에 넣고 빈 칸을 0으로 둔 임시 점수(provisional_yn)를 낸다.
    좌우 중 점수가 높은 쪽을 쓴다 (TP-10).
    수용 기준: AC-18 (KOSHA 지침 '휠 들어올리기' 예시 8점), AC-19 (손목을 입력하면 표시가 바뀐다).
    """
    raise NotImplementedError("WP1")


def pick_key_still(scores: Sequence[C.RebaScore]) -> int:
    """사진별 REBA 점수 → 대표 사진의 위치(0부터). 가장 높은 점수, 같으면 먼저 올린 사진 (F04-07 규칙 1).

    수용 기준: AC-20 (대표 사진을 바꾸면 점수가 다시 계산되고 이력에 한 줄이 남는다).
    """
    raise NotImplementedError("WP1")
