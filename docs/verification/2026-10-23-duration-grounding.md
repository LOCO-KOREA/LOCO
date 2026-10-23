# AI 작업시간 표현 누락 수정 · 2026-10-23

브랜치 `feat/mediapipe-heavy`, 수정 전 기준 `9cdec19`. 원격 main 통합과 별개인 숫자 근거 검증 수정이다. 사용자 앱·DB·마우스·키보드를 조작하지 않았다. PR/푸시/main 병합은 수행하지 않았다.

## 원인과 변경

`ergo/intake/grounding.py`의 합산은 특정 연결어 정규식에 맞아야 했고, 총/전체/괄호를 일괄 거부했다. 단일 수치 검증은 시간·분을 각각 비교해 `1시간 30분`을 90분으로 인정하지 못했다. `facts.merge_model`은 이를 `UNIT_OR_NUMBER_NOT_GROUNDED`로 탈락시켰으며 원문이 남아 있어도 실제 daily_work_min이 비어 재질문 대상이 됐다.

숫자 검증기는 특정 접속사에 의존하지 않고 복합 단위를 한 수량으로 읽는다. AI 응답의 선택 `calculation={operation,terms:[{quote,minutes}]}`를 공통 필드 계약의 derivations에서 생성하고, 원문·피연산자별 단위·중복 위치·합계를 독립 검증한다. 기존 계산 객체 없는 단순 나열도 읽는다. 별도 총합/괄호 환산이 섞인 원문에는 구조화한 피연산자를 사용한다. 예전 저장 fact와 ANALYSIS/EXPORT_LOG snapshot을 일괄 재작성하지 않는다.

`2시간(120분)`은 두 단위가 같을 때 한 피연산자로 인정하고 다르면 거부한다. `1시간 30분`을 60분/30분으로 부분 인용하거나 같은 원문 위치를 두 번 사용하지 못한다. 확정 총시간 옆에 다른 동작의 범위 시간이 있어도 서로 다른 사실로 읽는다. 겹침·포함·동시 작업·휴식·범위·다른 주기·부분 일정의 단순 합산은 계속 거부한다. USER 값과 모름의 기존 우선권, field 최대값, 11개 기준·REBA의 계산 경계는 유지한다.

## 실제 검증

- 신규 독립 회귀 `tests/test_intake_grounding.py` 12개 메서드: 연결어 변형/나열/총 머리말, 숫자·한글 수사·복합/반 단위, 실제 서비스/SQLite 재시작·재질문 제거·snapshot·USER 값 보존, strict schema, 잘못된 합계/환산·원문 위조·중복·부분 인용·겹침·휴식·주기·불완전 일정 반례를 검사했다. 수정 전 제보 표현과 schema 검증이 실패하는 것을 확인했다.
- 최종 Python 전체 **261개 통과**, skip 없음, 27.663초. 기존 실제 MediaPipe fixture 시험도 포함되지만 이번 live 작업시간 시험은 사진 추론을 요청하지 않았다.
- frontend 기존 14개 회귀와 build 통과. feature 기준 API 문서/구현 48개·renderer 41개 일치. 최신 원격 main의 크롭 API 2개가 아직 이 feature에 통합되지 않았다는 점과 구분한다.
- `scripts/verify_duration_grounding.py`의 최종 `.local/duration-grounding-release-20261023/receipt.json`: 실제 외부 **gpt-6-luna/xhigh** → Python 서비스 → 격리 SQLite → 재시작 → 실제 분석 snapshot → EXPORT_LOG snapshot → 실제 XLSX **4/4 통과**, errors=[]. `및`, 문장 나열, 총 머리말+괄호 환산은 480분, `한 시간 삼십분`은 90분이다. 실제 모델·effort·응답 ID를 확인했다. 입력한 값 시트의 단위 포함 셀과 저장값을 대조했다.

첫 live 시험에서 세 표현은 DB/파일에 올바르게 저장됐으나 검증 보조 코드가 Excel의 `480 분/일` 문자열을 순수 숫자와 비교해 실패했다. 실제 출력의 단위 포함 형식에 맞춰 검사했다. 같은 시험에서 괄호 환산을 포함한 AI 피연산자 인용이 실제로 탈락하는 추가 경계를 발견했고, 원 응답을 관측·보존한 뒤 같은 단위의 중복 표기를 한 번만 세도록 수정했다. 최종 전체 실행은 새 격리 폴더와 실제 외부 AI로 다시 수행했다.

## 재현

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -p test_intake_grounding.py
.\.venv\Scripts\python.exe -m unittest discover -s tests
# 실제 외부 AI 호출: 기존 환경에 OPENAI_API_KEY가 있을 때
$env:LOCO_LIVE_AI='1'
.\.venv\Scripts\python.exe scripts/verify_duration_grounding.py --directory .local/duration-proof-new-run --workers 2
```

live 도구는 기존 AI 설정의 모델·effort 기본값을 사용하며 LOCO_LIVE_MODEL/LOCO_LIVE_REASONING_EFFORT로 지정할 수 있다. 매 실행은 존재하지 않는 새 폴더를 사용한다. 실제 공급자 응답 관측은 합성 데이터의 응답과 근거만 기록하며 키를 기록하거나 응답을 바꾸지 않는다.

## 남은 경계

이번 범위는 저장 감사 AUD-04의 제보 표현과 숫자 근거 검증이다. 나머지 AUD-01/02/03/05/06/07/08은 수정하지 않았다. 모든 자연어 표현의 처리 성공을 입증한 시험이 아니며, 추출 모델이 근거를 제안하지 않거나 겹침·부분 일정이 불명확하면 기존 추가 확인이 필요하다. 최신 main의 질문 묶음/진행률/크롭/Excel UI와 결합한 Electron E2E, 사용자 작업의 소급 자동 재처리는 수행하지 않았다.
