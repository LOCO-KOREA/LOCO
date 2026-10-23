"""OpenAI Responses client with bounded latency and a strict, non-judgment schema."""
import json
from ergo import ai_config as config
from .intake import request as adaptive_intake
from .payload import explanation_schema, validate_content
from ergo.user_language import TERMS

PROMPT_VERSION='LOCO_NUMERIC_EXPLANATION_V6'
SYSTEM_PROMPT=(
    '당신은 현장 조사자가 계산 결과를 이해하도록 돕는 설명 작성자입니다. '
    '사용자 입력·사진을 추측하지 말고 제공된 숫자 요약과 공개 기준 문장만 사용하세요. '
    '계산 상태와 조사자 결론을 그대로 설명하고 기준 해당 여부를 새로 판정하거나 점수·노출시간을 변경하지 마세요. '
    '기술태그나 REBA를 법적 판단으로 표현하지 마세요. 확인이 필요한 사실은 확인 항목으로 제시하세요. '
    '개선 제안은 일반적인 검토 선택지로 쓰고, 실제 적용 전 조사자 확인이 필요하다고 표시하세요. '
    '모든 수치는 입력 요약 안의 값만 사용하고, 근거 없는 수치는 쓰지 마세요. '
    'basis_refs에는 요약의 근거 코드(item_code, 예: C01-B01)만 그대로 쓰고 값이나 설명을 덧붙이지 마세요. '
    '해당 여부를 확정하거나 "판정되었다"고 단정하지 말고 "계산 초안으로는 해당"처럼 초안·후보 표현을 쓰세요. '
    'criteria에는 1호부터 11호까지 11개 항목을 빠짐없이 순서대로 쓰세요. 입력이 없거나 해당 여부와 무관한 호도 한 문장으로 상태만 설명하세요. 한국어로 간결하게 답하세요. '
    '사용자에게 보이는 본문에는 상태 코드나 개발 용어를 쓰지 마세요. 아래 용어는 뜻에 맞는 한국어로 풀어 쓰세요. '
    + json.dumps(TERMS,ensure_ascii=False)
)

INTAKE_PROMPT_VERSION='LOCO_INTAKE_V2'
INTAKE_PROMPT=(
    '당신은 현장 조사자가 쓴 작업 설명 한 문장을 조사표 칸에 옮겨 적는 도우미입니다. '
    '입력은 사용자가 쓴 문장(text)과 채울 수 있는 칸 목록(targets)입니다. '
    '문장에 분명히 적힌 사실만 해당 칸에 옮기세요. 적히지 않은 값은 추측·추정·평균값으로 채우지 말고 그 칸은 만들지 마세요. '
    '시간은 분 단위, 횟수와 시간은 모두 하루 기준 숫자로 환산하세요(1시간=60분). 연간 값은 일수로 쓰세요. '
    'quote에는 그 값의 근거가 된 문장 속 구절을 글자 그대로 복사하세요. 고치거나 요약하지 마세요. '
    '같은 칸은 한 번만 쓰세요. 작업 종류(work_type.*)는 문장이 그 작업을 한다고 분명히 말할 때만 고르세요. '
    '하나의 시간이 여러 자세나 부위에 걸쳐 있으면 "합친 하루 총 시간" 칸에만 쓰고, 개별 칸은 문장이 따로 말했을 때만 쓰세요. '
    'daily_work_min은 문장이 하루 근무·작업 시간 전체를 말할 때만 쓰세요(특정 동작을 하는 시간은 쓰지 마세요). '
    '예/아니오 칸(YES/NO)은 문장이 직접 말한 경우에만 쓰세요. '
    '숫자 칸은 number에, 선택 칸과 이름 칸은 text에 쓰고 쓰지 않는 쪽은 null로 두세요. '
    '해당 여부, 위험도, 점수를 판단하거나 조언하지 마세요. 칸을 채우는 일만 하세요.'
)

def warm_up():
    """Load the OpenAI SDK in the background. Its first import takes ~14 s on a cold PC and would land on the first AI click."""
    import threading
    def load():
        try: import openai  # noqa: F401
        except Exception: pass
    thread=threading.Thread(target=load,daemon=True,name='openai-warm-up'); thread.start()
    return thread

def _reason(error):
    name=type(error).__name__
    if 'Timeout' in name: return 'TIMEOUT'
    if name in ('JSONDecodeError',): return 'INVALID_STRUCTURED_CONTENT'
    return 'API_ERROR'

def interpret(text, targets, schema, model, api_key, settings=None):
    """One sentence -> list of {target, number, text, quote}. The caller validates every answer against the sentence."""
    if not api_key: return None,'NO_API_KEY'
    if not model: return None,'MODEL_NOT_CONFIGURED'
    try:
        from openai import OpenAI
        transport,options=config.request_options(model,settings)
        client=OpenAI(api_key=api_key,**transport)
        response=client.responses.create(**options,input=[
            {'role':'system','content':INTAKE_PROMPT},
            {'role':'user','content':json.dumps({'text':text,'targets':targets},ensure_ascii=False,separators=(',',':'))}
        ],text={'format':{'type':'json_schema','name':'loco_intake','strict':True,'schema':schema}})
        if getattr(response,'status',None)!='completed': return None,'INCOMPLETE_RESPONSE'
        raw=getattr(response,'output_text',None)
        if not raw: return None,'REFUSAL_OR_EMPTY_RESPONSE'
        answers=json.loads(raw).get('answers')
        return (answers,None) if isinstance(answers,list) else (None,'INVALID_STRUCTURED_CONTENT')
    except ImportError: return None,'OPENAI_SDK_MISSING'
    except Exception as error: return None,_reason(error)

def generate(summary, model, api_key, settings=None):
    if not api_key: return None,'NO_API_KEY'
    if not model: return None,'MODEL_NOT_CONFIGURED'
    try:
        from openai import OpenAI
        transport,options=config.request_options(model,settings)
        client=OpenAI(api_key=api_key,**transport)
        response=client.responses.create(**options,input=[
            {'role':'system','content':SYSTEM_PROMPT},
            {'role':'user','content':json.dumps(summary,ensure_ascii=False,separators=(',',':'))}
        ],text={'format':{'type':'json_schema','name':'loco_explanation','strict':True,'schema':explanation_schema()}})
        if getattr(response,'status',None)!='completed': return None,'INCOMPLETE_RESPONSE'
        raw=getattr(response,'output_text',None)
        if not raw: return None,'REFUSAL_OR_EMPTY_RESPONSE'
        content=json.loads(raw)
        if not validate_content(content,summary): return None,'INVALID_STRUCTURED_CONTENT'
        content['_connection']=config.connection(response,model,settings)
        return content,None
    except ImportError: return None,'OPENAI_SDK_MISSING'
    except Exception as error:
        name=type(error).__name__
        if 'Timeout' in name: return None,'TIMEOUT'
        if name in ('JSONDecodeError',): return None,'INVALID_STRUCTURED_CONTENT'
        return None,'API_ERROR'

def content_text(content):
    if not content: return None
    parts=[content.get('summary','')]
    parts.extend(f"{item['criterion_no']}호: {item['explanation']}" for item in content.get('criteria',[]))
    if content.get('check_items'): parts.append('확인할 항목: '+'; '.join(content['check_items']))
    if content.get('improvement_options'): parts.append('개선 검토 선택지: '+'; '.join(x['proposal'] for x in content['improvement_options']))
    return '\n'.join(x for x in parts if x)
