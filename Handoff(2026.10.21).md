# LOCO 작업 인계 — 2026-10-21

> 기준 저장소: `C:\Users\금정산2-PC02\LOCO` (git worktree. `carelink_fullstack`와 `.git`을 공유한다)
> GitHub 정본: `loco` → `https://github.com/LOCO-KOREA/LOCO.git`
> 작업 브랜치: `fix/quick-slot-side-and-smoke` (기반: `loco/main` `2a970469` = PR #21 병합 직후)
> 완성 목표: **2026-10-23 시연** (Asia/Seoul)
> 상태 단일 진실: 코드 + `AGENTS.md`가 정본으로 지정한 `docs/*.md`. 이 문서는 인계용 요약이며 정본을 대신하지 않는다.
> 판정 기준: `AGENTS.md`대로 **전체 수용은 NOT ACCEPTED**다. 아래는 이 브랜치가 추가·변경한 범위의 기록이다.

## 1. 오늘의 결론

오늘 작업은 다섯 축이고 모두 끝났다. 포터블도 깨끗한 커밋에서 다시 빌드해 패키지 검증까지 마쳤다(§9). 남은 것은 별도 PC·현장 확인이다.

1. **시연 사진 18장에서 나온 인식 문제 3건을 고쳤다.** 비스듬한 "정면" 사진이 옆모습으로 오판되던 것, 앉은 자세가 "쪼그려 앉기"로 제안되며 1차 점수가 부풀던 것, 왼쪽을 보는 사진이 먼 쪽 몸으로 측정되던 것.
2. **AI 한 줄 입력**을 만들었다. 작업을 한 문장으로 쓰면 AI가 질문 칸을 근거 구절과 함께 채우고, 사람은 값과 근거를 보고 고치거나 지운다. 빠진 칸만 다시 묻는다.
3. **Excel을 일반인이 읽는 말로 바꿨다.** 코드·내부 용어를 없앴고, 사용자 요청으로 "전문가용 상세기록" 시트를 삭제했다.
4. **결과 화면과 Excel 화면을 나누고 Excel 미리보기를 넣었다.** 미리보기는 저장되는 파일과 같은 시트 정의에서 만든다.
5. **유해요인조사표 공식 양식을 웹에서 다시 조사하고(§7), Excel을 그 구조로 다시 짰다**(§8). 첫 시트가 별지 제1호서식 구성의 `유해요인조사표`이고 그 뒤에 `부담작업 해당 여부`·`체크리스트`·`증상조사표`(응답이 있을 때)가 온다.

## 2. 한눈에 보기

| 항목 | 상태 | 비고 |
|---|---|---|
| 시연 사진 인식 3건 | 완료·검증 | §3. 현장 사진 일반화는 미검증 |
| AI 한 줄 입력 | 완료·검증 | §4. 실제 OpenAI로 E2E 통과 |
| 일반인용 Excel, 전문가용 시트 삭제 | 완료·검증 | §5 |
| 결과/Excel 화면 분리, Excel 미리보기 | 완료·검증 | §6 |
| 공식 양식 조사 | 완료 | §7 |
| Excel을 공식 양식 구조로 재배열 | 완료·검증 | §8. 시트 정의·파일·미리보기가 같은 구조 |
| 사양서·검증 기록 갱신 | 완료 | 정본 문서(API 계약서·기능정의서·화면설계서·DB 아키텍처·ERD·요구사항·모듈 지도)와 `docs/verification/2026-10-21-simple-flow.md` |
| 포터블 재빌드·패키지 E2E | 완료·검증 | 깨끗한 커밋 `a57b3835`에서 빌드. `dist\LOCO-2.0-windows-x64-20261021T091456468494Z` (경로는 `.local/latest-package.txt`) |

## 3. 사진 인식 보정

시연용 사진 18장(`C:\Users\금정산2-PC02\Documents\카카오톡 받은 파일\KakaoTalk_20261016_163049235*.jpg`, 저장소에 없음)으로 점검해 나온 문제와 처리다. 사용자 지적은 "사람들이 완벽하게 정면을 보겠냐?"였다. 기울어진 사진을 사용자 잘못으로 돌리지 않고 프로그램이 받아들이게 했다.

| 문제 | 원인 | 처리 |
|---|---|---|
| 비스듬한 "정면" 사진(#7, #10)이 옆모습으로 판정됨 | 방향을 정면/옆 두 갈래로만 봤다 | 방향을 **정면·비스듬·옆 3단계**로 판정하고, 사용자가 고른 칸(slot)을 존중한다. 비스듬하면 측정은 하되 신뢰를 낮춘다 |
| 앉은 자세(#12~#17)가 "쪼그려 앉기"로 제안되고 1차 점수가 부풂 | 앉은 자세를 몰랐다 | `seated_signal`: 허벅지가 수평에서 30° 이내이고 (발목y−엉덩이y)/허벅지 길이 ≥ 0.95이면 앉은 자세. 무릎 굽힘 제안을 억제하고 다리 점수를 부풀리지 않는다 |
| 왼쪽을 보는 사진(#2, #8)이 먼 쪽 몸으로 측정되고 "칸 확인" 문구가 혼란스러움 | 신뢰도 차이로 근측을 골랐다 | **보는 방향으로 가까운 쪽을 정한다**(오른쪽을 보면 오른쪽 몸). 반대쪽 신뢰도가 0.6 이상 높을 때만 뒤집는다 |
| 타이핑 자세(위팔 51~58°)가 "팔이 머리 위"로 읽힘 | REBA 45° 태그를 그대로 썼다 | 작업유형 `arm_raised`는 **위팔 90° 이상**일 때만 켠다. 머리 위 신호는 별도(`arm_overhead_signal`) |

**상수** (`ergo/engine/quick_assess.py`)

| 이름 | 값 | 뜻 |
|---|---|---|
| `FRONT_SHOULDER_RATIO`, `FRONT_HIP_RATIO` | 0.65, 0.45 | 어깨·엉덩이 폭 ÷ 몸통 길이가 이 이상이면 정면 |
| `SIDE_SHOULDER_RATIO`, `SIDE_HIP_RATIO` | 0.35, 0.20 | 이 미만이면 옆모습. 그 사이는 비스듬 |
| `NEAR_SIDE_OVERRIDE` | 0.6 | 보는 방향 규칙을 뒤집는 신뢰도 차이 |
| `SEATED_THIGH_FLAT_DEG`, `SEATED_HIP_ABOVE_ANKLE` | 30, 0.95 | 앉은 자세 판정 |
| `OVERHEAD_WRIST_ABOVE_SHOULDER`, `OVERHEAD_ELBOW_ABOVE_SHOULDER` | 0.25, 0.05 | 손목·팔꿈치가 어깨보다 몸통 길이의 이만큼 위 |
| `ARM_OVERHEAD_DEG` | 90 | `arm_raised` 질문 기준 위팔 각도 |

함수: `guess_view`, `seated_signal`, `arm_overhead_signal`, `side_measure(..., slot_view=None, oblique=False)`, `provisional(..., seated=False)`, `posture_signals`, `work_type_question`. 서비스 연결은 `ergo/service/quick.py`의 사진별 루프(3단계 방향, `signals.update(seated=True, knee_bent=False)`)다.

**시험:** `tests/test_quick_assess.py` 28개. 가상 좌표로 비스듬·앉음·왼쪽 향함·타이핑 자세를 각각 반례로 둔다.

**한계:** 정면 판별 기준값(0.65/0.45 등)은 공개 예제와 위 18장으로만 맞췄다. 현장 사진 일반화는 확인하지 못했다.

## 4. AI 한 줄 입력

**사용자 흐름.** 질문 단계 첫 화면에서 작업을 한 문장으로 쓰고(예: "하루 4시간 키보드를 쓰고 20kg 상자를 30번 든다") "AI가 정리하기"를 누른다. AI가 채운 칸이 **근거 구절과 함께** 나오고, 값 하나씩 지우거나(`dropIntake`) 전체를 되돌릴(`undoIntake`) 수 있다. 문장이 채운 칸은 묻지 않고 **빠진 칸만** 묻는 압축 화면(`viewQuestionsCompact`)으로 넘어간다.

**서버.** 메서드 `quick_interpret`(문장 1~600자, 저장하지 않음, 응답 `{items, dropped, reason}`).

| 파일 | 역할 |
|---|---|
| `ergo/engine/quick_intake.py` | `catalogue()`(채울 수 있는 칸 목록), `prompt_targets()`, `schema()`(엄격한 structured output), `validate()` |
| `ergo/gpt/client.py` | `INTAKE_PROMPT_VERSION = 'LOCO_INTAKE_V2'`, `interpret(...)`, `warm_up()` |
| `ergo/service/quick.py` | `handle_quick_interpret` |
| `ergo/service/json_lines.py` | 시작 때 `warm_up`, `quick_interpret`는 별도 스레드 |
| `ergo/contracts.py`, `docs/API_계약서.md` | 계약 등록(문서화 메서드 43개) |

**지키는 규칙.** 모델은 아무것도 판정하지 않는다. 채울 수 있는 칸은 `work_type.*`, `card.<gate>.<field>`, `daily_work_min`, `annual_work_days`, `one_off`, `task_name`뿐이다. `validate()`가 다음을 걸러낸다.

- 근거 구절이 입력 문장에 **그대로** 있어야 한다.
- 숫자는 근거에 숫자 또는 한글 수사(한·두·세·…·반)가 있어야 한다.
- 칸별 범위(`maximum`), 중복, 최대 60개(`MAX_ITEMS`).
- 예/아니오 카드 답은 해당 작업유형이 켜져 있어야 한다. 숫자 카드 값은 작업유형을 자동으로 켠다.
- 걸러진 값은 `dropped`로 알리고, 사유(`reason`)는 `DISABLED`, `NO_API_KEY`, …, `NOTHING_FOUND` 등으로 돌려준다.

**성능.** 첫 호출이 33초 걸렸다(openai import 약 14초). `warm_up()`이 서비스 시작 때 백그라운드로 import해서 줄였다.

**키.** 환경변수 `OPENAI_API_KEY`(사용자 환경). 문서·로그·화면에 값을 남기지 않는다.

**실제 UI에서 잡은 결함.** ① `data-intake` 속성이 고급 편집의 textarea와 충돌 → `data-quick-intake`로 변경. ② 입력 중에는 화면을 다시 그리지 않아 버튼이 안 켜짐 → input 핸들러에서 `disabled`를 직접 토글.

**시험.** `tests/test_quick_intake.py` 19개, `tests/frontend-quick-answers.cjs`(채움·사람 답 유지·지움·완전히 답한 칸만 해결), `.local/try/intake.cjs`(실제 OpenAI E2E: 압축 화면, 지우기, 결과값 240분·20kg×30회).

## 5. 일반인용 Excel

**원칙.** Excel은 일반인이 읽는다. 저장 코드·내부 용어(`MoveNet`, 기술태그, 스키마, `UNKNOWN` 등)를 쓰지 않는다. 법정 번호는 "이름(법정 N호)"로만 적고 문장 앞에 번호를 세우지 않는다. 숫자에는 단위를 붙인다. 시각은 한국 시각(KST) 문장으로 쓴다.

**구조.** `ergo/report/plain.py`의 `plain_sheets(snapshot, ov)`가 시트 정의 `{name, title, lead, tables:[{heading, columns, rows, widths}], notes}` 목록을 돌려준다. 이것을 **파일 작성**(`ergo/report/renderer.py::_write_sheet`)과 **화면 미리보기**(서비스 `preview_excel_sheets`)가 함께 쓴다. 그래서 미리보기와 파일이 같다. 대표 사진 이미지만 파일에만 들어간다. 모든 문자열 셀은 `data_type='s'`로 고정해 수식 실행을 막는다.

**현재 시트.** 앞쪽이 공식 서식 구성이다: `유해요인조사표`, `부담작업 해당 여부`, `체크리스트`, `증상조사표`(익명 응답이 있을 때만). 뒤쪽은 `자세 분석(REBA)`, `입력한 값`, `확인사항`이고, 조건부로 `쉬운 설명`(적용한 AI/조사자 설명이 있을 때)과 `개선 전후 비교`(비교를 골랐을 때)가 붙는다. 시트 구성은 §8이다. 옛 `요약`·`기준별 결과`·`사진 자세`와 DISEASE_CASE 전용 `별지1`·`별지2`(`statutory_forms.py`)는 이 구조로 흡수하고 지웠다.

**전문가용 상세기록 삭제 (2026-10-21, 사용자 요청).** `ergo/report/expert.py`를 지우고 `workbook.py`의 `EXPERT_SHEET`, 미리보기 응답의 `expert_sheet`, 화면 안내 문구, 고급 편집 내보내기 화면의 시트 목록, `docs/API_계약서.md`의 해당 서술을 정리했다. DB에 저장된 원본 값과 경로, 출력 snapshot은 그대로다. 감사 추적이 필요하면 `export_log`의 snapshot을 읽는다.

**용어 자료.** `ergo/report/labels.py`(`MANUAL`, `EXPOSURES`, `CRITERIA`, `criterion_name`, `josa`, `MODULE_PLAIN`, `INCOMPLETE`, `AI_REASON_KO`, `RESULT_LABELS`, `unit_for`), `ergo/report/display.py`(상태·값·단위 한글표), `ergo/report/overview.py`(확인사항 문장. 조사 `이/가`를 받침으로 고른다).

**시험.** `tests/test_plain_report.py` 12개(코드·내부 용어 정규식 검사, 11개 기준 행, 입력한 값, 시각 형식, 조사, 미리보기 = 파일, 미리보기가 아무것도 바꾸지 않음, 쉬운 설명 시트, 전후 비교). 사진 시험(`PhotoWorkbook`)은 `.local/fixtures`와 `models/movenet_lightning.tflite`가 있을 때만 돈다.

## 6. 화면 분리와 Excel 미리보기

흐름이 **6단계**가 됐다: 사진 넣기 → 1차 점수 → 로코 질문 → **결과** → **검토·설명** → **Excel**.

| 화면 | 내용 | 코드 |
|---|---|---|
| 결과 | 11개 기준 결과, 해당하지 않는 기준은 접어서 보여줌, 값에 따른 근거 | `viewResult`, `resultSummary` |
| 검토·설명 | 조사자 결론·검토 표시, AI 설명 생성·편집·적용 | `viewReview`, `openReview` |
| Excel | "Excel 만들기 전 확인" 점검표, **시트 탭 미리보기**, 저장, "개선 후 다시 비교" | `viewExcel`, `excelPreviewPanel`, `checklistPanel`, `comparePanel`, `openExcel` |

저장 버튼은 Excel 화면에만 있다(검토 화면에는 없다). 파일: `frontend/quick-flow.js`(1057줄), `frontend/quick.css`, `frontend/desktop.js`(부제 "… → 결과 → 검토·설명 → Excel"). 단계 목록은 `STEPS`다.

## 7. 유해요인조사 공식 양식 조사 결과

사용자 지시("유해요인조사 자료 양식을 웹에서 다시 찾아보고 와")에 따라 조사했다. **공식 서식 원본은 HWP뿐이고 공식 xlsx는 없다.** 아래는 이번에 서식 페이지를 직접 렌더링해 읽은 구조다.

### 7.1 근거

- **고용노동부고시 제2020-12호** 「근골격계부담작업의 범위 및 유해요인조사 방법에 관한 고시」. 별지 제1호서식 **유해요인조사표**, 별지 제2호서식 **근골격계질환 증상조사표**(2018.2.9 신설 서식). 정의: 단기간 작업 = 2개월 안에 끝나는 1회성 작업, 간헐적 작업 = 연간 총 작업일수 60일 이하, 하루 = 1일 소정근로시간+연장근로시간 동안의 작업시간.
- **산업안전보건기준에 관한 규칙 제657~658조.** 정기조사 3년마다(신설 사업장은 1년 이내 최초 조사), 수시조사 사유 3가지(근골격계질환자 발생·업무상 질병 인정 / 새 작업·설비 도입 / 업무량·작업공정 등 작업환경 변경), 근로자대표 또는 해당 작업 근로자 참여. 조사 결과 서류는 5년 보존한다고 조사 중 확인했다. ⚠ 조문 번호·기한(수시조사 "1개월 이내" 표현 포함)은 요약본으로 확인한 것이라 **구현에 쓰기 전 원문과 대조**한다. 2026년 개정안 소문은 확정 근거를 찾지 못했다.
- **KOSHA GUIDE H-9-2022**(근골격계부담작업 유해요인조사 지침)와 **E-G-1-2025**(근골격계질환 예방에 관한 기술지원규정, 2025.3, 한국산업안전보건공단)가 별지 서식을 확장한다. **E-G-1-2025가 가장 새로우므로 Excel은 이 판을 기준으로 한다**(§7.3).

### 7.2 별지 제1호서식 유해요인조사표(고시, 4쪽)

- **가. 조사 개요**: 조사일시, 조사자, 부서명, 작업공정명, 작업명.
- **나. 작업장 상황 조사**: 작업설비(□변화 없음 □변화 있음(언제부터)), 작업량·작업속도·업무변화(□변화 없음 □줄음 □늘어남 □기타).
- **다. 작업조건 조사(인간공학적 측면)**
  - 1단계: 작업명, 작업내용(단위작업명) 1)·2)·3).
  - 2단계: 작업부하(A) 1~5점(매우 쉬움·쉬움·약간 힘듦·힘듦·매우 힘듦) × 작업빈도(B) 1~5점. 표: 단위작업명 / 부담작업(호) / 작업부하(A) / 작업빈도(B) / 총점수(A×B).
  - 3단계 유해요인평가: 작업명, 근로자명, 단위작업별 사진 또는 그림, **작업별 관찰된 유해요인에 대한 원인분석**(단위작업명, 부담작업(호), 표: 유해요인 / 발생 원인 / 비고).
- **작성방법** 쪽: 유해요인은 반복동작, 부자연스런(부적절한) 자세, 과도한 힘, 접촉스트레스, 진동, 기타요인으로 나눈다.

### 7.3 KOSHA GUIDE가 더한 것 — E-G-1-2025(2025.3, **기준판**)와 H-9-2022(이전판)

E-G-1-2025의 별지 제1호서식(문서 쪽번호 49~53쪽)이 가장 새롭고 앱의 질문 구조(작업장 상황 4가지, 작업강도·작업빈도)와 맞다. **Excel은 이 판을 기준으로 하고**, 이전판과 다른 점은 아래에 적는다.

- **가. 조사 개요**: 조사구분 □정기조사 □최초조사 □수시조사(규칙 제657조 2항에 근거). 수시조사 아래에 □근골격계질환자 발생시, 근로자가 근골격계질환으로 업무상 질병으로 인정받은 경우 □근골격계부담작업에 해당하는 새로운 작업·설비를 도입한 경우 □근골격계부담작업에 해당하는 업무의 양과 작업공정 등 작업환경을 변경한 경우. 이어서 조사 일시·조사자, 조사부서명, 작업공정명, 작업명.
- **나. 작업장 상황 조사**: 작업설비·작업량·작업속도·업무형태 4행, 각각 □변경 없음 □변경 있음(주요 변경 내용: ).
- **다. 작업조건 조사**: 1단계(작업명, 작업내용(단위작업명) 1)·2)·3))는 고시 별지와 같다. 2단계 이름이 **작업강도(A)**(매우 쉬움 1·쉬움 2·약간 힘듦 3·힘듦 4·매우 힘듦 5)와 **작업빈도(B)**(매우 가끔(년 2~3회) 1·가끔(하루 또는 주 2~3일에 1회) 2·자주(1일 4시간 미만) 3·계속(1일 4시간 이상) 4·초과근무 시간(1일 8시간 이상) 5)이고, 표는 단위작업명 / 부담작업(호) / 작업강도(A) / 작업빈도(B) / 총점수(A×B)다. 3단계(작업명·근로자명, 단위작업별 사진 또는 그림, 원인분석 표)는 고시 별지와 같다.
- **3-1. 인간공학적 작업·분석 평가 결과표**(※ 세부적인 작업분석평가가 필요한 경우 사용): 작업명·단위작업명, 분석평가 사진(단위작업별 작업모습), 표 [작업·분석평가도구 / 평가결과 / 판정].
- **라. 유해요인 조사 결과**: "결과 요약" 한 칸(자유 서술).
- **부록 3 근골격계부담작업 체크리스트 양식**(문서 쪽번호 42쪽): 머리에 사업장명·조사 일시·조사자·공정명·공정 내용. 열이 1~11호이고 행이 노출시간·노출빈도·신체부위·작업자세 및 내용·무게다. 그 아래 **단위작업명(  명)** 행마다 호별로 표시한다. 정확한 문구는 구현 때 원문 쪽번호 42쪽에서 옮긴다.
- **부록 4**: 해당 여부 판단 예시(아래 부록 1과 같은 표). **부록 5** 인간공학적 평가도구(RULA·REBA·NIOSH 등), **부록 6** 작업환경 개선 계획표 양식.

