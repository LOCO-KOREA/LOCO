# LOCO 작업 인계 — 2026-10-21

> 기준 저장소: `C:\Users\금정산2-PC02\LOCO` (git worktree. `carelink_fullstack`와 `.git`을 공유한다)
> GitHub 정본: `loco` → `https://github.com/LOCO-KOREA/LOCO.git`
> 작업 브랜치: `fix/quick-slot-side-and-smoke` (기반: `loco/main` `2a970469` = PR #21 병합 직후)
> 완성 목표: **2026-10-23 시연** (Asia/Seoul)
> 상태 단일 진실: 코드 + `AGENTS.md`가 정본으로 지정한 `docs/*.md`. 이 문서는 인계용 요약이며 정본을 대신하지 않는다.
> 판정 기준: `AGENTS.md`대로 **전체 수용은 NOT ACCEPTED**다. 아래는 이 브랜치가 추가·변경한 범위의 기록이다.

## 1. 오늘의 결론

오늘 작업은 다섯 축이다. 앞의 네 개는 끝났고 다섯 번째가 다음 작업이다.

1. **시연 사진 18장에서 나온 인식 문제 3건을 고쳤다.** 비스듬한 "정면" 사진이 옆모습으로 오판되던 것, 앉은 자세가 "쪼그려 앉기"로 제안되며 1차 점수가 부풀던 것, 왼쪽을 보는 사진이 먼 쪽 몸으로 측정되던 것.
2. **AI 한 줄 입력**을 만들었다. 작업을 한 문장으로 쓰면 AI가 질문 칸을 근거 구절과 함께 채우고, 사람은 값과 근거를 보고 고치거나 지운다. 빠진 칸만 다시 묻는다.
3. **Excel을 일반인이 읽는 말로 바꿨다.** 코드·내부 용어를 없앴고, 사용자 요청으로 "전문가용 상세기록" 시트를 삭제했다.
4. **결과 화면과 Excel 화면을 나누고 Excel 미리보기를 넣었다.** 미리보기는 저장되는 파일과 같은 시트 정의에서 만든다.
5. **유해요인조사표 공식 양식을 웹에서 다시 조사했다**(§7). 그 구조에 맞춰 Excel을 다시 짜는 것이 **다음 작업**이다(§8, 미착수·설계 확정).

## 2. 한눈에 보기

| 항목 | 상태 | 비고 |
|---|---|---|
| 시연 사진 인식 3건 | 완료·검증 | §3. 현장 사진 일반화는 미검증 |
| AI 한 줄 입력 | 완료·검증 | §4. 실제 OpenAI로 E2E 통과 |
| 일반인용 Excel, 전문가용 시트 삭제 | 완료·검증 | §5 |
| 결과/Excel 화면 분리, Excel 미리보기 | 완료·검증 | §6 |
| 공식 양식 조사 | 완료 | §7 |
| **Excel을 공식 양식 구조로 재배열** | **미착수** | §8에 칸 매핑까지 확정 |
| 사양서·검증 기록 갱신 | 일부 | `docs/API_계약서.md` 2행만 반영. 나머지는 §9 |
| 포터블 재빌드·패키지 E2E | **미수행** | 마지막 포터블 빌드에는 오늘 변경이 없다 |

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

**현재 시트.** `요약`, `기준별 결과`, `입력한 값`, `사진 자세`, `확인사항`. 조건부로 `쉬운 설명`(적용한 AI/조사자 설명이 있을 때), `개선 전후 비교`(비교를 골랐을 때), 수시조사 중 질환자 발생이면 `별지1 유해요인조사표`·`별지2 증상조사표`(`ergo/report/statutory_forms.py`).

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

## 8. 다음 작업 — Excel을 공식 양식 구조로 (미착수, 설계 확정)

사용자 취지: 첫 시트가 **유해요인조사표(별지 제1호서식)**처럼 보여야 한다. 아래 기본값은 사용자가 "멈추지 말고 진행"을 요구해 정해 둔 것이다. 바꾸고 싶으면 이 절만 고치면 된다.

### 8.1 시트 순서(목표)

| # | 시트 | 근거 서식 | 조건 |
|---|---|---|---|
| 1 | `유해요인조사표` | 별지 제1호서식(E-G-1-2025 판) | 항상 |
| 2 | `부담작업 해당 여부` | E-G-1-2025 부록 4(= H-9-2022 부록 1) 판단 서식 | 항상 |
| 3 | `체크리스트` | E-G-1-2025 부록 3 체크리스트 양식(단위작업 × 11개 호) | 항상 |
| 4 | `증상조사표` | 별지 제2호서식 | 증상조사 응답이 있을 때 |
| 5 | `자세 분석(REBA)` | 3-1 작업분석·평가 결과표의 상세 | 항상(지금 `사진 자세`) |
| 6 | `입력한 값` | — | 항상 |
| 7 | `확인사항` | — | 항상 |
| 8 | `쉬운 설명` | — | 적용한 설명이 있을 때 |
| 9 | `개선 전후 비교` | — | 비교를 골랐을 때 |

현재의 `요약`은 1번의 가·라로, `기준별 결과`는 2번으로 흡수한다. DISEASE_CASE 전용 `별지1`·`별지2` 시트(`statutory_forms.py`)는 1번과 4번에 흡수하며 폐지한다. 양식 시트(1~4)에는 탭 색(`tab_color='1F3A5F'`)을 준다.

### 8.2 시트 1 `유해요인조사표` 칸 매핑

| 서식 칸 | 앱 데이터 |
|---|---|
| 조사 구분 ☐정기조사 ☐최초조사 ☐수시조사(규칙 제657조 2항에 근거) | `survey.survey_type` (REGULAR / INITIAL / OCCASIONAL) |
| 수시 사유 ☐질환자 발생·업무상 질병 인정 ☐새 작업·설비 도입 ☐업무량·작업공정 등 작업환경 변경 | `survey.occasional_cause` (DISEASE_CASE / NEW_TASK_OR_EQUIPMENT / WORK_ENVIRONMENT_CHANGE). OTHER이면 사유 칸은 모두 ☐로 두고 `occasional_reason` 글을 아래에 적는다 |
| 조사 일시·조사자·조사부서명·작업공정명 | `survey_date`, `investigator`, `department`, `process` |
| 작업명 | 작업들의 `task_name`(여러 개면 줄바꿈) |
| (추가) 이전 조사일, 근로자 참여 | `previous_survey_date`, `participation`(status·role·method·date·notes·participant_code) |
| 나. 작업장 상황(설비·작업량·작업속도·업무형태) | `workplace_situation.{equipment,workload,speed,work_pattern}_{status,notes}`. NO → ☑변경 없음, YES → ☑변경 있음(주요 변경 내용: notes), UNKNOWN → 둘 다 ☐ 이고 내용 칸에 `입력 필요`(기존 주황 채움이 붙는다). 서식에 "기타" 행은 없다 |
| 1단계 작업명·작업내용 | `task_name`, `conditions.method_description` |
| 2단계 척도 표 | 고정 문구(E-G-1-2025 표기, §7.3) |
| 2단계 단위작업명 | `task_name` |
| 부담작업(호) | 최종 상태 `APPLICABLE`인 호("2, 3, 9"). 미확정(`NEEDS_INPUT`/`NEEDS_REVIEW`)이 있으면 "(미확정 N개)"를 덧붙인다. 해당 없음이면 "해당 없음", 판정 전이면 "계산 전" |
| 작업강도(A)·작업빈도(B)·총점수 | `conditions.work_intensity`, `work_frequency`, 둘 다 정수일 때만 A×B. 없으면 빈칸 |
| 3단계 근로자명 | `conditions.worker_code` |
| 3단계 사진 또는 그림 | 대표 사진(파일에만. `include_representative`가 꺼져 있으면 "대표 사진 이미지는 포함하지 않았어요") |
| 원인분석 표: 유해요인 | §7.4 분류 + 호. 예 "반복동작(2호)". 해당한 호마다 1행 |
| 원인분석 표: 발생원인 또는 노출특징 | 판정 근거의 입력값 문장(예 "하루 240분 동안 키보드·마우스를 집중 사용"). `plain._basis_lines` 재사용·정리 |
| 원인분석 표: 비고 | 검토 필요 사유, 조사자 사유 |
| (고급 입력이 있으면 행 추가) | `conditions.hazard_factors`, `hazard_causes`, `improvement_recommendations` |
| 3-1 인간공학적 작업·분석 평가 결과표 | 도구 "REBA", 평가결과 "최고 N점(위험도, 사진 M장)", 판정 문구(§7.6) |
| 라. 유해요인 조사 결과(결과 요약) | 작업별 [작업·부담작업 해당 호·REBA 최고 점수와 위험도·더 입력/검토할 건수·결과 기준(현재/이전 입력)·검토 상태], 증상조사 요약(방법·응답자 수·`symptom_survey.summary`), "조사자 종합 의견"(직접 쓰는 빈 칸) |

현재 `요약` 시트가 보여 주던 값(출력한 때, 결과 기준, 검토 상태, 입력/검토 필요 건수, 가장 먼저 할 일)은 사라지면 안 된다. 위 라와 `확인사항`에 나눠 담는다.

### 8.3 시트 2·3·4

- **부담작업 해당 여부(2)**: 호마다 블록. `제N호 이름(법정 문구 요약)` 아래 표 **[부담작업 요소(유해요인) / 하루 총 노출시간(또는 횟수) / 요소별 부담작업 여부 ○·X(기준 미만 사유) / 최종 판단]**. 3호는 합산 표시. 각주 "신체부위별 동일조직에 기준시간 이상 영향을 미치면 부담작업으로 판단". 현재 `기준별 결과`의 열(계산 초안, 조사자 결론, 최종 결과, 입력한 값과 기준 비교, 더 필요한 입력, 확인할 점, 조사자 사유·근거, 검토자, 검토한 때)은 **잃지 않는다**.
- **체크리스트(3)**: 행 = 작업, 열 = 1~11호(이름+호), 셀 = ○ 해당 / × 비해당 / `입력 필요` / `검토 필요`(기존 `MISSING_CELLS`·`REVIEW_CELLS` 채움 재사용), 마지막 열 "부담작업 여부". 머리는 부록 3 양식(사업장명·조사 일시·조사자·공정명·공정 내용)을 따르되 사업장명은 앱에 없으므로 빈칸으로 두고, 열 머리에 호별 기준(하루 총 4시간 이상, 2시간 이상, 10회 이상 …)을 한 줄로 적는다.
- **증상조사표(4)**: 응답마다 블록 — 기본 정보 표와 6개 부위 열 × (구체적 부위 / 통증 기간 / 아픈 정도 / 지난 1주일) 표. 앱에 없는 문항(지난 1년 빈도, 통증으로 인한 조치)은 빈칸. 단어 표(`SYMPTOM`, `SITE_NAMES`)는 `statutory_forms.py`에서 옮긴다. 응답 코드 사용을 권장하고 개인정보가 들어 있으면 접근을 제한하라는 주의 문구를 유지한다.

### 8.4 렌더러·미리보기 확장(양식다운 모양에 필요)

현 시트 정의는 "헤더 있는 표"뿐이다. 하위 호환을 지키며 표에 선택 키를 추가한다.

- `header: False` — 헤더 행을 그리지 않는다.
- `labels: [열 번호, …]` — 양식의 칸 이름 칸(굵게+연회색).
- `merges: [[행, 시작열, 끝열], …]` — 병합.
- 시트 `tab_color`는 이미 `_write_sheet`가 읽는다.
- `renderer._write_sheet`: `ws.merge_cells`로 병합, 행 높이는 병합 폭의 합으로 계산. `frontend/quick-flow.js`의 `excelPreviewPanel`: `colspan`·라벨 칸·헤더 숨김 반영.
- 체크박스는 `☑`/`☐`(같은 글꼴 계열) 글자로 쓴다.
- 대표 사진 앵커: 지금은 `_add_representatives`가 `사진 자세` 시트 아래에 붙인다. 양식 3단계 "사진 또는 그림" 칸으로 옮긴다(앵커 키를 시트 정의에 둔다).
- 문자열 셀 `data_type='s'` 고정은 새 시트도 지킨다.

### 8.5 영향받는 시험·스크립트·문서

- 시험: `tests/test_plain_report.py`(`PLAIN_SHEETS`, 첫 시트 `요약` 참조, `기준별 결과` 행 위치 `min_row=6` 가정), `test_acceptance.py`(35·38행), `test_json_lines_integration.py`(130행), `test_persistence_regressions.py`(209행), `test_survey_intake.py`(`별지1`·`별지2` 이름·내용 시험, 시트 수 5/7), `tests/verify_local_artifacts.py`(`expected_sheets`·독립 대조), `tests/portable-service-smoke.py`(시트 목록을 보는지 확인), `.local/try/flow.cjs`(`tabs.slice(0,5)` 단정. 로컬 파일).
- `ergo/service/reports.py::handle_preview_excel_sheets`의 `form_sheets` 목록(별지 이름을 직접 적어 둠).
- 문서: `docs/API_계약서.md` §8(출력)·`preview_excel_sheets` 행, `docs/기능정의서.md`, `docs/화면설계서.md`(4/6시트 서술), `docs/local-verification.md`(REQ-10 행), `frontend/README.md`, `docs/verification/2026-10-21-simple-flow.md`.

### 8.6 권장 구현 순서

1. 렌더러·미리보기 확장(`header`/`labels`/`merges`)과 그 시험(파일 병합 범위, 미리보기 `colspan`, 값 일치).
2. `ergo/report/form.py` 신설: 시트 1~4 빌더. `plain.py`의 `_basis_lines`, `_applicable`, `_reba_text`, `_slot_names` 재사용.
3. `plain_sheets` 순서 변경, `요약`·`기준별 결과` 흡수, `statutory_forms` 폐지.
4. 시험 갱신 + 새 시험(양식 칸 값, ☑/☐, A×B 조건, 호 분류, REBA 판정 문구, 미리보기 = 파일, 코드·내부 용어 없음).
5. E2E(`flow.cjs` 갱신) → 문서 → §9.

## 9. 마무리 체크리스트

- [ ] 전체 시험 재실행: Python `unittest discover`, `npm --prefix frontend test`, `audit_contract.py`, `tests/mutation/run_mutations.py`, `test:electron`·`test:explanation`(창 숨김), `flow.cjs`, `intake.cjs`, `rehearse.cjs`.
- [ ] **포터블 재빌드** `scripts/build_windows.py`(PyInstaller 약 1분) → 패키지 E2E(`LOCO_VERIFY_EXECUTABLE`) → 사용자에게 보이는 창으로 실행.
- [ ] 문서: `docs/verification/2026-10-21-simple-flow.md`에 오늘 변경(사진 인식·AI 한 줄 입력·일반인용 Excel·화면 분리·전문가용 시트 삭제) 반영. 그 문서에는 "Excel 판정 근거 시트에 영문 상태 코드가 보인다"는 낡은 문장이 남아 있다 — 지금은 사실과 다르므로 고친다. `frontend/README.md`, 정본 문서(§8.5).
- [ ] 이 Handoff 갱신.

## 10. 검증 결과

**수행(이 PC, Windows, CPython 3.12, 개발 Electron 창 숨김 모드)**

| 항목 | 결과 |
|---|---|
| Python 전체 `unittest discover -s tests -p "test_*.py"` | **167개 모두 통과**(100초, 실패·오류 0). 새 시험: `test_quick_assess` 28, `test_quick_intake` 19, `test_plain_report` 12 |
| 프론트 회귀 `npm --prefix frontend test` | 7개 스크립트 모두 통과(종료 코드 0, PASS 25줄, AI 한 줄 입력 시험 포함) |
| API 계약 대조 `scripts/audit_contract.py` | 문서화 43 / 구현 43, 렌더러 호출 37 |
| 전체 흐름 E2E `flow.cjs`(실제 OpenAI 설명 생성·편집·적용 포함) | **20단계 통과**, 페이지 오류 0. 저장한 Excel의 시트가 미리보기 탭(요약·기준별 결과·입력한 값·사진 자세·확인사항·쉬운 설명)과 같고 전문가용 시트는 없다. 개선 전후 비교 시트도 미리보기에 나온다 |
| AI 한 줄 입력 E2E `intake.cjs`(실제 OpenAI) | **4단계 통과**, 페이지 오류 0(압축 화면 요약 4줄, 값 지우기, 결과값 240분·20kg×30회가 2.0 구조에 도달, Excel 화면의 "Excel 만들기 전 확인"). 스크립트가 화면 분리 전 구조(검토 화면에 점검표)를 가정해 처음엔 실패했고, 스크립트를 Excel 화면 기준으로 고친 뒤 통과했다. 제품 결함이 아니었다 |
| 18장 사진 UI 리허설 `rehearse.cjs` | 경고 0건(이 세션 앞부분에 수행. Excel 변경·전문가용 시트 삭제 이후 재실행하지 않았다) |

**수행하지 못한 것**

- 포터블 재빌드와 패키지 E2E(§9).
- 별도 Windows PC 설치, 현장 조사자 사용 시간.
- 현장 사진에서의 방향·앉음·머리 위 신호 정확도(공개 예제와 시연 18장 밖).
- `tests/mutation/run_mutations.py`, `test:electron`, `test:explanation`(오늘 변경 이후 재실행하지 않았다).
- NO_KEY 환경(키 없음) UI 점검.
- 공식 HWP 원본과 서식 PDF 사본의 대조(§7.8).

**알려진 미결**

- "한 줄 입력" 화면이 길어질 때 "사진이 읽은 값"을 접는 것(우선순위 낮음).
- `AGENTS.md` 기준 전체 수용 판정은 NOT ACCEPTED 그대로다.

## 11. 알려진 제약·주의

- **로컬 전용 시험 스크립트**: `.local/try/`(`flow.cjs`, `intake.cjs`, `rehearse.cjs`, `ui.cjs`, `run-flow.ps1`, `run-intake.ps1`, `gen_xlsx.py`, `xlsx_*.py`, `demo_*.py`)는 `.gitignore`의 `.local/`에 걸려 **이 푸시에 들어 있지 않다.** 같은 시험이 필요하면 이 PC에서 가져가거나 같은 구조로 다시 만든다. 사진 fixture(`.local/fixtures`)도 마찬가지다.
- **시험 창**: `LOCO_HIDDEN=1`이면 창을 화면 밖으로 보낸다(`show:false`로 완전히 숨기면 화면 캡처가 멈춘다). 사용자 화면을 흔들지 않도록 시험은 이 모드로만 돌린다.
- **OpenAI 키**: 사용자 환경변수 `OPENAI_API_KEY`. PowerShell 래퍼(`run-flow.ps1`)가 환경에서 읽어 자식 프로세스에만 넘긴다. 값을 출력하지 않는다.
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

**넣음:** 사진 인식 보정(`ergo/engine/quick_assess.py`, `ergo/service/quick.py`), AI 한 줄 입력(`ergo/engine/quick_intake.py`, `ergo/gpt/client.py`, `ergo/service/json_lines.py`, `ergo/contracts.py`, `ergo/service/application.py`), 일반인용 Excel(`ergo/report/plain.py` 신규, `labels.py`, `overview.py`, `renderer.py`, `statutory_forms.py`, `workbook.py`, `ergo/service/reports.py`), 화면(`frontend/quick-flow.js`, `quick.css`, `desktop.js`, `analysis/export-view.js`), 시험(`tests/test_quick_assess.py`, `test_quick_intake.py`·`test_plain_report.py` 신규, `test_acceptance.py`, `test_json_lines_integration.py`, `test_persistence_regressions.py`, `test_survey_intake.py`, `test_v2_gpt.py`, `frontend-quick-answers.cjs`, `portable-service-smoke.py`, `verify_local_artifacts.py`), 문서(`docs/API_계약서.md` 2행), 이 Handoff.

**뺌:** `.local/`(시험 스크립트·fixture·산출물), `.venv/`, `build/`, `dist/`(빌드 산출물). 사용자 사진은 저장소에 넣지 않았다.

## 14. 이번 푸시 커밋

| 커밋 | 내용 |
|---|---|
| (이 푸시) | 사진 인식 보정, AI 한 줄 입력, 일반인용 Excel·전문가용 시트 삭제, 결과/Excel 화면 분리와 미리보기 |
| (이 푸시) | 이 Handoff |
