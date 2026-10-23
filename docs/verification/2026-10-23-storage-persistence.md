# 저장 감사 잔여 7건 수정 검증 · 2026-10-23

수정 브랜치 `feat/mediapipe-heavy`, 이전 기준 `39738e5`(AUD-04 표현/합산 근거 수정 포함). 현재 origin/main의 Excel 기본 출력·사진 크롭·질문 묶음/진행률을 가져오는 작업과는 별도다. PR 생성/재개·push·main 병합·배포는 수행하지 않았다. 사용자 앱이나 기존 DB를 재시작/일괄 수정하지 않았고, OS 마우스·키보드를 조작하지 않았다.

| 감사 ID | 결함 | 변경과 검증 |
|---|---|---|
| AUD-01 | 새 분석이 미완성 조사와 원문을 삭제 | 삭제 호출 제거, 독립 초안 목록, 미완성 작업 열기. 실제 새 분석 후 이전 조사/원문/초안 2건 보존 |
| AUD-02 | 과거 UNKNOWN이 더 최신 값을 비움 | 최신 근거/USER 우선 검사를 UNKNOWN에도 적용. 480 보존·현재 명시 모름·직접값 우선·재시작 회귀 |
| AUD-03 | 구조화 수정으로 앞의 원문이 AI 문맥에서 밀림 | 자연어를 먼저 선택하고 기본적으로 전체 저장 원문 제공. 구조화 수정 12회·부분 추출 후 장문 12회·24,000자 초과 원문 포함 확인 |
| AUD-05 | 보내기 전 최초 설명이 사진 전/후 사라짐 | 작업 생성 전에도 DB별 독립 초안으로 즉시 보관. 사진 전/후 실제 앱 재실행과 팝업 미전송 답변 복구 |
| AUD-06 | 지연 자동 저장 전 종료하면 수정값 소실·성공 오표시 | 입력 시 로컬 pending 보관, base/value/version으로 복구/충돌/성공 확인. 480→420 재실행·0/null·재사용 ID·늦은 성공·쓰기 실패 검증 |
| AUD-07 | 설명 수정문이 재실행/목적/이력 전환에서 사라짐 | 분석/목적/텍스트 수명별 초안. 간편 재실행·고급 목적/이력 전환·재실행·명시적 저장과 적용 분리 검증 |
| AUD-08 | 미반영 숫자가 안 보이고 마지막 진단이 덮임 | 원문 메시지/회차/요청 phase/응답 ID/제안/결정 연결. 후속 응답/재시작 후 미반영 안내 유지, 직접 해결 후 활성 안내만 해소 |

지연 응답은 시간으로 폐기하지 않는다. 같은 작업에 최신 값을 기준으로 재조정하여 비충돌 새 정보는 반영한다. 충돌 제안·원문·응답 ID·이전 결정을 보관하고 최신 직접 값은 유지한다. 원래 질문의 단위 문맥도 유지하므로 늦은 숫자만의 답변을 단위 없는 제안으로 오판하지 않는다. 원문 한 문장에서 항목 하나를 추출했다고 나머지를 처리 완료로 간주하지 않는다. 기본 문맥 예산은 `None`이며 시간/최근 회수에 따른 만료가 없다.

## 수행한 검증

- 신규 `tests/test_intake_persistence.py` **11개**. 실제 Application Service/격리 SQLite에 제어한 모델 응답을 주입해 정정/과거 모름/문맥/회차/후속 응답/늦은 응답 재조정/전역 조건 정규화 반례를 검증했다. 처음 추가한 저장 회귀는 수정 전 실패 4건·오류 2건을 확인했다.
- 최종 Python 전체 **272개 통과**, skip 없음. `work/origin-main-audit/storage-backend-release.log`에 기록했다.
- 프론트 **15개 회귀 스크립트와 build 통과**. 신규 LocalDrafts/AdaptiveIntake 시험은 독립 초안, 손상/공간 부족, 0/null, 다른 화면 변경, 재사용 소유자, 늦은 성공 확인, 설명 목적/이력별 보관, HTML escape를 포함한다.
- `tests/storage-persistence-e2e.cjs`: `.local/storage-confirmed-ui-20261023/receipt.json`, **8개 실스택 확인, errors=[]**. Electron→Python→SQLite→실제 MediaPipe Heavy→Excel이다. OpenAI HTTP만 루프백 고정 응답이며 네이티브 파일 선택만 자동 지정했다.
- `tests/adaptive-intake-full-live.cjs`: `.local/storage-confirmed-live-20261023/receipt.json`, **9개 실스택 확인, errors=[]**. 실제 외부 **gpt-6-luna/xhigh**, Heavy 33개 관절, 입력/후속 답변/420 직접 수정/모름/재시작/설명 생성·적용/검토/Excel/재시작을 검증했다. 실제 응답 ID·모델·effort를 확인했다.
- 두 시험의 창은 x/y=-12000, focusable=false였다. OS 마우스/키보드 입력을 사용하지 않았다.
- `tests/verify_local_artifacts.py <시험 폴더> 1`을 두 폴더에 실행해 실제 SQLite 여섯 테이블·EXPORT_LOG snapshot·XLSX 시트·11개 판정 표시·33점 자세 결과를 독립 대조했다. 추가로 하루 420 분/일 셀과 적용된 설명 원문 셀의 정확한 일치도 확인했다. 고급에서 나중에 저장한 미적용 설명으로 출력의 적용 문장이 바뀌지 않았다.
- 계약 감사: 문서/구현 **48개**, renderer **41개**, 폐기 진입점 없음. `git diff --check` 통과.

첫 숨김 UI 실행은 새 처리 이력의 중첩 summary 때문에 시험 locator가 두 요소를 잡았고, 다음 locator 수정은 실제 DOM의 section/details 계층을 잘못 지정했다. 첫 외부 실행도 그 locator에서 중단했다. 실제 첫 details의 summary를 명시한 뒤 새 DB/프로필로 전체 검증을 통과했다. 실패 실행 폴더·로그는 최종 통과 증거와 구분해 남겼다. 앱 동작을 가짜 성공으로 바꾸지 않았다.

## 재현

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests
npm --prefix frontend test
npm --prefix frontend run build
npm --prefix frontend run test:storage:e2e
$env:LOCO_LIVE_AI='1'
$env:LOCO_LIVE_MODEL='gpt-6-luna'
$env:LOCO_LIVE_REASONING_EFFORT='xhigh'
npm --prefix frontend run test:adaptive:full-live
.\.venv\Scripts\python.exe tests/verify_local_artifacts.py <출력된 시험 폴더> 1
```

보내기 전 임시 초안은 해당 PC의 Electron 프로필에 속한다. DB만 다른 PC로 복사할 때 함께 이동하지 않는다. 기존에 이미 사라진 원문을 복원하거나 과거 분석을 일괄 재계산한 것은 아니다. 최신 main 통합·포터블 재빌드·배포·현장 추론 정확도 검증은 이 완료 범위에 포함하지 않는다. 기존 분석/출력 snapshot과 여섯 테이블은 보존했다. 상세 계약은 [저장 계약](../storage-persistence.md)을 따른다.
