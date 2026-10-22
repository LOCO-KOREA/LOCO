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

## 실제 외부 AI를 포함한 전체 E2E 추가 실행

사용자의 추가 E2E 요청으로 `tests/adaptive-intake-full-live.cjs`를 실행했다. Computer Use 시도는 사용자 요청에 따라 중단했으며, 아래 시험은 OS 입력 없이 별도 Electron 창을 화면 밖(x=-12000, y=-12000)·초점 불가 상태로 실행했다. 기존 사용자 창/DB/프로필은 변경하지 않았다.

처음 시험은 `4874336`의 저장값 수정 화면에서 실패했다. ‘수정’을 누른 뒤 다시 그려진 `<details>`가 접혀 입력칸이 보이지 않았다(`.local/full-live-e2e-20261022-143009/receipt.json`). 편집 중인 정보 영역은 열린 상태를 유지하도록 고쳤고, 프론트 회귀 시험에 해당 반례를 추가했다.

수정 후 `.local/full-live-e2e-fixed-20261022-143053/receipt.json`에서 **9개 점검 모두 통과, 화면 오류 0개**를 확인했다. 외부 OpenAI gpt-4.1은 작업 정보 정리 3회와 실제 설명 생성 1회에 사용했다. 설명 결과는 `GENERATED`, fallback 없음이다. 네이티브 파일 선택/저장 대화상자의 경로만 자동 지정했으며 AI 응답·서비스·DB·모델·Excel 작성기는 실제 구현이다.

1. 공개 사진 실제 MoveNet 17관절 추론, 설명값 20kg/하루 30회/전체 480분/연 220일 저장, 같은 값 재질문 제외.
2. 두 번째 실제 AI 응답으로 동일한 20kg 조건에 분당 1회/하루 30분 누적 저장.
3. 화면에서 전체 시간을 420분으로 직접 수정하고 자동 저장/USER 출처 확인.
4. 어깨 위 들기 횟수에 모름을 답한 뒤 앱을 종료·재실행해 수정값 복원과 해당 질문 제외 확인.
5. 세 번째 실제 AI 요청 후에도 직접 수정 420분과 모름 유지.
6. 누락 입력이 있는 상태에서 11개 기준 결과 생성, 실제 관절 결과와 420분 snapshot 확인.
7. 실제 AI 설명 생성·적용, 검토 표시 저장. 계산 결과/REBA/분석 snapshot은 설명 전후 동일.
8. 화면 미리보기에서 실제 Excel 생성, 파일과 출력 snapshot/로그 저장.
9. 두 번째 앱 재실행 후 저장된 분석·적용 설명·검토 표시 복원.

`tests/verify_local_artifacts.py .local/full-live-e2e-fixed-20261022-143053 1` 독립 대조도 PASS다. 테이블은 기존 6개이며 분석 1개, 사진 1개, 출력 로그 1개와 Excel 1개(7시트)가 일치한다. 11개 판단 표시, 불변 분석 snapshot, 시트 구성, 수식 미삽입을 확인했다. 프론트 회귀 11개 스크립트와 build도 수정 후 다시 통과했다. 공개 사진은 현장 적합성이 검증된 사진이 아니므로 이 예제의 REBA는 미완성으로 남는다. 이는 입력 필요를 유지하는 진행 경로의 검증이며 완전한 현장 점수 검증으로 확대하지 않는다.

## 대화 팝업으로 사용 방식 수정

사용자가 ‘AI가 기존 정보를 정리하고 모르는 것만 팝업으로 물어보라’고 다시 지정했다. 앞선 폼 중심 추가 확인은 이 사용 방식을 충족하지 못했다. 이번 수정은 기본 입력 폼/질문 목록을 없애고, AI 자동 정리 후 대화 팝업을 자동으로 여는 것이다. 정책 질문 수는 하나이며 자연어로 답하면 AI가 정리·저장하고 다음 질문을 고른다. 직접 편집은 요약에서 명시적으로 수정할 때만 제공한다.

AI는 추출 뒤 실제로 남은 누락을 기준으로 질문한다. 추출 전 만든 질문이 이미 해결됐으면 추출값부터 저장하고 갱신된 누락을 AI에 다시 전달한다. 마지막 실제 응답의 CONNECTED/ERROR/NOT_REQUESTED·모델·사유·시각·응답 ID를 저장하고 팝업에 표시한다. 설정이나 키가 있다는 이유만으로 연결 성공을 표시하지 않는다. 오류가 나도 입력 문장과 기존 사실은 보존하며, 빈 재시도에서도 마지막 저장 진술을 문맥에서 제외하지 않는다.

