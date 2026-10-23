"""Send actual image bytes through Responses using the shared AI configuration."""
import json
from ergo import ai_config
from . import contract

def observe(image_url,context,model,api_key,settings=None):
    if not api_key:return None,'NO_API_KEY'
    if not model:return None,'MODEL_NOT_CONFIGURED'
    try:
        from openai import OpenAI
        transport,options=ai_config.request_options(model,settings)
        response=OpenAI(api_key=api_key,**transport).responses.create(**options,input=[
            dict(role='system',content=contract.PROMPT),dict(role='user',content=[
                dict(type='input_text',text=json.dumps(context,ensure_ascii=False,separators=(',',':'))),
                dict(type='input_image',image_url=image_url,detail=contract.policy()['detail'])])],
            text=dict(format=dict(type='json_schema',name=contract.RESPONSE_FORMAT_NAME,strict=True,schema=contract.response_schema())))
        if getattr(response,'status',None)!='completed':return None,'INCOMPLETE_RESPONSE'
        text=getattr(response,'output_text',None)
        if not text:return None,'REFUSAL_OR_EMPTY_RESPONSE'
        raw=json.loads(text)
        if not contract.valid(raw):return None,'INVALID_STRUCTURED_CONTENT'
        raw['_connection']=ai_config.connection(response,model,settings)
        raw['_response']=dict(id=getattr(response,'id',None),status=getattr(response,'status',None),
            model=getattr(response,'model',None),output_text=text)
        return raw,None
    except ImportError:return None,'OPENAI_SDK_MISSING'
    except Exception as error:
        from ergo.gpt.client import _reason
        return None,_reason(error)
