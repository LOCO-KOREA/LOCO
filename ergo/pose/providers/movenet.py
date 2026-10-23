"""Legacy MoveNet adapter; tensor contract and topology come from the shared registry."""
import threading
from ergo.pose_contract import COCO_NAMES

_models={}
_lock=threading.RLock()


def infer(image,model_bytes,settings,model_sha256):
    import numpy as np
    import cv2
    from ai_edge_litert.interpreter import Interpreter
    size=settings['input_size'];width,height=image.size;square=max(width,height)
    ox,oy=(square-width)//2,(square-height)//2
    padded=cv2.copyMakeBorder(np.asarray(image),oy,square-height-oy,ox,square-width-ox,cv2.BORDER_CONSTANT,value=(0,0,0))
    values=cv2.resize(padded,(size,size),interpolation=cv2.INTER_LINEAR).astype(np.uint8)[None,...]
    with _lock:
        if model_sha256 not in _models:
            model=Interpreter(model_content=model_bytes);model.allocate_tensors();_models[model_sha256]=model
        model=_models[model_sha256];info=model.get_input_details()[0]
        if list(info['shape'])!=[1,size,size,3] or info['dtype']!=np.uint8:raise ValueError('MoveNet 입력 텐서가 모델 계약과 다릅니다')
        model.set_tensor(info['index'],values);model.invoke()
        raw=model.get_tensor(model.get_output_details()[0]['index']).reshape(len(COCO_NAMES),3).copy()
    points=[dict(point_no=i,name=name,x_px=float(x)*square-ox,y_px=float(y)*square-oy,confidence=float(score),confidence_kind=settings['confidence_kind'])
            for i,(name,(y,x,score)) in enumerate(zip(COCO_NAMES,raw))]
    return dict(points=points,world_points=[],quality=dict(detected=True,detected_persons=1,confidence_kind=settings['confidence_kind']))
