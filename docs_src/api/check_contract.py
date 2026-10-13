import dataclasses, importlib.util, re, sqlite3, sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parent))
import paths  # noqa: E402
CONTRACTS = Path(sys.argv[1]) if len(sys.argv) > 1 else paths.CONTRACTS_FILE   # 틀리게 바꾼 사본으로도 돌릴 수 있게
spec = importlib.util.spec_from_file_location("contracts", CONTRACTS)
C = importlib.util.module_from_spec(spec)
sys.modules["contracts"] = C
spec.loader.exec_module(C)
schema = paths.SCHEMA_FILE.read_text(encoding="utf-8")

def block(table):
    m = re.search(rf"CREATE TABLE {table} \((.*?)\n\)\s*STRICT", schema, re.S)
    return m.group(1)

def check_list(table, col):
    b = block(table)
    m = re.search(rf"CHECK \({col} IN\s*\((.*?)\)\)", b, re.S)
    return {v.strip().strip("'") for v in m.group(1).replace("\n", " ").split(",")}

enum_map = {
    "SurveyType": ("survey", "survey_type_cd"), "OccasionalReason": ("survey_reason", "reason_cd"),
    "SurveyStatus": ("survey", "status_cd"), "ParticipantType": ("participant", "participant_type_cd"),
    "PeriodType": ("unit_task", "period_type_cd"), "BodyPart": ("repetition_input", "body_part_cd"),
    "LiftPosition": ("lift_position_input", "position_cd"), "Coupling": ("reba_input", "coupling_cd"),
    "WristFlex": ("reba_input", "wrist_flex_cd"), "LegsSupport": ("reba_input", "legs_support_cd"),
    "ThresholdCode": ("threshold_default", "threshold_cd"), "RunStatus": ("analysis_run", "status_cd"),
    "RiskLevel": ("reba_result", "risk_level_cd"), "JudgmentStatus": ("judgment", "computed_status_cd"),
    "FinalStatus": ("judgment", "final_status_cd"), "ReviewReason": ("judgment", "review_reason_cd"),
    "Exclusion": ("judgment", "exclusion_cd"), "ThresholdSource": ("judgment_basis", "threshold_source_cd"),
    "AiPurpose": ("ai_text", "purpose_cd"), "AiResult": ("ai_text", "result_cd"),
}
bad = 0
for e, (t, col) in enum_map.items():
    ev = {m.value for m in getattr(C, e)}
    dv = check_list(t, col)
    same = ev == dv
    bad += not same
    print(("OK  " if same else "DIFF"), f"{e} ↔ {t}.{col}", "" if same else f"enum-only {ev - dv} db-only {dv - ev}")

db = sqlite3.connect(":memory:")
db.executescript(schema)
def cols(name):
    return {r[1] for r in db.execute(f"PRAGMA table_xinfo({name})")}

field_map = {
    "TaskInputs": ("task_input", set()), "RebaInputs": ("reba_input", set()),
    "RebaScore": ("reba_result", {"needs_review_items"}), "StillInfo": ("still", {"notices"}),
    "Threshold": ("v_effective_threshold", set()), "SurveySummary": ("v_survey_list", set()),
    "EditLogEntry": ("v_edit_log", set()), "UnitTask": ("unit_task", set()),
    "Participant": ("participant", set()), "JudgmentBasis": ("judgment_basis", set()),
    "PoseModel": ("pose_model", set()),
}
for dto, (src, extra) in field_map.items():
    f = {x.name for x in dataclasses.fields(getattr(C, dto))}
    unknown = f - cols(src) - extra
    bad += bool(unknown)
    print(("OK  " if not unknown else "DIFF"), f"{dto} 필드 ⊆ {src} 컬럼", "" if not unknown else f"없는 컬럼 {unknown}")

methods = [n for n, v in vars(C.ServiceAPI).items() if callable(v) and not n.startswith("_")]
print("contract version", C.CONTRACT_VERSION, "| service functions", len(methods), "| enums", len(enum_map), "| mismatches", bad)
