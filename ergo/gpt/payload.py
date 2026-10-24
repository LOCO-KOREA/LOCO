"""Strict allowlist boundary for GPT explanations. Never serialize user-facing DTOs wholesale."""
import hashlib
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

def _safe_number(value):
    if isinstance(value,bool) or not isinstance(value,(int,float)):return None
    try:return value if math.isfinite(value) else None
    except OverflowError:return None


def _reba_risk(total):
    return 'NEGLIGIBLE' if total == 1 else 'LOW' if total <= 3 else 'MEDIUM' if total <= 7 else 'HIGH' if total <= 10 else 'VERY_HIGH'


def _photo_scope_sha256(photo_ids):
    return hashlib.sha256(','.join(str(value) for value in sorted(photo_ids)).encode('ascii')).hexdigest()


def normalize_provisional_reba_input(analysis, value):
    """Validate the transient first-pass score; retain only an opaque scope signature internally."""
    if value is None:
        return None
    if not isinstance(value, dict):
        raise ValueError('provisional_reba must be an object')
    total=value.get('total'); risk=value.get('risk')
    if type(total) is not int or not 1 <= total <= 15 or risk != _reba_risk(total):
        raise ValueError('provisional_reba score or risk is invalid')
    if set(value)=={'total','risk','photo_ids'}:
        photo_ids=value.get('photo_ids')
        if (not isinstance(photo_ids,list) or not photo_ids or
                any(type(photo_id) is not int or photo_id < 1 for photo_id in photo_ids) or
                len(set(photo_ids)) != len(photo_ids)):
            raise ValueError('provisional_reba photo scope is invalid')
        attached={slot.get('photo_id') for slot in (analysis.get('snapshot',{}).get('capture') or {}).get('slots',[])
                  if type(slot.get('photo_id')) is int and slot.get('photo_id') > 0}
        if not set(photo_ids).issubset(attached):
            raise ValueError('provisional_reba refers to a photo outside the analysis snapshot')
        return dict(total=total,risk=risk,photo_count=len(photo_ids),photo_scope_sha256=_photo_scope_sha256(photo_ids))
    if set(value)=={'total','risk','photo_count','photo_scope_sha256'}:
        count=value.get('photo_count'); signature=value.get('photo_scope_sha256')
        if type(count) is not int or count < 1 or not isinstance(signature,str) or not re.fullmatch('[0-9a-f]{64}',signature):
            raise ValueError('saved provisional_reba photo scope is invalid')
        return dict(total=total,risk=risk,photo_count=count,photo_scope_sha256=signature)
    raise ValueError('provisional_reba fields are invalid')


def _provisional_reba_summary(analysis, normalized, targets, analysis_currentness):
    if normalized is None:
        return None
    target_ids=[slot.get('photo_id') for slot in targets]
    same_scope=(len(target_ids)==normalized['photo_count'] and
                normalized['photo_scope_sha256']==_photo_scope_sha256(target_ids))
    reba=(analysis.get('reba') or {}).get('summary') or {}
    completed=reba.get('complete_count')
    final_total=reba.get('full_max')
    final_complete=(bool(target_ids) and type(completed) is int and completed==len(target_ids) and
                    type(final_total) is int and 1<=final_total<=15)
    comparable=analysis_currentness=='CURRENT' and same_scope and normalized['photo_count']==1 and final_complete
    if analysis_currentness=='STALE':
        status='STALE_ANALYSIS'
    elif analysis_currentness!='CURRENT':
        status='CURRENTNESS_UNVERIFIED'
    elif comparable:
        status='COMPARABLE'
    elif not final_complete:
        status='FINAL_INCOMPLETE'
    elif not same_scope:
        status='DIFFERENT_PHOTO_SCOPE'
    else:
        status='MULTI_PHOTO_COMPOSITION'
    return dict(assumption='미확인 자세 항목을 부담 없음으로 가정한 1차 점수',
        initial_total=normalized['total'],initial_risk=normalized['risk'],initial_photo_count=normalized['photo_count'],
        final_photo_count=len(target_ids),same_photo_scope=same_scope,final_complete=final_complete,
        final_total=final_total if final_complete else None,final_risk=_reba_risk(final_total) if final_complete else None,
        analysis_currentness=analysis_currentness,comparable=comparable,comparison_status=status,
        score_delta=(final_total-normalized['total']) if comparable else None)


