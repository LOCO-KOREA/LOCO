# LOCO
### 작업 사진 기반 자세 분석과 조사 기록 지원

작업 사진과 설명으로 자세를 분석하고, 조사자가 결과를 검토해 Excel로 정리하는 Windows 데스크톱 앱입니다.

---

## 1. 프로젝트 개요

- **주제**: 작업 사진을 활용한 REBA 자세 평가와 근골격계부담작업 조사 지원
- **인원**: 3명
- **대상**: 작업 자세와 작업 조건을 확인하고 기록하는 현장 조사자
- **목적**: 사진, 작업 조건, 계산 근거, 검토 내용을 한곳에서 관리하고 보고서로 정리

사진에서 확인하기 어려운 작업시간·중량·횟수 등은 직접 입력합니다. 계산 결과와 AI 설명은 검토를 돕는 자료이며, 최종 판단은 조사자가 합니다.

---

## 2. 입력 데이터

| 입력 | 내용 |
|---|---|
| 작업 사진 | 왼쪽·정면 또는 후면·오른쪽 사진. 간편 화면에서는 한 장으로도 분석을 시작할 수 있습니다. |
| 작업 설명 | 작업 방법, 취급 물체, 반복 동작 등 사용자가 작성한 설명 |
| 작업 조건 | 작업시간, 중량, 힘, 반복 횟수 등 직접 확인한 값 |
| 검토 기록 | 측정값 수정, 조사자 의견, 확인해 확정한 결과 설명 |

고정된 학습 데이터셋으로 모델을 새로 학습하는 방식이 아니라, 사전 학습된 자세 모델로 사용자가 등록한 사진을 분석합니다. 사진의 자세 비율을 하루 작업시간이나 횟수로 환산하지 않습니다.

---

## 3. 기술 스택

### 화면과 데스크톱 앱

