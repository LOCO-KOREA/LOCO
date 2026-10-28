"""Conservative image-plane wrist flexion/extension proxy; never a twist measure.

Side-body capture alone does not establish hand orientation. Finger-axis and
projected-width checks reject broad palm views, curled/mismatched and short
projections. Passing these heuristics is not clinical validation of the angle.
No inferred depth or world coordinate enters this module.
"""
import math
from backend.pose_contract import WRIST_JOINTS, WRIST_POLICY, WRIST_REASONS


def _angle(u, v):
    denominator=math.hypot(*u)*math.hypot(*v)
    numerator=sum(a*b for a,b in zip(u,v))
    if denominator<=0 or not math.isfinite(denominator) or not math.isfinite(numerator): raise ValueError('unstable projection')
    return math.degrees(math.acos(max(-1.0,min(1.0,numerator/denominator))))


def _minus(a,b): return (a[0]-b[0],a[1]-b[1])


def _bend(xy):
    center=tuple((xy['index'][i]+xy['pinky'][i])/2 for i in (0,1))
    return _angle(_minus(xy['wrist'],xy['elbow']),_minus(center,xy['wrist']))


def angles(points,width,height,confidence_min=0.5,*,camera_side=None,orientation=None,policy=None):
    policy={**WRIST_POLICY,**(policy or {})}
    by_name={point['name']:point for point in points}
    # COCO/MoveNet has no hand landmarks: retain its previous angle behaviour.
    if not any(side+'_'+joint in by_name for side in ('left','right') for joint in ('index','pinky','thumb')): return []
    result=[]
    for side in ('LEFT','RIGHT'):
        group={joint:by_name.get(side.lower()+'_'+joint) for joint in WRIST_JOINTS['mediapipe']}
        proof=dict(policy_version=policy['version'],coordinate_space=policy['coordinate_space'],auto_eligible=False,
                   hand_plane_method='PROJECTED_HAND_EDGE_HEURISTIC',used_world_coordinates=False,policy=dict(policy))
        row=dict(side=side,angle_code=policy['angle_code'],value_deg=None,min_confidence=None,diagnostic=None,measurement=proof)
        def reject(code):
            row.update(diagnostic_code=code,diagnostic=WRIST_REASONS[code]);result.append(row)
        if any(point is None for point in group.values()): reject('WRIST_MISSING_POINTS');continue
        row['min_confidence']=min(min(point.get('confidence',0),point.get('visibility',0),point.get('presence',0)) for point in group.values())
        if row['min_confidence']<max(confidence_min,policy['confidence_min']): reject('WRIST_POINTS_LOW_CONFIDENCE');continue
        margin=policy['frame_margin_px']
        if not all(margin<=point['x_px']<width-margin and margin<=point['y_px']<height-margin for point in group.values()): reject('WRIST_HAND_OUT_OF_FRAME');continue
        if side!=camera_side or orientation!='SIDE': reject('WRIST_DIRECTION_UNCONFIRMED');continue
        xy={joint:(point['x_px'],point['y_px']) for joint,point in group.items()}
        vectors={joint:_minus(xy[joint],xy['wrist']) for joint in ('index','pinky','thumb')}
        forearm=math.dist(xy['elbow'],xy['wrist'])
        center=tuple((xy['index'][i]+xy['pinky'][i])/2-xy['wrist'][i] for i in (0,1));hand=math.hypot(*center)
        lengths={joint:math.hypot(*vector) for joint,vector in vectors.items()}
        proof.update(forearm_px=forearm,hand_px=hand)
        if forearm<policy['forearm_min_px'] or min(lengths.values())<policy['hand_min_px'] or not policy['hand_forearm_min_ratio']<=hand/forearm<=policy['hand_forearm_max_ratio']:
            reject('WRIST_PROJECTION_SHORT');continue
        finger_ratio=min(lengths['index'],lengths['pinky'])/max(lengths['index'],lengths['pinky'])
        difference=_angle(vectors['index'],vectors['pinky'])
        hand_width_ratio=abs(center[0]*(xy['index'][1]-xy['pinky'][1])-center[1]*(xy['index'][0]-xy['pinky'][0]))/(hand*hand)
        proof.update(finger_axis_difference_deg=difference,projected_hand_width_ratio=hand_width_ratio)
        if hand_width_ratio>policy['hand_width_max_ratio']: reject('WRIST_PLANE_UNCLEAR');continue
        if finger_ratio<policy['finger_length_min_ratio'] or difference>policy['finger_axis_max_difference_deg']:
            reject('WRIST_FINGERS_DISAGREE');continue
        if not policy['thumb_length_min_ratio']<=lengths['thumb']/hand<=policy['thumb_length_max_ratio']:
            reject('WRIST_PLANE_UNCLEAR');continue
        try:
            value=round(_bend(xy),10) # Avoid floating-point noise crossing an exact 15-degree category.
            if not math.isfinite(value): raise ValueError('nonfinite wrist angle')
            if value>policy['max_angle_deg']: reject('WRIST_PLANE_UNCLEAR');continue
            # One-point pixel perturbations are a sensitivity test, not a confidence interval.
            delta=max(policy['sensitivity_pixel_min'],min(width,height)*policy['sensitivity_image_ratio'])
            samples=[value]
            for joint in ('elbow','wrist','index','pinky'):
                for shift in ((delta,0),(-delta,0),(0,delta),(0,-delta)):
                    changed=dict(xy);changed[joint]=(xy[joint][0]+shift[0],xy[joint][1]+shift[1]);sample=_bend(changed)
                    if not math.isfinite(sample): raise ValueError('nonfinite perturbed angle')
                    samples.append(sample)
        except (ValueError,OverflowError,ZeroDivisionError):
            reject('WRIST_UNSTABLE');continue
        lower,upper=min(samples),max(samples);proof.update(sensitivity_min_deg=lower,sensitivity_max_deg=upper,pixel_perturbation=delta)
        if upper-lower>policy['max_sensitivity_deg']: reject('WRIST_UNSTABLE');continue
        row['value_deg']=value
        boundary=policy['category_boundary_deg'];band=policy['boundary_margin_deg']
        if lower<=boundary<=upper or abs(value-boundary)<=band:
            reject('WRIST_BOUNDARY');continue
        proof['auto_eligible']=True;result.append(row)
    return result
