"""화면설계서 데이터: 화면마다 와이어프레임 HTML과 요소 표.

- 와이어프레임의 빨간 번호(n)와 요소 표의 번호가 같아야 한다 (gen_ui.py가 검사).
- 요소 표의 '데이터·동작'에는 API 함수 이름(괄호 포함)과 DTO.필드를 그대로 적는다 (gen_ui.py가 contracts.py와 대조).
- 예시 값은 ERD 시험 데이터와 덱(10/9 발표)의 예시와 같게 쓴다: 2026-10-23 정기조사, 포장공정, 상자 들어 옮기기,
  허리 굽힘 35% × 하루 6시간 = 2.10시간, REBA 9 (표 A 6 + 하중 2 = 8, 표 B 3 + 손잡이 0 = 3, 표 C 8 + 활동 1).
"""

W, H = 1366, 768

CSS = """
:root{--navy:#18232F;--tab:#E6EBF0;--bg:#F2F4F6;--card:#FBFCFD;--line:#D5DDE5;--orange:#D9661F;--risk:#B5521A;
--review:#F6E2B8;--muted:#5D6B78;--sub:#3D4B59;--text:#18232F}
*{box-sizing:border-box}
body{font-family:'IBM Plex Sans KR','Malgun Gothic',sans-serif;font-size:13px;color:var(--text);word-break:keep-all}
.win{width:1366px;height:768px;display:flex;flex-direction:column;background:var(--bg);overflow:hidden;position:relative}
.title{height:36px;flex:none;background:var(--navy);color:#F2F4F6;display:flex;align-items:center;gap:12px;padding:0 16px;font-size:14px}
.title .ctx{color:#C9D3DC;font-size:13px}.title .st{margin-left:auto}
.tabs{height:44px;flex:none;background:var(--tab);display:flex;align-items:flex-end;gap:2px;padding:0 12px;border-bottom:1px solid var(--line)}
.tab{padding:10px 18px 9px;font-size:14px;color:var(--sub);border-bottom:3px solid transparent;border-radius:6px 6px 0 0}
.tab.on{color:var(--text);font-weight:700;border-bottom-color:var(--orange);background:#fff}
.tab.off{color:#A9B4BF}
.task{margin-left:auto;align-self:center;background:#fff;border:1px solid #AEB9C4;border-radius:6px;padding:6px 12px;font-size:13px;position:relative}
.body{flex:1;padding:14px 18px;display:flex;gap:14px;min-height:0;position:relative}
.foot{height:26px;flex:none;background:#E9EDF1;border-top:1px solid var(--line);display:flex;align-items:center;padding:0 16px;font-size:11.5px;color:var(--muted)}
.foot .r2{margin-left:auto}
.col{display:flex;flex-direction:column;gap:12px;min-width:0}.row{display:flex;gap:12px;align-items:center}
.card{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:12px 14px;position:relative}
.card h3{font-size:14px;margin:0 0 8px}
h2{font-size:19px;margin:0}
.btn{display:inline-block;padding:7px 14px;border-radius:7px;border:1px solid #AEB9C4;background:#fff;font-size:13px;position:relative;white-space:nowrap}
.btn.p{background:var(--orange);border-color:var(--orange);color:#fff;font-weight:700}
.btn.dis{opacity:.45}.btn.s{padding:4px 10px;font-size:12px}
.lnk{color:#1F5FA8;text-decoration:underline;position:relative;margin-right:10px}
.badge{display:inline-block;padding:2px 8px;border-radius:999px;font-size:11.5px;font-weight:700;border:1px solid;white-space:nowrap}
.b-app{background:#FCE8DC;color:var(--risk);border-color:#E9B593}
.b-na{background:#EEF2F5;color:#5D6B78;border-color:#C9D3DC}
.b-rev{background:var(--review);color:#7A5A12;border-color:#E2C27A}
.b-in{background:#fff;color:#3D4B59;border-color:#8E9AA6;border-style:dashed}
.b-ok{background:#E3F1E3;color:#2F6B2F;border-color:#9CC59C}
.b-ai{background:#EEE9FB;color:#5550A0;border-color:#C4BEEB}
.b-draft{background:#FFF4E5;color:#9A5B12;border-color:#EBC48C}
.tbl{width:100%;border-collapse:collapse;font-size:12.5px}
.tbl th{text-align:left;color:var(--muted);font-weight:700;padding:8px 10px;border-bottom:2px solid var(--navy);background:#F7F9FA}
.tbl td{padding:7px 10px;border-bottom:1px solid var(--line);vertical-align:middle}
.fld{display:flex;flex-direction:column;gap:4px;position:relative}
.fld label{font-size:12px;color:var(--muted)}
.in{background:#fff;border:1px solid #AEB9C4;border-radius:6px;padding:6px 10px;min-height:32px;display:flex;align-items:center;gap:6px}
.in.empty{color:#9AA7B4}.in.err{border-color:#C62828;background:#FFF5F5}
.unit{color:var(--muted);margin-left:auto;font-size:12px}
.help{font-size:11.5px;color:var(--muted);line-height:1.45}
.err{font-size:11.5px;color:#C62828}
.seg{display:flex;border:1px solid #AEB9C4;border-radius:6px;overflow:hidden;background:#fff}
.seg span{padding:6px 12px;border-right:1px solid #AEB9C4}.seg span:last-child{border-right:0}
.seg .on{background:var(--navy);color:#fff;font-weight:700}
.chk{display:inline-flex;align-items:center;gap:6px}
.box{width:15px;height:15px;border:1.5px solid #5D6B78;border-radius:3px;display:inline-block;background:#fff}
.box.on{background:var(--navy);border-color:var(--navy);box-shadow:inset 0 0 0 3px #fff}
.radio{width:15px;height:15px;border:1.5px solid #5D6B78;border-radius:50%;display:inline-block;background:#fff}
.radio.on{background:var(--navy);box-shadow:inset 0 0 0 3px #fff}
.note{font-size:12px;color:var(--muted);position:relative}
.toast{position:absolute;right:18px;bottom:10px;background:#18232F;color:#fff;border-radius:8px;padding:9px 14px;font-size:12.5px;box-shadow:0 4px 14px rgba(0,0,0,.18)}
.toast b{color:#F6C28B}
.subtabs{display:flex;gap:4px;border-bottom:1px solid var(--line);margin:0 0 10px;position:relative}
.subtabs span{padding:6px 12px;font-size:12.5px;color:var(--sub);border-bottom:3px solid transparent}
.subtabs .on{border-bottom-color:var(--navy);font-weight:700;color:var(--text)}
.dot{display:inline-block;width:7px;height:7px;border-radius:50%;background:#C62828;margin-left:4px;vertical-align:middle}
.n{position:absolute;left:-10px;top:-10px;width:21px;height:21px;border-radius:50%;background:#C62828;color:#fff;
font:700 11.5px/21px Arial,sans-serif;text-align:center;z-index:9;box-shadow:0 0 0 2px #fff}
.r{position:relative}
.n + *:not(table){margin-left:13px}
.n2{position:relative;left:0;top:0;display:inline-block;margin-right:6px;vertical-align:middle}
.dlgwrap{width:100%;height:100%;background:rgba(24,35,47,.55);display:flex;align-items:center;justify-content:center}
.dlg{background:#fff;border-radius:12px;box-shadow:0 10px 40px rgba(0,0,0,.35);overflow:hidden;display:flex;flex-direction:column}
.dlg .dh{background:var(--navy);color:#fff;padding:12px 18px;font-size:15px;font-weight:700}
.dlg .db{padding:16px 18px;display:flex;flex-direction:column;gap:12px}
.dlg .df{padding:12px 18px;border-top:1px solid var(--line);display:flex;gap:8px;justify-content:flex-end;background:#F7F9FA}
"""

TABS = ["조사", "작업", "사진", "결과", "판정", "내보내기", "설정"]


def n(k):
    return f'<i class="n">{k}</i>'


def n2(k):          # 글줄 안에 넣는 번호 (글자를 가리지 않음)
    return f'<i class="n n2">{k}</i>'


def frame(active, body, task=True, ctx="2026-10-23 정기조사 · 포장공정", status="작성 중",
          foot_right="자동 저장됨 · 14:05", open_survey=True, task_n=None):
    tabs = []
    for t in TABS:
        cls = "on" if t == active else ("off" if (not open_survey and t not in ("조사", "설정")) else "")
        tabs.append(f'<span class="tab {cls}">{t}</span>')
    task_html = (f'<span class="task">{n(task_n) if task_n else ""}단위작업: <b>상자 들어 옮기기</b> ▾</span>'
                 if task else "")
    st = f'<span class="st"><span class="badge b-draft">{status}</span></span>' if open_survey else ""
    ctx_html = f'<span class="ctx">· {ctx}</span>' if open_survey else ""
    return (f'<div class="win"><div class="title"><b>유해요인조사 보조</b>{ctx_html}{st}</div>'
            f'<div class="tabs">{"".join(tabs)}{task_html}</div><div class="body">{body}</div>'
            f'<div class="foot">부담작업 해당 여부 결정과 조사 결과의 책임은 사업주와 조사자에게 있습니다.'
            f'<span class="r2">{foot_right}</span></div></div>')


def dialog(title, body, foot, w=560):
    return (f'<div class="dlgwrap"><div class="dlg" style="width:{w}px"><div class="dh">{title}</div>'
            f'<div class="db">{body}</div><div class="df">{foot}</div></div></div>')


# 사람 그림 (덱 screens1과 같은 좌표, 840×500 바탕을 줄여 씀). 머리는 회색 원
def figure(scale=0.78, w=840, h=500):
    limbs = [(319, 206, 161, -29.7), (461, 144, 67, -42), (442, 206, 85, 69.4), (465, 286, 81, 82.9),
             (298, 291, 95, 71.6), (309, 376, 83, 104)]
    joints = [(322, 242), (462, 162), (492, 242), (502, 322), (352, 332), (332, 412)]
    parts = [f'<div style="position:absolute;left:120px;top:420px;width:600px;height:4px;background:#3B4A5A"></div>',
             f'<div style="position:absolute;left:470px;top:330px;width:120px;height:80px;border:4px solid #C9D3DC;border-radius:6px"></div>']
    for x, y, L, a in limbs:
        parts.append(f'<div style="position:absolute;left:{x}px;top:{y}px;width:{L}px;height:8px;background:#F0A065;'
                     f'border-radius:4px;transform:rotate({a}deg);transform-origin:center"></div>')
    for x, y in joints:
        parts.append(f'<div style="position:absolute;left:{x}px;top:{y}px;width:16px;height:16px;border-radius:50%;background:#F2F4F6"></div>')
    parts.append('<div style="position:absolute;left:488px;top:90px;width:64px;height:64px;border-radius:50%;background:#9AA7B4"></div>')
    inner = "".join(parts)
    return (f'<div style="width:{w * scale:.0f}px;height:{h * scale:.0f}px;position:relative;overflow:hidden">'
            f'<div style="position:absolute;left:0;top:0;width:{w}px;height:{h}px;transform:scale({scale});transform-origin:0 0">'
            f'{inner}</div></div>')


SCREENS = []


def screen(**kw):
    SCREENS.append(kw)


