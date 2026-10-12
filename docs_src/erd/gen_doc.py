import json, os, re, sqlite3, sys, tempfile
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parent))
import paths  # noqa: E402
SCHEMA = paths.SCHEMA_FILE.read_text(encoding="utf-8")
SEED = paths.SEED_FILE.read_text(encoding="utf-8")
TEST = json.loads((paths.WORK / "test_results.json").read_text(encoding="utf-8"))
TEMPLATE = (HERE / "erd_template.md").read_text(encoding="utf-8")
OUT = paths.DOCS / "ERD_데이터설계서.md"

# 테이블·컬럼 설명 (한글명 | 설명). 기능 ID는 기능정의서 기준
D = {
 "criterion": ("부담작업 기준", "고시 제3조 1~11호 (기준 정보)", {
   "criterion_no": "호 번호 (1~11)", "short_name": "짧은 이름", "legal_text": "고시 원문",
   "source_ref": "근거 조문", "note_ref": "해설 '주' 위치", "basis_type_cd": "판정 근거 종류: 자세 측정·입력·혼합"}),
 "threshold_default": ("각도 기준 기본값", "해설의 각도 값 (F07-02, BR-06)", {
   "threshold_cd": "각도 기준 코드", "criterion_no": "적용 호", "value_deg": "기준 각도 (°)",
   "measure_cd": "측정 방법: 자세 측정·조사자 판단", "source_ref": "출처 (해설 호·주)"}),
 "pose_model": ("관절 모델", "분석에 쓸 수 있는 관절 모델 (F07-01)", {
   "model_id": "모델 식별자", "model_name": "모델 이름", "model_version": "버전", "keypoint_cnt": "관절 점 개수"}),
 "survey": ("조사", "유해요인조사 한 건 (F01-01)", {
   "survey_id": "조사 식별자", "survey_type_cd": "조사 구분: 정기·수시·최초", "survey_date": "조사일",
   "investigator_name": "조사자 이름 (개인정보)", "dept_name": "부서", "process_name": "작업공정명", "work_name": "작업명",
   "status_cd": "조사 상태: 작성 중·확정 (3.3절)", "confirmed_at": "확정 시각", "created_at": "만든 시각", "updated_at": "고친 시각"}),
 "survey_reason": ("수시조사 사유", "수시조사의 사유 (여러 개, 1NF로 분리)", {
   "survey_id": "조사", "reason_cd": "사유 코드"}),
 "participant": ("참여 근로자", "면담에 참여한 근로자·근로자 대표 (F02-03)", {
   "participant_id": "참여자 식별자", "survey_id": "조사", "participant_type_cd": "구분: 근로자 대표·해당 작업 근로자",
   "display_name": "표시 이름 (개인정보, 실명 대신 '근로자 A' 가능)", "created_at": "기록 시각"}),
 "survey_threshold": ("조사별 각도 기준 변경", "'특별한 사정'으로 바꾼 각도 (F07-02, EX-14)", {
   "survey_id": "조사", "threshold_cd": "각도 기준 코드", "value_deg": "바꾼 각도 (°)",
   "reason_text": "바꾼 사유 (필수)", "changed_by": "바꾼 사람", "changed_at": "바꾼 시각"}),
 "unit_task": ("단위작업", "판정 단위가 되는 작업 (F02-01)", {
   "unit_task_id": "단위작업 식별자", "survey_id": "조사", "task_name": "단위작업명", "task_desc": "작업 내용",
   "worker_cnt": "작업 인원", "period_type_cd": "작업 기간 구분: 상시·단기간·간헐 (BR-02)", "sort_no": "보여 줄 순서",
   "created_at": "만든 시각", "updated_at": "고친 시각"}),
 "task_input": ("작업 정보 입력", "조사자가 면담으로 넣는 값. NULL은 미입력 = '입력 필요' (F02-02)", {
   "unit_task_id": "단위작업", "daily_work_h": "하루 작업시간 (시간)",
   "unsupported_posture_yn": "4호 전제: 지지 없음·자세 변경 불가 (BR-09)",
   "neck_twist_h": "목 비틀림 시간 (시간/일, 4호)", "waist_twist_h": "허리 비틀림 시간 (시간/일, 4호)",
   "keyboard_h": "키보드·마우스 집중 입력 시간 (1호)", "keyboard_self_paced_yn": "입력 시간을 마음대로 조절 가능 (1호, BR-14)",
   "finger_pinch_kg": "손가락으로 집어 옮기는 무게 (6호)", "finger_grip_kg": "손가락으로 쥐는 힘 (kg 환산, 6호)",
   "finger_h": "6호 작업 시간", "finger_unsupported_yn": "6호 지지 없음",
   "onehand_kg": "한 손으로 드는 무게·쥐는 힘 (7호)", "onehand_h": "7호 작업 시간", "onehand_unsupported_yn": "7호 지지 없음",
   "lift_kg": "드는 물체 무게 (8호)", "lift_people_cnt": "함께 드는 인원 (8호, BR-11)", "lift_cnt_per_day": "하루 드는 횟수 (8호)",
   "freq_lift_kg": "자주 드는 무게 (10호)", "freq_lift_per_min": "분당 드는 횟수 (10호)", "freq_lift_h": "10호 작업 시간",
   "impact_h": "충격 작업 시간 (11호)", "impact_per_hour": "시간당 충격 횟수 (11호)", "updated_at": "고친 시각"}),
 "repetition_input": ("부위별 반복 시간", "2호 같은 동작 반복, 부위마다 1행", {
   "unit_task_id": "단위작업", "body_part_cd": "부위", "repeat_h": "반복 시간 (시간/일)"}),
 "lift_position_input": ("위치별 들기", "9호 무릎 아래·어깨 위·팔 뻗음, 위치마다 1행", {
   "unit_task_id": "단위작업", "position_cd": "들기 위치", "lift_cnt_per_day": "하루 횟수", "weight_kg": "무게 (kg)"}),
 "reba_input": ("REBA 사람 입력", "사진으로 못 재는 REBA 항목. NULL은 '사람 확인' (F04-06)", {
   "unit_task_id": "단위작업", "load_kg": "하중 (5단계)", "shock_yn": "충격·급격한 힘 (5단계)", "coupling_cd": "손잡이 (11단계)",
   "wrist_flex_cd": "손목 굽힘 0~15°·15° 초과 (9단계)", "wrist_twist_yn": "손목 꺾임·비틀림 (9a)",
   "neck_twist_side_yn": "목 비틀림·옆굽힘 (1a)", "trunk_twist_side_yn": "몸통 비틀림·옆굽힘 (2a)",
   "legs_support_cd": "다리 지지 (3단계)", "shoulder_raised_yn": "어깨 올림 (7a)", "arm_abducted_yn": "위팔 벌림 (7a)",
   "arm_supported_yn": "팔 받침·기댐 (7a)", "act_static_yn": "1분 넘는 정적 자세 (13단계)",
   "act_repeat_yn": "분당 4회 넘는 작은 반복 (13단계)", "act_rapid_yn": "급격한 큰 자세 변화 (13단계)", "updated_at": "고친 시각"}),
 "still": ("사진", "단위작업의 사진 한 장 (스틸샷). 원본은 복사하지 않고 위치만 저장. 분석에 쓴 사진은 지우지 않고 뺀 것으로 표시 (F03-01, BR-22)", {
   "still_id": "사진 식별자", "unit_task_id": "단위작업", "still_no": "단위작업 안의 순번 (1부터)", "file_path": "원본 위치",
   "file_name": "파일 이름", "width_px": "가로 (픽셀)", "height_px": "세로 (픽셀)", "rotation_deg": "회전 정보 (EXIF)",
   "consent_yn": "촬영 동의 확인 (F03-03)", "consent_at": "동의 확인 시각", "removed_yn": "표본에서 뺌", "registered_at": "등록 시각"}),
 "analysis_run": ("분석 실행", "단위작업의 사진 전체를 모델 1개로 분석한 한 번 (F03-04). 다시 분석하면 새 행", {
   "run_id": "분석 식별자", "unit_task_id": "단위작업", "model_id": "쓴 모델",
   "status_cd": "분석 상태 (3.1절)", "is_current_yn": "현재 결과 여부 (단위작업마다 1개)", "started_at": "시작 시각",
   "finished_at": "끝난 시각", "processing_s": "분석 시간 (초)", "still_total_cnt": "분석한 사진 수 (표본 수)",
   "still_valid_cnt": "판별 가능 사진 수", "invalid_ratio": "판별 불가 비율 (TP-03 비교)", "legs_cut_yn": "다리 잘림 (EX-06)",
   "error_cd": "실패 코드", "jitter_deg": "확신도 흔들기 폭 (TP-01)", "conf_min": "관절 신뢰도 하한 (TP-02)",
   "min_sample_cnt": "표본(사진) 최소 장수 (TP-12)"}),
 "still_angle": ("사진별 각도", "사진마다 각도와 자세 판별 결과 (F04-03, F04-04, OI-12). 관절 위치 원자료는 저장하지 않음", {
   "run_id": "분석", "still_id": "사진", "valid_yn": "판별 가능", "trunk_tilt_deg": "몸통 기울기 (수직 기준, 앞 +)",
   "neck_tilt_vert_deg": "목 기울기 (수직 기준, 4호)", "neck_flex_trunk_deg": "목 굽힘 (몸통 기준, REBA)",
   "upper_arm_raise_l_deg": "왼 위팔 들림 (수직 기준, 3호)", "upper_arm_raise_r_deg": "오른 위팔 들림 (수직 기준, 3호)",
   "upper_arm_flex_l_deg": "왼 위팔 굽힘 (몸통 기준, REBA)", "upper_arm_flex_r_deg": "오른 위팔 굽힘 (몸통 기준, REBA)",
   "elbow_flex_l_deg": "왼 팔꿈치 굽힘", "elbow_flex_r_deg": "오른 팔꿈치 굽힘", "knee_flex_l_deg": "왼 무릎 굽힘",
   "knee_flex_r_deg": "오른 무릎 굽힘", "hand_above_head_yn": "손이 머리 위 (3호 a)", "elbow_above_shoulder_yn": "팔꿈치가 어깨 위 (3호 b)",
   "elbow_behind_trunk_yn": "팔꿈치가 몸통 뒤 (3호 d)", "squat_yn": "쪼그려 앉기 (5호 a)", "kneeling_yn": "무릎 굽힌 자세 (5호 b)",
   "knee_on_floor_yn": "무릎이 바닥에 닿음 (4호 제외, BR-08)"}),
 "reba_result": ("REBA 결과", "대표 사진의 REBA 단계별 점수 (F04-06, F04-07)", {
   "run_id": "분석", "key_still_id": "대표 사진 (그 분석에 쓴 사진)", "key_still_by_cd": "대표 사진을 고른 주체: 자동·조사자",
   "side_cd": "쓴 쪽: 왼쪽·오른쪽 (TP-10)", "neck_score": "1단계 목", "trunk_score": "2단계 몸통", "legs_score": "3단계 다리",
   "table_a_score": "4단계 표 A", "load_score": "5단계 하중", "score_a": "6단계 점수 A", "upper_arm_score": "7단계 위팔",
   "lower_arm_score": "8단계 아래팔", "wrist_score": "9단계 손목", "table_b_score": "10단계 표 B", "coupling_score": "11단계 손잡이",
   "score_b": "12단계 점수 B", "table_c_score": "12단계 표 C", "activity_score": "13단계 활동", "reba_score": "REBA 점수 (1~15)",
   "risk_level_cd": "위험 단계", "provisional_yn": "임시 점수 (사람 입력 빈칸 있음)"}),
 "key_still_image": ("대표 사진 이미지", "얼굴을 가린 대표 사진 (엑셀에 넣음, BR-22)", {
   "run_id": "분석", "still_id": "사진", "image_jpeg": "JPEG 이미지", "masked_yn": "얼굴 가림 (항상 1)", "created_at": "만든 시각"}),
 "judgment": ("판정", "단위작업 × 호마다 1행. 지금 값만 두고 바뀐 내역은 수정 이력에 (F05-01, F05-05)", {
   "judgment_id": "판정 식별자", "unit_task_id": "단위작업", "criterion_no": "호", "run_id": "근거 분석 (사진 근거 호만)",
   "computed_status_cd": "계산 결과 (3.2절)", "review_reason_cd": "사람 확인 사유", "exclusion_cd": "제외 사유: 단기간·간헐",
   "final_status_cd": "확정 결과", "confirmed_yn": "확정 여부", "confirmed_by": "확정한 사람", "confirmed_at": "확정 시각",
   "confirm_reason_text": "확정 사유", "basis_text": "근거 문장", "source_text": "출처 문장", "computed_at": "계산 시각"}),
 "judgment_basis": ("판정 근거", "판정에 쓴 값의 스냅샷 (재현성, 의도적 반정규화)", {
   "basis_id": "근거 식별자", "judgment_id": "판정", "item_cd": "근거 항목 코드", "share_ratio": "자세 비율 (0~1)",
   "exposure_h": "하루 노출 시간", "input_value": "입력값", "unit_cd": "입력값 단위", "threshold_value": "비교한 기준값",
   "threshold_source_cd": "기준 출처: 고시·해설·조사자"}),
 "warning": ("경고", "'해당' 초안이 생길 때 띄운 경고 기록 (F05-03)", {
   "warning_id": "경고 식별자", "unit_task_id": "단위작업", "criterion_no": "호", "judgment_id": "근거 판정",
   "message_text": "기본 경고 문구", "basis_text": "근거 문장", "raised_at": "뜬 시각", "cleared_at": "사라진 시각 (다시 계산으로)"}),
 "ai_text": ("AI 문장", "GPT 요청과 결과 기록. 보낸 값을 남겨 개인정보가 없었음을 증명 (F06-02, F06-03)", {
   "ai_text_id": "식별자", "purpose_cd": "용도: 경고 조언·보고서 요약", "warning_id": "경고 (조언일 때)",
   "survey_id": "조사 (요약일 때)", "model_name": "GPT 모델 이름", "prompt_version": "프롬프트 버전",
   "request_json": "보낸 값 (JSON)", "response_text": "받은 문장", "result_cd": "결과: 정상·기본 문구로 대체 사유",
   "edited_text": "조사자가 고친 문장", "created_at": "요청 시각"}),
 "edit_log": ("수정 이력", "추가만 가능. 누가·언제·무엇을·왜 (F05-06)", {
   "log_id": "이력 식별자", "survey_id": "조사", "unit_task_id": "단위작업 (외래키 없음: 작업을 지워도 이력은 남김)",
   "target_cd": "바뀐 대상", "target_key": "대상 위치 (예: criterion=4)", "action_cd": "동작", "old_value": "이전 값",
   "new_value": "새 값", "reason_text": "사유", "actor_name": "바꾼 사람", "logged_at": "기록 시각"}),
 "export_log": ("엑셀 내보내기 기록", "엑셀을 만든 기록 (F06-01)", {
   "export_id": "식별자", "survey_id": "조사", "file_path": "저장 위치", "draft_cell_cnt": "'초안' 칸 수", "exported_at": "만든 시각"}),
 "app_setting": ("앱 설정", "모델·GPT 사용 여부 등. GPT 키는 여기 두지 않음 (F07-03)", {
   "setting_key": "설정 이름", "setting_value": "값", "updated_at": "고친 시각"}),
 "schema_version": ("스키마 버전", "스키마 변경 기록 (마이그레이션)", {
   "version_no": "버전", "description": "설명", "applied_at": "적용 시각"}),
}