- Python 전체 **207개 통과**, skip 없음. 실제 응답 상태/복원, 추출 후 누락으로 질문 계획, 빈 재시도의 마지막 진술 보존 반례 포함.
- 프론트 회귀 11개 스크립트와 build 통과. 팝업의 숫자 폼 미노출, 기본 페이지의 질문 목록 미노출, 연결 상태 구분, 오류 시 답변 보존 포함.
- 계약 문서/구현 46개, renderer 호출 40개 일치. 변이 13개 모두 탐지. 임시 복사 대조군의 사진 1개 skip은 기존과 같고 원본 전체 시험에서는 실행했다.
- **실제 OpenAI gpt-4.1 + Electron/Python/SQLite/MoveNet/Excel E2E 9개 통과**: `.local/popup-live-20261022-143925/receipt.json`. 팝업이 자동으로 열리고 질문 하나/숫자 폼 없음/실제 응답 ID/CONNECTED를 확인했다. 첫 질문은 이미 아는 20kg·하루 30회·전체 8시간을 제외하고 ‘20kg 상자를 이렇게 하루 총 몇 분쯤 들고 옮기나요?’였다. 이후 자연어 답변·수정·모름·재실행 2회·결과·실제 설명 적용·검토·Excel까지 통과했다.
- 해당 SQLite/Excel 독립 대조 PASS: `.local/popup-live-20261022-143925/artifact-receipt.json`.
- 실제 HTTP 실패 응답을 포함한 로컬 프로토콜 fixture E2E 7개 통과: `.local/popup-retry-20261022-144602/receipt.json`. 실패를 CONNECTED로 표시하지 않고 팝업에서 재시도/현재 결과 진행이 가능했다. 이 항목의 OpenAI 응답은 fixture이며 위 외부 계정 시험과 구분한다.

검증은 화면 밖·초점 불가 별도 Electron 창에서 수행했고 OS 마우스/키보드를 사용하지 않았다. 기존 앱 갱신 전에는 SQLite 일관 백업과 현재 입력/화면값 checkpoint를 따로 보관한다. 기존 사용자 입력을 이어 열고 창을 활성화하지 않는 방식으로 새 팝업을 표시한다. 현장 정확도·별도 PC·포터블 패키지·인쇄 미검증 범위는 앞 절과 같다.


## AI 설정 통합과 Luna / extra high 실스택 (2026-10-22)

프론트의 gpt-4.1 기본값과 각 GPT 호출의 15/20초·1400/1500/3200토큰 상수를 제거했다. 저장·SDK와 독립인 `ergo/ai_config.py`가 모델·추론 강도·시간·토큰·필드/타입/선택지/환경변수를 한 계약으로 정의한다. get_settings.gpt_contract와 frontend/ai-settings.js로 간편/고급 화면을 렌더링하며 실제 입력 정리·후속 질문·기존 한 줄 입력·설명 호출은 같은 옵션을 사용한다. 기본값은 gpt-6-luna / xhigh / 180초 / 32768토큰(추론 포함)이고 저장값이 환경 기본값보다 우선한다. 별도 운영 승인·배포 차단 기능은 추가하지 않았다.

- 실제 계정에서 gpt-6-luna / xhigh 응답 확인 후, `.local/luna-xhigh-full-20261022/receipt.json`의 전체 E2E **9개 통과**, 화면 오류 0개. 초기 자동 정리는 50.9초였고 AI 사실 13개와 실제 MoveNet 17관절을 저장했다. 첫 추가 질문은 이미 아는 중량/횟수/전체 시간 대신 하루 들고 옮기는 시간을 물었다.
- 입력 정리와 실제 설명 생성의 응답 model=gpt-6-luna, reasoning.effort=xhigh 및 response_id를 검증했다. 설명은 GENERATED, fallback 없음. 후속 답변·USER 수정 420분·모름·재실행 2회·실제 결과·설명 적용·검토·Excel까지 이어졌다.
- `verify_local_artifacts.py .local/luna-xhigh-full-20261022 1` PASS. 기존 여섯 테이블, 분석/사진/출력 각 1개, Excel 7시트, 분석/출력 snapshot과 11개 판단 표시를 독립 대조했다. 입력 시트의 420분/일, 20kg, 30회/일, 1회/분, 30분/일도 각 필드명과 함께 확인했다.
- Python **214개 통과**, 프론트 회귀 12개 스크립트와 build 통과, API 46개/renderer 40개 일치. 기존 변이 13개 탐지 후 ‘설정한 추론 강도를 SDK 요청에서 누락’ 변이를 추가해 별도 탐지했다. 설정 저장/환경 우선순위/누락 필드 호환/잘못된 값/세 SDK 경로 옵션/연결 상태 재사용 반례 포함.
- 실제 간편 설정 → 고급 설정 → SQLite → 재실행 E2E 3개 통과: `.local/ai-settings-1792649088808/receipt.json`. 사용자 화면은 조작하지 않았다. 최초 시험의 toast 선택자 오기를 `#toast`로 수정해 재실행했다.
- 실제 SDK/loopback 설명 E2E 4개(`.local/explanation-1792648843814`)와 적응형 E2E 7개(`.local/adaptive-1792648868902`) 통과. 시간 초과 시험은 자체 설정을 15초로 지정해 실제 TIMEOUT/재시도 없음/계산 보존을 검증했다. 이 응답은 외부 AI 검증과 구분한다.
- 개발 앱은 일관 SQLite 백업과 입력 checkpoint 후 같은 DB/프로필로 갱신했다. PID 38408에서 실제 Luna/xhigh CONNECTED 응답을 확인했고 창은 showInactive로 표시해 초점을 빼앗지 않았다. OS 입력은 사용하지 않았다.

공개 사진·합성 작업 설명에 대한 흐름 검증이다. 예제의 REBA/일부 기준은 입력 부족을 유지하며 완성 점수로 포장하지 않았다. 현장 정확도·다른 PC·새 포터블·인쇄는 이번 범위에서 미검증이다.
