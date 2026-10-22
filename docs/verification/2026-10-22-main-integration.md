# 2026-10-22 main 통합 검증

통합 대상은 `fix/quick-slot-side-and-smoke`의 `f1e4c13ea19eadc87542a87a9d99e8873d84697c`와 main의 `a782bdb3662bc4dbe6be0a683bd8d846533fe5d8`(PR #22)다. 실행 중인 사용자 앱과 DB는 유지하고 별도 Git worktree에서 통합했다.

## 통합 내용

- 브랜치의 사진 인식 보정, AI 한 줄 입력, 결과/검토/Excel 화면 분리, 공식 서식 구성 Excel과 미리보기를 유지했다.
- main의 데이터 저장 위치 설정 창, AI 설명 읽기/수정/적용, REBA 위험 수준 표시, 앱 아이콘을 유지했다.
- `frontend/quick-flow.js`의 초기 상태 충돌은 AI 설명의 `aiDraft: null`, `aiEditorOpen: false`와 한 줄 입력/Excel 상태를 모두 초기화하도록 해결했다.
- `frontend/package.json`은 양쪽 회귀 시험을 합쳐 10개 스크립트를 실행한다. REBA 표시 시험의 부분 화면 fixture에는 새 한 줄 입력 화면이 요구하는 빈 `intakeText`를 추가했다.

## 실제 수행한 검증

Windows, CPython 3.12, Electron 44.7.2에서 실행했다. 모델과 공개 예제 사진은 기존 로컬 자료의 SHA-256을 확인해 검증 worktree에 준비했다. 사용자 조사/사진/DB는 시험에 사용하지 않았다. Electron 시험은 `LOCO_HIDDEN=1`로 실행했다.

| 검증 | 결과 |
|---|---|
| Python `unittest discover -s tests -p "test_*.py"` | 183개 통과, 실패/오류/skip 없음. 실제 MoveNet 추론 포함 |
| `npm --prefix frontend test` | 10개 회귀 스크립트 통과. 한 줄 입력, Excel 미리보기, AI 설명, REBA 표시 포함 |
| `npm --prefix frontend run build` | 실제 화면 자산/모듈 참조와 JavaScript 구문 검사 통과 |
| `scripts/audit_contract.py` | 문서화 43개 / 구현 43개 / renderer 호출 37개 |
| `tests/mutation/run_mutations.py` | 대조군 통과, 변이 10개 모두 탐지 |
| `npm --prefix frontend run test:database` | 실제 Python/SQLite 연결 5개 사례 통과. 네이티브 창/클립보드/폴더 열기는 mock |
| `npm --prefix frontend run test:electron` | 실제 Electron → Python → SQLite → 모델/Excel 업무 흐름 29개 점검 통과 |
| `tests/verify_local_artifacts.py .local/merge-electron` | SQLite와 Excel 5개 독립 대조 PASS. 6개 테이블, 분석 10개, 출력 로그 5개 |
| `npm --prefix frontend run test:explanation` | 실제 SDK와 loopback HTTP fixture 4개 통과. 정상 응답, 잘못된 근거, 비차단 요청, 시간 초과 |
| `git diff --check` | 통과 |

원본 receipt, 검증 전용 DB, Excel, 화면 캡처는 worktree의 `.local/merge-electron/`과 `.local/explanation-*`에 있으며 Git에는 포함하지 않는다. 모델과 공개 예제 사진의 해시는 각각 `0fac2226112d0371903ca86e3853cec24ef603a0b2f96f589b180f0ebdd135ab`, `4dbdf2f342597a2415c96e82052217e083e61d72500c711b2cd0eebaeb8a58c6`다.

## 남은 검증 범위

이번 통합에서는 외부 OpenAI 계정 호출, 새 포터블 빌드, 별도 Windows PC, 현장 사진 정확도/실사용 시간, 공식 HWP와 칸 단위 대조, 실제 인쇄를 검증하지 않았다. 기존 포터블은 `a57b3835` 기준이므로 이번 main 통합본의 패키지로 간주하지 않는다. 인수인계에 적힌 입력 기능의 제약과 오래된 문서 일부의 출력 조건 불일치는 이번 통합에서 수정하지 않았다. 전체 수용 판정은 `NOT ACCEPTED`를 유지한다.
