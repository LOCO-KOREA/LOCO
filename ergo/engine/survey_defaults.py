"""Survey metadata defaults and validation for the ergonomic investigation workflow."""
from __future__ import annotations

from copy import deepcopy
from datetime import date


SURVEY_TYPES = {'INITIAL', 'REGULAR', 'OCCASIONAL'}
# Record groups older versions saved that never fed a score. Nothing asks for, checks, keeps or prints them any more
# (owner, 2026-10-27: LOCO calculates REBA and hands the values over as Excel); a row saved with them still loads, and read_survey() leaves them out.
REMOVED_KEYS = ('occasional_reason', 'occasional_cause', 'occasional_cause_source', 'workplace_situation', 'participation', 'symptom_survey')


def survey_draft(value: dict | None = None) -> dict:
    """Fill new fields while keeping existing 2.0 and legacy metadata readable. Only the kept fields are taken from `value`."""
    value = deepcopy(value or {})
    result = {
        'survey_type': 'REGULAR', 'survey_date': None, 'investigator': '', 'department': '',
        'process': '', 'title': '', 'previous_survey_date': None,
    }
    for key in result:
        if key in value:
            result[key] = value[key]
    source = value.get('survey_type_source')
    result['survey_type_source'] = source if source in ('USER', 'DEFAULT', 'UNKNOWN') else 'UNKNOWN'
    return result


def normalize_survey(value: dict | None) -> dict:
    if not isinstance(value, dict):
        raise ValueError('조사 입력은 객체여야 합니다')
    result = survey_draft(value)
    _choice(result['survey_type'], SURVEY_TYPES, 'survey_type')
    for key in ('investigator', 'department', 'process', 'title'):
        if not isinstance(result[key], str):
            raise ValueError(f'{key}은 문자열이어야 합니다')
    for date_key in ('survey_date', 'previous_survey_date'):
        _date(result[date_key], date_key)
    return result


def read_survey(row: dict) -> dict:
    """A saved survey as the app reads it: the checked fields over the stored ones, without the groups an older version saved."""
    survey = {**row, **normalize_survey(row)}
    for key in REMOVED_KEYS:
        survey.pop(key, None)
    return survey


def _choice(value, options, path):
    if value not in options:
        raise ValueError(f'{path} 값이 올바르지 않습니다')


def _date(value, path):
    if value in (None, ''):
        return
    if not isinstance(value, str):
        raise ValueError(f'{path}는 YYYY-MM-DD 또는 비어 있음이어야 합니다')
    try:
        date.fromisoformat(value)
    except ValueError as error:
        raise ValueError(f'{path}는 YYYY-MM-DD 형식이어야 합니다') from error
