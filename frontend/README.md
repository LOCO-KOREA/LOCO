# LOCO Electron 프론트와 시안 목업

UI 폰트는 Pretendard 1.3.9로 통일합니다. 공식 npm 패키지의 가변 WOFF2와 SIL Open Font License를 `assets/fonts`에 포함하고 `fonts.css`에서 로컬로 로드합니다. 설치/인터넷 연결 없이 100–900 굵기를 사용할 수 있습니다. 목업 SVG 사본의 글꼴 속성도 Pretendard로 바꾸며 원본 docs/ui 파일은 수정하지 않습니다. 레이아웃 좌표는 유지하지만 글꼴 변경으로 글자 폭은 달라질 수 있습니다.

## 실제 Electron 실행

### 조사 목록 대시보드

`desktop.html`의 S01은 `docs/ui/01_대시보드.svg` 기반 대시보드이며, S02는 기존 목록·조사개요 입력 화면입니다. `dashboard.js`와 `dashboard.css`가 요약 카드·이어 할 조사·최근 조사·단위작업 이동을 구성합니다. 수치는 저장된 SurveySummary에서 집계하고 분석 결과는 연결 예정으로 표시합니다. 정적 SVG 목업(`index.html`)의 동작과는 별개입니다.

### 사진 등록 화면 구현 추가

- S04 실제 HTML 화면: `photo-workspace.js` / `photos.css`. `docs/ui/05_사진등록.svg`의 왼쪽 5순간 × 3회차 배정표와 오른쪽 촬영 안내·관찰 입력 배치를 사용합니다.
- 상단 사진 등록 메뉴와 작업 조건의 `저장 후 사진 등록`을 연결했습니다. 작업 입력을 저장한 뒤 선택 작업의 사진 화면을 엽니다.
- 사진 다중 선택·끌어놓기, 후보 사진 대화상자, EXIF 방향을 적용한 미리보기, 배정·교체·해제, 등록 삭제를 추가했습니다. 원본은 복사하거나 삭제하지 않습니다.
- 카메라 위치·진행 방향, 슬롯별 촬영 순간·하중·한 사람·전신·고정·정상 작업, 관찰 근거·출처·한국시간, 사진 경로 재연결·동의 기록을 입력합니다. 관찰값은 `모름`으로 시작합니다.
- 배정·카메라 변경은 바로 저장하고, 관찰값은 저장 버튼 또는 다른 화면으로 이동할 때 저장합니다. 창을 닫기 전에는 `배정·관찰 저장`을 누르세요. 교체·카메라 변경의 관찰·수동값 초기화는 API 계약을 따릅니다.
- `service/photo_inputs.py`는 프론트 연결용 사진 어댑터입니다. 공용 storage의 사진 삭제를 사용하며 분석 엔진은 연결하지 않습니다. 파일별 읽기 실패와 중복 사용을 안내합니다.
- Python 사진 처리 의존성: 앱이 사용하는 Python에서 `python -m pip install -r frontend/requirements.txt`. 새 사진 API를 반영하려면 기존 Electron을 완전히 종료하고 다시 실행합니다.
- `15슬롯 분석 시작`은 입력 저장 후 분석 연결 예정 안내를 표시합니다. 실제 분석 실행·진행 화면은 후속 작업입니다.
- 브라우저 미리보기: `/frontend/desktop.html?screen=photos`. 새 테스트 추가·실행 없이 코드와 문서를 대조하고 빈 화면의 시안 배치를 확인했습니다. 실제 사진 파일 선택·저장·재열기 동작은 이번 단계에서 실행 확인하지 않았습니다.

### 작업 입력 구현 추가

- S03 실제 HTML 화면: `task-workspace.js` / `tasks.css`. 작업 목록–기본정보–하루 작업/기간의 3열과, 기준 목록–상세 조건의 2열을 UI 시안에 맞췄습니다.
- `create_task`, `get_task`, `rename_task`, `set_task_conditions`, `set_legal_inputs`, `delete_task`를 기존 공용 storage에 연결했습니다. 작업 생성 시 빈 15슬롯·11기준·20시간·수동값 배열을 초기화합니다.
- 기준별 조건, 제외기간 입력, 하루 횟수·조건별 횟수/힘, 중복제거 값, 20개 노출시간과 항목별 근거/출처/관찰시각을 저장하고 다시 엽니다. 계산 결과는 생성하지 않습니다.
- 작업자/방법/선반 높이를 변경하면 현재 사건관찰과 수동값을 비우고 사진 배정은 보존합니다. 작업명·조건·직접입력 변경은 입력 revision에 반영합니다. 비어 있는 숫자는 null이며 실제 0은 0으로 저장합니다.
- 작업을 바꾸거나 기준을 이동할 때 저장 전 입력은 메모리에 유지됩니다. 새로고침하면 저장하지 않은 입력은 사라집니다. 변경된 작업은 상태 문구로 구분합니다.
- `저장 후 사진 등록`은 작업 입력을 저장하고 S04 사진 등록 화면으로 이동합니다. 계산은 아직 연결하지 않았습니다.
- 확인: 별도 DB에서 생성·한글 근거·부분입력·0/null·새 프로세스 재조회·revision·삭제를 확인했습니다. 브라우저에서 기준 전환 시 입력 유지와 양쪽 화면의 표시를 확인했습니다. Playwright로 실제 Electron을 실행해 조사 생성 → 작업·조건·근거 입력 → 기준 전환 → 저장 → 조사 다시 열기 → 앱 종료·재실행 후 값 복원을 검증했습니다. 이 확인은 별도 테스트 DB를 사용했습니다.
- 브라우저 배치 미리보기: `/frontend/desktop.html?screen=task`. 실제 저장은 Electron에서만 가능합니다.

