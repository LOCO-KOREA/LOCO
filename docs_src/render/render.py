"""그림 만들기: Mermaid 코드나 draw.io XML을 헤드리스 Edge로 그려 PNG로 저장한다.

- mermaid_png(code, out): 1차로 --dump-dom 해서 그려진 SVG 크기를 재고, 2차로 그 크기에 맞춰 화면을 찍는다.
- drawio_png(xml, out, w, h): draw.io 공식 뷰어(viewer-static)로 그린다. draw.io 앱과 같은 엔진이다.
- html_png(html, out, w, h): 와이어프레임 같은 HTML을 그대로 찍는다.
"""
import html as _html
import json
import os
import shutil
import subprocess
from pathlib import Path

EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
WORK = Path(__file__).resolve().parents[1] / ".work" / "render"
WORK.mkdir(parents=True, exist_ok=True)
# Edge 프로필 폴더: TEMP의 8.3 짧은 경로(사용자 이름이 한글이면 USER~1 꼴로 바뀐다)나 너무 긴 경로를 쓰면 Edge가 조용히 아무것도 안 찍고 끝난다
PROFILE = Path.home() / "AppData" / "Local" / "Temp" / "ergo_edge"
FONT = "'IBM Plex Sans KR','Malgun Gothic',sans-serif"
FONT_LINK = ("<link href='https://fonts.googleapis.com/css2?family=IBM+Plex+Sans+KR:wght@400;500;700"
             "&display=swap' rel='stylesheet'>")


_RUN = [0]


def _shot(page: Path, out: Path, w: int, h: int, scale: float, budget: int, timeout: float = 120):
    """Edge 155부터 msedge.exe는 실제 브라우저를 따로 띄우고 바로 끝난다.
    그래서 끝나기를 기다리지 않고, 그림 파일이 생겨 크기가 멈출 때까지 기다린다.
    호출마다 새 프로필을 써서 앞 호출의 브라우저와 섞이지 않게 한다."""
    import time
    out = Path(out).resolve()             # 따로 뜬 브라우저는 작업 폴더가 달라 상대 경로가 엉뚱한 곳을 가리킨다
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.exists():
        out.unlink()
    _RUN[0] += 1
    profile = PROFILE / f"p{os.getpid()}_{_RUN[0]}"
    # --remote-debugging-port=0: 이게 없으면 Edge 155가 화면을 찍지 않고 끝나는 경우가 있다 (2026-10-12 실측)
    subprocess.run([EDGE, "--headless=new", "--remote-debugging-port=0", "--disable-gpu", "--hide-scrollbars", "--no-first-run",
                    f"--user-data-dir={profile}", f"--window-size={w},{h}", f"--force-device-scale-factor={scale}",
                    f"--virtual-time-budget={budget}", f"--screenshot={out}", page.as_uri()],
                   capture_output=True, timeout=60)
    t0, last = time.time(), -1
    while time.time() - t0 < timeout:
        if out.exists():
            size = out.stat().st_size
            if size > 0 and size == last:
                return out
            last = size
        time.sleep(0.4)
    raise RuntimeError(f"screenshot timed out: {out}")


def _stop_leftover_browsers():
    """_shot이 띄운 헤드리스 Edge는 그림을 찍어도 스스로 끝나지 않는다 (Edge 155부터).
    그대로 두면 프로필 폴더를 쥔 채 쌓여서 폴더 삭제가 끝나지 않는다 (2026-10-12 실측: 1,600개).
    이 PC에서 이 도구가 띄운 것만 (명령줄에 프로필 폴더가 들어 있는 것) 끈다. 사용자의 Edge는 건드리지 않는다."""
    if os.name != "nt":
        return
    # 폴더 이름만 보면 다른 도구의 프로필(deck_ergo_edge_profile 등)까지 걸리므로 '부모\폴더\'까지 맞춘다. 한글 경로를 피하려고 뒤 두 토막만 쓴다
    mark = f"\\{PROFILE.parent.name}\\{PROFILE.name}\\"
    ps = ("Get-CimInstance Win32_Process -Filter \"Name='msedge.exe'\" | "
          f"Where-Object {{ $_.CommandLine -like '*{mark}*' }} | "
          "ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }")
    try:
        subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", ps],
                       capture_output=True, timeout=120)
    except (OSError, subprocess.TimeoutExpired):
        pass


def cleanup_profiles():
    _stop_leftover_browsers()
    shutil.rmtree(PROFILE, ignore_errors=True)


