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
        values=resized.astype(info['dtype'])[None,...]
        if list(info['shape'])!=[1,192,192,3]: raise RuntimeError('192×192 Lightning 모델이 아닙니다')
        model.set_tensor(info['index'],values); model.invoke(); raw=model.get_tensor(model.get_output_details()[0]['index']).reshape(17,3)
        for index,(y,x,score) in enumerate(raw):
            px=float(x)*square-ox; py=float(y)*square-oy
            result['points'].append(dict(point_no=index,name=NAMES[index],x_px=px,y_px=py,confidence=float(score)))
        result['angles']=angles(result['points'],snapshot['capture']['forward_direction'],width,height)
        side=snapshot['capture']['camera_side']; direction=snapshot['capture']['forward_direction']
        if not side or not direction: result['diagnostics']=[diagnostic('MISSING_CAMERA','카메라 측면과 작업자 진행 방향을 입력하세요')]
        elif all(p['confidence']>=0.5 and 0<=p['x_px']<width and 0<=p['y_px']<height for p in result['points'] if p['name'] in [side.lower()+'_'+j for j in ['ear','shoulder','elbow','wrist','hip','knee','ankle']]): result['status']='VALID'
        else: result['diagnostics']=[diagnostic('LOW_CONFIDENCE','가까운 쪽 관절 가림·프레임·신뢰도를 확인하세요')]
    except Exception as error: result.update(status='ERROR',diagnostics=[diagnostic('MODEL_ERROR',str(error))])
    return result
