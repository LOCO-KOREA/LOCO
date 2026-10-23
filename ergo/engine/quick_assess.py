"""Photo-first quick assessment: provisional REBA from up to three photos (left, front/back, right) plus rule-based questions.

Nothing here is persisted. The provisional score assumes the no-burden option for every item a
photo cannot show; the final score is always recalculated by calculate_reba from answers the
user confirmed. Questions never pre-fill legal facts: unanswered stays UNKNOWN/null.
"""
import math
from copy import deepcopy

from .joint_angles import angles as joint_angles
from .reba_scoring import calculate_reba, candidates
from .task_defaults import ARM, COMMON

# The no-burden option for every REBA item, used only for the provisional score.
NO_BURDEN = {
    'trunk_base': 1, 'trunk_twisted': 'NO', 'trunk_side_bent': 'NO', 'neck_base': 1,
    'neck_twisted': 'NO', 'neck_side_bent': 'NO', 'legs_support': 'BILATERAL_STABLE',
    'seated': 'NO', 'knee_band': 'UNDER_30', 'shock_force': 'NO', 'static_over_1min': 'NO',
    'small_repeat_over_4min': 'NO', 'rapid_change_or_unstable': 'NO',
    'upper_arm_base': 1, 'arm_abducted_or_rotated': 'NO', 'shoulder_raised': 'NO',
    'arm_supported_or_gravity_assisted': 'NO', 'lower_arm_base': 1, 'wrist_base': 1,
    'wrist_deviated_or_twisted': 'NO', 'coupling': 'NOT_APPLICABLE',
}
FIELD_LABELS = {
    'trunk_base': '몸통 굽힘', 'knee_band': '무릎 굽힘', 'upper_arm_base': '위팔 들림',
    'lower_arm_base': '아래팔 굽힘', 'wrist_base': '손목 굽힘·폄',
}
YES_NO = [{'value': 'YES', 'label': '예'}, {'value': 'NO', 'label': '아니오'}, {'value': 'UNKNOWN', 'label': '모름'}]


# Shoulder/hip width over torso length. Measured on real photos: square-on front 0.77-0.99 / 0.51-0.56,
# slightly turned front 0.45-0.54 / 0.27-0.40, from the side <= 0.32 (shoulders) or <= 0.27 (hips) with overlapping hips.
FRONT_SHOULDER_RATIO, FRONT_HIP_RATIO = 0.65, 0.45
SIDE_SHOULDER_RATIO, SIDE_HIP_RATIO = 0.35, 0.20
# Facing the right edge of the picture shows the right body to the camera. The far body can look a little more
# "confident" by chance (0.05-0.11 in real photos), so it only wins when it is clearly the one that is visible.
NEAR_SIDE_OVERRIDE = 0.6
BODY = ('shoulder', 'elbow', 'wrist', 'hip', 'knee', 'ankle')


def guess_view(points, confidence_min=0.5):
    """Guess the facing direction, the body side nearer the camera and how square-on the worker is. The user confirms.

    Facing: nose ahead of the ears, else wrists ahead of the shoulders. Near side: the body side that faces the camera
    given the facing direction, unless MoveNet clearly sees the other side. Orientation: FRONT (square-on, front or
    back), SIDE (shoulders or hips overlap) or OBLIQUE (turned in between: used as it is, but with less trust).
    """
    p = {point['name']: point for point in points}
    seen = lambda names: [p[n] for n in names if n in p and p[n]['confidence'] >= confidence_min * 0.6]
    mean_x = lambda items: sum(i['x_px'] for i in items) / len(items)
    nose, ears = seen(['nose']), seen(['left_ear', 'right_ear'])
    shoulders, wrists = seen(['left_shoulder', 'right_shoulder']), seen(['left_wrist', 'right_wrist'])
    if nose and ears:
        forward = 'SCREEN_RIGHT' if nose[0]['x_px'] >= mean_x(ears) else 'SCREEN_LEFT'
    elif shoulders and wrists:
        forward = 'SCREEN_RIGHT' if mean_x(wrists) >= mean_x(shoulders) else 'SCREEN_LEFT'
    else:
        return None
    orientation = 'SIDE'
    trunk = [p.get(n) for n in ('left_shoulder', 'right_shoulder', 'left_hip', 'right_hip')]
    if all(x is not None and x['confidence'] >= confidence_min * 0.6 for x in trunk):
        ls, rs, lh, rh = trunk
        torso = math.dist(((ls['x_px'] + rs['x_px']) / 2, (ls['y_px'] + rs['y_px']) / 2), ((lh['x_px'] + rh['x_px']) / 2, (lh['y_px'] + rh['y_px']) / 2))
        width = lambda a, b: math.dist((a['x_px'], a['y_px']), (b['x_px'], b['y_px']))
        if torso > 0:
            shoulders_apart, hips_apart = width(ls, rs) / torso, width(lh, rh) / torso
            if shoulders_apart >= FRONT_SHOULDER_RATIO and hips_apart >= FRONT_HIP_RATIO:
                orientation = 'FRONT'
            elif shoulders_apart >= SIDE_SHOULDER_RATIO and hips_apart >= SIDE_HIP_RATIO:
                orientation = 'OBLIQUE'
    score = {side: sum(p[f'{side.lower()}_{j}']['confidence'] for j in BODY if f'{side.lower()}_{j}' in p) for side in ('LEFT', 'RIGHT')}
    camera = 'RIGHT' if forward == 'SCREEN_RIGHT' else 'LEFT'
    other = 'LEFT' if camera == 'RIGHT' else 'RIGHT'
    if score[other] - score[camera] >= NEAR_SIDE_OVERRIDE:
        camera = other
    return {'forward_direction': forward, 'camera_side': camera, 'orientation': orientation}


