"""Photo tag frequency; never converts sample ratios to daily exposure."""
from .task_defaults import TAGS

def calculate_tags(snapshot,pose):
    targets=[s for s in snapshot['capture']['slots'] if s.get('analysis_target',True) and s.get('photo_id') is not None]
    slots=[]; summary=[]; profile=snapshot['settings']['posture_profile']
    mapping={'HAND_ABOVE_HEAD':'hand_above_head','ELBOW_ABOVE_SHOULDER':'elbow_above_shoulder','ELBOW_BEHIND_TRUNK':'elbow_behind_trunk','NECK_TWIST':'neck_twisted','TRUNK_TWIST':'trunk_twisted','SQUAT':'squat','KNEEL':'kneel'}
    for slot in targets:
        ps=next((p for p in (pose or {}).get('slots',[]) if p['slot_no']==slot['slot_no']),{})
        camera=slot.get('camera_side',snapshot['capture'].get('camera_side'))
        aa={a['angle_code']:a['value_deg'] for a in ps.get('angles',[]) if ps.get('status')=='VALID' and a['side']==camera}
        manual={}
        for item in snapshot['manual']:
            if item['slot_no']==slot['slot_no'] and item['photo_id']==slot['photo_id']:
                manual.setdefault(item['scope'],{})[item['field']]=item['value']
        for tag in TAGS:
            value='UNKNOWN'; source='UNKNOWN'
            if tag in mapping:
                field=mapping[tag]; common=(manual.get('COMMON') or {}).get(field)
                if common in ('YES','NO'): value=common; source='MANUAL'
                elif tag in ('HAND_ABOVE_HEAD','ELBOW_ABOVE_SHOULDER','ELBOW_BEHIND_TRUNK'):
                    left=(manual.get('LEFT') or {}).get(field); right=(manual.get('RIGHT') or {}).get(field)
                    value='YES' if 'YES' in (left,right) else 'NO' if left=='NO' and right=='NO' else 'UNKNOWN'
                    source='MANUAL' if value in ('YES','NO') else 'UNKNOWN'
            else:
                code,threshold,reverse={'NECK_FORWARD_PROXY':('NECK_TILT_VERT_PROXY',profile['neck_forward_deg'],False),'TRUNK_FLEX':('TRUNK_TILT_VERT',profile['trunk_flex_deg'],False),'TRUNK_EXT':('TRUNK_TILT_VERT',profile['trunk_extension_deg'],True),'UPPER_ARM_RAISE':('UPPER_ARM_RAISE_VERT',profile['upper_arm_raise_deg'],False)}[tag]
                if aa.get(code) is not None: value='YES' if (aa[code]<=threshold if reverse else aa[code]>=threshold) else 'NO'; source='ANGLE'
            slots.append(dict(slot_no=slot['slot_no'],tag=tag,value=value,source=source))
    for tag in TAGS:
        observed=[s for s in slots if s['tag']==tag and s['value'] in ['YES','NO']]; yes=sum(s['value']=='YES' for s in observed)
        summary.append(dict(tag=tag,yes_count=yes,observed_count=len(observed),valid_pose_count=(pose or {}).get('valid_count',0),manual_observed_count=sum(s['source']=='MANUAL' for s in observed),total_slot_count=len(targets),sample_ratio=yes/len(observed) if observed else None))
    return dict(slots=slots,summary=summary)
