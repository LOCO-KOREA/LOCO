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