# The legs of a person on a chair: thigh roughly flat and the hip a full thigh-length or so above the ankle. A deep
# squat has the hip down near the ankle (measured 0.75-0.81 thigh lengths against 1.07-1.26 when sitting).
SEATED_THIGH_FLAT_DEG, SEATED_HIP_ABOVE_ANKLE = 30, 0.95
# A hand clearly above the shoulder, or an elbow above it. Vertical positions do not change when the body is turned,
# so this also works on front and slightly turned photos.
OVERHEAD_WRIST_ABOVE_SHOULDER, OVERHEAD_ELBOW_ABOVE_SHOULDER = 0.25, 0.05
# Upper arm angle from vertical at which the elbow reaches shoulder height. The posture profile's 45 degrees is the REBA
# tag, which a typist reaching for the keyboard (50-58 degrees) also passes; that is not "hand over the head".
ARM_OVERHEAD_DEG = 90


def seated_signal(points, camera_side, confidence_min=0.5):
    """True only when the near-side leg clearly looks like sitting on a chair; unsure means False."""
    p = {point['name']: point for point in points}
    names = [f'{camera_side.lower()}_{joint}' for joint in ('hip', 'knee', 'ankle')]
    if not all(n in p and p[n]['confidence'] >= confidence_min * 0.3 for n in names):
        return False
    hip, knee, ankle = (p[n] for n in names)
    thigh = math.dist((hip['x_px'], hip['y_px']), (knee['x_px'], knee['y_px']))
    if thigh <= 0:
        return False
    flat = math.degrees(math.atan2(abs(knee['y_px'] - hip['y_px']), abs(knee['x_px'] - hip['x_px']))) <= SEATED_THIGH_FLAT_DEG
    return flat and (ankle['y_px'] - hip['y_px']) / thigh >= SEATED_HIP_ABOVE_ANKLE


def arm_overhead_signal(points, confidence_min=0.5):
    """True when either arm has its hand clearly above the shoulder or its elbow above the shoulder."""
    p = {point['name']: point for point in points}
    ok = lambda *names: all(n in p and p[n]['confidence'] >= confidence_min * 0.6 for n in names)
    if not ok('left_shoulder', 'right_shoulder', 'left_hip', 'right_hip'):
        return False
    mid = lambda a, b, key: (p[a][key] + p[b][key]) / 2
    torso = math.dist((mid('left_shoulder', 'right_shoulder', 'x_px'), mid('left_shoulder', 'right_shoulder', 'y_px')),
                      (mid('left_hip', 'right_hip', 'x_px'), mid('left_hip', 'right_hip', 'y_px')))
    if torso <= 0:
        return False
    for side in ('left', 'right'):
        shoulder_y = p[f'{side}_shoulder']['y_px']
        if ok(f'{side}_elbow') and (shoulder_y - p[f'{side}_elbow']['y_px']) / torso >= OVERHEAD_ELBOW_ABOVE_SHOULDER:
            return True
        if ok(f'{side}_wrist') and (shoulder_y - p[f'{side}_wrist']['y_px']) / torso >= OVERHEAD_WRIST_ABOVE_SHOULDER:
            return True
    return False


TRUNK_SIDE_DEG, NECK_SIDE_DEG, ARM_ABDUCTION_DEG = 10, 15, 30
LOW_CONFIDENCE_FACTOR = 0.4
SEVERITY = {'trunk_base': [1, 2, 3, 4], 'knee_band': ['UNDER_30', 'FROM_30_TO_60', 'OVER_60'],
            'upper_arm_base': [1, 2, 3, 4], 'lower_arm_base': [1, 2], 'wrist_base': [1,2]}
VIEW_KO = {'LEFT': '왼쪽 사진', 'RIGHT': '오른쪽 사진', 'FRONT': '정면·후면 사진'}


def _confirmed_slot(camera_side, forward):
    """A slot as if the capture context were confirmed; used only to read angle candidates."""
    observation = {'load_state': 'UNLOADED', 'measured_load_kg': None, 'single_person': 'YES',
                   'full_frame': 'YES', 'normal_work': 'YES',
                   'evidence': {'source': None, 'text': None, 'observed_at': None}}
    return {'slot_no': 1, 'photo_id': 0, 'label': '사진 1', 'analysis_target': True,
            'camera_side': camera_side, 'forward_direction': forward,
            'side_view_verified': 'YES', 'observation': observation}


def _measured(scope, field, value, angle_rows, boundary, view, low_confidence=False):
    return {'scope': scope, 'field': field, 'value': value, 'label': FIELD_LABELS.get(field, field), 'view': view, 'low_confidence': low_confidence,
            'angles': [dict(side=a['side'],angle_code=a['angle_code'],value_deg=round(a['value_deg'],1),**({'measurement':a['measurement']} if a.get('measurement') else {})) for a in angle_rows],
            'boundary_review': boundary}


