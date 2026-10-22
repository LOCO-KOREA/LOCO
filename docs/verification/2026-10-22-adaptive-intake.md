# 2026-10-22 적응형 추가 확인 구현·검증

기준은 main `e645d1458be703d86e84085cfc4209a3707166f9`이며 구현 브랜치는 `feat/adaptive-intake-ux`다. 사용자가 승인한 범위는 사진·설명에서 이미 확보한 정보를 저장하고 계산에 재사용하며, AI가 부족한 부분만 추가로 질문하는 흐름이다.

## 구현

- 고정 질문 순회를 새 작업의 기본 흐름에서 제거했다. 사진·설명 → 자동 정리 → 필드별 추가 확인 → 현재 정보로 결과 생성 → 기존 검토/설명/Excel로 연결한다.
- 출처·근거·상태·작업 조건을 기존 TASK JSON과 실제 conditions/legal/capture/manual 값에 함께 저장한다. 여섯 테이블을 유지하며 기존 분석/출력 snapshot은 변경하지 않는다.
- 공통 catalogue 90개 필드, 메서드 이름, 저장 키, 단위·선택지·질문 수·시간 제한을 변수로 정의했다. 서비스가 반환한 계약으로 프론트와 AI schema를 구성한다. 계약·병합·누락 계산·모델 요청·저장·화면 모듈을 분리했다.
- 직접 수정 우선, 모름 반복 제외, 서로 다른 중량 조건 분리, 사진 하중과 하루 작업 하중 구분, 지연 응답의 최신 입력 덮어쓰기 방지를 구현했다. 말하지 않은 특징은 UNKNOWN으로 유지한다.
- 운영 승인·배포 차단·AI 성공 필수 조건은 추가하지 않았다. AI 실패/시간 초과 시에도 저장된 입력과 직접 답변으로 현재 결과를 생성할 수 있다. 필수 수치가 빠진 계산은 기존 입력 필요 상태로 남는다.

## 실제 수행한 검증

Windows / Python 3.12 / Electron 44.7.2 / 로컬 SQLite / 실제 MoveNet Lightning에서 실행했다. 사용자 현장 자료 대신 공개 예제 사진과 합성 작업 설명을 사용했다.

| 검증 | 결과·증거 범위 |
|---|---|
| Python 전체 `unittest discover -s tests -p "test_*.py" -q` | 204개 통과, skip 없음. 적응형 21개 포함, 실제 사진 추론 포함 |
| 프론트 `npm --prefix frontend test` | 11개 회귀 스크립트 통과. 동적 메서드/저장 키/단위/제한 주입, 0·모름 저장, 저장 실패 입력 보존, 지연 응답 제외, 후보 값 숫자 변환 포함 |
| `npm --prefix frontend run build` | 실제 Electron 화면 자산·모듈·JavaScript 구문 통과 |
| `scripts/audit_contract.py` | 문서 46 / 구현 46 / renderer 호출 40 |
| `tests/mutation/run_mutations.py` | 13개 결함 변이 모두 탐지. 직접 수정 덮어쓰기, 숫자 근거 생략, 서로 다른 중량 조건 합치기 포함. 대조군 통과; 임시 복사에 모델/사진이 없어 사진 사례 1개 skip, 전체 원본 시험에서는 해당 사례 통과 |
| `npm --prefix frontend run test:database` | 실제 main/preload/Python/SQLite 5개 사례 통과. 네이티브 클립보드/폴더 실행은 mock |
| `npm --prefix frontend run test:electron` | 기존 실제 Electron 업무 흐름 29개 통과. `.local/adaptive-advanced/receipt.json` |
| `tests/verify_local_artifacts.py .local/adaptive-advanced` | SQLite와 Excel 5개 독립 대조 PASS. 여섯 테이블, 분석 10개, 출력 로그 5개, 실제 모델 결과 8개 |
| `npm --prefix frontend run test:adaptive` | 실제 Electron/Python/SQLite/MoveNet/Excel 7개 통과. OpenAI HTTP만 loopback 응답 fixture. `.local/adaptive-ui-release/receipt.json` |
| 적응형 Excel 독립 대조 | 저장된 분석 snapshot, 11개 판단 표시, 시트/출력 로그 일치. `.local/adaptive-ui-release/artifact-receipt.json` |
| `npm --prefix frontend run test:adaptive:live` | **실제 외부 OpenAI gpt-4.1 두 회차** 통과. `.local/adaptive-live-release/receipt.json`. 최초 정리 약 6.0초, AI 사실 12개, 실제 MoveNet 관절 17개, 실제 분석 생성 |

외부 AI 시험에서 20kg·하루 30회·전체 8시간·연 220일·일회성 아님·사진 상황·손잡이를 저장하고 같은 항목을 다시 묻지 않는 것을 확인했다. 후속 자연어 답변의 분당 1회·하루 30분은 동일한 20kg 조건 행에 누적 저장했다. 5kg/99회와 30kg/1회 혼합, 하루 횟수를 분당 횟수로 오인, 단위가 다른 숫자, 잘못된 AI 형식, 직접 수정과 늦은 응답은 별도 반례로 검증했다.

검증 DB·사진·키·Excel은 Git에 포함하지 않는다. 모델 SHA-256은 `0fac2226112d0371903ca86e3853cec24ef603a0b2f96f589b180f0ebdd135ab`, 공개 사진은 `4dbdf2f342597a2415c96e82052217e083e61d72500c711b2cd0eebaeb8a58c6`다.

## 한계

합성 설명/공개 사진으로 저장·질문·계산·출력 연결을 검증했다. 실제 현장 사진의 정확도, 모든 자연어 표현의 추출률, 별도 Windows PC, 새 포터블 패키지, 공식 HWP와 칸별 대조, 실제 인쇄는 검증하지 않았다. MoveNet 사진 후보는 하루 시간/힘/중량의 측정 근거가 아니다. 전체 현장 수용은 기존 `NOT ACCEPTED`를 유지한다. 이것은 검증 기록이며 앱의 실행 차단 장치가 아니다.
