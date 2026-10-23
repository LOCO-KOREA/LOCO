# MediaPipe Heavy / Full 구현 및 검증

2026-10-22, 별도 브랜치 `feat/mediapipe-heavy`, 기준 main `4cdd0d1f51ae000815418e3cfab88f2d7063edb8`. 이 문서는 현재 PC의 소스 실행과 검증 기록이다. 운영 배포나 새 portable 실행파일 배포를 뜻하지 않는다.

## 구현

- 기본값은 MediaPipe Pose Landmarker Heavy. Full과 과거 MoveNet Lightning도 동일한 provider 인터페이스에서 명시적으로 선택한다. `ergo/pose_contract.py`에 모델·SHA-256·환경변수·설정 필드·랜드마크·연결선을 정의하고 서비스와 두 설정 화면이 이 카탈로그를 소비한다.
- `ergo/pose/engine.py`는 이미지, 실제 모델 파일 지문, 출력 검증, 공통 2D 각도와 오류를 관리한다. `providers/mediapipe.py`는 MediaPipe Tasks IMAGE CPU 실행, `providers/movenet.py`는 과거 LiteRT 실행을 맡는다. 모델 누락·잘못된 해시·미검출을 다른 모델로 숨기지 않는다.
- MediaPipe의 33개 관절, visibility와 presence, 실제 모델 해시, 단안 추정 world 좌표를 저장한다. world 팔꿈치/무릎 각도는 화면과 Excel에서 별도 참고값으로 표시하고 기존 REBA 점수에 사용하지 않는다. confidence는 두 확률의 최솟값이며 MoveNet score와 같은 확률로 해석하지 않는다.
- 사진 자동 사실은 POSE 출처로 저장하며 과거 MOVENET도 읽는다. 엔진 변경은 사진 후보를 다시 계산하고 직접 입력값/모름은 보존한다. 실제 모델 파일 변경도 후보 및 분석 재사용 키에 반영한다. 이전 분석/출력 snapshot과 여섯 테이블은 재작성하지 않는다.
- `LOCO_POSE_MODEL_ID`, `LOCO_POSE_MODEL_PATH`, `LOCO_POSE_MODEL_SHA256`, `LOCO_POSE_CONFIDENCE_MIN`, `LOCO_POSE_DETECTION_MIN`, `LOCO_POSE_PRESENCE_MIN`이 초기값을 제공한다. 명시적으로 저장한 설정이 우선하며 과거 명시적 MoveNet 설정도 의미를 유지한다. 운영 승인/배포 차단 기능을 추가하지 않았다.
- 빌더와 portable smoke 소스도 카탈로그의 세 모델을 소비하도록 수정했다. 이 PC에서는 새 portable 패키지를 빌드하거나 실행하지 않았다.

## 실제 모델 및 환경

Python 새 가상환경: mediapipe 1.1.1, ai-edge-litert 2.3.0, opencv-contrib-python 5.0.0.93. Windows CPU 실행이며 원래 main 가상환경은 변경하지 않았다.

| 모델 | 공식 파일 바이트 | SHA-256 |
| --- | ---: | --- |
| Heavy | 30,664,242 | 64437af838a65d18e5ba7a0d39b465540069bc8aae8308de3e318aad31fcbc7b |
| Full | 9,398,198 | 5134a3aad27a58b93da0088d431f366da362b44e3ccfbe3462b3827a839011b1 |

`scripts/download_pose_models.py`에서 공식 고정 버전 파일을 내려받아 검증했다. 파일은 Git에 포함하지 않는다. 공식 계약: <https://ai.google.dev/edge/mediapipe/solutions/vision/pose_landmarker>.

## Heavy / Full 비교

`scripts/compare_pose_models.py`를 두 모델의 같은 입력과 기본 문턱에서 실행했다. MMPose의 공개 COCO 형식 테스트 fixture 4장, visible=2 관절이 6개 이상인 12개 인물 ROI, 정답 관절 164개를 사용했다. 정답 bbox에 여백을 더해 자른 입력이므로 자동 작업자 탐지 성능으로 해석하지 않는다. 원본 전체 사진 실행은 JSON의 별도 항목이다. 입력/정답 파일의 SHA-256도 고정했다.

