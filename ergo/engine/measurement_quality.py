"""Read-only landmark coverage and model confidence, independent of REBA scoring."""
import math
from collections import Counter
from ergo.pose_contract import COCO_NAMES, MEDIAPIPE_NAMES

QUALITY_BANDS = ((0.75, 0.75, 'HIGH'), (0.50, 0.50, 'MEDIUM'))


def _number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def _names(model):
    model = model or {}
    identity = str(model.get('model_id') or '')
    return COCO_NAMES if model.get('provider') == 'movenet' or identity.startswith('movenet') else MEDIAPIPE_NAMES


def _level(measured, total, mean):
    if not measured:
        return 'MISSING'
    for coverage, confidence, label in QUALITY_BANDS:
        if measured / total >= coverage and mean is not None and mean >= confidence:
            return label
    return 'LOW'


def _sample(points, model, min_confidence):
    names = _names(model)
    threshold = min_confidence if _number(min_confidence) and 0 <= min_confidence <= 1 else 0.5
    candidates = []
    for point in points or []:
        if not isinstance(point, dict):
            continue
        name = point.get('name')
        number = point.get('point_no')
        if name is None and type(number) is int and 0 <= number < len(names):
            name = names[number]
        if name in names:
            candidates.append((name, point))
    occurrences = Counter(name for name, _ in candidates)
    confidence = []
    for name, point in candidates:
        value = point.get('confidence')
        if occurrences[name] != 1 or not all(_number(point.get(axis)) for axis in ('x_px', 'y_px')):
            continue
        if _number(value) and 0 <= value <= 1:
            confidence.append(value)
    measured = sum(value >= threshold for value in confidence)
    mean = sum(confidence) / len(confidence) if confidence else None
    return dict(measured_points=measured, total_points=len(names), mean_confidence=mean,
                confidence_level=_level(measured, len(names), mean)), confidence


def from_points(points, model=None, min_confidence=None):
    """Count unique usable 2D landmarks; confidence is not an accuracy estimate."""
    model = model or {}
    return _sample(points, model, model.get('confidence_min', 0.5) if min_confidence is None else min_confidence)[0]


def from_analysis(analysis):
    snapshot = analysis.get('snapshot') or {}
    settings = (snapshot.get('settings') or {}).get('pose_model') or {}
    legacy = snapshot.get('schema_version') != '2.0'
    targets = [slot for slot in (snapshot.get('capture') or {}).get('slots', [])
               if slot.get('photo_id') is not None and slot.get('analysis_target', legacy)]
    poses = (analysis.get('pose') or {}).get('slots') or []
    slots, confidences = [], []
    for slot in targets:
        pose = next((p for p in poses if p.get('slot_no') == slot.get('slot_no')
                     and p.get('photo_id') in (None, slot['photo_id'])), {})
        model = pose.get('engine') or settings
        quality, samples = _sample(pose.get('points'), model, settings.get('confidence_min', 0.5))
        slots.append(dict(slot_no=slot['slot_no'], photo_id=slot['photo_id'], **quality))
        confidences.extend(samples)
    measured, total = sum(s['measured_points'] for s in slots), sum(s['total_points'] for s in slots)
    mean = sum(confidences) / len(confidences) if confidences else None
    return dict(measured_points=measured, total_points=total, mean_confidence=mean,
                confidence_level=_level(measured, total, mean), slots=slots)


def from_pose_slots(slots, model=None):
    """Use the same quality calculation for preview results before an analysis exists."""
    targets = [dict(slot_no=slot['slot_no'], photo_id=slot.get('photo_id'), analysis_target=True) for slot in slots]
    return from_analysis(dict(snapshot=dict(schema_version='2.0', capture=dict(slots=targets),
        settings=dict(pose_model=model or {})), pose=dict(slots=slots)))
