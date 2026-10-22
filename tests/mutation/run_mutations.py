"""Check that rule, ownership, and GPT-boundary tests detect injected defects.

Run with the project's Python environment: python tests/mutation/run_mutations.py
Each mutation runs in a disposable copy; the checkout is never modified.
"""
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
PROJECT = Path(__file__).resolve().parents[2]
IGNORE = shutil.ignore_patterns(
    ".git", ".venv", ".local", "node_modules", "__pycache__", "*.pyc", "*.tflite", ".pytest_cache",
    "docs", "samples", "dist", "build",
)
TESTS = [
    "tests.test_v2_rules", "tests.test_v2_service", "tests.test_v2_gpt",
    "tests.test_v2_reba", "tests.test_json_lines_integration",
    "tests.test_persistence_regressions", "tests.test_adaptive_intake",
]
MUTATIONS = [('9호 미확인 중량을 적격 행으로 취급',
  'ergo/engine/burden_rules.py',
  'for rid in eligible_ids for state in row_location_states[rid].values()',
  'for rid in eligible_ids | unknown_ids for state in row_location_states[rid].values()',
  'test_c9_unknown_mass_cannot_be_promoted_by_a_position_count',
  'tests.test_persistence_regressions.RuleRegressions'),
 ('하루 시간보다 긴 합집합 허용',
  'ergo/engine/burden_rules.py',
  'if n != 8 and _number(union_value) and _number(total_work) and union_value>total_work:',
  'if False:',
  'test_all_time_unions_are_bounded_by_the_daily_work_duration',
  'tests.test_persistence_regressions.RuleRegressions'),
 ('계산 저장을 오래된 전체 결과 덮어쓰기로 변경',
  'ergo/service/analysis_records.py',
  "ctx.store('update_analysis_result', a['analysis_id'], update, job=(a['status'], a['finished_at']))",
  "ctx.store('update_analysis_result', a['analysis_id'], lambda latest: (latest.clear(), "
  'latest.update({key:a[key] for key in '
  "('module_states','pose','slot_tags','tags','reba','judgment','ai','notes')})), "
  "job=(a['status'],a['finished_at']))",
  'test_ai_edits_and_activation_survive_a_calculation_write',
  'tests.test_persistence_regressions.PersistenceRegressions'),
 ('분석 설정 변경 revision 무효화 제거',
  'ergo/service/settings.py',
  'if relevant:',
  'if False:',
  'test_related_analysis_settings_increment_once_and_ui_settings_do_not',
  'tests.test_persistence_regressions.PersistenceRegressions'),
 ('출력의 단일 SQLite 읽기 snapshot 제거',
  'ergo/service/reports.py',
  'with ctx.db_lock, storage.read_snapshot(ctx.db_path):',
  'with ctx.db_lock:',
  'test_export_uses_one_read_only_sqlite_transaction_for_all_rows',
  'tests.test_persistence_regressions.PersistenceRegressions'),
 ('기준 경계: 1호 240분을 241분으로 변경',
  'ergo/engine/burden_rules.py',
  "state=duration('C1_KEYBOARD_FOCUSED', 240)",
  "state=duration('C1_KEYBOARD_FOCUSED', 241)",
  'test_threshold_boundary_values_for_all_eleven_criteria',
  'tests.test_v2_rules.ThresholdBoundaries'),
 ('사진 소유권 검사 반전',
  'ergo/service/task_inputs.py',
  'photo_id not in photos',
  'photo_id in photos',
  'test_photo_from_another_task_cannot_be_attached',
  'tests.test_v2_service.AppCase'),
 ('GPT 기준 근거를 다른 호에 연결 허용',
  'ergo/gpt/payload.py',
  "if any(not isinstance(ref,str) or ref not in basis_by_criterion[item['criterion_no']] for ref in "
  "item['basis_refs']): return False",
  "if any(not isinstance(ref,str) for ref in item['basis_refs']): return False",
  'test_structured_content_must_reference_its_own_criterion',
  'tests.test_v2_gpt.GptBoundary'),
 ('앉은 작업의 불필요한 무릎 범주 입력을 다시 강제',
  'ergo/engine/reba_scoring.py',
  'if field in irrelevant: continue',
  "if field in irrelevant and field!='knee_band': continue",
  'test_seated_case_and_confirmed_or_do_not_require_irrelevant_unknowns',
  'tests.test_v2_reba.RebaBoundary'),
 ('9호 합계의 대상 행 누락 방어 제거',
  'ergo/engine/burden_rules.py',
  'elif (totals_location_positive or totals_combination) and not totals_supported:',
  'elif False:',
  'test_c9_totals_cannot_assert_counts_without_selected_qualifying_rows',
  'tests.test_v2_rules.GeneralCriteria')]


MUTATIONS += [
 ('AI가 직접 수정값을 덮어쓰게 변경', 'ergo/intake/facts.py',
  "if previous and previous['source']=='USER':", "if False:",
  'test_zero_is_a_real_value_and_user_edit_wins_over_ai', 'tests.test_adaptive_intake.AdaptiveIntake'),
 ('AI 숫자의 단위·근거 검사 제거', 'ergo/intake/facts.py',
  "if field['kind']=='number' and not number_grounded(value,quote,field['unit'],bare=bool(focused) and current_quote):", "if False:",
  'test_wrong_unit_and_fabricated_number_are_dropped', 'tests.test_adaptive_intake.AdaptiveIntake'),
 ('서로 다른 중량 조건을 같은 행으로 합침', 'ergo/intake/facts.py',
  "identity = key(field['target'],condition)", "condition='default'; identity = key(field['target'],condition)",
  'test_different_conditions_keep_their_own_weight_and_count', 'tests.test_adaptive_intake.AdaptiveIntake'),
]


def run(cwd, modules):
    command = [sys.executable, "-m", "unittest", *modules]
    result = subprocess.run(
        command, cwd=cwd, capture_output=True, text=True,
        encoding="utf-8", errors="replace", timeout=180,
    )
    output = result.stderr + result.stdout
    failed = re.findall(r"^(?:FAIL|ERROR): (\S+) \(([^)]+)\)", output, re.M)
    summary = [line for line in output.splitlines() if line.startswith(("Ran ", "OK", "FAILED"))]
    return result.returncode, failed, summary, output


def copy_project(destination):
    shutil.copytree(PROJECT, destination, ignore=IGNORE)


def main():
    passed = True
    with tempfile.TemporaryDirectory(prefix="loco_mutation_") as temporary:
        base = Path(temporary)
        for index, (label, relative, before, after, expected, module) in enumerate(MUTATIONS):
            work = base / f"mutation_{index}"
            copy_project(work)
            path = work / relative
            source = path.read_text(encoding="utf-8")
            if source.count(before) != 1:
                print(f"변이 설정 오류: {label} — 대상 문구가 {source.count(before)}개입니다")
                passed = False
                continue
            path.write_text(source.replace(before, after), encoding="utf-8", newline="\n")
            code, failed, summary, output = run(work, [module])
            names = [name for name, _ in failed]
            detected = code != 0 and any(expected in name for name in names)
            passed &= detected
            print(f"{'탐지' if detected else '미탐지'}: {label}; {summary[-1] if summary else '요약 없음'}")
            if not detected:
                print(output[-1600:])

        control = base / "control"
        copy_project(control)
        code, failed, summary, output = run(control, TESTS)
        clean = code == 0 and not failed
        passed &= clean
        print(f"대조군: {summary[-1] if summary else '요약 없음'}")
        if not clean:
            print(output[-1600:])
    print("변이 검증:", "모두 통과" if passed else "미통과")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