| 지표 | Heavy | Full |
| --- | ---: | ---: |
| 인물 검출 | 11/12 | 11/12 |
| PCK: 원 bbox 대각선 10%, 미검출도 오답 분모에 포함 | 86.59% | 84.15% |
| 검출된 정답 관절 평균 위치 오차 | 7.50 px | 9.27 px |
| 두 모델이 공통으로 사용한 86개 2D 각도 평균 절대오차 | 7.55° | 7.10° |
| warm CPU 처리 중앙값, 각 입력 3회 | 63.72 ms | 28.71 ms |

이 표에서 Heavy는 관절 위치 오차가 작고 Full은 약 2.2배 빠르며 공통 2D 각도 오차도 조금 작다. 사용자가 지정한 Heavy를 기본으로 제공하고 Full을 즉시 선택 가능하게 했다. 동시 개발 작업이 있던 현재 PC의 처리 시간이므로 장치별 절대 성능을 보장하지 않는다. 소규모 일반 사진 결과를 산업현장·3D·가림·손가락 정확도로 확대하지 않는다.

현재 앱 작업의 등록 사진도 DB를 읽기 전용으로 열어 `scripts/compare_task_photos.py`로 비교했다. 등록 3장/고유 이미지 3장이다. 정답 좌표가 없어 두 모델의 검출·각도 차이만 기록하며 정확도 순위를 만들지 않는다. 원본 사용자 사진은 Git에 넣지 않는다.

비교 원본: `.local/pose-comparison/comparison.json`, `sources.json`, `task-photos.json`. 재현 입력: <https://github.com/open-mmlab/mmpose/tree/main/tests/data/coco>. 배포용 HTML에는 녹색 정답/빨간색 예측을 나란히 비교하는 12개 샘플과 출처/라이선스를 담았다.

## 실제 스택 및 Excel E2E

OS 마우스/키보드 입력을 사용하지 않았다. Playwright가 테스트 전용 Electron의 CDP에 연결했고 창은 화면 밖(x/y=-12000), 초점 불가로 실행했다. Python 서비스, 실제 SQLite DB, 실제 모델, 실제 외부 AI와 기존 Excel writer를 사용했다. 입력 진술은 합성 시험 자료이고 사진은 공개 fixture다.

- Heavy `.local/heavy-integrated-live/receipt.json`: 9개 통과, errors=[]
- Full `.local/full-integrated-live/receipt.json`: 9개 통과, errors=[]
- 각 실행은 해당 모델의 33개 pixel/world 관절, AI 입력 정리와 부족한 정보만 질문, 후속 진술, 직접 수정 420분 보존, 모름 처리, 재시작, 11개 기준 결과, 실제 AI 설명 적용/검토, Excel 생성과 재시작 복원을 검증했다. 실제 모델은 gpt-6-luna, reasoning effort xhigh이며 GENERATED 응답을 확인했다.
- `tests/verify_local_artifacts.py`로 두 실행의 실제 DB 여섯 테이블, 불변 계산/출력 snapshot, 저장한 AI/검토와 7개 Excel 시트의 의미상 값을 독립 대조했다.
- 두 실제 최종 workbook을 artifact_tool로 읽기 전용 import/inspect/render했다. 5개 핵심 입력값과 중량 조건 연결, 모델명 E12, 33개 관절 표기, REBA와 분리된 3D 각도를 확인하고 자세 시트 렌더를 검사했다. QA 과정에서 workbook을 다시 저장하지 않았다.
- 고급 화면 기존 전체 흐름 `.local/mediapipe-advanced-integrated/receipt.json`: 29개 통과. 독립 검증도 여섯 테이블/10개 분석/5개 Excel/8개 자세 결과를 확인했다.
- 두 설정 화면과 실제 서비스/재시작 `.local/ai-settings-1792652781588/receipt.json`: 5개 통과. Full 경로/해시 자동 전환, 문턱 저장, 고급 화면 Heavy 복원, 저장값 우선순위가 포함된다.

