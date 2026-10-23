"""Korean display text for the Excel report. Stored DTO codes never change: this runs only on the cells being written."""
import re
from ergo.user_language import user_text

STATUS = {'APPLICABLE': '해당', 'NOT_APPLICABLE': '비해당', 'NEEDS_INPUT': '입력 필요', 'NEEDS_REVIEW': '검토 필요', 'EXCLUDED': '제외'}
CURRENTNESS = {'CURRENT': '현재 입력 기준', 'STALE': '이전 입력 기준', 'NONE': '분석 없음'}
REVIEW = {'NO_ANALYSIS': '분석 없음', 'UNREVIEWED': '미검토', 'REVIEWED_CURRENT': '검토 완료', 'REVIEWED_HISTORY': '이전 결과 검토'}
UNIT = {'MIN_DAY': '분/일', 'COUNT_DAY': '회/일', 'COUNT_MIN': '회/분', 'COUNT_HOUR': '회/시간', 'COUNT_YEAR': '일/년', 'MONTH': '개월',
        'KG': 'kg', 'KG_EQUIV': 'kg 상당', 'DEG': '도(°)', 'PX': '픽셀', 'RATIO': '비율', 'BOOLEAN': '예/아니오'}
SOURCE = {'INTERVIEW': '면담', 'DIRECT_OBSERVATION': '직접 관찰', 'DOCUMENT': '문서', 'MEASUREMENT': '측정', 'OTHER': '기타',
          'AUTO_ACCEPTED': '자동 후보 채택', 'MANUAL': '직접 입력', 'DIRECT_INPUT': '직접 입력', 'WORKER_QUESTIONNAIRE': '근로자 설문',
          'SAFETY_RULES_657_658': '안전보건규칙 제657·658조'}
MODULE = {'JUDGMENT': '11개 기준', 'COMPARISON': '전후 비교', 'REBA': 'REBA', 'POSE': '자세 인식', 'TAGS': '자세 태그', 'BURDEN': '11개 기준', 'SURVEY': '조사 개요',
          'ANALYSIS': '분석', 'EXPLANATION': '설명'}
KIND = {'MISSING_INPUT': '입력 필요', 'REVIEW_REQUIRED': '검토 필요', 'NOT_CALCULATED': '미계산', 'NOTE': '메모', 'LIMITATION': '한계',
        'SUMMARY': '요약', 'CONDITION_CHANGE': '입력값 변경', 'CRITERION_CHANGE': '기준 변경'}
VALUE = {
    'YES': '예', 'NO': '아니오', 'UNKNOWN': '모름', 'NOT_APPLICABLE': '해당 없음',
    'INITIAL': '최초', 'REGULAR': '정기', 'OCCASIONAL': '수시',
    'DISEASE_CASE': '질환자 발생', 'NEW_TASK_OR_EQUIPMENT': '신규 작업·설비 도입', 'WORK_ENVIRONMENT_CHANGE': '작업환경 변경',
    'WORKER_REPRESENTATIVE': '근로자대표', 'AFFECTED_WORKER': '해당 근로자', 'BOTH': '둘 다',
    'INTERVIEW': '면담', 'MEETING': '회의', 'OBSERVATION': '현장 관찰', 'OTHER': '기타', 'QUESTIONNAIRE': '설문', 'NOT_DONE': '실시하지 않음',
    'GENERAL': '일반', 'OFFICE': '사무', 'REPETITION': '반복 작업', 'POSTURE': '자세 부담', 'HAND_FORCE': '손·힘', 'LIFTING': '들기', 'IMPACT': '충격',
    'UNDER_30': '30° 미만', 'FROM_30_TO_60': '30~60°', 'OVER_60': '60° 초과',
    'BILATERAL_STABLE': '두 발 안정', 'UNILATERAL_OR_UNSTABLE': '한 발·불안정',
    'GOOD': '좋음', 'FAIR': '보통', 'POOR': '나쁨', 'UNACCEPTABLE': '잡을 곳 없음',
    'UNLOADED': '들고 있는 물건 없음', 'MEASURED': '측정', 'LEFT': '왼쪽', 'RIGHT': '오른쪽', 'COMMON': '공통', 'FRONT': '정면·후면',
    'AUTO': '자동', 'SCREEN_RIGHT': '화면 오른쪽', 'SCREEN_LEFT': '화면 왼쪽',
    'DIRECT_OBSERVATION': '직접 관찰', 'AUTO_ACCEPTED': '자동 후보 채택', 'DOCUMENT': '문서',
    'COMPLETE': '완료', 'INCOMPLETE': '미완료', 'NOT_REQUESTED': '요청 안 함', 'NOT_CALCULATED': '미계산', 'FAILED': '실패', 'CANCELED': '취소',
    'RUNNING': '진행 중', 'FINISHED': '완료', 'DONE': '완료', 'VALID': '유효', 'INVALID': '무효', 'ERROR': '오류', 'PENDING': '대기', 'NOT_PROCESSED': '처리 안 됨',
    'NEGLIGIBLE': '무시 가능', 'LOW': '낮음', 'MEDIUM': '보통', 'HIGH': '높음', 'VERY_HIGH': '매우 높음',
}
OPERATOR = {'GE': '이상', 'EQ': '같음', 'LE': '이하', 'GT': '초과', 'LT': '미만'}
EXCLUSION = {'SHORT_TERM': '단기간 작업', 'INTERMITTENT': '간헐적 작업', 'short_term': '단기간 작업', 'intermittent': '간헐적 작업'}
STATUS_TOKEN = re.compile(r'\b(' + '|'.join(STATUS) + r')\b')


