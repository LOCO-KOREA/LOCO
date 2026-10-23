"""Source context and append-only turn receipts inside the existing task JSON."""
import copy
import re
from uuid import uuid4
from ergo.engine.task_defaults import now
from .contract import POLICY, fields

ANSWER_KEYS=('target','condition','number','text','quote','calculation')
CONNECTION_KEYS=('status','model','reasoning_effort','requested_reasoning_effort','reason','observed_at','elapsed_ms','response_id')


def message_id(message,index):
    return message.get('message_id') or 'legacy:'+str(index)


def source_ids(session,quote):
    if not isinstance(quote,str) or not quote.strip():return []
    needle=re.sub(r'\s+','',quote)
    return [message_id(message,index) for index,message in enumerate(session['messages'])
            if needle in re.sub(r'\s+','',message.get('text',''))]


def diagnostics(session):
    latest={}
    decisions=[dict(decision,turn_id=turn['turn_id'],decided_at=decision.get('decided_at') or turn.get('created_at') or '')
               for turn in session.get('turns',[]) for decision in turn.get('decisions',[])]
    for decision in sorted(decisions,key=lambda d:d['decided_at']):
        if decision.get('outcome')=='IGNORED':continue
        identity=(decision.get('target'),decision.get('condition') or POLICY['default_condition'])
        latest[identity]=decision
    if not latest:
        return copy.deepcopy(session.get('last_dropped',[]))
    return [value for value in latest.values() if value['outcome']=='REJECTED']


def context(session,exclude_id=None):
    messages=[(message_id(message,index),message['text']) for index,message in enumerate(session['messages'])
              if isinstance(message.get('text'),str) and message['text'].strip() and message_id(message,index)!=exclude_id]
    retry={identity for item in diagnostics(session) for identity in item.get('source_message_ids',[])}
    # One extracted field is not proof that every fact in its sentence was understood.
    pending=[row for row in messages if row[0] in retry]+messages
    selected={};used=0
    for identity,text in pending:
        if identity in selected:continue
        limit=POLICY['history_context_chars']
        if limit is not None and used+len(text)>limit:continue
        selected[identity]=text;used+=len(text)
    chosen=[(identity,text) for identity,text in messages if identity in selected]
    return dict(texts=[text for _,text in chosen],message_ids=[identity for identity,_ in chosen],
                omitted_message_ids=[identity for identity,_ in messages if identity not in selected],char_count=used)


def begin(session,message,task,answers,focus):
    turns=session.setdefault('turns',[])
    if not turns and session.get('last_dropped'):
        turns.append(dict(turn_id='legacy-diagnostics',message_id=None,created_at=None,status='LEGACY',requests=[],
            decisions=[dict(item,outcome='REJECTED',source_message_ids=[]) for item in session['last_dropped']]))
    turn=dict(turn_id=uuid4().hex,message_id=message.get('message_id') if message else None,
        created_at=now(),decided_at=now(),input_revision=task['input_revision'],status='SAVED',requests=[],decisions=[],
        focus=[dict(target=item['target'],condition=item['condition']) for item in focus])
    for answer in answers:
        field=next(field for field in fields() if field['target']==answer['target'])
        condition=answer.get('condition') or POLICY['default_condition'] if field['conditioned'] else POLICY['default_condition']
        turn['decisions'].append(dict(target=answer['target'],condition=condition,
            outcome='USER_SAVED',reason=None,proposal_index=None,source_message_ids=[],decided_at=now()))
    turns.append(turn)
    return turn


def request(turn,phase,raw,reason,connection,source_context):
    answers=(raw or {}).get('answers',[])
    turn['requests'].append(dict(phase=phase,reason=reason,
        connection={key:copy.deepcopy(connection.get(key)) for key in CONNECTION_KEYS},
        answers=[{key:copy.deepcopy(answer[key]) for key in ANSWER_KEYS if key in answer}
                 for answer in answers if isinstance(answer,dict)],
        questions=copy.deepcopy((raw or {}).get('questions',[])),context=copy.deepcopy(source_context)))


def record_decisions(session,turn,outcomes,request_index=0):
    turn['decided_at']=now()
    for outcome in outcomes:
        turn['decisions'].append(dict(outcome,request_index=request_index,decided_at=now(),source_message_ids=source_ids(session,outcome.get('quote'))))


def ignored(session,turn,reason):
    index=len(turn['requests'])-1
    record_decisions(session,turn,[dict(target=answer.get('target'),condition=answer.get('condition'),
        quote=answer.get('quote'),proposal_index=i,outcome='IGNORED',reason=reason)
        for i,answer in enumerate(turn['requests'][index]['answers'])],index)
