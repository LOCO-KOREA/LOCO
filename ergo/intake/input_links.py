"""Propagate a stated same-operation weight to its assigned photos, with provenance."""
import copy
import math
import re
from .contract import key
from .grounding import evidence_quote, number_grounded

RULE='SAME_OPERATION_INPUT_V1'
MASS='card.lift.load_mass_kg'
PHOTO=re.compile(r'사진|촬영|이미지|photo|image',re.I)
SAME=re.compile(r'(?:같은|동일한?)\s*(?:작업|물건|상자|중량|무게)|same\s+(?:task|work|box|object)',re.I)
DIFFERENT=re.compile(r'(?:다른|별개)\s*(?:작업|물건|상자)|different\s+(?:task|work|box|object)',re.I)
NEGATIVE=re.compile(r'아니|아님|아닙|아닌|아닐|않|not\s+(?:the\s+)?same',re.I)


def _scoped(session,message):
    scope=message.get('source_photo_scope')
    if scope is None:
        scopes=[(request.get('context') or {}).get('source_photo_scope')
                for turn in session.get('turns') or [] if turn.get('message_id')==message.get('message_id')
                for request in turn.get('requests') or []]
    else:scopes=[scope]
    views=session.get('views') or {}
    expected={(view,photo_id) for view,photo_id in views.items()}
    return any(isinstance(item,dict) and item.get('photo_signature')==session.get('photo_signature') and
               {(row.get('view'),row.get('photo_id')) for row in item.get('views') or []}==expected for item in scopes)


def _relation(text):
    relation=None
    for sentence in re.split(r'(?<!\d)\.|\.(?!\d)|[!?。\n]',text):
        if not PHOTO.search(sentence):continue
        same=SAME.search(sentence)
        if same:
            tail=re.split(r'이며|이고|이지만|그리고|[,;]|\band\b|\bbut\b',sentence[same.end():],maxsplit=1,flags=re.I)[0]
            if NEGATIVE.search(tail) or re.search(r'\bnot\b',sentence[:same.start()],re.I):return None,True
        for different in DIFFERENT.finditer(sentence):
            # "다른 작업은 없어요" does not deny the stated same-work relation.
            tail=sentence[different.end():].strip()
            if not re.match(r'^(?:은|는|이|가|도)?\s*(?:없|아니|아님|아닙|않)',tail):return None,True
        if same:relation=sentence.strip()
    return relation,False


def _source_message(session,identity,mass,context):
    for message in reversed(session.get('messages') or []):
        if not _scoped(session,message):continue
        text=message.get('text') or ''
        relation,denied=_relation(text)
        if denied:return None  # A later refusal must not revive an older positive link.
        quote=evidence_quote(mass.get('quote'),text)
        grounded=quote is not None and number_grounded(mass['value'],quote,'kg')
        direct=any(answer.get('target')==MASS and (answer.get('condition') or 'default')==mass.get('condition','default')
                   and answer.get('value')==mass['value'] for answer in message.get('answers') or [])
        # A direct single-condition edit is scoped to the user's currently
        # confirmed work photo; AI text still needs a copied numeric quote.
        confirmed=context.get('state')=='KNOWN' and context.get('value')=='YES'
        if (grounded or direct) and (relation or confirmed):
            return message.get('message_id'),relation or context.get('quote') or '사진 작업 확인'
    if mass.get('source') in ('USER','SAVED') and context.get('state')=='KNOWN' and context.get('value')=='YES' and not context.get('reask'):
        return None,'직접 입력한 단일 작업 중량 · 현재 사진 작업 확인'
    return None


def synchronize(session):
    """Return new facts; never alter actual answers, snapshots, or the input session."""
    original=session.get('facts') or {}
    result={identity:copy.deepcopy(item) for identity,item in original.items()
            if not (item.get('origin')=='INPUT_LINK' and (item.get('input_link') or {}).get('rule')==RULE)}
    views=session.get('views') or {}
    if not views or not session.get('photo_signature'):return result
    context=result.get(key('context')) or {}
    if context.get('state')=='KNOWN' and context.get('value')=='NO' or context.get('state')=='UNKNOWN' and context.get('source')=='USER':return result
    for target in ('load','load_kg','load_link'):
        item=result.get(key(target))
        if item is None:continue
        if item.get('state') in ('UNKNOWN','CONFLICT') or item.get('reask'):return result
        if target=='load_kg':return result  # A real photo weight, including zero, owns this value.
        if target=='load' and item.get('value')!='MEASURED':return result
        if target=='load_link' and item.get('value')!='YES':return result
    masses=[(identity,item) for identity,item in result.items() if item.get('target')==MASS and not item.get('alias_of')]
    if len(masses)!=1:return result
    identity,mass=masses[0];value=mass.get('value')
    if mass.get('state')!='KNOWN' or type(value) not in (int,float) or not math.isfinite(value) or value<0:return result
    if mass.get('source') not in ('AI','USER','SAVED'):return result
    source=_source_message(session,identity,mass,context)
    if source is None:return result
    message_id,relation=source
    proof=dict(rule=RULE,source_identity=identity,source_condition=mass.get('condition','default'),source_value=value,
               source_updated_at=mass.get('updated_at'),source_message_id=message_id,
               photo_signature=session['photo_signature'],photo_ids=sorted(set(views.values())),relation_quote=relation)
    def linked(target,number):
        return dict(target=target,condition='default',value=number,state='KNOWN',source='AI',origin='INPUT_LINK',
                    quote=mass.get('quote') or relation,updated_at=mass.get('updated_at'),conflict=None,input_link=copy.deepcopy(proof))
    result[key('load_kg')]=linked('load_kg',value)
    if key('load') not in result:result[key('load')]=linked('load','MEASURED')
    return result
