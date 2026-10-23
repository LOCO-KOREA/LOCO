"""Photo-owned intake observations. A view is a label; photo/body/field own the value."""
import copy
from .contract import PHOTO_VIEWS, POLICY, key
from ergo.pose_contract import PHOTO_SOURCES
from ergo.vision.contract import SOURCE as VISION_SOURCE

PHOTO_POLICY=dict(version='PHOTO_OBSERVATIONS_V1',condition_prefix='photo:',front_boundary_deg=5)
VIEW_LABELS={'LEFT':'왼쪽에서 찍은 사진','RIGHT':'오른쪽에서 찍은 사진','FRONT':'정면·후면 사진'}

def condition(photo_id):return PHOTO_POLICY['condition_prefix']+str(photo_id)

def photo_id(item,views):
    raw=item.get('condition',POLICY['default_condition'])
    if raw.startswith(PHOTO_POLICY['condition_prefix']):
        try:return int(raw[len(PHOTO_POLICY['condition_prefix']):])
        except ValueError:return None
    return item.get('photo_id') or next((views[view] for view in PHOTO_VIEWS if view in views),None)

def view_for(identity,views):return next((view for view in PHOTO_VIEWS if views.get(view)==identity),None)

def label(identity,views):return VIEW_LABELS.get(view_for(identity,views),'등록한 사진')

def bind_aliases(existing,views):
    """Old default manual answers belong only to the primary photo, never to its replacement."""
    result=copy.deepcopy(existing);primary=next((views[view] for view in PHOTO_VIEWS if view in views),None)
    for identity,item in list(result.items()):
        if not item['target'].startswith('manual.') or item.get('condition')!=POLICY['default_condition']:continue
        owner=item.get('photo_id') or primary
        if owner is None:continue
        canonical=key(item['target'],condition(owner))
        if item.get('alias_of') and item.get('state')=='CONFLICT':
            previous=result.get(canonical)
            if previous and previous.get('state')!='CONFLICT' and previous.get('source')==item.get('source') and previous.get('updated_at')==item.get('updated_at'):
                result[canonical]=dict(previous,state='CONFLICT',conflict=copy.deepcopy(item.get('conflict')))
        if not item.get('alias_of'):
            previous=result.get(canonical);ranks={'USER':3,'AI':2,'SAVED':1,'POSE':0,'MOVENET':0}
            newer=not previous or ranks.get(item['source'],0)>ranks.get(previous['source'],0) or ranks.get(item['source'],0)==ranks.get(previous['source'],0) and item.get('updated_at','')>previous.get('updated_at','')
            if newer:result[canonical]=dict(item,condition=condition(owner),photo_id=owner,view=view_for(owner,views),photo_label=label(owner,views))
        result.pop(identity,None)
    for identity,item in list(result.items()):
        if not item['target'].startswith('manual.') or item.get('condition')==POLICY['default_condition']:continue
        owner=photo_id(item,views)
        if owner is None:continue
        item.update(photo_id=owner,photo_active=owner in views.values(),view=view_for(owner,views) or item.get('view'),photo_label=label(owner,views) if owner in views.values() else item.get('photo_label','등록한 사진'))
        if owner==primary:result[key(item['target'])]=dict(item,condition=POLICY['default_condition'],alias_of=identity)
    return result

def fact_for(saved,target,owner,views):
    canonical=saved.get(key(target,condition(owner)))
    if canonical:return canonical
    legacy=saved.get(key(target))
    return legacy if legacy and photo_id(legacy,views)==owner else None

def active(item,views):
    return not item['target'].startswith('manual.') or photo_id(item,views) in views.values()

