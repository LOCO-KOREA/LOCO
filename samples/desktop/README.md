# LOCO 데스크톱 프로그램 샘플

2026-10-15 설계 v1.5를 읽고 만든 독립 샘플입니다. 팀원의 `docs/`, `ergo/`, `tests/` 파일은 수정하지 않습니다. 이 안내는 샘플 실행 설명이며 새 설계 기준 문서가 아닙니다. 계산 DTO와 보고서 버전은 1.3입니다.

## 실행

Node.js 22.12 이상/npm과 Python 3.12 x64를 사용할 수 있는 PowerShell에서 저장소 루트 기준:

```powershell
cd samples/desktop
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-inference.txt
.\start.ps1 -ModelPath 'C:\models\movenet_lightning_float16_v4.tflite'
```

`py -3.12` 명령을 사용할 수 없으면 설치된 Python 3.12 실행파일의 전체 경로로 가상환경을 만듭니다. `.venv`가 이미 준비되어 있다면 앞의 두 설치 명령은 반복할 필요가 없습니다. PowerShell 실행 정책 때문에 스크립트를 실행할 수 없다면 정책 변경 없이 다음 명령을 사용합니다.

```powershell
$env:LOCO_PYTHON = "$PWD\.venv\Scripts\python.exe"
$env:LOCO_MOVENET_MODEL = 'C:\models\movenet_lightning_float16_v4.tflite'
npm.cmd install --cache .npm-cache
npm.cmd start
```

사진은 실제 JPG/PNG를 등록하고 각 슬롯에서 직접 배정합니다. 등록 순서로 자동 확정하지 않습니다. 시작·종료는 실제 무하중인지, 들기 3순간은 실제 전체 중량 지지인지 각각 관찰값에서 기록합니다.

## 구현 범위

| 항목 | 샘플 코드 |
|---|---|
| Electron 실행 | renderer → preload → main → Python, UTF-8 JSON Lines, 파일 선택·끌어놓기 |
| S01–S03 | 조사·작업 CRUD, 조건·20개 직접시간·11기준 입력 |
| S04–S05 | 사진 등록·EXIF 미리보기·15슬롯 배정·촬영관찰·분석 진행/취소 |
| S06 | 원본 픽셀 관절 표시·각도·6후보, 공통/좌우 수동입력·선택사진/같은순간/개별 편집·REBA 표 A/B/C |
| S07 | 직접입력 11기준 초안·근거·조사자 결론·검토 표시 |
| S08 | 같은 overview 기반 미리보기·SUMMARY 14열·4시트 .xlsx·출력 로그 |
| S09 | 모델정보·로코 표시·조용한 모드 저장 |
| 로코 | 기존 `docs/ui/loco-guide.js`를 수정하지 않고 직접 로드 |
| 설명 | 외부 GPT 호출 없이 고정 대체 설명 생성·수정·적용 |

빈값은 null로 유지합니다. 사진 비율로 하루 시간을 만들지 않으며 미완전해도 저장·분석·검토·출력을 계속할 수 있습니다. 부분 최대/15장 전체 최대/수동 대표와 검토 상태는 별개입니다.

## 실제 MoveNet 연결

현재 전처리는 `EXIF_OPENCV_LETTERBOX_V2`입니다. Pillow에서 EXIF 방향 보정·RGB 변환 후, OpenCV로 원본 해상도에서 검은 정사각형 패딩을 추가하고 `INTER_LINEAR`로 192×192에 축소합니다. 홀수 여백의 남은 1픽셀은 오른쪽/아래에 배치합니다. 관절은 실제 패딩 크기로 원본 픽셀에 역변환하며 소수점을 유지합니다. OpenCV에 RGB 배열을 전달하므로 BGR 변환을 추가하지 않습니다.

이전 전처리 버전의 저장 분석은 그대로 남습니다. 새 실행에서 현재 전처리 버전을 설정에 반영하고 기존 작업의 입력 revision을 올리며, 이전 자동 후보 적용값(AUTO_ACCEPTED)만 비웁니다. 직접 관찰값은 유지합니다. 새 관절·각도가 필요하면 사진 분석을 다시 실행해야 합니다. 실행 중이던 앱은 완전히 종료하고 다시 열어 Python 코드와 설정을 함께 갱신합니다.

모델 파일과 가상환경은 Git에 포함하지 않습니다. `requirements-inference.txt`는 Python 3.12 x64와 LiteRT 2.3.0을 사용하는 추론 환경입니다. **singlepose Lightning TFLite float16 v4, 192×192** 모델 경로를 지정합니다.

```powershell
$env:LOCO_MOVENET_MODEL = 'C:\models\movenet_lightning_float16_v4.tflite'
.\start.ps1
```

