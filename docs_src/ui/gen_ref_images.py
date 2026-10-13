"""화면 참고 이미지 2장: docs/화면참고_분석결과.png, docs/화면참고_결과엑셀.png

'화면명세서_GPT용.md'를 GPT에 줄 때 함께 첨부하는, 색과 모양의 기준 그림이다.
S06(분석 결과와 경고)과 S08(결과와 엑셀 내보내기)의 문구와 숫자를 명세서 그대로 쓴다.
스텁 서비스의 시험 데이터(사진 21장, 판별 가능 20장, 허리 굽힘 7장, 대표 사진 8번)와 같다.

    python docs_src/ui/gen_ref_images.py

(이전 그림은 영상 기준 발표 화면을 잘라 만든 것이어서 '.mp4', '7.2초', 시간 막대가 들어 있었다.)
"""
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE.parent / "render"))
import paths  # noqa: E402
from render import cleanup_profiles, html_png  # noqa: E402

DOCS = paths.DOCS
FLAGGED_AT = {1, 4, 7, 9, 12, 15, 18}     # 판별 가능한 사진 20장 안에서의 자리 (0부터). 7번째가 대표 사진(8번)
KEY_NO = 8                                # 대표 사진 (사진 번호는 1부터)
INVALID_NO = 21                           # 판별 불가 1장 (스텁은 맨 뒤 사진)

FONT = "'IBM Plex Sans KR','Malgun Gothic',sans-serif"
CSS = f"""
html,body{{margin:0;padding:0;background:#E6EBF0;font-family:{FONT};color:#18232F;word-break:keep-all}}
p{{margin:0}}
.abs{{position:absolute}}
"""


def line(x, y, w, deg):
    return (f'<div class="abs" style="left:{x}px;top:{y}px;width:{w}px;height:8px;background:#F0A065;'
            f'border-radius:4px;transform:rotate({deg}deg)"></div>')


def dot(x, y):
    return f'<div class="abs" style="left:{x}px;top:{y}px;width:16px;height:16px;border-radius:50%;background:#F2F4F6"></div>'


def figure():
    """허리를 깊이 굽혀 바닥의 상자를 드는 사람 (관절 선과 점). 머리는 회색 모자이크로 가린다."""
    parts = [
        '<div class="abs" style="left:120px;top:400px;width:600px;height:4px;background:#3B4A5A"></div>',
        '<div class="abs" style="left:470px;top:310px;width:120px;height:80px;border:4px solid #C9D3DC;border-radius:6px"></div>',
        line(319, 186, 161, -29.7), line(461, 124, 67, -42), line(442, 186, 85, 69.4),
        line(465, 266, 81, 82.9), line(298, 271, 95, 71.6), line(309, 356, 83, 104),
        dot(322, 222), dot(462, 142), dot(492, 222), dot(502, 302), dot(352, 312), dot(332, 392),
    ]
    for r in range(5):               # 머리 모자이크 5×5
        for c in range(5):
            shade = "#9AA7B4" if (r + c) % 2 == 0 else "#7C8996"
            parts.append(f'<div class="abs" style="left:{485 + 14 * c}px;top:{65 + 16 * r}px;width:14px;height:16px;background:{shade}"></div>')
    return "".join(parts)


def still_strip():
    """사진 21칸: 주황 = 허리 20° 이상 굽힌 사진, 짙은 회색 = 판별 불가, 흰 테두리 = 대표 사진."""
    cells, k = [], 0
    w, gap, x0 = 30, 6, 45
    for i in range(21):
        no = i + 1
        if no == INVALID_NO:
            bg = "#6B7885"
        else:
            bg = "#D9661F" if k in FLAGGED_AT else "#C9D3DC"
            k += 1
        edge = "3px solid #FFFFFF" if no == KEY_NO else "none"
        cells.append(f'<div class="abs" style="left:{x0 + i * (w + gap)}px;top:430px;width:{w}px;height:44px;'
                     f'border-radius:5px;background:{bg};border:{edge};box-sizing:border-box"></div>')
    return "".join(cells)