def side_measure(points, width, height, settings, camera_side, forward, slot_view=None, oblique=False):
    """Near-side REBA categories from one side photo; the far arm and knee are usually occluded.

    camera_side is the body side facing the camera (not the slot the user chose), so a photo put in the
    wrong slot is still measured on its visible side. slot_view only labels where the photo was put.
    oblique: the worker is turned part-way to the camera, so flexion angles read smaller than they are and every
    value is only a suggestion to confirm.
    """
    confidence = settings['pose_model'].get('confidence_min', 0.5)
    floor = confidence * LOW_CONFIDENCE_FACTOR
    # MoveNet's own estimate is used even when its confidence is modest: it is shown as a pre-selected suggestion
    # tagged 'low confidence' for the person to confirm, instead of leaving the question blank.
    rows = joint_angles(points, forward, width, height, floor,camera_side=camera_side,orientation='OBLIQUE' if oblique else 'SIDE')
    pose_slot = {'slot_no': 1, 'photo_id': 0, 'status': 'VALID', 'points': points, 'angles': rows}
    measured = []
    for item in candidates(_confirmed_slot(camera_side, forward), pose_slot, camera_side, floor):
        if item['proposed_value'] is None or item['field'] == 'knee_band' or item['scope'] not in ('COMMON', camera_side):
            continue
        low = oblique or (item['min_confidence'] or 0) < confidence
        measured.append(_measured(item['scope'], item['field'], item['proposed_value'], item['angles'], 'BOUNDARY_REVIEW' in item['review_reasons'], slot_view or camera_side, low))
    knee = next((a for a in rows if a['side'] == camera_side and a['angle_code'] == 'KNEE_FLEX' and a['value_deg'] is not None), None)
    if knee:
        v = knee['value_deg']
        band = 'UNDER_30' if v < 30 else 'FROM_30_TO_60' if v <= 60 else 'OVER_60'
        measured.append(_measured('COMMON', 'knee_band', band, [knee], any(abs(v - b) <= 5 for b in (30, 60)), slot_view or camera_side, oblique or (knee['min_confidence'] or 0) < confidence))
    return rows, measured


def merge_measured(*groups):
    """Both side photos show the same moment: keep each arm from its own side, and the heavier trunk/knee."""
    merged = {}
    for item in (m for group in groups for m in group):
        key = (item['scope'], item['field'])
        old = merged.get(key)
        if old is None or SEVERITY[item['field']].index(item['value']) > SEVERITY[old['field']].index(old['value']):
            merged[key] = dict(item, alternatives=(old or {}).get('alternatives', []) + ([old] if old else []))
        else:
            old.setdefault('alternatives', []).append(item)
    return list(merged.values())


def front_measure(points, confidence_min=0.5):
    """Side-agnostic frontal-plane suggestions (front or back photo): trunk/neck side bend, arm abduction."""
    p = {point['name']: point for point in points}
    ok = lambda *names: all(n in p and p[n]['confidence'] >= confidence_min * 0.6 for n in names)
    if not ok('left_shoulder', 'right_shoulder', 'left_hip', 'right_hip'):
        return []
    xy = lambda n: (p[n]['x_px'], p[n]['y_px'])
    mid = lambda a, b: ((p[a]['x_px'] + p[b]['x_px']) / 2, (p[a]['y_px'] + p[b]['y_px']) / 2)
    sm, hm = mid('left_shoulder', 'right_shoulder'), mid('left_hip', 'right_hip')

    def between(u, v):
        n = math.hypot(*u) * math.hypot(*v)
        return 0.0 if n == 0 else math.degrees(math.acos(max(-1, min(1, (u[0] * v[0] + u[1] * v[1]) / n))))

    up = (sm[0] - hm[0], sm[1] - hm[1])
    result = []
    trunk = between(up, (0, -1))
    result.append({'key': 'trunk_turn', 'label': '몸통 옆 기울임', 'value_deg': round(trunk, 1), 'suggested': trunk >= TRUNK_SIDE_DEG})
    head = 'nose' if ok('nose') else None
    if head:
        neck = between((p[head]['x_px'] - sm[0], p[head]['y_px'] - sm[1]), up)
        result.append({'key': 'neck_turn', 'label': '목 옆 기울임', 'value_deg': round(neck, 1), 'suggested': neck >= NECK_SIDE_DEG})
    arms = []
    for side in ('left', 'right'):
        if ok(f'{side}_shoulder', f'{side}_elbow'):
            s, e = xy(f'{side}_shoulder'), xy(f'{side}_elbow')
            arms.append(between((e[0] - s[0], e[1] - s[1]), (-up[0], -up[1])))
    if arms:
        result.append({'key': 'arm_abducted', 'label': '팔 옆으로 벌림', 'value_deg': round(max(arms), 1), 'suggested': max(arms) >= ARM_ABDUCTION_DEG})
    return result


FRONT_FIELDS = {'trunk_turn': [('COMMON', 'trunk_side_bent')], 'neck_turn': [('COMMON', 'neck_side_bent')],
                'arm_abducted': [('LEFT', 'arm_abducted_or_rotated'), ('RIGHT', 'arm_abducted_or_rotated')]}


def provisional(measured, front, settings, seated=False):
    """No-burden provisional REBA from photo measurements and frontal suggestions.

    seated: a photo showed the worker on a chair, so the legs are scored as seated instead of as bent knees.
    """
    known = {(m['scope'], m['field']): m['value'] for m in measured}
    if seated:
        known[('COMMON', 'seated')] = 'YES'
    for item in front:
        if item['suggested']:
            for key in FRONT_FIELDS[item['key']]:
                known[key] = 'YES'
    manual, assumed = [], []
    for scope, fields in [('COMMON', COMMON), ('LEFT', ARM), ('RIGHT', ARM)]:
        for field in fields:
            value = known.get((scope, field))
            if value is None:
                value = NO_BURDEN[field]
                assumed.append(f'{scope}.{field}')
            manual.append({'slot_no': 1, 'photo_id': 0, 'scope': scope, 'field': field, 'value': value})
    slot = _confirmed_slot('LEFT', 'SCREEN_RIGHT')
    snapshot = {'schema_version': '2.0', 'capture': {'slots': [slot]}, 'manual': manual, 'settings': {'pose_model': settings['pose_model']}}
    reba = calculate_reba(snapshot, {'slots': []})['slots'][0]
    return {'total': reba['total'], 'risk': reba['risk'], 'selected_side': reba['selected_side'],
            'left': reba['left']['total'], 'right': reba['right']['total'], 'assumed': assumed,
            'assumption': '사진에서 보이지 않는 항목은 부담 없음으로 가정한 1차 점수입니다. 질문에 답하면 달라질 수 있습니다.'}


