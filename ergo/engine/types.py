"""엔진이 주고받는 값 (제안. 10/14 회의에서 확정). 필드 이름은 ERD의 still_angle 컬럼과 같다.

MVP의 분석 입력은 사진(스틸샷)이고 관절 모델은 MoveNet Lightning이다 (2026-10-12 정욱 결정,
기능정의서 D-MVP-01 · D-MODEL-01). 사진 한 장이 분석의 한 단위다.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Optional

# 관절 17개 (기능정의서 F04-01). MoveNet이 내는 17개와 이름과 순서가 같다 (COCO 순서).
# MoveNet에는 발끝·발뒤꿈치·손가락 점이 없다: 5호의 '발끝보다 앞'(TP-05)과 REBA 손목은 이 점들로 못 잰다.
KEYPOINT_NAMES = (
    "nose", "left_eye", "right_eye", "left_ear", "right_ear",
    "left_shoulder", "right_shoulder", "left_elbow", "right_elbow", "left_wrist", "right_wrist",
    "left_hip", "right_hip", "left_knee", "right_knee", "left_ankle", "right_ankle",
)


@dataclass(frozen=True)
class EngineParams:
    """분석 한 번에 쓴 기술 파라미터 (기능정의서 8절 TP). analysis_run 컬럼의 기본값과 같다."""
    conf_min: float = 0.5            # TP-02 관절 신뢰도 하한 (MoveNet은 가려진 점의 점수가 낮다. 재연 사진으로 정함)
    jitter_deg: float = 5.0          # TP-01 확신도에서 각도를 흔드는 폭
    min_sample_cnt: int = 10         # TP-12 표본(사진) 최소 장수. 판별 가능한 사진이 이보다 적으면 자세 비율 판정은 '사람 확인'


@dataclass(frozen=True)
class Keypoint:
    x: float                         # 사진 가로 비율 0~1, 왼쪽이 0 (회전 정보를 적용해 똑바로 세운 사진 기준)
    y: float                         # 사진 세로 비율 0~1, 위쪽이 0
    conf: float                      # 0~1


@dataclass(frozen=True)
class StillKeypoints:
    still_id: int
    points: Mapping[str, Keypoint]   # KEYPOINT_NAMES의 이름 → 점. conf_min 미만인 점은 '안 보임'으로 둔다
    person_found_yn: bool = True     # 몸통 점(어깨·엉덩이)을 하나도 못 찾으면 False → 판별 불가 사진 (E-ANALYSIS-001의 재료)


@dataclass(frozen=True)
class StillAngles:
    """사진 한 장의 각도와 자세 표시. ERD still_angle 테이블의 한 행 (run_id 제외)."""
    still_id: int
    valid_yn: bool                                   # 판별에 쓸 관절이 보이는 사진인가
    trunk_tilt_deg: Optional[float] = None           # 앞으로 숙이면 +, 뒤로 젖히면 − (수직 기준)
    neck_tilt_vert_deg: Optional[float] = None
    neck_flex_trunk_deg: Optional[float] = None      # REBA용 (몸통 기준)
    upper_arm_raise_l_deg: Optional[float] = None
    upper_arm_raise_r_deg: Optional[float] = None
    upper_arm_flex_l_deg: Optional[float] = None
    upper_arm_flex_r_deg: Optional[float] = None
    elbow_flex_l_deg: Optional[float] = None
    elbow_flex_r_deg: Optional[float] = None
    knee_flex_l_deg: Optional[float] = None
    knee_flex_r_deg: Optional[float] = None
    hand_above_head_yn: Optional[bool] = None
    elbow_above_shoulder_yn: Optional[bool] = None
    elbow_behind_trunk_yn: Optional[bool] = None
    squat_yn: Optional[bool] = None
    kneeling_yn: Optional[bool] = None
    knee_on_floor_yn: Optional[bool] = None
