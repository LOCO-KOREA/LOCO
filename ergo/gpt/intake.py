"""One contextual extraction and follow-up request using the shared intake contract."""
import json
from ergo import ai_config as config
from ergo.intake.grounding import DURATION_SUM

PROMPT_VERSION='LOCO_ADAPTIVE_INTAKE_V1'
PROMPT=(
    '현장 작업 설명과 앞선 답변을 입력 항목에 옮기고, 부족한 사실만 추가로 질문하세요. '
    'targets는 허용 항목, known은 저장된 값, missing은 계산기의 누락 후보, asked는 지금 사용자에게 보여 준 질문입니다. '
    'answers는 이번 text 또는 prior_user_text에 명시된 사실만 쓰고 quote는 그 구절을 그대로 복사하세요. '
    '선택 항목의 text에는 choices의 value를 그대로 쓰세요(예: YES, NO, GOOD). label이나 불리언은 쓰지 마세요. '
    '숫자 항목은 number에 숫자를 쓰고 text=null로, 선택/이름 항목은 text에 쓰고 number=null로 하세요. '
    '사용자가 모름이라고 명시한 현재 질문은 number=null,text=UNKNOWN으로 기록하세요. 말하지 않은 항목은 답변 목록에서 빼세요. '
    '질문에 대한 짧은 답은 asked의 항목·단위·condition으로 해석하세요. 명시되지 않은 사실을 추측하지 마세요. '
    '사용자가 모른다고 답한 것은 다시 묻지 마세요. USER 출처의 값을 바꾸지 마세요. '
    '시간은 분, 중량은 kg, 연간 작업일수는 일입니다. 전체 하루 시간과 특정 동작의 시간을 구별하세요. '
    f'derivations에 {DURATION_SUM}이 있는 하루 총시간은 사용자가 하루 일정으로 나열한 서로 다른 작업시간을 합산할 수 있습니다. '
    '예: 손·팔 들기 2시간 하고 키보드 작업 6시간이면 daily_work_min=480입니다. 및·과·문장 나열 등 연결 표현이 달라도 같은 뜻이면 처리하세요. '
    '하루 총시간을 합산할 때 calculation={operation:허용 연산,terms:[{quote:작업별 실제 원문 구절,minutes:분 환산값},...]}를 작성하세요. '
    'terms는 원문 순서대로 서로 다른 작업시간만 넣고 quote에는 모든 피연산자 구절을 포함한 원문을 그대로 복사하세요. '
    '총·전체라는 머리말을 버리지 마세요. 원문에 총합이나 괄호 단위 환산값이 함께 있어도 terms에 같은 시간을 중복해서 넣지 마세요. '
    '1시간 30분·한 시간 삼십분은 각각 90분, 1시간 반도 90분입니다. 복합 단위의 일부만 인용하거나 다른 작업시간으로 분리하지 마세요. '
    '합산이 아닌 단일 시간·모름에는 calculation=null로 쓰세요. calculation을 허용하지 않는 대상에는 그 속성을 쓰지 마세요. '
    '합산에 사용한 작업별 시간도 각각 해당 항목에 따로 저장하고, 이미 계산할 수 있는 하루 총시간을 다시 묻지 마세요. '
    '동시에 하거나 포함·겹치는 시간, 휴식·범위·다른 주기의 시간은 단순 합산하지 마세요. 일부 작업시간만 말했거나 다른 작업시간이 미확인이면 하루 총시간으로 단정하지 마세요. '
    '물건 무게별로 condition을 나눠 같은 조건의 중량·횟수·시간만 연결하세요. 예: 5kg 99번과 30kg 1번은 두 조건입니다. '
    '사진 속 물건 무게(load_kg)와 일반 작업의 물건 무게(card.lift.load_mass_kg)를 같다고 가정하지 마세요. '
    '손잡이·자세·충격·반복·작업 종류는 사용자가 말한 경우에만 선택값으로 옮기세요. 사진 추정은 known에 이미 있습니다. '
    'context는 사진 속 사람이 한 명인지·전신인지·평소 작업 모습인지에 대한 사용자 진술입니다. '
    '예: "사진은 한 사람의 전신이 나온 평소 작업 모습입니다"라고 했으면 context=YES를 answers에 넣고 같은 확인을 다시 질문하지 마세요. '
    '저장할 때 필요한 입력 사실을 모두 추출하세요. 질문을 위해 명시된 사실을 일부러 비워두지 마세요. '
    '같은 작업 조건의 후속 답변에는 known/asked에 있는 기존 condition 이름을 그대로 재사용하세요. '
    '알 수 없는 작업 특징을 NO로 채우지 마세요. 상자를 옮기는 작업만 한다고 해도 그 작업에 허리 굽힘이나 반복이 없다는 뜻이 아닙니다. '
    'ai_writable=false 항목은 화면에서 여러 미확인 특징을 한 번에 직접 답하는 항목이며 answers에 쓰지 마세요. '
    'complete.*는 그 작업의 모든 조건을 기록했다고 사용자가 명시했을 때만 YES입니다. '
    'questions는 answers를 반영한 뒤에도 남는 후보 중 지금 필요한 항목을 question_limit개까지 고르세요. '
    '목록 전체를 채우라고 하지 말고 대화 팝업에서 한 번에 질문 하나만 하세요. '
    'missing은 답변 추출 전 누락일 수 있으므로 answers로 해결한 항목은 제외하고 새로 필요한 질문을 고르세요. '
    'phase=FOLLOWUP에서도 원문에 명시됐으나 known에서 빠진 사실을 발견하면 answers에 기록하세요. '
    '기존 USER 값은 바꾸지 말고, 새 답변을 반영한 뒤에도 남는 missing 중 한 가지 질문만 만드세요. '
    '한 질문은 한 target·condition에 대응하고 이미 알게 된 값은 다시 묻지 마세요. '
    '질문은 조사 용어를 피한 짧은 한국어로, reason은 왜 필요한지 한 문장으로 적으세요. '
    '점수·위험도·법정 해당 여부·조사자 결론은 작성하거나 변경하지 마세요.'
)


def request(payload,schema,model,api_key,settings=None):
    if not api_key: return None,'NO_API_KEY'
    if not model: return None,'MODEL_NOT_CONFIGURED'
    try:
        from openai import OpenAI
        transport,options=config.request_options(model,settings)
        response=OpenAI(api_key=api_key,**transport).responses.create(
            **options,input=[
                dict(role='system',content=PROMPT),dict(role='user',content=json.dumps(payload,ensure_ascii=False,separators=(',',':')))],
            text=dict(format=dict(type='json_schema',name='loco_adaptive_intake',strict=True,schema=schema)))
        if getattr(response,'status',None)!='completed': return None,'INCOMPLETE_RESPONSE'
        raw=getattr(response,'output_text',None)
        if not raw: return None,'REFUSAL_OR_EMPTY_RESPONSE'
        result=json.loads(raw)
        if not isinstance(result,dict) or not isinstance(result.get('answers'),list) or not isinstance(result.get('questions'),list): return None,'INVALID_STRUCTURED_CONTENT'
        result['_connection']=config.connection(response,model,settings)
        return result,None
    except ImportError: return None,'OPENAI_SDK_MISSING'
    except Exception as error:
        from .client import _reason
        return None,_reason(error)
