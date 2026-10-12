"""ERD 그림: schema_v1.sql을 읽어 draw.io 파일(4쪽)과 PNG 4장을 만든다.

- 테이블, 컬럼, PK, FK, 관계의 카디널리티는 모두 스키마에서 읽는다 (손으로 적지 않는다).
  · 부모 쪽: 자식의 FK가 NOT NULL이면 '반드시 하나'(||), NULL이면 '없거나 하나'(|o)
  · 자식 쪽: FK가 자식의 PK 전체이거나 단독 UNIQUE면 '없거나 하나'(o|), 아니면 '없거나 여럿'(o<)
  · FK가 자식 PK에 들어 있으면 식별 관계(실선), 아니면 비식별 관계(점선)
- 위치만 손으로 정한다. 선이 다른 테이블을 지나가지 않는지 기하 검사를 하고, 지나가면 멈춘다.
- PNG는 draw.io 공식 뷰어로 그린다 (draw.io 앱과 같은 엔진).
"""
import ast
import html
import re
import sqlite3
import sys
from pathlib import Path
from xml.sax.saxutils import escape as xesc

sys.stdout.reconfigure(encoding="utf-8")
HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE.parent / "render"))
import paths  # noqa: E402
from render import cleanup_profiles, crop_to_content, drawio_png  # noqa: E402

DOCS = paths.DOCS
OUT_DRAWIO = DOCS / "ERD.drawio"
OUT_DIR = DOCS / "ERD_그림"

# ---------------------------------------------------------------- 스키마 읽기
db = sqlite3.connect(":memory:")
db.executescript(paths.SCHEMA_FILE.read_text(encoding="utf-8"))
TABLES = [r[0] for r in db.execute(
    "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY rowid")]
COLS, PK, FK, UNIQUE1 = {}, {}, {}, {}
for t in TABLES:
    info = db.execute(f"PRAGMA table_xinfo({t})").fetchall()          # cid, name, type, notnull, dflt, pk, hidden
    COLS[t] = [(r[1], r[2], bool(r[3]), r[5]) for r in info]
    PK[t] = [r[1] for r in sorted(info, key=lambda r: r[5]) if r[5] > 0]
    FK[t] = [(r[3], r[2], r[4]) for r in db.execute(f"PRAGMA foreign_key_list({t})")]  # from, parent, to
    UNIQUE1[t] = set()
    for _, iname, uniq, origin, partial in db.execute(f"PRAGMA index_list({t})"):
        if uniq and not partial:
            icols = [r[2] for r in db.execute(f"PRAGMA index_info({iname})")]
            if len(icols) == 1:
                UNIQUE1[t].add(icols[0])

# 한글 이름: gen_doc.py의 설명 사전 D (문서와 같은 이름을 쓴다)
src = (HERE / "gen_doc.py").read_text(encoding="utf-8")
node = next(n for n in ast.parse(src).body if isinstance(n, ast.Assign) and getattr(n.targets[0], "id", "") == "D")
KNAME = {t: v[0] for t, v in ast.literal_eval(node.value).items()}
assert set(KNAME) == set(TABLES), set(TABLES) ^ set(KNAME)

AREA = {   # ERD 5.1 주제 영역
    "기준 정보": ["criterion", "threshold_default", "pose_model"],
    "조사": ["survey", "survey_reason", "participant", "survey_threshold"],
    "작업과 입력": ["unit_task", "task_input", "repetition_input", "lift_position_input", "reba_input"],
    "영상과 분석": ["video", "analysis_run", "frame_angle", "reba_result", "key_frame_image"],
    "판정과 경고": ["judgment", "judgment_basis", "warning", "ai_text"],
    "이력과 설정": ["edit_log", "export_log", "app_setting", "schema_version"],
}
COLOR = {"기준 정보": ("#E8EEF5", "#5D6B78"), "조사": ("#FDEBD9", "#C2571A"), "작업과 입력": ("#E3F1E3", "#3F7F3F"),
         "영상과 분석": ("#E9E7F8", "#5550A0"), "판정과 경고": ("#FBE3E3", "#A83A3A"), "이력과 설정": ("#EEEEEE", "#6E6E6E")}
AREA_OF = {t: a for a, ts in AREA.items() for t in ts}
assert set(AREA_OF) == set(TABLES)

