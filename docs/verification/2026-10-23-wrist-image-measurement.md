# 손목 2D 측정과 저장·질문 연결

기준은 `696f45792c8aa229f4652d6eaddb76e3deb22e7e`이며 별도 `fix/wrist-flexion-20261023`에서 작업한다. 사용자 원본 사진·기존 DB·과거 snapshot은 수정하거나 외부로 보내지 않는다. 여섯 SQLite 테이블 및 기존 `manual.LEFT/RIGHT.wrist_base`의 1/2 범주를 그대로 쓴다.

## 근거와 정확성 범위

Google의 [Pose Landmarker 개요](https://developers.google.com/edge/mediapipe/solutions/vision/pose_landmarker)에는 33점의 elbow/wrist/index/pinky/thumb가 명시되어 있고, [Python 결과 설명](https://developers.google.com/edge/mediapipe/solutions/vision/pose_landmarker/python#handle_and_display_results)은 image 좌표·추정 world 좌표·가시성을 구분한다. 이 구현은 EXIF 보정 원본의 x/y만 사용한다. Cornell의 [REBA 교육 자료](https://www.ergo.human.cornell.edu/studentdownloads/DEA4700pdfs/jsirebarula.pdf), 20쪽의 손목 굽힘·폄 15° 범주와 별도 편위·비틀림 보정은 기존 앱 계약과 일치하며 이번 작업에서 점수표를 바꾸지 않는다.

2D elbow-wrist-index 하나만으로 굽힘과 옆꺾임을 구분할 수 없다. 관절 confidence도 손 회전평면의 증명이 아니다. 따라서 근접 측면·가시성/presence·프레임·투영 길이·손 횡폭과 축 일치도·픽셀 변화 민감도를 별도 정책으로 검사한다. 이 정책은 관측가능성을 보수적으로 선별하는 heuristic이다. 조건 통과나 합성 시험 통과가 실제 사람의 해부학적 각도 정확도를 검증했다는 뜻은 아니다. 현재 표본에서 적격 사진이 없으면 그 사실을 그대로 보고하며 문턱을 완화해 성공시키지 않는다.

## 계약과 경로

`pose_contract.WRIST_JOINTS/WRIST_POLICY/WRIST_REASONS`가 공급자 관절·분류 경계/여유·관측 조건·한국어 이유의 정본이다. 정책은 새 `pose_artifact.wrist_policy`와 결과 angle의 `measurement.policy`에 보관된다. 새 `WRIST_FLEX_2D`는 원본 2D 크기각이며 굽힘·폄을 구분한 부호나 편위·회전값으로 사용하지 않는다. MoveNet은 손끝이 없으므로 손목 각도 행을 만들지 않는다.

관측 조건을 통과한 값은 기존 REBA candidate → quick measured → POSE fact → 사진 상황 확인 후 AUTO_ACCEPTED manual → 분석/Excel 경로를 사용한다. 15° 이하 1 / 초과 2, 경계 ±5°는 기존 기준을 유지한다. 경계는 ESTIMATED이며 자동 manual값으로 확정하지 않는다. 가림·프레임 밖·짧은 투영·손바닥 방향·불안정은 UNKNOWN과 구체 진단을 남기고 해당 질문에서 한국어로 이유를 보여 준다. AI의 일반적인 이유로 이 진단을 덮지 않는다. 편위/비틀림은 굽힘과 별도라는 문구로 확인하며 자동 NO를 만들지 않는다. USER 직접 값·직접 모름은 사진 제안보다 우선한다.

`preview.views[view].angles`는 측정과 진단을 보관하고 `preview.measurement_issues`의 `{scope,field,view,angle,reason,code}`는 미측정 이유를 사실 기록으로 옮긴다. fact의 선택 필드 `measurement_diagnostic` 및 `angles[].measurement`는 기존 JSON 확장이며 물리 migration은 없다. 사진별 provenance 연결은 별도 통합 작업과 함께 검증한다.

## 검증 구분

`tests/test_wrist_measurement.py`는 합성 픽셀 좌표의 범주 경계·가림·프레임·손바닥 정면·짧고 불안정한 투영·직접 값 우선·3D 미사용·MoveNet 호환·정확한 재질문 이유를 검사한다. 공급자 경계에만 합성 landmark를 주입하는 서비스→실제 SQLite→분석/Excel 시험은 연결 검증이며 실제 MediaPipe 정확도 시험과 구별한다. 실제 모델 표본에서는 원본 좌표·confidence·선택 조건과 거부 이유를 별도 증거에 보관한다. 성공한 모델 표본이 없으면 자동 측정 정확성 검증을 완료로 표시하지 않는다.

`tests/wrist_measurement_e2e.py --directory <새 증거 폴더>`는 실제 서비스 API/SQLite/분석/Excel에 공급자 infer만 합성 좌표로 대체한 성공 및 저품질 사례를 실행한다. 성공 사례의 `입력한 값!C15:F15`는 왼쪽 손목 꺾임 / 15° 넘게 / 사진에서 자동 채택 / 사진에서 잰 각도 30.0°다. 기존 source/수동값·사진 ID·분석/출력 snapshot을 대조하고 직접 수정 후 이전 분석 불변도 확인한다. 실제 모델 사례는 infer를 대체하지 않고 공개 TensorFlow 사진에서 사선 관측 거부와 구체 한국어 이유를 확인한다. 합성 저품질·실제 사진 모두 intake_session 세 번 조회 전후 input_revision 및 input_json 바이트가 완전히 같아야 한다. 동일 UNKNOWN 원인·측정·정책·모델·사진 소유권이면 기존 fact 시각을 유지하고, 바뀐 관측에만 새 근거를 만든다.

추가 음성 회귀는 12000px 사진의 픽셀 민감도 변화가 팔꿈치와 손목을 일치시키는 경우다. 손목만 WRIST_UNSTABLE로 거부하며 다른 관절·각도를 MODEL_ERROR로 지우지 않는다. 비유한 민감도 결과도 같은 원칙을 따른다.

독립 worktree에서 관련 Python 109개(실제 Heavy/Full 포함), frontend 전체 시험과 build를 통과했다. 연결 E2E 증거는 `.local/wrist-api-db-excel-r2/receipt.json`과 `synthetic/wrist.xlsx`이며, 원본 3장별 실제 모델 거부·조회 불변 증거는 `.local/wrist-original2-read-r1`, `wrist-original3-read-r1`, `wrist-original4-read-r1`의 `receipt.json`이다. 공급자 주입은 synthetic 사례에서만 사용했고 real-model 사례는 원본 읽기 사본에 실제 Heavy를 실행했다. 세 사진은 각각 손끝 가시성 부족 또는 넓게 보이는 손바닥면 때문에 거부됐으며, 표본에서 실제 모델의 손목 자동 측정 성공은 확인하지 못했다. 공개 COCO 사람 crop 12장과 기존 TensorFlow 예제도 가림·작은 투영·사선 관측으로 이 보수적 정책을 통과하지 못했다. 이 기록을 성공한 모델 정확도 검증으로 합산하지 않는다.
