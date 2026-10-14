"""가드가 '있다'가 아니라 '잡는다'를 증명한다: 프로젝트 사본에 일부러 망가뜨린 것을 넣고 시험이 실패하는지 본다.

    python tests/mutation/run_mutations.py     (시험은 python -m unittest discover -s tests -t . 로 돈다)


원본 프로젝트는 건드리지 않는다. 사본을 임시 폴더에 만들어 거기서만 바꾼다.
각 변이마다: (바꾼 파일, 바꾸기 전 문구, 바꾼 문구, 실패해야 하는 시험 이름 조각)
"""
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
PROJ = Path(__file__).resolve().parents[2]

MUTS = [
    ("M01 4호 문구의 '2시간'을 '3시간'으로", "ergo/db/seed_v1.sql",
     "하루에 총 2시간 이상 목이나 허리를", "하루에 총 3시간 이상 목이나 허리를", "test_db_criteria_are_the_law_text"),
    ("M02 3호 '어깨위에'에 띄어쓰기를 되돌림", "ergo/db/seed_v1.sql",
     "팔꿈치가 어깨위에 있거나", "팔꿈치가 어깨 위에 있거나", "test_db_criteria_are_the_law_text"),
    ("M03 원문 사본의 정의 한 줄을 고침", "tests/fixtures/고시_제2020-12호_본문.txt",
     "2개월 이내에 종료되는 1회성 작업을 말한다", "3개월 이내에 종료되는 1회성 작업을 말한다", "test_fixture_was_not_edited"),
    ("M04 '사람 확인'을 사유 없이 확정 가능하게", "ergo/service/stub.py",
     '_need((same and j["status"] != C.JudgmentStatus.NEEDS_REVIEW) or had_reason, "E-CONFIRM-002", "확정하는 이유를 입력해 주세요.")',
     '_need(True, "E-CONFIRM-002", "확정하는 이유를 입력해 주세요.")', "test_AC27_review_needs_a_reason"),
    ("M05 '입력 필요'를 확정 가능하게", "ergo/service/stub.py",
     '_need(j["status"] != C.JudgmentStatus.NEEDS_INPUT, "E-CONFIRM-001", "입력이 필요한 기준이 있어 확정할 수 없습니다.")',
     '_need(True, "E-CONFIRM-001", "입력이 필요한 기준이 있어 확정할 수 없습니다.")', "test_AC27_cannot_confirm_when_input_is_missing"),
    ("M06 각도 기준을 바꿔도 이력을 남기지 않음", "ergo/service/stub.py",
     '            self._entry(survey_id, None, "THRESHOLD", threshold_cd.value, "CHANGE", old, value_deg, reason.strip(), actor)\n',
     "", "test_AC34_threshold_change_needs_a_reason"),
    ("M07 GPT를 끄면 저장된 문장을 지움", "ergo/service/stub.py",
     '            if w["ai"] is None:\n                ai_id = next(self._id["ai"])',
     '            if w["ai"] is None or not self._settings["gpt_enabled"]:\n                ai_id = next(self._id["ai"])',
     "test_stored_ai_sentence_stays_when_gpt_is_turned_off"),
    ("M08 GPT 전송 뷰에 단위작업 이름 열을 추가", "ergo/db/schema_v1.sql",
     "SELECT w.warning_id, t.survey_id, w.unit_task_id,\n",
     "SELECT w.warning_id, t.survey_id, w.unit_task_id, t.task_name AS task_name,\n", "test_every_view_column_is_classified"),
    ("M09 계약의 코드 값 하나를 바꿈", "ergo/contracts.py",
     'NEEDS_REVIEW = "NEEDS_REVIEW"', 'NEEDS_REVIEW = "NEEDS_CHECK"', "test_enums_and_dtos_match_the_database"),
    ("M10 대표 사진이 그 분석에 쓰지 않은 사진이어도 저장되게", "ergo/db/schema_v1.sql",
     "  FOREIGN KEY (run_id, key_still_id) REFERENCES still_angle(run_id, still_id),   -- 대표 사진은 그 분석에 쓴 사진\n",
     "", "test_every_case_behaves_as_expected"),
    ("M11 연결할 때 외래키를 켜지 않음", "ergo/db/connection.py",
     '    con.execute("PRAGMA foreign_keys = ON")\n', "", "test_in_memory_has_schema_seed_and_foreign_keys"),
    ("M12 SQLite 최소 버전 확인을 지움", "ergo/db/connection.py",
     "    if sqlite3.sqlite_version_info < MIN_SQLITE:\n", "    if False:\n", "test_old_sqlite_is_refused_with_a_clear_message"),
    ("M13 GPT로 나가는 열에 단위작업 이름을 추가", "ergo/gpt/payload.py",
     '    "criterion_no",\n    "criterion_summary",', '    "criterion_no",\n    "task_name",\n    "criterion_summary",',
     "test_every_view_column_is_classified"),
    ("M14 스텁이 계약에 없는 오류 코드를 던짐", "ergo/service/stub.py",
     '"E-CONFIRM-001", "입력이 필요한 기준이 있어 확정할 수 없습니다.")', '"E-CONFIRM-999", "입력이 필요한 기준이 있어 확정할 수 없습니다.")',
     "test_AC27_cannot_confirm_when_input_is_missing"),
    ("M15 계약의 오류 코드 목록에서 하나를 뺌", "ergo/contracts.py",
     '"E-EXPORT-001", "E-DB-001", "E-DB-002", "W-GPT-001",', '"E-EXPORT-001", "E-DB-001", "W-GPT-001",',
     "test_contract_codes_match_the_error_table_in_the_api_template"),
]


