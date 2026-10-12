"""수용 기준(AC) 시험의 뼈대를 만든다. tests/test_acceptance.py가 이미 있으면 덮어쓰지 않는다
(사람이 채운 것을 지우지 않기 위해).

- 기능정의서의 'AC-NN: 문장'을 읽는다.
- tests/contract_suite.py에 이름에 ACNN이 있는 시험이 있으면 '이미 시험이 있다'로 센다.
- 나머지는 건너뛰는 시험(skip)으로 만든다. 구현한 사람이 skip을 지우고 채운다.
- 담당(WP)은 일정서의 기능별 표에서 읽는다.
"""
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import paths  # noqa: E402

OUT = paths.PROJECT / "tests" / "test_acceptance.py"
if OUT.exists():
    print("이미 있음 — 덮어쓰지 않음:", OUT)
    raise SystemExit(0)

fd = (paths.DOCS / "기능정의서.md").read_text(encoding="utf-8")
sched = (paths.DOCS / "일정서.md").read_text(encoding="utf-8")
suite = (paths.PROJECT / "tests" / "contract_suite.py").read_text(encoding="utf-8")
covered = {int(n) for n in re.findall(r"def test_AC([0-9]{2})", suite)}
owner = {fid: wp for fid, wp in re.findall(r"^\| (F0[0-9]-0[0-9]) \| [^|]+ \| (?:Must|Should) \| (WP[0-9]) \|", sched, re.M)}

items = []                                   # (AC 번호, 기능 ID, 문장)
for m in re.finditer(r"^#### (F0[0-9]-0[0-9]) [^\n]*\n(.*?)(?=^#{2,4} )", fd, re.M | re.S):
    for n, text in re.findall(r"^\s+- AC-([0-9]{2}): (.+)$", m.group(2), re.M):
        items.append((int(n), m.group(1), text.strip()))
items.sort()
todo = [i for i in items if i[0] not in covered]

lines = [
    '"""기능정의서의 수용 기준(AC) 중 아직 시험이 없는 것의 뼈대. 구현한 사람이 skip을 지우고 채운다.',
    "",
    "이미 시험이 있는 AC는 tests/contract_suite.py (스텁도 통과하는 계약 시험)에 있다:",
    "    " + ", ".join(f"AC-{n:02d}" for n in sorted(covered)),
    "",
    "docs_src/make_acceptance_tests.py가 처음 한 번 만들었다. 이 파일은 사람이 고친다 (다시 만들지 않는다).",
    '"""',
    "import unittest",
    "",
    "",
    "class AcceptanceTodo(unittest.TestCase):",
]
for n, fid, text in todo:
    wp = owner.get(fid, "?")
    esc = text.replace("\\", "\\\\").replace('"""', '\\"\\"\\"')
    lines += [f'    @unittest.skip("{wp} · {fid} · 아직 구현 전")',
              f"    def test_AC{n:02d}_{fid.replace('-', '_').lower()}(self):",
              f'        """AC-{n:02d}: {esc}"""',
              "        self.fail('구현하고 skip을 지운다')", ""]
with open(OUT, "w", encoding="utf-8", newline="\n") as f:
    f.write("\n".join(lines).rstrip("\n") + "\n\n\nif __name__ == \"__main__\":\n    unittest.main()\n")
print(f"AC {len(items)}개 중 시험이 있는 것 {len(covered & {i[0] for i in items})}개, 뼈대 {len(todo)}개 → {OUT}")
