"""DB 성능 실측 (DB 아키텍처 설계서 6절). 문서의 숫자는 이 스크립트가 잰 값이다.

    python docs_src/dba/bench_db.py            # 재서 화면에 보여 준다
    python docs_src/dba/bench_db.py --save     # 결과를 bench_snapshot.json에 저장한다 (문서가 이 파일을 읽는다)

재는 것
  1. 분석 결과 저장: 900프레임 (30fps 30초)을 한 트랜잭션으로 저장하는 시간
     실제 흐름대로 한다: 시작할 때 RUNNING 행을 만들어 두고 (재지 않음), 끝날 때 그 행을 DONE으로 바꾸며 결과를 쓴다
  2. 나쁜 예: 프레임마다 커밋하는 시간 (그래서 한 트랜잭션으로 묶는다)
  3. 다시 계산에 쓰는 읽기: 저장된 프레임으로 자세 비율을 다시 구하는 시간
  4. 큰 DB: 조사 100건 × 단위작업 5개 × 900프레임. 파일 크기, 목록 읽기, 판정 읽기, 백업, 무결성 검사, VACUUM
  5. 읽기와 쓰기가 동시에: 쓰기 스레드가 분석 저장을 반복하는 동안 읽기 스레드가 목록을 계속 읽는다
시간은 이 PC 한 대의 값이다. 다른 PC에서는 다시 재서 비교한다.
"""
import json
import platform
import random
import sqlite3
import statistics
import sys
import tempfile
import threading
import time
from datetime import date
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1]))
from ergo.db import open_db  # noqa: E402

FRAMES = 900
JPEG = bytes.fromhex("FFD8FFE0") + bytes(700)       # 대표 장면 자리표시자 (크기만 비슷하게)
_RNG = random.Random(20261012)                       # 같은 값이 나오게 고정한다


def ms(t0):
    return (time.perf_counter() - t0) * 1000


def frame_rows(run_id, n=FRAMES):
    """실제 각도처럼 소수점이 긴 값 (정수값 실수는 SQLite가 작게 저장해서 크기를 줄여 보이게 한다)."""
    r = _RNG.random
    return [(run_id, i, 1, 40 * r(), 30 * r(), 20 * r(), 90 * r(), 90 * r(), 60 * r(), 60 * r(), 120 * r(), 120 * r(),
             60 * r(), 60 * r(), int(r() < .1), int(r() < .1), int(r() < .1), int(r() < .05), 0, 0) for i in range(n)]


def start_run(con, task_id, run_id):
    """분석을 시작할 때: RUNNING 한 줄 (짧은 트랜잭션 1)."""
    with con:
        con.execute("INSERT INTO analysis_run(run_id,unit_task_id,video_id,model_id,status_cd) VALUES (?,?,?,4,'RUNNING')",
                    (run_id, task_id, task_id))


def save_analysis(con, task_id, run_id, replace_run=None):
    """분석이 끝났을 때 결과 전부를 한 트랜잭션으로 저장한다 (DB 아키텍처 설계서 5.1절의 순서)."""
    with con:
        if replace_run is not None:                         # 이전 '현재' 분석을 먼저 내린다 (5.2절)
            con.execute("UPDATE analysis_run SET is_current_yn = 0 WHERE run_id = ?", (replace_run,))
        con.executemany("INSERT INTO frame_angle VALUES (" + ",".join("?" * 20) + ")", frame_rows(run_id))
        con.execute("INSERT INTO reba_result VALUES (?,10,'AUTO','R',2,4,2,6,2,8,3,1,2,4,1,5,8,1,9,'HIGH',0)", (run_id,))
        con.execute("INSERT INTO key_frame_image(run_id,frame_no,image_jpeg,masked_yn) VALUES (?,10,?,1)", (run_id, JPEG))
        for no in range(1, 12):
            con.execute("INSERT INTO judgment(unit_task_id,criterion_no,run_id,computed_status_cd,basis_text,source_text)"
                        " VALUES (?,?,?,?,?,?) ON CONFLICT(unit_task_id,criterion_no) DO UPDATE SET run_id=excluded.run_id,"
                        "computed_status_cd=excluded.computed_status_cd,basis_text=excluded.basis_text",
                        (task_id, no, run_id if no in (3, 4, 5) else None, "APPLICABLE" if no == 4 else "NOT_APPLICABLE",
                         "허리 굽힘 35% × 하루 6시간 = 2.10시간", f"고시 제3조 제{no}호"))
        con.execute("UPDATE analysis_run SET status_cd='DONE', is_current_yn=1, finished_at='2026-10-23T10:01:00',"
                    " processing_s=19.4, frame_total_cnt=?, frame_valid_cnt=?, invalid_ratio=0 WHERE run_id=?",
                    (FRAMES, FRAMES, run_id))