def _posture_results(analysis,targets):
    pose=analysis.get('pose') or {};reba=analysis.get('reba') or {}
    pose_by_slot={item.get('slot_no'):item for item in pose.get('slots') or []}
    reba_by_slot={item.get('slot_no'):item for item in reba.get('slots') or []}
    output=[]
    for index,slot in enumerate(targets,1):
        number=slot.get('slot_no');p=pose_by_slot.get(number) or {};r=reba_by_slot.get(number) or {}
        angles=[]
        for angle in p.get('angles') or []:
            angles.append(dict(side=angle.get('side'),angle_code=angle.get('angle_code'),value_deg=_safe_number(angle.get('value_deg')),
                min_confidence=_safe_number(angle.get('min_confidence')),diagnostic=angle.get('diagnostic')))
        world_angles=[]
        for angle in p.get('world_angles') or []:
            world_angles.append(dict(side=angle.get('side'),angle_code=angle.get('angle_code'),value_deg=_safe_number(angle.get('value_deg')),
                min_confidence=_safe_number(angle.get('min_confidence')),coordinate_space='INFERRED_WORLD_3D',used_for_reba=False))
        sides={}
        for side in ('left','right'):
            source=r.get(side) or {}
            fields=('trunk','neck','legs','table_a','load_score','score_a','upper_arm','lower_arm','wrist','table_b','coupling_score','score_b','table_c','activity_score','total')
            sides[side]={key:_safe_number(source.get(key)) for key in fields}
            sides[side].update(risk=source.get('risk'),missing_fields=source.get('missing_fields') or [],review_reasons=source.get('review_reasons') or [])
        candidates=[]
        for item in r.get('candidates') or []:
            candidates.append(dict(scope=item.get('scope'),field=item.get('field'),proposed_value=item.get('proposed_value'),
                angle_values_deg=[_safe_number(angle.get('value_deg')) for angle in item.get('angles') or []],
                min_confidence=_safe_number(item.get('min_confidence')),review_reasons=item.get('review_reasons') or []))
        engine=p.get('engine') or {}
        output.append(dict(photo_ref=f'사진 {index}',pose_status=p.get('status'),pose_diagnostic_codes=[d.get('code') for d in p.get('diagnostics') or [] if d.get('code')],
            model=dict(name=engine.get('name') or engine.get('model_id'),version=engine.get('version'),provider=engine.get('provider')) if engine else None,
            landmark_count=len(p.get('points') or []),angles=angles,inferred_world_angles=world_angles,
            reba_status=r.get('status'),effective_load_kg=_safe_number(r.get('effective_load_kg')),selected_side=r.get('selected_side'),
            total=_safe_number(r.get('total')),risk=r.get('risk'),left=sides['left'],right=sides['right'],missing_fields=r.get('missing_fields') or [],
            candidates=candidates))
    return output


