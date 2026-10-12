"""GPT 어댑터 (WP2 · API 계약서 6절). 설명 문장만 쓴다. 판정과 점수에는 쓰지 않는다 (NFR-011).

규칙: 어댑터는 v_gpt_payload 뷰만 읽는다. 영상, 이미지, 이름, 파일 위치, 자유 입력 글은 보내지 않는다 (BR-21).
받은 문장에 보낸 적 없는 숫자가 있으면 버리고 기본 문구를 쓴다. GPT를 쓸 수 없어도 모든 기능이 동작한다 (NFR-012).
"""
from .payload import FILTER_COLUMNS, SENT_COLUMNS  # noqa: F401
