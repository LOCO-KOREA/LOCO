# 사진·REBA·Human in the Loop·Excel 인계 (2026-10-24)

이 문서는 현재 작업 상태와 검증 경계를 넘기기 위한 handoff다. 기능 요구사항의 정본은 `docs/requirements.md`, `docs/기능정의서.md`, `docs/화면설계서.md`, `docs/API_계약서.md` 및 데이터 설계 문서다. 이 handoff는 그 문서들을 대체하지 않는다.

## Git 및 작업 위치

- 작업 폴더: `C:\Users\금정산2-PC02\Documents\LOCO-origin-main-run-20261024`
- 원격 기준: `origin/main` = `450709556a6743965a3a63ba738d371babf87b2a` (push 직전 원격 조회로 확인)
- 작업 브랜치: `codex/loco-photo-reba-excel-hil`
- 코드 커밋: `73607b56abb29e77be09b3af0c8c5918e5d09426` — 69개 파일 변경, 원격 push 확인
- PR은 만들지 않았다. `main` 병합·배포도 하지 않았다.
- 코드 커밋 직후 작업 트리는 깨끗했다. handoff 문서는 별도 후속 변경이다.

## 사용자 목표와 기대 동작

1. 사진 분석과 AI 설명 응답을 개선한다. AI 요청에 임의의 짧은 hard timeout을 두지 않는다.
2. REBA 1차 계산 점수와 최종 AI 설명을 같은 분석 결과에서 구분해 보여준다. AI가 REBA 점수나 판정을 계산·변경하지 않는다.
3. 질문을 최소화하고 Excel 양식에서 불필요한 입력 칸을 줄인다. 묻지 않은 항목을 `입력되지 않음`으로 출력하지 않는다. 출력은 실제 조사자 응답, AI·MediaPipe가 확인한 내용, 조사자가 확정한 결과로 한정한다.
4. 5단계는 Human in the loop 검토다. AI·MediaPipe·REBA의 결과와 불확실성을 설명하고, 조사자가 설명을 편집·확정한 뒤 Excel에 그 확정값을 내보낸다.

사용자는 실제 실행에서 `FILE_ERROR: 'InputTrace' object has no attribute 'criterion_presence_recorded'`와, 직접 답했다고 한 내용이 빠졌다는 요약을 보고했다. 사용자는 질문을 더 많이 받는 것도 문제로 지적했다.

## 이번 코드 커밋에 들어간 변경

- AI 호출용 공유 클라이언트를 추가하고 SDK 요청 timeout을 무제한으로 설정했으며 SDK 자동 재시도는 끄도록 바꿨다. 기존 timeout 설정은 호환성 때문에 받아도 요청 중단값으로 쓰지 않는다. 실제 응답시간 개선은 측정하지 않았다.
- 빠른 입력 흐름과 질문 선택, 설명·분석 화면을 수정했다. MediaPipe 자세·REBA 상세를 검토하는 `frontend/quick-review.js`와 화면 연결을 추가했다.
- AI 설명의 1차 REBA 요약, 설명 편집, 조사자 적용 경로와 Excel 출력 매핑을 수정했다.
- 보고서 provenance 추적에 `InputTrace.criterion_presence_recorded()`를 추가했다. 현재 코드에서 메서드는 `ergo/report/input_trace.py:43`에 있고 `ergo/report/form.py`, `ergo/report/plain.py`에서 호출한다.
- 계약·요구사항·화면·사진 문서와 회귀 테스트를 함께 갱신했다.

## 실제 저장 데이터에서 확인된 불일치

이 작업 중 `.local/origin-main-run.db`를 읽기 전용으로 조회한 기록이 있다. 그 조회에서는 조사/작업 1건, 사진 3장, 완료 분석 1건이었고 작업 입력 revision과 분석 revision은 11로 같았다. 입력 fact 37개 중 직접 응답 provenance는 6개였다. 질문 대화에는 3개 turn이 있었고 확인 가능한 질문은 `other_work`, `card.lift.lift_rate_min`, `context`였다. 4·5호 노출시간과 8호 하루 횟수·완료 여부를 묻는 turn은 확인되지 않았다. `legal.exposures`의 15개 분량 값은 모두 `null`, 자세 상태는 `PARTIAL_REVIEW`, 완성 REBA 수는 0이었다.

