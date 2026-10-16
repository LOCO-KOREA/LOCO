"""Shared report column definitions and immutable DTO traversal."""
NOTICE = '작업 분석 보조 보고서. 법정 유해요인조사표·증상조사표의 완성을 뜻하지 않습니다.'

HEADERS = {'요약': ['task_id', 'task_name', 'analysis_id', 'currentness', 'review_status', 'applicable_criteria', 'needs_input_count', 'needs_review_count', 'first_next_input'], '작업별 결과': ['task_id', 'analysis_id', 'section', 'item_code', 'label', 'value', 'unit', 'source', 'evidence_text', 'observed_at'], '확인사항': ['task_id', 'analysis_id', 'module', 'slot_no', 'criterion_no', 'kind', 'message', 'source', 'reviewer_memo'], '판정 근거': ['task_id', 'analysis_id', 'criterion_no', 'computed_status', 'investigator_status', 'effective_status', 'exclusion', 'comparison_values', 'missing_fields', 'review_reasons', 'source', 'investigator_reason', 'investigator_evidence', 'reviewer', 'reviewed_at']}

HEADER_LABELS = {'요약': ['작업 ID', '작업명', '분석 ID', '결과 현재성', '검토 상태', '해당 호', '입력 필요 호 수', '검토 필요 호 수', '첫 다음 입력'], '작업별 결과': ['작업 ID', '분석 ID', '구역', '항목 코드', '항목명', '값', '단위', '출처', '근거 내용', '관찰 시각'], '확인사항': ['작업 ID', '분석 ID', '모듈', '사진 행 번호', '기준 호', '종류', '안내', '출처', '조사자 메모'], '판정 근거': ['작업 ID', '분석 ID', '기준 호', '계산 초안', '조사자 결론', '유효 결과', '제외 사유', '비교값', '누락 입력', '검토 사유', '규칙 출처', '조사자 사유', '조사자 근거', '검토자', '검토 시각']}

def currentness(task, analysis):
    return 'NONE' if analysis is None else 'CURRENT' if task['input_revision'] == analysis['input_revision'] and task['latest_analysis_id'] == analysis['analysis_id'] else 'STALE'

def flatten(value, prefix=''):
    if isinstance(value, dict):
        for key, child in value.items():
            yield from flatten(child, (prefix + '.' if prefix else '') + key)
    elif isinstance(value, list):
        for i, child in enumerate(value):
            identity = child.get('slot_no', child.get('criterion_no', child.get('condition_code', child.get('row_id', i)))) if isinstance(child, dict) else i
            if isinstance(child, dict) and 'scope' in child:
                identity = str(identity) + '.' + child['scope'] + '.' + child.get('field', '')
            yield from flatten(child, prefix + '.' + str(identity))
    else:
        yield (prefix, value)
