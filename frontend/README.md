# LOCO Electron 프론트엔드와 시안

> 안내 개정 2.0 · 2026-10-16 · 완성 목표 2026-10-23(Asia/Seoul)

정식 설계는 [요구사항](../docs/requirements.md)·[화면설계서](../docs/화면설계서.md)·[API 계약서](../docs/API_계약서.md)다. 현재 브랜치는 조사유형, 작업장 상황, 작업조건, 근로자 참여, 익명 증상 응답, 11개 기준 입력·가변 사진·선택적 REBA·GPT 설명·조사자 검토·한글 출력·전후 비교를 연결하고 검증 중이다. 질환자 발생에 따른 수시조사에는 별지 1·2 기반 출력 시트를 추가한다. 상자 들기도 같은 일반 작업 화면을 사용한다.

설계 기준 main e7b0cf1은 1.3 코드였으며, 이 브랜치에서 일반 작업 입력과 2.0 분석 흐름을 구현 중이다. 기존 SVG·시안의 예시 점수와 진행률은 실제 분석 결과의 증거가 아니다.

## 현재 통합 코드 실행

저장소 루트에서 CPython 3.12 x64와 Node.js/npm을 준비한 뒤 실행한다. 모델은 제공된 공식 다운로드 스크립트가 버전과 SHA-256을 확인해 받는다.

~~~powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-desktop.txt
npm --prefix frontend ci
.\scripts\download_movenet.ps1
.\run-integrated.ps1 -PythonPath "$PWD\.venv\Scripts\python.exe"
~~~

모델은 `models/movenet_lightning.tflite`에 내려받으며 이 바이너리는 Git에서 제외한다. 다른 경로를 사용하면 -ModelPath를 지정한다. 통합 DB 기본은 frontend/.local/loco_frontend.db이며 -DatabasePath로 바꿀 수 있다. 기존 샘플 DB를 자동 복사/합치지 않는다.

electron/main.cjs는 기본으로 공통 서비스 ergo/service/json_lines.py를 실행한다. run-integrated.ps1은 서비스·Python·DB 경로를 명시적으로 전달하는 편의 진입점이며, 두 경로가 같은 Application Service를 사용한다.

## 현재 코드의 구성

| 경로 | 역할 |
|---|---|
| desktop.html / desktop.js / desktop.css | 실제 Electron 화면 진입점 |
| dashboard.js / dashboard.css | 조사 요약·목록 이동 |
| task-workspace.js / tasks.css | 작업·11개 기준 직접입력 화면 |
| survey-intake.js | 조사유형·상황·참여·증상 설문 입력 |
| photo-workspace.js / photos.css | 등록·배정·촬영 관찰·미리보기 |
| electron/main.cjs / preload.cjs | 파일 선택·Python JSON Lines·DesktopBridge |
| ergo/service/ | Electron과 연결되는 공통 Python JSON Lines 서비스 |
| index.html / app.js | 별도 SVG 인터랙티브 목업 |
| build-designs.cjs / serve.cjs | 원본 시안 사본 생성·정적 미리보기 |
| assets/fonts / fonts.css | 로컬 Pretendard 1.3.9 가변 WOFF2와 OFL 라이선스 |

일반 작업·11개 기준·가변 사진·조사 맥락·분석 이력·유형별 Excel 흐름은 로컬에서 통합 확인했다. 2026-10-16 검증은 CPython 3.11.9 전체 48개 시험, 5개 mutation과 대조군, 정적 프론트 빌드, Electron UI에서 SQLite 저장·실제 공식 MoveNet TFLite CPU 추론·6시트/4시트 Excel 생성을 통과했다. E2E 이미지와 조사 응답은 합성 자료다. 실제 GPT API 호출, CPython 3.12 x64, 사용 중인 1.3 DB 표본, 개발 환경 없는 Windows PC 설치와 조사자 현장 사용은 별도 검증이 필요하다. 별지 출력은 고시 서식 기반이며 원본 서식 대조·서명·전문가 검토 없이 법정 조사 완료를 뜻하지 않는다.

## 2.0 화면 흐름과 남은 검증

- 조사 맥락·참여·익명 증상응답, 일반 입력, 11개 기준, 사진 선택 분석, 조사자 검토, GPT 설명, 유형별 Excel 내보내기, 분석 이력과 비교는 공통 흐름에 연결되어 있다.
- 이 브랜치의 자동 시험은 기준 경계·누락·모순, 사진 소유권과 관찰 보존, GPT 근거 경계, 저장 revision, 출력 시트를 다룬다.
- 화면을 통한 실제 조작, 실제 GPT API 호출, 실제 사용 중인 1.3 DB 표본의 마이그레이션, 깨끗한 Windows PC 설치는 아직 확인해야 한다. MoveNet은 공식 모델로 CPU 추론 경로까지 확인했다.

사진 교체 시 확인값 초기화, 분석 저장 시 조사자 결론·설명 편집 보존, 기본 Electron 경로의 공통 서비스 연결은 회귀 시험 대상으로 추가했다. 표본 코드 fixture의 1.3 입력 읽기·명시적 편집 승격은 시험했지만 실제 사용 DB 재열기·Windows 3.12 설치·UI와 실제 API 상호작용 확인이 남아 있다. 세부 담당·일정·수용 기준은 요구사항을 따른다.

## 정적 시안 미리보기

저장소 루트에서 다음 두 명령을 차례로 실행한다.

~~~powershell
node frontend/build-designs.cjs
node frontend/serve.cjs
~~~

또는 frontend에서 npm run preview를 사용한다. 주소는 [시안 미리보기](http://127.0.0.1:4318/frontend/index.html)다. 실제 HTML 배치는 같은 서버의 /frontend/desktop.html에서 볼 수 있으나 브라우저에는 Electron 저장 브리지가 없다.

build-designs.cjs는 docs/ui의 기존 SVG 사본에 선택 로고·글꼴을 적용한다. 원본의 고정 사진·예시값은 이전 설계 참고 자료이며 2.0 요구를 덮어쓰지 않는다. 목업 편집은 메모리 전용으로 새로고침하면 사라진다.

## 검증과 배포

10/19 전체 흐름 통합, 10/20 출력/비교, 10/21 독립 검토, 10/22 개발 환경 없는 PC 실행, 10/23 전달을 목표로 한다. 입력 저장·재열기·null/0·혼합 중량·사진 0/1/여러 건·재연결·GPT 실패/편집·이전 결과 출력을 확인한다.

시험 지침은 [AGENTS.md](../AGENTS.md)를 따른다. 완료 보고·초록 시험을 주장으로 두고 변경 범위·실패 경로·경계·최소 반례를 독립 점검한다. 현재 자동 시험 결과만으로 실제 모델/API 사용이나 배포 완료를 보고하지 않는다.
