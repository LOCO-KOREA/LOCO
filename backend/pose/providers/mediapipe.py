"""MediaPipe Tasks IMAGE inference; retains native 33-point and inferred world outputs."""
import atexit
import threading
from backend.pose_contract import MEDIAPIPE_NAMES,NUM_POSES

_instances={}
_lock=threading.RLock()


def close():
    with _lock:
        for task in _instances.values():task.close()
        _instances.clear()


atexit.register(close)


def _sdk():
    import mediapipe as mp
    return mp


def infer(image,model_bytes,settings,model_sha256):
    mp=_sdk()
    import numpy as np
    identity=(model_sha256,settings['detection_min'],settings['presence_min'])
    with _lock:
        if identity not in _instances:
            if len(_instances)>=4:_instances.pop(next(iter(_instances))).close()
            options=mp.tasks.vision.PoseLandmarkerOptions(
                base_options=mp.tasks.BaseOptions(model_asset_buffer=model_bytes),
                running_mode=mp.tasks.vision.RunningMode.IMAGE,num_poses=NUM_POSES,
                min_pose_detection_confidence=settings['detection_min'],min_pose_presence_confidence=settings['presence_min'])
            _instances[identity]=mp.tasks.vision.PoseLandmarker.create_from_options(options)
        result=_instances[identity].detect(mp.Image(image_format=mp.ImageFormat.SRGB,data=np.asarray(image)))
    if not result.pose_landmarks:return dict(points=[],world_points=[],quality=dict(detected=False,detected_persons=0))
    landmarks=result.pose_landmarks[0];world=result.pose_world_landmarks[0]
    if len(landmarks)!=len(MEDIAPIPE_NAMES) or len(world)!=len(MEDIAPIPE_NAMES):raise ValueError('MediaPipe 관절 출력 개수가 계약과 다릅니다')
    width,height=image.size;points=[];world_points=[]
    for index,(name,item,spatial) in enumerate(zip(MEDIAPIPE_NAMES,landmarks,world)):
        visibility=float(item.visibility);presence=float(item.presence)
        common=dict(point_no=index,name=name,confidence=min(visibility,presence),visibility=visibility,presence=presence,confidence_kind=settings['confidence_kind'])
        points.append(dict(common,x_px=float(item.x)*width,y_px=float(item.y)*height,z_normalized=float(item.z)))
        world_points.append(dict(common,x_m=float(spatial.x),y_m=float(spatial.y),z_m=float(spatial.z)))
    return dict(points=points,world_points=world_points,
                quality=dict(detected=True,detected_persons=len(result.pose_landmarks),confidence_kind=settings['confidence_kind'],world_coordinates='INFERRED_HIP_CENTER_METERS'))
