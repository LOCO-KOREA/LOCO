"""API 계약서 생성: 템플릿 + contracts.py + 실제 검사 출력 → docs/API_계약서.md

- 계약 코드는 contracts.py를 그대로 넣는다 (문서와 코드가 갈라지지 않게).
- 계약 ↔ ERD 대조는 check_contract.py를 실제로 돌린 출력을 넣는다. 틀리게 바꾼 사본도 돌려 검사가 잡는지 보인다.
- 문서가 인용하는 함수, 오류 코드, 기능정의서·요구사항 ID가 실제로 있는지 확인하고, 없으면 멈춘다.
"""
import datetime, importlib.util, json, re, shutil, sqlite3, subprocess, sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parent))
import paths  # noqa: E402
ERD = HERE.parent / "erd"
MUT = paths.WORK / "api_mut"
DOCS = paths.DOCS
OUT = DOCS / "API_계약서.md"

tpl = (HERE / "api_template.md").read_text(encoding="utf-8")
contracts_src = paths.CONTRACTS_FILE.read_text(encoding="utf-8")

spec = importlib.util.spec_from_file_location("contracts", paths.CONTRACTS_FILE)
C = importlib.util.module_from_spec(spec)
sys.modules["contracts"] = C
spec.loader.exec_module(C)
service_fns = [n for n, v in vars(C.ServiceAPI).items() if callable(v) and not n.startswith("_")]


def section(text, start, end):
    i = text.index(start)
    return text[i:text.index(end, i)]


# ---- 계약 ↔ ERD 대조: 실제 코드와 틀리게 바꾼 사본
def run_check(contracts_file=None):
    cmd = [sys.executable, "-I", str(HERE / "check_contract.py")] + ([str(contracts_file)] if contracts_file else [])
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
    if r.returncode != 0:
        raise SystemExit(f"check_contract 실패 ({contracts_file}):\n{r.stderr}")
    return r.stdout.strip()

real = run_check()
assert real.endswith("mismatches 0"), real

if MUT.exists():
    shutil.rmtree(MUT)
MUT.mkdir()
mut_src = contracts_src
for old, new in (('KNEE_ON_FLOOR = "KNEE_ON_FLOOR"', 'KNEE_ON_FLOOR = "KNEE_FLOOR"'),
                 ("lift_people_cnt: Optional[int] = None", "lift_person_cnt: Optional[int] = None")):
    assert mut_src.count(old) == 1, old
    mut_src = mut_src.replace(old, new)
(MUT / "contracts.py").write_text(mut_src, encoding="utf-8")
mut = run_check(MUT / "contracts.py")
mut_diff = [ln for ln in mut.splitlines() if ln.startswith("DIFF")]
assert len(mut_diff) == 2 and mut.endswith("mismatches 2"), mut
shutil.rmtree(MUT)

# ---- GPT 경고 조언 예시: ERD 시험 데이터로 뷰를 실제로 읽어 만든다
bt_spec = importlib.util.spec_from_file_location("build_and_test", ERD / "build_and_test.py")
bt = importlib.util.module_from_spec(bt_spec)
bt_spec.loader.exec_module(bt)                  # fresh(), sample()를 쓴다
db = bt.fresh()
bt.sample(db)
db.row_factory = sqlite3.Row
row = db.execute("SELECT * FROM v_gpt_payload WHERE warning_id = 1").fetchone()
SENT = ["criterion_no", "criterion_summary", "criterion_legal_text", "daily_work_h",
        "max_share_ratio", "max_exposure_h", "reba_score", "risk_level_cd"]
payload = {"purpose": "WARNING_ADVICE"}
for k in SENT:
    v = row[k]
    payload[k] = round(v, 2) if isinstance(v, float) else v
assert set(row.keys()) - set(SENT) == {"warning_id", "survey_id", "unit_task_id", "survey_task_cnt"}, row.keys()
payload_json = json.dumps(payload, ensure_ascii=False, indent=2)