**H-9-2022(이전판)와 다른 점**: 2단계가 작업부하(A)이고 B열이 "계절마다(연 2~3회)···자주(1일 4시간 이하)"이며 단위작업명 칸에 **인원**도 적는다. 나 항목이 "변화 없음/변화 있음(내용요약)" 5행(기타 포함)이다. 3단계 머리글이 "유해요인의 발생원인 또는 노출특징"이다. "4. 종합요약" 칸이 있다(E-G-1-2025는 라. 결과 요약으로 바뀜). 조사 구분에 최초조사가 없다.

**부록 1 「근골격계부담작업 해당 여부 판단」(H-9-2022 예시. E-G-1-2025 부록 4와 같은 표)**: 호마다 법정 문구, 부담작업 예, 그리고 표 **[부담작업 요소(유해요인) / 하루 총 노출시간 / 요소별 부담작업 여부(○ 또는 X와 기준 미만 사유) / 최종판단결과(부담작업·부담작업 아님)]**. 각주: "신체부위별 동일조직(근육, 힘줄, 인대 등)에 기준시간 이상 동안 영향을 미칠 경우 부담작업으로 판단", 3호는 개별 동작을 합산한다.

### 7.4 11개 호 ↔ 유해요인 분류 (H-9-2022 부록 1 예시 기준)

