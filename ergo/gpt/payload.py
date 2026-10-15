"""Strict allowlist boundary for GPT explanations. Never serialize user-facing DTOs wholesale."""
import math
import re

PUBLIC_RULE_TEXT=[
 '1호: 집중 자료입력 키보드·마우스 조작이 하루 240분 이상인지 확인한다.',
 '2호: 같은 신체부위의 같은 동작 반복이 하루 120분 이상인지 확인한다.',
 '3호: 손·팔의 해당 자세가 중복 제거 기준 하루 120분 이상인지 확인한다.',
 '4호: 지지되지 않거나 자세 변경이 제한된 상태의 목·허리 굽힘·비틀림이 하루 120분 이상인지 확인한다.',
 '5호: 쪼그리거나 무릎을 굽힌 자세가 하루 120분 이상인지 확인한다.',
 '6호: 비지지 손가락 집기 중량 1kg 이상 또는 힘 2kg 상당 이상, 하루 120분 이상인지 확인한다.',
 '7호: 비지지 한 손 중량 또는 쥐기 힘이 4.5kg 이상, 하루 120분 이상인지 확인한다.',
 '8호: 25kg 이상 물체를 하루 10회 이상 드는지 확인한다.',
 '9호: 10kg 이상 물체를 불편한 위치에서 하루 25회 이상 드는지 확인한다.',
 '10호: 4.5kg 이상을 분당 2회 이상, 하루 120분 이상 드는지 확인한다.',
 '11호: 손·무릎으로 물체에 시간당 10회 이상 실제 충격을, 하루 120분 이상 가하는지 확인한다.',
 '사진 표본 비율은 하루 노출시간이나 법적 해당 확률이 아니다. GPT는 수치나 조사자 판정을 변경할 수 없다.'
]

def build_numeric_summary(analysis):
    snapshot=analysis['snapshot']; result=analysis.get('judgment') or {}; pose=analysis.get('pose') or {}; reba=analysis.get('reba') or {}
    scope=snapshot.get('analysis_scope') or dict(judgment=True,pose=True,tags=True,reba=True)
    targets=[s for s in (snapshot.get('capture') or {}).get('slots',[]) if s.get('analysis_target',snapshot.get('schema_version')!='2.0') and s.get('photo_id') is not None]
    criteria=[]; all_refs=set()
    by_number={x['criterion_no']:x for x in result.get('judgments',[])}
    for number in range(1,12):
        judgment=by_number.get(number); basis=[]; refs=[]
        for index,item in enumerate((judgment or {}).get('basis',[]),1):
            # Replace paths containing row IDs with stable, anonymous references.
            ref=f'C{number:02d}-B{index:02d}'; refs.append(ref); all_refs.add(ref)
            basis.append(dict(item_code=ref,value=item.get('value'),unit=item.get('unit'),operator=item.get('operator'),threshold=item.get('threshold')))
        fields=['criteria.'+str(number)+'.input_needed'] if (judgment or {}).get('missing_fields') else []
        criteria.append(dict(criterion_no=number,computed_status=(judgment or {}).get('computed_status'),investigator_status=(judgment or {}).get('investigator',{}).get('status'),effective_status=(judgment or {}).get('effective_status'),effective_source='INVESTIGATOR' if (judgment or {}).get('investigator',{}).get('status') else 'COMPUTED' if judgment else None,exclusion=(judgment or {}).get('exclusion'),missing_fields=fields,review_reasons=(judgment or {}).get('review_reasons',[]),basis=basis))
    tags=[]
    for tag in analysis.get('tags') or []:
        tags.append(dict(tag=tag.get('tag'),yes_count=tag.get('yes_count'),observed_count=tag.get('observed_count'),valid_pose_count=tag.get('valid_pose_count'),total_slot_count=tag.get('total_slot_count')))
    settings=snapshot.get('settings') or {}
    return dict(schema_version='2.0',purpose='TASK_EXPLANATION',rule_version='|'.join(str(x) for x in [settings.get('burden_rule'),settings.get('reba_rule'),(settings.get('posture_profile') or {}).get('version')]),module_states=analysis.get('module_states') or {},requested_scope=scope,
        pose_quality=dict(target_count=len(targets),valid_count=pose.get('valid_count') if pose else None),
        reba=dict(complete_count=(reba.get('summary') or {}).get('complete_count'),available_max=(reba.get('summary') or {}).get('available_max'),full_max=(reba.get('summary') or {}).get('full_max')),
        tag_counts=tags,criteria=criteria,public_rule_text=PUBLIC_RULE_TEXT)

