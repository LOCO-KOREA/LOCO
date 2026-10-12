"""기능정의서의 수용 기준(AC) 중 아직 시험이 없는 것의 뼈대. 구현한 사람이 skip을 지우고 채운다.

이미 시험이 있는 AC는 tests/contract_suite.py (스텁도 통과하는 계약 시험)에 있다:
    AC-01, AC-02, AC-04, AC-05, AC-06, AC-09, AC-10, AC-20, AC-22, AC-23, AC-26, AC-27, AC-28, AC-33, AC-34, AC-35, AC-37

docs_src/make_acceptance_tests.py가 처음 한 번 만들었다. 이 파일은 사람이 고친다 (다시 만들지 않는다).
"""
import unittest


class AcceptanceTodo(unittest.TestCase):
    @unittest.skip("WP0 · F01-03 · 아직 구현 전")
    def test_AC03_f01_03(self):
        """AC-03: 2026-10-30에 확정한 정기조사 → 다음 정기조사 예정일 2029-10-30"""
        self.fail('구현하고 skip을 지운다')

    @unittest.skip("WP1 · F03-01 · 아직 구현 전")
    def test_AC07_f03_01(self):
        """AC-07: 회전 정보(EXIF)가 있는 폰 사진(JPG·PNG)이 똑바로 세워져 분석된다."""
        self.fail('구현하고 skip을 지운다')

    @unittest.skip("WP1 · F03-02 · 아직 구현 전")
    def test_AC08_f03_02(self):
        """AC-08: 사진 올리기 화면에 안내 4줄이 보인다."""
        self.fail('구현하고 skip을 지운다')

    @unittest.skip("WP1 · F04-01 · 아직 구현 전")
    def test_AC11_f04_01(self):
        """AC-11: MoveNet Lightning으로 사진 한 장을 돌려 관절 17개와 신뢰도가 나온다."""
        self.fail('구현하고 skip을 지운다')

    @unittest.skip("WP1 · F04-02 · 아직 구현 전")
    def test_AC12_f04_02(self):
        """AC-12: 결과 화면과 엑셀 어디에도 얼굴이 보이지 않는다 (시험: 사진 150장 모두 가림, 한 장당 20ms)."""
        self.fail('구현하고 skip을 지운다')

    @unittest.skip("WP1 · F04-03 · 아직 구현 전")
    def test_AC13_f04_03(self):
        """AC-13: 각도기로 잰 재연 사진과 비교해 각도별 평균 오차를 낸다. 목표치는 10/17 기술 검토에서 정한다 (NFR-015)."""
        self.fail('구현하고 skip을 지운다')

    @unittest.skip("WP1 · F04-04 · 아직 구현 전")
    def test_AC14_f04_04(self):
        """AC-14: 허리를 25° 굽힌 사진은 4호 허리 굽힘으로 세고, 15°는 세지 않는다."""
        self.fail('구현하고 skip을 지운다')

    @unittest.skip("WP1 · F04-04 · 아직 구현 전")
    def test_AC15_f04_04(self):
        """AC-15: 무릎을 바닥에 댄 채 허리를 30° 굽힌 사진은 허리 굽힘으로 세지 않는다."""
        self.fail('구현하고 skip을 지운다')

    @unittest.skip("WP1 · F04-05 · 아직 구현 전")
    def test_AC16_f04_05(self):
        """AC-16: 판별 가능한 사진 20장 중 허리 굽힘 7장 = 35%, 하루 작업시간 6시간 → 하루 노출 2.10시간"""
        self.fail('구현하고 skip을 지운다')

    @unittest.skip("WP1 · F04-05 · 아직 구현 전")
    def test_AC17_f04_05(self):
        """AC-17: 사진 20장 중 3호 a만 4장, b만 2장, a와 b 동시 2장 → 3호 8장 = 40%. 동시는 한 번만 센다."""
        self.fail('구현하고 skip을 지운다')

    @unittest.skip("WP1 · F04-06 · 아직 구현 전")
    def test_AC18_f04_06(self):
        """AC-18: KOSHA 지침의 '휠 들어올리기' 예시를 워크시트로 손 계산한 8점과 같다 (계산기로 확인함)."""
        self.fail('구현하고 skip을 지운다')

    @unittest.skip("WP1 · F04-06 · 아직 구현 전")
    def test_AC19_f04_06(self):
        """AC-19: 손목을 입력하기 전에는 손목 칸이 '사람 확인'이고, 입력하면 표시가 바뀐다."""
        self.fail('구현하고 skip을 지운다')

    @unittest.skip("WP3 · F05-01 · 아직 구현 전")
    def test_AC21_f05_01(self):
        """AC-21: 지침 부록 1의 판단 예시 11개와 결과가 같다 (판정 엔진으로 확인함)."""
        self.fail('구현하고 skip을 지운다')

    @unittest.skip("WP2 · F05-02 · 아직 구현 전")
    def test_AC24_f05_02(self):
        """AC-24: 허리 각도가 20° 근처에 몰린 사진 표본에서 −5°로는 비해당, +5°로는 해당이 되면 4호가 '사람 확인'으로 나온다."""
        self.fail('구현하고 skip을 지운다')

    @unittest.skip("WP2 · F05-03 · 아직 구현 전")
    def test_AC25_f05_03(self):
        """AC-25: 허리 굽힘 35% × 하루 6시간이면 "부담작업 4호 기준(하루 총 2시간)을 넘습니다"가 뜬다. 인터넷을 끊어도 뜬다."""
        self.fail('구현하고 skip을 지운다')

    @unittest.skip("WP3 · F06-01 · 아직 구현 전")
    def test_AC29_f06_01(self):
        """AC-29: 엑셀에서 열리고 시트가 4개다. 확정되지 않은 칸에 "초안"이 있고, 이미지에 얼굴이 없다."""
        self.fail('구현하고 skip을 지운다')

    @unittest.skip("WP2 · F06-02 · 아직 구현 전")
    def test_AC30_f06_02(self):
        """AC-30: 보낸 요청 기록에 사진과 이름이 없다."""
        self.fail('구현하고 skip을 지운다')

    @unittest.skip("WP2 · F06-02 · 아직 구현 전")
    def test_AC31_f06_02(self):
        """AC-31: 받은 문장에 보내지 않은 숫자가 있으면 기본 문구가 나온다."""
        self.fail('구현하고 skip을 지운다')

    @unittest.skip("WP2 · F06-03 · 아직 구현 전")
    def test_AC32_f06_03(self):
        """AC-32: 인터넷을 끊고 분석부터 엑셀 저장까지 할 수 있다."""
        self.fail('구현하고 skip을 지운다')

    @unittest.skip("MVP 이후 · F07-04 · 모델이 확정되어(D-MODEL-01) MVP에서는 만들지 않는다")
    def test_AC36_f07_04(self):
        """AC-36: 후보별 각도 오차, 분석 시간, 설치 크기 표가 나온다."""
        self.fail('구현하고 skip을 지운다')


if __name__ == "__main__":
    unittest.main()
