"""Non-binding AI choices and explicit human review, separate from calculation."""
import hashlib
import json
from ergo.engine.reba_scoring import project_score_continuity

VERSION='CRITERION_REVIEW_V1'
PROPOSAL_STATUSES=('APPLICABLE','NOT_APPLICABLE','UNDETERMINED')
BINARY_STATUSES=PROPOSAL_STATUSES[:2]


def digest(value):
    return hashlib.sha256(json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False).encode('utf-8')).hexdigest()


def context_digest(analysis):
    current=project_score_continuity(analysis)
    # AI generation/edit/application is independent of the reviewed facts and
    # calculations. Investigator changes, including reason/evidence, are not.
    return digest({name:current.get(name) for name in (
        'analysis_id','task_id','input_revision','created_at','snapshot','module_states',
        'pose','slot_tags','tags','reba','judgment')})


def confirmation_current(analysis):
    review=analysis.get('criterion_review')
    if (analysis.get('currentness')!='CURRENT' or not isinstance(review,dict) or
            review.get('version')!=VERSION or review.get('analysis_id')!=analysis.get('analysis_id') or
            review.get('input_revision')!=analysis.get('input_revision')):return False
    try:return review.get('context_digest')==context_digest(analysis)
    except (TypeError,ValueError):return False


def proposals(analysis):
    """Only an actual current typed AI response can populate a draft selection."""
    texts=[item for item in analysis.get('ai',[]) if item.get('purpose')=='TASK_EXPLANATION']
    if not texts:return []
    ai=texts[-1]
    if ai.get('result')!='GENERATED' or not (ai.get('source_current') is True or ai.get('confirmation_current') is True):return []
    content=ai.get('content') or {};items=content.get('criteria')
    from .payload import validate_content
    if not validate_content(content,ai.get('input_summary'),allow_legacy=False):return []
    if (not isinstance(items,list) or [item.get('criterion_no') for item in items if isinstance(item,dict)]!=list(range(1,12)) or
            any(not isinstance(item,dict) or item.get('proposed_status') not in PROPOSAL_STATUSES for item in items)):return []
    by_number={item['criterion_no']:item for item in (analysis.get('judgment') or {}).get('judgments',[])}
    result=[]
    for item in items:
        judgment=by_number.get(item['criterion_no'],{})
        computed=judgment.get('computed_status');proposed=item['proposed_status']
        result.append(dict(criterion_no=item['criterion_no'],proposed_status=proposed,
            reason=item.get('explanation',''),basis_refs=list(item.get('basis_refs') or []),
            source_text_id=ai['text_id'],source_current=ai.get('source_current') is True,
            confirmation_current=ai.get('confirmation_current') is True,computed_status=computed,
            investigator_status=(judgment.get('investigator') or {}).get('status'),
            conflicts_with_computed=computed in BINARY_STATUSES and proposed in BINARY_STATUSES and computed!=proposed))
    return result


def project(analysis):
    """Read-time fields only. Never rewrite stored AI, review or calculation data."""
    analysis['confirmation_current']=confirmation_current(analysis)
    review=analysis.get('criterion_review') or {}
    for ai in analysis.get('ai',[]):
        ai['confirmation_current']=bool(analysis['confirmation_current'] and review.get('source_text_id')==ai.get('text_id')
                                      and review.get('source_summary_digest')==digest(ai.get('input_summary'))
                                      and review.get('source_text_digest')==digest({key:ai.get(key) for key in ('content','generated_text','prompt_version')}))
    analysis['criteria_proposals']=proposals(analysis)
    return analysis
