# LOCO Electron 프론트엔드와 시안

> 안내 개정 2.0 · 2026-10-15 · 완성 목표 2026-10-23(Asia/Seoul)

정식 설계는 [요구사항](../docs/requirements.md)·[화면설계서](../docs/화면설계서.md)·[API 계약서](../docs/API_계약서.md)다. 새 목표는 모든 작업에서 11개 기준 입력·가변 사진·선택적 REBA·GPT 설명·조사자 검토·한글 출력·전후 비교를 연결하는 것이다. 상자 들기도 같은 일반 작업 화면을 사용한다.

이 안내를 고쳤다고 앱이 2.0을 지원하는 것은 아니다. 기준 main e7b0cf1의 화면에는 기존 상자 작업/고정 사진 전제가 남아 있다. 기존 SVG·시안의 예시 점수와 진행률도 실제 분석 결과의 증거가 아니다.

## 현재 통합 코드 실행

저장소 루트에서 CPython 3.12 x64, Node.js/npm, MoveNet Lightning TFLite 파일을 준비한 뒤 실행한다.

~~~powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-desktop.txt
npm --prefix frontend install
.\run-integrated.ps1 -PythonPath "$PWD\.venv\Scripts\python.exe" -ModelPath "C:\models\movenet_lightning.tflite"
~~~

모델 파일은 별도로 준비하고 경로를 실제 위치로 바꾼다. 통합 DB 기본은 frontend/.local/loco_frontend.db이며 -DatabasePath로 바꿀 수 있다. 기존 샘플 DB를 자동 복사/합치지 않는다.

run-integrated.ps1이 frontend/start.ps1에 공통 서비스 ergo/service/json_lines.py를 전달한다. frontend의 npm start만 실행하면 electron/main.cjs의 이전 service/survey_service.py adapter를 사용할 수 있다. 두 경로는 지원 메서드가 다르므로 새 통합 구현은 공통 서비스 기준으로 진행한다.

## 현재 코드의 구성

| 경로 | 역할 |
|---|---|
| desktop.html / desktop.js / desktop.css | 실제 Electron 화면 진입점 |
| dashboard.js / dashboard.css | 조사 요약·목록 이동 |
| task-workspace.js / tasks.css | 작업·11개 기준 직접입력 화면 |
| photo-workspace.js / photos.css | 등록·배정·촬영 관찰·미리보기 |
| electron/main.cjs / preload.cjs | 파일 선택·Python JSON Lines·DesktopBridge |
| service/ | 이전 프론트 저장용 adapter |
| index.html / app.js | 별도 SVG 인터랙티브 목업 |
| build-designs.cjs / serve.cjs | 원본 시안 사본 생성·정적 미리보기 |
| assets/fonts / fonts.css | 로컬 Pretendard 1.3.9 가변 WOFF2와 OFL 라이선스 |

조사/작업 저장·사진 입력 코드는 있지만 전체 2.0 흐름의 실행 검증을 뜻하지 않는다. 이전 개발 보고의 검증 주장은 해당 커밋·환경의 기록으로만 보고, 이번 변경에서 앱을 다시 실행해 확인한 것으로 인용하지 않는다.

## 2.0 화면 구현 과제

- 모든 작업을 GENERAL_TASK로 입력하고 템플릿은 질문 순서에만 사용한다. 1~5호 시간 15종과 6~11호 조건 행·망라성·직접 합집합을 편집한다.
- 상자 들기를 포함해 사진 0..N개를 선택한다. 신규 화면에서 15장·회차·순간·자동 하중을 제거한다. 사진별 관찰 하중·촬영조건을 사용한다.
- 기본은 11개 기준 직접입력이다. 사진/기술태그/REBA의 요청·미요청·미완성 상태와 분모 N을 표시한다.
- 후보 적용과 직접 확인을 구분하고 목/손목/쥐기/충격/활동은 확인값으로 입력한다.
- 계산 초안·조사자 결론·GPT 생성/수정/적용본을 분리하고 이전 입력 결과·이전 설명을 표시한다.
- 한글 4시트 미리보기와 첫 다음 입력, 과거 분석 선택, 전후 비교를 공통 overview에 연결한다.
- 1.3 자료는 당시 버전으로 읽고 명시적 편집 저장부터 새 계약을 적용한다.

동일 사진 재연결의 관찰 보존, 분석 완료의 AI 편집 덮어쓰기, 기본 adapter와 통합 서비스 차이는 우선 확인 항목이다. 세부 담당·일정·수용 기준은 요구사항을 따른다.

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

시험 금지 지침은 [AGENTS.md](../AGENTS.md)에서 폐기했다. 기존 시험도 새 계약과 맞는지 검토하고 경계·실패·반례를 잡는 검증을 수행한다. 현재 문서 변경만으로 시험 통과·배포 완료를 보고하지 않는다.