샘플 어댑터는 `ai_edge_litert.interpreter.Interpreter`, 다음으로 TensorFlow의 Interpreter를 사용합니다. 모델·런타임이 없으면 해당 사진에 MODEL_ERROR를 반환합니다. 예시 관절이나 임의 점수를 성공 결과로 생성하지 않습니다.

Electron과 `start.ps1`은 샘플의 `.venv/Scripts/python.exe`를 우선 사용합니다. `LOCO_PYTHON`이나 `-PythonPath`로 별도 실행파일을 지정할 수도 있습니다. 모델은 `-ModelPath` 또는 `LOCO_MOVENET_MODEL`로 지정하며, 지정하지 않으면 샘플의 `models/movenet_lightning.tflite`가 있을 때 사용합니다. 실행 경로는 APP_SETTINGS/계산 DTO에 추가하지 않습니다.

2026-10-15 첫 연결 작업에서 이 PC의 Python 3.12 가상환경과 LiteRT 2.3.0으로 기존 `pose2/movenet_lightning.tflite`를 로드했습니다. 모델 입출력은 `[1,192,192,3]` uint8 / `[1,1,17,3]`이었습니다. 사용자 제공 `sample.jpg`(360×540)에서 17개 좌표를 추출했고, 16개가 신뢰도 0.5 이상이었습니다. 정확도·측면 촬영 적합성을 검증했다는 의미는 아닙니다.

제공 사진은 정측면의 바닥→선반 작업 사진이 아니므로 카메라 측면/앞쪽 방향·촬영 순간·하중을 미확인으로 유지했습니다. 좌표는 표시하되 각도는 null과 진단, 포즈는 INVALID/MISSING_CAMERA, REBA 총점은 null입니다. 빈 14슬롯과 함께 결과를 저장합니다. 샘플 DB에는 `첫 연결 확인 · 제공사진` 조사와 `관절 표시 연결 · 촬영 조건 미확인` 작업을 만들었습니다. 사진은 경로만 저장하고 원본을 수정하지 않았습니다.

## 데이터와 파일 경계

- 기존 팀 storage와 스키마를 import해서 사용하되, **DB는 이 폴더의 `loco_sample.db`로 분리**합니다. 공식 앱의 `%LOCALAPPDATA%\LOCO\loco_demo.db`를 기본으로 열지 않습니다.
- 필요하면 실행 전에 `LOCO_SAMPLE_DB`로 샘플 DB 경로를 지정할 수 있습니다. 기존 팀 DB를 지정하지 않는 것을 권장합니다.
- 원본 사진은 복사·삭제하지 않고 경로만 참조합니다. Excel은 사용자가 선택한 경로에 생성합니다.
- Python 프로세스는 한 개이며 추론은 백그라운드에서 수행합니다. HTTP 서버·포트·추가 테이블·승인 단계·설치 프로그램은 없습니다.
- 별도 HTML/CSS/JavaScript 화면을 사용합니다. 문서의 화면 언어 계약을 따르며 React 프로젝트로 변환하는 작업은 포함하지 않았습니다.

## 아직 남은 부분과 확인 수준

- Electron 의존성과 실행 파일을 설치하고 기본 제공 Python으로 앱을 실행했습니다. 화면에서 모든 기능을 순회하거나 계산 결과를 검증한 상태는 아닙니다.
- 제공 사진 한 장의 실제 추론과 DB 저장 결과는 확인했습니다. 실제 작업 사진 15장 및 화면 전체의 동작·계산 정확도는 확인하지 않았습니다.
- 외부 GPT API, 관절점 직접 드래그 편집, 상세 분석설정 편집 UI, 사진 경로 재연결 UI는 미연결입니다. 사진 경로/동의 업데이트 서비스는 있습니다.
- 기준·근거의 입력 UI와 Excel 상세 출력은 샘플 수준입니다. 9호 union 별도 근거·목 자세의 자세한 기록, 긴 셀의 최대 높이, 상세 결과 항목코드·서식은 팀 구현 시 문서와 추가 대조해야 합니다.
- 재사용 비교는 보수적으로 처리하므로 일부 관련 없는 입력 변경에도 다른 모듈을 미계산으로 남길 수 있습니다. 이전 수치를 최신으로 잘못 복사하지 않습니다.
- 팀 지침에 따라 테스트/검증 스크립트는 추가하거나 실행하지 않았습니다. 구현 코드는 기능 완료·계산 검증 완료의 증거가 아닙니다.

샘플을 정식 앱에 합치기 전에 담당자별로 renderer, Python 서비스/계산/report, 기존 storage 연결을 검토하세요. 기존 문서를 이 샘플에 맞춰 바꾸지 않습니다.
