import json, sqlite3, sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import paths  # noqa: E402
SCHEMA = paths.SCHEMA_FILE.read_text(encoding="utf-8")
SEED = paths.SEED_FILE.read_text(encoding="utf-8")

def fresh():
    c = sqlite3.connect(":memory:")
    c.execute("PRAGMA foreign_keys = ON")
    c.executescript(SCHEMA)
    c.executescript(SEED)
    return c

def sample(c):
    x = c.execute
    x("INSERT INTO survey(survey_id,survey_type_cd,survey_date,investigator_name,dept_name,process_name,work_name)"
      " VALUES (1,'REGULAR','2026-10-23','홍길동','포장부','포장공정','상자 포장 및 운반')")
    x("INSERT INTO participant(survey_id,participant_type_cd,display_name) VALUES (1,'WORKER','근로자 A')")
    x("INSERT INTO unit_task(unit_task_id,survey_id,task_name,worker_cnt,period_type_cd) VALUES (10,1,'상자 들어 옮기기',2,'ONGOING')")
    x("INSERT INTO unit_task(unit_task_id,survey_id,task_name,worker_cnt,period_type_cd) VALUES (11,1,'선반 정리',1,'ONGOING')")
    x("INSERT INTO task_input(unit_task_id,daily_work_h,unsupported_posture_yn,lift_kg,lift_people_cnt,lift_cnt_per_day)"
      " VALUES (10,6,1,30,2,12)")
    for n in range(20):                     # 단위작업 10: 사진 20장 (still_id 100~119, still_no 1~20)
        x("INSERT INTO still(still_id,unit_task_id,still_no,file_path,file_name,width_px,height_px,consent_yn,consent_at)"
          " VALUES (?,10,?,?,?,720,1280,1,'2026-10-23T10:00:00')",
          (100 + n, n + 1, f"D:/사진/상자옮기기_{n + 1:02d}.jpg", f"상자옮기기_{n + 1:02d}.jpg"))
    x("INSERT INTO still(still_id,unit_task_id,still_no,file_path,file_name,width_px,height_px,consent_yn,consent_at)"
      " VALUES (200,11,1,'D:/사진/선반.jpg','선반.jpg',720,1280,1,'2026-10-23T10:05:00')")
    x("INSERT INTO analysis_run(run_id,unit_task_id,model_id,status_cd,is_current_yn,finished_at,processing_s,"
      "still_total_cnt,still_valid_cnt,invalid_ratio) VALUES (1000,10,1,'DONE',1,'2026-10-23T10:01:00',0.4,20,20,0)")
    # 사진 20장 중 7장(still_no 1~7)이 허리 굽힘 35° → 비율 35%
    rows = [(1000, 100 + n, 1, 35.0 if n < 7 else 10.0, 10.0, 5.0, 20.0, 20.0, 10.0, 10.0, 90.0, 90.0, 10.0, 10.0,
             0, 0, 0, 0, 0, 0) for n in range(20)]
    c.executemany("INSERT INTO still_angle VALUES (" + ",".join("?" * 20) + ")", rows)
    x("INSERT INTO reba_result VALUES (1000,100,'AUTO','R',2,4,2,6,2,8,3,1,2,4,1,5,8,1,9,'HIGH',0)")
    x("INSERT INTO key_still_image(run_id,still_id,image_jpeg,masked_yn) VALUES (1000,100,X'FFD8FFE0',1)")
    x("INSERT INTO judgment(judgment_id,unit_task_id,criterion_no,run_id,computed_status_cd,basis_text,source_text)"
      " VALUES (1,10,4,1000,'APPLICABLE','허리 굽힘 35% × 하루 6시간 = 2.10시간 ≥ 2시간','고시 제3조 제4호 · 각도 20°(해설 4호 주3)')")
    x("INSERT INTO judgment_basis(judgment_id,item_cd,share_ratio,exposure_h,threshold_value,threshold_source_cd)"
      " VALUES (1,'WAIST_FLEX',0.35,2.1,20,'MOEL_NOTE')")
    x("INSERT INTO judgment(judgment_id,unit_task_id,criterion_no,computed_status_cd,basis_text,source_text)"
      " VALUES (2,10,8,'NOT_APPLICABLE','30kg ÷ 2명 = 15kg < 25kg','고시 제3조 제8호 · 해설 8호 주2')")
    x("INSERT INTO judgment_basis(judgment_id,item_cd,input_value,unit_cd,threshold_value,threshold_source_cd)"
      " VALUES (2,'LIFT_KG_PER_PERSON',15,'KG',25,'NOTICE')")
    x("INSERT INTO judgment(judgment_id,unit_task_id,criterion_no,computed_status_cd,basis_text,source_text)"
      " VALUES (3,10,1,'NEEDS_INPUT','키보드·마우스 집중 입력 시간 없음','고시 제3조 제1호')")
    x("INSERT INTO judgment(judgment_id,unit_task_id,criterion_no,run_id,computed_status_cd,review_reason_cd,basis_text,source_text)"
      " VALUES (4,10,5,1000,'NEEDS_REVIEW','JITTER','−5°: 비해당 / +5°: 해당','고시 제3조 제5호')")
    x("INSERT INTO warning(warning_id,unit_task_id,criterion_no,judgment_id,message_text,basis_text,raised_at)"
      " VALUES (1,10,4,1,'부담작업 4호 기준(하루 총 2시간)을 넘습니다.','허리 굽힘 35% × 하루 6시간 = 2.10시간','2026-10-23T10:01:00')")
    x("INSERT INTO edit_log(survey_id,unit_task_id,target_cd,target_key,action_cd,old_value,new_value,actor_name)"
      " VALUES (1,10,'TASK_INPUT','daily_work_h','SET',NULL,'6','홍길동')")