| 호 | 앱 표시 이름(`labels.CRITERIA`) | 서식의 유해요인 분류 |
|---|---|---|
| 1 | 키보드·마우스 집중 입력 | 반복동작 |
| 2 | 같은 동작 반복 | 반복동작 |
| 3 | 손·팔의 부담 자세 | 부적절한 자세 (개별 동작을 **합산**해 판단) |
| 4 | 목·허리 굽힘·비틀림 | 부적절한 자세 |
| 5 | 쪼그림·무릎 굽힘 | 부적절한 자세 |
| 6 | 한 손 손가락 집기 | 과도한 힘(집기) |
| 7 | 한 손 들기·쥐기 | 과도한 힘(잡기) |
| 8 | 25kg 이상 들기 | 과도한 힘(들기) |
| 9 | 10kg 이상 불편한 위치 들기 | 과도한 힘 + 부적절한 자세 |
| 10 | 반복 들기 | 과도한 힘 + 반복성 |
| 11 | 손·무릎 충격 | 접촉스트레스 |

### 7.5 별지 제2호서식 근골격계질환 증상조사표(고시, 2쪽 / H-9-2022 동일 구성)

- **Ⅰ 기본 정보**: 성명, 연령, 성별, 현 직장경력, 작업부서(부·라인·작업), 결혼여부, 현재 작업(내용·기간), 1일 근무시간(휴식 분씩 몇 회), 현작업 전 작업(내용·기간). 문항 1 규칙적 여가·취미(컴퓨터·악기·뜨개질·운동 등), 2 가사노동 시간, 3 진단 경험(류머티스 관절염·당뇨병·루프스병·통풍·알코올중독 / 완치·치료 중), 4 사고 상해 부위, 5 육체적 부담 정도(5단계).
- **Ⅱ 지난 1년 통증**: 6개 부위(목·어깨·팔/팔꿈치·손/손목/손가락·허리·다리/발) 열 × 6개 문항(구체적 부위 / 통증 기간 / 아픈 정도(약한·중간·심한·매우 심한) / 지난 1년 빈도(6개월에 1번~매일) / 지난 1주일 증상 / 통증으로 인한 조치(병원 치료·약국·병가 산재·작업 전환·기타)).
- 유의사항: 증상을 과대·과소 평가하지 않는다. 증상조사 결과는 질환을 부정·입증하는 근거나 반증자료로 쓸 수 없다.

