# LOCO 2.0 구현·검증 대조표

검증 당시 기준: feat/loco-2.0-oct23, HEAD a4213eb와 당시 미커밋 변경. 검증일 2026-10-16(Asia/Seoul). **로컬 검증 통과 / 전체 수용 NOT ACCEPTED**다. 검증한 실행 소스 90개의 해시는 [소스 manifest](verification/2026-10-16-source-manifest.json)의 source_sha256에 기록한다. 게시 전 v13.py의 빈 EOF 행과 actions.js의 끝 공백만 정리했으며, 공백 정규화 후 원문 동일성을 확인했다. publication_formatting_changes와 publication_source_sha256에 변경 전후 해시를 기록하고 정리 후 Python·프론트 시험을 다시 통과했다. Electron/포터블 영수증은 공백 정리 전 실행 기록이다. 외부 계정·별도 PC·실사용 자료·현장 성과를 로컬 합성 실행으로 대체하지 않는다.

## 정본 요구사항 대조

| 요구사항 | 구현 영역 | 실제 검증 | 범위 |
|---|---|---|---|
| REQ-01 조사·복수 작업 | service/surveys·task_inputs, frontend/task·survey | 최초/정기/수시·분리·저장/재열기·재시작, 복수 작업 생성/삭제, 조사 삭제 후 다른 자료 보존을 실제 화면에서 확인 | 로컬 통과 |
| REQ-02 UNKNOWN·질문 순서 | task_defaults, task/defaults·definitions·inputs | 7개 템플릿의 11개 질문 유지·순서 변경·입력 불변, 작업명으로 판정 추측 없음 | 로컬 통과 |
| REQ-03 조건 행·합집합 | burden_rules | 혼합 중량·망라성·대상 행·중복 제거·하루 시간 초과·null/0·OR 반례 | 자동 검증 통과 |
| REQ-04 11개 초안·근거 | burden_rules, criteria-view | 44개 최소 사례, 수치 경계, 제외·누락·해석·9호 중량 누락, 결론 수정/해제 | 자동/화면 통과 |
| REQ-05 가변 사진 | service/photos·task_inputs, frontend/photo | 사진 없는 입력, 요청 0건, 1/여러 행·배정·삭제·안정적 번호·불량 파일·수동값 보존. 경로 재연결·사진 교체 회귀 | 로컬 통과 |
| REQ-06 MoveNet | movenet·images·joint_angles | 공식 SHA-256·실제 CPU 17관절, EXIF·비정방형·신뢰도·촬영 맥락·모델/사진 오류 | 실제 모델/경계 통과 |
| REQ-07 좌우 REBA | reba_scoring, reba-view·actions | 선택 후보 적용, 양쪽 구성값, 무하중/미입력, 대표·미완성 분모, 수동값 복귀, 과거 snapshot 사진 행 | 로컬 통과 |
| REQ-08 GPT | explanations, gpt/client·payload, explanation-view | 목적별 편집/적용·현재성·키 없음 대체. 실제 SDK+127.0.0.1 구조/잘못된 근거/비차단/시간 제한 | 로컬 통과 / 외부 성공 미검증 |
| REQ-09 저장·검토 | analysis_records·analysis_jobs·runtime, db | 부분 저장·결론·검토 이력·지연 완료·취소·삭제·최신 포인터·불변 snapshot·충돌 저장 거부 | 자동/화면 통과 |
| REQ-10 Excel | overview·renderer·statutory_forms | 개발/포터블 각 5개 Excel. 기본 4/질환자 발생 수시만 6시트, SQLite snapshot·11개 판정 셀·비교값·수식 아님 독립 대조 | 로컬 통과 |
| REQ-11 상세 전후 | comparisons, review-links | 11개 상태, 조건/범위/법령/사진/수동값/설정 차이. 호환 화면 REBA 2→1·차이 −1, 독립 시험 3→1·차이 −2. 불일치 표본은 null | 로컬 통과 |
| REQ-12 1.3 호환 | legacy/v13, settings, report | 합성 원문/추가 키/과거 분석·출력·설정 보존, 명시 저장 승격, 사진 비율 시간 승계 금지. 폐기 관계형 DB는 쓰기 전 거부 | 합성 통과 / 사용자 DB 미검증 |
| REQ-13 Windows | electron/main·preload, build_windows | 최신 EXE·포함 Python/모델, PATH 시스템 경로 제한 후 전체 29개 화면·재시작·SDK 4개. 현재 실행 소스 90개 해시 일치 | 포터블 통과 / 별도 PC 미검증 |
| REQ-14 조사 맥락 | survey_defaults, frontend/survey, report | 상황 4종·작업조건 저장·누락·출력·조사별 분리 | 로컬 통과 |
| REQ-15 참여·증상 | survey_defaults, frontend/survey, statutory_forms | 참여 누락, 익명 응답·중복 코드·6부위 계약·유형별 출력, 실제 화면 익명 응답 보존 | 합성 통과 / 현장 미검증 |

