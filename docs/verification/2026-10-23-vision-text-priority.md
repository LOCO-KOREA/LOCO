# 현재 사용자 원문과 사진 AI 추정의 우선권

변경은 VISION의 추정 소유권에만 적용한다. 현재 복사 원문으로 검증한 텍스트가 다른 값을 말하면 KNOWN/CONFLICT VISION을 AI KNOWN으로 정정한다. 같은 값도 현재 원문이 있으면 AI 출처로 승격하고 reconcile의 UNCHANGED로 VISION에 남기지 않는다. 원본 모델 제안과 이미지 raw 관찰은 보존한다.

새 tests/test_vision_text_priority.py 9개 회귀 통과. 무릎 VISION YES→현재 “무릎은 굽히지 않아요” NO, conflict/followup/late 동작, 같은 값의 출처 승격과 과거 인용만으로 승격 금지, USER 모름·직접값/AI/SAVED/POSE 보호, 사진 변경 시 manual/전역 사진 작업특징 차단, 숫자 단위 근거 거절, 서비스 SQLite의 재질문 제외·raw 캐시 불변, canonical manual/alias 사진 소유권, 이후 사진 삭제 후 명시 작업특징 보존을 대조했다.

photo_vision의 계산용 known은 context=NO에서 비우되 public raw 관찰은 보존한다. 사진 부정 후 FOLLOWUP payload가 빈 관찰을 받는지, YES 직접 정정 후 API를 추가 호출하지 않고 다시 사용하는지 기존 서비스 시험에서 확인했다. 신규/관련 vision+registration 총25개 통과. 이 후속 시험은 통제 응답 회귀이며 새 외부 실호출을 의미하지 않는다.