# ---------------------------------------------------------------- 관계 (스키마에서 계산)
REL = []
for child in TABLES:
    for fcol, parent, pcol in FK[child]:
        notnull = next(c[2] for c in COLS[child] if c[0] == fcol) or fcol in PK[child]
        REL.append({
            "parent": parent, "child": child, "fcol": fcol, "pcol": pcol,
            "identifying": fcol in PK[child],
            "one": PK[child] == [fcol] or fcol in UNIQUE1[child],
            "parent_optional": not notnull,
        })


def markers(r):
    start = "ERzeroToOne" if r["parent_optional"] else "ERmandOne"
    end = "ERzeroToOne" if r["one"] else "ERzeroToMany"
    return start, end


def mermaid_card(r):
    return ("|o" if r["parent_optional"] else "||") + "--" + ("o|" if r["one"] else "o{")


# 개념 ERD의 관계 이름 (부모, 자식) → 이름. 빠지면 멈춘다
LABEL = {
    ("criterion", "threshold_default"): "각도를 정함", ("threshold_default", "survey_threshold"): "조사별로 바뀜",
    ("survey", "survey_threshold"): "적용", ("survey", "survey_reason"): "수시 사유", ("survey", "participant"): "참여",
    ("survey", "unit_task"): "포함", ("unit_task", "task_input"): "작업 정보", ("unit_task", "repetition_input"): "부위별 반복",
    ("unit_task", "lift_position_input"): "위치별 들기", ("unit_task", "reba_input"): "REBA 사람 입력",
    ("unit_task", "video"): "영상", ("unit_task", "analysis_run"): "분석", ("video", "analysis_run"): "분석 대상",
    ("pose_model", "analysis_run"): "사용 모델", ("analysis_run", "frame_angle"): "프레임별 각도",
    ("analysis_run", "reba_result"): "REBA 결과", ("reba_result", "key_frame_image"): "대표 장면",
    ("unit_task", "judgment"): "호마다 판정", ("criterion", "judgment"): "기준", ("analysis_run", "judgment"): "근거 분석",
    ("judgment", "judgment_basis"): "근거 값", ("unit_task", "warning"): "경고", ("criterion", "warning"): "기준",
    ("judgment", "warning"): "근거 판정", ("warning", "ai_text"): "조언 문장", ("survey", "ai_text"): "요약 문장",
    ("survey", "edit_log"): "수정 이력", ("survey", "export_log"): "엑셀 기록",
}
assert {(r["parent"], r["child"]) for r in REL} == set(LABEL), {(r["parent"], r["child"]) for r in REL} ^ set(LABEL)
LABEL_POS = {("unit_task", "warning"): 0.55}   # 선이 겹치는 곳에서 이름이 겹치지 않게 (−1 부모 쪽 … 1 자식 쪽)

# 문서 5.5절 관계 정의 표의 카디널리티가 스키마와 같은지 대조한다
tpl = (HERE / "erd_template.md").read_text(encoding="utf-8")
sec55 = tpl[tpl.index("### 5.5 관계 정의"):tpl.index("### 5.6")]
MISMATCH = []
for parent, children, card in re.findall(r"^\| (\w+) \| ([^|]+?) \| (\S+ : \S+) \|", sec55, re.M):
    for child in re.findall(r"[a-z_]+", children):
        r = next((r for r in REL if r["parent"] == parent and r["child"] == child), None)
        if r is None:
            MISMATCH.append(f"5.5절에 있는데 스키마에 없는 관계 {parent} → {child}")
            continue
        want = ("0..1" if r["parent_optional"] else "1") + " : " + ("0..1" if r["one"] else "0..N")
        if card != want:
            MISMATCH.append(f"{parent} → {child}: 5.5절 {card}, 스키마 {want}")
listed = {(p, c) for p, cs, _ in re.findall(r"^\| (\w+) \| ([^|]+?) \| (\S+ : \S+) \|", sec55, re.M)
          for c in re.findall(r"[a-z_]+", cs)}
MISMATCH += [f"5.5절에 빠진 관계 {p} → {c}" for p, c in sorted({(r["parent"], r["child"]) for r in REL} - listed)]

# ---------------------------------------------------------------- draw.io 조각
ROW, HEAD, KW, NW, TW = 22, 30, 44, 184, 76
W = KW + NW + TW
LINE = "#5D6B78"


