"""Optional real MoveNet inference. Missing models yield diagnostics, never fake poses."""
import os
import sys
from pathlib import Path
from .task_defaults import diagnostic
from .images import read_image
from .joint_angles import angles

NAMES=['nose','left_eye','right_eye','left_ear','right_ear','left_shoulder','right_shoulder','left_elbow','right_elbow','left_wrist','right_wrist','left_hip','right_hip','left_knee','right_knee','left_ankle','right_ankle']
_interpreter=None

def interpreter():
    global _interpreter
    if _interpreter is None:
        local_model=Path(__file__).resolve().parents[2]/'models'/'movenet_lightning.tflite'
        configured=os.environ.get('LOCO_MOVENET_MODEL')
        if configured and Path(configured).is_file(): path=configured
        elif local_model.is_file():
            path=str(local_model)
            if configured: print(f'지정한 모델 경로를 읽지 못해 프로젝트 기본 모델을 사용합니다: {configured}',file=sys.stderr)
        else:
            attempted=' / '.join(str(p) for p in [configured,local_model] if p)
            raise RuntimeError(f'MoveNet 모델을 찾지 못했습니다. 확인한 경로: {attempted}. 모델 배치 또는 경로 설정 후 앱을 완전히 종료하고 다시 실행하세요.')
        try: from ai_edge_litert.interpreter import Interpreter
        except ImportError:
            try: from tensorflow.lite.python.interpreter import Interpreter
            except ImportError as error: raise RuntimeError('TFLite 추론 런타임이 설치되지 않았습니다.') from error
        _interpreter=Interpreter(model_path=path); _interpreter.allocate_tensors()
    return _interpreter

def process(slot,snapshot):
    result=dict(slot_no=slot['slot_no'],photo_id=slot['photo_id'],status='INVALID',diagnostics=[],points=[],angles=[])
    if slot['photo_id'] is None:
        result['diagnostics']=[diagnostic('MISSING_PHOTO','사진이 배정되지 않았습니다','capture.slots.photo_id')]; return result
    photo=next((p for p in snapshot['photos'] if p['photo_id']==slot['photo_id']),None)
    try: image=read_image(photo['file_path'] if photo else '')
    except Exception as error:
        result.update(status='ERROR',diagnostics=[diagnostic('UNREADABLE_FILE',str(error))]); return result
    try:
        import numpy as np
        import cv2
        model=interpreter(); info=model.get_input_details()[0]; width,height=image.size
        # RGB comes from Pillow after EXIF correction; OpenCV does not swap channels here.
        # Pad at source resolution, allocating any odd extra pixel to bottom/right.
        square=max(width,height); ox,oy=(square-width)//2,(square-height)//2
        padded=cv2.copyMakeBorder(np.asarray(image),oy,square-height-oy,ox,square-width-ox,cv2.BORDER_CONSTANT,value=(0,0,0))
        resized=cv2.resize(padded,(192,192),interpolation=cv2.INTER_LINEAR)
        if list(info['shape'])!=[1,192,192,3] or info['dtype']!=np.uint8: raise RuntimeError('입력 192×192 uint8 Lightning 모델이 아닙니다')
        values=resized.astype(np.uint8)[None,...]
        model.set_tensor(info['index'],values); model.invoke(); raw=model.get_tensor(model.get_output_details()[0]['index']).reshape(17,3)
        if not np.isfinite(raw).all(): raise RuntimeError('관절 출력에 유한하지 않은 값이 있습니다')
        for index,(y,x,score) in enumerate(raw):
            px=float(x)*square-ox; py=float(y)*square-oy
            result['points'].append(dict(point_no=index,name=NAMES[index],x_px=px,y_px=py,confidence=float(score)))
        side=slot.get('camera_side',snapshot['capture'].get('camera_side')); direction=slot.get('forward_direction',snapshot['capture'].get('forward_direction'))
        observation=slot.get('observation') or {}
        result['angles']=angles(result['points'],direction,width,height)
        context_ok=side in ('LEFT','RIGHT') and direction in ('SCREEN_RIGHT','SCREEN_LEFT') and slot.get('side_view_verified')=='YES' and observation.get('single_person')=='YES' and observation.get('full_frame')=='YES' and observation.get('normal_work')=='YES'
        if side not in ('LEFT','RIGHT') or direction not in ('SCREEN_RIGHT','SCREEN_LEFT'):
            result['diagnostics']=[diagnostic('INVALID_CAMERA','측면 카메라와 작업자 전방 방향을 확인하세요','capture.camera_side')]
        elif not context_ok:
            result['diagnostics']=[diagnostic('CAPTURE_CONTEXT_UNCONFIRMED','측면·단일 작업자·전신·통상 작업 확인을 마쳐야 분석대상으로 사용할 수 있습니다','capture.observation')]
        elif any(angle['value_deg'] is not None for angle in result['angles']): result['status']='VALID'
        else: result['diagnostics']=[diagnostic('LOW_CONFIDENCE','관절 가림·프레임·신뢰도를 확인하세요')]
    except Exception as error: result.update(status='ERROR',diagnostics=[diagnostic('MODEL_ERROR',str(error))])
    return result
