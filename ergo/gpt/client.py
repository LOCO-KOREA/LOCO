"""OpenAI Responses client with bounded latency and a strict, non-judgment schema."""
import json
from .payload import explanation_schema, validate_content

PROMPT_VERSION='LOCO_NUMERIC_EXPLANATION_V2'
SYSTEM_PROMPT=(
    '당신은 현장 조사자가 계산 결과를 이해하도록 돕는 설명 작성자입니다. '
    '사용자 입력·사진을 추측하지 말고 제공된 숫자 요약과 공개 기준 문장만 사용하세요. '
    '계산 상태와 조사자 결론을 그대로 설명하고 기준 해당 여부를 새로 판정하거나 점수·노출시간을 변경하지 마세요. '
    '기술태그나 REBA를 법적 판단으로 표현하지 마세요. 확인이 필요한 사실은 확인 항목으로 제시하세요. '
    '개선 제안은 일반적인 검토 선택지로 쓰고, 실제 적용 전 조사자 확인이 필요하다고 표시하세요. '
    '모든 수치는 입력 요약 안의 값만 사용하고, 근거 없는 수치는 쓰지 마세요. 한국어로 간결하게 답하세요.'
)

def generate(summary, model, api_key):
    if not api_key: return None,'NO_API_KEY'
    if not model: return None,'MODEL_NOT_CONFIGURED'
    try:
        from openai import OpenAI
        client=OpenAI(api_key=api_key,timeout=10.0,max_retries=0)
        response=client.responses.create(model=model,max_output_tokens=1400,input=[
            {'role':'system','content':SYSTEM_PROMPT},
            {'role':'user','content':json.dumps(summary,ensure_ascii=False,separators=(',',':'))}
        ],text={'format':{'type':'json_schema','name':'loco_explanation','strict':True,'schema':explanation_schema()}})
        if getattr(response,'status',None)!='completed': return None,'INCOMPLETE_RESPONSE'
        raw=getattr(response,'output_text',None)
        if not raw: return None,'REFUSAL_OR_EMPTY_RESPONSE'
        content=json.loads(raw)
        if not validate_content(content,summary): return None,'INVALID_STRUCTURED_CONTENT'
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