# ---- 채우기
sec5 = section(tpl, "## 5. 분석 엔진 API", "## 6. GPT API 계약")
engine_fns = sorted(set(re.findall(r"`(\w+)\(", sec5)))
sec8 = section(tpl, "## 8. 오류 코드", "## 9. 주요 시나리오")
err_codes = re.findall(r"^\| ([EWI]-[A-Z]+-\d{3}) \|", sec8, re.M)
assert len(err_codes) == len(set(err_codes)), "오류 코드 중복"
if set(err_codes) != set(C.ERROR_CODES):
    raise SystemExit(f"8절 표와 contracts.ERROR_CODES가 다름: 표에만 {sorted(set(err_codes) - set(C.ERROR_CODES))}, "
                     f"코드에만 {sorted(set(C.ERROR_CODES) - set(err_codes))}")

doc = (tpl.replace("{{N_FUNC}}", str(len(service_fns)))
          .replace("{{N_ENGINE}}", str(len(engine_fns)))
          .replace("{{N_ERR}}", str(len(err_codes)))
          .replace("{{PAYLOAD_EXAMPLE}}", payload_json)
          .replace("{{CHECK_DATE}}", datetime.date.today().isoformat())
          .replace("{{CONTRACT_CHECK}}", real)
          .replace("{{CONTRACT_CHECK_MUT}}", "\n".join(
              mut_diff + [f"(OK 줄 {len(mut.splitlines()) - len(mut_diff) - 1}개 생략)", mut.splitlines()[-1]]))
          .replace("{{CONTRACTS}}", contracts_src.rstrip()))
left = re.findall(r"\{\{[A-Z_]+\}\}", doc)
assert not left, left

# ---- 인용 확인
body = doc[:doc.index("## 부록 A.")]
problems = []

sec4 = section(doc, "## 4. 서비스 API", "## 5. 분석 엔진 API")
named = set(re.findall(r"`(\w+)\(", sec4))
problems += [f"4절 함수 {n}가 contracts.ServiceAPI에 없음" for n in sorted(named - set(service_fns))]
problems += [f"contracts.ServiceAPI.{n}가 4절에 없음" for n in service_fns if n not in named]

used_codes = set(re.findall(r"\b([EWI]-[A-Z]+-\d{3})\b", body))
problems += [f"오류 코드 {c}가 8절 표에 없음" for c in sorted(used_codes - set(err_codes))]

fd = (DOCS / "기능정의서.md").read_text(encoding="utf-8")
req = (DOCS / "requirements.md").read_text(encoding="utf-8")
for ref in sorted(set(re.findall(r"\b((?:F0\d-0\d)|(?:AC|EX|BR|TP|OI)-\d{2})\b", body))):
    if ref not in fd:
        problems.append(f"{ref}가 기능정의서에 없음")
for ref in sorted(set(re.findall(r"\b((?:NFR|FR)-\d{3})\b", body))):
    if ref not in req:
        problems.append(f"{ref}가 requirements.md에 없음")
for s in sorted(set(re.findall(r"\bS0\d\b", body))):
    if s not in fd:
        problems.append(f"화면 {s}가 기능정의서에 없음")

erd_doc = (DOCS / "ERD_데이터설계서.md").read_text(encoding="utf-8")
for v in sorted(set(re.findall(r"\b(v_[a-z_]+)\b", body))):
    if f"CREATE VIEW {v} " not in erd_doc:
        problems.append(f"뷰 {v}가 ERD에 없음")

if problems:
    print("\n".join(problems))
    raise SystemExit(f"인용 문제 {len(problems)}개")

paths.write_text(OUT, doc)
print("service", len(service_fns), "| engine", len(engine_fns), engine_fns, "| errors", len(err_codes))
print("contract check:", real.splitlines()[-1])
print("mutation check:", mut.splitlines()[-1], "|", " / ".join(mut_diff))
print("refs OK →", OUT, len(doc), "chars")