## 모듈화·폐기 경로

[모듈 지도](module-map.md)에 서비스 조립/Runtime·8개 domain 서비스·entity 저장·보고서 상태/비교/렌더링/조건부 서식·프론트 입력/표시/이벤트와 분석 view를 정리했다. 앱 인스턴스의 DB·취소·잠금 분리와 역방향 의존 금지를 시험한다.

0.3 Protocol·StubService·get_service, 가짜 엔진/Excel scaffold, 별도 1.3 서버·프론트 adapter, 이전 SQL view 검사, 15장 목업 실행 경로·미사용 SVG를 제거했다. 새 계산의 순서 기반 하중, 이전 설명 적용 매개변수, 전체 result_json 덮어쓰기·최신 포인터 임의 변경 저장 API도 제거했다. 1.3 읽기는 [읽기 계약](legacy-compatibility.md)에 남겼다.

정본/registry/dispatch 40개와 renderer 정적 호출 31개를 대조했다. 좁은 저장 API는 통합 입력 저장 또는 동적 조사 CRUD 흐름에 대응한다. 이전 버전 생성·잘못된 매개변수/ID·수동값 누락·boolean 동의·문자열 검토·지원하지 않는 모델/규칙 설정은 저장 전에 거부한다.

## 실제 실행 결과

- CPython 3.12 x64 **96개 시험 통과**, 공식 모델 smoke 포함, skip 없음.
- 프론트 회귀 **4종 통과**: ES module 로드, 최신 사진/수동값과 미저장 소유 필드 보존, 동시 편집 충돌, 질문 순서/입력 불변.
- mutation **10종 탐지**, 대조군 통과. 주입 코드에서의 시험 실패는 기대된 반증 결과다.
- 개발 Electron과 최신 포터블 각각 **29개 실제 화면 점검 통과**. 대화상자 경로만 fixture로 공급하고 renderer·preload·Python·SQLite·공식 모델·Excel은 실제 실행했다.
- 최신 포터블의 실제 OpenAI SDK와 로컬 HTTP fixture **4개 통과**. 외부 GPT 계정 호출이 아니다.
- 각 검증 DB: 여섯 테이블, 조사 3·작업 1·사진 2·분석 10·출력 로그 5. 중간 삭제 전용 작업/조사는 제거하고 다른 자료 보존을 확인했다.
- 4/6시트, 일반/비교용 snapshot, 판정 셀, 호환 REBA 차이·수동값 변경의 Excel 내용을 SQLite와 독립 대조했다.
- 최신 경로는 `.local/latest-package.txt`, 실행 소스 **90개 SHA-256**은 build-manifest.json과 현재 파일이 일치한다. HEAD만으로 미커밋 구현을 식별하지 않는다.

[요약 JSON](verification/2026-10-16-local.json)에 실행 경로·실행물·점검·DB/Excel 대조·환경을 기록했다. 초기 증거는 verification/2026-10-16-initial.json에 보존한다. 원본 로그와 시작 상태 백업은 .local/continuation-20261016/, 각 실행 디렉터리에 receipt·검증 SQLite·Excel·화면 PNG가 있다.

수정한 반례는 계산/AI 충돌, 결론 변경/해제, 복귀 후 수동값 소실, 9호 미확인 중량, union 시간 모순, 설정 현재성, 4/6시트 문서 충돌, 과거 사진 행 열람, 전후 수동값/관찰/설정 차이 누락이다. 시험 범위에서 남은 P0/P1 반례는 재현되지 않았다. 모든 임의 입력·응답 문장·실제 조사자 판단을 검증했다는 뜻은 아니다.

## 재현

저장소 루트에서 의존성·공식 모델을 준비한다. 자세한 실행/빌드는 [README](../README.md)를 따른다.

```powershell
.\.venv\Scripts\python.exe -B -m unittest discover -s tests
npm.cmd --prefix frontend test
npm.cmd --prefix frontend run build
.\.venv\Scripts\python.exe -B scripts/audit_contract.py
.\.venv\Scripts\python.exe -B docs_src/erd/build_and_test.py
.\.venv\Scripts\python.exe -B tests/mutation/run_mutations.py
npm.cmd --prefix frontend run test:electron
npm.cmd --prefix frontend run test:explanation
.\.venv\Scripts\python.exe -B tests/verify_local_artifacts.py '<Evidence 디렉터리>'
```

포터블은 LOCO_VERIFY_EXECUTABLE에 최신 폴더의 LOCO.exe 절대 경로를 지정하고 같은 test:electron/test:explanation 명령으로 검증한다. 검증은 새 전용 DB를 생성한다. 사용자 DB·기본 앱 DB를 검증 경로로 지정하지 않는다.