def analysis_result_html():
    return f"""
<div style="padding:14px;width:1500px">
<div style="width:1500px;height:704px;display:flex;flex-direction:column;background:#FBFCFD;border:3px solid #18232F;border-radius:18px;overflow:hidden;box-sizing:border-box">
 <div style="height:52px;display:flex;align-items:center;gap:16px;background:#18232F;padding:0 24px;flex:none">
  <p style="font-size:22px;color:#F2F4F6;font-weight:500">유해요인조사 보조 · 분석 결과 — 작업: 상자 들어 옮기기</p>
  <div style="flex:1"></div>
  <p style="font-size:22px;color:#C9D3DC">사진 21장 · 판별 가능 20장</p>
 </div>
 <div style="flex:1;display:flex;gap:24px;padding:24px">
  <div style="width:840px;position:relative;background:#22303F;border-radius:12px;overflow:hidden">
   {figure()}
   <p class="abs" style="left:20px;top:16px;font-size:22px;color:#F2F4F6;font-weight:700;background:#B5521A;border-radius:8px;padding:4px 12px">REBA 9</p>
   <p class="abs" style="right:20px;top:20px;font-size:22px;color:#C9D3DC">가장 위험한 사진 · 8번</p>
   {still_strip()}
   <p class="abs" style="left:40px;top:488px;font-size:22px;color:#9FB0C0">주황 = 허리를 20° 이상 굽힌 사진 7장 / 20장 = 35%</p>
  </div>
  <div style="flex:1;display:flex;flex-direction:column;gap:12px">
   <div style="display:flex;flex-direction:column;gap:6px;background:#F2F4F6;border-radius:12px;padding:18px 20px">
    <p style="font-size:22px;color:#5D6B78">가장 높은 점수</p>
    <p style="font-size:44px;font-weight:700;color:#B5521A">REBA 9 · 높음</p>
    <p style="font-size:22px;color:#3D4B59">목 2 · 몸통 4 · 다리 2 · 위팔 3 · 무게 15kg</p>
   </div>
   <div style="display:flex;flex-direction:column;gap:8px;background:#F2F4F6;border-radius:12px;padding:18px 20px">
    <p style="font-size:22px;color:#5D6B78">4호 · 허리 20° 이상 굽힘 · 기준 하루 총 2시간</p>
    <div style="display:flex;align-items:baseline;gap:10px">
     <p style="font-size:34px;font-weight:700;color:#B5521A">2.1시간</p>
     <p style="font-size:22px;color:#3D4B59">= 사진 표본 35% × 하루 6시간</p>
    </div>
    <div style="position:relative;width:548px;height:20px;background:#D5DDE5;border-radius:10px">
     <div class="abs" style="left:0;top:0;width:288px;height:20px;background:#D9661F;border-radius:10px"></div>
     <div class="abs" style="left:272px;top:-6px;width:4px;height:32px;background:#18232F"></div>
    </div>
    <p style="font-size:20px;color:#5D6B78">각도 기준: 고용노동부 해설</p>
   </div>
   <div style="display:flex;flex-direction:column;gap:6px;background:#FFF4EB;border:3px solid #D9661F;border-radius:12px;padding:18px 20px">
    <p style="font-size:22px;font-weight:700;color:#B5521A">경고</p>
    <p style="font-size:26px;font-weight:700;line-height:1.35">부담작업 4호 기준(하루 총 2시간)을 넘습니다</p>
    <p style="font-size:22px;color:#3D4B59;line-height:1.4">AI 작성 · 상자를 허리 높이 선반에 두면 굽힘을 줄일 수 있어요.</p>
   </div>
  </div>
 </div>
</div>
</div>"""


def thumb():
    return ('<div style="width:72px;height:44px;background:#22303F;border-radius:4px;display:flex;align-items:center;'
            'justify-content:center"><div style="width:16px;height:18px;background:#8A97A4"></div></div>')


