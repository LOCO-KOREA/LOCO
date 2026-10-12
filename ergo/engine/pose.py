"""관절 추출과 얼굴 가림 (WP1 · 기능정의서 F04-01, F04-02 · API 계약서 5절).

알려진 함정 (2026-10-08 이 PC에서 확인)
- MediaPipe는 모델 파일 경로에 한글이 하나라도 있으면 `model_asset_path`로 못 연다.
  `model_asset_buffer=open(경로, "rb").read()`로 읽어서 넘긴다. OpenCV는 한글 경로를 열 수 있다.
- OpenCV 5는 폰 회전 정보를 기본으로 적용한다 (ORIENTATION_AUTO=1). 끄면 옆으로 누운 프레임이 되고,
  MediaPipe가 그래도 사람을 찾아 각도가 조용히 틀린다. 끄지 않는다.
- 처리 속도 (i7-10700K, 720×1280, 프레임당): MediaPipe Lite 11.9ms · Full 16.0ms · Heavy 49.8ms.
"""
from __future__ import annotations

import threading
from pathlib import Path
from typing import Callable, Iterator, Optional

from .types import EngineParams, FrameKeypoints


def extract_keypoints(video_path: Path, model_id: int, params: EngineParams,
                      on_frame: Optional[Callable[[int, int], None]] = None,
                      cancel: Optional[threading.Event] = None) -> Iterator[FrameKeypoints]:
    """영상 → 프레임별 관절 17개와 신뢰도. 원자료는 메모리에서만 쓰고 저장하지 않는다 (ERD D-08).

    on_frame(처리한 프레임 수, 전체 프레임 수)를 프레임마다 부르고, cancel이 켜지면 바로 멈춘다.
    수용 기준: AC-11 (모델 두 개로 같은 영상을 돌려 둘 다 결과가 나온다).
    """
    raise NotImplementedError("WP1")


def mask_face(frame, keypoints: FrameKeypoints, params: EngineParams):
    """프레임 → 얼굴(머리 상자)을 모자이크한 프레임.

    머리 점(코, 눈, 귀)이 안 보이면 직전 상자를 10프레임 유지하고 (TP-11), 그래도 없으면 프레임 전체를 흐리게 한다.
    화면, 대표 장면, 엑셀에는 이 결과만 쓴다 (BR-22). 수용 기준: AC-12 (150프레임 모두 가림, 프레임당 20ms).
    """
    raise NotImplementedError("WP1")