def add_task(con, survey_id, task_id, name):
    con.execute("INSERT INTO unit_task(unit_task_id,survey_id,task_name,worker_cnt,period_type_cd) VALUES (?,?,?,2,'ONGOING')",
                (task_id, survey_id, name))
    con.execute("INSERT INTO task_input(unit_task_id,daily_work_h,unsupported_posture_yn) VALUES (?,6,1)", (task_id,))
    con.execute("INSERT INTO video(video_id,unit_task_id,file_path,file_name,duration_s,fps,frame_cnt,width_px,height_px,"
                "consent_yn,consent_at) VALUES (?,?,?,?,30,30,900,720,1280,1,'2026-10-23T10:00:00')",
                (task_id, task_id, f"D:/영상/{task_id}.mp4", f"{task_id}.mp4"))


def add_survey(con, sid):
    con.execute("INSERT INTO survey(survey_id,survey_type_cd,survey_date,investigator_name,dept_name,process_name,work_name)"
                " VALUES (?,'REGULAR',?,'홍길동','포장부','포장공정','상자 포장')",
                (sid, f"2026-{1 + sid % 12:02d}-{1 + sid % 27:02d}"))


def main():
    save = "--save" in sys.argv
    out = {"date": date.today().isoformat(), "platform": platform.platform(), "python": platform.python_version(),
           "sqlite": sqlite3.sqlite_version, "frames": FRAMES}
    with tempfile.TemporaryDirectory(dir=str(Path.home() / "AppData/Local/Temp")) as d:
        # 1, 3 ---------------------------------------------------------------
        con = open_db(Path(d) / "one.db")
        out["journal_mode"] = con.execute("PRAGMA journal_mode").fetchone()[0]
        out["synchronous"] = {0: "OFF", 1: "NORMAL", 2: "FULL", 3: "EXTRA"}[con.execute("PRAGMA synchronous").fetchone()[0]]
        with con:
            add_survey(con, 1)
            add_task(con, 1, 10, "상자 들어 옮기기")
        times = []
        prev = None
        for k in range(10):                       # 같은 단위작업에 분석을 10번 (이전 분석을 내리고 새 분석을 올림)
            run = 1000 + k
            start_run(con, 10, run)               # 재지 않는다
            t0 = time.perf_counter()
            save_analysis(con, 10, run, replace_run=prev)
            times.append(ms(t0))
            prev = run
        out["save_900_frames_ms"] = {"median": round(statistics.median(times), 1), "max": round(max(times), 1)}
        t0 = time.perf_counter()
        for _ in range(100):
            con.execute("SELECT * FROM v_posture_exposure_check WHERE unit_task_id = 10").fetchall()
        out["recalc_read_ms"] = round(ms(t0) / 100, 2)
        con.close()

        # 2 --------------------------------------------------------------------
        con = open_db(Path(d) / "bad.db")
        with con:
            add_survey(con, 1)
            add_task(con, 1, 10, "작업")
            con.execute("INSERT INTO analysis_run(run_id,unit_task_id,video_id,model_id,status_cd,is_current_yn,finished_at)"
                        " VALUES (1,10,10,4,'DONE',0,'2026-10-23T10:01:00')")
        pers = []
        for rep in range(3):                      # 커밋 시간은 디스크 동기화에 달려 있어 흔들린다. 세 번 재서 중앙값과 범위를 쓴다
            run = 1 + rep
            if rep:
                with con:
                    con.execute("INSERT INTO analysis_run(run_id,unit_task_id,video_id,model_id,status_cd,is_current_yn,finished_at)"
                                " VALUES (?,10,10,4,'DONE',0,'2026-10-23T10:01:00')", (run,))
            rows = frame_rows(run, 200)
            t0 = time.perf_counter()
            for r in rows:
                with con:
                    con.execute("INSERT INTO frame_angle VALUES (" + ",".join("?" * 20) + ")", r)
            pers.append(ms(t0) / len(rows))
        per = statistics.median(pers)
        out["commit_per_frame_ms"] = round(per, 2)
        out["commit_per_frame_range_ms"] = [round(min(pers), 2), round(max(pers), 2)]
        out["commit_per_frame_900_s"] = round(per * FRAMES / 1000, 1)
        con.close()

        # 4 --------------------------------------------------------------------
        path = Path(d) / "big.db"
        con = open_db(path)
        t0 = time.perf_counter()
        with con:
            for sid in range(1, 101):
                add_survey(con, sid)
                for k in range(1, 6):
                    add_task(con, sid, sid * 10 + k, f"작업 {k}")
        for sid in range(1, 101):
            for k in range(1, 6):
                tid = sid * 10 + k
                start_run(con, tid, 100000 + tid)
                save_analysis(con, tid, 100000 + tid)
        out["build_big_s"] = round(time.perf_counter() - t0, 1)
        con.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        out["big_db_mb"] = round(path.stat().st_size / 1e6, 1)
        out["big_counts"] = {t: con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
                             for t in ("survey", "unit_task", "analysis_run", "frame_angle", "judgment")}
        con.close()
        t = []
        for _ in range(7):                        # 한 번만 재면 백신 검사 같은 잡음이 들어간다. 여러 번 재서 중앙값
            t0 = time.perf_counter()
            c2 = open_db(path)
            t.append(ms(t0))
            c2.close()
        out["open_big_ms"] = round(statistics.median(t), 1)
        out["open_big_max_ms"] = round(max(t), 1)
        con = open_db(path)
        t = []
        for _ in range(20):
            t0 = time.perf_counter()
            con.execute("SELECT * FROM v_survey_list ORDER BY survey_date DESC").fetchall()
            t.append(ms(t0))
        out["list_100_surveys_ms"] = round(statistics.median(t), 2)
        t = []
        for _ in range(50):
            t0 = time.perf_counter()
            con.execute("SELECT * FROM v_judgment_sheet WHERE unit_task_id = 551").fetchall()
            t.append(ms(t0))
        out["judgments_of_one_task_ms"] = round(statistics.median(t), 2)
        t = []
        for i in range(3):                        # 중앙값 (세 번)
            t0 = time.perf_counter()
            bak = sqlite3.connect(Path(d) / f"backup{i}.db")
            con.backup(bak)
            bak.close()
            t.append(time.perf_counter() - t0)
        out["backup_big_s"] = round(statistics.median(t), 2)
        t = []
        for _ in range(3):
            t0 = time.perf_counter()
            ok = con.execute("PRAGMA integrity_check").fetchone()[0]
            t.append(time.perf_counter() - t0)
        out["integrity_check"] = {"result": ok, "s": round(statistics.median(t), 2)}
        t = []
        for _ in range(3):
            t0 = time.perf_counter()
            con.execute("VACUUM")
            t.append(time.perf_counter() - t0)
        out["vacuum_big_s"] = round(statistics.median(t), 2)
        con.close()

        # 5 --------------------------------------------------------------------
        stop = threading.Event()
        read_ms, errors = [], []

        def reader():
            c = open_db(path)                      # 읽기 스레드는 자기 연결을 쓴다
            while not stop.is_set():
                t0 = time.perf_counter()
                try:
                    c.execute("SELECT * FROM v_survey_list ORDER BY survey_date DESC").fetchall()
                    read_ms.append(ms(t0))
                except sqlite3.OperationalError as e:
                    errors.append(f"read: {e}")
            c.close()

        w = open_db(path)
        with w:
            add_survey(w, 999)
            for k in range(1, 41):
                add_task(w, 999, 9000 + k, f"동시 {k}")
        rt = threading.Thread(target=reader)
        rt.start()
        write_ms = []
        for k in range(1, 41):
            try:
                start_run(w, 9000 + k, 500000 + k)
                t0 = time.perf_counter()
                save_analysis(w, 9000 + k, 500000 + k)
                write_ms.append(ms(t0))
            except sqlite3.OperationalError as e:
                errors.append(f"write: {e}")
        stop.set()
        rt.join()
        w.close()
        out["concurrent"] = {
            "writes": len(write_ms), "write_median_ms": round(statistics.median(write_ms), 1), "write_max_ms": round(max(write_ms), 1),
            "reads": len(read_ms), "read_median_ms": round(statistics.median(read_ms), 2), "read_max_ms": round(max(read_ms), 1),
            "errors": errors[:3], "error_count": len(errors)}

    print(json.dumps(out, ensure_ascii=False, indent=1))
    if save:
        with open(HERE / "bench_snapshot.json", "w", encoding="utf-8", newline="\n") as f:
            f.write(json.dumps(out, ensure_ascii=False, indent=1) + "\n")
        print("저장:", HERE / "bench_snapshot.json")


if __name__ == "__main__":
    main()