def posture_signals(rows_by_view, profile):
    """Which posture families the side photos hint at; used only to choose which questions to ask."""
    near = [a for side, rows in rows_by_view.items() for a in rows if a['side'] == side and a['value_deg'] is not None]
    values = lambda code: [a['value_deg'] for a in near if a['angle_code'] == code]
    return {
        'arm_raised': any(v >= ARM_OVERHEAD_DEG for v in values('UPPER_ARM_RAISE_VERT')),
        'trunk_flexed': any(v >= profile['trunk_flex_deg'] for v in values('TRUNK_TILT_VERT')),
        'neck_flexed': any(v >= profile['neck_forward_deg'] for v in values('NECK_TILT_VERT_PROXY')),
        'knee_bent': any(v > 60 for v in values('KNEE_FLEX')),
    }


def _choice(qid, group, text, target, choices=YES_NO, help_text='', suggested=None, show_if=None):
    return {'id': qid, 'group': group, 'kind': 'choice', 'text': text, 'help': help_text,
            'choices': deepcopy(choices), 'target': target, 'suggested': suggested, 'show_if': show_if}


def _number(qid, group, text, target, unit, maximum=None, help_text='', chips=None, show_if=None):
    return {'id': qid, 'group': group, 'kind': 'number', 'text': text, 'help': help_text,
            'unit': unit, 'maximum': maximum, 'chips': chips or [], 'target': target, 'show_if': show_if}


def _flag(key, label, *sets):
    """A checklist line; each set is (scope, field, value_if_checked, value_if_unchecked)."""
    return {'key': key, 'label': label, 'sets': [dict(scope=a, field=b, checked=c, unchecked=d) for a, b, c, d in sets]}


def _checklist(qid, group, text, items, help_text):
    return {'id': qid, 'group': group, 'kind': 'checklist', 'text': text, 'help': help_text,
            'items': items, 'target': {'type': 'flags'}, 'show_if': None}


BASE_CHOICES = {
    'trunk_base': [{'value': 1, 'label': '똑바로'}, {'value': 2, 'label': '조금(20° 이내)'}, {'value': 3, 'label': '많이(20~60°)'}, {'value': 4, 'label': '아주 많이(60° 초과)'}],
    'knee_band': [{'value': 'UNDER_30', 'label': '거의 안 굽힘(30° 미만)'}, {'value': 'FROM_30_TO_60', 'label': '30~60°'}, {'value': 'OVER_60', 'label': '60° 초과'}],
    'upper_arm_base': [{'value': 1, 'label': '몸 옆(20° 이내)'}, {'value': 2, 'label': '20~45°'}, {'value': 3, 'label': '45~90°'}, {'value': 4, 'label': '90° 초과'}],
    'lower_arm_base': [{'value': 1, 'label': '60~100°'}, {'value': 2, 'label': '그 밖(60° 미만·100° 초과)'}],
}
BASE_TEXT = {'trunk_base': '몸통을 얼마나 굽히나요?', 'knee_band': '무릎을 얼마나 굽히나요?',
             'upper_arm_base': '위팔을 얼마나 드나요?', 'lower_arm_base': '팔꿈치 각도는 어떤가요?'}
SIDE_KO = {'LEFT': '왼쪽', 'RIGHT': '오른쪽'}
MINUTE_CHIPS = [0, 60, 120, 240]


TEMPLATES = [('GENERAL', '일반'), ('OFFICE', '사무'), ('REPETITION', '반복 작업'), ('POSTURE', '자세 부담'), ('HAND_FORCE', '손·힘'), ('LIFTING', '들기'), ('IMPACT', '충격')]
SITUATION = [('equipment', '설비'), ('workload', '작업량'), ('speed', '작업 속도'), ('work_pattern', '업무 형태')]


def _text(qid, group, text, target, placeholder='', help_text='', required=False, maxlength=80):
    return {'id': qid, 'group': group, 'kind': 'text', 'text': text, 'help': help_text, 'placeholder': placeholder,
            'target': target, 'required': required, 'maxlength': maxlength, 'show_if': None}