def run(cwd):
    r = subprocess.run([sys.executable, "-m", "unittest", "discover", "-s", "tests", "-t", "."],
                       cwd=cwd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=300)
    out = r.stderr
    failed = re.findall(r"^(?:FAIL|ERROR): (\S+) \(([^)]+)\)", out, re.M)
    summary = [ln for ln in out.splitlines() if ln.startswith(("Ran ", "OK", "FAILED"))]
    return failed, summary, out


def main():
    ok_all = True
    base = Path(tempfile.mkdtemp(prefix="ergo_mut_"))
    try:
        for label, rel, old, new, expect in MUTS:
            work = base / "p"
            if work.exists():
                shutil.rmtree(work)
            shutil.copytree(PROJ, work, ignore=shutil.ignore_patterns(".work", ".git", "docs", "__pycache__", "*.pyc"))
            f = work / rel
            text = f.read_text(encoding="utf-8")
            n = text.count(old)
            if n != 1:
                print(f"[변이 실패] {label}: 바꿀 문구가 {n}개 — {rel}")
                ok_all = False
                continue
            with open(f, "w", encoding="utf-8", newline="\n") as fh:
                fh.write(text.replace(old, new))
            failed, summary, out = run(work)
            names = [n for n, _ in failed]
            hit = any(expect in n for n in names)
            ok_all &= hit
            mark = "잡음" if hit else "못 잡음 !!"
            print(f"{mark}  {label}")
            print(f"       실패한 시험 {len(failed)}개: {', '.join(sorted(set(names)))[:200]}  ({summary[-1] if summary else '?'})")
            if not hit:
                print(out[-1500:])
        # 대조군: 망가뜨리지 않은 사본은 통과해야 한다
        work = base / "p"
        if work.exists():
            shutil.rmtree(work)
        shutil.copytree(PROJ, work, ignore=shutil.ignore_patterns(".work", ".git", "docs", "__pycache__", "*.pyc"))
        failed, summary, out = run(work)
        print(f"대조군 (손대지 않은 사본): {summary[-1] if summary else '?'}")
        ok_all &= not failed
    finally:
        shutil.rmtree(base, ignore_errors=True)
    print("결과:", "변이를 모두 잡음" if ok_all else "못 잡은 것이 있음")
    return 0 if ok_all else 1


if __name__ == "__main__":
    sys.exit(main())
