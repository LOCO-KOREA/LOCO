"""팀원용 읽기 안내 생성: 템플릿 + 일정서·화면설계서에서 읽은 값 → 팀원_읽기안내.md

숫자와 날짜를 손으로 다시 적지 않는다 (문서가 바뀌면 안내도 같이 바뀐다). 인용한 절이 실제로 있는지 확인한다.
"""
import re
import sys
from datetime import date
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import paths  # noqa: E402

D = paths.DOCS
tpl = (HERE / "team_guide_template.md").read_text(encoding="utf-8")
sched = (D / "일정서.md").read_text(encoding="utf-8")
ui = (D / "화면설계서.md").read_text(encoding="utf-8")
docs = {n: (D / n).read_text(encoding="utf-8") for n in
        ("기능정의서.md", "화면설계서.md", "일정서.md", "API_계약서.md", "ERD_데이터설계서.md", "DB아키텍처_설계서.md")}
problems = []


def section(text, start, end):
    i = text.index(start)
    return text[i:text.index(end, i)]


# ---- 화면 흐름: 화면 목록 표 (화면설계서 2절)
ui_list = section(ui, "## 2. 화면 목록", "## 3. 화면 흐름")
screens = re.findall(r"^\| (S0[0-9]) \| ([^|]+?) \| ([^|]+?) \| ([^|]+?) \|", ui_list, re.M)
flow = " → ".join(f"{i} {n}" for i, n, *_ in screens if i != "S09") + ". 설정(S09)은 언제든 연다."

# ---- 묶음별 (일정서 4절)
sec4 = section(sched, "## 4. 역할과 작업 묶음", "## 5. 기능별 일정")
wp_rows = re.findall(r"^\| (WP[0-9] [^|]+?) \| ([^|]+?) \| ([^|]+?) \| ([^|]+?) \| ([^|]+?) \|$", sec4, re.M)
READ = {  # 묶음 → 더 읽을 곳 (절 번호는 아래에서 존재를 확인한다)
    "WP0": "ERD 전체, **DB 아키텍처 설계서 전체**, API 계약서 2절 · 4절",
    "WP1": "API 계약서 5절 (엔진), ERD 5.3절의 '영상과 분석' 그림, 저장소 `README.md`의 알려진 함정",
    "WP2": "API 계약서 6절 (GPT), `ergo/gpt/payload.py`, 화면설계서 S06 · S09",
    "WP3": "API 계약서 7절 (엑셀), 화면설계서 S03 · S07 · S08 · S09",
}
wp_tbl = ["| 묶음 | 담당 | 기능정의서에서 읽을 기능 | 그 밖에 읽을 것 |", "|---|---|---|---|"]
for name, who, feats, scr, mods in wp_rows:
    key = name.split()[0]
    wp_tbl.append(f"| {name} | {who} | {feats} | {READ[key]} |")
wp_tbl.append("| 함께 | 전원 | 재연 촬영, 정답 채점, 시험, 평가, 발표 | 일정서 5절 · 6절 |")

# ---- 10/14 결정 (일정서 7절)
sec7 = section(sched, "## 7. 결정 일정", "## 8. 주요 경로와 버퍼")
dec = [r for r in re.findall(r"^\| (10/14 [^|]+?) \| ([^|]+?) \| ([^|]+?) \| ([^|]+?) \| ([^|]+?) \|$", sec7, re.M)]
dec_tbl = ["| ID | 무엇 | 기본안 | 누가 |", "|---|---|---|---|"] + [
    f"| {i} | {w} | {d} | {who} |" for _, i, w, d, who in dec]
dec_tbl.append("| 담당 | WP1 ~ WP3 담당 확정 (10/13에 가배정) | 총괄이 정함 | 전원 |")

# ---- 내일 할 일 (일정서 6절)
sec6 = section(sched, "## 6. 날짜별 계획", "## 7. 결정 일정")
cur, rows = None, []
for ln in sec6.splitlines():
    m = re.match(r"^\| ([^|]*) \| ([^|]+?) \| ([^|]+?) \|$", ln)
    if not m or m.group(1).strip() in ("날짜",) or set(m.group(2)) <= set("-"):
        continue
    if m.group(1).strip():
        cur = re.search(r"([0-9]{1,2}/[0-9]{2})", m.group(1)).group(1)
    if cur == "10/13":
        rows.append((m.group(2).strip(), m.group(3).strip()))
tomorrow = ["| 누가 | 할 일 |", "|---|---|"] + [f"| {w} | {t} |" for w, t in rows]

# ---- 인용한 절이 있는지
need = [("화면설계서.md", "## 3. 화면 흐름"), ("일정서.md", "## 1. 한눈에 보기"), ("일정서.md", "## 4. 역할과 작업 묶음"),
        ("일정서.md", "## 6. 날짜별 계획"), ("기능정의서.md", "## 3. 상태 정의"), ("기능정의서.md", "## 6. 업무 규칙"),
        ("API_계약서.md", "## 2. 공통 규약"), ("API_계약서.md", "## 4. 서비스 API"), ("API_계약서.md", "## 5. 분석 엔진 API"),
        ("API_계약서.md", "## 6. GPT API 계약"), ("API_계약서.md", "## 7. 파일 계약"), ("ERD_데이터설계서.md", "### 5.3 ")]
for n, h in need:
    if h not in docs[n]:
        problems.append(f"{n}에 '{h}'이(가) 없음")
for k in ("WP0", "WP1", "WP2", "WP3"):
    if not any(r[0].startswith(k) for r in wp_rows):
        problems.append(f"일정서 4절에 {k}가 없음")
if not dec:
    problems.append("일정서 7절에서 10/14 결정을 못 찾음")
if not rows:
    problems.append("일정서 6절에서 10/13 할 일을 못 찾음")
if len(screens) < 9:
    problems.append(f"화면설계서 2절에서 화면 {len(screens)}개만 찾음")

out = (tpl.replace("{{DATE}}", date.today().isoformat()).replace("{{SCREEN_FLOW}}", flow)
          .replace("{{WP_TABLE}}", "\n".join(wp_tbl)).replace("{{DECISIONS}}", "\n".join(dec_tbl))
          .replace("{{TOMORROW}}", "\n".join(tomorrow)))
left = re.findall(r"\{\{[A-Z_]+\}\}", out)
if left:
    problems.append(f"채우지 못한 자리 {left}")
if problems:
    print("\n".join(problems))
    raise SystemExit(f"문제 {len(problems)}개 — 읽기 안내를 쓰지 않음")
paths.write_text(D / "팀원_읽기안내.md", out)
print(f"화면 {len(screens)} · 묶음 {len(wp_rows)} · 10/14 결정 {len(dec)}개 · 10/13 할 일 {len(rows)}개 → {D / '팀원_읽기안내.md'}")
