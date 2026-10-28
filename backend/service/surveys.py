"""LOCO 2.0 surveys service. Dependencies are supplied by Runtime."""
import copy
from backend.engine.task_defaults import now
from backend.engine.survey_defaults import REMOVED_KEYS, normalize_survey, read_survey
from backend.report import workbook as report

def handle_list_surveys(ctx, method, p):
    summaries = []
    for s in ctx.store('list_surveys'):
        ov = report.overview(ctx.export_snapshot(s['survey_id'], []))
        summaries.append(dict(survey_id=s['survey_id'], title=s['title'], survey_date=s['survey_date'], task_count=len(ov['tasks']), reviewed=s['review']['reviewed'], review_current=ov['state']['review_current']))
    return summaries

def handle_create_survey(ctx, method, p):
    review = dict(reviewed=False, reviewed_analysis_ids=[], reviewed_metadata_revision=None, reviewer=None, reviewed_at=None, note=None)
    draft = normalize_survey(p['draft'])
    draft['survey_type_source'] = 'USER' if 'survey_type' in p['draft'] else 'DEFAULT'
    identity = ctx.store('create_survey', draft, review, now(), now())
    return ctx.require('survey', identity)

def handle_get_survey(ctx, method, p):
    return read_survey(ctx.require('survey', p['survey_id']))

def handle_update_survey(ctx, method, p):
    current = ctx.require('survey', p['survey_id'])
    current_draft = normalize_survey(current)
    supplied = copy.deepcopy(p['draft'])
    if 'survey_type' not in supplied:
        supplied['survey_type'] = current_draft['survey_type']
    draft = normalize_survey(supplied)
    survey_type_changed = draft['survey_type'] != current_draft['survey_type']
    draft['survey_type_source'] = 'USER' if survey_type_changed else current.get('survey_type_source', 'UNKNOWN')
    # A row an older version saved keeps the record groups it already has: existing rows are preserved. Nothing reads, shows or exports them, and nothing new is stored in them.
    draft.update({key: current[key] for key in REMOVED_KEYS if key in current})
    ctx.store('update_survey_metadata', p['survey_id'], draft, now())
    return read_survey(ctx.require('survey', p['survey_id']))

def handle_set_survey_review(ctx, method, p):
    s = ctx.require('survey', p['survey_id'])
    review = copy.deepcopy(p['review'])
    if review.get('reviewed') and review.get('reviewed_metadata_revision') != s['metadata_revision']:
        raise ValueError('조사 정보가 변경되었습니다. 최신 조사 정보를 확인하고 다시 검토하세요.')
    for identity in review.get('reviewed_analysis_ids', []):
        a = ctx.require('analysis', identity)
        if ctx.require('task', a['task_id'])['survey_id'] != s['survey_id']:
            raise ValueError('검토 분석은 이 조사에 속해야 합니다')
    ctx.store('set_survey_review', s['survey_id'], review, now())
    return read_survey(ctx.require('survey', s['survey_id']))
