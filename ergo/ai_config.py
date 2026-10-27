"""Pure shared AI settings contract, independent of storage and provider clients."""
import copy
import math
import os

VERSION = 'LOCO_AI_SETTINGS_V1'
FIELDS = (
    dict(key='gpt_enabled', label='AI 사용', kind='boolean', default=False),
    dict(key='gpt_model', label='모델 ID', kind='text', default='gpt-6-luna', env='LOCO_AI_MODEL'),
    dict(key='gpt_reasoning_effort', label='추론 강도', kind='choice', default='high', env='LOCO_AI_REASONING_EFFORT',
         choices=[dict(value=v, label=label) for v,label in (
             ('','전송 안 함'),('none','None'),('low','Low'),('medium','Medium'),('high','High'),('xhigh','Extra high'),('max','Max'))]),
    dict(key='gpt_max_output_tokens', label='최대 출력 토큰 (추론 포함)', kind='integer', default=32768, env='LOCO_AI_MAX_OUTPUT_TOKENS'),
)
KEYS = tuple(field['key'] for field in FIELDS)
# User rule: wait for this request without a local deadline or automatic resubmission.
# Provider/connection failures still return through each caller's existing error handling.
REQUEST_TIMEOUT_SECONDS = None
REQUEST_ATTEMPTS = 1
REQUEST_POLICY = dict(timeout=REQUEST_TIMEOUT_SECONDS, max_retries=0)


def validate(settings):
    for field in FIELDS:
        value=settings[field['key']]
        kind=field['kind']
        valid=(type(value) is bool if kind=='boolean' else
               isinstance(value,str) if kind=='text' else
               value in [c['value'] for c in field['choices']] if kind=='choice' else
               type(value) is int and value>0 if kind=='integer' else
               type(value) in (int,float) and math.isfinite(value) and value>0)
        if not valid: raise ValueError(field['label']+' 설정 형식이 올바르지 않습니다')


def defaults():
    result={}
    for field in FIELDS:
        value=os.environ.get(field.get('env',''),field['default'])
        if field['kind']=='number': value=float(value)
        elif field['kind']=='integer': value=int(value)
        result[field['key']]=value
    validate(result)
    return result


def values(settings=None):
    result=defaults()
    result.update({key:settings[key] for key in KEYS if settings and key in settings})
    validate(result)
    return result


def public_contract():
    return dict(version=VERSION,fields=copy.deepcopy(FIELDS),defaults=defaults())


def request_options(model=None, settings=None):
    selected=values(settings)
    options=dict(model=model if model is not None else selected['gpt_model'],
                 max_output_tokens=selected['gpt_max_output_tokens'])
    if selected['gpt_reasoning_effort']: options['reasoning']=dict(effort=selected['gpt_reasoning_effort'])
    return options


def connection(response, model, settings=None):
    requested=values(settings)
    reasoning=getattr(response,'reasoning',None)
    effort=reasoning.get('effort') if isinstance(reasoning,dict) else getattr(reasoning,'effort',None)
    return dict(response_id=getattr(response,'id',None),model=getattr(response,'model',None) or model,
                reasoning_effort=effort,requested_reasoning_effort=requested['gpt_reasoning_effort'])
