"""GPT에 보내는 값의 경계 (API 계약서 6.2절). v_gpt_payload 뷰의 열을 '보냄 / 거르기용'으로 나눈다.

tests/test_gpt_payload.py가 이 목록과 DB 뷰의 열을 대조한다. 뷰에 열이 생기면 여기에 어느 쪽인지 적어야
시험이 통과한다 — 새 열이 말없이 GPT로 나가는 것을 막기 위해서다.
"""

# GPT에 보낸다 (공개 법령 문구, 숫자, 점수만)
SENT_COLUMNS = (
    "criterion_no",
    "criterion_summary",
    "criterion_legal_text",
    "daily_work_h",
    "max_share_ratio",
    "max_exposure_h",
    "reba_score",
    "risk_level_cd",
)

# 거르고 묶는 데만 쓴다. 보내지 않는다 (보고서 요약에서 survey_task_cnt만 'task_cnt'로 보냄)
FILTER_COLUMNS = (
    "warning_id",
    "survey_id",
    "unit_task_id",
    "survey_task_cnt",
)


def build_warning_payload(row: dict) -> dict:
    """뷰의 한 행 → 경고 조언 요청 본문 (API 계약서 6.2절의 JSON). WP2가 채운다."""
    raise NotImplementedError("WP2")


def numbers_in_text_are_allowed(sentences: list[str], payload: dict) -> bool:
    """받은 문장의 모든 숫자가 보낸 JSON 안에 있는가 (API 계약서 6.4절).
    2.10과 2.1은 같은 숫자, 비율은 백분율도 인정 (0.35 → 35). WP2가 채운다. 수용 기준: AC-31."""
    raise NotImplementedError("WP2")
