"""데이터베이스 아키텍처 설계서 생성: 템플릿 + 스키마에서 센 값 + 실측 snapshot → DB아키텍처_설계서.md + 그림 2장

확인하는 것 (어긋나면 문서를 쓰지 않는다)
1. 5.1절의 '결과를 저장하는 순서'가 스키마의 외래키 순서(부모 먼저)를 지킨다
2. 템플릿이 인용하는 서비스 함수가 contracts.ServiceAPI에 있다
3. 템플릿이 인용하는 오류 코드가 contracts.ERROR_CODES에 있다
4. 인용한 테이블·뷰 이름이 스키마에 있다
5. 인용한 ERD 절, API 절이 그 문서에 있다
"""
import importlib.util
import json
import re
import sqlite3
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE.parent / "render"))
import paths  # noqa: E402
from render import cleanup_profiles, mermaid_png  # noqa: E402

DOCS = paths.DOCS
OUT = DOCS / "DB아키텍처_설계서.md"
IMG = DOCS / "DB아키텍처_그림"
SNAP = json.loads((HERE / "bench_snapshot.json").read_text(encoding="utf-8"))
tpl = (HERE / "dba_template.md").read_text(encoding="utf-8")
schema = paths.SCHEMA_FILE.read_text(encoding="utf-8")

spec = importlib.util.spec_from_file_location("contracts", paths.CONTRACTS_FILE)
C = importlib.util.module_from_spec(spec)
sys.modules["contracts"] = C
spec.loader.exec_module(C)
SERVICE = {k for k, v in vars(C.ServiceAPI).items() if callable(v) and not k.startswith("_")}

connection_src = (paths.ERGO / "db" / "connection.py").read_text(encoding="utf-8")
MIN_SQLITE = ".".join(re.search(r"MIN_SQLITE = \(([0-9, ]+)\)", connection_src).group(1).replace(" ", "").split(","))
SCHEMA_VERSION = re.search(r"SCHEMA_VERSION = ([0-9]+)", connection_src).group(1)

