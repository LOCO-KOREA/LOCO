"""관절 추출 (WP1 · 기능정의서 F04-01 · API 계약서 5절).

MVP의 모델은 MoveNet Lightning (singlepose, TFLite float16 v4)이다 (2026-10-12 정욱 결정).
정욱님 PC의 `pose2` 폴더에 TensorFlow 공식 예제의 래퍼(`ml/movenet.py`)와 모델 파일(`movenet_lightning.tflite`, 4.8MB)이 있다.
모델 파일은 TF Hub `lite-model/movenet/singlepose/lightning/tflite/float16/4`에서 받는다 (pose2/download_models.py).

모델 사실 (pose2 예제 코드와 README에서 확인함)
- 입력 192×192 RGB uint8, 출력 [1, 1, 17, 3] = (y, x, 점수). 좌표는 모델에 넣은 자른 영역 기준 0~1이라 원본 사진 좌표로 되돌려야 한다.
- 한 사람만 낸다 (singlepose). 사진에 여러 사람이 있어도 한 명만 나오고 사람 수는 알 수 없다 → 촬영 안내로 막고, 결과 화면에서 사람이 확인한다.
- 사진마다 독립이다. 예제의 `detect(image, reset_crop_region=True)`로 이전 사진의 자르기 영역을 쓰지 않는다.
  (같은 사진을 두 번 돌려 자르기 영역을 다듬는 방법이 TF 예제에 있다. 정확도와 속도를 재서 정한다.)
- 점은 코, 눈 2, 귀 2, 어깨 2, 팔꿈치 2, 손목 2, 엉덩이 2, 무릎 2, 발목 2. 발끝·발뒤꿈치·손가락 점은 없다.
- 실행: Windows는 TensorFlow(`tf.lite.Interpreter`)를 쓴다. LiteRT(`ai-edge-litert`)는 Windows 바퀴가 없다 (pose2/requirements.txt).
- 속도 (i7-10700K, 4스레드, 2026-10-08 측정): 한 장 5.2ms. 사진 디코딩 시간은 따로다.

알려진 함정
- 폰 사진은 회전 정보(EXIF Orientation)가 있다. 읽을 때 반드시 똑바로 세운다 (`PIL.ImageOps.exif_transpose`).
  안 하면 옆으로 누운 사람을 모델이 그래도 찾아서 각도가 조용히 틀린다. Pillow는 한글 경로도 연다.
- 사진 속 사람이 작으면 192×192로 줄이는 과정에서 관절이 뭉개진다. 촬영 안내: 사람이 화면의 절반 이상을 차지하게 찍는다.
- 가려진 점은 점수가 낮게 나온다. TP-02(0.5)는 제안값이다. 예제는 자르기 판단에 0.2를 쓴다.
"""
from __future__ import annotations

from pathlib import Path

from .types import EngineParams, StillKeypoints


def extract_keypoints(still_id: int, image_path: Path, model_id: int, params: EngineParams) -> StillKeypoints:
    """사진 한 장 → 관절 17개와 신뢰도. 원자료는 메모리에서만 쓰고 저장하지 않는다 (ERD D-08).

    회전 정보를 적용해 똑바로 세운 사진에서 재고, 좌표는 그 사진의 가로·세로 비율(0~1)로 돌려준다.
    사진을 서비스가 한 장씩 돌리며 진행률(처리한 사진 ÷ 전체)과 취소를 다룬다.
    수용 기준: AC-11 (MoveNet Lightning으로 사진 한 장을 돌려 관절 17개가 나온다).
    """
    raise NotImplementedError("WP1")
