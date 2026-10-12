# LOCO — 근골격계 유해요인조사 보조 앱

Windows PC 프로그램 (코드 이름 `ergo-assist`).
작업 영상을 올리고 하루 작업시간을 넣으면, 고시 제3조의 부담작업 11개 기준에 대한 판정 초안과 경고를 만든다. 확정은 사람이 하고, 결과는 엑셀로 낸다.

**처음 오셨다면: [`docs/팀원_읽기안내.md`](docs/팀원_읽기안내.md)부터 읽으세요.** (30분이면 된다)

## 지금 상태 (2026-10-12)

| 있는 것 | 없는 것 |
|---|---|
| 서비스 계약 (`ergo/contracts.py`, 함수 43개), 계약 시험 | 화면 |
| DB 스키마 · 시드 · 연결 규칙, 제약 시험 30개 | 저장소 계층 (SQL을 쓰는 곳) |
| 법 원문 사본과 시험 (고시 제2020-12호) | 분석 엔진 (관절, 각도, 판별, REBA, 판정) |
| 스텁 서비스 (가짜 값을 돌려줘서 화면을 먼저 만들 수 있다) | GPT 어댑터, 엑셀 작성기 |
| 설계 문서를 만드는 도구 (`docs_src/`) | |

## 시작하기

Python 3.11 이상 (SQLite 3.38 이상). 아직 설치할 패키지가 없다.

```text
python -m unittest discover -s tests -t .      # 시험 전체 (몇 초)
python docs_src/build_all.py                    # 설계 문서와 그림을 다시 만든다 (Edge가 필요하다)
python tests/mutation/run_mutations.py          # 시험이 실제로 잡는지: 사본에 일부러 망가뜨린 15가지를 넣어 본다
```

스텁으로 화면을 먼저 만들 때:

```python
from ergo.service import get_service
svc = get_service()                  # 가짜 값. 분석 진행률은 0.2초마다 콜백으로 온다
svc.get_task_result(10)              # '상자 들어 옮기기'의 결과 (REBA 9, 4호 해당 초안 등)
```

## 폴더

| 폴더 | 무엇이 있나 |
|---|---|
| `ergo/contracts.py` | **화면 ↔ 서비스 계약**. 함수, 데이터 묶음(DTO), 코드 값, 오류 코드. 계약의 원본 |
| `ergo/db/` | `schema_v1.sql` (스키마 원본), `seed_v1.sql` (기준 정보), `connection.py` (연결 규칙) |
| `ergo/service/` | 서비스 함수. 지금은 `stub.py`만 있다 |
| `ergo/engine/` | 분석 엔진 (순수 함수). 지금은 자리만 있다 |
| `ergo/gpt/` | GPT 어댑터. `payload.py`가 'GPT로 나가는 열'의 경계 |
| `ergo/report/` | 엑셀 작성기 |
| `tests/` | 시험. `contract_suite.py`는 진짜 서비스도 통과해야 하는 계약 시험 |
| `tests/fixtures/` | 고시 원문 사본 |
| `docs_src/` | 설계 문서를 만드는 스크립트와 템플릿. 일부 문서는 **여기서 만들어진다** |
| `docs/` | 설계 문서와 그림 |

### 문서 (`docs/`)

| 문서 | 만드는 방식 | 고치려면 |
|---|---|---|
| `requirements.md`, `기능정의서.md`, `project-overview.md`, `benchmark-apps.md`, `법정서식_검증목록.md`, `화면명세서_GPT용.md`, `presentation-script.md` | 손으로 쓴다 | 파일을 직접 고친다 |
| `ERD_데이터설계서.md`, `ERD.drawio`, `DB아키텍처_설계서.md`, `API_계약서.md`, `화면설계서.md`, `일정서.md`, `팀원_읽기안내.md`와 `*_그림/` | **스크립트가 만든다** | 원본(스키마·계약·화면 데이터·일정 데이터)을 고치고 `python docs_src/build_all.py` |

저장소에 넣지 않은 자료: REBA 워크시트(Cornell, Alan Hedge)와 KOSHA GUIDE H-9-2022 텍스트. 저작권이 있는 자료라 정욱님이 따로 갖고 있다.

## 규칙