### 7.6 REBA 위험 단계

앱의 `risk` 5단계와 같다: 점수 1 무시 가능, 2~3 낮음, 4~7 보통, 8~10 높음, 11~15 매우 높음(표준 REBA 조치수준). 서식 3-1의 "판정" 문구로 쓸 때는 표준 조치 표현(조치 필요 없음 / 변화가 필요할 수 있음 / 추가 조사하고 곧 개선 / 조사하고 개선 필요 / 즉시 개선)을 쓰되 **앱의 판정이 아니라 표준 해석**임을 시트 주석에 밝힌다.

### 7.7 앱이 모르는 항목(빈칸으로 두거나 있는 값만 채운다)

| 서식 항목 | 앱 현황 |
|---|---|
| 작업강도(A)·작업빈도(B) | 고급 편집 `conditions.work_intensity`, `work_frequency`가 있으면 채운다. 간편 흐름은 비어 있다 → **빈칸(직접 기입)** |
| 단위작업 | 개념 없음 → **작업 = 단위작업 1개**로 취급 |
| 근로자명 | `conditions.worker_code`(표시명)만 있다. 실명은 받지 않는다 |
| 작업장 상황 "기타" 행 | 없음 → 빈칸 |
| 증상조사표 빈도·조치 문항 | 저장 필드 없음 → 빈칸 |
| 결과 요약(종합요약) | 조사자가 직접 쓰는 칸 |