class Page:
    def __init__(self, pid, name, title):
        self.pid, self.name, self.title, self.cells, self.n = pid, name, title, [], 0
        self.rects, self.ports, self.edges = {}, {}, []

    def nid(self, p):
        self.n += 1
        return f"{self.pid}{p}{self.n}"

    def add(self, xml):
        self.cells.append(xml)

    def text(self, x, y, w, h, value, size=12, color="#18232F", bold=False, align="left"):
        self.add(f'<mxCell id="{self.nid("x")}" value="{xesc(value, {chr(34): "&quot;"})}" '
                 f'style="text;html=1;whiteSpace=wrap;align={align};verticalAlign=top;fontSize={size};'
                 f'fontColor={color};fontStyle={1 if bold else 0};" vertex="1" parent="1">'
                 f'<mxGeometry x="{x}" y="{y}" width="{w}" height="{h}" as="geometry"/></mxCell>')

    def table(self, t, x, y, stub=False):
        fill, stroke = COLOR[AREA_OF[t]]
        cols = [c for c in COLS[t] if c[3] > 0] if stub else COLS[t]
        rows = len(cols) + (1 if stub else 0)
        h = HEAD + rows * ROW
        tid = f"{self.pid}t_{t}"
        label = f"{t}&lt;br&gt;&lt;span style=&quot;font-weight:normal;font-size:11px&quot;&gt;{KNAME[t]}{' · 다른 그림에 있음' if stub else ''}&lt;/span&gt;"
        self.add(f'<mxCell id="{tid}" value="{label}" style="shape=table;startSize={HEAD};container=1;collapsible=0;'
                 f'childLayout=tableLayout;fixedRows=1;rowLines=0;fontStyle=1;align=center;resizeLast=1;html=1;'
                 f'fillColor={"#F4F4F4" if stub else fill};strokeColor={stroke};fontSize=13;'
                 f'{"dashed=1;" if stub else ""}swimlaneFillColor=#FFFFFF;" vertex="1" parent="1">'
                 f'<mxGeometry x="{x}" y="{y}" width="{W}" height="{h}" as="geometry"/></mxCell>')
        fk_cols = {f[0] for f in FK[t]}
        for i, (name, typ, notnull, pkpos) in enumerate(cols):
            rid = f"{tid}_{name}"
            key = "PK, FK" if pkpos and name in fk_cols else "PK" if pkpos else "FK" if name in fk_cols else ""
            last_pk = pkpos and (i + 1 == len(cols) or cols[i + 1][3] == 0)
            self.add(f'<mxCell id="{rid}" value="" style="shape=tableRow;horizontal=0;startSize=0;swimlaneHead=0;'
                     f'swimlaneBody=0;fillColor=#FFFFFF;collapsible=0;dropTarget=0;points=[[0,0.5],[1,0.5]];'
                     f'portConstraint=eastwest;top=0;left=0;right=0;bottom={1 if last_pk else 0};html=1;'
                     f'strokeColor={stroke};" vertex="1" parent="{tid}">'
                     f'<mxGeometry y="{HEAD + i * ROW}" width="{W}" height="{ROW}" as="geometry"/></mxCell>')
            for cx, cw, val, st in ((0, KW, key, "fontStyle=1;fontSize=10;align=center;"),
                                    (KW, NW, name, f"align=left;spacingLeft=4;fontSize=11;fontStyle={5 if pkpos else 0};"),
                                    (KW + NW, TW, typ + ("" if notnull or pkpos else " ?"),
                                     "align=left;spacingLeft=4;fontSize=10;fontColor=#6B7680;")):
                self.add(f'<mxCell id="{rid}_{cx}" value="{val}" style="shape=partialRectangle;connectable=0;'
                         f'fillColor=none;top=0;left=0;bottom=0;right=0;overflow=hidden;whiteSpace=wrap;html=1;{st}" '
                         f'vertex="1" parent="{rid}"><mxGeometry x="{cx}" width="{cw}" height="{ROW}" as="geometry">'
                         f'<mxRectangle width="{cw}" height="{ROW}" as="alternateBounds"/></mxGeometry></mxCell>')
            self.ports[(t, name)] = (rid, y + HEAD + i * ROW + ROW / 2)
        if stub:
            self.add(f'<mxCell id="{tid}_more" value="…" style="text;html=1;align=center;fontColor=#999999;" '
                     f'vertex="1" parent="{tid}"><mxGeometry y="{HEAD + len(cols) * ROW}" width="{W}" height="{ROW}" '
                     f'as="geometry"/></mxCell>')
        self.rects[t] = (x, y, W, h)

    def box(self, t, cx, cy, w=184, h=56):
        fill, stroke = COLOR[AREA_OF[t]]
        x, y = cx - w // 2, cy - h // 2
        label = (f"&lt;b&gt;{KNAME[t]}&lt;/b&gt;&lt;br&gt;&lt;span style=&quot;font-size:10px;"
                 f"color:#5D6B78&quot;&gt;{t}&lt;/span&gt;")
        self.add(f'<mxCell id="{self.pid}b_{t}" value="{label}" style="rounded=1;whiteSpace=wrap;html=1;arcSize=14;'
                 f'fillColor={fill};strokeColor={stroke};strokeWidth=1.5;fontSize=13;" vertex="1" parent="1">'
                 f'<mxGeometry x="{x}" y="{y}" width="{w}" height="{h}" as="geometry"/></mxCell>')
        self.rects[t] = (x, y, w, h)

    def edge(self, r, src, tgt, label="", er_style=True):
        start, end = markers(r)
        style = ("edgeStyle=entityRelationEdgeStyle;" if er_style else "") + (
            f"html=1;rounded=0;startArrow={start};endArrow={end};startFill=0;endFill=0;startSize=10;endSize=10;"
            f"strokeColor={LINE};strokeWidth=1.3;{'dashed=1;' if not r['identifying'] else ''}"
            f"fontSize=10;fontColor=#3D4B59;labelBackgroundColor=#FFFFFF;")
        pos = LABEL_POS.get((r["parent"], r["child"]), 0) if label else 0
        self.add(f'<mxCell id="{self.nid("e")}" value="{xesc(label)}" style="{style}" edge="1" parent="1" '
                 f'source="{src}" target="{tgt}"><mxGeometry x="{pos}" relative="1" as="geometry"/></mxCell>')

    def model(self):
        return ('<mxGraphModel dx="1600" dy="1000" grid="0" gridSize="10" guides="1" tooltips="1" connect="1" '
                'arrows="1" fold="1" page="0" pageScale="1" math="0" shadow="0"><root><mxCell id="0"/>'
                '<mxCell id="1" parent="0"/>' + "".join(self.cells) + "</root></mxGraphModel>")

    def bounds(self):
        xs = [x for x, y, w, h in self.rects.values()] + [x + w for x, y, w, h in self.rects.values()]
        ys = [y for x, y, w, h in self.rects.values()] + [y + h for x, y, w, h in self.rects.values()]
        return max(xs) + 60, max(ys) + 140