![Electron](https://img.shields.io/badge/Electron-47848F?style=for-the-badge&logo=electron&logoColor=white)
![JavaScript](https://img.shields.io/badge/JavaScript-F7DF1E?style=for-the-badge&logo=javascript&logoColor=black)
![HTML5](https://img.shields.io/badge/HTML5-E34F26?style=for-the-badge&logo=html5&logoColor=white)
![CSS](https://img.shields.io/badge/CSS-663399?style=for-the-badge&logo=css&logoColor=white)

### 자세 분석과 이미지 처리

![Python](https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white)
![MediaPipe](https://img.shields.io/badge/MediaPipe-0097A7?style=for-the-badge&logo=mediapipe&logoColor=white)
![NumPy](https://img.shields.io/badge/NumPy-013243?style=for-the-badge&logo=numpy&logoColor=white)
![OpenCV](https://img.shields.io/badge/OpenCV-5C3EE8?style=for-the-badge&logo=opencv&logoColor=white)
![Pillow](https://img.shields.io/badge/Pillow-3776AB?style=for-the-badge)

### 데이터 저장·보고서·AI

![SQLite](https://img.shields.io/badge/SQLite-003B57?style=for-the-badge&logo=sqlite&logoColor=white)
![openpyxl](https://img.shields.io/badge/openpyxl-217346?style=for-the-badge)
![OpenAI API](https://img.shields.io/badge/OpenAI_API-412991?style=for-the-badge)

---

## 4. 분석 과정

```text
사진·작업 설명 입력 → 자세 추정·정보 정리 → 필요한 값 보완 → 계산 → 조사자 검토 → Excel 출력
```

| 구성 | 역할 |
|---|---|
| MediaPipe | 사진의 관절 좌표와 자세 각도를 추정합니다. 기본 모델은 Pose Landmarker Heavy이며 33개 관절을 사용합니다. Full과 기존 MoveNet Lightning도 지원합니다. |
| 규칙 엔진 | 입력값과 자세 측정 결과로 REBA 점수와 11개 기준을 각각 계산합니다. |
| AI | 작업 설명에서 정보를 정리하고 사진 속 동작을 설명합니다. 계산 규칙을 실행하거나 점수를 직접 정하는 역할은 맡지 않습니다. |
| SQLite | 조사, 작업, 사진 정보, 분석 결과, 설정, 출력 이력을 저장합니다. |

현재 점수에는 확인하지 못한 값을 가정한 점수가 포함될 수 있습니다. 화면의 가정 항목과 측정 상태를 함께 확인해야 합니다. 비교용 기준값을 표시하는 경우에는 자세를 측정해 얻은 점수와 구분해 안내합니다.

관절 각도는 2D 측정과 3D 추정을 구분합니다. 팔꿈치·무릎 굽힘은 유효한 3D 추정값을 우선 사용하고, 없으면 2D 값을 사용합니다. 직접 확인한 값은 자동 측정값보다 우선합니다. 3D 좌표도 사진 한 장에서 추정한 값이므로 실제 공간을 계측한 결과로 볼 수는 없습니다.

---

## 5. 주요 기능

| 기능 | 내용 |
|---|---|
| 사진 등록·크롭 | 사진에서 분석할 영역을 선택하고 방향별로 등록 |
| 관절·각도 표시 | 관절과 자세 각도를 사진 위에 표시하고 측정 근거 확인 |
| REBA 계산 | 자세와 하중 등 입력을 반영한 점수 및 위험 수준 확인 |
| 11개 기준 계산 | 작업 조건별 계산 초안과 부족한 입력 확인 |
| AI 정보 정리·설명 | 작업 설명과 사진 속 동작을 정리하고 계산 결과 설명 |
| 검토·Excel 출력 | 설명 편집·확정, 저장한 입력과 계산 결과 출력 |
| 기록 관리 | 임시 저장·이어쓰기, 기존 기록 재열기, 개선 전후 분석 비교 |

### 사용 순서

1. 홈에서 **새 분석 시작**을 누릅니다.
2. 작업 사진을 선택하고 사용할 영역을 자른 뒤 작업 내용을 적습니다. 간편 화면에는 왼쪽·정면 또는 후면·오른쪽 사진을 등록할 수 있습니다. 사진 한 장으로도 시작할 수 있습니다.
3. **사진·작업 설명 정리**를 누릅니다. 사진의 자세를 먼저 측정하고, AI가 작업 설명과 사진 속 동작을 정리합니다.
4. 현재 점수와 측정 근거를 확인합니다. 부족한 정보를 추가하려면 **점수 보완(선택)**을 누릅니다. 질문창은 자동으로 열리지 않습니다.
5. 결과 화면에서 REBA 점수와 11개 기준의 계산 결과를 검토합니다. **결과 설명 확인**에서는 설명을 고치거나 자세 분석값을 수정할 수 있습니다.
6. **Excel 미리보기**로 내용을 확인한 뒤 저장합니다. 결과 설명은 사용자가 확인해 확정한 문장만 현재 분석의 Excel에 포함됩니다.

간편 화면에서 작성하던 내용은 임시 저장 후 이어서 열 수 있습니다. 조사·작업별 상세 입력과 기록 관리는 **고급 편집**에서 진행합니다.

---

## 6. 설치와 실행

### 개발 환경 설치

개발 환경은 Windows x64, CPython 3.12, Node.js/npm입니다. 아래 명령은 저장소 루트의 PowerShell에서 실행합니다.

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-desktop.txt
npm.cmd --prefix frontend ci
.\.venv\Scripts\python.exe scripts/download_pose_models.py
```

모델 다운로드 명령은 MediaPipe Heavy와 Full을 `models/`에 저장하고 파일 해시를 확인합니다. 모델 파일은 Git에 포함되지 않습니다.

기존 DB를 열면 그 DB에 저장된 모델 설정이 적용됩니다. MediaPipe 파일을 내려받는 것만으로 기존 MoveNet 설정이나 과거 분석 결과가 바뀌지는 않습니다.

### 앱 실행

```powershell
.\run-integrated.ps1 -PythonPath "$PWD\.venv\Scripts\python.exe" -DatabasePath "$PWD\.local\loco.db"
```

위 명령은 `.local/loco.db`를 사용합니다. 기존 기록을 열려면 `-DatabasePath`에 사용 중인 DB 경로를 지정하세요. 지정한 파일이 없으면 빈 DB를 만듭니다. DB를 선택하는 작업과 기존 데이터를 복사·병합하는 작업은 별개입니다.

DB 경로를 생략했을 때의 기본값은 실행 방식에 따라 다릅니다.

| 실행 방식 | 기본 DB |
|---|---|
| `run-integrated.ps1` | 저장소의 `frontend/.local/loco_frontend.db` |
| 직접 Electron 실행 또는 포터블 앱 | `%LOCALAPPDATA%\LOCO\loco_demo.db` |

실행 중인 앱이 사용하는 DB는 **데이터 저장 위치**에서 확인할 수 있습니다. 다른 PC로 기록을 옮길 때는 DB와 함께 사진 파일도 보존해야 합니다. 사진은 파일 경로로 참조합니다.

### AI 연결

AI 기능을 사용하려면 앱을 실행할 PowerShell 창에 API 키를 설정합니다.

```powershell
$env:OPENAI_API_KEY = '발급받은 API 키'
.\run-integrated.ps1 -PythonPath "$PWD\.venv\Scripts\python.exe" -DatabasePath "$PWD\.local\loco.db"
```

기본 AI 모델은 `gpt-6-luna`, 추론 강도는 `high`입니다. `LOCO_AI_MODEL`과 `LOCO_AI_REASONING_EFFORT`로 초기값을 지정할 수 있으며, DB에 저장된 설정이 있으면 그 값을 사용합니다. OpenAI 호환 서버를 쓰는 경우에는 `OPENAI_BASE_URL`을 지정합니다.

작업 사진을 AI가 설명하는 기능은 사진을 외부 API로 전송합니다. API 키는 실행 환경에서 읽으며 앱 화면, DB, 배포 패키지에 저장하지 않습니다.

AI 연결이 없거나 실패해도 직접 입력과 규칙 기반 계산을 이용할 수 있습니다. 현재 AI 요청에는 별도의 시간 제한과 자동 재시도가 없습니다. 응답 시간은 모델과 연결 상태에 따라 달라지며, 처리 중 같은 요청을 자동으로 다시 보내지 않습니다.

---

## 7. 저장과 출력

- 작업 입력과 분석 결과는 선택한 SQLite DB에 저장합니다. 작성 중인 미전송 문장과 화면 복구 정보는 이 PC의 로컬 초안에 보관합니다.
- 계산 당시의 입력과 설정은 분석별 snapshot으로 남깁니다. 입력이나 모델 설정을 바꿔도 과거 분석을 새 값으로 덮어쓰지 않습니다.
- Excel에는 저장한 입력, 계산 결과, 확인해 확정한 설명을 정리합니다. 개선 전후 분석을 선택해 비교할 수 있습니다.
- 사용자 출력은 Excel입니다. 저장소의 PDF 모듈은 내부 호환용이며 화면의 출력 기능으로 제공하지 않습니다.

---

## 8. 한계와 개선 방향

- **사진의 가림과 촬영 방향**: 보이지 않는 관절이나 낮은 신뢰도의 측정값은 직접 확인이 필요합니다.
- **3D 추정의 한계**: 사진에서 추정한 좌표는 실제 공간을 계측한 값과 다를 수 있습니다.
- **입력 누락과 가정**: 화면 점수에 가정이 포함될 수 있으므로 측정 상태와 가정 항목을 함께 확인해야 합니다.
- **현장 검증**: 실제 조사자의 사용성과 측정 정확도, 작성 시간 단축 효과는 별도 검증이 필요합니다.

개선 과제는 촬영 조건별 측정 검증, 조사자의 사용성 평가, 별도 Windows PC에서의 실행·출력 확인입니다. 시험 수치나 시연 화면은 해당 기록의 날짜와 조건을 함께 확인해야 합니다.


---

## 9. 역할 분담

| 이름 | 담당 영역 |
|---|---|
| 김나리 | 일반 입력·사진·검토 화면, Electron 배포 |
| 유서하 | Application Service, 자세 추론·REBA·GPT 연동 |
| 한정욱 | 11개 기준, 저장·출력, 개선 전후 비교, 통합 총괄 |


---

## 10. 프로젝트 구조

```text
Electron 화면 → preload/main → Python 서비스 → 분석·저장·출력 모듈
```

| 경로 | 내용 |
|---|---|
| `frontend/` | Electron 앱과 화면 코드 |
| `ergo/service/` | 화면 요청 처리와 기능 연결 |
| `ergo/pose/` | MediaPipe·MoveNet 추론 |
| `ergo/engine/` | 관절 각도, REBA, 11개 기준 계산 |
| `ergo/intake/`, `ergo/vision/`, `ergo/gpt/` | 작업 설명 정리, 사진 관찰, 결과 설명 |
| `ergo/db/`, `ergo/report/` | SQLite 저장과 보고서 출력 |
| `tests/`, `scripts/` | 검증 코드, 모델 다운로드, 패키지 빌드 |
| `docs/` | 설계 문서, 검증 기록, 발표 자료 |

서비스 진입점은 `ergo/service/json_lines.py`입니다. 화면은 이 서비스에 요청을 보내며, 계산은 Python 기능 모듈에서 수행합니다. SQLite의 여섯 테이블은 `SURVEY`, `TASK`, `PHOTO`, `ANALYSIS`, `APP_SETTINGS`, `EXPORT_LOG`입니다.

---

## 11. 개발자 검증과 패키지 빌드

```powershell
.\.venv\Scripts\python.exe -B -m unittest discover -s tests
npm.cmd --prefix frontend test
npm.cmd --prefix frontend run build
```

`build` 명령은 화면에서 사용하는 파일과 JavaScript 문법을 검사합니다. 실행 패키지를 만드는 명령은 아닙니다.

Electron 통합 시험, 실제 외부 AI 시험, 출력 파일 대조 방법은 [프런트엔드 실행·검증 안내](frontend/README.md)와 [검증 기록](docs/local-verification.md)을 참고하세요. 실제 외부 AI 시험에는 별도 키와 실행 설정이 필요합니다. 로컬 모의 응답으로 통과한 시험과 외부 AI를 호출한 시험은 구분해 기록합니다.

### Windows 실행 패키지

패키지를 빌드하려면 등록된 세 모델을 모두 준비해야 합니다.

```powershell
.\.venv\Scripts\python.exe scripts/download_pose_models.py mediapipe-heavy mediapipe-full movenet-lightning
.\.venv\Scripts\python.exe -m pip install -r requirements-build.txt
.\.venv\Scripts\python.exe scripts/build_windows.py
```

결과물은 `dist/LOCO-2.0-windows-x64-<빌드시각>`에 생성됩니다. 폴더 전체를 유지한 채 `LOCO.exe`를 실행합니다. 사용자 DB·사진·API 키는 패키지에 포함하지 않습니다. 빌드 정보와 모델 해시는 패키지의 `build-manifest.json`에서 확인할 수 있습니다.

---

## 12. 참고 자료

| 문서 | 내용 |
|---|---|
| [요구사항](docs/requirements.md) · [기능정의서](docs/기능정의서.md) · [화면설계서](docs/화면설계서.md) | 기능과 화면 설계 |
| [ERD](docs/ERD_데이터설계서.md) · [DB 설계](docs/DB아키텍처_설계서.md) · [API 계약](docs/API_계약서.md) | 데이터와 서비스 계약 |
| [자세 엔진](docs/pose-engine.md) · [사진 관찰](docs/photo-vision.md) · [추가 확인 입력](docs/adaptive-intake.md) | 모델과 입력 처리 방식 |
| [모듈 지도](docs/module-map.md) · [기존 자료 호환](docs/legacy-compatibility.md) | 코드 구조와 과거 데이터 읽기 |
| [발표 자료](docs/presentation/LOCO-발표.pptx) · [시연 시나리오](docs/presentation/demo/시연-시나리오.md) | 발표·시연 준비 |
| [시험 사실 기록](docs/presentation/TEST_FACTS.md) · [사진 출처](docs/presentation/assets/PHOTO_CREDITS.md) | 당시 검증 범위와 사용 사진 출처 |
