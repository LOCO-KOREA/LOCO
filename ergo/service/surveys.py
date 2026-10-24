"""LOCO 2.0 surveys service. Dependencies are supplied by Runtime."""
import copy
from ergo.engine.task_defaults import now
from ergo.engine.survey_defaults import normalize_survey
from ergo.report import workbook as report

def handle_list_surveys(ctx, method, p):
    summaries = []
    for s in ctx.store('list_surveys'):
        ov = report.overview(ctx.export_snapshot(s['survey_id'], []))
        summaries.append(dict(survey_id=s['survey_id'], title=s['title'], survey_date=s['survey_date'], task_count=len(ov['tasks']), reviewed=s['review']['reviewed'], review_current=ov['state']['review_current']))
    return summaries

def handle_create_survey(ctx, method, p):
    review = dict(reviewed=False, reviewed_analysis_ids=[], reviewed_metadata_revision=None, reviewer=None, reviewed_at=None, note=None)
    draft = normalize_survey(p['draft'], require_occasional_cause=True)
    draft['survey_type_source'] = 'USER' if 'survey_type' in p['draft'] else 'DEFAULT'
    draft['occasional_cause_source'] = 'USER' if draft['occasional_cause'] else 'UNKNOWN'
    identity = ctx.store('create_survey', draft, review, now(), now())
    return ctx.require('survey', identity)

def handle_get_survey(ctx, method, p):
    result = ctx.require('survey', p['survey_id'])
    result.update(normalize_survey(result))
    return result

def handle_update_survey(ctx, method, p):
    current = ctx.require('survey', p['survey_id'])
    current_draft = normalize_survey(current)
    supplied = copy.deepcopy(p['draft'])
    if 'survey_type' not in supplied:
        supplied['survey_type'] = current_draft['survey_type']
    draft = normalize_survey(supplied, require_occasional_cause=True)
    survey_type_changed = draft['survey_type'] != current_draft['survey_type']
    cause_changed = draft['occasional_cause'] != current_draft['occasional_cause']
    draft['survey_type_source'] = ('USER' if survey_type_changed or cause_changed else
                                   current.get('survey_type_source', 'UNKNOWN'))
    draft['occasional_cause_source'] = ('USER' if cause_changed and draft['occasional_cause'] else
                                        current.get('occasional_cause_source', 'UNKNOWN'))
    ctx.store('update_survey_metadata', p['survey_id'], draft, now())
    result = ctx.require('survey', p['survey_id'])
    result.update(normalize_survey(result))
    return result

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
    return ctx.require('survey', s['survey_id'])