# ---------------------------------------------------------------- 기하 검사 (선이 다른 상자를 지나가는지)
def _inside(px, py, rect, pad=6):
    x, y, w, h = rect
    return x - pad < px < x + w + pad and y - pad < py < y + h + pad


def _hits(points, rects, skip):
    bad = set()
    for (x0, y0), (x1, y1) in zip(points, points[1:]):
        for k in range(1, 200):
            px, py = x0 + (x1 - x0) * k / 200, y0 + (y1 - y0) * k / 200
            for t, rc in rects.items():
                if t not in skip and _inside(px, py, rc):
                    bad.add(t)
    return bad


def check_straight(page):
    probs = []
    for r in page.edges:
        a, b = page.rects[r["parent"]], page.rects[r["child"]]
        ca, cb = (a[0] + a[2] / 2, a[1] + a[3] / 2), (b[0] + b[2] / 2, b[1] + b[3] / 2)
        hit = _hits([ca, cb], page.rects, {r["parent"], r["child"]})
        if hit:
            probs.append(f"[{page.name}] {r['parent']} → {r['child']} 선이 {sorted(hit)}를 지나감")
    return probs


def check_er(page, stub=30):
    """entityRelationEdgeStyle을 흉내 낸다: 옆으로 30px 나갔다가 곧게 이어 상대 옆으로 들어간다."""
    probs = []
    for r in page.edges:
        a, b = page.rects[r["parent"]], page.rects[r["child"]]
        ya, yb = page.ports[(r["parent"], r["pcol"])][1], page.ports[(r["child"], r["fcol"])][1]
        if b[0] >= a[0] + a[2]:                       # 자식이 오른쪽
            xa, xb, da, db = a[0] + a[2], b[0], stub, -stub
        elif b[0] + b[2] <= a[0]:                     # 자식이 왼쪽
            xa, xb, da, db = a[0], b[0] + b[2], -stub, stub
        else:                                         # 같은 열: 오른쪽으로 돌아 들어감
            xa, xb, da, db = a[0] + a[2], b[0] + b[2], stub, stub
        pts = [(xa, ya), (xa + da, ya), (xb + db, yb), (xb, yb)]
        hit = _hits(pts, page.rects, {r["parent"], r["child"]})
        if hit:
            probs.append(f"[{page.name}] {r['parent']}.{r['pcol']} → {r['child']}.{r['fcol']} 선이 {sorted(hit)}를 지나감")
    return probs


