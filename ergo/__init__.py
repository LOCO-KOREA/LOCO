"""근골격계 유해요인조사 보조 앱 (ergo-assist).

층 (API 계약서 1절)
    화면  →  서비스 (ergo.service)  →  엔진 (ergo.engine) · 저장소 (ergo.db) · GPT (ergo.gpt) · 엑셀 (ergo.report)

- 화면은 서비스 함수만 부른다. DB를 직접 읽거나 쓰지 않는다.
- 엔진은 DB와 화면을 모르는 순수 함수다. 같은 입력이면 같은 출력이 나와야 한다 (NFR-004).
- 계약의 원본은 ergo/contracts.py 이다. 문서(API 계약서)는 이 파일에서 만들어진다.
"""
from .contracts import CONTRACT_VERSION  # noqa: F401