# ---------------------------------------------------------------- S01 조사 목록
screen(id="S01", name="조사 목록", tab="조사", fids=["F01-02", "F01-03"],
       purpose="조사를 만들고, 저장된 조사를 고르거나 지운다. 프로그램을 켜면 처음 보이는 화면이다.",
       entry="프로그램 시작, 탭 '조사'", exit="S02 (새 조사), S03 (열기), D04 (삭제)",
       html=frame("조사", f'''
<div class="col" style="flex:1">
 <div class="row"><h2>조사 목록</h2><span class="note">조사일 최신순</span>
  <span class="btn p" style="margin-left:auto">{n(1)}+ 새 조사</span></div>
 <div class="card" style="padding:0">{n(2)}
  <table class="tbl"><tr><th>조사일</th><th>구분</th><th>작업공정 · 작업명</th><th>단위작업</th><th>남은 초안</th><th>상태</th><th>다음 정기조사 예정일</th><th></th></tr>
  <tr><td>2026-10-23</td><td>정기</td><td>포장공정 · 상자 포장 및 운반</td><td>3</td><td>31</td><td><span class="badge b-draft">작성 중</span></td><td>—</td>
      <td><span class="lnk">{n2(3)}열기</span><span class="lnk">{n2(4)}삭제</span></td></tr>
  <tr><td>2026-05-14</td><td>수시 (새 설비 도입)</td><td>포장공정 · 자동 포장기 투입</td><td>1</td><td>0</td><td><span class="badge b-ok">확정</span></td><td>— (수시조사는 바꾸지 않음)</td>
      <td><span class="lnk">열기</span><span class="lnk">삭제</span></td></tr>
  <tr><td>2023-10-20</td><td>정기</td><td>포장공정 · 상자 포장 및 운반</td><td>3</td><td>0</td><td><span class="badge b-ok">확정</span></td><td>2026-10-27</td>
      <td><span class="lnk">열기</span><span class="lnk">삭제</span></td></tr>
  </table></div>
 <div class="card" style="background:#F7F9FA">{n(5)}<h3>기록 보존 (지침 11)</h3>
  <div class="help">새 조사가 끝날 때까지 보존합니다. 근로자 신상정보가 있으면 5년, 개선계획은 해당 설비가 있는 동안 보존합니다.
  조사 기록은 이 PC의 사용자 폴더에만 저장되고, 자동으로 지우지 않습니다.</div></div>
 <div class="note">유해요인조사는 근로자 면담, 증상설문조사, 인간공학적 조사를 모두 해야 합니다. 이 프로그램은 인간공학적 조사와 면담 기록을 돕습니다.</div>
</div>''', task=False, open_survey=False, foot_right="v0.1"),
       rows=[
           (1, "+ 새 조사", "버튼 (주)", "S02를 빈 양식으로 연다", "—"),
           (2, "조사 목록 표", "표", "list_surveys() → SurveySummary.survey_date, SurveySummary.survey_type_cd, SurveySummary.process_name, "
               "SurveySummary.work_name, SurveySummary.task_cnt, SurveySummary.draft_judgment_cnt, SurveySummary.status_cd, "
               "SurveySummary.next_regular_due_date", "조사일 최신순 (F01-02 규칙 2). 예정일은 정기·최초 조사의 확정일 + 3년, 수시조사는 '—' (F01-03, AC-03)"),
           (3, "열기", "링크", "get_survey(survey_id) → S03. 마지막 상태 그대로 연다", "사진이 옮겨졌어도 결과는 보인다. 다시 분석할 때만 위치를 다시 고른다 (F01-02 규칙 4)"),
           (4, "삭제", "링크", "D04 → delete_survey(survey_id, actor)", "조사와 수정 이력이 함께 지워진다. 보존 기간을 확인하게 한다"),
           (5, "기록 보존 안내", "안내", "고정 문구", "NFR-014, BR-20"),
       ],
       states=["조사가 없으면 표 대신 \"아직 조사가 없습니다. '+ 새 조사'로 시작하세요.\"",
               "저장소 파일을 열 수 없으면 화면 위 띠에 E-DB-001"])

# ---------------------------------------------------------------- S02 조사 개요
screen(id="S02", name="조사 개요", tab="조사", fids=["F01-01"],
       purpose="조사 한 건의 기본 정보를 넣는다. 처음 저장하면 조사가 만들어지고, 그 뒤로는 바꿀 때마다 자동 저장된다.",
       entry="S01 '+ 새 조사', 탭 '조사'", exit="S03 (저장하고 작업 등록)",
       html=frame("조사", f'''
<div class="col" style="flex:1.3">
 <h2>조사 개요</h2>
 <div class="card col" style="gap:14px">
  <div class="fld">{n(1)}<label>조사 구분 *</label>
   <div class="row" style="gap:18px"><span class="chk"><i class="radio on"></i>정기조사</span><span class="chk"><i class="radio"></i>수시조사</span><span class="chk"><i class="radio"></i>최초조사 (신설 1년 이내)</span></div></div>
  <div class="fld">{n(2)}<label style="opacity:.55">수시조사 사유 * (수시조사일 때만, 하나 이상)</label>
   <div class="row" style="gap:16px;flex-wrap:wrap;opacity:.55"><span class="chk"><i class="box"></i>근골격계질환자 발생</span><span class="chk"><i class="box"></i>부담작업에 해당하는 새 작업·설비 도입</span><span class="chk"><i class="box"></i>업무량·작업공정 등 작업환경 변경</span></div></div>
  <div class="row" style="gap:14px;align-items:flex-start">
   <div class="fld" style="flex:1">{n(3)}<label>조사일 *</label><div class="in">2026-10-23<span class="unit">📅</span></div></div>
   <div class="fld" style="flex:1">{n(4)}<label>조사자 *</label><div class="in">홍길동</div><span class="help">수정 이력의 '누가'로 쓰입니다</span></div></div>
  <div class="row" style="gap:14px">{''}
   <div class="fld" style="flex:1">{n(5)}<label>부서 *</label><div class="in">포장부</div></div>
   <div class="fld" style="flex:1"><label>작업공정명 *</label><div class="in">포장공정</div></div>
   <div class="fld" style="flex:1.4"><label>작업명 *</label><div class="in">상자 포장 및 운반</div></div></div>
  <div class="row" style="justify-content:flex-end"><span class="btn">취소</span><span class="btn p">{n(6)}저장하고 작업 등록</span></div>
 </div>
</div>
<div class="col" style="flex:1">
 <div class="card">{n(7)}<h3>조사 구분 (규칙 제657조)</h3>
  <div class="help">· 정기조사: 3년마다<br>· 최초조사: 신설일부터 1년 이내<br>· 수시조사: 사유 발생 후 1개월 이내에 조사대상·방법 등을 검토하여 조사 (규칙 제657조제2항)<br>· 질환자 발생·업무상 질병 인정, 부담작업에 해당하는 새 작업·설비 도입 또는 작업환경 변경. 질환 관련 사유에는 최근 1년 이내 조사·개선조치 예외가 있습니다. 이 앱은 사유 발생일을 저장하지 않아 기한을 계산하지 않습니다.</div></div>
 <div class="card" style="background:#FFF8EE;border-color:#EBC48C"><h3>증상설문조사는 따로 하세요</h3>
  <div class="help">유해요인조사는 근로자 면담, 증상설문조사, 인간공학적 조사를 모두 해야 합니다 (규칙 제658조).
  이 프로그램은 인간공학적 조사와 면담 기록을 돕습니다. 증상설문조사는 별도로 하고 결과를 함께 보관하세요.</div></div>
</div>''', task=False),
       rows=[
           (1, "조사 구분", "라디오", "SurveyCreate.survey_type_cd (REGULAR · OCCASIONAL · INITIAL)", "필수"),
           (2, "수시조사 사유", "체크 (여러 개)", "SurveyCreate.occasional_reasons", "수시조사일 때만 켜짐. 하나 이상 고르지 않으면 E-INPUT-002 (BR-19)"),
           (3, "조사일", "날짜", "SurveyCreate.survey_date", "필수. YYYY-MM-DD"),
           (4, "조사자", "글자", "SurveyCreate.investigator_name", "필수. 이 조사의 수정 이력에서 '누가'로 쓴다 (F01-01 규칙 3)"),
           (5, "부서 · 작업공정명 · 작업명", "글자 3칸", "SurveyCreate.dept_name, SurveyCreate.process_name, SurveyCreate.work_name",
            "필수. 작업공정명은 엑셀 파일 이름에 들어간다"),
           (6, "저장하고 작업 등록", "버튼 (주)", "새 조사: create_survey(data) → S03. 있는 조사: 칸마다 자동 저장 update_survey(survey_id, data, actor)",
            "빈 필수 칸은 칸 아래 \"입력해 주세요\" (E-INPUT-002)"),
           (7, "조사 구분 안내", "안내", "고정 문구", "BR-19. 수시조사는 사유 발생 후 1개월 이내에 조사대상·방법 등을 검토해 조사한다는 안내와 질환 관련 예외를 표시한다. 사유 발생일을 저장하지 않아 기한은 계산하지 않는다. 아래 카드는 증상설문조사 별도 안내 (BR-18)"),
       ],
       states=["확정된 조사를 고치면 조사가 '작성 중'으로 돌아가고 위 띠에 알린다 (API 2.1절 ⑩)"])

# ---------------------------------------------------------------- S03 단위작업과 작업 정보 (기본·자세)
def _s03_left(marks=True):
    m = n if marks else (lambda k: '')
    return f'''
<div class="col" style="width:250px;flex:none">
 <div class="card">{m(1)}<h3>단위작업</h3>
  <div class="col" style="gap:6px">
   <div style="background:#E6EBF0;border-radius:6px;padding:7px 9px"><b>상자 들어 옮기기</b><br><span class="help">2명 · 상시 · <span style="color:#C62828">입력 필요 1</span></span></div>
   <div style="padding:7px 9px"><b>선반 정리</b><br><span class="help">1명 · 상시 · 입력 필요 0</span></div>
   <div style="padding:7px 9px"><b>수레 밀기</b><br><span class="help">1명 · 단기간작업 → 11개 호 비해당</span></div>
  </div>
  <div style="margin-top:8px"><span class="btn s">{m(2)}+ 단위작업 추가</span></div></div>
 <div class="card">{m(3)}<h3>면담 참여자</h3>
  <div class="help">근로자 대표 · 김OO <span style="float:right">×</span><br>해당 작업 근로자 · 근로자 A <span style="float:right">×</span></div>
  <div style="margin-top:6px"><span class="btn s">+ 참여자</span></div></div>
</div>'''


def _s03_head(active):
    tabs = ["기본·자세 (3·4·5호)", "키보드·반복 (1·2호)", "손 (6·7호)", "들기 (8·9·10호)", "충격 (11호)"]
    dots = {"키보드·반복 (1·2호)": True}
    t = "".join(f'<span class="{"on" if x == active else ""}">{x}{"<i class=dot></i>" if dots.get(x) else ""}</span>' for x in tabs)
    return t