def overlap_check(page, gap=20):
    probs, items = [], list(page.rects.items())
    for i, (t1, (x1, y1, w1, h1)) in enumerate(items):
        for t2, (x2, y2, w2, h2) in items[i + 1:]:
            if x1 < x2 + w2 + gap and x2 < x1 + w1 + gap and y1 < y2 + h2 + gap and y2 < y1 + h1 + gap:
                probs.append(f"[{page.name}] {t1}와 {t2}가 너무 가깝거나 겹침")
    return probs


LEGEND = ("표기 (IE, 까마귀발): 선 끝 ‖ = 반드시 하나 · o| = 없거나 하나 · o&lt; = 없거나 여럿 · "
          "실선 = 식별 관계 (FK가 자식의 PK에 들어감) · 점선 = 비식별 관계")

# ---------------------------------------------------------------- 0쪽: 3단계 스키마
P0 = Page("s", "0 3단계 스키마", "3단계 스키마 (ANSI/SPARC) · 외부 · 개념 · 내부")
N_VIEW = db.execute("SELECT count(*) FROM sqlite_master WHERE type='view'").fetchone()[0]
N_INDEX = db.execute("SELECT count(*) FROM sqlite_master WHERE type='index' AND sql IS NOT NULL").fetchone()[0]
N_TRIGGER = db.execute("SELECT count(*) FROM sqlite_master WHERE type='trigger'").fetchone()[0]
N_WOR = sum("WITHOUT ROWID" in (r[0] or "") for r in db.execute("SELECT sql FROM sqlite_master WHERE type='table'"))
LEVELS = [
    ("ext", f"외부 스키마 · 사용자와 응용이 보는 모양 (뷰 {N_VIEW}개)", "#FFF8E6", "#B58A1E",
     [("조사자 화면", "S01 · S06 · S07 · S09"), ("엑셀 보고서", "요약 · 작업별 결과 · 경고 기록 · 판정 초안"),
      ("GPT 어댑터", "v_gpt_payload만 · 숫자만"), ("검증 담당", "엔진 결과 대조")], False),
    ("con", f"개념 스키마 · 전체 논리 구조 (엔티티 {len(TABLES)}개, 관계 {len(REL)}개, 무결성)", "#F3F6FA", "#5D6B78",
     [(a, f"엔티티 {len(ts)}개") for a, ts in AREA.items()], True),
    ("int", "내부 스키마 · 저장 구조 (SQLite 파일 1개)", "#F4F4F4", "#6E6E6E",
     [("SQLite 파일 1개", "사용자 폴더 · 관리자 권한 불필요"), (f"STRICT 테이블 {len(TABLES)}개", f"그중 WITHOUT ROWID {N_WOR}개"),
      (f"인덱스 {N_INDEX}개 · 트리거 {N_TRIGGER}개", "조회 경로 · 업무 규칙"), ("WAL · 외래키 켜기", "백업 · 보존 · 마이그레이션")], False),
]
LW, LH, GAPY = 1300, 150, 110
for i, (key, title, fill, stroke, items, colored) in enumerate(LEVELS):
    y = 70 + i * (LH + GAPY)
    P0.add(f'<mxCell id="s_{key}" value="" style="rounded=1;arcSize=4;whiteSpace=wrap;html=1;fillColor={fill};'
           f'strokeColor={stroke};strokeWidth=1.5;" vertex="1" parent="1">'
           f'<mxGeometry x="40" y="{y}" width="{LW}" height="{LH}" as="geometry"/></mxCell>')
    P0.text(60, y + 12, LW - 40, 26, title, size=15, bold=True)
    gap = 16
    bw = (LW - 40 - gap * (len(items) - 1)) / len(items)
    for j, (h1, h2) in enumerate(items):
        bf, bs = COLOR[h1] if colored else ("#FFFFFF", stroke)
        label = (f"&lt;b&gt;{h1}&lt;/b&gt;&lt;br&gt;&lt;span style=&quot;font-size:11px;color:#3D4B59&quot;&gt;"
                 f"{h2}&lt;/span&gt;")
        P0.add(f'<mxCell id="s_{key}_{j}" value="{label}" style="rounded=1;arcSize=10;whiteSpace=wrap;html=1;'
               f'fillColor={bf};strokeColor={bs};fontSize=13;" vertex="1" parent="1">'
               f'<mxGeometry x="{60 + j * (bw + gap):.0f}" y="{y + 54}" width="{bw:.0f}" height="78" as="geometry"/></mxCell>')
    P0.rects[key] = (40, y, LW, LH)
