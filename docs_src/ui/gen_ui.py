"""화면설계서 생성: ui_screens.py (와이어프레임 HTML + 요소 표) → PNG + docs/화면설계서.md

확인하는 것 (하나라도 어긋나면 문서를 쓰지 않는다)
1. 와이어프레임의 빨간 번호 = 요소 표의 번호
2. 요소 표의 API 함수와 DTO.필드가 contracts.py에 있다
3. 기능정의서 4절에서 그 화면에 배정된 기능이 그 화면의 기능 목록에 있다
4. 서비스 함수가 모두 어느 화면에서 쓰인다
5. API 계약서 8절의 오류 코드가 모두 메시지 목록에 있다 (거꾸로도)
6. 인용한 기능정의서·요구사항 ID가 실제로 있다
"""
import dataclasses
import importlib.util
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
HERE = Path(__file__).parent
SCR = HERE.parent
sys.path.insert(0, str(SCR))
sys.path.insert(0, str(SCR / "render"))
sys.path.insert(0, str(HERE))
import paths  # noqa: E402
from render import cleanup_profiles, html_png, mermaid_png  # noqa: E402
import ui_screens as U  # noqa: E402

DOCS = paths.DOCS
OUT = DOCS / "화면설계서.md"
IMG = DOCS / "화면설계서_그림"
RENDER = "--no-render" not in sys.argv

spec = importlib.util.spec_from_file_location("contracts", paths.CONTRACTS_FILE)
C = importlib.util.module_from_spec(spec)
sys.modules["contracts"] = C
spec.loader.exec_module(C)
SERVICE = {k for k, v in vars(C.ServiceAPI).items() if callable(v) and not k.startswith("_")}
DTO = {k: {f.name for f in dataclasses.fields(v)} for k, v in vars(C).items()
       if isinstance(v, type) and dataclasses.is_dataclass(v)}
ENUMS = {k for k, v in vars(C).items() if isinstance(v, type) and issubclass(v, C.Enum) and v is not C.Enum}

fd = (DOCS / "기능정의서.md").read_text(encoding="utf-8")
req = (DOCS / "requirements.md").read_text(encoding="utf-8")
api = (DOCS / "API_계약서.md").read_text(encoding="utf-8")
FEAT = {fid: (name, scr) for fid, name, fr, scr, prio in re.findall(
    r"^\| (F0\d-0\d) \| ([^|]+?) \| ([^|]+?) \| ([^|]+?) \| (Must|Should|Could) \|$", fd, re.M)}
sec8 = api[api.index("## 8. 오류 코드"):api.index("## 9. 주요 시나리오")]
ERRS = {c: (m, k, t) for c, m, k, t in re.findall(r"^\| ([EWI]-[A-Z]+-\d{3}) \| ([^|]+?) \| ([^|]+?) \| ([^|]+?) \|", sec8, re.M)}

ALL = U.SCREENS + U.DIALOGS
problems = []


def calls(text):
    return set(re.findall(r"\b([a-z_]+)\(", text))


def dto_refs(text):
    return set(re.findall(r"\b([A-Z][A-Za-z]+)\.([a-z_]+)\b", text))


# ---------------------------------------------------------------- 확인
used = {}
for s in ALL:
    marks = sorted(int(x) for x in re.findall(r'<i class="n[^"]*"[^>]*>(\d+)</i>', s["html"]))
    nums = [r[0] for r in s["rows"]]
    if sorted(set(marks)) != sorted(nums) or len(marks) != len(set(marks)):
        problems.append(f"{s['id']}: 그림 번호 {marks} ≠ 표 번호 {nums}")
    for r in s["rows"]:
        text = " ".join(str(x) for x in r[1:])
        for fn in calls(text):
            if fn not in SERVICE:
                problems.append(f"{s['id']}-{r[0]}: 없는 함수 {fn}()")
            used.setdefault(fn, set()).add(s["id"])
        for cls, field in dto_refs(text):
            if cls in DTO and field not in DTO[cls]:
                problems.append(f"{s['id']}-{r[0]}: {cls}에 {field} 필드가 없음")
            elif cls not in DTO and cls not in ENUMS:
                problems.append(f"{s['id']}-{r[0]}: 없는 DTO {cls}")
for sid, name, purpose, items in U.SMALL:
    for k, v in items:
        for fn in calls(v):
            if fn not in SERVICE:
                problems.append(f"{sid}: 없는 함수 {fn}()")
            used.setdefault(fn, set()).add(sid)
        for cls, field in dto_refs(v):
            if cls in DTO and field not in DTO[cls]:
                problems.append(f"{sid}: {cls}에 {field} 필드가 없음")
missing_fn = sorted(SERVICE - set(used))
if missing_fn:
    problems.append(f"어느 화면에서도 쓰지 않는 서비스 함수: {missing_fn}")

