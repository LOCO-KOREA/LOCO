"""관절 각도 계산 (WP1 · 기능정의서 F04-03).

기능정의서의 표를 따른다. 핵심: 4호·3호는 해설대로 '수직 기준'으로, REBA는 워크시트대로 '몸통 기준'으로 잰다.
같은 목이라도 두 각도가 다를 수 있다 (neck_tilt_vert_deg와 neck_flex_trunk_deg).

사진은 2차원이다. 앞으로 숙임·젖힘은 옆모습 사진에서, 옆으로 드는 팔은 정면 사진에서 의미가 있다 (OI-07).
MoveNet에는 발끝·손가락 점이 없어 5호의 '발끝보다 앞'(TP-05)과 REBA 손목은 이 점들로 못 잰다. 사람 확인으로 둔다.
"""
from __future__ import annotations

from typing import Sequence

from .types import EngineParams, StillAngles, StillKeypoints


def compute_angles(keypoints: Sequence[StillKeypoints], params: EngineParams) -> list[StillAngles]:
    """사진별 관절 → 사진별 각도. 왼쪽·오른쪽을 따로 계산한다. 사진은 서로 이어지지 않으므로 평활화는 없다.

    수용 기준: AC-13 (각도기로 잰 재연 사진과 비교한 평균 오차. 목표치는 10/17 기술 검토에서 정함).
    """
    raise NotImplementedError("WP1")