db = sqlite3.connect(":memory:")
db.executescript(schema)
tables = [r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")]
views = [r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='view'")]
triggers = [r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='trigger'")]
fk_parents = {t: {r[2] for r in db.execute(f"PRAGMA foreign_key_list({t})")} for t in tables}
problems = []

# ---- 1. 저장 순서
ORDER = [
    ("analysis_run", "시작할 때 이미 있음 (RUNNING). 끝날 때 상태와 완료 시각을 바꾼다"),
    ("still_angle", "사진 수만큼 (표본). 한 번의 `executemany`"),
    ("reba_result", "분석 한 줄"),
    ("key_still_image", "얼굴을 가린 대표 사진 (BLOB)"),
    ("judgment", "단위작업 × 11개 호. 이미 있으면 갱신 (`ON CONFLICT`)"),
    ("judgment_basis", "판정마다 근거 값"),
    ("warning", "'해당' 초안인 호마다. 기존 경고는 해소 시각을 채운다"),
]
seen = set()
for name, _ in ORDER:
    missing = (fk_parents[name] & {n for n, _ in ORDER}) - seen
    if missing:
        problems.append(f"저장 순서: {name}의 부모 {sorted(missing)}가 앞에 없음")
    seen.add(name)
order_tbl = ["| 순서 | 테이블 | 외래키의 부모 | 하는 일 |", "|---|---|---|---|"]
for i, (name, what) in enumerate(ORDER, 1):
    parents = ", ".join(f"`{p}`" for p in sorted(fk_parents[name])) or "—"
    order_tbl.append(f"| {i} | `{name}` | {parents} | {what} |")

# ---- 이식성 목록
sql_all = " ".join(r[0] for r in db.execute("SELECT sql FROM sqlite_master WHERE sql IS NOT NULL"))
PORT = [
    ("`STRICT` 테이블", len(re.findall(r"\)\s*STRICT", sql_all)), "다른 DBMS는 기본이 엄격하다. 삭제"),
    ("`WITHOUT ROWID`", len(re.findall(r"WITHOUT ROWID", sql_all)), "해당 개념이 없다. 삭제 (기본키 순서 저장은 클러스터 인덱스로 대신할 수 있다)"),
    ("`INTEGER PRIMARY KEY` (자동 번호이거나, 1:1 관계에서 부모의 키를 그대로 쓴 기본키)", len(re.findall(r"INTEGER PRIMARY KEY", sql_all)),
     "자동 번호는 `GENERATED ... AS IDENTITY`로, 부모 키를 쓰는 것은 일반 기본키로"),
    ("0/1 정수를 참/거짓으로 쓴 열 (`CHECK (x IN (0,1))`)", len(re.findall(r"IN \(0,\s*1\)", sql_all)), "`boolean`으로"),
    ("`strftime(...)`으로 만든 시각 기본값 (시각을 TEXT로 저장)", len(re.findall(r"strftime\(", sql_all)), "`timestamp` 타입과 `now()`로"),
    ("`date(...)` 함수와 날짜 계산 (`'+3 years'`)", len(re.findall(r"\bdate\(", sql_all)), "`date + interval '3 years'`로"),
    ("`json_valid(...)`", len(re.findall(r"json_valid\(", sql_all)), "`jsonb` 타입으로"),
    ("`RAISE(ABORT, ...)` 트리거", len(re.findall(r"RAISE\(", sql_all)), "트리거 함수 (`RAISE EXCEPTION`)로 다시 쓴다"),
    ("`IS` / `IS NOT`으로 값 비교 (NULL 아닌 것끼리)",
     len(re.findall(r"\bIS NOT (?!NULL\b)|\bIS (?!NOT\b|NULL\b)", sql_all)), "`IS DISTINCT FROM`으로"),
    ("부분 유일 인덱스 (`... WHERE ...`)", len(re.findall(r"CREATE UNIQUE INDEX[^;]*WHERE", sql_all)), "그대로 쓸 수 있다"),
]
port_tbl = ["| SQLite 구문 | 개수 | 옮길 때 |", "|---|---|---|"] + [
    f"| {n} | {c} | {how} |" for n, c, how in PORT if c]

# ---- 그림
FIG1 = '''flowchart LR
  subgraph PC["사용자 PC · 프로그램 하나 (프로세스 1개)"]
    direction LR
    subgraph UIT["화면 스레드"]
      direction TB
      UI["화면<br/>S01 ~ S09"] --> SVC["서비스 함수<br/>함수 하나 = 트랜잭션 하나"]
    end
    subgraph ANT["분석 스레드 (분석할 때만)"]
      ENG["분석 엔진 (순수 함수)<br/>관절 · 각도 · 판별 · REBA<br/>원자료는 메모리에서만"]
    end
    SVC -->|"시작 / 취소<br/>진행률 콜백"| ENG
    SVC -->|"연결 A"| REPO["저장소 계층<br/>SQL은 여기에만"]
    ENG -->|"끝나면 결과를 모아<br/>연결 B로 한 번에"| REPO
    SVC --> GPT["GPT 어댑터"]
    SVC --> XLS["엑셀 작성기"]
    GPT -->|"읽기만<br/>v_gpt_payload"| REPO
    XLS -->|"읽기만<br/>뷰"| REPO
  end
  REPO --> DB[("ergo_assist.db<br/>SQLite · WAL")]
  PIC["원본 사진<br/>사용자 폴더 · 읽기만"] --> ENG
  XLS --> XF["엑셀 · DB 백업<br/>사용자 폴더"]
  GPT -->|"숫자와 법 문구만"| API["GPT API (인터넷)"]
  GPT -.-> CRED["Windows 자격 증명 관리자<br/>GPT 키는 여기에만 있다"]
'''
FIG2 = '''sequenceDiagram
  participant UI as 화면 스레드 (연결 A)
  participant AN as 분석 스레드 (연결 B)
  participant DB as SQLite 파일 (WAL)
  UI->>DB: 트랜잭션 1 · analysis_run 한 줄 (RUNNING). 동의 확인
  UI->>AN: 분석 시작 (스레드를 만든다)
  loop 분석하는 동안 (DB에 쓰지 않는다)
    AN->>AN: 관절 · 각도 · 판별을 메모리에서
    AN-->>UI: 진행률 (콜백)
    UI->>DB: 읽기 (get_task_result 등). 막히지 않고 이전 '현재' 분석이 보인다
  end
  AN->>DB: 트랜잭션 2 · 결과 전부 (5.1절 순서). 이전 현재 분석을 내리고 새 분석을 올린다
  DB-->>AN: COMMIT
  AN-->>UI: 진행률 DONE
  UI->>DB: 읽기 · 새 결과
  Note over UI,DB: 취소나 실패는 analysis_run을 CANCELED 또는 FAILED로만 바꾼다. 결과는 쓰지 않는다
'''

# ---- 채우기
def f1(x): return f"{x:g}"
big = SNAP["big_counts"]
conc = SNAP["concurrent"]
runs = big["analysis_run"]
kb_per_run = round(SNAP["big_db_mb"] * 1000 / runs)
n_check = len(re.findall(r"\bCHECK\s*\(", sql_all))
fill = {
    "BENCH_DATE": SNAP["date"], "BENCH_ENV": f"Windows 10 · Python {SNAP['python']} · SQLite {SNAP['sqlite']}",
    "MIN_SQLITE": MIN_SQLITE, "SCHEMA_VERSION": SCHEMA_VERSION,
    "JOURNAL": SNAP["journal_mode"].upper(), "SYNC": SNAP["synchronous"],
    "SAVE_MS": f1(SNAP["save_30_stills_ms"]["median"]), "SAVE_MAX": f1(SNAP["save_30_stills_ms"]["max"]),
    "COMMIT_MS": f1(SNAP["commit_per_still_ms"]), "COMMIT_30": f1(SNAP["commit_per_still_30_s"] * 1000),
    "COMMIT_RANGE": "~".join(f1(x) for x in SNAP["commit_per_still_range_ms"]),
    "RECALC_MS": f1(SNAP["recalc_read_ms"]), "LIST_MS": f1(SNAP["list_100_surveys_ms"]), "JUDG_MS": f1(SNAP["judgments_of_one_task_ms"]),
    "N_SURVEY": str(big["survey"]), "N_STILLS": f"{big['still_angle']:,}", "N_JUDG": f"{big['judgment']:,}",
    "BIG_MB": f1(SNAP["big_db_mb"]), "KB_PER_RUN": str(kb_per_run),
    "CONC_W": str(conc["writes"]), "CONC_R": str(conc["reads"]), "CONC_WMED": f1(conc["write_median_ms"]),
    "CONC_WMAX": f1(conc["write_max_ms"]), "CONC_RMED": f1(conc["read_median_ms"]), "CONC_RMAX": f1(conc["read_max_ms"]),
    "CONC_ERR": str(conc["error_count"]), "OPEN_MS": f1(SNAP["open_big_ms"]), "BACKUP_S": f1(SNAP["backup_big_s"]),
    "INTEG_S": f1(SNAP["integrity_check"]["s"]), "INTEG_RESULT": SNAP["integrity_check"]["result"],
    "VACUUM_S": f1(SNAP["vacuum_big_s"]),
    "N_TABLES": str(len(tables)), "N_VIEWS": str(len(views)), "N_TRIGGERS": str(len(triggers)),
    "C_NOTNULL": str(len(re.findall(r"NOT NULL", sql_all))), "C_CHECK": str(n_check),
    "C_FK": str(len(re.findall(r"REFERENCES", sql_all))), "C_UNIQUE": str(len(re.findall(r"UNIQUE", sql_all))),
    "N_SENT": "8", "N_RULES": str(len(re.findall(r"^\| R[0-9]+ \|", tpl, re.M))),
    "N_DEC": str(len(re.findall(r"^\| DB-[0-9]+ \|", tpl, re.M))),
    "SAVE_ORDER": "\n".join(order_tbl), "PORTABILITY": "\n".join(port_tbl),
}
doc = tpl
for k, v in fill.items():
    doc = doc.replace("{{" + k + "}}", v)
left = re.findall(r"\{\{[A-Z_]+\}\}", doc)
if left:
    problems.append(f"채우지 못한 자리 {left}")

# ---- 인용 확인
body = doc
named = set(re.findall(r"`((?:create|list|get|update|delete|add|remove|confirm|unconfirm|save|set|reset|export|request|edit|start|cancel|attach|inspect)_[a-z_]+)`", body))
problems += [f"함수 `{n}`이 contracts.ServiceAPI에 없음" for n in sorted(named - SERVICE - set(tables))]
for code in sorted(set(re.findall(r"\b([EWI]-[A-Z]+-[0-9]{3})\b", body))):
    if code not in C.ERROR_CODES:
        problems.append(f"오류 코드 {code}가 계약에 없음")
for name in sorted(set(re.findall(r"`((?:v_[a-z_]+)|(?:[a-z]+_[a-z_]+))`", body))):
    if name.startswith("v_") and name not in views:
        problems.append(f"뷰 {name}이 스키마에 없음")
erd_doc = (DOCS / "ERD_데이터설계서.md").read_text(encoding="utf-8")
api_doc = (DOCS / "API_계약서.md").read_text(encoding="utf-8")
for sec in sorted(set(re.findall(r"ERD ([0-9]+)절", body))):
    if f"\n## {sec}. " not in erd_doc:
        problems.append(f"ERD {sec}절이 없음")
for sec in sorted(set(re.findall(r"API 계약서 ([0-9]+)\.?[0-9]*절", body))):
    if f"\n## {sec}. " not in api_doc:
        problems.append(f"API 계약서 {sec}절이 없음")
if problems:
    print("\n".join(problems))
    raise SystemExit(f"문제 {len(problems)}개 — 문서를 쓰지 않음")

IMG.mkdir(parents=True, exist_ok=True)
mermaid_png(FIG1, IMG / "DBA_1_구성도.png", scale=2, name="dba_fig1")
mermaid_png(FIG2, IMG / "DBA_2_분석_한번.png", scale=2, name="dba_fig2")
cleanup_profiles()
paths.write_text(OUT, doc)
print(f"규칙 {fill['N_RULES']} · 결정 {fill['N_DEC']} · 저장 순서 {len(ORDER)}단계 · 이식성 항목 {len([1 for p in PORT if p[1]])} → {OUT} {len(doc)} chars")