screen_fids = {s["id"].split("-")[0] if s["id"].startswith("S") else s["id"]: set() for s in ALL}
for s in ALL:
    screen_fids.setdefault(s["id"].split("-")[0], set()).update(s["fids"])
for fid, (name, scr) in FEAT.items():
    for sc in re.findall(r"S0\d", scr):
        if fid not in screen_fids.get(sc, set()):
            problems.append(f"기능정의서 4절: {fid}({name})는 {sc}에 배정됐는데 {sc}의 기능 목록에 없음")

if set(ERRS) != set(U.MESSAGE_PLACE):
    problems.append(f"메시지 목록 불일치: API에만 {sorted(set(ERRS) - set(U.MESSAGE_PLACE))}, "
                    f"화면설계서에만 {sorted(set(U.MESSAGE_PLACE) - set(ERRS))}")

# ---------------------------------------------------------------- 표 만들기
def esc(t):
    return str(t).replace("|", "\\|")


def fn_list(s):
    return ", ".join(f"`{f}`" for f in sorted({f for r in s["rows"] for f in calls(' '.join(map(str, r[1:])))})) or "—"


lst = ["| ID | 화면 | 탭 | 목적 | 기능 | 쓰는 API 함수 |", "|---|---|---|---|---|---|"]
for s in U.SCREENS:
    lst.append(f"| {s['id']} | {s['name']} | {s['tab']} | {s['purpose'].split('. ')[0].rstrip('.')} | {', '.join(s['fids'])} | {fn_list(s)} |")
for d in U.DIALOGS:
    lst.append(f"| {d['id']} | {d['name']} | (대화상자) | {d['purpose'].split('. ')[0].rstrip('.')} | {', '.join(d['fids'])} | {fn_list(d)} |")
for sid, name, purpose, items in U.SMALL:
    fns = sorted({f for k, v in items for f in calls(v)})
    lst.append(f"| {sid} | {name} | (대화상자) | {purpose.rstrip('.')} | — | {', '.join(f'`{f}`' for f in fns)} |")


def detail(s, level="###"):
    img = f"화면설계서_그림/{s['id']}.png"
    out = [f"{level} {s['id']} {s['name']}", "", f"![{s['id']} {s['name']}]({img})", "",
           f"- **목적**: {s['purpose']}"]
    if "entry" in s:
        out += [f"- **들어오는 길**: {s['entry']}", f"- **나가는 길**: {s['exit']}"]
    out += [f"- **기능**: {', '.join(f'{f} {FEAT[f][0]}' for f in s['fids'])}", "",
            "| 번호 | 요소 | 종류 | 데이터 · 동작 | 규칙 · 메시지 |", "|---|---|---|---|---|"]
    out += [f"| {r[0]} | {esc(r[1])} | {esc(r[2])} | {esc(r[3])} | {esc(r[4])} |" for r in s["rows"]]
    if s.get("states"):
        out += ["", "**상태**", ""] + [f"- {x}" for x in s["states"]]
    return "\n".join(out) + "\n"


details = "\n".join(detail(s) for s in U.SCREENS)
dlg = "\n".join(detail(d) for d in U.DIALOGS)
for sid, name, purpose, items in U.SMALL:
    dlg += f"\n### {sid} {name}\n\n- **목적**: {purpose}\n\n| 항목 | 내용 |\n|---|---|\n" + "\n".join(
        f"| {esc(k)} | {esc(v)} |" for k, v in items) + "\n"

msgs = ["| 코드 | 종류 | 화면 문구 (API 계약서) | 나오는 화면 | 위치 · 방법 |", "|---|---|---|---|---|"]
for code in ERRS:
    m, kind, text = ERRS[code]
    place, how = U.MESSAGE_PLACE.get(code, ("?", "?"))
    msgs.append(f"| {code} | {kind} | {esc(text)} | {place} | {esc(how)} |")

trace = ["| 기능 | 이름 | 화면 | API 함수 (그 화면에서) |", "|---|---|---|---|"]
for fid, (name, scr) in FEAT.items():
    shown = [s for s in ALL if fid in s["fids"]]
    fns = sorted({f for s in shown for r in s["rows"] for f in calls(' '.join(map(str, r[1:])))})
    where = ", ".join(s["id"] for s in shown) or ("(내부, 화면 없음)" if "내부" in scr else "?")
    trace.append(f"| {fid} | {name} | {where} | {', '.join(f'`{f}`' for f in fns) or '—'} |")

oi = ["| ID | 무엇 | 언제 |", "|---|---|---|"] + [f"| {a} | {esc(b)} | {c} |" for a, b, c in U.OPEN_ITEMS]

