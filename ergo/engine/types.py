"""엔진이 주고받는 값 (제안. 10/14 회의에서 확정). 필드 이름은 ERD의 frame_angle 컬럼과 같다."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Optional

# 관절 17개 (기능정의서 F04-01). 모델이 33개를 내도 이 17개만 쓴다.
KEYPOINT_NAMES = (
    "nose", "left_eye", "right_eye", "left_ear", "right_ear",
    "left_shoulder", "right_shoulder", "left_elbow", "right_elbow", "left_wrist", "right_wrist",
    "left_hip", "right_hip", "left_knee", "right_knee", "left_ankle", "right_ankle",
)


@dataclass(frozen=True)
class EngineParams:
    """분석 한 번에 쓴 기술 파라미터 (기능정의서 8절 TP-01~11). analysis_run 컬럼의 기본값과 같다."""
    conf_min: float = 0.5            # TP-02 관절 신뢰도 하한
    jitter_deg: float = 5.0          # TP-01 확신도에서 각도를 흔드는 폭
    smoothing_frames: int = 5        # TP-09 각도 평활화 (이동 평균)


@dataclass(frozen=True)
class Keypoint:
    x: float                         # 화면 가로 비율 0~1, 왼쪽이 0
    y: float                         # 화면 세로 비율 0~1, 위쪽이 0
    conf: float                      # 0~1


@dataclass(frozen=True)
class FrameKeypoints:
    frame_no: int
    points: Mapping[str, Keypoint]   # KEYPOINT_NAMES의 이름 → 점. 안 보이는 점은 conf_min 미만이거나 빠짐
    person_count: int = 1            # 2 이상이면 W-ANALYSIS-002 (가장 크게 보이는 한 명만 씀, EX-05)


@dataclass(frozen=True)
class FrameAngles:
    """프레임 하나의 각도와 자세 표시. ERD frame_angle 테이블의 한 행 (run_id 제외)."""
    frame_no: int
    valid_yn: bool                                   # 판별에 쓸 관절이 보이는 프레임인가
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