def work_info_questions():
    """Who, what and the survey context the Excel report needs. Nothing is guessed or pre-filled."""
    group = '조사 정보'
    q = [
        _text('task_name', group, '어떤 작업을 조사하나요?', {'type': 'task', 'field': 'task_name'}, '예: 상자 포장 작업', required=True),
        _choice('template', group, '작업 종류에 가장 가까운 것은요?', {'type': 'task', 'field': 'input_template'},
                [{'value': k, 'label': v} for k, v in TEMPLATES], '질문 순서만 정해요. 판정에는 영향이 없어요.'),
        _text('investigator', group, '조사자 이름', {'type': 'survey', 'field': 'investigator'}, '예: 김조사'),
        _text('department', group, '부서', {'type': 'survey', 'field': 'department'}, '예: 생산팀'),
        _text('process', group, '작업공정', {'type': 'survey', 'field': 'process'}, '예: 제품 포장 공정'),
    ]
    for key, label in SITUATION:
        q.append(_choice(f'situation_{key}', '작업장 상황', f'최근 {label}이(가) 바뀌었나요?', {'type': 'situation', 'field': f'{key}_status'},
                         [{'value': 'YES', 'label': '바뀌었어요'}, {'value': 'NO', 'label': '그대로예요'}, {'value': 'UNKNOWN', 'label': '모름'}]))
    q += [
        _choice('participation', '참여·증상', '근로자대표 또는 해당 근로자가 조사에 참여했나요?', {'type': 'participation', 'field': 'status'},
                [{'value': 'YES', 'label': '참여했어요'}, {'value': 'NO', 'label': '참여하지 않았어요'}, {'value': 'UNKNOWN', 'label': '모름'}]),
        _choice('participation_method', '참여·증상', '어떤 방식으로 참여했나요?', {'type': 'participation', 'field': 'method'},
                [{'value': 'INTERVIEW', 'label': '면담'}, {'value': 'MEETING', 'label': '회의'}, {'value': 'OBSERVATION', 'label': '현장 관찰'}, {'value': 'OTHER', 'label': '기타'}],
                show_if={'participation': ['YES']}),
        _choice('symptom', '참여·증상', '근골격계 증상조사는 했나요?', {'type': 'symptom', 'field': 'method'},
                [{'value': 'QUESTIONNAIRE', 'label': '설문으로 했어요'}, {'value': 'INTERVIEW', 'label': '면담으로 했어요'}, {'value': 'NOT_DONE', 'label': '하지 않았어요'}, {'value': 'UNKNOWN', 'label': '모름'}],
                '응답 내용은 이 흐름에서 받지 않고, 실시 여부만 기록해요.'),
    ]
    return q


def _exposure(code, label, chips=None):
    return {'key': code, 'label': label, 'type': 'number', 'unit': '분/일', 'maximum': 1440, 'chips': chips or [0, 60, 120, 240], 'to': {'exposure': code}}


def _crit_field(key, label, type_='number', unit='', maximum=None, chips=None, to=None):
    return {'key': key, 'label': label, 'type': type_, 'unit': unit, 'maximum': maximum, 'chips': chips or [], 'to': to or {'row': key}}


GROUP_TYPES = '이 작업의 특징'
GROUP_FOLLOWUP = '하루 시간·횟수'
# Which work type switches on which statutory criterion. The person never sees these numbers while answering.
GATES = {1: 'keyboard', 2: 'repeat', 3: 'arm_over', 4: 'trunk_neck', 5: 'knee', 6: 'pinch', 7: 'grip', 8: 'lift', 9: 'lift', 10: 'lift', 11: 'impact'}
WORK_TYPES = [
    ('keyboard', '키보드·마우스를 오래 쓰는 작업', None),
    ('repeat', '같은 동작을 계속 반복하는 작업', None),
    ('arm_over', '손이 머리 위로, 또는 팔꿈치가 어깨 위로 올라가는 작업', 'arm_raised'),
    ('trunk_neck', '허리나 목을 굽히거나 비틀며 하는 작업', 'trunk_neck'),
    ('knee', '쪼그려 앉거나 무릎을 굽히는 작업', 'knee_bent'),
    ('pinch', '손가락 끝으로 작은 물건을 집는 작업', None),
    ('grip', '한 손으로 물건을 들거나 세게 쥐는 작업', None),
    ('lift', '무거운 물건을 들어 올리거나 옮기는 작업', None),
    ('impact', '손이나 무릎으로 물건을 때리는 충격 작업', None),
]
SIGNAL_NOTE = {'arm_raised': '팔이 어깨 위로 올라간 자세', 'trunk_neck': '허리·목을 숙인 자세', 'knee_bent': '무릎을 많이 굽힌 자세'}


def work_type_question(signals):
    """One checklist replaces eleven yes/no cards. Postures the photo shows are pre-checked; the rest the person ticks."""
    flags = {'arm_raised': bool(signals.get('arm_raised')), 'trunk_neck': bool(signals.get('trunk_flexed') or signals.get('neck_flexed')),
             'knee_bent': bool(signals.get('knee_bent')) and not signals.get('seated')}
    items = []
    for key, label, signal in WORK_TYPES:
        hinted = bool(signal and flags.get(signal))
        items.append({'key': key, 'label': label, 'sets': [], 'suggested': hinted,
                      'evidence': f'사진에서 {SIGNAL_NOTE[signal]}가 보였어요' if hinted else None})
    return {'id': 'work_types', 'group': GROUP_TYPES, 'kind': 'checklist', 'text': '이 작업에서 해당하는 것을 모두 골라 주세요.',
            'help': '체크한 것만 이어서 하루 시간이나 횟수를 물어봐요. 체크하지 않은 것은 "해당 없음"으로 기록돼요. 사진에서 보인 자세는 미리 체크해 두었어요.',
            'items': items, 'target': {'type': 'work_types'}, 'show_if': None}


def _row_field(key, label, unit='', maximum=None, chips=None, type_='number'):
    return _crit_field(key, label, type_, unit, maximum, chips)


