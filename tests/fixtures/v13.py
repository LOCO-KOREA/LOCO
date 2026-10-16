"""Synthetic 1.3 input fixture for compatibility tests."""
EXPOSURES = ['C1_KEYBOARD_FOCUSED','C2_NECK','C2_SHOULDER','C2_ELBOW','C2_WRIST','C2_HAND','C3_UNION','C4_NECK_FLEX','C4_TRUNK_FLEX','C4_TRUNK_EXT','C4_NECK_TWIST','C4_TRUNK_TWIST','C4_UNION','C5_SQUAT','C5_KNEEL','C5_UNION','C6_QUALIFYING','C7_QUALIFYING','C10_LIFT','C11_IMPACT']
def capture():
    phases=['CYCLE_START','LIFT_OFF','MID_LIFT','SHELF_APPROACH','CYCLE_END']
    return dict(protocol='BOX_LIFT_15_V1', camera_side=None, forward_direction=None, slots=[dict(slot_no=i+1,cycle_no=i//5+1,phase=phases[i%5],photo_id=None,observation={}) for i in range(15)])