따라서 이 조회는 “사용자가 화면에서 답한 필드가 DB 저장 과정에서 모두 유실됐다”는 것을 증명하지 않는다. 오히려 사용자가 답한 질문과 시스템이 보고서에서 요구한 필드가 서로 달랐을 가능성을 보여준다. 위 DB 수치는 그 시점의 단일 로컬 자료다. 현재 파일을 다시 조회한 값으로 간주하지 말고, 재현 시 같은 조사·작업·분석 ID와 revision, 질문 transcript, source fact, `legal.exposures`, 계산 snapshot을 함께 대조한다. 이 작업에서 사용자 자료 DB를 수정하지 않았다.

별도 읽기 전용 소스 검토에서는 AI 요약에 사람이 읽을 수 있는 원 질문 대신 기준 코드와 계산상 누락 상태가 전달되고, 생성 문장의 의미가 저장된 `condition_present=YES`와 모순되는지 검사하지 않는 경로가 확인됐다. 이것은 “4호 미확인” 표현의 유력한 원인이지만, 해당 실호출의 원문 payload·응답을 확보한 것은 아니므로 확정 원인으로 쓰지 않는다.

**P2 — DB 관측 연결 근거 부족:** 이전 조회의 `legal.exposures`는 15개 행이 모두 `minutes=null`이었다. 이후 전달된 별도 DB 관측은 노출 행 0개로 보고됐다. 어느 조사·작업·분석 ID와 schema version을 조회했는지, query time과 원문 결과가 남아 있지 않아 두 관측이 같은 레코드인지 판정할 수 없다. 현재 2.0 기본값은 15개 노출 코드를 만들고 저장 검증도 그 목록을 요구하므로, **같은 2.0 작업이라면 0행은 정상 검증 경로와 맞지 않는다.** 다음 조사에서 같은 DB 경로·조사 ID·작업 ID·분석 ID·revision·schema version·조회 시각을 함께 기록해 대조한다.

## 현재 오류와 미수용 경계

- **`criterion_presence_recorded` 오류:** 브랜치 소스에는 메서드가 들어 있다. 독립 재점검에서는 현재 체크아웃의 Python worker 3개가 해당 파일 수정 시각보다 먼저 시작되어 구버전 클래스를 메모리에 유지했을 가능성이 가장 높다고 판단했다. 프로세스를 재시작하지 않았고 실제 IPC/Excel 요청으로 오류가 해소됐는지 확인하지 않았다. 새 코드의 통합 증거로 주장하지 않는다.
- **오래된 AI 설명 확정 위험:** 읽기 전용 리뷰에서 `ergo/service/explanations.py`의 적용 분기는 저장 후 `source_current`를 계산한다. 입력이 바뀐 설명의 확정을 서비스 계층에서 차단하는지 추가 검증이 필요하다. 화면의 현재성 확인만으로 서버와 Excel 경로까지 보장된다고 판정하지 않는다.
- **P1 — AI 생성 입력의 현재성 누락:** 프롬프트는 `analysis_currentness`가 `CURRENT`가 아니면 과거 분석임을 밝히라고 하지만, `ergo/gpt/payload.py`의 일반 numeric summary에는 이 필드가 없다. `_provisional_reba_summary()`는 1차 REBA 값이 없으면 즉시 `None`을 반환하고, currentness가 든 비교 요약은 그 결과가 있을 때만 추가된다 (`payload.py:63–65, 159–165`; 프롬프트 `client.py:22`). 따라서 1차 REBA 없이 오래된 분석으로 AI 설명을 만들 때 모델이 입력만으로 과거 분석임을 구분하지 못할 수 있다. 실제 provider 요청·응답으로 재현하지 않았다.
- **Human review → 실제 Excel:** 화면에 검토 단계와 편집·적용·미리보기 경로가 있다. 동일 분석 ID에 대해 설명 편집·확정 후 저장된 실제 Excel 내용까지 이어지는 전체 실행은 이 handoff 작성 시점에 검증되지 않았다.
- **자세·REBA 0건:** 기록된 한 분석에서는 유효한 자세 자료와 완성 REBA가 없었다. 결과가 없는 상태를 자세 없음 또는 REBA 0점으로 해석하지 않는다.
- **AI 무제한 대기:** timeout을 두지 말라는 사용자 결정을 따른 상태다. 공급자 응답이 오지 않을 때 진행 상태·취소·복구가 어떻게 동작하는지 별도 확인이 필요하다. 임의 hard timeout을 다시 넣지 않는다.