def _map(table, value):
    return table.get(value, value) if isinstance(value, str) else value


def status_text(text):
    """Replace status codes inside a sentence, e.g. 'NOT_APPLICABLE -> NEEDS_INPUT'."""
    if not isinstance(text, str):
        return text
    return user_text(text)


def basis_text(text):
    """One comparison line per basis item: item_code | value | unit | operator | threshold | source."""
    if not isinstance(text, str):
        return text
    lines = []
    for line in text.split('\n'):
        parts = line.split(' | ')
        if len(parts) == 6:
            code, value, unit, operator, threshold, source = parts
            value = VALUE.get(value, '미입력' if value == 'None' else value)
            parts = [code, value, UNIT.get(unit, unit), OPERATOR.get(operator, operator), '' if threshold == 'None' else threshold, SOURCE.get(source, source)]
        lines.append(' | '.join(parts))
    return '\n'.join(lines)


def localize_row(sheet, row):
    """Return a copy of the row with codes shown in Korean. Column positions follow common.HEADER_LABELS."""
    row = list(row)
    if sheet == '요약':
        row[3] = _map(CURRENTNESS, row[3]); row[4] = _map(REVIEW, row[4])
    elif sheet == '작업별 결과':
        row[5] = _map(VALUE, row[5]); row[6] = _map(UNIT, row[6]); row[7] = _map(SOURCE, row[7])
    elif sheet == '확인사항':
        row[2] = _map(MODULE, row[2]); row[5] = _map(KIND, row[5]); row[6] = status_text(row[6]); row[7] = _map(SOURCE, row[7])
    elif sheet == '판정 근거':
        for index in (3, 4, 5):
            row[index] = _map(STATUS, row[index])
        row[6] = _map(EXCLUSION, row[6]); row[7] = basis_text(row[7])
    return row


# Cells that mark "something is missing" for the amber/orange highlighting, in Korean.
MISSING_CELLS = {STATUS['NEEDS_INPUT'], KIND['MISSING_INPUT'], '미완료'}
REVIEW_CELLS = {STATUS['NEEDS_REVIEW'], KIND['REVIEW_REQUIRED']}


PART = {'legal': '11개 기준 입력', 'exposures': '하루 노출시간', 'conditions': '작업조건', 'manual': '수동 관찰', 'capture': '사진 배정',
        'slots': '사진 행', 'rows': '조건 행', 'evidence': '근거', 'source': '출처', 'text': '메모', 'observed_at': '관찰 시각',
        'condition_present': '해당 조건 존재', 'rows_complete': '조건 행 기록 완료', 'minutes': '시간(분)', 'value': '값', 'union': '합집합',
        'totals': '합계', 'LEFT': '왼쪽', 'RIGHT': '오른쪽', 'COMMON': '공통', 'unsupported': '비지지 여부',
        'posture_restricted': '자세 변경 제한', 'label': '이름', 'photo_id': '사진 배정', 'analysis_target': '분석 대상',
        'camera_side': '촬영 측면', 'forward_direction': '작업자 방향', 'side_view_verified': '측면 확인'}


def path_label(path):
    """Readable Korean label for a stored field path, e.g. legal.criteria.9.condition_present -> 11개 기준 입력 · 9호 · 해당 조건 존재."""
    from .labels import MANUAL, INPUTS, EXPOSURES
    parts, out, i = str(path).split('.'), [], 0
    while i < len(parts):
        p = parts[i]
        nxt = parts[i + 1] if i + 1 < len(parts) else None
        if p == 'criteria' and nxt and nxt.isdigit():
            out.append(f'{nxt}호'); i += 2; continue
        if p in ('manual', 'slots') and nxt and nxt.isdigit():
            out.append(PART[p] if p == 'slots' else PART['manual']); out.append(f'사진 행 {nxt}'); i += 2; continue
        if p == 'rows' and nxt:
            out.append(f'조건 행({nxt})'); i += 2; continue
        out.append(PART.get(p) or EXPOSURES.get(p) or MANUAL.get(p) or INPUTS.get(p) or p)
        i += 1
    return ' · '.join(x for x in out if x)


def value_text(value):
    """A before/after value in a change line."""
    if value is None:
        return '없음'
    if isinstance(value, str):
        return VALUE.get(value) or SOURCE.get(value) or value
    return str(value)


def change_text(field_path, before, after):
    """Label first, the stored path kept in parentheses for audit: '<한글 이름> (<path>): 이전 → 이후'."""
    return f'{path_label(field_path)} ({field_path}): {value_text(before)} → {value_text(after)}'
