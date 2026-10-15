"""Optional real MoveNet inference. Missing models yield diagnostics, never fake poses."""
import math
import os
import sys
from pathlib import Path
from domain import diagnostic, TAGS

NAMES=['nose','left_eye','right_eye','left_ear','right_ear','left_shoulder','right_shoulder','left_elbow','right_elbow','left_wrist','right_wrist','left_hip','right_hip','left_knee','right_knee','left_ankle','right_ankle']
_interpreter=None

def interpreter():
    global _interpreter
    if _interpreter is None:
        local_model=Path(__file__).resolve().parents[1]/'models'/'movenet_lightning.tflite'
        configured=os.environ.get('LOCO_MOVENET_MODEL')
        if configured and Path(configured).is_file(): path=configured
        elif local_model.is_file():
            path=str(local_model)
            if configured: print(f'지정한 모델 경로를 읽지 못해 샘플 기본 모델을 사용합니다: {configured}',file=sys.stderr)
        else:
            attempted=' / '.join(str(p) for p in [configured,local_model] if p)
            raise RuntimeError(f'MoveNet 모델을 찾지 못했습니다. 확인한 경로: {attempted}. 모델 배치 또는 경로 설정 후 앱을 완전히 종료하고 다시 실행하세요.')
        try: from ai_edge_litert.interpreter import Interpreter
        except ImportError:
            try: from tensorflow.lite.python.interpreter import Interpreter
            except ImportError as error: raise RuntimeError('TFLite 추론 런타임이 설치되지 않았습니다.') from error
        _interpreter=Interpreter(model_path=path); _interpreter.allocate_tensors()
    return _interpreter

def read_image(path):
    from PIL import Image, ImageOps
    with Image.open(path) as image: return ImageOps.exif_transpose(image).convert('RGB')

def angles(points, forward, width, height):
    sign=1 if forward=='SCREEN_RIGHT' else -1
    p={point['name']:point for point in points}; result=[]
    norm=lambda a:(a+180)%360-180
    for side in ['LEFT','RIGHT']:
        prefix=side.lower()+'_'
        def vector(a,b): return (sign*(p[prefix+b]['x_px']-p[prefix+a]['x_px']),-(p[prefix+b]['y_px']-p[prefix+a]['y_px']))
        def tilt(a,b,down=False):
            x,y=vector(a,b)
            if math.hypot(x,y)==0: raise ValueError('길이 0')
            return math.degrees(math.atan2(x,-y if down else y))
        def flex(a,j,b):
            u=vector(j,a); v=vector(j,b); denominator=math.hypot(*u)*math.hypot(*v)
            if denominator==0: raise ValueError('길이 0')
            return 180-math.degrees(math.acos(max(-1,min(1,sum(x*y for x,y in zip(u,v))/denominator))))
        specs=[('TRUNK_TILT_VERT',['hip','shoulder'],lambda:tilt('hip','shoulder')),('NECK_TILT_VERT_PROXY',['shoulder','ear'],lambda:tilt('shoulder','ear')),('NECK_FLEX_TRUNK_PROXY',['hip','shoulder','ear'],lambda:norm(tilt('shoulder','ear')-tilt('hip','shoulder'))),('UPPER_ARM_RAISE_VERT',['shoulder','elbow'],lambda:tilt('shoulder','elbow',True)),('UPPER_ARM_FLEX_TRUNK',['hip','shoulder','elbow'],lambda:norm(tilt('shoulder','elbow',True)+tilt('hip','shoulder'))),('ELBOW_FLEX',['shoulder','elbow','wrist'],lambda:flex('shoulder','elbow','wrist')),('KNEE_FLEX',['hip','knee','ankle'],lambda:flex('hip','knee','ankle'))]
        for code,joints,compute in specs:
            confidence=min(p[prefix+j]['confidence'] for j in joints); value=None; note=None
            in_frame=all(0<=p[prefix+j]['x_px']<width and 0<=p[prefix+j]['y_px']<height for j in joints)
            if confidence<0.5 or not in_frame: note='관절 신뢰도 부족 또는 프레임 밖'
            elif forward is None: note='작업자 진행 방향 미입력'
            else:
                try: value=compute()
                except ValueError as error: note=str(error)
            result.append(dict(side=side,angle_code=code,value_deg=value,min_confidence=confidence,diagnostic=note))
    return result

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

def calculate_tags(snapshot,pose):
    slots=[]; summary=[]; profile=snapshot['settings']['posture_profile']; camera=snapshot['capture']['camera_side']
    mapping={'HAND_ABOVE_HEAD':'hand_above_head','ELBOW_ABOVE_SHOULDER':'elbow_above_shoulder','ELBOW_BEHIND_TRUNK':'elbow_behind_trunk','NECK_TWIST':'neck_twisted','TRUNK_TWIST':'trunk_twisted','SQUAT':'squat','KNEEL':'kneel'}
    for slot in snapshot['capture']['slots']:
        ps=next((p for p in (pose or {}).get('slots',[]) if p['slot_no']==slot['slot_no']),{})
        aa={a['angle_code']:a['value_deg'] for a in ps.get('angles',[]) if a['side']==camera}
        manual={v['field']:v['value'] for v in snapshot['manual'] if v['slot_no']==slot['slot_no'] and v['photo_id']==slot['photo_id'] and v['scope']=='COMMON'}
        for tag in TAGS:
            value='UNKNOWN'; source='UNKNOWN'
            if tag in mapping:
                value=manual.get(mapping[tag],'UNKNOWN'); source='MANUAL' if value in ['YES','NO'] else 'UNKNOWN'
            else:
                code,threshold,reverse={'NECK_FORWARD_PROXY':('NECK_TILT_VERT_PROXY',profile['neck_forward_deg'],False),'TRUNK_FLEX':('TRUNK_TILT_VERT',profile['trunk_flex_deg'],False),'TRUNK_EXT':('TRUNK_TILT_VERT',profile['trunk_extension_deg'],True),'UPPER_ARM_RAISE':('UPPER_ARM_RAISE_VERT',profile['upper_arm_raise_deg'],False)}[tag]
                if aa.get(code) is not None: value='YES' if (aa[code]<=threshold if reverse else aa[code]>=threshold) else 'NO'; source='ANGLE'
            slots.append(dict(slot_no=slot['slot_no'],tag=tag,value=value,source=source))
    for tag in TAGS:
        observed=[s for s in slots if s['tag']==tag and s['value'] in ['YES','NO']]; yes=sum(s['value']=='YES' for s in observed)
        summary.append(dict(tag=tag,yes_count=yes,observed_count=len(observed),valid_pose_count=(pose or {}).get('valid_count',0),manual_observed_count=sum(s['source']=='MANUAL' for s in observed),total_slot_count=15,sample_ratio=yes/len(observed) if observed else None))
    return dict(slots=slots,summary=summary)