screen(id="S03", name="단위작업과 작업 정보", tab="작업", fids=["F02-01", "F02-02", "F02-03", "F05-04"],
       purpose="단위작업을 등록하고, 판정에 필요한 값을 넣는다. 값을 넣으면 자동 저장되고 그 값을 쓰는 호가 바로 다시 판정된다.",
       entry="S02 '저장하고 작업 등록', S01 '열기', S07 '입력하기', 탭 '작업'", exit="S04 (사진 올리기)",
       html=frame("작업", _s03_left() + f'''
<div class="col" style="flex:1">
 <div class="row"><h2>상자 들어 옮기기</h2><span class="note">작업 인원 2명 · 상시 (단기간작업도 간헐적인 작업도 아님)</span>
  <span class="btn s" style="margin-left:auto">{n(4)}수정</span><span class="btn s">삭제</span></div>
 <div class="card" style="flex:1">
  <div class="subtabs">{n(5)}{_s03_head("기본·자세 (3·4·5호)")}</div>
  <div class="row" style="align-items:flex-start;gap:16px">
   <div class="col" style="flex:1;gap:12px">
    <div class="fld">{n(6)}<label>하루 작업시간 *</label><div class="in">6<span class="unit">시간 (0~24)</span></div>
     <span class="help">잔업을 포함한 1일 총 작업시간 (해설 1호 주1). 3·4·5호 하루 노출 = 사진 표본의 비율 × 이 값</span></div>
    <div class="fld">{n(7)}<label>4호 전제: 지지되지 않은 상태이거나 임의로 자세를 바꿀 수 없는 조건인가요?</label>
     <div class="seg" style="width:max-content"><span class="on">예</span><span>아니오</span></div>
     <span class="help">지지대 없이 버티거나, 작업하려면 모든 근로자가 그 자세를 취할 수밖에 없으면 '예' (해설 4호 주1·2)</span></div>
    <div class="row" style="gap:12px;align-items:flex-start">
     <div class="fld" style="flex:1">{n(8)}<label>목 비틀림 시간</label><div class="in">0.5<span class="unit">시간/일</span></div><span class="help">어깨를 고정하고 좌우 5° 이상 (해설 4호 주4)</span></div>
     <div class="fld" style="flex:1"><label>허리 비틀림 시간</label><div class="in err">7<span class="unit">시간/일</span></div><span class="err">하루 작업시간(6시간)보다 클 수 없습니다 (E-INPUT-001)</span></div></div>
   </div>
   <div class="col" style="width:330px;flex:none;gap:10px">
    <div class="card" style="background:#F7F9FA">{n(9)}<h3>사진에서 잰 값 (읽기 전용)</h3>
     <table class="tbl"><tr><th>자세</th><th>비율</th><th>하루 노출</th></tr>
      <tr><td>4호 허리 굽힘 20°↑</td><td>35%</td><td><b style="color:var(--risk)">2.10시간</b></td></tr>
      <tr><td>4호 목 굽힘 20°↑</td><td>12%</td><td>0.72시간</td></tr>
      <tr><td>3호 (합산)</td><td>30%</td><td>1.80시간</td></tr>
      <tr><td>5호 쪼그림</td><td>5%</td><td>0.30시간</td></tr></table></div>
    <div class="card">{n(10)}<h3>이 작업의 판정</h3>
     <div class="row" style="gap:6px;flex-wrap:wrap"><span class="badge b-app">해당 2</span><span class="badge b-rev">사람 확인 1</span><span class="badge b-in">입력 필요 1</span><span class="badge b-na">비해당 7</span></div>
     <div class="help" style="margin-top:6px">누르면 판정 탭(S07)으로</div></div>
   </div>
  </div>
 </div>
 <div class="row" style="justify-content:flex-end"><span class="btn p">{n(11)}사진 올리기 →</span></div>
</div>
<div class="toast" style="bottom:54px">{n(12)}저장됨 · 하루 작업시간 5 → 6 · <b>4호 비해당 → 해당 (초안)</b> · 경고 1개 새로 뜸</div>''',
                  task=False, foot_right="자동 저장됨 · 14:05"),
       rows=[
           (1, "단위작업 목록", "목록", "get_survey(survey_id) → SurveyDetail.unit_tasks (UnitTask.task_name, UnitTask.worker_cnt, UnitTask.period_type_cd). "
               "작업마다 '입력 필요' 수는 get_task_result(unit_task_id) → TaskResult.judgments", "고르면 오른쪽이 그 작업으로 바뀐다"),
           (2, "+ 단위작업 추가", "버튼", "D05 → create_unit_task(survey_id, data)", "F02-01"),
           (3, "면담 참여자", "목록", "SurveyDetail.participants (Participant.participant_type_cd, Participant.display_name). "
               "'+ 참여자' → D06 → add_participant(...), × → remove_participant(participant_id)",
            "실명 대신 '근로자 A'처럼 적어도 된다. 참여자 이름은 GPT에 보내지 않는다 (F02-03, BR-21)"),
           (4, "수정 · 삭제", "버튼", "D05 → update_unit_task(unit_task_id, data, actor) · D04 → delete_unit_task(unit_task_id, actor)",
            "작업 기간 구분을 바꾸면 11개 호를 다시 판정한다 (BR-02). 단위작업을 지워도 수정 이력은 남는다"),
           (5, "입력 묶음 탭", "탭 5개", "get_task_inputs(unit_task_id) → TaskInputBundle.inputs, TaskInputBundle.repetitions, TaskInputBundle.lift_positions. "
               "키보드·반복 탭의 2호 부위별 표는 save_repetition_inputs(unit_task_id, items, actor)",
            "판정에 필요한 값이 빈 탭에는 빨간 점. 탭 구성은 기능정의서 F02-02 표의 '쓰는 곳'을 따른다"),
           (6, "하루 작업시간", "숫자 (시간)", "TaskInputs.daily_work_h → save_task_inputs(unit_task_id, inputs, actor)",
            "0~24. 비우면 3·4·5호가 '입력 필요' (AC-05). 25를 넣으면 저장하지 않고 칸 아래 E-INPUT-001"),
           (7, "4호 전제", "예 / 아니오", "TaskInputs.unsupported_posture_yn", "비우면 4호는 '입력 필요'. '아니오'면 노출이 길어도 4호 비해당 (AC-23, BR-09)"),
           (8, "목 · 허리 비틀림 시간", "숫자 2칸", "TaskInputs.neck_twist_h, TaskInputs.waist_twist_h",
            "사진 한 장으로는 못 재서 조사자가 넣는다. 하루 작업시간보다 크면 저장하지 않는다 (E-INPUT-001, ERD 시험 M22)"),
           (9, "사진에서 잰 값", "표 (읽기 전용)", "get_task_result(unit_task_id) → TaskResult.shares (PostureShare.share_ratio, PostureShare.exposure_h)",
            "사진 분석 전에는 '사진을 분석하면 채워집니다'. 비율은 사진 표본의 비율이다. 시간은 소수 둘째 자리 (F04-05 규칙 5)"),
           (10, "이 작업의 판정", "상태 배지", "TaskResult.judgments (Judgment.computed_status_cd를 상태별로 셈)", "누르면 S07"),
           (11, "사진 올리기", "버튼 (주)", "S04로 이동", "—"),
           (12, "다시 계산 알림", "알림 (5초)", "save_* 함수가 돌려준 RecalcResult.changes (JudgmentChange.before → JudgmentChange.after), "
               "RecalcResult.warnings_raised, RecalcResult.warnings_cleared",
            "확정이 풀리면 노란 알림 \"4호 확정이 풀렸습니다 (수정 이력에 남음)\" (JudgmentChange.unconfirmed, API 2.2절)"),
       ],
       states=["단위작업이 없으면 오른쪽에 \"단위작업을 먼저 추가하세요\"와 '+ 단위작업 추가'",
               "작업 기간 구분이 단기간·간헐이면 입력 칸 위에 띠: \"단기간작업이라 11개 호를 모두 비해당으로 판정합니다 (BR-02). 사진 분석과 REBA는 그대로 보여 줍니다.\"",
               "저장은 칸에서 벗어나거나 Enter를 누를 때 한다 (자동 저장, F01-02 규칙 1). 범위 밖 값은 저장하지 않고 이전 값을 지킨다"])

# ---------------------------------------------------------------- S03-2 들기 탭
screen(id="S03-2", name="단위작업과 작업 정보 · 들기 탭", tab="작업", fids=["F02-02"],
       purpose="8·9·10호에 필요한 무게와 횟수를 넣는다. 9호는 손의 위치별로 따로 넣는다.",
       entry="S03의 '들기 (8·9·10호)' 탭", exit="S03의 다른 탭",
       html=frame("작업", _s03_left(False) + f'''
<div class="col" style="flex:1">
 <div class="row"><h2>상자 들어 옮기기</h2><span class="note">작업 인원 2명 · 상시</span></div>
 <div class="card" style="flex:1">
  <div class="subtabs">{_s03_head("들기 (8·9·10호)")}</div>
  <div class="row" style="align-items:flex-start;gap:16px">
   <div class="col" style="flex:1;gap:14px">
    <div class="card r" style="background:#fff">{n(1)}<h3>8호 · 25kg 이상 들기 (하루 10회 이상)</h3>
     <div class="row" style="gap:10px"><div class="fld" style="flex:1"><label>드는 물체 무게</label><div class="in">15<span class="unit">kg</span></div></div>
      <div class="fld" style="flex:1"><label>함께 드는 인원</label><div class="in">1<span class="unit">명</span></div></div>
      <div class="fld" style="flex:1"><label>하루 드는 횟수</label><div class="in">300<span class="unit">회</span></div></div></div></div>
    <div class="card r" style="background:#fff">{n(2)}<h3>9호 · 불편한 위치에서 10kg 이상 들기 (하루 25회 이상)</h3>
     <table class="tbl"><tr><th>손의 위치</th><th>하루 횟수</th><th>무게</th></tr>
      <tr><td>무릎 아래</td><td><div class="in">300<span class="unit">회</span></div></td><td><div class="in">15<span class="unit">kg</span></div></td></tr>
      <tr><td>어깨 위</td><td><div class="in empty">비어 있음</div></td><td><div class="in empty">—</div></td></tr>
      <tr><td>팔을 뻗은 상태</td><td><div class="in">20<span class="unit">회</span></div></td><td><div class="in">15<span class="unit">kg</span></div></td></tr></table></div>
    <div class="card r" style="background:#fff">{n(3)}<h3>10호 · 자주 드는 작업 (4.5kg 이상, 분당 2회 이상, 하루 총 2시간 이상)</h3>
     <div class="row" style="gap:10px"><div class="fld" style="flex:1"><label>무게</label><div class="in">15<span class="unit">kg</span></div></div>
      <div class="fld" style="flex:1"><label>분당 횟수</label><div class="in">0.8<span class="unit">회/분</span></div></div>
      <div class="fld" style="flex:1"><label>그 작업 시간</label><div class="in">6<span class="unit">시간/일</span></div></div></div></div>
   </div>
   <div class="col" style="width:330px;flex:none;gap:10px">
    <div class="card" style="background:#F7F9FA">{n(4)}<h3>해설 (고용노동부)</h3>
     <div class="help">· 8호는 중력에 반해 드는 작업만. 밀기·당기기 제외<br>· 2명 이상이 함께 들면 특별한 사유가 없는 한 무게를 인원수로 나눔<br>
     · 9호의 위치는 물체를 잡는 손의 위치<br>· '팔을 뻗은 상태' = 팔을 들고 팔꿈치를 곧게 편 상태. 아래로 늘어뜨린 팔은 제외</div></div>
    <div class="card">{n(5)}<h3>이 탭의 판정 (초안)</h3>
     <div class="col" style="gap:6px;font-size:12.5px">
      <div><span class="badge b-na">8호 비해당</span> 15kg ÷ 1명 = 15kg &lt; 25kg</div>
      <div><span class="badge b-app">9호 해당</span> 무릎 아래 15kg · 하루 300회 ≥ 25회</div>
      <div><span class="badge b-na">10호 비해당</span> 분당 0.8회 &lt; 2회</div></div></div>
   </div>
  </div>
 </div>
</div>''', task=False),
       rows=[
           (1, "8호 입력", "숫자 3칸", "TaskInputs.lift_kg, TaskInputs.lift_people_cnt, TaskInputs.lift_cnt_per_day → save_task_inputs(unit_task_id, inputs, actor)",
            "1인 무게는 화면이 계산하지 않고 판정 근거(Judgment.basis_text)를 보여 준다 (BR-11, AC-22)"),
           (2, "9호 위치별 표", "표 (3행 × 2칸)", "LiftPositionInput.position_cd, LiftPositionInput.lift_cnt_per_day, LiftPositionInput.weight_kg "
               "→ save_lift_position_inputs(unit_task_id, items, actor)",
            "보낸 표로 통째로 바꾼다. 빈 행은 보내지 않는다. 위치별로 따로 판정 (OI-01 기본안, BR-12)"),
           (3, "10호 입력", "숫자 3칸", "TaskInputs.freq_lift_kg, TaskInputs.freq_lift_per_min, TaskInputs.freq_lift_h", "시간은 하루 작업시간 이하"),
           (4, "해설 도움말", "안내", "고정 문구", "BR-11, BR-12"),
           (5, "이 탭의 판정", "배지 + 근거", "TaskResult.judgments → Judgment.computed_status_cd, Judgment.basis_text", "저장할 때마다 다시 계산된 값으로 바뀐다 (F05-04)"),
       ],
       states=["다른 탭(키보드·반복, 손, 충격)도 같은 모양이다: 왼쪽에 입력 카드, 오른쪽에 해설과 그 탭의 판정"])