def build_numeric_summary(analysis,purpose='TASK_EXPLANATION',provisional_reba=None,analysis_currentness=None):
    if analysis_currentness is None:
        analysis_currentness=analysis.get('currentness')
    if analysis_currentness not in ('CURRENT','STALE'):
        analysis_currentness='UNKNOWN'
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
            def safe_value(value):
                if value is None or value in ('YES','NO','UNKNOWN'): return value
                if isinstance(value,bool) or not isinstance(value,(int,float)): return None
                try: return value if math.isfinite(value) else None
                except OverflowError: return None
            basis.append(dict(item_code=ref,value=safe_value(item.get('value')),unit=item.get('unit'),operator=item.get('operator'),threshold=safe_value(item.get('threshold'))))
        fields=['criteria.'+str(number)+'.input_needed'] if (judgment or {}).get('missing_fields') else []
        criteria.append(dict(criterion_no=number,computed_status=(judgment or {}).get('computed_status'),investigator_status=(judgment or {}).get('investigator',{}).get('status'),effective_status=(judgment or {}).get('effective_status'),effective_source='INVESTIGATOR' if (judgment or {}).get('investigator',{}).get('status') else 'COMPUTED' if judgment else None,exclusion=(judgment or {}).get('exclusion'),missing_fields=fields,review_reasons=(judgment or {}).get('review_reasons',[]),basis=basis))
    tags=[]
    for tag in analysis.get('tags') or []:
        tags.append(dict(tag=tag.get('tag'),yes_count=tag.get('yes_count'),observed_count=tag.get('observed_count'),valid_pose_count=tag.get('valid_pose_count'),total_slot_count=tag.get('total_slot_count')))
    settings=snapshot.get('settings') or {}
    normalized=normalize_provisional_reba_input(analysis,provisional_reba)
    summary=dict(schema_version='2.0',purpose=purpose,rule_version='|'.join(str(x) for x in [settings.get('burden_rule'),settings.get('reba_rule'),(settings.get('posture_profile') or {}).get('version')]),module_states=analysis.get('module_states') or {},requested_scope=scope,
        pose_quality=dict(target_count=len(targets),valid_count=pose.get('valid_count') if pose else None),
        reba=dict(complete_count=(reba.get('summary') or {}).get('complete_count'),available_max=(reba.get('summary') or {}).get('available_max'),full_max=(reba.get('summary') or {}).get('full_max')),
        posture_results=_posture_results(analysis,targets) if scope.get('pose') or scope.get('reba') else [],
        tag_counts=tags,criteria=criteria,public_rule_text=PUBLIC_RULE_TEXT)
    comparison=_provisional_reba_summary(analysis,normalized,targets,analysis_currentness)
    if comparison is not None: summary['provisional_reba']=comparison
    return summary

def reba_comparison_text(summary):
    comparison = summary.get('provisional_reba') if isinstance(summary, dict) else None
    if not comparison:
        return ''
    risk_names = {'NEGLIGIBLE': '무시 가능', 'LOW': '낮음', 'MEDIUM': '보통', 'HIGH': '높음', 'VERY_HIGH': '매우 높음'}
    initial = f"{comparison['initial_total']}점({risk_names.get(comparison.get('initial_risk'), '위험수준 미확인')})"
    if comparison.get('analysis_currentness') != 'CURRENT':
        if comparison.get('final_complete'):
            final = f"{comparison['final_total']}점({risk_names.get(comparison.get('final_risk'), '위험수준 미확인')})"
            return f"1차 가정 REBA는 {initial}입니다. 저장 당시 최종 분석은 {final}이지만 현재 입력과의 점수 차이는 비교하지 않습니다."
        return f"1차 가정 REBA는 {initial}입니다. 저장 당시 최종 REBA가 완성되지 않았고 현재 입력과의 점수 차이는 비교하지 않습니다."
    if not comparison.get('final_complete'):
        return f"1차 가정 REBA는 {initial}입니다. 최종 REBA 계산이 미완성이라 점수 차이를 비교하지 않습니다."
    final = f"{comparison['final_total']}점({risk_names.get(comparison.get('final_risk'), '위험수준 미확인')})"
    if comparison.get('comparable') and type(comparison.get('score_delta')) is int:
        delta = comparison['score_delta']
        direction = '낮아짐' if delta < 0 else '높아짐' if delta > 0 else '같음'
        return (f"1차 가정 REBA는 {initial}, 최종 REBA는 {final}입니다. 같은 단일 사진 범위의 점수 차이는 "
                f"{delta:+d}점({direction})입니다. 점수 차이만으로 개별 답변의 효과를 단정할 수 없습니다.")
    if comparison.get('comparison_status') == 'DIFFERENT_PHOTO_SCOPE':
        return (f"1차 가정 REBA는 {initial}, 최종 분석은 {final}입니다. 사진 범위가 달라 직접 점수 차이를 비교하지 않습니다.")
    return (f"1차 가정 REBA는 {initial}, 최종 분석은 {final}입니다. 여러 사진을 합친 1차 점수와 사진별 최종 계산은 직접 비교하지 않습니다.")