def explanation_schema():
    string={'type':'string'}; refs={'type':'array','items':string}
    return {'type':'object','additionalProperties':False,'required':['summary','criteria','check_items','improvement_options'],'properties':{
        'summary':string,
        'criteria':{'type':'array','items':{'type':'object','additionalProperties':False,'required':['criterion_no','explanation','basis_refs'],'properties':{'criterion_no':{'type':'integer'},'explanation':string,'basis_refs':refs}}},
        'check_items':refs,
        'improvement_options':{'type':'array','items':{'type':'object','additionalProperties':False,'required':['proposal','basis_refs','needs_confirmation'],'properties':{'proposal':string,'basis_refs':refs,'needs_confirmation':{'type':'boolean'}}}}
    }}

def validate_content(content,summary):
    if not isinstance(content,dict) or set(content)!={'summary','criteria','check_items','improvement_options'}: return False
    if not isinstance(summary,dict) or not isinstance(summary.get('criteria'),list): return False
    criteria=content.get('criteria')
    if not isinstance(criteria,list) or len(criteria)!=11 or not all(isinstance(x,dict) for x in criteria): return False
    if [x.get('criterion_no') for x in criteria]!=list(range(1,12)): return False
    basis_by_criterion={}
    try:
        for criterion in summary['criteria']:
            number=criterion['criterion_no']; basis=criterion['basis']
            if number not in range(1,12) or not isinstance(basis,list): return False
            basis_by_criterion[number]={item['item_code'] for item in basis if isinstance(item,dict) and isinstance(item.get('item_code'),str)}
    except (KeyError,TypeError): return False
    if set(basis_by_criterion)!=set(range(1,12)): return False
    references=set().union(*basis_by_criterion.values())
    refs=[]
    for item in criteria:
        if set(item)!={'criterion_no','explanation','basis_refs'} or not isinstance(item.get('explanation'),str) or not isinstance(item.get('basis_refs'),list): return False
        if any(not isinstance(ref,str) or ref not in basis_by_criterion[item['criterion_no']] for ref in item['basis_refs']): return False
        refs.extend(item['basis_refs'])
    if not isinstance(content.get('improvement_options'),list): return False
    for item in content['improvement_options']:
        if not isinstance(item,dict) or set(item)!={'proposal','basis_refs','needs_confirmation'} or not isinstance(item['proposal'],str) or not isinstance(item['needs_confirmation'],bool) or not isinstance(item['basis_refs'],list): return False
        refs.extend(item['basis_refs'])
    if not isinstance(content['summary'],str) or not isinstance(content['check_items'],list) or not all(isinstance(x,str) for x in content['check_items']): return False
    if any(not isinstance(ref,str) or ref not in references for ref in refs): return False
    sentences=[content['summary'],*content['check_items'],*(x['explanation'] for x in criteria),*(x['proposal'] for x in content['improvement_options'])]
    return numbers_in_text_are_allowed(sentences,summary)

def numbers_in_text_are_allowed(sentences,payload):
    allowed=set()
    def walk(value):
        if isinstance(value,bool) or value is None: return
        if isinstance(value,(int,float)) and math.isfinite(value):
            allowed.add(round(float(value),6)); allowed.add(round(float(value)*100,6)); return
        if isinstance(value,dict):
            for child in value.values(): walk(child)
        elif isinstance(value,list):
            for child in value: walk(child)
    walk(payload)
    pattern=re.compile(r'(?<![\w])[-+]?\d+(?:[.,]\d+)?%?')
    for sentence in sentences:
        for token in pattern.findall(sentence):
            percent=token.endswith('%'); raw=token[:-1] if percent else token
            try: value=float(raw.replace(',','.'))
            except ValueError: return False
            if round(value,6) not in allowed and not percent and round(value*100,6) not in allowed: return False
    return True
