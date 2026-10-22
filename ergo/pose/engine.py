"""Common pose result contract; provider inference never owns REBA or legal scoring."""
import hashlib
import importlib
import math
import os
from pathlib import Path
from threading import RLock
from ergo import pose_contract as contract
from ergo.engine.images import read_image
from ergo.engine.joint_angles import angles
from ergo.engine.task_defaults import diagnostic

PROVIDERS=dict(mediapipe='ergo.pose.providers.mediapipe',movenet='ergo.pose.providers.movenet')
_files={}
_file_lock=RLock()


def _provider(identity):
    return importlib.import_module(PROVIDERS[identity])


def artifact(settings):
    path=Path(settings['model_path'])
    if not path.is_absolute():path=Path(os.environ.get('LOCO_MODELS_ROOT') or Path(__file__).resolve().parents[2])/path
    stat=path.stat();identity=(str(path),stat.st_size,stat.st_mtime_ns)
    with _file_lock:
        if identity not in _files:
            if len(_files)>=4:_files.pop(next(iter(_files)))
            data=path.read_bytes();_files[identity]=(data,hashlib.sha256(data).hexdigest())
        data,digest=_files[identity]
    if settings['model_sha256'] and digest!=settings['model_sha256'].lower():raise ValueError('선택한 자세 모델 파일의 SHA-256이 설정과 다릅니다')
    return path,data,digest


def fingerprint(settings):
    selected=contract.normalize(settings)
    try:path,_,digest=artifact(selected);return dict(settings=selected,path=str(path),sha256=digest)
    except (OSError,ValueError) as error:return dict(settings=selected,artifact_error=str(error))


def world_angles(points,confidence_min):
    by_name={p['name']:p for p in points};result=[]
    for side in ('left','right'):
        for field in contract.WORLD_ANGLES:
            label,names=field['code'],field['joints']
            group=[by_name.get(side+'_'+n) for n in names]
            if any(p is None for p in group):continue
            confidence=min(p['confidence'] for p in group);value=None
            a,j,b=[tuple(p[k] for k in ('x_m','y_m','z_m')) for p in group]
            u=tuple(x-y for x,y in zip(a,j));v=tuple(x-y for x,y in zip(b,j));denominator=math.sqrt(sum(x*x for x in u)*sum(x*x for x in v))
            if confidence>=confidence_min and denominator>0:value=180-math.degrees(math.acos(max(-1,min(1,sum(x*y for x,y in zip(u,v))/denominator))))
            result.append(dict(side=side.upper(),angle_code=label,label=field['label'],value_deg=value,min_confidence=confidence,coordinate_space='INFERRED_WORLD_3D',used_for_reba=False))
    return result


def process(slot,snapshot):
    result=dict(slot_no=slot['slot_no'],photo_id=slot['photo_id'],status='INVALID',diagnostics=[],points=[],angles=[],world_points=[],world_angles=[])
    if slot['photo_id'] is None:
        result['diagnostics']=[diagnostic('MISSING_PHOTO','사진이 배정되지 않았습니다','capture.slots.photo_id')];return result
    photo=next((p for p in snapshot['photos'] if p['photo_id']==slot['photo_id']),None)
    try:image=read_image(photo['file_path'] if photo else '')
    except Exception as error:
        result.update(status='ERROR',diagnostics=[diagnostic('UNREADABLE_FILE',str(error),f"photos.{slot['photo_id']}.file_path")]);return result
    try:
        selected=contract.normalize((snapshot.get('settings') or {}).get('pose_model'))
        path,data,digest=artifact(selected)
        frozen=(snapshot.get('pose_artifact') or {}).get('sha256')
        if frozen and frozen!=digest:raise ValueError('분석 시작 후 자세 모델 파일이 변경되었습니다')
        result['engine']=dict(selected,actual_model_sha256=digest,contract_version=contract.VERSION)
        module=_provider(selected['provider'])
        output=module.infer(image,data,selected,digest)
        names=list(contract.topology(selected['provider'])[0])
        if output['points'] and [p['name'] for p in output['points']]!=names:raise ValueError('관절 이름/순서가 공급자 계약과 다릅니다')
        if selected['provider']=='mediapipe' and output['points'] and [p['name'] for p in output['world_points']]!=names:raise ValueError('3D 관절 이름/개수가 공급자 계약과 다릅니다')
        for point in output['points']:
            if not all(math.isfinite(point[k]) for k in ('x_px','y_px','confidence')) or not 0<=point['confidence']<=1:raise ValueError('관절 출력에 유효하지 않은 좌표/신뢰도가 있습니다')
            if 'z_normalized' in point and not math.isfinite(point['z_normalized']):raise ValueError('관절 깊이 출력이 유한 수가 아닙니다')
            if any(key in point and (not math.isfinite(point[key]) or not 0<=point[key]<=1) for key in ('visibility','presence')):raise ValueError('관절 가시성/존재 확률이 유효하지 않습니다')
        for point in output['world_points']:
            if not all(math.isfinite(point[k]) for k in ('x_m','y_m','z_m')):raise ValueError('3D 관절 출력에 유효하지 않은 좌표가 있습니다')
        if output['points'] and len(output['points'])!=selected['point_count']:raise ValueError('관절 출력 개수가 모델 계약과 다릅니다')
        result.update(output);result['connections']=list(contract.topology(selected['provider'])[1])
        if not result['points']:
            result['diagnostics']=[diagnostic('NO_PERSON','사진에서 자세를 검출하지 못했습니다')];return result
        width,height=image.size;confidence=selected['confidence_min']
        result['angles']=angles(result['points'],slot.get('forward_direction'),width,height,confidence)
        result['world_angles']=world_angles(result['world_points'],confidence)
        side=slot.get('camera_side');direction=slot.get('forward_direction');observation=slot.get('observation') or {}
        prefix=f"capture.slots.{slot['slot_no']}."
        if side not in ('LEFT','RIGHT') or direction not in ('SCREEN_RIGHT','SCREEN_LEFT'):
            result['diagnostics']=[diagnostic('INVALID_CAMERA','측면 카메라와 작업자 전방 방향을 확인하세요',prefix+('camera_side' if side not in ('LEFT','RIGHT') else 'forward_direction'))]
        elif slot.get('side_view_verified')!='YES' or any(observation.get(k)!='YES' for k in ('single_person','full_frame','normal_work')):
            field='side_view_verified' if slot.get('side_view_verified')!='YES' else 'observation.'+next(k for k in ('single_person','full_frame','normal_work') if observation.get(k)!='YES')
            result['diagnostics']=[diagnostic('CAPTURE_CONTEXT_UNCONFIRMED','측면·단일 작업자·전신·통상 작업을 확인하세요',prefix+field)]
        elif any(a['value_deg'] is not None for a in result['angles']):result['status']='VALID'
        else:result['diagnostics']=[diagnostic('LOW_CONFIDENCE','관절 가림·프레임·신뢰도를 확인하세요')]
    except Exception as error:
        result.update(status='ERROR',points=[],angles=[],world_points=[],world_angles=[],diagnostics=[diagnostic('MODEL_ERROR',str(error))])
    return result
