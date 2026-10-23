"""One variable field catalogue for the service, model schema and renderer."""
from ergo.engine import quick_assess
from ergo.engine.task_defaults import COMMON, ARM, AUXILIARY_CONDITION_KEYS
from .grounding import DURATION_SUM, calculation_schema

VERSION = 'ADAPTIVE_INTAKE_V1'
SESSION_KEY = AUXILIARY_CONDITION_KEYS[0]
METHODS = dict(contract='intake_contract', session='intake_session', turn='intake_turn')
POLICY = dict(question_limit=1, text_limit=2400, autosave_delay_ms=500, quick_review_interval=5,
              default_condition='default', unknown='UNKNOWN', history_context_chars=None, auto_title_length=60, source_coverage_passes=1)

STATES = ('KNOWN', 'ESTIMATED', 'UNKNOWN', 'CONFLICT')
AI_STATES = ('NOT_REQUESTED', 'CONNECTED', 'ERROR')
SOURCES = ('USER', 'AI', 'POSE', 'MOVENET', 'SAVED', 'VISION')
LATER_GROUPS = ('조사 정보', '작업장 상황', '참여·증상')
PHOTO_VIEWS = ('LEFT', 'RIGHT', 'FRONT')
PHOTO_DESTINATIONS = ('context','view','manual','load','load_kg','load_link')
POLICY.update(optional_photo_destinations=list(PHOTO_DESTINATIONS), form_prompt_limit=3)
LIFT_FIELDS = {8: ('load_mass_kg','lift_count_day'),
               9: ('load_mass_kg','below_knee_count_day','above_shoulder_count_day','extended_arm_count_day','union_count_day'),
               10: ('load_mass_kg','lift_rate_min','minutes')}
YES_NO = [dict(value='YES', label='예'), dict(value='NO', label='아니오')]
REPLY_EXAMPLES = {'kg':'예: 20kg 상자예요.', '회/일':'예: 하루 30번 정도요.', '회/분':'예: 1분에 1번 정도 들어요.',
                  '회/시간':'예: 한 시간에 10번 정도요.', '분':'예: 하루에 30분 정도요.', '분/일':'예: 하루에 30분 정도요.', '일':'예: 1년에 220일 정도요.'}


