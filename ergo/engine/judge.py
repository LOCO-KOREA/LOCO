"""11개 호 판정 초안 (WP3 · 기능정의서 F05-01, 확신도 F05-02는 WP2).

판정은 단위작업 × 호마다 하나다. 순서: 부담작업 전제(BR-02) → 입력 확인 → 계산 → 확신도 → 해석 차이.
앞 단계에서 결론이 나면 뒤 단계는 보지 않는다 (기능정의서 3.2절 규칙 1). 비교는 모두 '이상(≥)'이고
반올림하기 전 값으로 한다.

이 함수 하나가 'LLM을 쓰지 않는다'는 원칙의 중심이다. 채점·판정·점수에 GPT를 쓰지 않는다 (NFR-011).
"""
from __future__ import annotations

from typing import Mapping, Optional, Sequence

from .. import contracts as C


def judge_criteria(period_type: C.PeriodType, inputs: C.TaskInputs,
                   repetitions: Sequence[C.RepetitionInput], lift_positions: Sequence[C.LiftPositionInput],
                   shares: Sequence[C.PostureShare], valid_still_cnt: int = 0,
                   min_sample_cnt: int = 5) -> Mapping[int, C.Judgment]:
    """입력값과 자세 비율 → 호 번호(1~11)별 판정 초안과 근거.

    판정 상태: 해당 · 비해당 · 사람 확인 · 입력 필요. 호마다 근거와 출처(고시 제3조 제N호 · 각도 출처)를 함께 만든다.
    자세 비율을 쓰는 3·4·5호는 판별 가능한 사진이 min_sample_cnt(TP-12)보다 적으면 '사람 확인'(SMALL_SAMPLE)이다.
    수용 기준: AC-21 (KOSHA 지침 부록 1의 판단 예시 11개와 같다), AC-22 (30kg ÷ 2명 = 15kg → 8호 비해당),
    AC-23 (4호 전제가 '아니오'면 노출 3시간이어도 비해당).
    """
    raise NotImplementedError("WP3")