`frontend`에서 `npm install` 후 `npm start`를 실행합니다. Python 실행 경로를 지정하려면 저장소 루트에서:

```powershell
.\frontend\start.ps1 -PythonPath 'C:\설치된Python경로\python.exe'
```

PowerShell 스크립트 실행 정책 때문에 실행이 안 되면 정책 변경 없이 다음 명령을 사용합니다.

```powershell
cd frontend
$env:LOCO_PYTHON = 'C:\설치된Python경로\python.exe'
npm.cmd start
```

실행 파일 누락 메시지가 나오면 `node node_modules/electron/install.js`로 공식 Electron 바이너리를 설치합니다.

- 실제 앱 진입점: `desktop.html` / `desktop.css` / `desktop.js`. S01/S02의 시안 배치를 HTML 폼·표·버튼으로 구현했습니다. SVG 화면을 렌더링하지 않습니다.
- Electron: `electron/main.cjs`가 Python 프로세스 하나를 실행하고 UTF-8 JSON Lines 응답을 request_id로 연결합니다. `preload.cjs`는 API 계약의 DesktopBridge를 제공합니다.
- 현재 연결 기능: 조사·작업 생성·조회·수정·삭제, 조사 검색·검토상태 필터·정렬, 작업 기본조건과 11개 기준 직접입력 저장. 저장 성공 시 실제 SQLite 결과를 반영합니다. 목록에 예시 데이터를 넣지 않습니다.
- 임시 입력 API: `service/survey_service.py`와 `service/task_inputs.py`는 기존 `ergo/db/storage.py`를 호출합니다. 공용 Application Service가 아직 준비되지 않아 A의 조사·작업 저장 흐름을 확인하기 위한 어댑터입니다. `LOCO_SERVICE_ENTRY` 또는 start.ps1의 `-ServiceEntry`로 교체합니다.
- DB는 기본 `frontend/.local/loco_frontend.db`로 분리합니다. 공식 DB를 변경하지 않습니다. 필요 시 `LOCO_DB_PATH` / `-DatabasePath`로 지정합니다. UI와 DB 버전은 공용 문서 기준을 따릅니다.
- 사진 네이티브 파일 선택 브리지는 S04에 연결했습니다. Excel 경로 선택 브리지와 S05 이후 분석·검토·보고서 및 설정 저장은 다음 단계입니다. 로코 설정은 현재 창에만 적용됩니다.
- HTML 배치 미리보기: 정적 서버에서 `/frontend/desktop.html`. 브라우저에서는 실제 저장을 사용할 수 없습니다.

확인 결과: 실제 Electron과 Python·SQLite를 함께 실행한 화면 흐름 검증을 통과했습니다. 앱 재실행 후 작업명·중량·노출시간·한글 근거·출처 복원과 빈 값/숫자 0 구분, 사진 등록 미구현 안내를 확인했습니다. Node→Python JSON Lines로 수정(revision 증가)·삭제도 확인했습니다. Windows 자동 클릭·화면 캡처 도구는 좌표 오류와 캡처 타임아웃이 있어, 화면 흐름은 Playwright의 Electron 기능으로 검증했습니다.

## 별도 시안 원본 목업

`docs/ui`의 개별 SVG 10개를 화면으로 사용합니다. 원본의 배치·색·문구·예시값을 유지하고 왼쪽 상단 로고 블록만 선택한 C 로고로 교체합니다. 샘플 폴더는 사용하지 않습니다.

## 실행

저장소 루트에서:

```
node frontend/build-designs.cjs
node frontend/serve.cjs
```

또는 frontend 폴더에서 `npm run preview`를 실행합니다. 정적 목업은 외부 패키지 없이 위 두 Node 명령으로 실행할 수 있습니다.
<http://127.0.0.1:4318/frontend/index.html>

## 구성과 범위

- `build-designs.cjs`: docs/ui 원본을 읽어 헤더 로고 블록만 바꾸고 assets/screens에 저장합니다. 로고 이후의 원본 문자열이 동일한지 확인합니다.
- `app.js`: 원본 SVG를 표시하고 원래 좌표에 키보드로 조작 가능한 메뉴·주요 이동 버튼을 연결합니다. 기존 입력 상자의 텍스트는 해당 위치에서 편집할 수 있고 탭 메모리에 보관합니다.
- `assets/logo.svg`: 선택한 C 시안의 연결 글자와 관절 요소를 재구성한 SVG입니다.
- S01/S02는 원본의 조사 목록+조사개요 통합 시안을 공유합니다. S03의 작업조건 버튼으로 조건 입력 시안, S06의 수동 입력 버튼으로 REBA 수동 입력 시안을 엽니다.
- 1440×1024 원본 비율을 유지합니다. 좁은 창은 최소 너비 1100px과 가로 스크롤로 원본 배치를 보존합니다.

이 결과물은 원본 SVG를 활용한 인터랙티브 디자인 목업입니다. HTML/CSS로 화면 요소 전체를 재작성한 정식 Electron 프론트가 아닙니다. 원본에 보이는 점수·사진명·진행률은 정적 예시이며 실제 계산 결과가 아닙니다. 입력 편집은 메모리 전용이고 새로고침하면 초기화됩니다. 원본의 주요 화면 이동·입력 편집 외 저장·분석·사진 등록·삭제·Excel·GPT·실시간 진행·완전한 위젯 기능은 연결하지 않았습니다. 해당 동작은 연결 전 안내를 표시합니다. 백엔드 연결 및 실제 기능 구현은 별도 단계입니다.
