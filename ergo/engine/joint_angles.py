"""Signed original-pixel joint angles from functional specification section 3."""
import math
from .wrist_angles import angles as wrist_angles

def angles(points, forward, width, height, confidence_min=0.5, *, camera_side=None, orientation=None, wrist_policy=None):
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
            if confidence<confidence_min or not in_frame: note='관절 신뢰도 부족 또는 프레임 밖'
            elif forward is None: note='작업자 진행 방향 미입력'
            else:
                try: value=compute()
                except ValueError as error: note=str(error)
            result.append(dict(side=side,angle_code=code,value_deg=value,min_confidence=confidence,diagnostic=note))
    return result+wrist_angles(points,width,height,confidence_min,camera_side=camera_side,orientation=orientation,policy=wrist_policy)
