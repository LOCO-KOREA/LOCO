"""문서와 그림을 처음부터 끝까지 다시 만든다 (순서가 있다: 앞 문서를 뒤 문서가 읽는다).

    python docs_src/build_all.py

하나라도 실패하면 거기서 멈추고 그 단계의 출력을 보여 준다. 마지막 줄만 보면 된다.
"""
import subprocess
import sys
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
SRC = Path(__file__).resolve().parent
STEPS = [
    ("DB 시험 (ERD 9절)", "erd/build_and_test.py"),
    ("ERD 그림 (draw.io + PNG)", "erd/gen_erd_drawio.py"),
    ("ERD 설계서", "erd/gen_doc.py"),
    ("DB 아키텍처 설계서", "dba/gen_dba_doc.py"),
    ("API 계약서", "api/gen_api_doc.py"),
    ("화면설계서", "ui/gen_ui.py"),
    ("화면 참고 이미지 2장", "ui/gen_ref_images.py"),
    ("일정서", "sched/gen_schedule.py"),
    ("팀원 읽기 안내", "team/gen_team_guide.py"),
]
t_all = time.time()
for name, script in STEPS:
    t0 = time.time()
    r = subprocess.run([sys.executable, str(SRC / script)], capture_output=True, text=True, encoding="utf-8", errors="replace")
    lines = [ln for ln in r.stdout.splitlines() if ln.strip()]
    if r.returncode != 0:
        print(f"[실패] {name} ({script})")
        print("\n".join(lines[-30:]))
        print(r.stderr[-2000:])
        sys.exit(1)
    print(f"[{time.time() - t0:5.1f}s] {name}: {lines[-1] if lines else ''}")
print(f"전체 {time.time() - t_all:.0f}초. 모두 통과")