# ---------------------------------------------------------------- S04 사진 올리기
screen(id="S04", name="사진 올리기", tab="사진", fids=["F03-01", "F03-02", "F03-03", "F03-04"],
       purpose="작업 중에 찍은 사진 여러 장(표본)을 고르고, 촬영 동의를 확인한 뒤 분석을 시작한다.",
       entry="S03 '사진 올리기', 탭 '사진'", exit="S05 (분석 시작)",
       html=frame("사진", f'''
<div class="col" style="flex:1.35">
 <h2>사진 올리기 · 상자 들어 옮기기</h2>
 <div class="card" style="border:2px dashed #AEB9C4;background:#fff;height:130px;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:8px">{n(1)}
  <div style="font-size:30px;color:#8E9AA6">⇪</div><div>작업 사진을 여기에 끌어 놓거나 <span class="btn s">파일 고르기</span></div><div class="help">jpg · png · 여러 장을 한 번에</div></div>
 <div class="card">{n(2)}<h3>고른 사진</h3>
  <div class="row" style="gap:18px;font-size:12.5px"><b>상자옮기기_측면_22.jpg</b><span>1080×1920</span>
   <span class="badge b-na">회전 정보 90° → 바로 세워서 분석</span></div></div>
 <div class="card">{n(3)}<h3>이 단위작업의 사진 · 22장</h3>
  <table class="tbl"><tr><th>순번</th><th>파일</th><th>동의</th><th>결과</th><th></th></tr>
   <tr><td>1</td><td>상자옮기기_측면_01.jpg</td><td>10-23 13:58 확인</td><td><span class="badge b-ok">지금 결과에 쓴 사진</span></td><td><span class="lnk">빼기</span></td></tr>
   <tr><td>…</td><td>…</td><td>…</td><td>…</td><td></td></tr>
   <tr><td>22</td><td>상자옮기기_측면_22.jpg</td><td>아직</td><td><span class="badge b-rev">새 사진 · 다시 분석 필요</span></td><td><span class="lnk">빼기</span></td></tr></table></div>
</div>
<div class="col" style="flex:1">
 <div class="card">{n(4)}<h3>잘 찍은 사진</h3>
  <div class="col" style="gap:6px">✔ 한 사람만, 옆모습으로 찍기<br>✔ 전신이 보이고, 사람이 화면의 절반 이상이 되게 찍기<br>✔ 작업 중 여러 순간을 일정한 간격으로 찍기 (많을수록 비율이 정확)<br>✔ 카메라를 수평으로 두기 (각도의 기준이 화면 세로선)</div></div>
 <div class="card">{n(5)}<span class="chk"><i class="box on"></i><b>촬영 대상자에게 목적을 설명하고 동의를 받았습니다</b></span>
  <div class="help" style="margin-top:6px">확인한 시각을 남깁니다. 동의를 확인해야 분석을 시작할 수 있습니다.</div></div>
 <div class="card">{n(6)}<h3>관절 모델</h3><div class="help">MoveNet Lightning · 이 프로그램은 이 모델만 씁니다</div></div>
 <div class="row" style="justify-content:flex-end;margin-top:auto"><span class="btn p">{n(7)}분석 시작</span></div>
</div>''', task_n=None),
       rows=[
           (1, "사진 고르기", "끌어 놓기 + 버튼", "inspect_still(path) → StillInfo", "jpg·png. 여러 장을 한 번에 고를 수 있다. 열 수 없으면 선택을 취소하고 E-STILL-001 (EX-01)"),
           (2, "고른 사진 정보", "정보 줄", "StillInfo.file_name, StillInfo.width_px, StillInfo.height_px, StillInfo.rotation_deg, StillInfo.notices",
            "회전 정보(EXIF)가 있으면 바로 세워 분석한다는 표시 (F03-01 규칙 2). 원본은 복사하지 않는다"),
           (3, "이 단위작업의 사진", "표", "list_stills(unit_task_id) → StillInfo.still_no, StillInfo.file_name, StillInfo.consent_yn. "
               "'빼기' → detach_still(still_id, actor). 지금 결과에 쓴 사진 수는 TaskResult.still_cnt",
            "사진이 옮겨졌으면 '위치를 다시 고르기' (E-STILL-004). 사진이 5장(TP-12)보다 적으면 노란 배지 W-STILL-002 (EX-02). 뺀 사진은 목록에서 사라지고 이미 나온 결과는 그대로"),
           (4, "촬영 안내 4줄", "안내", "고정 문구", "F03-02, AC-08"),
           (5, "촬영 동의", "체크", "고른 사진을 붙일 때 attach_still(unit_task_id, path, consent, actor), 붙인 뒤에는 confirm_consent(still_id, actor)",
            "체크 전에는 '분석 시작'이 꺼져 있다 (AC-09, E-STILL-003). 확인 시각을 남긴다"),
           (6, "관절 모델 표시", "정보", "get_settings() → Settings.pose_model_id, list_models() → PoseModel.model_name, PoseModel.model_version",
            "MVP는 MoveNet Lightning 하나 (D-MODEL-01)"),
           (7, "분석 시작", "버튼 (주)", "start_analysis(unit_task_id, on_progress) → RunHandle → S05",
            "다른 분석이 돌고 있으면 E-ANALYSIS-004. 사진이 없으면 버튼이 꺼져 있다 (E-INPUT-002)"),
       ],
       states=["사진을 아직 고르지 않았으면 2·3번 카드 대신 촬영 안내만 크게 보인다"])

# ---------------------------------------------------------------- S05 분석 진행
screen(id="S05", name="분석 진행", tab="사진", fids=["F03-04", "F04-01"],
       purpose="분석이 어디까지 됐는지 보여 주고, 취소할 수 있게 한다. 끝나면 결과 화면으로 넘어간다.",
       entry="S04 '분석 시작'", exit="S06 (끝남), S04 (취소·실패)",
       html=frame("사진", f'''
<div class="col" style="flex:1;align-items:center">
 <div class="card col" style="width:820px;gap:14px">
  <h2>분석 중 · 사진 21장</h2>
  <div class="r">{n(1)}<div style="height:22px;background:#D5DDE5;border-radius:11px;overflow:hidden"><div style="width:67%;height:100%;background:var(--orange)"></div></div>
   <div class="row" style="margin-top:6px;font-size:12.5px"><b>67%</b><span>관절 찾기</span><span>14 / 21 장</span><span style="margin-left:auto">남은 시간 약 2초</span></div></div>
  <div class="row" style="align-items:flex-start;gap:16px">
   <div class="r"><div style="background:#22303F;border-radius:10px;overflow:hidden">{figure(0.5, 840, 500)}</div>{n(2)}</div>
   <div class="col r" style="gap:8px;font-size:13px">{n(3)}
    <div>✔ 사진 열기</div><div><b style="color:var(--orange)">● 관절 찾기</b></div><div style="color:#9AA7B4">○ 각도 계산</div>
    <div style="color:#9AA7B4">○ 자세 판별 · 판정 · REBA</div><div style="color:#9AA7B4">○ 저장</div>
    <div class="help" style="margin-top:8px">원본 사진은 바꾸지 않습니다.</div></div>
  </div>
  <div class="row" style="justify-content:flex-end"><span class="btn">{n(4)}취소</span></div>
 </div>
</div>'''),
       rows=[
           (1, "진행 막대", "진행 표시", "on_progress로 받는 Progress.percent, Progress.stage, Progress.processed_stills, Progress.total_stills, Progress.eta_s",
            "콜백은 분석 스레드에서 온다. 화면은 자기 스레드로 넘겨 그린다 (API 4.3절). 사진 몇 십 장은 몇 초면 끝난다"),
           (2, "미리보기", "그림", "get_still_preview(run_id, still_id) — 지금 처리한 사진을 1초에 한 번", "원본 사진을 읽어 보여 줄 뿐 저장하지 않는다"),
           (3, "단계 목록", "목록", "Progress.stage (DECODE · KEYPOINT · ANGLE · JUDGE · SAVE)", "—"),
           (4, "취소", "버튼", "cancel_analysis(run_id) → I-ANALYSIS-005 → S04", "결과를 저장하지 않는다 (EX-07, AC-10)"),
       ],
       states=["실패하면 본문이 바뀐다: 마지막 Progress가 FAILED이고 Progress.error_code가 E-ANALYSIS-001이면 \"사람을 찾지 못했습니다…\" + '다시 찍는 방법', "
               "E-ANALYSIS-009면 \"분석 중 문제가 생겼습니다\" + '다시 시도' · '사진 바꾸기'",
               "끝나면 (DONE) 자동으로 S06으로 넘어간다"])


# 사진 목록 막대의 칸: 판별 가능 20장 중 7장이 허리 굽힘 (35%), 마지막 한 장은 판별 불가, 8번째가 대표 사진
def _still_strip():
    flagged_at = {1, 4, 7, 9, 12, 15, 18}   # 7번째 자리 = 대표 사진 (8번, 테두리)
    cells, k = [], 0
    for i in range(21):
        if i == 20:
            bg = "#8E9AA6"
        else:
            bg = "var(--orange)" if (k % 20) in flagged_at else "#D5DDE5"
            k += 1
        edge = "3px solid var(--navy)" if i == 7 else "1px solid #fff"
        cells.append(f'<div style="width:22px;height:34px;border-radius:4px;background:{bg};border:{edge};box-sizing:border-box;'
                     f'font-size:9px;color:#fff;text-align:center;line-height:34px">{i + 1}</div>')
    return "".join(cells)