def approx(a, b):
    return a is not None and abs(a - b) < 1e-9

results = []
def check(tid, name, fn, expect_error):
    c = fresh(); sample(c)
    try:
        detail = fn(c)
        ok = not expect_error
        msg = detail if detail else "통과"
    except sqlite3.IntegrityError as e:
        ok = expect_error
        msg = str(e)
    except AssertionError as e:
        ok = False
        msg = "기대와 다름: " + str(e)
    except sqlite3.Error as e:            # 없는 열·문법 오류 등: 막힌 것이 아니라 시험 실패
        ok = False
        msg = "SQL 오류: " + str(e)
    results.append({"id": tid, "name": name, "expect": "막혀야 함" if expect_error else "통과해야 함",
                    "ok": ok, "msg": msg})

# ---- 통과해야 하는 시험 ----
def p1(c):
    r = c.execute("SELECT waist_flex_ratio, waist_flex_h FROM v_posture_exposure_check WHERE run_id=1000").fetchone()
    assert approx(r[0], 0.35) and approx(r[1], 2.1), r
    return f"허리 굽힘 비율 {r[0]:.2f}, 하루 노출 {r[1]:.2f}시간"
check("P1", "저장된 사진별 각도로 자세 비율과 하루 노출을 다시 계산 (20장 중 7장 = 35% × 6시간)", p1, False)

def p2(c):
    r = c.execute("SELECT value_deg, source_label FROM v_effective_threshold WHERE survey_id=1 AND threshold_cd='WAIST_FLEX'").fetchone()
    assert r == (20.0, '해설 4호 주3'), r
    c.execute("INSERT INTO survey_threshold(survey_id,threshold_cd,value_deg,reason_text,changed_by)"
              " VALUES (1,'WAIST_FLEX',40,'허리를 받치는 지지대가 있음','홍길동')")
    r2 = c.execute("SELECT value_deg, source_label FROM v_effective_threshold WHERE survey_id=1 AND threshold_cd='WAIST_FLEX'").fetchone()
    s2 = c.execute("SELECT waist_flex_ratio FROM v_posture_exposure_check WHERE run_id=1000").fetchone()[0]
    assert r2[0] == 40.0 and r2[1].startswith('조사자 변경') and approx(s2, 0.0), (r2, s2)
    return f"기본 20°(해설 4호 주3) → 변경 40° '{r2[1]}' → 비율 {s2:.2f}"
check("P2", "각도 기준을 사유와 함께 바꾸면 뷰와 다시 계산 결과가 바뀜", p2, False)

def p3(c):
    c.execute("UPDATE survey SET status_cd='CONFIRMED', confirmed_at='2026-10-30T15:00:00' WHERE survey_id=1")
    d = c.execute("SELECT next_regular_due_date FROM v_survey_list WHERE survey_id=1").fetchone()[0]
    assert d == '2029-10-30', d
    return f"다음 정기조사 예정일 {d}"
