"""Shared set-up for the workbook tests: a survey, a small lifting task entered by hand, and an analysis of it."""
import re
import threading

from ergo.engine.task_defaults import task_input
from ergo.service import application

# Words a reader of the workbook must never meet: stored codes, field paths, internal names.
CODE = re.compile(r'\b[A-Z][A-Z0-9]*(?:_[A-Z0-9]+)+\b|\b[a-z]+(?:_[a-z0-9]+)+\b|\b[a-z_]+\.[a-z0-9_.-]+\b|MoveNet|기술태그|스키마|None|null|UNKNOWN')
SURVEY_KEYS = ('survey_type', 'survey_date', 'investigator', 'department', 'process', 'title', 'occasional_reason', 'occasional_cause', 'previous_survey_date',
               'workplace_situation', 'participation', 'symptom_survey')


def make_survey(title='일반 보고서 검증', **changes):
    draft = {'survey_type': 'REGULAR', 'survey_date': '2026-10-23', 'investigator': '조사자', 'department': '팀', 'process': '공정', 'title': title, 'occasional_reason': None}
    draft.update(changes)
    return application.dispatch('create_survey', {'draft': draft})


def update_survey(survey_id, **changes):
    """Change some survey fields and keep the rest, the way the editor saves."""
    survey = application.dispatch('get_survey', {'survey_id': survey_id})
    for key, value in changes.items():
        if isinstance(value, dict) and isinstance(survey.get(key), dict):
            survey[key] = dict(survey[key], **value)
        else:
            survey[key] = value
    return application.dispatch('update_survey', {'survey_id': survey_id, 'draft': {k: v for k, v in survey.items() if k in SURVEY_KEYS}})


def run_analysis(task, scope=('judgment',)):
    analysis = application.new_analysis(task, list(scope))
    application.run(analysis, list(scope), threading.Event(), application._context.analysis_token(analysis['analysis_id']))
    return analysis


def lifting_input(task_name='상자 들기'):
    """Keyboard work 240 min/day and lifting a 20 kg box 30 times a day, entered directly (no photo needed)."""
    draft = task_input({'task_name': task_name, 'input_template': 'LIFTING'})
    draft['conditions'].update(one_off='NO', daily_work_min=480, annual_work_days=220)
    note = {'source': 'INTERVIEW', 'text': '빠른 분석 질문: 무거운 물건을 드는 작업', 'observed_at': '2026-10-23T01:00:00Z'}
    for criterion in draft['legal']['criteria']:
        criterion['condition_present'] = 'NO'
        if criterion['criterion_no'] >= 6:
            criterion['rows_complete'] = 'YES'
    keyboard = draft['legal']['criteria'][0]
    keyboard.update(condition_present='YES', evidence=dict(note))
    next(e for e in draft['legal']['exposures'] if e['condition_code'] == 'C1_KEYBOARD_FOCUSED').update(minutes=240, evidence=dict(note))
    lift = draft['legal']['criteria'][7]
    lift.update(condition_present='YES', evidence=dict(note), rows=[{'row_id': 'quick-1', 'label': '빠른 분석 입력', 'evidence': dict(note), 'load_mass_kg': 20, 'lift_count_day': 30}], rows_complete='YES')
    return draft