# ---------------------------------------------------------------- S06 분석 결과와 경고
screen(id="S06", name="분석 결과와 경고", tab="결과", fids=["F04-03", "F04-04", "F04-05", "F04-06", "F04-07", "F05-02", "F05-03", "F05-04", "F06-02", "F06-03"],
       purpose="대표 사진, REBA 점수, 법 문구의 자세별 하루 노출, 경고를 한 화면에서 본다. REBA 사람 입력과 대표 사진을 고칠 수 있다.",
       entry="S05 (분석이 끝남), 탭 '결과'", exit="S07 (판정 보기), D03 (REBA 입력)",
       html=frame("결과", f'''
<div class="col" style="width:640px;flex:none">
 <div class="r"><div style="background:#22303F;border-radius:10px;overflow:hidden;height:330px;position:relative">{figure(0.74, 840, 500)}
  <span style="position:absolute;left:12px;top:10px;background:var(--risk);color:#fff;font-weight:700;border-radius:7px;padding:3px 10px">REBA 9</span>
  <span style="position:absolute;right:12px;top:12px;color:#C9D3DC">대표 사진 · 8번 (REBA 가장 높음)</span></div>{n(1)}</div>
 <div class="card r" style="padding:10px 12px">{n(2)}
  <div class="row" style="gap:3px;flex-wrap:wrap">{_still_strip()}</div>
  <div class="row" style="margin-top:6px;font-size:12px"><span><b style="color:var(--orange)">■</b> 허리 20° 이상 굽힘 (7장 / 20장 = 35%)</span><span><b style="color:#8E9AA6">■</b> 판별 불가 (1장)</span><span>┃ 대표 사진</span>
   <span style="margin-left:auto"><span class="badge b-na">자세 바꾸기: 허리 굽힘 ▾</span></span></div></div>
 <div class="card r row" style="padding:8px 12px">{n(3)}<span class="help">사진 고르기</span>
  <span class="btn s">◀</span><span class="help">8 / 21</span><span class="btn s">▶</span><span class="btn s" style="margin-left:auto">이 사진을 대표 사진으로</span></div>
 <div class="note">{n2(4)}MoveNet Lightning · 사진 21장 (판별 가능 20장) · 판별 불가 5% · 각도 기준: 고용노동부 해설 (S09)</div>
</div>
<div class="col" style="flex:1">
 <div class="card">{n(5)}<div class="row"><h3 style="margin:0">REBA</h3><span class="badge b-rev">임시 점수 · 손목 입력 전</span>
   <span class="btn s" style="margin-left:auto">{n(6)}REBA 입력</span></div>
  <div class="row" style="align-items:baseline;gap:10px;margin-top:4px"><b style="font-size:30px;color:var(--risk)">9</b><b style="color:var(--risk)">높음</b>
   <span class="help">표 C 8 + 활동 1</span></div>
  <div class="help">목 2 · 몸통 4 · 다리 2 → 표 A 6 + 하중 2 = 점수 A 8 │ 위팔 3 · 아래팔 1 · 손목 <span class="badge b-rev">사람 확인</span> → 표 B 3 + 손잡이 0 = 점수 B 3</div></div>
 <div class="card">{n(7)}<h3>법 기준 자세의 하루 노출 (하루 작업시간 6시간)</h3>
  <table class="tbl"><tr><th>호 · 자세</th><th>비율 (사진)</th><th>하루 노출</th><th>기준</th></tr>
   <tr><td>4호 허리 20° 이상 굽힘</td><td>35% (7/20장)</td><td><b style="color:var(--risk)">2.10시간</b></td><td>2시간 · 해설 4호 주3</td></tr>
   <tr><td>3호 팔 (a~d 합산)</td><td>30% (6/20장)</td><td>1.80시간 <span class="badge b-rev">사람 확인</span></td><td>2시간 · 해설 3호 주1</td></tr>
   <tr><td>5호 쪼그림</td><td>5% (1/20장)</td><td>0.30시간</td><td>2시간 · 해설 5호 주1</td></tr></table></div>
 <div class="card" style="background:#FFF4EB;border:2px solid var(--orange)">{n(8)}<b style="color:var(--risk)">경고</b>
  <div style="font-weight:700;font-size:14px;margin:4px 0">부담작업 4호 기준(하루 총 2시간)을 넘습니다.</div>
  <div class="help">허리 굽힘 35% × 하루 6시간 = 2.10시간</div>
  <div class="row r" style="margin-top:6px;gap:8px">{n(9)}<span class="badge b-ai">AI 작성</span><span style="font-size:12.5px">상자를 허리 높이 선반에 두면 굽힘을 줄일 수 있어요.</span><span class="lnk" style="margin-left:auto">고치기</span></div>
  <div style="margin-top:8px;font-size:12.5px"><span class="badge b-app">9호</span> 하루 25회 이상 10kg 이상을 불편한 위치에서 듦 <span class="lnk">조언 받기</span><br>
   <span class="badge b-rev">확인 필요</span> 3호: 각도를 ±5° 바꾸면 1.50~2.28시간 (기준 2시간 근처)</div></div>
 <div class="row" style="justify-content:flex-end;margin-top:auto"><span class="btn p">{n(10)}판정 보기 →</span></div>
</div>'''),
       rows=[
           (1, "대표 사진", "그림", "get_task_result(unit_task_id) → TaskResult.key_still_jpeg, TaskResult.key_still_id, RebaScore.reba_score",
            "대표 사진 JPEG 한 장. 기본은 REBA가 가장 높은 사진 (F04-07 규칙 1)"),
           (2, "사진 목록 막대", "칸 목록", "get_still_results(unit_task_id) → StillResult.still_no, StillResult.valid_yn, StillResult.flagged_items, StillResult.reba_score, StillResult.is_key_yn",
            "사진 한 장이 한 칸. 자세를 고르면 그 자세로 판별된 사진을 칠한다. 판별 불가는 회색, 대표 사진은 굵은 테두리. 각도 기준을 바꾸면 다시 계산된다"),
           (3, "사진 고르기", "◀ ▶ + 버튼", "get_still_preview(run_id, still_id)로 미리 보고, '이 사진을 대표 사진으로' → set_key_still(unit_task_id, still_id, actor)",
            "바꾸면 REBA를 다시 계산하고 수정 이력에 남긴다 (AC-20)"),
           (4, "분석 정보", "정보 줄", "RunHandle.model_id → PoseModel.model_name, TaskResult.still_cnt, TaskResult.valid_still_cnt, TaskResult.invalid_ratio, TaskResult.notices",
            "판별 불가 비율이 20%(TP-03)를 넘으면 노란 표시. 판별 가능한 사진이 5장(TP-12)보다 적으면 W-STILL-002를 보이고 자세 비율로 정하는 호는 '사람 확인'. 다리 잘림은 W-ANALYSIS-003"),
           (5, "REBA 카드", "점수 + 단계", "TaskResult.reba → RebaScore.neck_score, RebaScore.trunk_score, RebaScore.legs_score, RebaScore.table_a_score, "
               "RebaScore.load_score, RebaScore.upper_arm_score, RebaScore.lower_arm_score, RebaScore.wrist_score, RebaScore.table_b_score, "
               "RebaScore.coupling_score, RebaScore.table_c_score, RebaScore.activity_score, RebaScore.reba_score, RebaScore.risk_level_cd, "
               "RebaScore.provisional_yn, RebaScore.needs_review_items",
            "사람 입력이 빈 칸은 '사람 확인'이고 점수는 '임시' (F04-06 규칙 5, AC-19). REBA는 판정과 경고에 쓰지 않는다 (BR-15)"),
           (6, "REBA 입력", "버튼", "D03", "—"),
           (7, "하루 노출 표", "표", "TaskResult.shares → PostureShare.item_cd, PostureShare.share_ratio, PostureShare.exposure_h, "
               "PostureShare.threshold_value, PostureShare.threshold_source_cd",
            "비율은 사진 표본의 비율이라 '해당 사진 수 / 판별 가능 사진 수'를 함께 보인다. 각도 출처를 함께 보인다 (해설 / 조사자 변경). 확신도 때문에 '사람 확인'이면 노란 배지 (F05-02)"),
           (8, "경고", "강조 상자", "TaskResult.warnings → WarningItem.criterion_no, WarningItem.message_text, WarningItem.basis_text",
            "문구: \"부담작업 {N}호 기준({기준 요약})을 넘습니다.\" (F05-03). '사람 확인'인 호는 경고 대신 '확인 필요'. 인터넷이 없어도 뜬다 (AC-25)"),
           (9, "AI 조언", "문장 + 표시", "WarningItem.ai_text, WarningItem.ai_result_cd. '조언 받기' → request_warning_advice(warning_id) → AiTextResult.text, AiTextResult.is_ai. "
               "'고치기' → edit_ai_text(ai_text_id, text, actor)",
            "GPT 문장에는 'AI 작성'. GPT를 쓸 수 없으면 기본 문구만 보이고 표시가 없다 (F06-03, W-GPT-001)"),
           (10, "판정 보기", "버튼 (주)", "S07로 이동", "—"),
       ],
       states=["분석 결과가 없으면 \"사진을 분석하면 결과가 나옵니다\"와 'S04로'",
               "분석 뒤 각도 기준이나 입력값이 바뀌면 화면이 저장된 각도로 다시 계산된 값으로 바뀐다 (사진을 다시 분석하지 않음, F05-04)",
               "분석 뒤 사진을 더하거나 뺐으면 위에 띠: \"사진이 바뀌었습니다. 다시 분석하면 반영됩니다\" (이미 나온 결과는 그대로 보임)"])

