"""분석 엔진 (API 계약서 5절). DB와 화면을 모르는 순수 함수만 둔다.

모듈과 담당 (일정서 4절, 이름은 10/14에 확정)
    pose.py      WP1  관절 추출, 얼굴 가림             F04-01, F04-02
    angles.py    WP1  관절 각도                         F04-03
    postures.py  WP1  법 문구 자세 판별, 비율          F04-04, F04-05
    reba.py      WP1  REBA, 대표 장면                   F04-06, F04-07
    judge.py     WP3  11개 호 판정 초안                 F05-01 (확신도 F05-02는 WP2)

아직 모두 자리만 있다 (NotImplementedError). 함수의 입출력 모양은 10/14 회의에서 확정한다.
"""