def explanation_schema():
    string={'type':'string'}; refs={'type':'array','items':string}
    posture={'type':'array','items':{'type':'object','additionalProperties':False,'required':['photo_ref','explanation'],'properties':{'photo_ref':string,'explanation':string}}}
    return {'type':'object','additionalProperties':False,'required':['summary','reba_comparison','posture_explanations','criteria','check_items','improvement_options'],'properties':{
        'summary':string,'reba_comparison':string,'posture_explanations':posture,
        'criteria':{'type':'array','items':{'type':'object','additionalProperties':False,'required':['criterion_no','explanation','basis_refs'],'properties':{'criterion_no':{'type':'integer'},'explanation':string,'basis_refs':refs}}},
        'check_items':refs,
        'improvement_options':{'type':'array','items':{'type':'object','additionalProperties':False,'required':['proposal','basis_refs','needs_confirmation'],'properties':{'proposal':string,'basis_refs':refs,'needs_confirmation':{'type':'boolean'}}}}
    }}

def validate_content(content,summary):
    if not isinstance(content,dict) or set(content)!={'summary','reba_comparison','posture_explanations','criteria','check_items','improvement_options'}: return False
    if not isinstance(summary,dict) or not isinstance(summary.get('criteria'),list): return False
    expected_photos=[item.get('photo_ref') for item in summary.get('posture_results') or []]
    if any(not isinstance(ref,str) for ref in expected_photos) or len(set(expected_photos))!=len(expected_photos): return False
    posture=content.get('posture_explanations')
    if not isinstance(posture,list) or len(posture)!=len(expected_photos): return False
    if any(not isinstance(item,dict) or set(item)!={'photo_ref','explanation'} or not isinstance(item.get('photo_ref'),str) or not isinstance(item.get('explanation'),str) for item in posture): return False
    if [item['photo_ref'] for item in posture]!=expected_photos: return False
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
    if not isinstance(content['summary'],str) or not isinstance(content['reba_comparison'],str) or not isinstance(content['check_items'],list) or not all(isinstance(x,str) for x in content['check_items']): return False
    if bool(summary.get('provisional_reba')) != bool(content['reba_comparison'].strip()): return False
    if any(not isinstance(ref,str) or ref not in references for ref in refs): return False
    sentences=[content['summary'],content['reba_comparison'],*(x['explanation'] for x in posture),*content['check_items'],*(x['explanation'] for x in criteria),*(x['proposal'] for x in content['improvement_options'])]
    return numbers_in_text_are_allowed(sentences,summary)

def numbers_in_text_are_allowed(sentences,payload):
    allowed=set()
    pattern=re.compile(r'(?<![\w])[-+]?\d+(?:[.,]\d+)?%?')
    def add_text_numbers(text):
        # The summary's own public criterion sentences quote thresholds (e.g. 4.5kg); quoting them is not inventing.
        for token in pattern.findall(text):
            try: number=float(token.rstrip('%').replace(',','.'))
            except ValueError: continue
            if math.isfinite(number): allowed.add(round(number,6))
    def walk(value):
        if isinstance(value,str): add_text_numbers(value); return
        if isinstance(value,bool) or value is None: return
        if isinstance(value,(int,float)) and math.isfinite(value):
            allowed.add(round(float(value),6)); allowed.add(round(float(value)*100,6)); return
        if isinstance(value,dict):
            for child in value.values(): walk(child)
        elif isinstance(value,list):
            for child in value: walk(child)
    walk(payload)
    for sentence in sentences:
        for token in pattern.findall(sentence):
            percent=token.endswith('%'); raw=token[:-1] if percent else token
            try: value=float(raw.replace(',','.'))
            except ValueError: return False
            if round(value,6) not in allowed and not percent and round(value*100,6) not in allowed: return False
    return True