### 7.8 출처(조사에서 열어본 것)

- 고시 안내 페이지(본문은 첨부 HWP): `https://www.moel.go.kr/info/lawinfo/instruction/view.do?bbs_seq=20200100345`
- 서식 PDF 사본(비공식 미러): `blog.occupationalhealthblog.net`의 `별지-1-유해요인조사표…pdf`, `별지-2-근골격계질환-증상조사표…pdf`(2022/11 업로드), `H-9-2022_근골격계부담작업-유해요인조사-지침.pdf`(2023/03). 공식 HWP와 대조는 하지 못했다.
- **KOSHA GUIDE E-G-1-2025 원문**(공식. 한국산업안전보건공단 자료실 PDF, 이번에 렌더링해 읽은 기준판): `https://oshri.kosha.or.kr/kosha/info/koshaGuideData.do?mode=download&articleNo=453891&attachNo=261185`
- 산안규칙 제657조(국가법령정보센터 조문 링크): `https://www.law.go.kr/LSW/lsLawLinkInfo.do?lsJoLnkSeq=1000727571&chrClsCd=010202`
- 지청 자료실 양식: `moel.go.kr/local/seoulgwanak/…bbs_seq=1507784282302`(유해요인조사서식(방법).hwp, 2017), `moel.go.kr/local/boryeong/…bbs_seq=1441949310716`(체크리스트·증상조사표 포함 hwp, 2015)
- 고시 요약(정의 조항): U-LEX 사본(비공식)

## 8. 공식 양식 구성 Excel (구현 완료)

Excel의 앞쪽 시트가 고시 별지 제1·2호서식(KOSHA GUIDE E-G-1-2025 판) 구성을 따른다. 코드: `ergo/report/form.py`(시트 정의), `ergo/report/plain.py::plain_sheets`(시트 순서), `ergo/report/renderer.py`(파일 쓰기), `frontend/quick-flow.js::excelPreviewPanel`(화면 미리보기). 같은 시트 정의 하나에서 파일과 미리보기를 만들므로 둘은 같다(`tests/test_plain_report.py`가 미리보기의 모든 값이 파일에 있는지 대조한다). 칸 모양은 Excel로 실제 인쇄 미리보기(PDF 내보내기)를 뽑아 눈으로 확인했다. 사용자가 이 구조로 가기로 한 것이 아니라 "양식을 다시 찾아보고 오라"는 지시를 따라 내가 정한 기본값이므로, 바꾸고 싶으면 §8.1·§8.2만 고치면 된다.

### 8.1 시트 순서

| # | 시트 | 근거 서식 | 조건 |
|---|---|---|---|
| 1 | `유해요인조사표` | 별지 제1호서식(E-G-1-2025 판) | 항상 |
| 2 | `부담작업 해당 여부` | E-G-1-2025 부록 4(= H-9-2022 부록 1) 판단 서식 | 항상 |
| 3 | `체크리스트` | E-G-1-2025 부록 3 체크리스트 양식(작업 × 11개 호) | 항상 |
| 4 | `증상조사표` | 별지 제2호서식 | 증상조사 응답이 있을 때 |
| 5 | `자세 분석(REBA)` | 3-1 결과표의 상세 | 항상 |
| 6 | `입력한 값` | — | 항상 |
| 7 | `확인사항` | — | 항상 |
| 8 | `쉬운 설명` | — | 적용한 설명이 있을 때 |
| 9 | `개선 전후 비교` | — | 비교를 골랐을 때 |

1~4번에는 탭 색(`1F3A5F`)이 붙는다. 모든 시트의 둘째 줄에 `조사: 이름 · 조사일 · 출력 시각`이 들어간다(옛 `요약`이 보여 주던 값).

### 8.2 `유해요인조사표` 칸 매핑

| 서식 칸 | 앱 데이터 |
|---|---|
| 조사 구분 ☐정기조사 ☐최초조사 ☐수시조사(규칙 제657조 2항에 근거) | `survey.survey_type` (REGULAR / INITIAL / OCCASIONAL) |
| 수시 사유 ☐질환자 발생·업무상 질병 인정 ☐새 작업·설비 도입 ☐업무량·작업공정 등 작업환경 변경 | `survey.occasional_cause` (DISEASE_CASE / NEW_TASK_OR_EQUIPMENT / WORK_ENVIRONMENT_CHANGE). OTHER이면 세 칸은 ☐로 두고 "사유: 기타 · `occasional_reason` 글"을 아래에 적는다 |
| 조사 일시·조사자·조사부서명·작업공정명 | `survey_date`, `investigator`, `department`, `process` |
| 작업명 | 작업들의 `task_name`(여러 개면 줄바꿈) |
| (추가) 이전 조사일, 근로자 참여 | `previous_survey_date`, `participation`(status·role·method·date·notes·participant_code). 기록이 없으면 "입력 필요"(주황) |
| 나. 작업장 상황(설비·작업량·작업속도·업무형태) | `workplace_situation.{equipment,workload,speed,work_pattern}_{status,notes}`. NO → ☑변경 없음, YES → ☑변경 있음 + 주요 변경 내용(없으면 "입력 필요"), UNKNOWN → 둘 다 ☐ 이고 내용 칸에 "입력 필요". 서식에 "기타" 행은 없다 |
| 1단계 작업명·작업내용 | `task_name`, 작업내용은 "1) 작업명"과 `conditions.method_description` |
| 2단계 척도 표 | 고정 문구(E-G-1-2025 표기, §7.3) |
| 2단계 표: 단위작업명 | `task_name` (앱에 단위작업 개념이 없어 작업 = 단위작업 1개) |
| 부담작업(호) | 최종 상태 `APPLICABLE`인 호("1, 4"). 미확정(`NEEDS_INPUT`/`NEEDS_REVIEW`)이 있으면 "(미확정 N개)"를 덧붙인다. 확정된 호가 없고 미확정만 있으면 "확정된 호 없음", 전부 해당하지 않으면 "해당 없음", 판정 전이면 "계산 전" |
| 작업강도(A)·작업빈도(B)·총점수 | `conditions.work_intensity`, `work_frequency`(1~5 정수), 둘 다 있을 때만 A×B. 없으면 빈칸(직접 기입). **간편 흐름은 이 두 값을 묻지 않아 빈칸이다** |
| 3단계 근로자명 | `conditions.worker_code` (실명은 받지 않는다) |
| 3단계 사진 또는 그림 | 대표 사진(파일에만. `include_representative`가 꺼져 있으면 "대표 사진 이미지는 포함하지 않았어요.", 대표 사진이 없으면 "대표 사진이 없어요") |
| 원인분석 표: 유해요인 | §7.4 분류 + 호. 예 "반복동작(1호)". 해당한 호마다 1행. 사용자가 그 작업을 한다고 답했지만 값이 모자란 호도 "입력 필요"/"검토 필요" 비고와 함께 올린다 |
| 원인분석 표: 발생원인 또는 노출특징 | 판정 근거의 입력값 문장(예 "집중 키보드·마우스 사용: 240 분/일"). 값이 비어 판정에 꼭 필요한 입력은 "입력 필요: …"로 덧붙인다 |
| 원인분석 표: 비고 | 입력 필요·검토 필요·조사자 결론 |
| (고급 입력이 있으면 행 추가) | `conditions.hazard_factors`, `hazard_causes` ("관찰한 유해요인", "유해요인의 원인"). `improvement_recommendations`는 이 시트에 없고 `입력한 값`에 있다 |
| 3-1 인간공학적 작업·분석 평가 결과표 | REBA 점수가 있을 때만. 도구 "REBA(전신 자세 평가)", 평가결과 "N점 (위험도)"와 계산한 사진 수, 판정은 표준 REBA 조치 문구(§7.6) |
| 라. 유해요인 조사 결과(결과 요약) | 작업별 표 [작업·부담작업(호)·자세 점수(REBA)·더 입력/검토할 것(건수와 먼저 할 일)·결과 기준과 검토 상태], 증상조사 요약 행(방법·조사일·응답자 수·`symptom_survey.summary`, 없으면 "입력 필요"), "조사자 종합 의견(직접 쓰는 칸)" 빈 칸 |