# ---------------------------------------------------------------- S07 부담작업 판정
_rows7 = [
    ("1호", "키보드·마우스 집중 입력", '<span class="badge b-in">입력 필요</span>', "키보드·마우스 작업 시간을 넣어 주세요", '<span class="btn s dis">확정</span> <span class="lnk">입력하기</span>'),
    ("2호", "같은 동작 반복", '<span class="badge b-ok">비해당 · 확정</span>', "부위별 반복 시간 중 가장 긴 것 1.5시간 &lt; 2시간", '<span class="help">홍길동 14:02</span> <span class="lnk">풀기</span>'),
    ("3호", "팔을 들거나 뒤로 한 자세", '<span class="badge b-rev">사람 확인</span>', "30% × 6시간 = 1.80시간 · ±5°면 1.50~2.28시간", '<span class="seg" style="display:inline-flex;font-size:11.5px"><span>해당</span><span>비해당</span></span> <span class="btn s">확정…</span>'),
    ("4호", "목·허리 굽힘·비틀림", '<span class="badge b-app">해당 (초안)</span>', "허리 20° 이상 굽힘 35% × 6시간 = 2.10시간 ≥ 2시간 · 해설 4호 주3", '<span class="btn s">확정</span>'),
    ("5호", "쪼그림·무릎 굽힘", '<span class="badge b-ok">비해당 · 확정</span>', "쪼그림 5% × 6시간 = 0.30시간", '<span class="help">홍길동 14:03</span> <span class="lnk">풀기</span>'),
    ("6호", "손가락 집기·쥐기", '<span class="badge b-na">비해당 (초안)</span>', "손가락 작업 0시간", '<span class="btn s">확정</span>'),
    ("7호", "한 손 들기·쥐기", '<span class="badge b-na">비해당 (초안)</span>', "한 손 작업 0시간", '<span class="btn s">확정</span>'),
    ("8호", "25kg 이상 들기", '<span class="badge b-na">비해당 (초안)</span>', "15kg ÷ 1명 = 15kg &lt; 25kg", '<span class="btn s">확정</span>'),
    ("9호", "불편한 위치에서 10kg 들기", '<span class="badge b-app">해당 (초안)</span>', "무릎 아래 15kg · 하루 300회 ≥ 25회", '<span class="btn s">확정</span>'),
    ("10호", "자주 드는 작업", '<span class="badge b-na">비해당 (초안)</span>', "분당 0.8회 &lt; 2회", '<span class="btn s">확정</span>'),
    ("11호", "손·무릎 충격", '<span class="badge b-na">비해당 (초안)</span>', "충격 작업 0시간", '<span class="btn s">확정</span>'),
]
_t7 = "".join(f'<tr><td><b>{a}</b></td><td>{b}</td><td>{c}</td><td style="font-size:12px">{d}</td><td style="white-space:nowrap">{e}</td></tr>' for a, b, c, d, e in _rows7)
screen(id="S07", name="부담작업 판정", tab="판정", fids=["F02-02", "F05-01", "F05-02", "F05-04", "F05-05", "F05-06"],
       purpose="단위작업의 11개 호 판정 초안과 근거를 보고, 조사자가 확정한다. 확정과 변경은 수정 이력에 남는다.",
       entry="S06 '판정 보기', 탭 '판정'", exit="S03 (입력하기), D01 (확정·풀기 사유), S08",
       html=frame("판정", f'''
<div class="col" style="flex:1">
 <div class="row"><h2>부담작업 판정 · 상자 들어 옮기기</h2><span class="note">확정 전에는 모든 결과가 초안입니다</span></div>
 <div class="card" style="padding:0">{n(1)}
  <table class="tbl"><tr><th>호</th><th>기준 (고시 제3조)</th><th>판정</th><th>근거와 출처</th><th>확정</th></tr>{_t7}</table>
  <i class="n" style="left:auto;right:150px;top:120px">2</i><i class="n" style="left:auto;right:230px;top:162px">3</i>
  <i class="n" style="left:auto;right:96px;top:40px">4</i><i class="n" style="left:auto;right:96px;top:80px">5</i></div>
 <div class="row"><span class="btn">{n(6)}초안대로 모두 확정</span><span class="help">'사람 확인'과 '입력 필요'는 빼고 확정합니다</span>
  <span class="r" style="margin-left:auto"><span class="btn dis">조사 전체 확정</span>{n(7)}</span></div>
</div>
<div class="col" style="width:330px;flex:none">
 <div class="card" style="flex:1">{n(8)}<h3>수정 이력 (이 단위작업)</h3>
  <div class="col" style="gap:8px;font-size:12px">
   <div><b>14:03 홍길동</b> · 판정 5호 확정 · 비해당</div>
   <div><b>14:02 홍길동</b> · 판정 2호 확정 · 비해당</div>
   <div><b>13:40 홍길동</b> · 각도 기준 허리 굽힘 20° → 20° 되돌림</div>
   <div class="help">이력은 지우거나 고칠 수 없습니다</div></div></div>
</div>'''),
       rows=[
           (1, "11개 호 판정표", "표", "get_task_result(unit_task_id) → TaskResult.judgments: Judgment.criterion_no, Judgment.short_name, Judgment.computed_status_cd, "
               "Judgment.basis_text, Judgment.source_text, Judgment.final_status_cd, Judgment.confirmed_by, Judgment.confirmed_at",
            "작업 기간 구분이 단기간·간헐이면 표 위에 띠 \"11개 호 모두 비해당 (단기간작업)\" (BR-02)"),
           (2, "'사람 확인' 행", "고르기 + 버튼", "해당·비해당을 고르고 '확정…' → D01 (사유 필수) → confirm_judgment(unit_task_id, criterion_no, final_status, reason, actor)",
            "사유 없이 확정되지 않는다 (AC-27, E-CONFIRM-002). 사람 확인 사유는 Judgment.review_reason_cd"),
           (3, "'해당 · 비해당 (초안)' 행", "버튼", "'확정' → confirm_judgment(unit_task_id, criterion_no, final_status, reason, actor). 초안과 같은 결과면 사유 없이",
            "초안과 다른 결과로 확정하려면 D01에서 사유 (기능정의서 3.2절 규칙 2)"),
           (4, "'입력 필요' 행", "버튼 꺼짐 + 링크", "'입력하기' → S03의 그 호 탭 (F02-02는 S03과 S07에서 입력)", "확정 버튼이 꺼져 있다 (AC-27, E-CONFIRM-001)"),
           (5, "확정된 행", "링크", "'풀기' → D01 → unconfirm_judgment(unit_task_id, criterion_no, reason, actor). 결과를 바꾸면 D01 → confirm_judgment (API 2.1절 ②)",
            "확정 결과를 고칠 때도 사유가 있어야 한다 (3.2절 규칙 4)"),
           (6, "초안대로 모두 확정", "버튼", "confirm_all(unit_task_id, actor) → ConfirmAllResult.confirmed, ConfirmAllResult.needs_decision, ConfirmAllResult.blocked",
            "'사람 확인'이 남아 있으면 먼저 알린다 (F05-05 규칙 5): \"3호는 사람 확인이라 따로 확정하세요\""),
           (7, "조사 전체 확정", "버튼", "confirm_survey(survey_id, actor)", "모든 단위작업의 11개 호가 확정돼야 켜진다 (E-CONFIRM-003, 기능정의서 3.3절)"),
           (8, "수정 이력", "목록", "list_edit_log(survey_id) → EditLogEntry.logged_at, EditLogEntry.actor_name, EditLogEntry.target_cd, EditLogEntry.action_cd, "
               "EditLogEntry.old_value, EditLogEntry.new_value, EditLogEntry.reason_text (EditLogEntry.unit_task_id로 이 작업만)",
            "추가만 된다. 지우거나 고칠 수 없다 (AC-28, F05-06)"),
       ],
       states=["판정이 하나도 없으면 (분석·입력 전) 11개 호가 모두 '입력 필요'로 보인다",
               "다른 화면에서 입력값이 바뀌어 확정이 풀리면 그 행이 초안으로 돌아오고 이력에 '확정 해제 (입력값 변경)'이 남는다 (API 2.2절)"])

# ---------------------------------------------------------------- S08 결과와 엑셀 내보내기
screen(id="S08", name="결과와 엑셀 내보내기", tab="내보내기", fids=["F06-01", "F06-02", "F06-03"],
       purpose="모든 단위작업의 결과를 모아 보고, 엑셀 보고서로 내보낸다. 확정되지 않은 칸은 '초안'으로 표시해서 내보낸다.",
       entry="S07, 탭 '내보내기'", exit="엑셀 파일 (폴더 열기)",
       html=frame("내보내기", f'''
<div class="col" style="flex:1.25">
 <h2>결과와 엑셀 내보내기</h2>
 <div class="card" style="padding:0">{n(1)}
  <table class="tbl"><tr><th>단위작업</th><th>REBA</th><th>해당 호 (초안 포함)</th><th>남은 초안</th></tr>
   <tr><td>상자 들어 옮기기</td><td><b style="color:var(--risk)">9 높음</b></td><td>4호 · 9호 <span class="badge b-rev">사람 확인 1</span></td><td>9</td></tr>
   <tr><td>선반 정리</td><td>6 보통</td><td>없음</td><td>11</td></tr>
   <tr><td>수레 밀기</td><td>5 보통</td><td>없음 (단기간작업)</td><td>11</td></tr></table></div>
 <div class="card">{n(2)}<div class="row"><h3 style="margin:0">보고서 요약 문장</h3><span class="badge b-ai">AI 작성</span><span class="lnk" style="margin-left:auto">고치기</span></div>
  <div style="font-size:12.5px;line-height:1.6;margin-top:6px">조사한 작업 3개 중 1개가 부담작업 기준을 넘었습니다. 상자 들어 옮기기는 허리를 굽히는 시간이 하루 2.1시간으로 4호 기준(2시간)을 넘고,
  무릎 아래에서 상자를 드는 횟수가 9호 기준을 넘습니다. 상자를 허리 높이에 두는 받침대를 쓰면 두 기준을 함께 낮출 수 있습니다.</div></div>
 <div class="card" style="background:#FFF8EE;border-color:#EBC48C">{n(3)}<h3>엑셀에도 들어가는 안내</h3>
  <div class="help">· 증상설문조사는 따로 해야 합니다 (규칙 제658조)<br>· 기록 보존: 새 조사가 끝날 때까지, 신상정보가 있으면 5년, 개선계획은 해당 설비가 있는 동안<br>· 부담작업 해당 여부 결정과 조사 결과의 책임은 사업주와 조사자에게 있습니다</div></div>
</div>
<div class="col" style="flex:1">
 <div class="card col" style="gap:10px">
  <div class="fld">{n(4)}<label>저장 위치</label><div class="in">D:\\보고서\\유해요인조사<span class="unit">바꾸기</span></div>
   <span class="help">파일 이름: 유해요인조사_2026-10-23_포장공정.xlsx (같은 이름이 있으면 _2)</span></div>
  <span class="chk r">{n(5)}<i class="box on"></i>DB 사본도 같은 폴더에 저장 (ergo_assist_backup_…db)</span>
  <div class="row" style="justify-content:flex-end"><span class="btn p">{n(6)}엑셀로 내보내기</span></div>
  <div class="help">확정되지 않은 칸 31개는 '초안'으로 표시해서 내보냅니다.</div></div>
 <div class="r"><div class="card" style="padding:0;overflow:hidden">
  <div style="background:#1E7145;color:#fff;padding:6px 10px;font-size:12px">유해요인조사_2026-10-23_포장공정.xlsx</div>
  <table class="tbl" style="font-size:11.5px"><tr><th>작업</th><th>REBA</th><th>위험</th><th>대표 사진</th></tr>
   <tr><td>상자 들어 옮기기</td><td>9</td><td>높음</td><td><span style="display:inline-block;width:46px;height:28px;background:#22303F;border-radius:3px"></span></td></tr>
   <tr><td>선반 정리</td><td>6</td><td>보통</td><td><span style="display:inline-block;width:46px;height:28px;background:#22303F;border-radius:3px"></span></td></tr></table>
  <div class="row" style="gap:0;font-size:11px;border-top:1px solid var(--line)"><span style="padding:5px 10px">요약</span><span style="padding:5px 10px;background:#fff;font-weight:700;border-bottom:2px solid #1E7145">작업별 결과</span><span style="padding:5px 10px">경고 기록</span><span style="padding:5px 10px">판정 초안</span></div></div>{n(7)}</div>
</div>''', task=False),
       rows=[
           (1, "작업별 결과 표", "표", "get_survey(survey_id) → SurveyDetail.unit_tasks, 작업마다 get_task_result(unit_task_id) → RebaScore.reba_score, "
               "RebaScore.risk_level_cd, Judgment.computed_status_cd, Judgment.confirmed_yn", "확정되지 않은 판정 수를 함께 보인다"),
           (2, "보고서 요약 문장", "문장 + 표시", "request_report_summary(survey_id) → AiTextResult.text, AiTextResult.is_ai, AiTextResult.result_cd. '고치기' → edit_ai_text(ai_text_id, text, actor)",
            "GPT를 쓸 수 없으면 기본 문구, 열린 경고가 없으면 \"법 기준(고시 제3조)을 넘는 작업이 없습니다.\" (NO_WARNING). 작업 이름은 보내지 않는다 (OI-05)"),
           (3, "엑셀에도 들어가는 안내", "안내", "고정 문구", "BR-18, NFR-014, NFR-013"),
           (4, "저장 위치", "폴더 고르기", "get_settings() → Settings.last_export_dir", "파일 이름 규칙은 API 7.1절"),
           (5, "DB 사본도 저장", "체크", "export_excel의 with_db_backup", "기본 켜짐. SQLite 온라인 백업 (ERD 6.6절)"),
           (6, "엑셀로 내보내기", "버튼 (주)", "export_excel(survey_id, path, actor, with_db_backup) → ExportResult.file_path, ExportResult.draft_cell_cnt, ExportResult.backup_path",
            "파일이 열려 있으면 저장하지 않고 다른 이름으로 저장하게 한다 (E-EXPORT-001, EX-12). 끝나면 '폴더 열기'"),
           (7, "엑셀 미리보기", "그림", "고정 그림 (시트 4개: 요약 · 작업별 결과 · 경고 기록 · 판정 초안)", "실제 내용은 API 7.1절 (AC-29)"),
       ],
       states=["인터넷이 없으면 요약 문장은 기본 문구로 바뀌고, 엑셀 내보내기는 그대로 된다 (AC-32)"])

