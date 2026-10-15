# LOCO

현장 조사자가 근골격계 부담작업의 **11개 기준**에 대한 사실과 근거를 기록하고, 계산 초안을 검토하고, 개선 전후를 비교·출력하는 Windows 데스크톱 도구를 개발합니다.

사용자가 하루 노출시간·중량·힘·횟수를 입력하면 규칙 엔진이 기준별 초안을 계산합니다. 선택한 사진은 MoveNet으로 자세 후보를 얻어 조사자가 확인한 뒤 별도 REBA 평가에 사용합니다. GPT API는 계산 요약을 설명하고 추가 확인·개선안을 제안합니다. 조사자가 결론과 설명을 검토·적용합니다.

상자 들기도 다른 작업과 같은 일반 입력·가변 사진 흐름을 사용합니다. 11개 호는 서로 겹칠 수 있는 조건이며, 사진 11개 동작을 분류하는 모델이 아닙니다. 사진 비율로 하루 작업량을 추정하거나 GPT가 판정을 대신하는 구조를 사용하지 않습니다.

## 문서와 구현 상태

**설계 버전 2.0 / 개정일 2026-10-15 / 완성 목표 2026-10-23(Asia/Seoul).** 이 날짜는 개발 목표이며 구현 완료 선언이 아닙니다. 검토 기준 main e7b0cf1은 기존 상자 작업·15슬롯·저장 1.3 계약을 주로 구현합니다. 실제 GPT 연결·일반 작업 입력·2.0 출력은 아래 문서에 따라 개발할 대상입니다. 기존 1.3 분석·출력 자료는 보존해 읽습니다.

| 정본 | 내용 |
|---|---|
| [요구사항](docs/requirements.md) | 프로젝트 의의, 현재와 목표의 차이, 담당·일정·수용 기준 |
| [기능정의서](docs/기능정의서.md) | 11개 규칙·누락·REBA·GPT·검토·비교 |
| [화면설계서](docs/화면설계서.md) | 일반 입력·사진·결과·검토·출력 흐름 |
| [ERD 데이터 설계서](docs/ERD_데이터설계서.md) | 여섯 테이블·JSON·snapshot·버전 호환 |
| [DB 아키텍처 설계서](docs/DB아키텍처_설계서.md) | 공통 서비스·저장·비동기·배포 |
| [API 계약서](docs/API_계약서.md) | DTO 2.0·서비스 호출·출력 계약 |

[AGENTS.md](AGENTS.md)는 작업·검증 지침입니다. [frontend 안내](frontend/README.md)와 [desktop 샘플 안내](samples/desktop/README.md)는 현재 코드 실행과 목표 설계를 구분합니다.

## 현재 통합 코드 실행

Windows PowerShell에서 CPython 3.12 x64, Node.js/npm, MoveNet Lightning TFLite 파일을 준비합니다. 모델 파일은 Git에 포함하지 않습니다.

~~~powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-desktop.txt
npm --prefix frontend install
.\run-integrated.ps1 -PythonPath "$PWD\.venv\Scripts\python.exe" -ModelPath "C:\models\movenet_lightning.tflite"
~~~

모델 경로는 실제 파일 위치로 바꿉니다. 현재 루트 스크립트는 공통 Python 서비스 ergo/service/json_lines.py를 명시적으로 연결하며 DB 기본값은 frontend/.local/loco_frontend.db입니다. -DatabasePath로 바꿀 수 있습니다. frontend의 npm start만 실행하면 이전 adapter를 사용할 수 있으므로 위 통합 진입점을 사용합니다.

이 실행 방법은 현재 개발 코드를 위한 안내입니다. 2.0 전체 지원과 개발 도구가 필요 없는 배포본은 10월 23일 전달 목표이며, 실제 검증 기록 없이 완료로 표시하지 않습니다.

## 개발과 검증

담당은 김나리(화면·배포), 유서하(서비스·MoveNet·REBA·GPT), 한정욱(11개 기준·저장·출력·통합)입니다. 구조는 Electron → Python Application Service → 기능 모듈 → SQLite이며 여섯 테이블의 JSON 저장 구조를 유지합니다.

정상·실패·경계·누락·통합 사례와 독립 반례로 검증합니다. 기존 시험에도 폐기된 가정이 있을 수 있으므로 기대값부터 확인합니다. 완료 보고·초록 시험만으로 수용하지 않으며 남은 결함과 미검증 범위를 남깁니다. 상세 개발 계획과 10월 23일 전달물은 요구사항을 따릅니다.

법령 규칙의 고정 근거는 [고용노동부고시 제2020-12호](https://www.law.go.kr/admRulInfoP.do?admRulSeq=2100000185793)입니다. 계산 초안·조사자 결론·REBA·GPT 설명을 구분해 표시하며, 법정 조사 완료나 질환 진단을 자동 보증하지 않습니다.