c = sqlite3.connect(":memory:")
c.execute("PRAGMA foreign_keys = ON")
c.executescript(SCHEMA)
c.executescript(SEED)

tables = [r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY rowid")]
missing_desc = [t for t in tables if t not in D]
col_missing = []
out = []
for i, t in enumerate(tables, 1):
    kname, purpose, cols = D[t]
    opts = c.execute("SELECT sql FROM sqlite_master WHERE name=?", (t,)).fetchone()[0]
    tail = opts[opts.rfind(")") + 1:]
    tags = [w for w in ("STRICT", "WITHOUT ROWID") if w in tail]
    fks = {r[3]: f"{r[2]}.{r[4]}" for r in c.execute(f"PRAGMA foreign_key_list({t})")}
    uniq = [r[1] for r in c.execute(f"PRAGMA index_list({t})") if r[2] == 1 and r[3] == 'u']
    out.append(f"#### T{i:02d}. {t} ({kname})\n")
    out.append(f"{purpose}. 저장 방식: {', '.join(tags) if tags else '기본'}\n")
    out.append("| 컬럼 | 타입 | NULL | 기본값 | 키 | 설명 |\n|---|---|---|---|---|---|")
    for cid, name, typ, notnull, dflt, pk, hidden in c.execute(f"PRAGMA table_xinfo({t})"):
        key = []
        if pk: key.append("PK")
        if name in fks: key.append("FK → " + fks[name])
        if name not in cols: col_missing.append(f"{t}.{name}")
        d = "" if dflt is None else str(dflt).replace("strftime('%Y-%m-%dT%H:%M:%S','now','localtime')", "지금 시각").replace("|", "\\|")
        out.append(f"| {name} | {typ} | {'아니오' if notnull or pk else '예'} | {d} | {' · '.join(key)} | {cols.get(name, '')} |")
    for u in uniq:
        ucols = [r[2] for r in c.execute(f"PRAGMA index_info({u})")]
        out.append(f"\n고유 제약: ({', '.join(ucols)})")
    out.append("")
TABLE_DEFS = "\n".join(out)

idx = []
for name, tbl, sql in c.execute("SELECT name, tbl_name, sql FROM sqlite_master WHERE type='index' AND sql IS NOT NULL ORDER BY rowid"):
    cols = re.search(r"\((.*?)\)", sql).group(1)
    where = re.search(r"WHERE (.*)$", sql)
    kind = "고유·부분" if "UNIQUE" in sql and where else ("고유" if "UNIQUE" in sql else "일반")
    idx.append(f"| {name} | {tbl} | {cols} | {kind}{' (' + where.group(1) + ')' if where else ''} |")
INDEXES = "| 인덱스 | 테이블 | 열 | 종류 |\n|---|---|---|---|\n" + "\n".join(idx)

trg = []
for name, tbl, sql in c.execute("SELECT name, tbl_name, sql FROM sqlite_master WHERE type='trigger' ORDER BY rowid"):
    msg = re.search(r"RAISE\(ABORT, '(.*?)'\)", sql).group(1)
    when = re.search(r"(BEFORE \w+(?: OF \w+)? ON \w+)", sql).group(1)
    trg.append(f"| {name} | {when} | {msg} |")
TRIGGERS = "| 트리거 | 언제 | 막는 것 (오류 문구) |\n|---|---|---|\n" + "\n".join(trg)

# 용량 실측: 사진 30장 분석 1건이 파일에서 차지하는 크기 (사진 기록 30행 + 사진별 각도 30행)
tmp = Path(tempfile.gettempdir()) / "erd_size_probe.db"
if tmp.exists(): tmp.unlink()
f = sqlite3.connect(tmp); f.execute("PRAGMA foreign_keys = ON"); f.executescript(SCHEMA); f.executescript(SEED); f.commit()
f.execute("VACUUM"); base = os.path.getsize(tmp)
f.execute("INSERT INTO survey(survey_id,survey_type_cd,survey_date,investigator_name,dept_name,process_name,work_name) VALUES (1,'REGULAR','2026-10-23','a','b','c','d')")
f.execute("INSERT INTO unit_task(unit_task_id,survey_id,task_name,worker_cnt,period_type_cd) VALUES (1,1,'t',1,'ONGOING')")
N_STILL = 30
for n in range(N_STILL):
    f.execute("INSERT INTO still(still_id,unit_task_id,still_no,file_path,file_name,width_px,height_px,consent_yn,consent_at)"
              " VALUES (?,1,?,?,?,720,1280,1,'2026-10-23T10:00:00')", (n + 1, n + 1, f"D:/사진/작업_{n + 1:02d}.jpg", f"작업_{n + 1:02d}.jpg"))
f.execute("INSERT INTO analysis_run(run_id,unit_task_id,model_id,status_cd,is_current_yn,finished_at) VALUES (1,1,1,'DONE',1,'2026-10-23T10:01:00')")
import random
random.seed(1)
f.executemany("INSERT INTO still_angle VALUES (" + ",".join("?" * 20) + ")",
              [(1, n + 1, 1) + tuple(round(random.uniform(0, 90), 3) for _ in range(11)) + (0, 0, 0, 0, 0, 0) for n in range(N_STILL)])
f.commit(); f.execute("VACUUM"); per_run = os.path.getsize(tmp) - base; f.close(); tmp.unlink()

counts = TEST["objects"]
res = TEST["results"]
ok = sum(r["ok"] for r in res)
rows = []
for r in res:
    msg = r["msg"].replace("\n", " ")
    msg = re.sub(r"\s{2,}", " ", msg).replace("|", "\\|")
    if len(msg) > 120: msg = msg[:117] + "…"
    rows.append(f"| {r['id']} | {r['name']} | {r['expect']} | {'맞음' if r['ok'] else '틀림'} | {msg} |")
TESTS = (f"SQLite {TEST['sqlite']}에서 실행. **{ok}/{len(res)} 기대대로** "
         f"(통과해야 할 것 {sum(1 for r in res if r['id'].startswith('P'))}개, 막혀야 할 것 {sum(1 for r in res if r['id'].startswith('M'))}개)\n\n"
         "| ID | 시험 | 기대 | 결과 | 실제 메시지 |\n|---|---|---|---|---|\n" + "\n".join(rows))

q = []
for k, v in TEST["queries"].items():
    q.append(f"**{k}**\n\n```sql\n{v['sql']}\n```\n\n결과: " + ", ".join(str(tuple(r)) for r in v["rows"]) + "\n")
QUERIES = "\n".join(q)
PLANS = "| 조회 | 실행 계획 |\n|---|---|\n" + "\n".join(f"| {k} | {' / '.join(v)} |" for k, v in TEST["plans"].items())

views = re.findall(r"(-- [^\n]*\n)?(CREATE VIEW .*?;)\n", SCHEMA, re.S)
VIEW_SQL = "\n\n".join((cm or "") + sql for cm, sql in views)

doc = (TEMPLATE
       .replace("{{TABLE_DEFS}}", TABLE_DEFS)
       .replace("{{INDEXES}}", INDEXES)
       .replace("{{TRIGGERS}}", TRIGGERS)
       .replace("{{TESTS}}", TESTS)
       .replace("{{QUERIES}}", QUERIES)
       .replace("{{PLANS}}", PLANS)
       .replace("{{VIEW_SQL}}", VIEW_SQL)
       .replace("{{DDL}}", SCHEMA.strip())
       .replace("{{SEED}}", SEED.strip())
       .replace("{{N_TABLE}}", str(counts["table"]))
       .replace("{{N_VIEW}}", str(counts["view"]))
       .replace("{{N_INDEX}}", str(counts["index_explicit"]))
       .replace("{{N_TRIGGER}}", str(counts["trigger"]))
       .replace("{{RUN_KB}}", f"{per_run / 1024:.0f}"))
left = re.findall(r"\{\{\w+\}\}", doc)
paths.write_text(OUT, doc)
print("tables", len(tables), "missing desc", missing_desc, "missing cols", col_missing, "placeholders left", left)
print(f"per {N_STILL}-still run bytes", per_run, "→ doc", OUT, len(doc), "chars")
