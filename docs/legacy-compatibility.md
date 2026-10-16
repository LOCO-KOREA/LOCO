# 기존 1.3 자료의 읽기 계약

이 문서는 이전 자료 해석용이다. 새 작업·새 계산은 2.0만 생성한다. 0.3 가짜 서비스, 이전 샘플 서버와 입력 API는 제거했다.

`LegacyTaskV13`은 기존 `TASK.input_json` 원문이다. `schema_version:'1.3'`, `task_kind:'BOX_LIFT'`, 당시 작업명·조건·법령 입력·15슬롯 capture·수동값과 알 수 없는 추가 키를 보존한다. DB 열의 ID·revision·시각과 원문을 구분한다. `ergo/legacy/v13.py`는 기존 중량·시간·조건을 메모리의 일반 작업 편집 DTO로 변환하고 `legacy_input`에 원문 전체를 보존한다. 사진의 기존 회차/순간은 과거 표시명이며 새 하중 근거가 아니다.

`LegacyAnalysisV13`은 `ANALYSIS`의 ID·task_id·input_revision·status·시각과 `snapshot_json/result_json`이다. snapshot의 1.3 입력·설정·모델/규칙과 기존 pose·tags·reba·judgment·조사자 결론·AI를 당시 의미로 읽는다. 새 기준으로 재계산하거나 snapshot을 다시 쓰지 않는다. 당시 module_states가 없으면 표시용 상태만 메모리에서 파생한다.

`LegacyExportSnapshotV13`은 `EXPORT_LOG.snapshot_json` 원문이다. 기존 receipt와 경로·시각도 그대로 보존한다. 과거 출력 버전은 2.0으로 바꾸지 않는다. 기존 출력 로그의 수치 근거는 파일 존재와 별개다. 과거 분석을 새 보조 보고서에 선택할 때도 분석의 source_schema_version과 당시 근거를 표시하며, 새 출력의 버전만 2.0이다.

기존 설정은 읽을 때 현재 실제 엔진의 지원 설정으로 메모리에서 정규화하며 그 조회만으로 원본을 다시 쓰지 않는다. 새 snapshot은 실제 2.0 규칙/공식 모델/전처리를 기록한다. 명시적 작업 저장부터 2.0 입력과 증가된 revision을 기록하며, 새 분석에 과거 결론·설명·검토를 자동 승계하지 않는다.

검증은 합성 1.3 fixture의 원문·분석 snapshot 보존과 명시 저장, 과거 설정 조회 보존을 포함한다. 실제 사용자의 1.3 DB 표본은 제공되지 않아 그 자료의 호환 완료를 주장하지 않는다. 사용자 데이터 일괄 migration·테이블/trigger 추가·기존 snapshot 갱신은 수행하지 않는다.
