# LOCO Electron 화면

실제 진입점은 `desktop.html`과 네이티브 ES module `desktop.js`다. 개발 실행·의존성·모델·패키지 안내는 루트 [README](../README.md)를 따른다. `electron/main.cjs`는 공통 Python JSON Lines 서비스를 실행하고 `preload.cjs`는 파일 선택과 서비스 호출을 제공한다.

| 모듈 | 책임 |
|---|---|
| `task-workspace.js`, `task/` | 작업 defaults·편집 상태·11개 기준 view·저장·이벤트 |
| `photo-workspace.js`, `photo/` | 가변 사진·배정/관찰·재연결·상세 기록·단계 이동 |
| `survey-intake.js`, `survey/` | 조사 상황·근로자 참여·익명 증상 응답의 입력/표시/이벤트 |
| `dashboard.js` | 저장된 조사 목록·현재성 요약과 이동 |
| `analysis-workspace.js`, `analysis/` | workspace 조립·공유 labels/DOM/state·진행/REBA/판정/설명/출력/설정 view·canvas·actions·navigation |
| `review-links.js` | 누락 필드 이동·GPT 계산 근거·상세 전후 비교 표시 |

전역 가짜 API와 이전 SVG 목업·별도 저장 adapter는 제거했다. 각 workspace는 자기 편집 상태를 갖고, 작업 편집기는 소유 필드만 최신 DTO에 합치며 `expected_revision`으로 충돌을 확인한다. 사진/수동값·불변 분석 snapshot·설명 목적별 적용 이력을 보존한다.

```powershell
npm.cmd --prefix frontend test
npm.cmd --prefix frontend run build
npm.cmd --prefix frontend run test:electron
npm.cmd --prefix frontend run test:explanation
```

`build`는 실제 페이지의 자산·ES module import·문법을 검증한다. 배포 폴더 생성은 루트 `scripts/build_windows.py`가 담당한다. E2E는 별도 SQLite와 공개 예제 사진·합성 조사를 사용한다. 실제 외부 계정·현장 검증의 대체 증거가 아니다. [모듈 지도](../docs/module-map.md)와 [검증 대조표](../docs/local-verification.md)에 실행 범위와 남은 제약을 기록한다.

## 화면설계서 2.0 탐색 정렬

상단 메뉴는 S01 대시보드, S02 조사 목록·생성, S03 작업 목록·개요, S04 작업 조건·11개 기준, S05 사진 등록·배정, S06 자세 결과·REBA, S07 조사자 검토·GPT, S08 출력·전후 비교, S09 분석 진행, S10 설정입니다. `screens.js`가 메뉴와 작업 단계의 공통 기준입니다. 작업 개요와 기준 입력은 같은 작업 편집 상태를 공유합니다. S04의 저장 후 기준 초안 계산은 사진 없이 고시 초안만 재계산하고 S07로 이동합니다. 사진 분석은 S09로 이동하며 사진·태그·REBA를 요청합니다.

`npm run test:navigation`은 문서 화면 ID, 분석 진행/설정 화면 분기, 입력 화면 복귀 대기, 사진 없는 저장 후 계산, 로코 안내를 확인합니다.

## N01 삭제 확인

조사·작업 삭제는 이름과 ID, 삭제되는 DB 기록과 보존되는 원본 파일을 확인한 뒤 실행합니다. 취소·Esc는 삭제 요청을 보내지 않습니다. 삭제 중에는 확인창을 유지하고 중복 확인·취소를 막으며, 서비스 실패 시 편집 상태를 보존합니다. 작업 삭제는 기존 조사 출력 기록을 지우지 않습니다. 백업 선택은 서비스 연결 후 추가할 예정입니다. `npm test`에 삭제 확인 회귀 시험이 포함됩니다. 실제 Electron 화면·DB 사본 대조와 지정 교차 검증자의 확인은 별도 수행이 필요합니다.

## 공통 디자인

`design-system.css`는 마지막에 로드하는 공통 시각 기준입니다. 로고의 보라색, 상태 색상, 카드·컨트롤·입력 크기와 선택 표시를 한곳에서 관리합니다. 화면별 CSS는 공통 색상 토큰을 참조하며 그리드와 사진·표 전용 배치를 유지합니다. Pretendard는 기존 로컬 폰트를 사용합니다. 사진 관절 범례의 좌우 색상은 분석 의미를 보존합니다.

## 조사 편집과 TOP

S02의 새 조사·목록 항목·선택 조사 수정에서 중앙 편집창을 엽니다. 좌측 5개 항목은 같은 폼의 표시만 전환하므로 입력과 익명 응답을 유지합니다. 닫기·Esc는 임시 입력을 유지하며 DB 저장은 하지 않습니다. 저장 성공 후 작업 등록 화면으로 이동하고 실패 시 편집창에 오류를 표시합니다. 화면 내부의 중복 단계 탭을 제거하고 상단 메뉴로 이동을 통일했습니다. 각 페이지 왼쪽 아래에 TOP 버튼이 있습니다. 생성·수정 편집창에는 TOP 버튼을 두지 않습니다. 자동 시험은 편집 상태 유지·저장 중 닫기 방지를 확인하며 실제 창의 배치와 전체 Electron 흐름은 별도 시각 검증이 필요합니다.

버튼 간격은 일반 묶음 12px, 사진 행·후보의 작은 묶음 8px, 입력·본문에서 실행 버튼 묶음까지 20px입니다. 새 버튼 묶음은 `button-group` 또는 분석 영역의 `toolbar`를 사용하고, 본문 아래에는 `section-actions`를 함께 지정합니다. 좁은 폭에서는 줄바꿈하며 상단 메뉴·행 선택 버튼에는 본문 여백을 추가하지 않습니다.
