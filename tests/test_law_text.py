"""법 원문 시험: DB에 넣은 11개 기준 문구가 고시 원문 그대로인가.

원문 사본: tests/fixtures/고시_제2020-12호_본문.txt
    고용노동부고시 제2020-12호 (시행 2020.1.16), 국가법령정보센터 현행 본문, 2026-10-12 확인.
이 시험이 지키는 것
    1. DB의 criterion.legal_text가 원문 제3조 11개 호와 공백만 합쳐서 똑같다.
    2. 원문 사본 자체가 말없이 고쳐지지 않았다 (SHA-256).
    3. 이 비교가 실제로 다른 점을 잡는다 (일부러 고친 문구를 걸러 내는지).
고시가 개정되면: 국가법령정보센터에서 새 본문을 확인해 사본과 해시, 시드를 함께 고치고 문서를 다시 만든다.
"""
import hashlib
import re
import unittest
from pathlib import Path

from ergo.db import open_db

FIXTURE = Path(__file__).parent / "fixtures" / "고시_제2020-12호_본문.txt"
BODY_SHA256 = "9bddf9611101878843de8679a1f926d934e2f9397d36843e1255ef773a649004"   # 공백을 합친 본문. 브라우저에서 계산한 값과 같음


def norm(s: str) -> str:
    return " ".join(s.split())


def body() -> str:
    return FIXTURE.read_text(encoding="utf-8").split("=== 본문 ===\n", 1)[1]


def law_items() -> dict[int, str]:
    text = body()
    sec = text[text.index("제3조(근골격계부담작업)"):text.index("제4조(유해요인조사 방법)")]
    return {int(n): norm(t) for n, t in re.findall(r"^([0-9]+)\. (.+)$", sec, re.M)}


def differing_items(ours: dict[int, str], law: dict[int, str]) -> list[int]:
    return sorted(n for n in set(ours) | set(law) if norm(ours.get(n, "")) != norm(law.get(n, "")))


class LawText(unittest.TestCase):
    def test_fixture_was_not_edited(self):
        got = hashlib.sha256(norm(body()).encode("utf-8")).hexdigest()
        self.assertEqual(got, BODY_SHA256, "원문 사본이 바뀌었다. 국가법령정보센터에서 다시 확인하고 해시를 갱신하세요")

    def test_law_has_eleven_items(self):
        self.assertEqual(sorted(law_items()), list(range(1, 12)))

    def test_db_criteria_are_the_law_text(self):
        con = open_db()
        try:
            ours = {n: t for n, t in con.execute("SELECT criterion_no, legal_text FROM criterion")}
        finally:
            con.close()
        self.assertEqual(differing_items(ours, law_items()), [], "DB의 기준 문구가 고시 원문과 다르다")

    def test_the_comparison_catches_a_changed_word(self):
        law = law_items()
        mutated = dict(law)
        mutated[4] = mutated[4].replace("2시간", "3시간")
        self.assertEqual(differing_items(mutated, law), [4])
        mutated = dict(law)
        mutated[3] = mutated[3].replace("어깨위에", "어깨 위에")          # 띄어쓰기만 달라도 잡아야 한다 (원문 그대로 쓴다)
        self.assertEqual(differing_items(mutated, law), [3])

    def test_definitions_used_by_the_app_are_in_the_law(self):
        text = norm(body())
        for needle in ("2개월 이내에 종료되는 1회성 작업", "연간 총 작업일수가 60일을 초과하지 않는 작업",
                       "1일 소정근로시간과 1일 연장근로시간", "실제로 수행한 시간을 합산한 시간",
                       "작업분석·평가도구를 활용할 수 있다"):
            self.assertIn(needle, text)


if __name__ == "__main__":
    unittest.main()