FOLLOWUPS = [
    # (gate, criterion, title, ask, mode, fields)
    ('keyboard', 1, '키보드·마우스 작업', '하루에 모두 몇 분쯤 쓰나요?', 'time',
     [_exposure('C1_KEYBOARD_FOCUSED', '하루 총 시간', [120, 240, 360, 480])]),
    ('repeat', 2, '같은 동작 반복', '어느 부위로 하루에 몇 분쯤 반복하나요? 해당 없는 부위는 비워 두세요.', 'time',
     [_exposure('C2_NECK', '목'), _exposure('C2_SHOULDER', '어깨'), _exposure('C2_ELBOW', '팔꿈치'), _exposure('C2_WRIST', '손목'), _exposure('C2_HAND', '손')]),
    ('arm_over', 3, '손·팔을 높이 드는 작업', '하루에 모두 몇 분쯤 하나요? 겹치는 시간은 한 번만 세어 주세요.', 'time',
     [_exposure('C3_UNION', '하루 총 시간')]),
    ('trunk_neck', 4, '허리·목을 굽히거나 비트는 작업', '하루에 몇 분쯤 하나요?', 'time',
     [_crit_field('unsupported', '몸을 받칠 지지대 없이 하나요?', 'truth', to={'criterion': 'unsupported'}),
      _crit_field('posture_restricted', '자세를 바꾸기 어려운 작업인가요?', 'truth', to={'criterion': 'posture_restricted'}),
      _exposure('C4_TRUNK_FLEX', '허리 굽힘'), _exposure('C4_NECK_FLEX', '목 굽힘'), _exposure('C4_TRUNK_TWIST', '허리 비틀림'),
      _exposure('C4_NECK_TWIST', '목 비틀림'), _exposure('C4_UNION', '위 자세를 합친 하루 총 시간(겹치는 시간은 한 번만)')]),
    ('knee', 5, '쪼그리거나 무릎을 굽히는 작업', '하루에 몇 분쯤 하나요?', 'time',
     [_exposure('C5_SQUAT', '쪼그려 앉기'), _exposure('C5_KNEEL', '무릎 꿇기·굽히기'), _exposure('C5_UNION', '위 자세를 합친 하루 총 시간(겹치는 시간은 한 번만)')]),
    ('pinch', 6, '손가락 끝으로 집는 작업', '손을 받치지 않고 집는 물건의 무게와 하루 시간을 알려 주세요.', 'row',
     [_crit_field('unsupported', '손을 받치지 않고 하나요?', 'truth'), _crit_field('pinch_mass_kg', '집는 물건 무게', unit='kg', chips=[0.5, 1, 2]),
      _crit_field('pinch_force_kg_equiv', '집는 힘(kg 상당)', unit='kg', chips=[1, 2, 4]), _crit_field('minutes', '하루 시간', unit='분/일', maximum=1440, chips=[60, 120, 240])]),
    ('grip', 7, '한 손으로 들거나 쥐는 작업', '손을 받치지 않고 한 손으로 드는 무게와 하루 시간을 알려 주세요.', 'row',
     [_crit_field('unsupported', '손을 받치지 않고 하나요?', 'truth'), _crit_field('single_hand_mass_kg', '한 손으로 드는 무게', unit='kg', chips=[2, 4.5, 8]),
      _crit_field('grip_force_kg_equiv', '쥐는 힘(kg 상당)', unit='kg', chips=[2, 4.5, 8]), _crit_field('minutes', '하루 시간', unit='분/일', maximum=1440, chips=[60, 120, 240])]),
    ('impact', 11, '손·무릎으로 때리는 작업', '물체를 때리는 충격에 대해 알려 주세요.', 'row',
     [_crit_field('impact_verified', '실제로 물체에 충격이 가해지나요?', 'truth'), _crit_field('impact_rate_hour', '1시간에 몇 번쯤 가하나요?', unit='회/시간', chips=[5, 10, 20]),
      _crit_field('minutes', '하루 시간', unit='분/일', maximum=1440, chips=[60, 120, 240])]),
]
# One lifting card feeds three statutory criteria (heavy lifting, awkward-position lifting, repeated lifting) from the same answers.
LIFT_FIELDS = [
    _crit_field('load_mass_kg', '가장 무거운 물건의 무게', unit='kg', chips=[5, 10, 20, 25], to={'lift': 'load_mass_kg'}),
    _crit_field('lift_count_day', '하루에 들어 올리는 횟수', unit='회/일', chips=[10, 25, 50, 100], to={'lift': 'lift_count_day'}),
    _crit_field('lift_rate_min', '1분에 몇 번쯤 드나요?', unit='회/분', chips=[1, 2, 4], to={'lift': 'lift_rate_min'}),
    _crit_field('minutes', '이렇게 드는 시간(하루)', unit='분/일', maximum=1440, chips=[60, 120, 240], to={'lift': 'minutes'}),
    _crit_field('below_knee_count_day', '무릎 아래에서 드는 횟수(하루)', unit='회/일', chips=[0, 10, 25], to={'lift': 'below_knee_count_day'}),
    _crit_field('above_shoulder_count_day', '어깨 위에서 드는 횟수(하루)', unit='회/일', chips=[0, 10, 25], to={'lift': 'above_shoulder_count_day'}),
    _crit_field('extended_arm_count_day', '팔을 뻗어 드는 횟수(하루)', unit='회/일', chips=[0, 10, 25], to={'lift': 'extended_arm_count_day'}),
    _crit_field('union_count_day', '위 세 가지를 합친 횟수(겹치는 것은 한 번만)', unit='회/일', chips=[0, 25, 50], to={'lift': 'union_count_day'}),
]