def fields():
    questions = quick_assess.questions({}, [], {})
    by_id = {q['id']: q for q in questions}
    result = []

    def add(target, label, kind, destination, *, question=None, choices=None, unit='', maximum=None,
            gate=None, priority=50, group='', path=None):
        result.append(dict(target=target, label=label, question=question or label, kind=kind,
                           destination=destination, choices=choices or [], unit=unit, maximum=maximum,
                           gate=gate, priority=priority, group=group, path=path,reply_example=REPLY_EXAMPLES.get(unit,'답변을 편하게 적어 주세요. 여러 내용을 한 번에 말해도 돼요.'),
                           conditioned=destination['type']=='criterion' and bool(destination.get('mapping',{}).get('row') or destination.get('mapping',{}).get('lift'))))

    work = by_id['work_types']
    cards = [q for q in questions if q['kind'] == 'criterion']
    gates = {q['gate']: q.get('criteria') or [q['criterion']] for q in cards}
    for item in work['items']:
        gate = item['key']
        add('work_type.' + gate, item['label'], 'choice', dict(type='work_type', criteria=gates[gate]),
            question=f"{item['label']}도 하나요?", choices=YES_NO, priority=85, group='작업 종류')
    for card in cards:
        if card['mode'] in ('row','lift'):
            add('complete.'+card['gate'], '이 작업의 물건 무게와 작업 조건을 모두 기록했나요?', 'choice',
                dict(type='complete',criteria=card.get('criteria') or [card['criterion']]), choices=YES_NO,
                gate=card['gate'],priority=45,group=card['text'])
        for field in card['fields']:
            add(f"card.{card['gate']}.{field['key']}", field['label'], 'choice' if field['type']=='truth' else 'number',
                dict(type='criterion', criteria=card.get('criteria') or [card['criterion']], mapping=field['to']),
                question=field['label'] if field['label'].endswith('?') else f"{card['text']} · {field['label']}",
                choices=YES_NO if field['type']=='truth' else None, unit=field.get('unit',''),
                maximum=field.get('maximum'),
                gate=card['gate'], priority=35, group=card['text'])
    for qid in ('daily_work_min', 'one_off', 'annual_work_days', 'task_name', 'context', 'load', 'load_kg'):
        q = by_id[qid]
        add(qid, q['text'], q['kind'], dict(q['target']), choices=[c for c in q.get('choices',[]) if c['value']!='UNKNOWN'],
            unit=q.get('unit',''), maximum=q.get('maximum'), priority=5 if qid=='task_name' else 10 if qid=='context' else 30,
            group=q['group'], path='conditions.'+qid if q['target']['type']=='conditions' else None)
    for view in ('LEFT','RIGHT'):
        add('view_'+view, f"{'왼쪽' if view=='LEFT' else '오른쪽'} 사진에서 바라보는 방향", 'choice',
            dict(type='view', view=view), choices=[dict(value='SCREEN_LEFT',label='화면 왼쪽'),dict(value='SCREEN_RIGHT',label='화면 오른쪽')], priority=15)
    add('planned_duration_months','일회성 작업은 몇 개월 동안 하나요?','number',dict(type='conditions',field='planned_duration_months'),
        unit='개월',priority=30,path='conditions.planned_duration_months')
    for scope, names in [('COMMON',COMMON),('LEFT',ARM),('RIGHT',ARM)]:
        for name in names:
            original = next((q for q in questions if q['target'].get('type')=='manual' and q['target'].get('field')==name), None)
            flags = [(q,item,s) for q in questions for item in q.get('items',[]) for s in item.get('sets',[]) if s['field']==name]
            if original:
                label, choices = original['text'], original['choices']
            elif flags:
                _q, item, setting = flags[0]
                label = item['label']
                choices = [dict(value=setting['checked'] or 'YES',label='예'),dict(value=setting['unchecked'],label='아니오')]
            else:
                label, choices = name, YES_NO
            side = '' if scope=='COMMON' else ('왼쪽 ' if scope=='LEFT' else '오른쪽 ')
            add(f'manual.{scope}.{name}', side+label, 'choice', dict(type='manual',scope=scope,field=name),
                choices=[c for c in choices if c['value']!='UNKNOWN'], priority=55, group='사진 자세 보완', path=scope.lower()+'.'+name)
    add('load_link', '사진 속 물건도 설명한 물건과 같은 무게인가요?', 'choice', dict(type='load_link'),
        choices=YES_NO, priority=18, group='사진 속 물건 확인')
    add('other_work', '아직 확인하지 못한 아래 작업 특징이 있나요?', 'choice', dict(type='other_work'),
        choices=[dict(value='NO',label='아래 특징은 모두 없어요'),dict(value='YES',label='해당하는 특징이 있어요')], priority=80, group='나머지 작업 특징')
    for field in result:
        field['ai_writable']=field['target']!='other_work'
        field['photo_scoped']=field['destination']['type']=='manual'
    for field in result: field['derivations']=[DURATION_SUM] if field['target']=='daily_work_min' else []
    return result


def public_contract():
    from .photo_facts import PHOTO_POLICY
    from ergo.vision.contract import public_contract as vision_contract
    return dict(version=VERSION, session_key=SESSION_KEY, methods=METHODS, policy=POLICY,photo_policy=PHOTO_POLICY,
        photo_vision=vision_contract(),states=STATES, sources=SOURCES, ai_states=AI_STATES, fields=fields())


def response_schema(catalogue=None):
    catalogue=catalogue or fields()
    targets = [f['target'] for f in catalogue]
    variants=[]
    for field in (f for f in catalogue if f['ai_writable']):
        numeric=field['kind']=='number'
        text_schema=dict(type=['string','null'])
        if numeric: text_schema['enum']=[None,'UNKNOWN']
        elif field['kind']=='choice': text_schema['enum']=[None,'UNKNOWN']+[str(c['value']) for c in field['choices']]
        answer=dict(type='object',additionalProperties=False,properties=dict(
            target=dict(type='string',enum=[field['target']]),condition=dict(type='string'),
            number=dict(type=['number','null'] if numeric else 'null'),text=text_schema,quote=dict(type='string')))
        if field.get('derivations'):
            answer['properties']['calculation']=calculation_schema(field['derivations'])
        answer['required']=list(answer['properties']); variants.append(answer)
    question = dict(type='object',additionalProperties=False,
        properties=dict(target=dict(type='string',enum=targets),condition=dict(type='string'),text=dict(type='string'),reason=dict(type='string')))
    question['required'] = list(question['properties'])
    return dict(type='object',additionalProperties=False,required=['answers','questions'],properties=dict(
        answers=dict(type='array',items=dict(anyOf=variants),maxItems=100),
        questions=dict(type='array',items=question,maxItems=POLICY['question_limit'])))


def key(target, condition=None):
    return target + '@' + (condition or POLICY['default_condition'])
