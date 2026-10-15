"""Survey metadata defaults and validation for the ergonomic investigation workflow."""
from __future__ import annotations

from copy import deepcopy
from datetime import date


SURVEY_TYPES = {'INITIAL', 'REGULAR', 'OCCASIONAL'}
OCCASIONAL_CAUSES = {'DISEASE_CASE', 'NEW_TASK_OR_EQUIPMENT', 'WORK_ENVIRONMENT_CHANGE', 'OTHER'}
PARTICIPANT_ROLES = {'WORKER_REPRESENTATIVE', 'AFFECTED_WORKER', 'BOTH', 'UNKNOWN'}
PARTICIPATION_METHODS = {'INTERVIEW', 'MEETING', 'OBSERVATION', 'OTHER', 'UNKNOWN'}
SYMPTOM_METHODS = {'QUESTIONNAIRE', 'INTERVIEW', 'OTHER', 'NOT_DONE', 'UNKNOWN'}
BODY_SITES = ('neck', 'shoulder', 'arm_elbow', 'hand_wrist', 'back', 'leg_foot')
SIDES = {'RIGHT', 'LEFT', 'BOTH', 'NONE', 'UNKNOWN'}
DURATIONS = {'LT_1_DAY', 'DAY_TO_WEEK', 'WEEK_TO_MONTH', 'MONTH_TO_6_MONTHS', 'GE_6_MONTHS', 'UNKNOWN'}
SEVERITIES = {'MILD', 'MODERATE', 'SEVERE', 'VERY_SEVERE', 'UNKNOWN'}
TRUTHS = {'YES', 'NO', 'UNKNOWN'}


def blank_response(index: int = 1) -> dict:
    return {
        'response_code': f'익명-{index:03d}', 'name': '', 'age_years': None, 'sex': 'UNKNOWN',
        'workplace_tenure_months': None, 'department': '', 'job': '', 'current_work': '',
        'current_work_months': None, 'daily_work_hours': None, 'rest_breaks': '',
        'previous_work': '', 'previous_work_months': None, 'leisure_activities': '',
        'household_work': 'UNKNOWN', 'medical_history': 'UNKNOWN',
        'injury_history': 'UNKNOWN', 'injury_sites': [], 'physical_burden': None,
        'work_related_symptoms_last_year': 'UNKNOWN', 'regions': {
            site: {'side': 'UNKNOWN', 'duration': 'UNKNOWN', 'severity': 'UNKNOWN', 'last_week': 'UNKNOWN'}
            for site in BODY_SITES
        },
    }


def survey_draft(value: dict | None = None) -> dict:
    """Fill new fields while keeping existing 2.0 and legacy metadata readable."""
    value = deepcopy(value or {})
    result = {
        'survey_type': 'REGULAR', 'survey_date': None, 'investigator': '', 'department': '',
        'process': '', 'title': '', 'occasional_reason': None, 'occasional_cause': None,
        'previous_survey_date': None,
        'workplace_situation': {
            'equipment_status': 'UNKNOWN', 'equipment_notes': '',
            'workload_status': 'UNKNOWN', 'workload_notes': '',
            'speed_status': 'UNKNOWN', 'speed_notes': '',
            'work_pattern_status': 'UNKNOWN', 'work_pattern_notes': '',
        },
        'participation': {
            'status': 'UNKNOWN', 'role': 'UNKNOWN', 'participant_code': '',
            'method': 'UNKNOWN', 'date': None, 'notes': '',
        },
        'symptom_survey': {
            'method': 'UNKNOWN', 'date': None, 'respondent_count': None,
            'summary': '', 'responses': [],
        },
    }
    for key, default in result.items():
        incoming = value.get(key)
        if isinstance(default, dict):
            merged = deepcopy(default)
            if isinstance(incoming, dict):
                merged.update(incoming)
            result[key] = merged
        elif key in value:
            result[key] = incoming
    return result