check("P3", "2026-10-30 확정 정기조사 → 다음 정기조사 예정일 (AC-03)", p3, False)

def p4(c):
    cols = [d[0] for d in c.execute("SELECT * FROM v_gpt_payload").description]
    bad = [k for k in cols if any(w in k for w in ("name", "path", "investigator", "display", "dept", "process", "work_name", "task_name"))]
    row = c.execute("SELECT max_exposure_h, reba_score, survey_task_cnt FROM v_gpt_payload"
                    " WHERE warning_id=1 AND survey_id=1").fetchone()
    assert not bad and approx(row[0], 2.1) and row[1] == 9 and row[2] == 2, (bad, row)
    return f"열 {len(cols)}개: {', '.join(cols)} · 이름·경로 열 없음 · 조사의 단위작업 {row[2]}개"
check("P4", "GPT 전송 뷰에 이름·경로·자유 입력 글이 없음 (AC-30)", p4, False)

def p5(c):
    r = c.execute("SELECT applicable_criteria, draft_cnt FROM v_excel_summary WHERE unit_task_id=10").fetchone()
    assert r == ('4호', 4), r
    return f"해당 호 '{r[0]}', 초안 {r[1]}개"
check("P5", "엑셀 요약 뷰가 해당 호와 초안 개수를 보여 줌", p5, False)

def p6(c):
    c.execute("UPDATE judgment SET confirmed_yn=1, final_status_cd='APPLICABLE', confirmed_by='홍길동',"
              " confirmed_at='2026-10-30T14:00:00' WHERE judgment_id=1")
    c.execute("UPDATE judgment SET confirmed_yn=1, final_status_cd='NOT_APPLICABLE', confirmed_by='홍길동',"
              " confirmed_at='2026-10-30T14:01:00', confirm_reason_text='사진을 다시 보니 쪼그림 시간이 짧음' WHERE judgment_id=4")
    return "초안과 같은 결과는 사유 없이, '사람 확인'은 사유와 함께 확정됨"
check("P6", "정상 확정 (초안과 같으면 사유 없이, 사람 확인은 사유와 함께)", p6, False)

def p7(c):
    c.execute("DELETE FROM survey WHERE survey_id=1")
    left = {t: c.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
            for t in ("unit_task", "still_angle", "judgment", "warning", "edit_log", "still", "analysis_run")}
    assert all(v == 0 for v in left.values()), left
    return "조사를 지우면 단위작업·사진·분석·판정·경고·이력이 함께 지워짐"
check("P7", "조사 전체 삭제는 수정 이력까지 함께 지움 (보존 기간이 끝난 조사 정리)", p7, False)

def p8(c):
    c.execute("DELETE FROM unit_task WHERE unit_task_id=10")
    n = c.execute("SELECT COUNT(*) FROM analysis_run WHERE unit_task_id=10").fetchone()[0]
    e = c.execute("SELECT COUNT(*) FROM edit_log WHERE unit_task_id=10").fetchone()[0]
    assert n == 0 and e == 1, (n, e)
    return "단위작업을 지우면 사진·분석은 지워지고 수정 이력 1줄은 남음"
check("P8", "단위작업 삭제: 분석은 함께 지워지고 이력은 남음", p8, False)