for a, b, label in (("ext", "con", "외부/개념 사상 = 뷰 → 논리적 독립성"), ("con", "int", "개념/내부 사상 = DDL → 물리적 독립성")):
    P0.add(f'<mxCell id="s_{a}_{b}" value="{label}" style="html=1;endArrow=block;endFill=1;strokeWidth=2;'
           f'strokeColor=#18232F;fontSize=13;fontStyle=1;labelBackgroundColor=#FFFFFF;" edge="1" parent="1" '
           f'source="s_{a}" target="s_{b}"><mxGeometry relative="1" as="geometry"/></mxCell>')
P0.text(40, 10, 1300, 30, P0.title, size=18, bold=True)

# ---------------------------------------------------------------- 1쪽: 개념 ERD
P1 = Page("c", "1 개념 ERD", "개념 ERD · 엔티티 25개와 관계 28개 (주제 영역별 색)")
CONCEPT = {
    "survey": (800, 210), "survey_reason": (560, 70), "participant": (800, 70), "edit_log": (1040, 70),
    "export_log": (1280, 70), "survey_threshold": (300, 210), "threshold_default": (300, 900),
    "criterion": (800, 900), "unit_task": (800, 430), "task_input": (500, 300), "repetition_input": (500, 390),
    "lift_position_input": (500, 480), "reba_input": (500, 570), "video": (1060, 330), "analysis_run": (1060, 470),
    "pose_model": (1270, 330), "frame_angle": (1060, 600), "reba_result": (1320, 600), "key_frame_image": (1560, 600),
    "judgment": (800, 700), "judgment_basis": (520, 700), "warning": (1060, 760), "ai_text": (1520, 210),
    "app_setting": (1320, 900), "schema_version": (1560, 900),
}
OFF = 70   # 제목 공간
for t, (cx, cy) in CONCEPT.items():
    P1.box(t, cx, cy + OFF)
for r in REL:
    P1.edges.append(r)
    P1.edge(r, f"cb_{r['parent']}", f"cb_{r['child']}", LABEL[(r["parent"], r["child"])], er_style=False)
P1.text(210, 10, 1200, 30, P1.title, size=18, bold=True)
P1.text(1230, 1010, 420, 40, "app_setting · schema_version: 다른 엔티티와 관계 없음 (설정, 스키마 버전)", size=11, color="#5D6B78")
legend_area = " · ".join(f'<span style="background:{COLOR[a][0]};border:1px solid {COLOR[a][1]};'
                         f'padding:1px 6px">{a}</span>' for a in AREA)   # text()가 한 번 이스케이프한다
P1.text(210, 1010, 1000, 24, "주제 영역: " + legend_area, size=12)
P1.text(210, 1040, 1300, 24, LEGEND, size=12, color="#3D4B59")