def followup_cards():
    """Cards that appear only for the work types the person ticked. Titles use everyday words, not criterion numbers."""
    cards = []
    for gate, number, title, ask, mode, fields in FOLLOWUPS:
        cards.append({'id': f'crit_{gate}', 'group': GROUP_FOLLOWUP, 'kind': 'criterion', 'criterion': number, 'gate': gate, 'implicit': True,
                      'text': title, 'ask': ask, 'help': '', 'hint': False, 'mode': mode, 'fields': fields,
                      'target': {'type': 'criterion_card', 'criterion': number}, 'show_if': {'work_types': [gate]}})
    cards.append({'id': 'crit_lift', 'group': GROUP_FOLLOWUP, 'kind': 'criterion', 'criterion': None, 'criteria': [8, 9, 10], 'gate': 'lift', 'implicit': True,
                  'text': '무거운 물건을 드는 작업', 'ask': '물건의 무게와 드는 횟수를 알려 주세요. 모르는 칸은 비워 두세요.', 'help': '', 'hint': False,
                  'mode': 'lift', 'fields': LIFT_FIELDS, 'target': {'type': 'criterion_card', 'criterion': 0}, 'show_if': {'work_types': ['lift']}})
    return cards


def _guess_help(item):
    degrees = ' / '.join(f"{a['value_deg']}°" for a in item.get('angles', []))
    return f'사진에서 추정했어요({degrees}, 신뢰도 낮음). 맞는지 확인해 주세요.'