인쇄는 가로 한 쪽 폭에 맞추고 "다. 작업조건 조사", "3단계", "3-1", "라" 앞에서 쪽을 나눈다. 시트 맨 아래 주석에 참고 자료이며 공식 서식을 대신하지 않는다는 말과 "판정"이 REBA 표준 해석이라는 말을 적는다.

### 8.3 시트 2·3·4

- **부담작업 해당 여부(2)**: 작업마다 11개 호 블록. 블록 제목은 "이름(법정 N호) → 최종 판단: 부담작업/부담작업 아님/입력 필요/검토 필요/제외", 첫 줄은 법정 기준 문구(`labels.CRITERION_RULE`), 그다음 표 [부담작업 요소 / 입력한 값 / 기준 / 요소별 해당 여부]에 입력 하나가 한 줄(○ 기준을 채움, X 못 미침). 여러 조건 행이 있으면 "(조건 2)"를, 하루 합계는 "하루 합계 · …"를 붙인다. 값이 비어 있어도 **계산이 그 입력을 필요로 할 때만** "입력 필요"(주황)이고 아니면 "입력 안 됨"이다(예: 4호가 이미 해당이면 다른 시간 칸은 비어도 "입력 안 됨"). 조사자 결론·더 필요한 입력·확인할 점은 있을 때만 블록 아래 줄로 붙는다(옛 `기준별 결과`의 계산 초안·조사자 결론·검토자·검토 시각·확인할 점을 잃지 않는다).
- **체크리스트(3)**: 머리 정보(사업장명(앱에 없어 빈칸)·조사 일시·조사자·공정명·공정 내용(빈칸)·작업명), 열 = 1~11호, 첫 줄은 호별 기준(`form.CHECK_RULE`), 작업마다 ○ / X / 입력 필요 / 검토 필요 / 제외와 마지막 열 "부담작업 여부"(부담작업·부담작업 아님·미확정·계산 전).
- **증상조사표(4)**: 응답마다 "응답 N · 코드" 블록 — 기본 정보 표(성명(선택)·연령·성별·현 직장 경력·작업부서·현재 작업·1일 근무시간·이전 작업·여가·가사노동·진단·사고·육체적 부담)와 6개 부위 열 × (구체적 부위·통증 기간·아픈 정도·지난 1주일) 표. 앱에 입력란이 없는 "지난 1년 빈도"와 "통증으로 인한 조치" 문항은 표에 넣지 않았다고 주석에 적는다. 개인정보 주의와 "증상조사 결과는 질환을 인정·부정하는 근거로 쓰지 않는다" 문구를 유지한다.

### 8.4 표 정의의 선택 키 (렌더러·미리보기 공통)

기존 시트 정의 `{heading, columns, rows, widths}`에 하위 호환되는 선택 키를 더했다(`docs/API_계약서.md` §8에도 적었다).

- `header: False` 헤더 행 없음. `labels`(열), `label_rows`(행), `label_cells`([행, 열]) 양식의 칸 이름 칸(굵게·연회색). `merges` [[첫 행, 첫 열, 끝 행, 끝 열]] 병합(행·열은 표 안 0부터). `bordered` 테두리. `heights` {행: 높이(pt)}. `break` 이 표 앞에서 쪽 나눔. `photo` {task_id, row} 대표 사진을 넣을 칸. 시트의 `tab_color`.
- `renderer._write_sheet`는 행 번호를 자기가 세는 `put()`으로 센다. (`ws.max_row`는 빈 줄을 세지 않아 머리 행이 없는 표의 병합이 한 줄 위로 어긋난 적이 있다 — 2026-10-21에 잡았고 `test_merged_blocks_sit_on_the_rows_the_preview_says`가 지킨다.)
- 미리보기(`excelPreviewPanel`)는 `rowspan`·`colspan`·라벨 칸·헤더 숨김·열이 8개를 넘으면 머리글 줄바꿈을 그린다. `tests/frontend-excel-preview.cjs`가 지킨다.
- 체크박스는 `☑`/`☐`다. Excel(맑은 고딕)에서 대체 글꼴로 정상 표시됨을 확인했다.

### 8.5 갱신한 시험·스크립트·문서