def normalize_survey(value: dict | None, *, require_occasional_cause: bool = False) -> dict:
    if not isinstance(value, dict):
        raise ValueError('조사 입력은 객체여야 합니다')
    result = survey_draft(value)
    _choice(result['survey_type'], SURVEY_TYPES, 'survey_type')
    cause = result['occasional_cause']
    if cause not in (None, ''):
        _choice(cause, OCCASIONAL_CAUSES, 'occasional_cause')
    if require_occasional_cause and result['survey_type'] == 'OCCASIONAL' and not cause:
        raise ValueError('수시조사 사유 유형을 선택해 주세요')
    for key in ('investigator', 'department', 'process', 'title'):
        if not isinstance(result[key], str):
            raise ValueError(f'{key}은 문자열이어야 합니다')
    for date_key in ('survey_date', 'previous_survey_date'):
        _date(result[date_key], date_key)

    situation = result['workplace_situation']
    for key in ('equipment_status', 'workload_status', 'speed_status', 'work_pattern_status'):
        _choice(situation.get(key), TRUTHS, f'workplace_situation.{key}')
    for key in ('equipment_notes', 'workload_notes', 'speed_notes', 'work_pattern_notes'):
        _string(situation.get(key), f'workplace_situation.{key}')

    participation = result['participation']
    _choice(participation.get('status'), TRUTHS, 'participation.status')
    _choice(participation.get('role'), PARTICIPANT_ROLES, 'participation.role')
    _choice(participation.get('method'), PARTICIPATION_METHODS, 'participation.method')
    for key in ('participant_code', 'notes'):
        _string(participation.get(key), f'participation.{key}')
    _date(participation.get('date'), 'participation.date')

    symptom = result['symptom_survey']
    _choice(symptom.get('method'), SYMPTOM_METHODS | {'UNKNOWN'}, 'symptom_survey.method')
    _date(symptom.get('date'), 'symptom_survey.date')
    count = symptom.get('respondent_count')
    if count is not None and (isinstance(count, bool) or not isinstance(count, int) or count < 0):
        raise ValueError('symptom_survey.respondent_count는 0 이상의 정수여야 합니다')
    _string(symptom.get('summary'), 'symptom_survey.summary')
    responses = symptom.get('responses')
    if not isinstance(responses, list):
        raise ValueError('symptom_survey.responses는 목록이어야 합니다')
    seen = set()
    for i, response in enumerate(responses):
        _validate_response(response, i)
        code = response['response_code'].strip()
        if not code or code in seen:
            raise ValueError('증상 응답 코드는 비어 있거나 중복될 수 없습니다')
        seen.add(code)
    if responses and count is None:
        symptom['respondent_count'] = len(responses)
    elif responses and count < len(responses):
        raise ValueError('응답자 수는 입력된 익명 응답 수보다 작을 수 없습니다')
    return result


def _validate_response(response, index):
    prefix = f'symptom_survey.responses.{index}'
    if not isinstance(response, dict):
        raise ValueError(f'{prefix}는 객체여야 합니다')
    base = blank_response(index + 1)
    for key, default in base.items():
        if key in ('regions',):
            continue
        if key not in response:
            response[key] = deepcopy(default)
    for key in ('response_code', 'name', 'department', 'job', 'current_work', 'rest_breaks',
                'previous_work', 'leisure_activities'):
        _string(response.get(key), f'{prefix}.{key}')
    for key in ('age_years', 'workplace_tenure_months', 'current_work_months',
                'previous_work_months', 'daily_work_hours', 'physical_burden'):
        number = response.get(key)
        if number is not None and (isinstance(number, bool) or not isinstance(number, int) or number < 0):
            raise ValueError(f'{prefix}.{key}는 0 이상의 정수 또는 비어 있음이어야 합니다')
    for key in ('medical_history', 'injury_history', 'work_related_symptoms_last_year'):
        _choice(response.get(key), TRUTHS, f'{prefix}.{key}')
    _choice(response.get('sex'), {'MALE', 'FEMALE', 'UNKNOWN'}, f'{prefix}.sex')
    _choice(response.get('household_work'), {'NONE', 'LT_1_HOUR', '1_TO_2_HOURS', '2_TO_3_HOURS', 'GE_3_HOURS', 'UNKNOWN'}, f'{prefix}.household_work')
    if response.get('physical_burden') not in (None, 1, 2, 3, 4, 5):
        raise ValueError(f'{prefix}.physical_burden는 1~5 또는 비어 있음이어야 합니다')
    injury_sites = response.get('injury_sites')
    if not isinstance(injury_sites, list) or any(not isinstance(x, str) or x not in BODY_SITES for x in injury_sites):
        raise ValueError(f'{prefix}.injury_sites 형식이 올바르지 않습니다')
    regions = response.get('regions')
    if not isinstance(regions, dict):
        raise ValueError(f'{prefix}.regions는 객체여야 합니다')
    for site in BODY_SITES:
        item = regions.get(site)
        if item is None:
            regions[site] = deepcopy(base['regions'][site])
            item = regions[site]
        if not isinstance(item, dict):
            raise ValueError(f'{prefix}.regions.{site} 형식이 올바르지 않습니다')
        for key, options in (('side', SIDES), ('duration', DURATIONS), ('severity', SEVERITIES), ('last_week', TRUTHS)):
            _choice(item.get(key, 'UNKNOWN'), options, f'{prefix}.regions.{site}.{key}')


def _choice(value, options, path):
    if value not in options:
        raise ValueError(f'{path} 값이 올바르지 않습니다')


def _string(value, path):
    if value is not None and not isinstance(value, str):
        raise ValueError(f'{path}는 문자열이어야 합니다')


def _date(value, path):
    if value in (None, ''):
        return
    if not isinstance(value, str):
        raise ValueError(f'{path}는 YYYY-MM-DD 또는 비어 있음이어야 합니다')
    try:
        date.fromisoformat(value)
    except ValueError as error:
        raise ValueError(f'{path}는 YYYY-MM-DD 형식이어야 합니다') from error