def questions(views, measured, signals, front=()):
    """Rule-based questions for everything the photos could not settle, grouped into a few steps.

    views maps 'LEFT' / 'FRONT' / 'RIGHT' to that photo's guess (or None when no person was found).
    """
    have = {(m['scope'], m['field']): m['value'] for m in measured if not m.get('low_confidence')}
    guessed = {(m['scope'], m['field']): m for m in measured if m.get('low_confidence')}
    loaded = {'load': ['MEASURED']}
    q = [
        _choice('context', '사진 확인', '올린 사진이 모두 한 사람의 전신이 나온 평소 작업 모습인가요?', {'type': 'context'},
                [{'value': 'YES', 'label': '예, 모두 맞아요'}, {'value': 'NO', 'label': '아니오'}],
                '아니오면 사진 각도를 쓰지 않고 질문 답으로만 계산해요.'),
    ]
    for side in ('LEFT', 'RIGHT'):
        if side in views:
            guess = views[side] or {}
            q.append(_choice(f'view_{side}', '사진 확인', f'{VIEW_KO[side]}에서 작업자는 화면의 어느 쪽을 보고 있나요?',
                             {'type': 'slot', 'view': side, 'field': 'forward_direction'},
                             [{'value': 'SCREEN_RIGHT', 'label': '오른쪽'}, {'value': 'SCREEN_LEFT', 'label': '왼쪽'}],
                             '프로그램이 얼굴·손 위치로 추정했어요. 다르면 바꿔 주세요.', guess.get('forward_direction'), show_if={'context': ['YES']}))
    q.append(work_type_question(signals))
    q += [
        _choice('load', '물건과 힘', '이 순간 손에 든 물건이나 미는 힘이 있나요?', {'type': 'load'},
                [{'value': 'UNLOADED', 'label': '없음'}, {'value': 'MEASURED', 'label': '있음'}, {'value': 'UNKNOWN', 'label': '모름'}]),
        _number('load_kg', '물건과 힘', '무게(또는 힘)는 몇 kg인가요?', {'type': 'load_kg'}, 'kg', 500,
                '저울·표시값·면담으로 확인한 값이에요.', [2, 5, 10, 20], loaded),
        _choice('coupling', '물건과 힘', '손잡이나 잡는 상태는 어떤가요?', {'type': 'manual', 'scope': 'BOTH', 'field': 'coupling'},
                [{'value': 'GOOD', 'label': '좋음'}, {'value': 'FAIR', 'label': '보통'}, {'value': 'POOR', 'label': '나쁨'}, {'value': 'UNACCEPTABLE', 'label': '잡을 곳 없음'}],
                show_if=loaded),
    ]
    photo_unusable = {'context': ['NO']}
    photo_usable = {'context': ['YES']}
    for field in ('trunk_base', 'knee_band'):
        measured_here = ('COMMON', field) in have
        guess = guessed.get(('COMMON', field))
        q.append(_choice(field, '자세', BASE_TEXT[field], {'type': 'manual', 'scope': 'COMMON', 'field': field}, BASE_CHOICES[field],
                         '사진 각도를 쓰지 않으므로 직접 골라 주세요.' if measured_here else (_guess_help(guess) if guess else '사진에서 이 각도를 읽지 못했어요.'),
                         suggested=guess['value'] if guess else None, show_if=photo_unusable if measured_here else None))
    for field in ('upper_arm_base', 'lower_arm_base'):
        seen = {side: have[(side, field)] for side in ('LEFT', 'RIGHT') if (side, field) in have}
        guess = next((guessed[(side, field)] for side in ('LEFT', 'RIGHT') if (side, field) in guessed), None) if not seen else None
        q.append(_choice(field, '자세', '양팔 ' + BASE_TEXT[field], {'type': 'manual', 'scope': 'BOTH', 'field': field}, BASE_CHOICES[field],
                         '사진 각도를 쓰지 않으므로 직접 골라 주세요.' if seen else (_guess_help(guess) if guess else '사진에서 이 각도를 읽지 못했어요.'),
                         suggested=guess['value'] if guess else None, show_if=photo_unusable if seen else None))
        if len(seen) == 1:
            side, value = next(iter(seen.items()))
            other = 'RIGHT' if side == 'LEFT' else 'LEFT'
            label = next(c['label'] for c in BASE_CHOICES[field] if c['value'] == value)
            q.append(_choice(f'{field}_{other.lower()}', '자세', f'{SIDE_KO[other]} 팔도 같은가요? ({BASE_TEXT[field]})',
                             {'type': 'manual', 'scope': other, 'field': field},
                             [{'value': value, 'label': f'{SIDE_KO[side]} 팔과 같음({label})'}] + [c for c in BASE_CHOICES[field] if c['value'] != value],
                             f'{SIDE_KO[side]} 팔은 사진에서 측정했고, {SIDE_KO[other]} 팔은 사진에서 읽지 못했어요.', show_if=photo_usable))
    q += [
        _choice('neck_base', '자세', '목은 어떤가요?', {'type': 'manual', 'scope': 'COMMON', 'field': 'neck_base'},
                [{'value': 1, 'label': '똑바로·조금 숙임(20° 이내)'}, {'value': 2, 'label': '20° 넘게 숙임'}, {'value': '2_EXTENSION', 'label': '뒤로 젖힘'}],
                '사진의 목 각도는 참고값이라 직접 골라 주세요.'),
        _choice('wrist_base', '자세', '손목을 앞뒤로 얼마나 굽히거나 젖히나요?', {'type': 'manual', 'scope': 'BOTH', 'field': 'wrist_base'},
                [{'value': 1, 'label': '15° 이내'}, {'value': 2, 'label': '15° 넘게'}]),
        _checklist('posture_flags', '자세', '해당하는 자세를 모두 골라 주세요.', [
            _flag('neck_turn', '목을 비틀거나 옆으로 기울임', ('COMMON', 'neck_twisted', 'YES', 'NO'), ('COMMON', 'neck_side_bent', None, 'NO')),
            _flag('trunk_turn', '몸통을 비틀거나 옆으로 기울임', ('COMMON', 'trunk_twisted', 'YES', 'NO'), ('COMMON', 'trunk_side_bent', None, 'NO')),
            _flag('wrist_twist', '손목을 비틀거나 옆으로 꺾음(앞뒤 굽힘과 별도)', ('BOTH', 'wrist_deviated_or_twisted', 'YES', 'NO')),
            _flag('arm_abducted', '팔을 옆으로 벌리거나 돌림', ('BOTH', 'arm_abducted_or_rotated', 'YES', 'NO')),
            _flag('shoulder_raised', '어깨를 으쓱 들어 올림', ('BOTH', 'shoulder_raised', 'YES', 'NO')),
            _flag('arm_supported', '팔을 받치거나 기대어 작업함', ('BOTH', 'arm_supported_or_gravity_assisted', 'YES', 'NO')),
            _flag('unstable_legs', '한 발로 서거나 발 받침이 불안정함', ('COMMON', 'legs_support', 'UNILATERAL_OR_UNSTABLE', 'BILATERAL_STABLE')),
            _flag('seated', '앉아서 작업함', ('COMMON', 'seated', 'YES', 'NO')),
        ], '고르지 않은 항목은 "아니오"로 기록돼요. 나중에 상세 편집에서 바꿀 수 있어요.'),
        _checklist('activity_flags', '활동', '작업 중 해당하는 것을 모두 골라 주세요.', [
            _flag('shock', '갑자기 큰 힘이나 충격이 가해짐', ('COMMON', 'shock_force', 'YES', 'NO')),
            _flag('static', '같은 자세를 1분 넘게 유지함', ('COMMON', 'static_over_1min', 'YES', 'NO')),
            _flag('repeat', '좁은 범위 동작을 1분에 4번 넘게 반복함', ('COMMON', 'small_repeat_over_4min', 'YES', 'NO')),
            _flag('unstable', '자세가 크게 바뀌거나 불안정함', ('COMMON', 'rapid_change_or_unstable', 'YES', 'NO')),
        ], '고르지 않은 항목은 "아니오"로 기록돼요.'),
        _number('daily_work_min', '작업 시간', '하루 실제 작업시간은 몇 분인가요?', {'type': 'conditions', 'field': 'daily_work_min'}, '분', 1440,
                '휴식을 뺀 실제 작업시간이에요.', [240, 360, 480]),
        _choice('one_off', '작업 시간', '한 번만 하고 끝나는 일회성 작업인가요?', {'type': 'conditions', 'field': 'one_off'}),
        _number('annual_work_days', '작업 시간', '이 작업을 1년에 며칠 하나요?', {'type': 'conditions', 'field': 'annual_work_days'}, '일', 366,
                '60일 이하이면 간헐적 작업으로 볼 수 있어요.', [60, 120, 220, 250]),
    ]
    hints = {item['key']: item for item in front}
    for question in q:
        if question['id'] == 'work_types':
            continue
        for item in question.get('items', []):
            hint = hints.get(item['key'])
            item['suggested'] = bool(hint and hint['suggested'])
            item['evidence'] = f"정면·후면 사진 {hint['label']} {hint['value_deg']}°" if hint else None
    if signals.get('seated'):
        flags = next(question for question in q if question['id'] == 'posture_flags')
        seated = next(item for item in flags['items'] if item['key'] == 'seated')
        seated['suggested'] = True
        seated['evidence'] = '사진에서 의자에 앉은 자세로 보였어요. 쪼그려 앉은 거라면 해제해 주세요.'
    q.extend(followup_cards())
    q += work_info_questions()
    return q
