# LOCO 2.0 모듈 지도

외부 실행 경로는 Electron → preload → JSON Lines → Application Service → 기능 모듈 → SQLite다. `backend/contracts.py`의 40개 메서드와 API 계약서 §7을 대조한다. 새 구현과 불변 저장자료의 읽기 호환을 분리한다.

| 경계 | 모듈 | 책임 |
|---|---|---|
| 서비스 조립 | `backend/service/application.py`, `runtime.py` | 메서드 연결, DB 주입, 앱별 잠금·취소 상태. `create_service(path)`는 독립 앱 인스턴스다. |
| 작업 입력 | `service/task_inputs.py` | 2.0 입력 검증·사진 배정 변경·revision·수동값 보존 |
| 조사 검토 | `service/surveys.py` | 조사 CRUD·검토 이력 |
| 사진 | `service/photos.py` | 등록·재연결·미리보기·삭제 |
| 분석 기록/실행 | `service/analysis_records.py`, `analysis_jobs.py` | 불변 snapshot·부분 저장·결론·대표 선택 / 재사용·추론·취소 |
| 설명 | `service/explanations.py`, `gpt/client.py`, `gpt/payload.py` | 생성/편집/적용 이력 / SDK 호출 / 비식별 허용 요약과 응답 검증 |
| 설정·출력 | `service/settings.py`, `reports.py` | 실제 엔진 설정·현재성 / 단일 읽기 snapshot·출력 영수증 |
| 순수 계산 | `engine/burden_rules.py`, `reba_scoring.py`, `movenet.py`, `joint_angles.py`, `pose_tags.py` | 11개 기준·좌우 REBA·공식 모델·관절 각도·표본 태그. DB/화면을 참조하지 않는다. |
| 저장 | `db/storage.py`, `storage_common.py`, `surveys.py`, `tasks.py`, `photos.py`, `analyses.py`, `settings.py`, `exports.py` | 기존 여섯 테이블의 entity별 CRUD, 짧은 트랜잭션, JSON 행 변환 |
| 보고서 | `report/workbook.py`, `common.py`, `overview.py`, `comparisons.py`, `plain.py`, `form.py`, `renderer.py`, `labels.py`, `display.py` | 공통 상태/누락·전후 비교·일반인용 데이터 시트 정의(plain)·기록 입력 요약(form)·Excel 렌더링(renderer)·한글 표시 |
| 이전 자료 | `legacy/v13.py` | 저장된 1.3 입력을 메모리에서 편집 DTO로 읽는다. 이전 규칙을 실행하지 않는다. |

서비스의 domain 모듈은 조립 진입점을 import하지 않고 `Runtime`을 인자로 받는다. 저장 모듈은 engine/GPT/service를 import하지 않는다. 분석 완료와 AI·조사자 편집은 각자 담당 필드만 저장하며 snapshot을 수정하지 않는다.

프론트는 네이티브 ES module이다. `desktop.js`가 작업·사진·조사·대시보드·분석 workspace를 조립한다. `task/`, `photo/`, `survey/`에는 입력 상태·화면 렌더링·이벤트 모듈이 있다. `analysis/`에는 공유 표시/DOM 도구, 상태, 진행·REBA·판정·설명·출력·설정 view, 사진 canvas, actions, navigation controller가 있다. 각 분석 workspace는 별도 상태와 명시적 의존 객체를 갖는다. 전역 가짜 서비스나 SVG 목업을 실행하지 않는다.

`database-location.js`는 설정의 “데이터 저장 위치” 창과 저장 연결 실패 시의 공통 안내를 담당한다. 사용자용 설정 진입은 숨기고 내부 S10 설정 화면에서 이 창을 열며, 일반 작업 화면에는 경로를 상시 표시하지 않는다. `electron/database-location.cjs`는 worker에 전달할 경로 결정·연결 조회·복사/폴더 열기를 담당하며 Python 서비스·계산·저장 모듈을 수정하지 않는다. 경로와 연결 성공은 별도로 표시한다. `tests/frontend-database-location.cjs`는 오류·중복·경로 반례를, `tests/desktop-database-integration.cjs`는 실제 main/preload와 Python·SQLite 연결을 검증한다. 후자의 네이티브 창·클립보드·폴더 열기는 mock이며 실제 GUI 검증과 구분한다.

`scripts/check_frontend.cjs`는 실제 Electron 페이지·ES module import·문법을 확인한다. `scripts/audit_contract.py`는 정본/registry/dispatch/renderer 호출을 대조한다. `tests/test_modularity.py`는 앱 인스턴스 분리와 역방향 의존을 검증한다. 실제 업무 흐름과 배포본 검증은 `local-verification.md`를 따른다.

## 적응형 입력 모듈 (2026-10-22)