def observations(preview,views):
    """Keep per-photo originals, including alternatives hidden by the preview's severity merge."""
    result=[]
    def add(row):
        owner=views.get(row.get('view'))
        if owner is not None:
            data=preview.get('views',{}).get(row.get('view'),{})
            result.append(dict(copy.deepcopy(row),photo_id=owner,photo_label=label(owner,views),engine=copy.deepcopy(data.get('engine')),quality=copy.deepcopy(data.get('quality'))))
    per_view=any('measured' in data for data in preview.get('views',{}).values())
    if per_view:
        for view,data in preview.get('views',{}).items():
            for row in data.get('measured',[]):add(dict(row,view=view))
    else:
        def flatten(row):
            add({name:value for name,value in row.items() if name!='alternatives'})
            for other in row.get('alternatives',[]):flatten(other)
        for row in preview.get('measured',[]):flatten(row)
    for view,data in preview.get('views',{}).items():
        for row in data.get('front_measurements',[]):add(dict(row,view=view))
        if data.get('signals',{}).get('seated'):
            proof=copy.deepcopy(data.get('signal_details',{}).get('seated',{}))
            add(dict(scope='COMMON',field='seated',value='YES',view=view,angles=[],low_confidence=bool(proof.get('low_confidence')),boundary_review=False,signal='seated',signal_proof=proof))
    for issue in preview.get('measurement_issues',[]):
        add(dict(scope=issue['scope'],field=issue['field'],value=None,view=issue['view'],angles=[issue['angle']],measurement_diagnostic=issue['code'],measurement_reason=issue['reason']))
    # Old one-photo receipts can attribute an aggregate seated signal unambiguously.
    if len(views)==1 and preview.get('signals',{}).get('seated') and not any(row['field']=='seated' for row in result):
        add(dict(scope='COMMON',field='seated',value='YES',view=next(iter(views)),angles=[],low_confidence=False,boundary_review=False,signal='seated'))
    return result

def add(existing,preview,views):
    from .facts import fact
    from .contract import fields
    result=bind_aliases(existing,views);catalogue={field['target']:field for field in fields()}
    for view,data in preview.get('views',{}).items():
        target='view_'+view;direction=(data.get('guess') or {}).get('forward_direction');old=result.get(key(target))
        source='POSE' if (data.get('engine') or {}).get('provider')=='mediapipe' else 'MOVENET'
        if direction and target in catalogue and (not old or old['state']=='UNKNOWN' and old['source'] in PHOTO_SOURCES):
            result[key(target)]=dict(fact(catalogue[target],direction,source,'사진에서 바라보는 방향 추정'),photo_id=views.get(view),view=view,photo_label=VIEW_LABELS.get(view))
    for measured in observations(preview,views):
        target=f"manual.{measured['scope']}.{measured['field']}";identity=key(target,condition(measured['photo_id']));old=result.get(identity)
        # A later reliable measurement can replace a visual fallback; uncertainty cannot erase it.
        measured_over_vision=bool(old and old['source']==VISION_SOURCE and measured.get('value') is not None
            and not measured.get('low_confidence') and not measured.get('boundary_review') and not measured.get('measurement_diagnostic'))
        if target not in catalogue or old and not (old['state']=='UNKNOWN' and old['source'] in PHOTO_SOURCES or measured_over_vision):continue
        if old and old.get('photo_proof')==measured:continue
        data=preview.get('views',{}).get(measured['view'],{});source='POSE' if (data.get('engine') or {}).get('provider')=='mediapipe' else 'MOVENET'
        quote=' / '.join(str(angle['value_deg'])+'°' for angle in measured.get('angles',[]) if angle.get('value_deg') is not None)
        if not quote:quote=measured.get('measurement_reason') or ('사진에서 앉은 자세 감지' if measured.get('signal')=='seated' else '사진에서 이 자세를 확정하지 못했어요.')
        value=fact(catalogue[target],measured['value'],source,quote,condition(measured['photo_id']))
        value.update(photo_id=measured['photo_id'],view=measured['view'],photo_label=measured['photo_label'],angles=copy.deepcopy(measured.get('angles',[])),photo_proof=copy.deepcopy(measured))
        if measured.get('low_confidence') or measured.get('boundary_review'):value['state']='ESTIMATED'
        if measured.get('measurement_diagnostic'):value['measurement_diagnostic']=measured['measurement_diagnostic']
        elif measured['field']=='wrist_base' and measured.get('boundary_review'):value['measurement_diagnostic']='WRIST_BOUNDARY'
        if measured.get('measurement_reason'):value['measurement_reason']=measured['measurement_reason']
        result[identity]=value
    return bind_aliases(result,views)

def snapshot(preview,views):
    return dict(version=PHOTO_POLICY['version'],observations=observations(preview,views),views={str(owner):dict(photo_id=owner,view=view,photo_label=label(owner,views),engine=copy.deepcopy(preview.get('views',{}).get(view,{}).get('engine')),angles=copy.deepcopy(preview.get('views',{}).get(view,{}).get('angles',[])),world_angles=copy.deepcopy(preview.get('views',{}).get(view,{}).get('world_angles',[])),quality=copy.deepcopy(preview.get('views',{}).get(view,{}).get('quality')),signals=copy.deepcopy(preview.get('views',{}).get(view,{}).get('signals',{})),front=copy.deepcopy(preview.get('views',{}).get(view,{}).get('front',[]))) for view,owner in views.items()})