# ---- 막혀야 하는 시험 ----
M = [
 ("M01", "REBA 점수 16점", lambda c: c.execute("UPDATE reba_result SET reba_score=16 WHERE run_id=1000")),
 ("M02", "REBA 9점인데 위험 단계 '보통'", lambda c: c.execute("UPDATE reba_result SET risk_level_cd='MEDIUM' WHERE run_id=1000")),
 ("M03", "REBA 점수 ≠ 표 C 점수 + 활동 점수", lambda c: c.execute("UPDATE reba_result SET activity_score=3 WHERE run_id=1000")),
 ("M04", "얼굴을 가리지 않은 대표 사진 저장", lambda c: c.execute("UPDATE key_still_image SET masked_yn=0 WHERE run_id=1000")),
 ("M05", "수정 이력 고치기", lambda c: c.execute("UPDATE edit_log SET new_value='5'")),
 ("M06", "수정 이력 한 줄만 지우기", lambda c: c.execute("DELETE FROM edit_log")),
 ("M07", "사유 없이 각도 기준 변경", lambda c: c.execute(
     "INSERT INTO survey_threshold(survey_id,threshold_cd,value_deg,reason_text,changed_by) VALUES (1,'WAIST_FLEX',30,'   ','홍길동')")),
 ("M08", "'입력 필요' 판정 확정", lambda c: c.execute(
     "UPDATE judgment SET confirmed_yn=1, final_status_cd='NOT_APPLICABLE', confirmed_by='홍길동', confirmed_at='2026-10-30T14:00:00' WHERE judgment_id=3")),
 ("M09", "'사람 확인'을 사유 없이 확정", lambda c: c.execute(
     "UPDATE judgment SET confirmed_yn=1, final_status_cd='APPLICABLE', confirmed_by='홍길동', confirmed_at='2026-10-30T14:00:00' WHERE judgment_id=4")),
 ("M10", "초안과 다른 결과로 사유 없이 확정", lambda c: c.execute(
     "UPDATE judgment SET confirmed_yn=1, final_status_cd='NOT_APPLICABLE', confirmed_by='홍길동', confirmed_at='2026-10-30T14:00:00' WHERE judgment_id=1")),
 ("M11", "촬영 동의 없는 사진이 있는데 분석", lambda c: (
     c.execute("INSERT INTO still(still_id,unit_task_id,still_no,file_path,file_name,width_px,height_px)"
               " VALUES (150,10,21,'D:/사진/b.jpg','b.jpg',720,1280)"),
     c.execute("INSERT INTO analysis_run(unit_task_id,model_id,status_cd) VALUES (10,1,'RUNNING')"))),
 ("M12", "한 단위작업에 '현재' 분석이 2개", lambda c: c.execute(
     "INSERT INTO analysis_run(unit_task_id,model_id,status_cd,is_current_yn,finished_at) VALUES (10,1,'DONE',1,'2026-10-23T11:00:00')")),
 ("M13", "다른 단위작업의 사진으로 각도 저장", lambda c: c.execute(
     "INSERT INTO still_angle(run_id,still_id,valid_yn) VALUES (1000,200,1)")),
 ("M14", "없는 조사에 단위작업 추가 (외래키)", lambda c: c.execute(
     "INSERT INTO unit_task(survey_id,task_name,worker_cnt,period_type_cd) VALUES (999,'x',1,'ONGOING')")),
 ("M15", "하루 작업시간 25시간", lambda c: c.execute("UPDATE task_input SET daily_work_h=25 WHERE unit_task_id=10")),
 ("M16", "정기조사에 수시 사유 넣기", lambda c: c.execute("INSERT INTO survey_reason VALUES (1,'NEW_TASK')")),
 ("M17", "같은 단위작업·같은 호 판정 2개", lambda c: c.execute(
     "INSERT INTO judgment(unit_task_id,criterion_no,computed_status_cd,basis_text,source_text) VALUES (10,4,'APPLICABLE','x','y')")),
 ("M18", "분석에 쓴 사진만 지우기", lambda c: c.execute("DELETE FROM still WHERE still_id=105")),
 ("M19", "확정 시각 없이 조사 확정", lambda c: c.execute("UPDATE survey SET status_cd='CONFIRMED' WHERE survey_id=1")),
 ("M20", "다른 단위작업의 분석 결과로 판정", lambda c: c.execute(
     "INSERT INTO judgment(unit_task_id,criterion_no,run_id,computed_status_cd,basis_text,source_text) VALUES (11,3,1000,'APPLICABLE','x','y')")),
 ("M21", "AI 문장이 경고와 조사 둘 다를 가리킴", lambda c: c.execute(
     "INSERT INTO ai_text(purpose_cd,warning_id,survey_id,model_name,prompt_version,request_json,result_cd)"
     " VALUES ('WARNING_ADVICE',1,1,'gpt','v1','{}','DISABLED')")),
 ("M22", "비틀림 시간이 하루 작업시간보다 큼", lambda c: c.execute("UPDATE task_input SET waist_twist_h=7 WHERE unit_task_id=10")),
 ("M23", "대표 사진이 그 분석에 쓰지 않은 사진", lambda c: c.execute("UPDATE reba_result SET key_still_id=200 WHERE run_id=1000")),
 ("M24", "사진이 없는 단위작업을 분석", lambda c: (
     c.execute("INSERT INTO unit_task(unit_task_id,survey_id,task_name,worker_cnt,period_type_cd) VALUES (12,1,'사진 없는 작업',1,'ONGOING')"),
     c.execute("INSERT INTO analysis_run(unit_task_id,model_id,status_cd) VALUES (12,1,'RUNNING')"))),
]
for tid, name, fn in M:
    check(tid, name, fn, True)

