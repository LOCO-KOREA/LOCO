"""관절 각도 계산 (WP1 · 기능정의서 F04-03).

기능정의서의 표를 따른다. 핵심: 4호·3호는 해설대로 '수직 기준'으로, REBA는 워크시트대로 '몸통 기준'으로 잰다.
같은 목이라도 두 각도가 다를 수 있다 (neck_tilt_vert_deg와 neck_flex_trunk_deg).
"""
from __future__ import annotations

from typing import Sequence

from .types import EngineParams, FrameAngles, FrameKeypoints


def compute_angles(keypoints: Sequence[FrameKeypoints], params: EngineParams) -> list[FrameAngles]:
    """프레임별 관절 → 프레임별 각도. 왼쪽·오른쪽을 따로 계산하고 TP-09 평활화를 한다.

    수용 기준: AC-13 (각도기로 잰 재연 영상과 비교한 평균 오차. 목표치는 10/17 기술 검토에서 정함).
    """
    raise NotImplementedError("WP1")