def result_excel_html():
    rows = [("상자 들어 옮기기", "9", "높음"), ("선반 정리", "6", "보통"), ("수레 밀기", "5", "보통")]
    cell = "display:flex;align-items:center;padding:10px 14px;border-bottom:1px solid #D5DDE5"
    head = "display:flex;align-items:center;padding:12px 14px;border-bottom:2px solid #18232F"
    excel_rows = "".join(
        f'<div style="{cell}"><p style="font-size:20px">{a}</p></div><div style="{cell}"><p style="font-size:20px">{b}</p></div>'
        f'<div style="{cell}"><p style="font-size:20px">{c}</p></div><div style="{cell}">{thumb()}</div>' for a, b, c in rows)
    return f"""
<div style="padding:14px;width:1666px;display:flex;gap:40px;align-items:flex-start">
 <div style="width:850px;display:flex;flex-direction:column;gap:14px;align-items:center">
  <div style="width:100%;display:flex;flex-direction:column;background:#FBFCFD;border:3px solid #18232F;border-radius:18px;overflow:hidden;box-sizing:border-box">
   <div style="height:52px;display:flex;align-items:center;background:#18232F;padding:0 24px">
    <p style="font-size:22px;color:#F2F4F6;font-weight:500">유해요인조사 보조 · 작업별 결과</p>
   </div>
   <div style="display:flex;flex-direction:column;gap:18px;padding:24px">
    <table style="font-size:22px;color:#18232F;border-collapse:collapse;width:100%">
     <tr style="border-bottom:2px solid #18232F"><th style="width:34%;text-align:left;padding:10px 6px">작업</th><th style="width:18%;text-align:left">REBA</th><th style="width:18%;text-align:left">하루 노출</th><th style="width:30%;text-align:left">판정 초안</th></tr>
     <tr style="border-bottom:1px solid #D5DDE5"><td style="padding:12px 6px">상자 들어 옮기기</td><td><b style="color:#B5521A">9 높음</b></td><td>2.1시간</td><td>4호 해당 · <b style="color:#8A5A00">사람 확인</b></td></tr>
     <tr style="border-bottom:1px solid #D5DDE5"><td style="padding:12px 6px">선반 정리</td><td>6 보통</td><td>0.7시간</td><td>해당 없음</td></tr>
     <tr style="border-bottom:1px solid #D5DDE5"><td style="padding:12px 6px">수레 밀기</td><td>5 보통</td><td>0.4시간</td><td>입력 필요</td></tr>
    </table>
    <div style="display:flex;gap:14px">
     <p style="font-size:22px;font-weight:700;background:#D9661F;color:#18232F;border-radius:10px;padding:12px 24px">엑셀로 내보내기</p>
     <p style="font-size:22px;font-weight:700;background:#E6EBF0;color:#18232F;border-radius:10px;padding:12px 24px">조사자 확정</p>
    </div>
   </div>
  </div>
  <p style="font-size:24px;font-weight:700">프로그램 화면</p>
 </div>
 <div style="width:740px;display:flex;flex-direction:column;gap:14px;align-items:center">
  <div style="width:100%;display:flex;flex-direction:column;background:#FFFFFF;border:3px solid #1D6F42;border-radius:18px;overflow:hidden;box-sizing:border-box">
   <div style="height:52px;display:flex;align-items:center;background:#1D6F42;padding:0 24px">
    <p style="font-size:22px;color:#FFFFFF;font-weight:500">보고서_2026-10-23.xlsx</p>
   </div>
   <div style="display:grid;grid-template-columns:40fr 16fr 18fr 26fr;color:#18232F">
    <div style="{head}"><p style="font-size:20px;font-weight:700;color:#3D4B59">작업</p></div>
    <div style="{head}"><p style="font-size:20px;font-weight:700;color:#3D4B59">REBA</p></div>
    <div style="{head}"><p style="font-size:20px;font-weight:700;color:#3D4B59">위험</p></div>
    <div style="{head}"><p style="font-size:20px;font-weight:700;color:#3D4B59">대표 사진</p></div>
    {excel_rows}
   </div>
   <div style="display:flex;gap:4px;background:#E6EBF0;padding:8px 12px">
    <p style="font-size:20px;color:#5D6B78;padding:4px 12px">요약</p>
    <p style="font-size:20px;color:#1D6F42;font-weight:700;background:#FFFFFF;border-radius:4px;padding:4px 12px">작업별 결과</p>
    <p style="font-size:20px;color:#5D6B78;padding:4px 12px">경고 기록</p>
    <p style="font-size:20px;color:#5D6B78;padding:4px 12px">판정 초안</p>
   </div>
  </div>
  <p style="font-size:24px;font-weight:700">내보낸 엑셀</p>
 </div>
</div>"""


if __name__ == "__main__":
    out1 = DOCS / "화면참고_분석결과.png"
    out2 = DOCS / "화면참고_결과엑셀.png"
    html_png(analysis_result_html(), out1, 1528, 732, scale=1, name="ref_analysis", css=CSS)
    html_png(result_excel_html(), out2, 1694, 500, scale=1, name="ref_excel", css=CSS)
    cleanup_profiles()
    print("→", out1.name, out2.name)