# ---------------------------------------------------------------- S09 설정
screen(id="S09", name="설정", tab="설정", fids=["F07-01", "F07-02", "F07-03"],
       purpose="쓰는 관절 모델을 확인하고, GPT 사용을 정하고, 열린 조사의 각도 기준(고용노동부 해설)을 보고 사유와 함께 바꾼다.",
       entry="탭 '설정' (언제든)", exit="D02 (각도 기준 변경)",
       html=frame("설정", f'''
<div class="col" style="flex:1">
 <h2>설정</h2>
 <div class="card">{n(1)}<h3>관절 모델</h3><div style="font-weight:700;font-size:14px">MoveNet Lightning · singlepose float16 v4 · 관절 17개</div>
  <div class="help" style="margin-top:4px">이 프로그램은 이 모델만 씁니다. 분석 결과마다 모델 이름과 버전을 남깁니다.</div></div>
 <div class="card">{n(2)}<h3>자세 각도 기준 · 이 조사 (2026-10-23 정기조사)</h3>
  <table class="tbl"><tr><th>기준</th><th>값</th><th>출처</th><th></th></tr>
   <tr><td>목 굽힘 (수직 기준)</td><td>20° 이상</td><td>고용노동부 해설 4호 주3</td><td><span class="lnk">{n(3)}변경</span></td></tr>
   <tr><td>허리 굽힘 (앞)</td><td><b>30° 이상</b></td><td><span class="badge b-rev">조사자 변경</span> 허리를 받치는 지지대가 있음</td><td><span class="lnk">변경</span><span class="lnk">기본값으로</span></td></tr>
   <tr><td>허리 젖힘 (뒤)</td><td>20° 이상</td><td>고용노동부 해설 4호 주3</td><td><span class="lnk">변경</span></td></tr>
   <tr><td>목 · 허리 비틀림</td><td>5° · 20° (판단 안내)</td><td>고용노동부 해설 4호 주4</td><td><span class="lnk">변경</span></td></tr>
   <tr><td>팔꿈치 들기 (위팔, 수직 기준)</td><td>45° 이상</td><td>고용노동부 해설 3호 주1</td><td><span class="lnk">변경</span></td></tr></table>
  <div class="help" style="margin-top:4px">'특별한 사정'이 있을 때만 사유와 함께 바꿉니다. 바꾼 값은 이 조사에만 적용되고 엑셀에 '조사자 변경'으로 나옵니다.</div></div>
</div>
<div class="col" style="width:440px;flex:none">
 <div class="card col" style="gap:10px"><h3 style="margin:0">GPT 문장</h3>
  <span class="chk r">{n(4)}<i class="box on"></i>경고 조언과 보고서 요약 문장 쓰기</span>
  <div class="fld">{n(5)}<label>모델</label><div class="in">(10/15 결정)<span class="unit">▾</span></div></div>
  <div class="fld">{n(6)}<label>API 키</label><div class="in">●●●●●●●●●●●● 저장됨<span class="unit">바꾸기 · 지우기</span></div>
   <span class="help">Windows 자격 증명 관리자에 저장합니다. DB·파일·엑셀에는 남기지 않습니다.</span></div>
  <div class="help">{n2(7)}보내는 값: 호 번호, 기준 문구, 시간·비율·점수 숫자만. 사진, 이미지, 이름은 보내지 않습니다.</div></div>
 <div class="note">{n2(8)}저장 위치: %LOCALAPPDATA%\\ergo-assist · 계약 0.3</div>
 <div class="row" style="justify-content:flex-end;margin-top:auto"><span class="btn p">{n(9)}저장</span></div>
</div>''', task=False),
       rows=[
           (1, "관절 모델", "정보 (고를 수 없음)", "list_models() → PoseModel.model_name, PoseModel.model_version, PoseModel.keypoint_cnt. 저장할 때 save_settings(pose_model_id, ...)에는 지금 값을 그대로 넘긴다",
            "MVP는 모델이 하나다 (D-MODEL-01). 모델을 더하면 이 칸이 고르기로 바뀐다. 분석 결과마다 모델 이름과 버전을 남긴다 (F07-01 규칙 4)"),
           (2, "각도 기준 표", "표", "get_thresholds(survey_id) → Threshold.threshold_cd, Threshold.value_deg, Threshold.source_label, Threshold.overridden_yn",
            "열린 조사가 없으면 기본값만 보이고 바꿀 수 없다. 쪼그려 앉기는 각도가 아니라서 표에 없다 (무릎이 발끝보다 앞, 해설 5호 주1)"),
           (3, "변경 · 기본값으로", "링크", "'변경' → D02 → set_threshold(...). '기본값으로' → reset_threshold(survey_id, threshold_cd, actor)",
            "사유 없이 바꿀 수 없다 (AC-34, E-THRESHOLD-001). 바꾸면 이 조사의 모든 단위작업을 다시 판정한다"),
           (4, "GPT 사용", "체크", "Settings.gpt_enabled", "끄면 기본 문구만 나온다 (AC-35, DISABLED)"),
           (5, "GPT 모델", "고르기", "Settings.gpt_model", "D-API-03 (10/15)"),
           (6, "API 키", "가린 칸", "set_gpt_api_key(key), delete_gpt_api_key(). 있는지만 Settings.has_gpt_key로 안다",
            "키 자체는 다시 보여 주지 않는다. 빈 키는 E-INPUT-002"),
           (7, "보내는 값 안내", "안내", "고정 문구 (API 6.2절)", "BR-21"),
           (8, "저장 위치", "정보", "고정 (ERD 6.1절)", "—"),
           (9, "저장", "버튼 (주)", "get_settings()로 열고 save_settings(pose_model_id, gpt_enabled, gpt_model)로 저장", "설정은 '저장'을 누를 때 저장한다 (입력 화면의 자동 저장과 다름)"),
       ],
       states=["GPT 키가 없으면 키 칸에 \"키 없음 · 기본 문구로 동작\" (FALLBACK_NO_KEY)"])

# ---------------------------------------------------------------- 대화상자
DIALOGS = []


def dlg(**kw):
    DIALOGS.append(kw)


dlg(id="D01", name="확정 · 확정 풀기 사유", w=900, h=560, fids=["F05-05"],
    purpose="'사람 확인'을 확정하거나, 초안과 다른 결과로 확정하거나, 확정을 풀거나, 확정 결과를 바꿀 때 사유를 받는다.",
    html=dialog("판정 확정 · 3호 팔을 들거나 뒤로 한 자세", f'''
<div class="row">{n2(1)}<span class="badge b-rev">사람 확인</span><span style="font-size:12.5px">30% × 6시간 = 1.80시간 · 각도 ±5°면 1.50~2.28시간 (기준 2시간 근처)</span></div>
<div class="fld">{n(2)}<label>확정할 결과 *</label><div class="row" style="gap:18px"><span class="chk"><i class="radio on"></i>해당</span><span class="chk"><i class="radio"></i>비해당</span></div></div>
<div class="fld">{n(3)}<label>사유 *</label><div class="in" style="min-height:70px;align-items:flex-start">사진에서 팔꿈치가 어깨 높이에 머무는 것을 직접 확인함. 선반 윗단 작업이 하루 대부분</div></div>
<div class="help">{n2(4)}확정자: 홍길동 (조사자) · 확정 시각과 사유가 수정 이력에 남습니다.</div>''',
                f'<span class="btn">취소</span><span class="btn p">{n(5)}확정</span>'),
    rows=[
        (1, "호와 초안", "정보", "Judgment.criterion_no, Judgment.short_name, Judgment.computed_status_cd, Judgment.basis_text", "—"),
        (2, "확정할 결과", "라디오", "FinalStatus (APPLICABLE · NOT_APPLICABLE)", "확정을 풀 때는 이 칸이 없다"),
        (3, "사유", "글자 (여러 줄)", "reason", "필수 조건: '사람 확인', 초안과 다른 결과, 확정 결과 바꾸기, 확정 풀기. 비면 E-CONFIRM-002"),
        (4, "확정자", "정보", "SurveyDetail.investigator_name (actor)", "—"),
        (5, "확정 · 풀기", "버튼 (주)", "confirm_judgment(unit_task_id, criterion_no, final_status, reason, actor) 또는 unconfirm_judgment(unit_task_id, criterion_no, reason, actor) → Judgment",
         "'입력 필요'는 이 창을 열 수 없다 (E-CONFIRM-001)"),
    ])

dlg(id="D02", name="각도 기준 변경", w=900, h=560, fids=["F07-02"],
    purpose="열린 조사의 각도 기준 하나를 사유와 함께 바꾼다. 바꾸면 그 조사의 모든 단위작업을 다시 판정한다.",
    html=dialog("각도 기준 변경 · 허리 굽힘 (앞)", f'''
<div class="row">{n2(1)}<span style="font-size:12.5px">지금 값 <b>20° 이상</b> · 고용노동부 해설 4호 주3 ("특별한 사정이 없는 한")</span></div>
<div class="fld" style="width:200px">{n(2)}<label>새 값 *</label><div class="in">30<span class="unit">°</span></div></div>
<div class="fld">{n(3)}<label>사유 * ('특별한 사정')</label><div class="in" style="min-height:60px;align-items:flex-start">허리를 받치는 지지대가 있음</div></div>
<div class="card r" style="background:#FFF8EE;border-color:#EBC48C">{n(4)}<div class="help">이 조사의 단위작업 3개를 저장된 각도로 다시 판정합니다. 확정된 4호가 있으면 결과가 같아도 확정이 풀립니다 (수정 이력에 남음). 엑셀에는 '조사자 변경 (사유)'로 나옵니다.</div></div>''',
                f'<span class="btn" style="margin-right:auto">{n(5)}기본값으로 되돌리기</span><span class="btn">취소</span><span class="btn p">{n(6)}바꾸기</span>'),
    rows=[
        (1, "지금 값과 출처", "정보", "Threshold.value_deg, Threshold.source_label", "—"),
        (2, "새 값", "숫자 (°)", "value_deg", "범위 밖이면 E-INPUT-001"),
        (3, "사유", "글자", "reason", "필수 (BR-06). 비면 E-THRESHOLD-001"),
        (4, "영향 안내", "안내", "API 2.2절의 규칙을 그대로 알린다", "—"),
        (5, "기본값으로 되돌리기", "버튼", "reset_threshold(survey_id, threshold_cd, actor)", "해설 값으로 돌아간다. 이력에 RESET"),
        (6, "바꾸기", "버튼 (주)", "set_threshold(survey_id, threshold_cd, value_deg, reason, actor) → RecalcResult 목록",
         "끝나면 \"단위작업 3개 다시 판정 · 4호 1개 바뀜 · 확정 1개 풀림\" 알림"),
    ])

