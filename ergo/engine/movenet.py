"""Compatibility entry point for explicitly requested historical MoveNet inference."""
import copy
import os
from ergo.pose_contract import COCO_NAMES,for_model
from ergo.pose.engine import process as infer

NAMES=list(COCO_NAMES)
_interpreter=None  # Historical attribute; provider modules own inference caches.


def process(slot,snapshot):
    value=copy.deepcopy(snapshot);selected=for_model('movenet-lightning')
    old=(value.get('settings') or {}).get('pose_model') or {}
    selected['confidence_min']=old.get('confidence_min',selected['confidence_min'])
    if os.environ.get('LOCO_MOVENET_MODEL'):selected['model_path']=os.environ['LOCO_MOVENET_MODEL']
    value.setdefault('settings',{})['pose_model']=selected
    return infer(slot,value)