`backend/intake/{contract,facts,planner}.py`는 공통 계약·순수 값 통합·누락 후보 계산을 담당하고 DB/서비스 조립 루트를 참조하지 않는다. `backend/service/intake.py`가 저장·추론·AI를 조정하고 `backend/gpt/intake.py`가 문맥 기반 모델 호출을 담당한다. `frontend/intake/{client,view}.js`와 `intake.css`는 동적 계약 소비·자동 저장·추가 질문 화면을 맡는다. [상세 계약](adaptive-intake.md)을 따른다.

`backend/ai_config.py`는 저장/SDK 의존이 없는 공통 AI 설정 계약이다. 서비스와 저장 계층은 이 순수 계약의 키/값만 소비한다. `backend/gpt/{client,intake}.py`는 같은 요청 옵션을 SDK에 전달하고, `frontend/ai-settings.js`는 get_settings.gpt_contract의 필드/타입/선택지로 내부 설정을 렌더링/저장한다. 모델명·추론 강도·시간/토큰 제한은 프론트/개별 AI 모듈에서 중복 정의하지 않는다.

사용자용 간편 홈 설정 영역과 상단 S10 설정 탭은 표시하지 않는다. `screens.js`의 S10은 내부 화면 계약으로 유지하고 메뉴 렌더링에서 제외하며, 저장된 AI·분석·UI 설정과 서비스 호출은 유지한다.

## 내부 PDF 출력 모듈 (2026-10-22)

사용자 출력 흐름은 Excel을 유지한다. 간편·고급 화면에는 PDF 모드·카드·버튼·미리보기 진입을 표시하지 않는다. 다음 PDF 모듈과 서비스 API는 호환을 위한 내부 구현으로 유지한다.

## 자세 엔진 공급자 분리

`backend/pose_contract.py`는 순수 설정/토폴로지 계약, `backend/pose/engine.py`는 파일/해시/출력 검증과 공통 결과 조립, `backend/pose/providers/{mediapipe,movenet}.py`는 실제 추론 adapter다. 서비스는 공통 process만 호출한다. `backend/engine/movenet.py`는 과거 직접 호출의 명시적 호환 진입점이다. `frontend/pose-settings.js`는 두 설정 화면의 필드/모델 선택을 공유한다. 33개 좌표/3D 추정은 결과 JSON에 기록하고 Excel/화면에 모델 및 별도 3D 참고 각도를 표시한다.

## 별지 1 PDF 출력 (2026-10-22 개정안)

- backend/report/form_mapping.py: 고정 snapshot → 원본 칸·앱용 미확정 안내. 규칙 계산 없음.
- backend/report/pdf.py: 원본 배경에 글자·체크·사진을 배치하고 칸을 넘는 작성 내용만 별첨 생성.
- backend/service/pdf_exports.py: 선택 검증·요청 순서의 snapshot 준비·PDF 미리보기/원자적 파일 교체·기존 출력 이력.
- frontend/pdf-export.js: 대상 고정·중복 요청 억제·저장 취소·실제 PDF 표시를 위한 내부 구현. 사용자 화면에서는 연결하지 않는다.
- templates/assets: 원본 해시, 빈 양식, PDF용 한글 글꼴과 라이선스.

`backend/intake/planner.py`는 현재 필요한 확인 범위의 처리/전체/남은 항목과 진행률 메타데이터를 계산하고, `backend/service/intake.py`가 `progress` DTO로 반환한다. `frontend/intake/dialog.js`는 이 값을 진행 막대와 남은 항목으로 표시하고 `intake.css`가 제목·본문 스크롤·하단 버튼의 배치를 분리한다. 계산 완전성 및 DB 저장 계약은 유지한다.

`backend/intake/grounding.py`는 AI가 제안한 숫자·단위와 허용된 작업시간 합산의 근거를 검증하는 순수 모듈이다. 항목별 derivations는 공통 catalogue에서 전달하며 계산 결과를 규칙 판정으로 만들지 않는다.


## 입력 저장 감사 7건 정정 (2026-10-23)

backend/intake/history.py는 원문 선택·회차 영수증·활성 미반영 진단을 담당하는 순수 모듈이다. frontend/drafts.js는 DB별/레코드 수명별 초안과 성공 확인을 공유하며 QuickFlow·AdaptiveIntake·고급 설명이 소비한다. frontend/intake/history-view.js는 지속 진단과 처리 이력을 렌더링한다. 서비스가 최신 입력에 늦은 응답을 재조정하고 계산/저장 계층을 조정한다. 상세는 [저장 계약](storage-persistence.md)을 따른다.


## 실호출 입력·출력 대조 정정 (2026-10-23)

backend/report/input_trace.py는 공통 입력 catalogue와 선택 snapshot의 facts로 값별 표시 출처·근거를 연결하는 순수 표시 모듈이다. 규칙 계산, DB 접근, 현재 입력/과거 snapshot 수정은 하지 않는다. plain.py의 조건/조건 행/수동 관찰/사진 표시가 같은 resolver를 소비한다. 상세는 [저장·출력 보존 계약](storage-persistence.md)을 따른다.