따라서 전체 기능은 **NOT ACCEPTED**다. P0/P1 반례가 전부 해소됐다고 판단하지 않았고, 실제 사용자 앱의 동작도 이 브랜치 커밋으로 확인하지 않았다.

## 검증 기록

- `git diff --check`: 통과. CRLF→LF 경고가 일부 있었으나 공백 오류는 보고되지 않았다.
- 프론트엔드 `npm test`, `npm run build`: 통과 기록(회귀 스크립트 26개).
- Python 집중 보고서·입력 검증: 48개 통과 기록. AI·적응형 입력 집중 실행도 통과 기록이 있으나, 다른 실행에서는 `tests.test_user_language`가 `KeyError: 'task'`로 실패했다. 실행 조건별 결과가 일치하지 않으므로 해당 테스트는 재실행 대상으로 남긴다.
- 전체 Python unittest discovery: 450개 실행, 순서 의존 입력 revision 실패 1건, `pdfplumber` 미설치로 인한 `test_pdf_export` import 오류 1건, skip 3건 기록. 전체 suite는 통과가 아니다.
- 실제 사용자 프로세스 재시작, 검토 화면에서 Excel 저장까지의 실사용 end-to-end, 응답시간 비교는 미수행이다. 외부 AI 호출과 사용자 DB 쓰기도 이 변경 검증으로 수행하지 않았다.

## 이어서 할 순서

1. 이 브랜치와 현재 `origin/main`을 다시 확인하고, 코드나 원격 상태가 달라졌으면 그 사실부터 기록한다. main 병합·PR·배포는 별도 지시 없이는 하지 않는다.
2. `criterion_presence_recorded` 오류를 격리 DB의 새 worker에서 재현하고, 앱 IPC의 실제 Excel 미리보기까지 실행해 수정된 모듈이 로드됐음을 확인한다.
3. 질문 transcript와 저장 fact를 같은 분석에서 대조해, 질문하지 않은 시간·횟수·완료 필드는 “미응답”으로 출력하지 않도록 빠진 질문 경로와 출력 분기를 고친다. 질문은 필요한 입력을 합쳐 최소화한다.
4. AI 요약에 현재성 정보를 항상 전달하고, 저장된 응답과 계산 초안의 차이를 사람이 읽을 수 있게 보여준다. 모델 설명이 직접 답변·점수와 모순되거나 오래된 분석을 현재 결과처럼 말하는 최소 반례를 회귀 테스트로 고정한다.
5. 서버 적용 경로에서 설명의 입력 snapshot/currentness가 현재 분석과 일치할 때만 확정할 수 있도록 검증한다. stale 설명이 Excel에 들어가는 최소 반례를 확인한다.
6. 격리된 실제 앱 흐름으로 5단계에서 AI·MediaPipe·REBA 결과 확인 → 설명 편집 → 조사자 확정 → Excel 저장을 진행한다. 저장된 Excel 셀을 같은 분석 ID·revision과 대조하고, 묻지 않은 필드가 출력되지 않는지 확인한다.
7. 순서 의존 Python 실패를 고치고, 현재 가상환경의 `pdfplumber` 설치 상태를 확인해 전체 검증을 다시 실행한다. 마지막 판정은 테스트 수와 마지막 결과를 보고한다.
