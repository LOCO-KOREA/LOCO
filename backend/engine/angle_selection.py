"""Select one observed segment angle; inferred 3D stays an estimated draft input."""
import copy
import math

WORLD_FOR_IMAGE={'ELBOW_FLEX':'ELBOW_FLEX_3D','KNEE_FLEX':'KNEE_FLEX_3D'}


def _finite(value):
    try:return type(value) in (int,float) and math.isfinite(value)
    except OverflowError:return False


def selected_angle(pose,side,image_code,confidence_min=0.5):
    pose=pose or {}
    world=[a for a in pose.get('world_angles') or [] if a.get('side')==side and a.get('angle_code')==WORLD_FOR_IMAGE.get(image_code)]
    threshold=pose.get('world_confidence_min',confidence_min)
    if len(world)==1:
        angle=world[0];value=angle.get('value_deg');confidence=angle.get('min_confidence')
        valid=(angle.get('coordinate_space')=='INFERRED_WORLD_3D' and _finite(value)
            and 0<=value<=180 and _finite(confidence) and threshold<=confidence<=1)
        if valid:return dict(copy.deepcopy(angle),used_for_reba=True)
    image=[a for a in pose.get('angles') or [] if a.get('side')==side and a.get('angle_code')==image_code]
    return copy.deepcopy(image[0]) if len(image)==1 else None
