"""OpenAI Responses client with a strict, non-judgment schema."""
import copy
import json
from ergo import ai_config as config
from .client_pool import create_response
from .intake import request as adaptive_intake
from .payload import explanation_schema, reba_comparison_text, validate_content
from ergo.user_language import TERMS

PROMPT_VERSION='LOCO_NUMERIC_EXPLANATION_V16'
SYSTEM_PROMPT=(
    '당신은 현장 조사자가 계산 결과를 이해하도록 돕는 설명 작성자입니다. '
    '사용자 입력·사진을 추측하지 말고 제공된 숫자 요약과 공개 기준 문장만 사용하세요. '
    '계산 상태와 조사자 결론을 그대로 설명하고 기준 해당 여부를 새로 판정하거나 점수·노출시간을 변경하지 마세요. '
    '기술태그나 REBA를 법적 판단으로 표현하지 마세요. 확인이 필요한 사실은 확인 항목으로 제시하세요. '
    '개선 제안은 일반적인 검토 선택지로 쓰고, 실제 적용 전 조사자 확인이 필요하다고 표시하세요. '
    '모든 수치는 입력 요약 안의 값만 사용하고, 근거 없는 수치는 쓰지 마세요. '
    '각도는 display_value_deg의 소수 한 자리 표시값, 관절 신뢰도 백분율은 display_confidence_percent를 사용하세요. 원시 각도·신뢰도는 계산 근거이며 중량·시간·횟수 등 다른 입력을 임의 반올림하지 마세요. '
    'recorded_work_inputs는 실제 저장된 작업시간·횟수·중량·작업조건 입력입니다. field와 고정 label/unit으로 뜻을 구분하고 익명 condition_ref가 다른 조건의 값을 합치지 마세요. '
    '전체 작업시간·연간 작업일수·하루 횟수는 작업 맥락이며, 특정 자세 노출시간이나 REBA 활동 가산점으로 다시 환산하지 마세요. REBA 활동은 같은 사진의 recorded_inputs와 엔진 current_score를 그대로 설명하세요. '
    '입력한 작업시간·횟수·연간 작업일수는 summary에 실제 값으로 짧게 반영하고, 기록된 값이 있는데도 미입력이라고 말하지 마세요. 알려진 0과 NO도 실제 응답입니다. '
    '기준별 추가 확인은 missing_fields와 review_reasons에 실제 남은 항목으로 한정하세요. '
    'computed_status가 APPLICABLE·NOT_APPLICABLE·EXCLUDED이고 두 목록이 모두 비었으면 선택적 근거의 null·UNKNOWN을 별도의 필수 미입력으로 만들지 마세요. '
    'investigator_status나 effective_status만으로 미완성 계산이 완료되었다고 간주하지 마세요. '
    'recorded_work_inputs의 같은 조건 값을 다시 입력하라고 하거나, effective_source가 INVESTIGATOR인 저장된 해당·비해당 결론을 다시 선택하라고 하지 마세요. '
    '조사자 결론과 계산의 미완성은 구분해서 설명하세요. 전체 120회와 위치별 횟수처럼 서로 다른 조건의 값은 같은 입력으로 간주하지 마세요. '
    'unknown_work_inputs와 사진별 unknown_inputs는 사용자가 모름으로 답한 항목이며 value=null은 0이나 아니오가 아닙니다. 아예 묻지 않은 항목과 구분하고 이미 답한 모름을 다시 입력하라고 하지 마세요. '
    'posture_results가 있으면 posture_explanations에 각 photo_ref를 입력 순서대로 빠짐없이 한 번씩 넣고 그 사진의 측정 관절 수/토폴로지 수, 신뢰도 수준, 좌우 REBA 결과·누락을 설명하세요. 관절 신뢰도는 검출 신뢰도일 뿐 REBA 정확도 보증이 아닙니다. '
    '각 사진의 current_score는 엔진이 계산한 그 사진의 현재 표시 점수입니다. 전체 최대 점수를 다른 사진의 점수로 쓰거나 기록된 입력으로 점수를 다시 계산하지 마세요. '
    'recorded_inputs는 같은 사진에 저장된 자세·잡기·충격·유지·반복 입력입니다. INTERVIEW는 설명에서 입력한 값, DIRECT_OBSERVATION은 조사자 관찰, AUTO_ACCEPTED는 사진 후보임을 구분하세요. '
    '확인한 잡기·활동 입력은 결과 설명에 반영하고, 좌우 확정 구성점수가 미완성이어도 이 입력까지 없다고 말하지 마세요. recorded_inputs에 없는 항목은 다른 사진에서 빌리거나 추측하지 마세요. '
    'summary에는 전체 자세 결과의 핵심을 짧게 설명하세요. 미측정·누락은 0으로 바꾸지 마세요. '
    '3D 추정각은 used_for_reba가 true인 항목만 현재 점수 초안에 사용한 것으로 설명하고, false인 항목은 참고로 분리하세요. '
    '3D 추정값 사용을 사람이 확정한 측정이나 정확도 보증으로 표현하지 마세요. '
    '사진 표본 결과를 하루 노출량이나 법적 해당 판단으로 바꾸지 마세요. '
    'provisional_reba가 있으면 reba_comparison에 1차 부담 없음 가정과 최종 저장 결과의 관계를 설명하세요. '
    'score_delta가 있을 때만 점수 차이를 말하세요. 사진 범위가 다르거나 여러 사진을 합친 1차 계산이면 답변만의 효과라고 설명하지 마세요. '
    'analysis_currentness가 CURRENT가 아니면 최종 결과는 저장 당시의 과거 분석이라고 밝히고 현재 입력과의 차이나 답변 효과를 추론하지 마세요. '
    '최종 점수가 미완성이면 0점으로 말하지 말고 누락 사유를 설명하세요. provisional_reba가 없으면 reba_comparison은 빈 문자열이어야 합니다. '
    'reba.current_score.kind가 ASSUMED_REFERENCE면 점수는 부담 없음 참조 가정이며 측정값·확정 점수로 표현하지 마세요. WITH_ASSUMPTIONS면 가정 포함 현재 점수라고 설명하세요. CONFIRMED만 완성 계산 점수입니다. '
    'reba.current_score가 있으면 이를 사진의 현재 표시 점수로 설명하고, first_pass는 같은 사진의 답변 전 기준값으로 분리하세요. '
    'reba.score_so_far가 있으면 지금까지 확인한 값 기준의 확정 전 점수이며 assumed_count개 항목을 부담 없음으로 가정했다고 밝히세요. '
    'unconfirmed_photo_count가 있으면 사진 상황을 확인하기 전의 사진 값이 그만큼 들어 있다고, load_assumed가 있으면 물건 무게가 미확인이라 하중 가산점을 0으로 가정했다고 함께 밝히세요. 물건을 들지 않았다고 단정하지 마세요. '
    '실제 점수는 현재 가정 점수보다 높거나 낮을 수 있다고 말하고, 최종 점수나 조사자 결론처럼 말하지 마세요. '
    'posture_explanations는 입력에 있는 모든 사진 참조를 같은 순서로 반환하세요. 없는 사진을 추가하거나 사진 참조를 바꾸지 마세요. ' 'basis_refs에는 요약의 근거 코드(item_code, 예: C01-B01)만 그대로 쓰고 값이나 설명을 덧붙이지 마세요. '
    '해당 여부를 확정하거나 "판정되었다"고 단정하지 말고 "계산 초안으로는 해당"처럼 초안·후보 표현을 쓰세요. '
    'criteria에는 1호부터 11호까지 11개 항목을 빠짐없이 순서대로 쓰세요. 입력이 없거나 해당 여부와 무관한 호도 한 문장으로 상태만 설명하세요. 한국어로 간결하게 답하세요. '
    '각 criteria의 proposed_status는 사람이 검토할 비구속 참고 선택이며 최종 판정이 아닙니다. APPLICABLE·NOT_APPLICABLE·UNDETERMINED 중 하나로 쓰고 explanation과 basis_refs로 사유를 설명하세요. '
    '중량·시간·횟수나 해당 기준의 증거가 부족하면 UNDETERMINED로 두세요. 모름이나 사진에서 안 보임을 NOT_APPLICABLE로 발명하지 마세요. 제안으로 계산·기존 조사자 결론·점수·입력값을 바꾸지 마세요. '
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
        options=config.request_options(model,settings)
        response=create_response(api_key,**options,input=[
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

def explanation_request_summary(summary):
    """Hide unused unknown basis only in the model view; preserve audit/currentness data."""
    request=copy.deepcopy(summary)
    for criterion in request.get('criteria',[]):
        if (isinstance(criterion,dict) and
                criterion.get('computed_status') in ('APPLICABLE','NOT_APPLICABLE','EXCLUDED') and
                criterion.get('missing_fields')==[] and criterion.get('review_reasons')==[] and
                isinstance(criterion.get('basis'),list)):
            criterion['basis']=[item for item in criterion['basis'] if not (
                isinstance(item,dict) and 'value' in item and item['value'] in (None,'UNKNOWN'))]
    return request


def generate(summary, model, api_key, settings=None):
    if not api_key: return None,'NO_API_KEY'
    if not model: return None,'MODEL_NOT_CONFIGURED'
    try:
        options=config.request_options(model,settings)
        response=create_response(api_key,**options,input=[
            {'role':'system','content':SYSTEM_PROMPT},
            {'role':'user','content':json.dumps(explanation_request_summary(summary),ensure_ascii=False,separators=(',',':'))}
        ],text={'format':{'type':'json_schema','name':'loco_explanation','strict':True,'schema':explanation_schema()}})
        if getattr(response,'status',None)!='completed': return None,'INCOMPLETE_RESPONSE'
        raw=getattr(response,'output_text',None)
        if not raw: return None,'REFUSAL_OR_EMPTY_RESPONSE'
        content=json.loads(raw)
        # This field is always replaced by the engine's comparison. Normalize
        # its text before validation while preserving missing/wrong-type errors.
        if isinstance(content,dict) and isinstance(content.get('reba_comparison'),str):
            content['reba_comparison']=reba_comparison_text(summary)
        if not validate_content(content,summary,allow_legacy=False): return None,'INVALID_STRUCTURED_CONTENT'
        # Score direction is deterministic; never expose the model-authored comparison.
        content['reba_comparison']=reba_comparison_text(summary)
        content['_connection']=config.connection(response,model,settings)
        return content,None
    except ImportError: return None,'OPENAI_SDK_MISSING'
    except Exception as error:
        name=type(error).__name__
        if 'Timeout' in name: return None,'TIMEOUT'
        if name in ('JSONDecodeError',): return None,'INVALID_STRUCTURED_CONTENT'
        return None,'API_ERROR'

def _recorded_input_text(summary):
    """Local explanation of the same allowlisted inputs sent to the model."""
    from ergo.intake.contract import fields
    import re
    catalogue={field['target']:field for field in fields()}
    work_labels=dict(daily_work_min='하루 총 작업시간',annual_work_days='연간 작업일수',one_off='일회성 작업 여부',planned_duration_months='예정 작업기간')
    work_labels.update({'card.trunk_neck.unsupported':'몸통·목 지지 없음','card.trunk_neck.posture_restricted':'자세 변경 제한',
        'card.pinch.unsupported':'집기 작업의 손 지지 없음','card.grip.unsupported':'쥐기 작업의 손 지지 없음',
        'card.impact.impact_verified':'실제 충격 여부','card.impact.impact_rate_hour':'시간당 충격 횟수',
        'card.lift.lift_rate_min':'드는 빈도'})
    pose_labels=dict(trunk_base='몸통 기본 자세',neck_base='목 기본 자세',knee_band='무릎 굽힘',
        upper_arm_base='위팔 자세',lower_arm_base='아래팔 자세',wrist_base='손목 굽힘·폄',coupling='손잡이·잡는 상태')
    def phrase(row,*,photo=False):
        target=f"manual.{row.get('scope')}.{row.get('field')}" if photo else row.get('field')
        field=catalogue.get(target)
        if field is None:return None
        value=row.get('value')
        if row.get('state')=='UNKNOWN':rendered='모름으로 응답'
        elif field['kind']=='number':
            if type(value) not in (int,float):return None
            rendered=f"{value:g}{field.get('unit') or ''}"
        else:
            rendered=next((item['label'] for item in field.get('choices') or [] if item['value']==value),None)
            if rendered is None:return None
        condition=row.get('condition_ref') or ''
        prefix=condition+' · ' if isinstance(condition,str) and re.fullmatch(r'작업 조건 \d+',condition) else ''
        label=field['label'].rstrip(' ?')
        if photo and row.get('field') in pose_labels:
            label=({'LEFT':'왼쪽 ','RIGHT':'오른쪽 '}.get(row.get('scope'),''))+pose_labels[row['field']]
        elif target.startswith('complete.'):label='작업 조건 전체 기록 여부'
        elif target in work_labels:label=work_labels[target]
        return prefix+label+': '+rendered
    work=[text for row in [*(summary.get('recorded_work_inputs') or []),*(summary.get('unknown_work_inputs') or [])] if (text:=phrase(row))]
    paragraphs=['입력한 작업 정보: '+'; '.join(work)+'.'] if work else []
    for photo in summary.get('posture_results') or []:
        inputs=[text for row in [*(photo.get('recorded_inputs') or []),*(photo.get('unknown_inputs') or [])] if (text:=phrase(row,photo=True))]
        label=photo.get('photo_ref')
        if inputs and isinstance(label,str) and re.fullmatch(r'사진 \d+',label):paragraphs.append(label+'의 저장 입력: '+'; '.join(inputs)+'.')
    return '\n\n'.join(paragraphs)


def fallback_text(summary):
    text='수치 요약의 입력 누락과 추가 확인 항목을 검토하세요. 사진 표본 비율은 하루 노출시간이 아니며, 계산 결과와 조사자 결론은 별도로 확인해야 합니다.'
    risk_names={'NEGLIGIBLE':'무시 가능','LOW':'낮음','MEDIUM':'보통','HIGH':'높음','VERY_HIGH':'매우 높음'}
    reba_summary=(summary.get('reba') or {}) if isinstance(summary,dict) else {}
    current=reba_summary.get('current_score')
    if current:
        risk_text=risk_names.get(current.get('risk'),'위험수준 미확인')
        if current.get('kind')=='ASSUMED_REFERENCE':
            text+=f" 현재 REBA 참조값은 {current['total']}점({risk_text})이며, 관측·답변 근거가 부족해 부담 없음으로 둔 값입니다. 측정값이나 확정 점수가 아닙니다."
        elif current.get('kind')=='CONFIRMED':
            text+=f" 현재 완성 계산 REBA는 {current['total']}점({risk_text})입니다."
        else:
            so_far=reba_summary.get('score_so_far') or {}
            source={'ANSWERS_SO_FAR':'지금까지 확인한 값','FIRST_PASS':'사진 1차 측정값'}.get(current.get('source'),'현재 확인값')
            photo=f" 사진 확인 전 값 {so_far['unconfirmed_photo_count']}개를 포함하고" if so_far.get('unconfirmed_photo_count') else ''
            assumed_count=so_far.get('assumed_count',current.get('assumed_count',0))
            load=' 물건 무게가 미확인이라 하중 가산점을 0으로 가정했으며,' if current.get('load_assumed') or so_far.get('load_assumed') else ''
            text+=f" {source} 기준 REBA는 {current['total']}점({risk_text})이며,{photo} 확인하지 못한 {assumed_count}개 항목을 부담 없음으로 가정한 확정 전 점수입니다. 확정 점수가 아닙니다.{load} 실제 점수는 이 점수보다 높거나 낮을 수 있습니다."
    else:
        so_far=reba_summary.get('score_so_far')
        if so_far:
            photo=f" 사진 확인 전 값 {so_far['unconfirmed_photo_count']}개를 포함하고" if so_far.get('unconfirmed_photo_count') else ''
            load=' 물건 무게가 미확인이라 하중 가산점을 0으로 가정했으며,' if so_far.get('load_assumed') else ''
            text+=f" 지금까지 확인한 값 기준 REBA는 {so_far['total']}점({risk_names.get(so_far['risk'],'위험수준 미확인')})이며,{photo} 확인하지 못한 {so_far['assumed_count']}개 항목을 부담 없음으로 가정한 확정 전 점수입니다.{load} 실제 점수는 이 점수보다 높거나 낮을 수 있습니다."
    quality=(summary.get('pose_quality') or {}) if isinstance(summary,dict) else {}
    if quality.get('total_points'):
        quality_names={'HIGH':'높음','MEDIUM':'보통','LOW':'낮음','MISSING':'측정 없음'}
        level=quality_names.get(quality.get('confidence_level'),'확인 중')
        text+=f" 관절 측정은 {quality.get('measured_points',0)}/{quality['total_points']}개이며 신뢰도 수준은 {level}입니다. 이는 모델 검출 신뢰도이지 REBA 정확도 보증이 아닙니다."
    recorded=_recorded_input_text(summary) if isinstance(summary,dict) else ''
    if recorded:text+='\n\n'+recorded
    comparison=summary.get('provisional_reba') if isinstance(summary,dict) else None
    if not comparison: return text
    parts=[f"미확인 자세 항목을 부담 없음으로 가정한 1차 REBA는 {comparison['initial_total']}점({risk_names.get(comparison['initial_risk'],'위험수준 미확인')})입니다."]
    if comparison.get('analysis_currentness') != 'CURRENT':
        if comparison.get('final_complete'):
            parts.append(f"저장 당시 분석은 {comparison['final_total']}점({risk_names.get(comparison['final_risk'],'위험수준 미확인')})이지만 현재 작업 입력에 대한 결과가 아닙니다.")
        else:
            parts.append('저장 당시 REBA가 완성되지 않았고 현재 작업 입력과도 다를 수 있습니다.')
        parts.append('현재 입력과의 점수 차이는 계산하지 않았습니다.')
        return text+' '+' '.join(parts)
    if comparison.get('final_complete'):
        parts.append(f"최종 저장 분석은 {comparison['final_total']}점({risk_names.get(comparison['final_risk'],'위험수준 미확인')})입니다.")
        if comparison.get('comparable'):
            delta=comparison['score_delta']
            parts.append(f"같은 단일 사진의 두 점수 차이는 {delta:+d}점이며, 답변 하나의 영향으로 단정할 수 없습니다.")
        elif comparison.get('comparison_status')=='DIFFERENT_PHOTO_SCOPE':
            parts.append(f"1차는 사진 {comparison['initial_photo_count']}장, 최종 분석은 사진 {comparison['final_photo_count']}장 대상이라 범위가 달라 점수 차이를 계산하지 않았습니다.")
        else:
            parts.append('여러 사진을 합친 1차 점수와 사진별 최종 계산은 직접 점수 차이로 비교하지 않았습니다.')
    else:
        parts.append(f"최종 REBA는 대상 사진 {comparison['final_photo_count']}장 중 완성되지 않은 사진이 있어 전체 점수를 계산하지 않았습니다. 1차와 최종을 점수 차이로 비교하지 않았습니다.")
    return text+' '+' '.join(parts)


def content_text(content):
    if not content: return None
    parts=[content.get('summary','')]
    if content.get('reba_comparison'): parts.append('REBA 현재 점수와 계산 설명: '+content['reba_comparison'])
    if content.get('posture_explanations'):
        parts.append('사진별 자세·REBA 설명:')
        parts.extend(f"{item['photo_ref']}: {item['explanation']}" for item in content['posture_explanations'])
    parts.extend(f"{item['criterion_no']}호: {item['explanation']}" for item in content.get('criteria',[]))
    if content.get('check_items'): parts.append('확인할 항목: '+'; '.join(content['check_items']))
    if content.get('improvement_options'): parts.append('개선 검토 선택지: '+'; '.join(x['proposal'] for x in content['improvement_options']))
    return '\n'.join(x for x in parts if x)
