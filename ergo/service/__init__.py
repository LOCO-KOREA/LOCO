"""서비스 계층: 화면이 부르는 함수 (API 계약서 4절, contracts.ServiceAPI).

지금은 스텁(가짜 값)만 있다. 진짜 서비스가 같은 시험(tests/contract_suite.py)을 통과하면 get_service()를 바꾼다.
"""
from .stub import StubService


def get_service(progress_delay_s: float = 0.2) -> StubService:
    return StubService(progress_delay_s=progress_delay_s)
