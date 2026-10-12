"""법 문구 자세 판별과 비율 (WP1 · 기능정의서 F04-04, F04-05).

판별 기준은 각도 기준(thresholds) 하나만 쓴다. 기본값은 고용노동부 해설 값이고, 조사자가 사유와 함께 바꿀 수 있다.
앱이 만든 기준은 쓰지 않는다 (BR-01).

자세 비율은 사진 표본의 비율이다: 그 자세로 판별된 사진 수 ÷ 판별 가능한 사진 수 (워크샘플링, BR-05).
"""
from __future__ import annotations

from typing import Mapping, Sequence

from .. import contracts as C
from .types import StillAngles

Thresholds = Mapping[C.ThresholdCode, float]


def classify_postures(angles: Sequence[StillAngles], thresholds: Thresholds) -> list[dict]:
    """사진별 각도 → 사진별 자세 판별 (3호 a~d, 4호 a~c, 4호 제외, 5호 a·b).

    판별에 필요한 관절이 안 보이는 사진은 그 자세를 '판별 불가'로 두고 표본에서 뺀다.
    수용 기준: AC-14 (허리 25° → 세고 15° → 안 센다), AC-15 (무릎을 바닥에 댄 굽힘은 세지 않는다).
    """
    raise NotImplementedError("WP1")


def posture_shares(postures: Sequence[dict], daily_work_h: float | None) -> list[C.PostureShare]:
    """사진별 자세 → 자세별 비율과 하루 노출 시간 (비율 × 하루 작업시간). 3호는 a~d를 합쳐 한 번만 센다.

    수용 기준: AC-16 (7장 ÷ 20장 = 35% × 6시간 = 2.10시간), AC-17 (a 4장 · b 2장 · 동시 2장 → 3호 8장 ÷ 20장 = 40%).
    판정은 반올림하기 전 값으로 한다 (F04-05 규칙 5).
    """
    raise NotImplementedError("WP1")
