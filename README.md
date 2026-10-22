# LOCO 2.0

현장 조사자가 작업 조건과 11개 부담작업 기준의 근거를 기록하고, 계산 초안·좌우 REBA·설명을 검토해 저장·출력·개선 전후 비교를 수행하는 Windows 데스크톱 도구다. 상자 들기와 다른 작업은 같은 일반 작업·가변 사진 흐름을 사용한다. 사진 비율을 하루 노출량으로 환산하거나 GPT가 판정·점수를 변경하지 않는다.

정본은 [요구사항](docs/requirements.md), [기능정의서](docs/기능정의서.md), [화면설계서](docs/화면설계서.md), [ERD](docs/ERD_데이터설계서.md), [DB 아키텍처](docs/DB아키텍처_설계서.md), [API 계약서](docs/API_계약서.md)의 설계 2.0이다. 개정일은 2026-10-16, 목표일은 2026-10-23(Asia/Seoul)이다. 현재 구현과 실제 검증 범위는 [검증 대조표](docs/local-verification.md)를 따른다.

## 실행

Windows x64·CPython 3.12·Node.js/npm 환경에서 저장소 루트 기준으로 실행한다.

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-desktop.txt
npm.cmd --prefix frontend ci
.\scripts\download_movenet.ps1
.\run-integrated.ps1 -PythonPath "$PWD\.venv\Scripts\python.exe" -DatabasePath "$PWD\.local\my-loco.db"
```

`run-integrated.ps1`의 DB 기본값은 `frontend/.local/loco_frontend.db`다. 직접 Electron 실행과 포터블 실행은 `%LOCALAPPDATA%\LOCO\loco_demo.db`를 기본으로 사용한다. `LOCO_DB_PATH`나 `-DatabasePath`로 명시할 수 있다. 기존 DB를 자동 복사·병합하지 않는다. 원본 사진은 경로로 참조하므로 원본 파일을 보존한다.

실행 서비스는 `ergo/service/json_lines.py` 하나다. 낡은 가짜 서비스·별도 샘플 서버·프론트 저장 adapter·SVG 목업 실행 경로는 제거했다. 프론트는 네이티브 ES module이며 작업·사진·조사·분석 화면의 상태/표시/이벤트를 분리했다. Python 서비스·순수 계산·여섯 테이블 저장·보고서 모듈의 경계는 [모듈 지도](docs/module-map.md)를 따른다.

기존 1.3 입력은 읽기 adapter에서 메모리상 2.0 편집 DTO로 읽는다. 명시 저장 전에는 원문을 재작성하지 않고, 분석/출력 snapshot과 과거 설정·receipt는 보존한다. 자세한 범위는 [기존 자료 읽기 계약](docs/legacy-compatibility.md)을 따른다.

## GPT와 Windows 패키지

GPT를 사용할 때는 실행 환경의 `OPENAI_API_KEY`와 설정 화면의 사용 여부·실제 API 모델 ID를 직접 설정한다. 키는 renderer·SQLite·패키지에 저장하지 않는다. 설정 없음·실패·불완전 응답은 로컬 대체 설명으로 표시하고 계산과 기존 적용문을 보존한다. 로컬 HTTP fixture 성공은 외부 GPT 계정 성공과 구분한다.

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-build.txt
.\.venv\Scripts\python.exe scripts/build_windows.py
```

`dist/LOCO-2.0-windows-x64-<빌드시각>` 폴더 전체를 유지하고 `LOCO.exe`를 실행한다. Electron·고정 Python 서비스·공식 모델이 포함된다. 패키지에는 사용자 DB·사진·키를 복사하지 않는다. `실행안내.txt`와 `build-manifest.json`에 기본 DB·소스 커밋·미커밋 여부·실행 소스 해시·모델 해시를 기록한다. 빌드 경로는 `.local/latest-package.txt`에도 남는다.

## 검증

```powershell
.\.venv\Scripts\python.exe -B -m unittest discover -s tests
npm.cmd --prefix frontend test
npm.cmd --prefix frontend run build
.\.venv\Scripts\python.exe -B scripts/audit_contract.py
.\.venv\Scripts\python.exe -B docs_src/erd/build_and_test.py
.\.venv\Scripts\python.exe -B tests/mutation/run_mutations.py
npm.cmd --prefix frontend run test:electron
npm.cmd --prefix frontend run test:explanation
```

Electron 검증에는 공식 모델과 `.local/fixtures/tensorflow-movenet-example.jpeg`가 필요하다. 준비 명령·출처·검증 전용 SQLite·화면 캡처·유형별 Excel·최신 패키지 재현은 검증 대조표를 따른다. 실제 외부 GPT 계정, 깨끗한 별도 Windows PC, 사용자 1.3 DB 표본, 현장 시간 단축·의학적/법적 성과는 로컬 합성 검증으로 대체하지 않는다.

기본 판정은 NOT ACCEPTED다. 로컬 검증이 끝난 범위와 미검증 환경을 분리해 보고한다. 2026-10-16 후속 사용자 지시에 따라 현재 변경을 feat/loco-2.0-oct23 브랜치에만 커밋·push한다. main 반영·PR·병합·운영 배포는 수행하지 않는다. 검증 당시 실행 소스 해시는 [소스 manifest](docs/verification/2026-10-16-source-manifest.json)에 보존한다. DB·사진·모델·실행 패키지와 원본 로그는 로컬 자료로 유지한다.

## 적응형 추가 확인

사진·작업 설명에서 얻은 정보를 자동 저장하고 필요한 항목만 추가 질문하는 흐름은 [적응형 입력 계약](docs/adaptive-intake.md)을 따른다. 새 운영 승인/배포 차단 절차는 추가하지 않는다.