공개 사진은 기존에 확보한 [TensorFlow MoveNet 튜토리얼](https://www.tensorflow.org/hub/tutorials/movenet) 예제다. .local/fixtures/tensorflow-movenet-example.jpeg SHA-256은 `4dbdf2f342597a2415c96e82052217e083e61d72500c711b2cd0eebaeb8a58c6`이다. 여러 사진 조작은 같은 공개 이미지의 복사본을 사용했다. 실제 여러 작업 자세 검증으로 해석하지 않는다. 준비 URL은 https://images.pexels.com/photos/4384679/pexels-photo-4384679.jpeg 이며 내려받은 뒤 해시를 확인한다.

## 남은 제약·보존

외부 GPT 성공과 응답 내용 평가, 깨끗한 별도 Windows PC 설치, 사용자 실제 1.3 DB, 현장 조사자 3~5명의 사용·시간 측정은 미수행이다. 최신 법률 적용 해석·표본 대표성·임상/산재 감소 효과도 이 시험으로 입증하지 않는다. 전체 수용은 NOT ACCEPTED로 유지한다.

schema_v1.sql의 SHA-256은 시작 백업과 동일하다. 새 테이블·trigger·물리 migration을 추가하지 않았다. 기존 분석/출력 snapshot을 재작성하지 않고 사용자 DB를 검증에 사용하지 않았다. 초기 수정·새 파일·patch는 .local/continuation-20261016/baseline/에 보존했다. 이 검증 기록은 커밋·push 전 로컬 실행 결과다. 2026-10-16 후속 사용자 지시에 따라 소스·설계·시험·검증 요약을 feat/loco-2.0-oct23 브랜치에만 커밋·push한다. main 반영·PR·병합·운영 배포는 수행하지 않는다. 검증 DB·사진·모델·실행 패키지·원본 로그는 Git에 포함하지 않는다.


## 2026-10-20 후속 · N02 일부와 N05 사전 점검

기준 HEAD `d5fe9d9`와 미커밋 후속 소스다. 기존 2026-10-16 실행 기록을 새 화면의 완료 증거로 재사용하지 않는다. 관련 소스·실행물·ZIP 해시는 [후속 manifest](verification/2026-10-20-n02-n05.json)에 기록한다. Python 서비스·계산·저장 모듈은 수정하지 않았다.

| 범위 | 이번에 확인한 결과 | 남은 확인 |
|---|---|---|
| N02 경로 표시 | Electron이 worker에 넘기는 절대경로를 표시. 연결 실패·8초 지연·중복·메모리·미리보기·복사/열기 실패 15개 독립 반례 통과 | 실제 창의 배치와 OS 클릭, 유서하 교차 검증 |
| N02 실제 연결 | 실제 main/preload 코드와 실제 Python/SQLite로 절대/기본/상대경로·손상 DB·Python 실패 5개 통과. 모든 행과 JSON 보존 대조 | 네이티브 창·클립보드·폴더 열기는 mock으로 검증했음 |
| 프론트 계약 | 기존 회귀, 프론트 빌드, 40개 서비스 메서드 계약 대조 통과 | DB 선택·실행 중 전환·미저장 처리 미구현 |
| N05 패키징 | 요구 빌드 의존성·공식 모델 해시 확인 후 새 포터블 폴더·ZIP 생성. 코드/모델·EXE·ZIP 해시 기록 | 미커밋 작업 포함 개발 점검용. 최종 전달 전 커밋 소스로 재빌드 |
| N05 frozen 서비스 | Windows 기본 PATH에서 실제 EXE로 한글·공백 DB 생성, 직접입력, 흰 합성 PNG의 실제 CPU 추론 17점, 키 없는 설명 대체/편집/적용, 4/6시트 Excel, 재실행 보존, 잘못된 모델 오류 등 7개 통과 | 별도 PC, 네이티브 GUI, 실제 GPT·현장 사진 정확도·실물 인쇄 미검증 |

실제 개발 Electron은 전용 임시 DB로 실행했다. Windows 화면 캡처는 `FrameArrived timed out`과 `window capture timed out`으로 실패하여 이후 UI 자동 조작을 중단했다. 코드/서비스 검증 통과를 실제 배치·클릭 검증으로 보고하지 않는다. 포함 LiteRT의 OpenVINO 선택 플러그인 DLL 경고가 있었으나 CPU 추론은 통과했으며 해당 가속 경로는 검증하지 않았다.

N02 재현: `npm.cmd --prefix frontend test`, `npm.cmd --prefix frontend run build`, `LOCO_VERIFY_PYTHON`을 지정한 `npm.cmd --prefix frontend run test:database`, `python -B scripts/audit_contract.py`. N05 재현: 빌드 환경에서 `python -B tests/portable-service-smoke.py`. 모든 신규 검증은 새 전용 DB와 합성 입력을 사용한다. 결과는 로컬 임시 검증 폴더의 receipt와 패키지 manifest로 남긴다.

팀원이 지정된 교차 검증과 별도 PC 검증은 아직 수행하지 않았으므로 N02/N05 전체 완료나 전체 수용으로 표시하지 않는다. 기존 전체 수용 상태 NOT ACCEPTED를 유지한다.
