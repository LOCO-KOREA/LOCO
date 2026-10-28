# 자세 추론 엔진 계약

현재 기본 엔진은 MediaPipe Pose Landmarker Heavy이며 Full과 MoveNet Lightning은 같은 추론 인터페이스의 선택 가능한 provider/variant다. `backend/pose_contract.py`가 모델 목록·파일·해시·입력/출력 차원·랜드마크 이름·연결선·수치 설정·환경변수의 단일 정의다. 서비스/프론트/내보내기는 공급자를 직접 import하지 않고 이 계약을 소비한다.

`analysis.pose_model`은 model_id/provider/variant/name/version/preprocess_version/input_size/point_count/confidence_kind/model_path/model_sha256와 confidence_min/detection_min/presence_min을 포함한다. 선택 모델별 메타데이터는 registry에서 생성하며 수치·경로·해시는 설정할 수 있다. `get_settings.pose_contract={version,models,fields,defaults,landmarks,connections}`는 읽기 전용 메타데이터다. 환경변수 LOCO_POSE_MODEL_ID, LOCO_POSE_MODEL_PATH, LOCO_POSE_MODEL_SHA256, LOCO_POSE_CONFIDENCE_MIN, LOCO_POSE_DETECTION_MIN, LOCO_POSE_PRESENCE_MIN으로 초기값을 지정하고 저장된 명시값이 우선한다. 예전 MoveNet 설정은 그 엔진 의미를 유지해 읽고 이전 분석/출력 snapshot은 재작성하지 않는다.

공통 process(slot,snapshot)는 기존 points/angles/status/diagnostics를 유지하고 engine 메타데이터·world_points·quality를 추가한다. MediaPipe points는 33개 전체이며 공통 17관절은 이름으로 접근한다. 각 point는 원본 EXIF 보정 사진의 x_px/y_px, visibility/presence, 공급자별 confidence와 confidence_kind를 기록한다. MediaPipe confidence는 min(visibility,presence)이며 MoveNet score와 같은 통계량으로 해석하지 않는다. world_points는 골반 중심 단위 m의 단안 3D 추정값으로 저장하고 기존 REBA/11개 법정 계산에 그대로 대입하지 않는다. 3D 분절각은 기존 2D 각도와 좌표계를 구분한다. 현재 계산하는 유효한 팔꿈치·무릎 굽힘각은 현재 점수 초안의 같은 필드에서 3D를 우선 선택하고, 없으면 2D를 사용한다. 직접 확인한 값은 항상 우선하며 사람의 확정값으로 자동 승격하지 않는다. 실제 선택 근거를 AI·Excel·검토 화면까지 전달한다.

사진 자동 사실 출처는 POSE이며 과거 MOVENET 출처도 읽는다. 엔진 변경 시 이전 사진 후보를 무효화하고 USER 직접 값/모름은 보존한다. 실제 모델 파일 해시를 추론 결과에 남기며 파일/설정 변경은 캐시 키에서 구별한다. 모델 누락/잘못된 해시/미검출/잘못된 출력은 기존 진단으로 처리하고 다른 엔진으로 조용히 전환하지 않는다. 기존 여섯 테이블과 JSON 구조를 유지하며 운영 승인/배포 차단 기능을 만들지 않는다.

Heavy/Full은 동일한 공개 COCO 예제와 정답 관절 좌표로 비교한다. 정답 bbox로 자른 인물 입력과 원본 전체 사진을 구별한다. 관절 오차·PCK의 정규화와 실패 분모·각도 오차·처리 시간을 기록하며 confidence 개수로 정확도 순위를 매기지 않는다. 공개 일반 사진의 결과를 산업현장 정확도/임상 효과로 확대하지 않는다. 실제 Electron/Python/SQLite/MediaPipe/OpenAI/Excel E2E는 화면 밖·초점 불가 창에서 수행하며 OS 입력을 사용하지 않는다.