- 시험: `tests/test_form_report.py` 신규 15개(조사 구분 상자, 작업장 상황, A×B, 원인분석, 체크리스트, 병합 위치, 미리보기 표시 키, 입력 필요 규칙, 두 작업, 분석 전 작업, **법령 문구의 숫자를 보존한 고시 본문(`tests/fixtures/고시_제2020-12호_본문.txt`)과 대조**), `tests/report_helpers.py` 신규(공용 준비), `tests/test_plain_report.py`·`test_acceptance.py`·`test_json_lines_integration.py`·`test_persistence_regressions.py`·`test_survey_intake.py`(별지 시트 시험을 증상조사표 시험으로 교체)·`tests/frontend-excel-preview.cjs` 신규(프론트 회귀 8번째)·`tests/electron-workflow.cjs`(시트 목록 단정)·`tests/portable-service-smoke.py`(7/6시트)·`tests/verify_local_artifacts.py`(체크리스트 매트릭스와 조사자 결론 줄로 11개 판정 독립 대조).
- 서비스: `preview_excel_sheets` 응답에서 `form_sheets`를 뺐다.
- 문서: `docs/API_계약서.md` §8, `기능정의서.md` §8, `화면설계서.md` S08, `DB아키텍처_설계서.md`, `ERD_데이터설계서.md`, `requirements.md`(REQ-10), `module-map.md`, `frontend/README.md`, `docs/verification/2026-10-21-simple-flow.md`. `docs/local-verification.md`와 `docs/verification/2026-10-16-*.json`은 당시 기록이라 고치지 않았다.

### 8.6 남은 개선 후보

- 간편 흐름에 **작업강도(A)·작업빈도(B)** 질문(1~5)을 더하면 2단계 표가 채워진다. 지금은 고급 편집의 작업 조건에만 입력란이 있다.
- 단위작업 개념(작업 안의 세부 작업)과 근로자명 입력은 없다. 증상조사표의 "지난 1년 빈도"·"통증으로 인한 조치" 문항도 없다.
- 공식 HWP 원본과 칸 단위 대조는 못 했다(§7.8). 인쇄는 Excel의 인쇄 미리보기(PDF 내보내기)까지만 보았고 실제 프린터 출력은 보지 않았다.
- 쪽 나눔은 작업이 하나일 때를 기준으로 맞췄다. 작업이 여러 개이면 작업마다 3단계·3-1이 이어지고 Excel이 알아서 쪽을 넘긴다.

## 9. 마무리 체크리스트

- [x] 전체 시험 재실행(§10): Python `unittest discover`, `npm --prefix frontend test`, `audit_contract.py`, 변이 시험, `test:electron`, `flow.cjs`, `intake.cjs`.
- [x] **포터블 재빌드** `scripts/build_windows.py`(약 1분 40초). 깨끗한 작업 트리에서 빌드해 manifest의 `source_has_local_changes`가 false이고 `source_commit`이 `a57b3835`다(`dist/`는 gitignore라 푸시에 없음). 패키지 스모크 7개, 패키지 전체 흐름 E2E 20단계(실제 OpenAI), 패키지 고급 화면 E2E 29단계와 독립 대조가 통과했다(§10). 바로 실행하려면 위 폴더의 `LOCO.exe`를 연다(Python·Node 설치 불필요, DB는 `%LOCALAPPDATA%\LOCO\loco_demo.db`).
- [x] 문서(§8.5). `docs/verification/2026-10-21-simple-flow.md`의 낡은 문장("Excel 판정 근거 시트에 영문 상태 코드가 보인다")은 고쳤다.
- [x] 이 Handoff 갱신.

## 10. 검증 결과

**수행(이 PC, Windows, CPython 3.12, 개발 Electron 창 숨김 모드). 공식 서식 구성 Excel까지 반영한 뒤의 결과다.**

| 항목 | 결과 |
|---|---|
| Python 전체 `unittest discover -s tests -p "test_*.py"` | **183개 모두 통과**(실패·오류 0). 새 시험: `test_quick_assess` 28, `test_quick_intake` 19, `test_plain_report` 12, `test_form_report` 15 |
| 프론트 회귀 `npm --prefix frontend test` | **8개 스크립트 모두 통과**(종료 코드 0). AI 한 줄 입력 시험과 Excel 미리보기 그리기 시험(`frontend-excel-preview.cjs`) 포함 |
| API 계약 대조 `scripts/audit_contract.py` | 문서화 43 / 구현 43, 렌더러 호출 37 |
| 변이 시험 `tests/mutation/run_mutations.py` | 모두 탐지(종료 코드 0) |
| 고급 화면 E2E `npm --prefix frontend run test:electron` | **29단계 통과**. 이어서 `tests/verify_local_artifacts.py`로 SQLite와 XLSX 5개 문서를 독립 대조(시트 목록, 11개 판정 ○/X, 조사자 결론 줄, 전후 비교 값): **PASS** |
| 설명 E2E `npm --prefix frontend run test:explanation` | 통과(종료 코드 0) |
| 전체 흐름 E2E `flow.cjs`(실제 OpenAI 설명 생성·편집·적용 포함) | **20단계 통과**, 페이지 오류 0. 저장한 Excel의 시트가 미리보기 탭(유해요인조사표·부담작업 해당 여부·체크리스트·자세 분석(REBA)·입력한 값·확인사항·쉬운 설명)과 같고, 미리보기에 병합 칸·칸 이름 칸이 그려진다 |
| AI 한 줄 입력 E2E `intake.cjs`(실제 OpenAI) | **4단계 통과**, 페이지 오류 0(압축 화면 요약 4줄, 값 지우기, 결과값 240분·20kg×30회가 2.0 구조에 도달, Excel 화면의 "Excel 만들기 전 확인"). 스크립트가 화면 분리 전 구조를 가정해 처음엔 실패했고 Excel 화면 기준으로 고친 뒤 통과했다. 제품 결함이 아니었다 |
| 시연 사진 UI 리허설 `rehearse.cjs` | 5개 세트(사진 15장) 경고 0건, 페이지 오류 0 |
| 포터블 스모크 `tests/portable-service-smoke.py` | **7개 통과**(해시 일치, 한글 경로 DB, 실제 CPU 추론 17점, 키 없는 설명, 공식 서식 구성 Excel 7시트/6시트, 재실행 보존, 틀린 모델 거부) |
| 포터블 전체 흐름 E2E(`flow.cjs`, `LOCO_VERIFY_EXECUTABLE`, 실제 OpenAI) | **20단계 통과** |
| 포터블 고급 화면 E2E(`test:electron`) | **29단계 통과**, 독립 대조 PASS. 첫 실행은 28단계 뒤 29단계에서 멈췄다(작업 삭제 직후 늦은 화면 갱신이 나중 화면 이동을 되돌리는 **기존 시험 불안정**, 화면에 삭제 알림이 뜨기 전에 다음 화면으로 넘어간 것). 같은 포터블로 다시 돌려 29단계 통과했고, 시험이 삭제 알림을 기다리게 고쳤다 |
| Excel 모양 확인 | Excel(COM)로 문서를 PDF로 내보내 쪽 나눔·병합·칸 이름 칸·체크박스·사진 칸·열 머리를 눈으로 확인했고, 앱 미리보기도 화면 캡처로 확인했다 |