FLOW = """flowchart LR
  S01["S01 조사 목록"] -->|"+ 새 조사"| S02["S02 조사 개요"]
  S01 -->|열기| S03["S03 단위작업과<br/>작업 정보"]
  S01 -.->|삭제| D04(["D04 삭제 확인"])
  S02 -->|저장하고 작업 등록| S03
  S03 -.->|"+ 단위작업 · 수정"| D05(["D05 단위작업"])
  S03 -.->|"+ 참여자"| D06(["D06 참여자"])
  S03 -->|사진 올리기| S04["S04 사진 올리기"]
  S04 -->|분석 시작| S05["S05 분석 진행"]
  S05 -->|끝남| S06["S06 분석 결과와 경고"]
  S05 -->|취소 · 실패| S04
  S06 -.->|REBA 입력| D03(["D03 REBA 사람 입력"])
  S06 -->|판정 보기| S07["S07 부담작업 판정"]
  S07 -.->|"확정 · 풀기"| D01(["D01 사유"])
  S07 -->|입력하기| S03
  S07 -->|탭| S08["S08 결과와<br/>엑셀 내보내기"]
  S09["S09 설정<br/>(언제든)"] -.->|각도 변경| D02(["D02 각도 기준 변경"])"""

if problems:
    print("\n".join(problems))
    raise SystemExit(f"문제 {len(problems)}개 — 화면설계서를 쓰지 않음")

# ---------------------------------------------------------------- 그림
IMG.mkdir(parents=True, exist_ok=True)
if RENDER:
    for s in U.SCREENS:
        html_png(s["html"], IMG / f"{s['id']}.png", U.W, U.H, scale=1.5, name=f"ui_{s['id']}", css=U.CSS)
        print("render", s["id"])
    for d in U.DIALOGS:
        html_png(f'<div style="width:{d["w"]}px;height:{d["h"]}px">{d["html"]}</div>', IMG / f"{d['id']}.png",
                 d["w"], d["h"], scale=1.5, name=f"ui_{d['id']}", css=U.CSS)
        print("render", d["id"])
    mermaid_png(FLOW, IMG / "화면흐름.png", scale=2, name="ui_flow")
    cleanup_profiles()
imgs = sorted(IMG.glob("*.png"))
need = {f"{s['id']}.png" for s in ALL} | {"화면흐름.png"}
lack = need - {p.name for p in imgs}
if lack:
    raise SystemExit(f"그림이 없음: {sorted(lack)}")

# ---------------------------------------------------------------- 문서
n_rows = sum(len(s["rows"]) for s in ALL)
tpl = (HERE / "ui_template.md").read_text(encoding="utf-8")
doc = (tpl.replace("{{SCREEN_LIST}}", "\n".join(lst)).replace("{{SCREEN_DETAILS}}", details)
          .replace("{{DIALOG_DETAILS}}", dlg).replace("{{MESSAGES}}", "\n".join(msgs))
          .replace("{{TRACE}}", "\n".join(trace)).replace("{{OPEN_ITEMS}}", "\n".join(oi))
          .replace("{{FLOW_MERMAID}}", FLOW)
          .replace("{{N_SCREEN}}", str(len({s['id'].split('-')[0] for s in U.SCREENS})))
          .replace("{{N_SCREEN_IMG}}", str(len(U.SCREENS)))
          .replace("{{N_DIALOG}}", str(len(U.DIALOGS) + len(U.SMALL)))
          .replace("{{N_DIALOG_IMG}}", str(len(U.DIALOGS)))
          .replace("{{N_IMG}}", str(len(need)))
          .replace("{{N_ROWS}}", str(n_rows)).replace("{{N_MSG}}", str(len(ERRS)))
          .replace("{{N_FUNC}}", str(len(SERVICE))))
left = re.findall(r"\{\{[A-Z_]+\}\}", doc)
if left:
    raise SystemExit(f"채우지 못한 자리 {left}")
for ref in sorted(set(re.findall(r"\b((?:F0\d-0\d)|(?:AC|EX|BR|TP|OI)-\d{2})\b", doc))):
    if ref not in fd:
        problems.append(f"{ref}가 기능정의서에 없음")
for ref in sorted(set(re.findall(r"\b((?:NFR|FR|UC)-\d{3})\b", doc))):
    if ref not in req:
        problems.append(f"{ref}가 requirements.md에 없음")
for code in sorted(set(re.findall(r"\b([EWI]-[A-Z]+-\d{3})\b", doc))):
    if code not in ERRS:
        problems.append(f"오류 코드 {code}가 API 계약서 8절에 없음")
if problems:
    print("\n".join(problems))
    raise SystemExit(f"인용 문제 {len(problems)}개 — 화면설계서를 쓰지 않음")
paths.write_text(OUT, doc)
print(f"화면 {len(U.SCREENS)} · 대화상자 {len(U.DIALOGS)}+{len(U.SMALL)} · 요소 {n_rows} · 메시지 {len(ERRS)} · "
      f"함수 {len(set(used) & SERVICE)}/{len(SERVICE)} → {OUT} {len(doc)} chars")
