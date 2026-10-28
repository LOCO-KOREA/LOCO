"""Build a second source check without treating earlier model proposals as facts."""
import copy
from .contract import PHOTO_VIEWS

PURPOSE='SOURCE_COVERAGE'
PHASE='FOLLOWUP'
KNOWN_KEYS=('target','condition','value','state','source','photo_id','view')


def known_values(session):
    active=set(session.get('views',{}).values())
    return [{name:copy.deepcopy(item[name]) for name in KNOWN_KEYS if name in item}
            for item in session['facts'].values() if not item.get('alias_of')
            and not (item['target'].startswith('manual.') and item.get('photo_id') is not None and item['photo_id'] not in active)]


def photo_scope(session,preview):
    return dict(photo_signature=session.get('photo_signature'),views=[
        dict(view=view,photo_id=session['views'][view],
             engine=copy.deepcopy(preview.get('views',{}).get(view,{}).get('engine')),
             quality=copy.deepcopy(preview.get('views',{}).get(view,{}).get('quality')))
        for view in PHOTO_VIEWS if view in session.get('views',{})])


def photo_changed(context,original,latest):
    source=context.get('source_photo_scope',{}).get('photo_signature',original.get('photo_signature'))
    return source!=latest.get('photo_signature')


def payload(first,session,preview,turn,context,source_scope,missing):
    result=copy.deepcopy(first)
    result.update(phase=PHASE,purpose=PURPOSE,known=known_values(session),missing=missing,asked=[],
        prior_user_text=context['texts'],source_photo_scope=copy.deepcopy(source_scope),
        current_photo_scope=photo_scope(session,preview),
        previous_proposals=[dict(phase=request['phase'],answers=copy.deepcopy(request['answers'])) for request in turn['requests']],
        previous_decisions=copy.deepcopy(turn['decisions']))
    return result