**수행하지 못한 것**

- 별도 Windows PC 설치, 현장 조사자 사용 시간.
- 현장 사진에서의 방향·앉음·머리 위 신호 정확도(공개 예제와 시연 18장 밖).
- NO_KEY 환경(키 없음) UI 점검.
- 공식 HWP 원본과 서식 PDF 사본의 칸 단위 대조(§7.8), 실제 프린터 출력.

**알려진 미결**

- "한 줄 입력" 화면이 길어질 때 "사진이 읽은 값"을 접는 것(우선순위 낮음).
- `AGENTS.md` 기준 전체 수용 판정은 NOT ACCEPTED 그대로다.

## 11. 알려진 제약·주의

- **로컬 전용 시험 스크립트**: `.local/try/`(`flow.cjs`, `intake.cjs`, `rehearse.cjs`, `ui.cjs`, `run-flow.ps1`, `run-intake.ps1`, `gen_xlsx.py`, `xlsx_*.py`, `demo_*.py`)는 `.gitignore`의 `.local/`에 걸려 **이 푸시에 들어 있지 않다.** 같은 시험이 필요하면 이 PC에서 가져가거나 같은 구조로 다시 만든다. 사진 fixture(`.local/fixtures`)도 마찬가지다.
- **시험 창**: `LOCO_HIDDEN=1`이면 창을 화면 밖으로 보낸다(`show:false`로 완전히 숨기면 화면 캡처가 멈춘다). 사용자 화면을 흔들지 않도록 시험은 이 모드로만 돌린다.
- **OpenAI 키**: 사용자 환경변수 `OPENAI_API_KEY`. PowerShell 래퍼(`run-flow.ps1`)가 환경에서 읽어 자식 프로세스에만 넘긴다. 값을 출력하지 않는다.
- **Excel 모양 확인**: Excel이 설치된 PC에서 `New-Object -ComObject Excel.Application`(보이지 않게)으로 파일을 열고 `ExportAsFixedFormat(0, "x.pdf")`로 PDF를 내보내 쪽 나눔·병합·글꼴을 눈으로 본다. 앱 미리보기는 `.local/try/tabshot.cjs`처럼 저장된 분석을 열어 탭마다 화면 캡처한다(둘 다 로컬 전용 스크립트). PowerShell 스크립트 본문에 한글 경로를 적으면 깨지므로 경로는 환경변수로 넘긴다.
- **개발용 `.venv`**로 띄운 앱을 닫아도 Python 서비스 프로세스가 남을 수 있다(포터블은 해당 없음). 내가 띄운 프로세스만 정리한다.
- **한글 경로·인코딩**: Python에서 파일을 쓸 때 `encoding='utf-8'`을 명시한다(기본이 cp949). 셸 here-doc에 복잡한 인용이 있으면 깨지므로 패치 스크립트는 파일로 만들어 실행한다.
- 공식 서식은 HWP뿐이라 **서식 PDF 사본은 비공식 미러**다. 법적 적합성을 근거 없이 완료로 표현하지 않는다(`AGENTS.md`).
- 사진 비율을 하루 노출시간으로 바꾸지 않고, GPT 응답으로 판정·점수를 바꾸지 않는다(`AGENTS.md`). AI 한 줄 입력도 칸을 채울 뿐 판정하지 않는다.

## 12. 실행 방법

저장소 루트(`C:\Users\금정산2-PC02\LOCO`)에서:

```powershell
.\.venv\Scripts\python.exe -X utf8 -m unittest discover -s tests -p "test_*.py"
npm.cmd --prefix frontend test
.\.venv\Scripts\python.exe -X utf8 scripts/audit_contract.py
.\.venv\Scripts\python.exe -X utf8 tests/mutation/run_mutations.py
npm.cmd --prefix frontend run test:electron
npm.cmd --prefix frontend run test:explanation
```

개발 앱 실행은 `README.md`를 따른다. 포터블 빌드는 `.\.venv\Scripts\python.exe scripts/build_windows.py`다. 실제 OpenAI를 쓰는 E2E는 `OPENAI_API_KEY`가 사용자 환경에 있어야 한다.

## 13. 이번 푸시에 넣은 것과 뺀 것

**넣음:** 사진 인식 보정(`ergo/engine/quick_assess.py`, `ergo/service/quick.py`), AI 한 줄 입력(`ergo/engine/quick_intake.py`, `ergo/gpt/client.py`, `ergo/service/json_lines.py`, `ergo/contracts.py`, `ergo/service/application.py`), 일반인용 Excel·공식 서식 구성 시트(`ergo/report/plain.py`·`form.py` 신규, `labels.py`, `overview.py`, `renderer.py`, `workbook.py`, `ergo/service/reports.py`; `statutory_forms.py`는 삭제), 화면(`frontend/quick-flow.js`, `quick.css`, `desktop.js`, `analysis/export-view.js`), 시험(`tests/test_quick_assess.py`, `test_quick_intake.py`·`test_plain_report.py` 신규, `test_acceptance.py`, `test_json_lines_integration.py`, `test_persistence_regressions.py`, `test_survey_intake.py`, `test_v2_gpt.py`, `test_form_report.py`·`report_helpers.py`·`frontend-excel-preview.cjs` 신규, `frontend-quick-answers.cjs`, `electron-workflow.cjs`, `portable-service-smoke.py`, `verify_local_artifacts.py`), 문서(§8.5), 이 Handoff.

**뺌:** `.local/`(시험 스크립트·fixture·산출물), `.venv/`, `build/`, `dist/`(빌드 산출물). 사용자 사진은 저장소에 넣지 않았다.

## 14. 이번 푸시 커밋

| 커밋 | 내용 |
|---|---|
| `9c4f4ff3` | 사진 인식 보정, AI 한 줄 입력, 일반인용 Excel·전문가용 시트 삭제, 결과/Excel 화면 분리와 미리보기 |
| `85d67968` | 첫 Handoff(공식 양식 조사 결과와 설계) |
| `cc5bc236` | Excel을 공식 유해요인조사 서식 구성으로(코드·시험) |
| `a57b3835` | 정본 문서·검증 기록·Handoff 갱신 (포터블은 이 커밋에서 빌드) |
| `5030c388` | 패키지 검증 결과 기록, 삭제 알림을 기다리는 고급 화면 시험 보강 |
| 이 문서를 마지막으로 고친 커밋 | 커밋 표 정리, Excel 모양 확인 방법 추가 |