# ---------------------------------------------------------------- 2~4쪽: 논리·물리 ERD (컬럼 전체)
COLX = {"A": 40, "B": 480, "C": 920, "D": 1360}
TOP = 70
LOGICAL = [
    ("l2", "2 조사·작업과 입력", "논리·물리 ERD ① 기준 정보 · 조사 · 작업과 입력 (컬럼 전체)", [
        ("criterion", "A", 0), ("threshold_default", "A", 222), ("survey_threshold", "A", 422),
        ("survey", "B", 0), ("survey_reason", "B", 332), ("participant", "B", 466),
        ("unit_task", "C", 0), ("repetition_input", "C", 288), ("lift_position_input", "C", 444),
        ("task_input", "D", 0), ("reba_input", "D", 596)], set()),
    ("l3", "3 영상과 분석", "논리·물리 ERD ② 영상과 분석 (컬럼 전체)", [
        ("unit_task", "A", 0), ("pose_model", "A", 140),
        ("video", "B", 0), ("analysis_run", "B", 376),
        ("frame_angle", "C", 0), ("reba_result", "C", 530),
        ("key_frame_image", "D", 530)], {"unit_task"}),
    ("l4", "4 판정·경고·이력", "논리·물리 ERD ③ 판정과 경고 · 이력과 설정 (컬럼 전체)", [
        ("unit_task", "A", 0), ("criterion", "A", 112), ("analysis_run", "A", 224),
        ("judgment", "B", 0), ("warning", "B", 420), ("survey", "B", 690),
        ("judgment_basis", "C", 0), ("ai_text", "C", 420), ("edit_log", "C", 752), ("export_log", "C", 1084),
        ("app_setting", "D", 0), ("schema_version", "D", 156)], {"unit_task", "criterion", "analysis_run", "survey"}),
]
PAGES = [P0, P1]
for pid, name, title, placed, stubs in LOGICAL:
    pg = Page(pid, name, title)
    for t, col, y in placed:
        pg.table(t, COLX[col], TOP + y, stub=t in stubs)
    shown = {t for t, _, _ in placed}
    for r in REL:
        if r["parent"] in shown and r["child"] in shown and not (r["parent"] in stubs and r["child"] in stubs):
            if r["child"] in stubs:
                continue
            pg.edges.append(r)
            pg.edge(r, pg.ports[(r["parent"], r["pcol"])][0], pg.ports[(r["child"], r["fcol"])][0])
    pg.text(40, 10, 1300, 30, title, size=18, bold=True)
    bx, by = pg.bounds()
    pg.text(40, by - 100, 1500, 24, LEGEND + " · 타입 뒤 ? = NULL 허용 · 밑줄 = 기본키", size=12, color="#3D4B59")
    PAGES.append(pg)

# 관계가 빠짐없이 그려졌는지 (개념 ERD는 전부, 논리 ERD들은 합쳐서 전부)
drawn = {(r["parent"], r["child"], r["fcol"]) for pg in PAGES if pg.pid.startswith("l") for r in pg.edges}
all_rel = {(r["parent"], r["child"], r["fcol"]) for r in REL}
problems = [f"논리 ERD에 빠진 관계: {sorted(all_rel - drawn)}"] if drawn != all_rel else []
problems += check_straight(P1) + overlap_check(P1)
for pg in [q for q in PAGES if q.pid.startswith("l")]:
    problems += check_er(pg) + overlap_check(pg)
if problems:
    print("\n".join(problems))
    raise SystemExit(f"그림 문제 {len(problems)}개 — 파일을 쓰지 않음")

if MISMATCH:
    print("\n".join(MISMATCH))
    raise SystemExit(f"5.5절 관계 정의와 스키마가 다름 {len(MISMATCH)}개")
print("5.5절 관계 정의 ↔ 스키마: 28개 모두 같음")

# ---------------------------------------------------------------- 저장과 그리기
mxfile = ('<mxfile host="ergo-gen" modified="2026-10-12" agent="gen_erd_drawio.py" version="24.0.0">' +
          "".join(f'<diagram id="{pg.pid}" name="{pg.name}">{pg.model()}</diagram>' for pg in PAGES) + "</mxfile>")
paths.write_text(OUT_DRAWIO, mxfile)
OUT_DIR.mkdir(parents=True, exist_ok=True)
FILES = {"s": "ERD_0_3단계_스키마.png", "c": "ERD_1_개념.png", "l2": "ERD_2_조사_작업.png", "l3": "ERD_3_영상_분석.png", "l4": "ERD_4_판정_이력.png"}
for pg in PAGES:
    w, h = pg.bounds()
    out = OUT_DIR / FILES[pg.pid]
    drawio_png(pg.model(), out, w, h, scale=2, name=f"erd_{pg.pid}")
    _, size = crop_to_content(out, margin=40)
    print(f"{pg.name}: 상자 {len(pg.rects)} · 선 {len(pg.edges)} → {out.name} {size}")
cleanup_profiles()
print("relations", len(REL), "| identifying", sum(r["identifying"] for r in REL),
      "| 1:1", sum(r["one"] for r in REL), "| optional parent", sum(r["parent_optional"] for r in REL))

print("→", OUT_DRAWIO)