1. **화면은 서비스 함수만 부른다.** DB를 직접 읽거나 쓰지 않고, 판정·점수·시간을 계산하지 않는다.
2. **SQL은 `ergo/db/`에만 둔다.** 연결은 `ergo.db.open_db`로만 연다. 값은 `?`로 넘긴다.
3. **엔진은 DB와 화면을 모르는 순수 함수다.** 같은 입력이면 같은 출력이 나와야 한다.
4. **GPT는 설명 문장에만 쓴다.** 판정·점수·경고에는 쓰지 않는다. GPT로 나가는 값은 `ergo/gpt/payload.py`의 `SENT_COLUMNS`뿐이다.
5. **법 기준은 고시 원문 그대로다.** 앱이 만든 기준은 쓰지 않는다. 문구를 바꾸면 `tests/test_law_text.py`가 막는다.
6. **스크립트가 만드는 문서는 손으로 고치지 않는다.** 스키마·계약·화면 데이터를 고치고 `build_all.py`를 돌린다 (위 표).

### 계약을 바꿀 때

1. `ergo/contracts.py`를 고친다 (함수나 필드를 더하면 `CONTRACT_VERSION`을 올린다).
2. 오류 코드를 더했으면 `ERROR_CODES`와 `docs_src/api/api_template.md`의 8절 표를 함께 고친다.
3. `python -m unittest discover -s tests -t .` → 계약 ↔ ERD 대조와 스텁 시험이 돈다.
4. `python docs_src/build_all.py` → API 계약서 등이 다시 만들어진다.

### 스키마를 바꿀 때

`ergo/db/schema_v1.sql`을 고치고 (이미 쓰는 DB를 위한 `migrations/NNN_*.sql`도 만든다) 위와 같이 시험과 `build_all.py`를 돈다.
DB 담당: 한정욱. 자세한 절차는 DB 아키텍처 설계서 10.2절.

## 진짜 서비스로 바꾸는 법

스텁의 함수를 하나씩 진짜 함수로 바꿔 끼운다. 새 서비스는 `tests/contract_suite.py`를 통과해야 한다:

```python
class MyServiceContract(ServiceContractTests, unittest.TestCase):
    def make_service(self, progress_delay_s=0.0):
        return MyService(...)          # contract_suite.py 첫머리의 '시험용 데이터'를 담고 있어야 한다
```

## 담당 (10/14 회의에서 확정)

| 묶음 | 담당 | 맡은 곳 |
|---|---|---|
| WP0 총괄 · 데이터 | 한정욱 | `ergo/db/` 저장소 계층, 조사·단위작업 서비스, 통합, 계약 시험 |
| WP1 자세 분석 | 배정 | `ergo/engine/pose.py`, `angles.py`, `postures.py`, `reba.py` |
| WP2 경고 · 확신도 | 배정 | `ergo/gpt/`, 확신도 (각도를 ±5° 바꿔 세 번 판정), 경고 |
| WP3 판정 · 보고서 | 배정 | `ergo/engine/judge.py`, 다시 계산, `ergo/report/excel.py` |

## 알려진 함정

- **한글 경로**: MediaPipe는 모델 파일 경로에 한글이 하나라도 있으면 `model_asset_path`로 못 연다. `model_asset_buffer=open(경로, "rb").read()`로 넘긴다. (OpenCV는 한글 경로를 연다.)
- **폰 영상의 회전 정보**: OpenCV 5는 기본으로 적용한다. 끄면 옆으로 누운 프레임이 되는데 MediaPipe가 그래도 사람을 찾아서, 각도가 조용히 틀린다.
- **SQLite 버전**: `STRICT` 테이블은 3.37, JSON 함수 내장은 3.38부터다. 낮으면 `open_db`가 시작을 막는다.
- **줄바꿈**: 생성 스크립트는 LF로 쓴다. 편집기에서 CRLF로 저장하면 변경 내역이 줄마다 바뀐 것으로 보인다.
- **문서 그림 만들기**: Edge 155에서는 `--headless=new`만으로는 화면을 안 찍는다. `docs_src/render/render.py`가 필요한 옵션을 넣어 둔다 (프로필 폴더는 짧은 경로여야 한다).

## 이 PC에서 확인해 둔 패키지 버전 (2026-10-08, Python 3.11.9)

Pose 담당이 설치할 때 쓴다. 서로 함께 설치되는 것을 확인했다. 아직 `requirements.txt`는 없다.

```text
mediapipe==1.1.0
opencv-contrib-python==5.0.0.93
numpy==2.4.6
```

처리 속도 (i7-10700K, 720×1280, 프레임당, CPU): MediaPipe Lite 11.9ms · Full 16.0ms · Heavy 49.8ms.