## 회귀 및 반례

- Python 전체 245개 통과, 현재 소스 실행 skip 없음. 새 엔진 계약/실제 모델 테스트 13개 포함.
- frontend 회귀 스크립트 14개 통과, production build 성공.
- API 계약 audit: 구현/문서 48개, renderer 41개 일치.
- 최초 구현 커밋 2e7d704에서 pose mutation 17개 모두 검출, 원본 control 통과. 이 추론/계약 소스는 아래 main 통합에서도 유지했다. 모델 파일을 복사하지 않는 disposable mutation 환경에서 실제 모델/공개 사진 의존 4개만 skip했다. presence 무시, Full 선택 무시, 3D를 REBA 입력으로 잘못 표기하는 변이를 검출했다.
- 최초 고급 E2E의 UI 재계산 완료 대기 부족, offline fallback 시험에 상속된 실제 API 키, 과거 confidence selector 문제를 수정하고 전체 29개를 다시 완료했다. 설정 저장 성공 표시가 선택 분석이 없는 경우 누락되던 실제 UI 문제도 수정하고 5개 설정 E2E로 확인했다.

## 띄운 앱과 남은 범위

검증한 별도 작업 트리의 앱 PID 38564을 `showInactive()`로 표시했다. 제목은 `LOCO · MediaPipe Heavy · feat/mediapipe-heavy`이며 표시 당시 focused=false다. 새 DB는 기존 main DB의 일관된 복제본 `.local/mediapipe-demo/loco.db`이고 기존 입력/사진/이력과 작성 중 값을 보존했다. 원래 main 앱/DB는 수정하지 않았다. 새 앱에서 Heavy 실제 SHA, 33개 관절/world 좌표, Luna/xhigh 실제 CONNECTED 응답을 확인했다. AI 팝업을 열어 두었다.

소스 실행과 위 검증 범위는 완료했다. 별도 PC, 새 portable 패키지, 설치된 Microsoft Excel 앱에서 열기, 산업현장 정답 영상/사진 및 3D 정답 정확도는 미검증이다. 사용자 지정 별도 브랜치의 변경이며 main 병합이나 운영 배포를 수행하지 않았다.

## 작업 중 변경된 main 통합

마지막 원격 확인에서 main이 `556ae54792a2cc1f542adacd1ca42d8732f42296`으로 변경되어 PDF 기능이 추가된 것을 확인했다. main 자체를 수정하지 않고 feature 브랜치에 해당 커밋을 통합했다. 정본의 MediaPipe/PDF 절을 모두 보존하고 프론트의 두 import, 양쪽 회귀 시험, MediaPipe와 PDF 의존성을 함께 유지해 11개 충돌 파일을 해결했다. 중복 cv2 배포 패키지는 추가하지 않았다.

최신 간편 화면은 PDF 미리보기가 기본이다. 기존 고급 Excel 출력 화면은 유지했으므로 위 두 실제 AI E2E는 최신 PDF 미리보기를 거쳐 고급 화면에서 실제 Excel을 저장하는 경로로 다시 검증했다. 고급 전체 흐름 29개와 Python 245개도 통합 후 재실행했다. Python 최초 재실행은 upstream PDF 시험 의존성 pdfplumber가 없어 실패했으며 requirements-test.txt에 고정해 설치한 뒤 전체 통과했다. 재현 명령: `.venv/Scripts/python.exe -m pip install -r requirements-test.txt`, `.venv/Scripts/python.exe -m unittest discover -s tests`, `npm --prefix frontend test`, `npm --prefix frontend run build`, `.venv/Scripts/python.exe scripts/audit_contract.py`.

최신 소스로 새 앱 프로세스를 다시 띄우면서 기존 feature 앱의 작성 중 값과 복제 DB/프로필을 보존했다. 새 main 통합에 관한 원격 PR은 사용자 사전 확인 없이 생성했던 #26을 닫았다. PR 생성/재오픈은 사용자의 승인을 기다린다.