# ---- 예시 쿼리 (SQLD 연습 겸 업무 질의) ----
queries = {
 "Q1 작업별 REBA 순위 (윈도우 함수)":
   "SELECT survey_id, task_name, reba_score, RANK() OVER (PARTITION BY survey_id ORDER BY reba_score DESC) AS reba_rank FROM v_task_result",
 "Q2 해당 호가 1개 이상인 단위작업 (GROUP BY · HAVING)":
   "SELECT unit_task_id, COUNT(*) AS applicable_cnt FROM judgment WHERE COALESCE(final_status_cd, computed_status_cd)='APPLICABLE' GROUP BY unit_task_id HAVING COUNT(*) >= 1",
 "Q3 8호 다시 계산: 무게 ÷ 인원 (CTE · CASE)":
   "WITH lift AS (SELECT unit_task_id, lift_kg*1.0/lift_people_cnt AS kg_per_person, lift_cnt_per_day FROM task_input WHERE lift_kg IS NOT NULL) "
   "SELECT unit_task_id, kg_per_person, CASE WHEN kg_per_person >= 25 AND lift_cnt_per_day >= 10 THEN 'APPLICABLE' ELSE 'NOT_APPLICABLE' END AS c8 FROM lift",
 "Q4 아직 분석하지 않은 단위작업 (LEFT JOIN · IS NULL)":
   "SELECT t.unit_task_id, t.task_name FROM unit_task t LEFT JOIN analysis_run r ON r.unit_task_id=t.unit_task_id AND r.is_current_yn=1 WHERE r.run_id IS NULL",
 "Q5 '사람 확인'이 남은 조사 (EXISTS)":
   "SELECT s.survey_id FROM survey s WHERE EXISTS (SELECT 1 FROM judgment j JOIN unit_task t ON t.unit_task_id=j.unit_task_id "
   "WHERE t.survey_id=s.survey_id AND j.computed_status_cd='NEEDS_REVIEW' AND j.confirmed_yn=0)",
}
c = fresh(); sample(c)
qres = {}
for k, q in queries.items():
    cur = c.execute(q)
    qres[k] = {"sql": q, "cols": [d[0] for d in cur.description], "rows": cur.fetchall()}
plans = {}
for k, q in {
    "현재 분석 찾기": "SELECT * FROM analysis_run WHERE unit_task_id=10 AND is_current_yn=1",
    "조사의 수정 이력 시간순": "SELECT * FROM edit_log WHERE survey_id=1 ORDER BY logged_at",
    "단위작업의 판정 11개": "SELECT * FROM judgment WHERE unit_task_id=10",
}.items():
    plans[k] = [r[3] for r in c.execute("EXPLAIN QUERY PLAN " + q)]

objs = {t: c.execute("SELECT COUNT(*) FROM sqlite_master WHERE type=?", (t,)).fetchone()[0]
        for t in ("table", "view", "index", "trigger")}
objs["index_explicit"] = c.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='index' AND sql IS NOT NULL").fetchone()[0]

def write_report():
    (paths.WORK / "test_results.json").write_text(json.dumps(
        {"sqlite": sqlite3.sqlite_version, "results": results, "queries": qres, "plans": plans, "objects": objs},
        ensure_ascii=False, indent=1, default=str), encoding="utf-8")

    ok = sum(r["ok"] for r in results)
    print(f"SQLite {sqlite3.sqlite_version} · {ok}/{len(results)} OK · objects {objs}")
    for r in results:
        print(("OK  " if r["ok"] else "FAIL"), r["id"], r["name"], "→", r["msg"])
    for k, v in qres.items():
        print(k, v["rows"])
    for k, v in plans.items():
        print("PLAN", k, v)


if __name__ == "__main__":
    write_report()