def html_png(body_html: str, out: Path, w: int, h: int, scale: float = 2, name: str = "page", css: str = ""):
    page = WORK / f"{name}.html"
    page.write_text("<!doctype html><html><head><meta charset='utf-8'>" + FONT_LINK +
                    f"<style>html,body{{margin:0;padding:0;background:#fff}}{css}</style></head>"
                    f"<body>{body_html}</body></html>", encoding="utf-8")
    return _shot(page, out, w, h, scale, 6000)


def mermaid_png(code: str, out: Path, scale: float = 2, name: str = "mermaid", max_width: int = 1600):
    page = WORK / f"{name}.html"
    page.write_text(f"""<!doctype html><html><head><meta charset='utf-8'>{FONT_LINK}
<style>html,body{{margin:0;padding:0;background:#fff}} #box{{display:inline-block;padding:16px}}
#box svg{{max-width:{max_width}px !important}}</style>
<script src="https://cdn.jsdelivr.net/npm/mermaid@10.9.1/dist/mermaid.min.js"></script></head>
<body><div id="box"><pre class="mermaid">{_html.escape(code)}</pre></div>
<script>
mermaid.initialize({{startOnLoad:false, theme:'default', fontFamily:"{FONT.replace('"', '')}",
  themeVariables:{{fontFamily:"{FONT.replace('"', '')}"}}, er:{{useMaxWidth:false}}, flowchart:{{useMaxWidth:false}},
  sequence:{{useMaxWidth:false}}, gantt:{{useMaxWidth:false, useWidth:1400}} }});
Promise.race([document.fonts.load('16px "IBM Plex Sans KR"'), new Promise(r => setTimeout(r, 4000))])
  .then(() => mermaid.run()).catch(e => {{ document.body.innerHTML = '<p style="font-size:40px;color:red">MERMAID ERROR ' + e + '</p>'; }});
</script></body></html>""", encoding="utf-8")
    probe = WORK / f"{name}_probe.png"
    _shot(page, probe, 3200, 3200, 1, 10000)          # 1차: 크게 찍어서 그려진 범위를 잰다
    w, h = content_size(probe)
    probe.unlink()
    _shot(page, out, w + 16, h + 16, scale, 10000)
    return crop_to_content(out, margin=int(12 * scale))


def crop_to_content(png: Path, margin: int = 24, white: int = 250):
    """흰 여백을 잘라 내고 사방에 margin만큼 남긴다."""
    from PIL import Image
    im = Image.open(png).convert("RGB")
    box = im.convert("L").point(lambda v: 255 if v < white else 0).getbbox()
    if not box:
        raise RuntimeError(f"blank image: {png}")
    x0, y0 = max(0, box[0] - margin), max(0, box[1] - margin)
    x1, y1 = min(im.width, box[2] + margin), min(im.height, box[3] + margin)
    im.crop((x0, y0, x1, y1)).save(png, optimize=True)
    return png, (x1 - x0, y1 - y0)


def content_size(png: Path, white: int = 250):
    """흰 바탕이 아닌 부분의 오른쪽 아래 끝 (그림은 왼쪽 위에서 시작한다)."""
    from PIL import Image
    im = Image.open(png).convert("L").point(lambda v: 255 if v < white else 0)
    box = im.getbbox()
    if not box:
        raise RuntimeError(f"blank image: {png}")
    if box[2] >= im.width - 2 or box[3] >= im.height - 2:
        raise RuntimeError(f"drawing larger than the probe canvas: {box}")
    return box[2], box[3]


VIEWER = "https://viewer.diagrams.net/js/viewer-static.min.js"


def drawio_png(model_xml: str, out: Path, w: int, h: int, scale: float = 2, name: str = "drawio"):
    """model_xml = <mxGraphModel>...</mxGraphModel> 하나 (한 페이지)."""
    cfg = {"highlight": "#0000ff", "nav": False, "resize": False, "toolbar": "", "lightbox": False,
           "edit": None, "xml": model_xml, "border": 0}
    page = WORK / f"{name}.html"
    page.write_text("<!doctype html><html><head><meta charset='utf-8'>" + FONT_LINK +
                    "<style>html,body{margin:0;padding:0;background:#fff}</style></head><body>"
                    f"<div class='mxgraph' style='width:{w}px;height:{h}px' "
                    f"data-mxgraph=\"{_html.escape(json.dumps(cfg, ensure_ascii=False))}\"></div>"
                    f"<script src='{VIEWER}'></script></body></html>", encoding="utf-8")
    return _shot(page, out, w, h, scale, 12000)
