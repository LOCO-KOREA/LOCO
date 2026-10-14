"""UI 시안(docs/ui/svg)의 전체 미리보기와 PNG 미리보기를 만든다.

- svg/01~08은 사람이 고치는 원본이다. svg/00_전체미리보기.svg는 01~08을 한 장에 모은 것이라
  이 스크립트가 다시 조립한다 (주석은 빼고, 3열 격자, 화면마다 480x341). 손으로 고치지 않는다.
- png/*.png는 svg를 헤드리스 Edge로 그린 미리보기다 (화면 1440x1024, 전체 미리보기는 SVG 크기).

    python docs_src/ui/gen_ui_previews.py

원본 SVG를 고쳤는데 이 스크립트를 안 돌리면 00과 png가 낡는다. build_all.py에 들어 있다.
"""
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE.parent / "render"))
import paths  # noqa: E402
from render import cleanup_profiles, html_png  # noqa: E402

UI = paths.DOCS / "ui"
SVG = UI / "svg"
PNG = UI / "png"
OVERVIEW = SVG / "00_전체미리보기.svg"
TITLE = "LOCO MVP · 핵심 화면 8개"
COLS, CELL_W, CELL_H, GAP_X, GAP_Y = 3, 480, 341, 504, 371


def compose_overview(files):
    """01~08 원본에서 전체 미리보기 SVG 문자열을 만든다."""
    out = ["<?xml version='1.0' encoding='utf-8'?>\n"]
    rows = (len(files) + COLS - 1) // COLS
    width = 24 + (COLS - 1) * GAP_X + CELL_W + 24
    height = 90 + (rows - 1) * GAP_Y + CELL_H + 24
    out.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">'
               '<rect width="100%" height="100%" fill="#DDE3EA" />'
               f'<text x="24" y="55" font-family="Malgun Gothic,sans-serif" font-size="24" font-weight="700" fill="#172230">{TITLE}</text>\n')
    for i, p in enumerate(files):
        text = p.read_text(encoding="utf-8")
        m = re.match(r"<svg [^>]*>", text)
        assert m, f"{p.name}: <svg> 시작 태그가 없다"
        inner = text[m.end():].rstrip()
        assert inner.endswith("</svg>"), f"{p.name}: </svg>로 끝나지 않는다"
        inner = re.sub(r"<!--.*?-->", "", inner[: -len("</svg>")], flags=re.S)
        x, y = 24 + (i % COLS) * GAP_X, 90 + (i // COLS) * GAP_Y
        out.append(f'<text x="{x}" y="{y - 5}" font-family="Malgun Gothic,sans-serif" font-size="14" fill="#172230">{p.stem}</text>'
                   f'<svg x="{x}" y="{y}" width="{CELL_W}" height="{CELL_H}" viewBox="0 0 1440 1024">{inner}</svg>\n')
    out.append("</svg>")
    return "".join(out)


def render(svg_path, out_path, name):
    text = re.sub(r"^<\?xml[^>]*\?>\s*", "", svg_path.read_text(encoding="utf-8"))
    m = re.search(r"<svg[^>]*\bwidth=\"(\d+)\"[^>]*\bheight=\"(\d+)\"", text)
    w, h = int(m.group(1)), int(m.group(2))
    html_png(f'<div style="width:{w}px;height:{h}px;overflow:hidden">{text}</div>', out_path, w, h, scale=1, name=name)
    return w, h


if __name__ == "__main__":
    files = sorted(p for p in SVG.glob("*.svg") if not p.name.startswith("00_"))
    assert len(files) == 8, f"화면 SVG가 8개가 아니다: {[p.name for p in files]}"
    paths.write_text(OVERVIEW, compose_overview(files))
    print("전체 미리보기 조립:", OVERVIEW.name)
    PNG.mkdir(parents=True, exist_ok=True)
    for i, p in enumerate([OVERVIEW] + files):
        w, h = render(p, PNG / (p.stem + ".png"), f"uiprev_{i}")
        print(f"  {p.stem}.png {w}x{h}")
    cleanup_profiles()
