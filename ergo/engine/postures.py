"""법 문구 자세 판별과 비율 (WP1 · 기능정의서 F04-04, F04-05).

판별 기준은 각도 기준(thresholds) 하나만 쓴다. 기본값은 고용노동부 해설 값이고, 조사자가 사유와 함께 바꿀 수 있다.
앱이 만든 기준은 쓰지 않는다 (BR-01).
"""
from __future__ import annotations

from typing import Mapping, Sequence

from .. import contracts as C
from .types import FrameAngles

Thresholds = Mapping[C.ThresholdCode, float]


def classify_postures(angles: Sequence[FrameAngles], thresholds: Thresholds) -> list[dict]:
    """프레임별 각도 → 프레임별 자세 판별 (3호 a~d, 4호 a~c, 4호 제외, 5호 a·b).

    판별에 필요한 관절이 안 보이는 프레임은 그 자세를 '판별 불가'로 두고 분석 구간에서 뺀다.
    수용 기준: AC-14 (허리 25° → 세고 15° → 안 센다), AC-15 (무릎을 바닥에 댄 굽힘은 세지 않는다).
    """
    raise NotImplementedError("WP1")


def posture_shares(postures: Sequence[dict], daily_work_h: float | None) -> list[C.PostureShare]:
    """프레임별 자세 → 자세별 비율과 하루 노출 시간 (비율 × 하루 작업시간). 3호는 a~d를 합쳐 한 번만 센다.

    수용 기준: AC-16 (35% × 6시간 = 2.10시간), AC-17 (a 20% · b 10% · 동시 10% → 3호 40%).
    판정은 반올림하기 전 값으로 한다 (F04-05 규칙 5).
    """
    raise NotImplementedError("WP1")