dlg(id="D03", name="REBA 사람 입력", w=1000, h=700, fids=["F04-06"],
    purpose="사진으로 재기 어려운 REBA 항목을 조사자가 넣는다. 넣으면 REBA만 다시 계산한다 (판정에는 쓰지 않음).",
    html=dialog("REBA 사람 입력 · 상자 들어 옮기기", f'''
<div class="row" style="gap:14px;align-items:flex-start">
 <div class="col" style="flex:1;gap:10px">
  <div class="fld">{n(1)}<label>하중 · 충격</label><div class="row" style="gap:8px"><div class="in" style="width:120px">15<span class="unit">kg</span></div><span class="chk"><i class="box"></i>충격·급격한 힘</span></div></div>
  <div class="fld">{n(2)}<label>손잡이</label><div class="seg" style="width:max-content"><span class="on">좋음</span><span>보통</span><span>나쁨</span><span>받아들일 수 없음</span></div></div>
  <div class="fld">{n(3)}<label>손목</label><div class="row" style="gap:8px"><div class="seg"><span>15° 이하</span><span>15° 넘음</span></div><span class="badge b-rev">사람 확인</span><span class="chk"><i class="box"></i>꺾임·비틀림</span></div></div>
  <div class="fld">{n(4)}<label>비틀림 · 옆으로 굽힘</label><div class="row" style="gap:16px"><span class="chk"><i class="box"></i>목</span><span class="chk"><i class="box on"></i>몸통</span></div></div>
 </div>
 <div class="col" style="flex:1;gap:10px">
  <div class="fld">{n(5)}<label>다리 지지</label><div class="seg" style="width:max-content"><span class="on">양발</span><span>한 발 · 불안정</span></div></div>
  <div class="fld">{n(6)}<label>팔</label><div class="row" style="gap:14px"><span class="chk"><i class="box"></i>어깨 올림</span><span class="chk"><i class="box"></i>위팔 벌림 (정면 사진 필요)</span><span class="chk"><i class="box"></i>팔 받침·기댐</span></div></div>
  <div class="fld">{n(7)}<label>활동</label><div class="col" style="gap:4px"><span class="chk"><i class="box"></i>1분 넘게 정적 자세</span><span class="chk"><i class="box on"></i>분당 4회 넘는 작은 반복</span><span class="chk"><i class="box"></i>급격한 큰 자세 변화 · 불안정</span></div></div>
 </div>
</div>
<div class="help">비워 두면 그 칸은 '사람 확인'이고 점수는 '임시'로 계산합니다 (기능정의서 F04-06 규칙 5).</div>''',
                f'<span class="btn">취소</span><span class="btn p">{n(8)}저장</span>', w=860),
    rows=[
        (1, "하중 · 충격", "숫자 + 체크", "RebaInputs.load_kg, RebaInputs.shock_yn", "REBA 5단계 (kg 구간)"),
        (2, "손잡이", "4단", "RebaInputs.coupling_cd", "REBA 11단계"),
        (3, "손목", "2단 + 체크", "RebaInputs.wrist_flex_cd, RebaInputs.wrist_twist_yn", "MoveNet에는 손 점이 없어 조사자가 넣는다 (REBA 9단계)"),
        (4, "비틀림 · 옆 굽힘", "체크 2개", "RebaInputs.neck_twist_side_yn, RebaInputs.trunk_twist_side_yn", "REBA 1a · 2a"),
        (5, "다리 지지", "2단", "RebaInputs.legs_support_cd", "REBA 3단계"),
        (6, "팔", "체크 3개", "RebaInputs.shoulder_raised_yn, RebaInputs.arm_abducted_yn, RebaInputs.arm_supported_yn", "벌림은 측면 사진으로 못 잰다 (OI-07)"),
        (7, "활동", "체크 3개", "RebaInputs.act_static_yn, RebaInputs.act_repeat_yn, RebaInputs.act_rapid_yn", "REBA 13단계"),
        (8, "저장", "버튼 (주)", "열 때 get_reba_inputs(unit_task_id), 저장은 save_reba_inputs(unit_task_id, inputs, actor) → RecalcResult",
         "REBA만 다시 계산한다. 확정은 풀리지 않는다 (BR-15, API 2.2절)"),
    ])

dlg(id="D05", name="단위작업 추가 · 수정", w=900, h=560, fids=["F02-01"],
    purpose="단위작업을 등록하거나 이름·인원·작업 기간 구분을 고친다.",
    html=dialog("단위작업 추가", f'''
<div class="fld">{n(1)}<label>단위작업명 *</label><div class="in">수레 밀기</div></div>
<div class="fld">{n(2)}<label>작업 내용</label><div class="in empty">예: 완제품 상자를 수레로 창고까지 옮김</div></div>
<div class="fld" style="width:200px">{n(3)}<label>작업 인원 *</label><div class="in">1<span class="unit">명</span></div></div>
<div class="fld">{n(4)}<label>작업 기간 구분 *</label>
 <div class="col" style="gap:4px"><span class="chk"><i class="radio"></i>상시 (단기간작업도 간헐적인 작업도 아님)</span>
 <span class="chk"><i class="radio on"></i>단기간작업 (2개월 이내에 종료되는 1회성 작업) → 11개 호 모두 비해당</span>
 <span class="chk"><i class="radio"></i>간헐적인 작업 (연간 총 작업일수 60일 이하) → 11개 호 모두 비해당</span></div></div>''',
                f'<span class="btn">취소</span><span class="btn p">{n(5)}저장</span>'),
    rows=[
        (1, "단위작업명", "글자", "UnitTaskCreate.task_name", "필수 (E-INPUT-002). 한 조사 안에서 겹치면 E-INPUT-003"),
        (2, "작업 내용", "글자", "UnitTaskCreate.task_desc", "선택. GPT에 보내지 않는다 (OI-05)"),
        (3, "작업 인원", "정수", "UnitTaskCreate.worker_cnt", "1 이상 (E-INPUT-001)"),
        (4, "작업 기간 구분", "라디오", "UnitTaskCreate.period_type_cd (ONGOING · SHORT_TERM · INTERMITTENT)", "단기간·간헐이면 11개 호를 모두 비해당으로 판정 (BR-02, AC-04)"),
        (5, "저장", "버튼 (주)", "추가: create_unit_task(survey_id, data) · 수정: update_unit_task(unit_task_id, data, actor)", "새 단위작업은 11개 호 판정 행이 '입력 필요'로 생긴다"),
    ])

# 그림 없이 표만 두는 작은 대화상자
SMALL = [
    ("D04", "삭제 확인", "조사나 단위작업을 지우기 전에 한 번 더 묻는다.",
     [("문구 (조사)", "\"조사와 수정 이력이 모두 지워집니다. 기록 보존 기간(새 조사가 끝날 때까지, 신상정보가 있으면 5년)이 지났는지 확인하세요.\""),
      ("문구 (단위작업)", "\"단위작업과 사진 기록, 분석 결과, 판정이 지워집니다. 수정 이력은 남습니다.\""),
      ("동작", "'삭제' → delete_survey(survey_id, actor) 또는 delete_unit_task(unit_task_id, actor). 기본 단추는 '취소'")]),
    ("D06", "참여자 추가", "면담에 참여한 근로자를 기록한다 (F02-03).",
     [("구분", "Participant.participant_type_cd (근로자 대표 · 해당 작업 근로자)"),
      ("표시 이름", "Participant.display_name. 실명 대신 '근로자 A'처럼 적어도 된다. GPT에 보내지 않는다 (BR-21)"),
      ("동작", "'추가' → add_participant(survey_id, participant_type_cd, display_name). 빈 이름은 E-INPUT-002")]),
]

# 메시지가 어디에 어떻게 나오는지 (API 계약서 8절의 코드를 모두 다룬다)
MESSAGE_PLACE = {
    "E-INPUT-001": ("S02 · S03 · D02 · D05", "그 칸 아래 빨간 글씨. 값은 저장하지 않고 이전 값을 지킨다"),
    "E-INPUT-002": ("S02 · D05 · D06 · S09", "그 칸 아래 빨간 글씨"),
    "E-INPUT-003": ("D05", "단위작업명 칸 아래"),
    "E-NOTFOUND-001": ("모든 화면", "화면 위 띠 + 목록으로 돌아감"),
    "E-STILL-001": ("S04", "끌어 놓기 상자 아래. 선택을 취소"),
    "W-STILL-002": ("S04 · S06", "사진 목록 위와 분석 정보 줄의 노란 배지"),
    "E-STILL-003": ("S04", "'분석 시작'이 꺼져 있고, 누르면 동의 칸을 강조"),
    "E-STILL-004": ("S04 · S06", "사진 목록의 그 줄에 '위치를 다시 고르기'"),
    "E-ANALYSIS-001": ("S05", "본문이 실패 안내로 바뀜 + 다시 찍는 방법"),
    "W-ANALYSIS-003": ("S06", "분석 정보 줄의 노란 배지"),
    "E-ANALYSIS-004": ("S04", "'분석 시작' 옆 알림"),
    "I-ANALYSIS-005": ("S04", "화면 아래 알림 (5초)"),
    "E-ANALYSIS-009": ("S05", "본문이 실패 안내로 바뀜 + '다시 시도'"),
    "E-CONFIRM-001": ("S07", "확정 버튼이 꺼져 있음 + 행의 '입력하기'"),
    "E-CONFIRM-002": ("D01", "사유 칸 아래"),
    "E-CONFIRM-003": ("S07", "'조사 전체 확정'이 꺼져 있고, 남은 판정 수를 표시"),
    "E-THRESHOLD-001": ("D02", "사유 칸 아래"),
    "E-EXPORT-001": ("S08", "확인 대화상자: 닫고 다시 저장 · 다른 이름으로 저장"),
    "E-DB-001": ("S01", "화면 위 띠. 저장 위치를 알려 줌"),
    "E-DB-002": ("모든 화면", "화면 위 띠 \"저장하지 못했습니다\". 로그에 제약 이름 (앱 버그 신호)"),
    "W-GPT-001": ("S06 · S08", "따로 띄우지 않음. 'AI 작성' 표시 없이 기본 문구만 보임"),
}

OPEN_ITEMS = [
    ("UI-OI-01", "화면 도구 (D-API-01)가 정해지면 와이어프레임의 배치는 그대로 두고 모양만 도구에 맞춘다. Streamlit이면 탭이 위쪽 메뉴, PySide6면 창 위 탭", "10/14"),
    ("UI-OI-02", "기준 해상도. 발표 노트북 사양이 정해지면 바꿀 수 있음 (지금 1366×768, 최소 1280×720)", "10/16"),
    ("UI-OI-03", "분석할 사람을 고르는 화면 (OI-08). MoveNet 한 사람 모델은 사람 수를 세지 못해 지금은 촬영 안내와 관절 겹쳐 보기로 사람이 확인한다", "10/17"),
    ("UI-OI-04", "사진을 시간 간격으로 뽑는 영상 가져오기(영상 도입)와 분석 구간 지정 (OI-06). MVP 이후", "10/17"),
    ("UI-OI-05", "정면 사진을 따로 받을지 (OI-07). 받으면 S04에 사진마다 '촬영 방향' 칸 추가", "10/17"),
]
