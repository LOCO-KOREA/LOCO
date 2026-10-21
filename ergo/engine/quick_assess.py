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
    'lower_arm_base': '아래팔 굽힘',
}
YES_NO = [{'value': 'YES', 'label': '예'}, {'value': 'NO', 'label': '아니오'}, {'value': 'UNKNOWN', 'label': '모름'}]


FRONT_SHOULDER_RATIO, FRONT_HIP_RATIO = 0.65, 0.45
BODY = ('shoulder', 'elbow', 'wrist', 'hip', 'knee', 'ankle')


def guess_view(points, confidence_min=0.5):
    """Guess the facing direction and the body side nearer the camera. The user confirms both.

    Facing: nose ahead of the ears, else wrists ahead of the shoulders. Near side: the side whose
    joints MoveNet sees more confidently, because the far side is usually occluded.
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
        # Side views overlap the two shoulders/hips; a front or back view shows them ~0.8 torso apart.
        if torso > 0 and width(ls, rs) / torso >= FRONT_SHOULDER_RATIO and width(lh, rh) / torso >= FRONT_HIP_RATIO:
            orientation = 'FRONT'
    score = {side: sum(p[f'{side.lower()}_{j}']['confidence'] for j in BODY if f'{side.lower()}_{j}' in p) for side in ('LEFT', 'RIGHT')}
    if abs(score['LEFT'] - score['RIGHT']) < 0.05:
        camera = 'LEFT' if forward == 'SCREEN_RIGHT' else 'RIGHT'
    else:
        camera = max(score, key=score.get)
    return {'forward_direction': forward, 'camera_side': camera, 'orientation': orientation}


TRUNK_SIDE_DEG, NECK_SIDE_DEG, ARM_ABDUCTION_DEG = 10, 15, 30
SEVERITY = {'trunk_base': [1, 2, 3, 4], 'knee_band': ['UNDER_30', 'FROM_30_TO_60', 'OVER_60'],
            'upper_arm_base': [1, 2, 3, 4], 'lower_arm_base': [1, 2]}
VIEW_KO = {'LEFT': '왼쪽 사진', 'RIGHT': '오른쪽 사진', 'FRONT': '정면·후면 사진'}


def _confirmed_slot(camera_side, forward):
    """A slot as if the capture context were confirmed; used only to read angle candidates."""
    observation = {'load_state': 'UNLOADED', 'measured_load_kg': None, 'single_person': 'YES',
                   'full_frame': 'YES', 'normal_work': 'YES',
                   'evidence': {'source': None, 'text': None, 'observed_at': None}}
    return {'slot_no': 1, 'photo_id': 0, 'label': '사진 1', 'analysis_target': True,
            'camera_side': camera_side, 'forward_direction': forward,
            'side_view_verified': 'YES', 'observation': observation}


def _measured(scope, field, value, angle_rows, boundary, view):
    return {'scope': scope, 'field': field, 'value': value, 'label': FIELD_LABELS.get(field, field), 'view': view,
            'angles': [{'side': a['side'], 'angle_code': a['angle_code'], 'value_deg': round(a['value_deg'], 1)} for a in angle_rows],
            'boundary_review': boundary}


def side_measure(points, width, height, settings, camera_side, forward):
    """Near-side REBA categories from one side photo; the far arm and knee are usually occluded."""
    confidence = settings['pose_model'].get('confidence_min', 0.5)
    rows = joint_angles(points, forward, width, height, confidence)
    pose_slot = {'slot_no': 1, 'photo_id': 0, 'status': 'VALID', 'points': points, 'angles': rows}
    measured = []
    for item in candidates(_confirmed_slot(camera_side, forward), pose_slot, camera_side, confidence):
        if item['proposed_value'] is None or item['field'] == 'knee_band' or item['scope'] not in ('COMMON', camera_side):
            continue
        measured.append(_measured(item['scope'], item['field'], item['proposed_value'], item['angles'], 'BOUNDARY_REVIEW' in item['review_reasons'], camera_side))
    knee = next((a for a in rows if a['side'] == camera_side and a['angle_code'] == 'KNEE_FLEX' and a['value_deg'] is not None), None)
    if knee:
        v = knee['value_deg']
        band = 'UNDER_30' if v < 30 else 'FROM_30_TO_60' if v <= 60 else 'OVER_60'
        measured.append(_measured('COMMON', 'knee_band', band, [knee], any(abs(v - b) <= 5 for b in (30, 60)), camera_side))
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


def provisional(measured, front, settings):
    """No-burden provisional REBA from photo measurements and frontal suggestions."""
    known = {(m['scope'], m['field']): m['value'] for m in measured}
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
        'arm_raised': any(v >= profile['upper_arm_raise_deg'] for v in values('UPPER_ARM_RAISE_VERT')),
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


CRITERIA = {
    1: ('키보드·마우스 집중 입력', '집중해서 자료를 입력하는 키보드·마우스 작업을 하루 240분(4시간) 이상 하나요?', 'time',
        [_exposure('C1_KEYBOARD_FOCUSED', '하루 총 시간', [120, 240, 360, 480])]),
    2: ('같은 동작 반복', '목·어깨·팔꿈치·손목·손 중 한 부위로 같은 동작을 반복하는 작업을 하루 120분(2시간) 이상 하나요?', 'time',
        [_exposure('C2_NECK', '목'), _exposure('C2_SHOULDER', '어깨'), _exposure('C2_ELBOW', '팔꿈치'), _exposure('C2_WRIST', '손목'), _exposure('C2_HAND', '손')]),
    3: ('손·팔의 부담 자세', '손을 머리 위로 들거나 팔꿈치를 어깨 위로 드는 등 손·팔이 부담 자세인 작업을 하루 120분(2시간) 이상 하나요?', 'time',
        [_exposure('C3_UNION', '해당 자세 하루 총 시간(겹치는 시간은 한 번만)')]),
    4: ('목·허리 굽힘·비틀림', '지지대 없이, 또는 자세를 바꾸기 어려운 상태로 목·허리를 굽히거나 비틀며 하는 작업을 하루 120분(2시간) 이상 하나요?', 'time',
        [_crit_field('unsupported', '몸을 받칠 지지대가 없나요?', 'truth', to={'criterion': 'unsupported'}),
         _crit_field('posture_restricted', '자세를 바꾸기 어려운 작업인가요?', 'truth', to={'criterion': 'posture_restricted'}),
         _exposure('C4_NECK_FLEX', '목 굽힘'), _exposure('C4_TRUNK_FLEX', '허리 굽힘'), _exposure('C4_NECK_TWIST', '목 비틀림'),
         _exposure('C4_TRUNK_TWIST', '허리 비틀림'), _exposure('C4_UNION', '위 자세 하루 총 시간(겹치는 시간은 한 번만)')]),
    5: ('쪼그림·무릎 굽힘', '쪼그려 앉거나 무릎을 굽힌 자세로 하는 작업을 하루 120분(2시간) 이상 하나요?', 'time',
        [_exposure('C5_SQUAT', '쪼그려 앉기'), _exposure('C5_KNEEL', '무릎 꿇기·굽히기'), _exposure('C5_UNION', '위 자세 하루 총 시간(겹치는 시간은 한 번만)')]),
    6: ('한 손 손가락 집기', '받치지 않은 손가락으로 1kg 이상(또는 힘 2kg 상당 이상)을 집는 작업을 하루 120분(2시간) 이상 하나요?', 'row',
        [_crit_field('unsupported', '손을 받치지 않고 하나요?', 'truth'), _crit_field('pinch_mass_kg', '집는 무게', unit='kg', chips=[0.5, 1, 2]),
         _crit_field('pinch_force_kg_equiv', '집는 힘(kg 상당)', unit='kg', chips=[1, 2, 4]), _crit_field('minutes', '하루 시간', unit='분/일', maximum=1440, chips=[60, 120, 240])]),
    7: ('한 손 들기·쥐기', '받치지 않은 한 손으로 4.5kg 이상(또는 쥐는 힘 4.5kg 상당 이상)을 드는 작업을 하루 120분(2시간) 이상 하나요?', 'row',
        [_crit_field('unsupported', '손을 받치지 않고 하나요?', 'truth'), _crit_field('single_hand_mass_kg', '한 손으로 드는 무게', unit='kg', chips=[2, 4.5, 8]),
         _crit_field('grip_force_kg_equiv', '쥐는 힘(kg 상당)', unit='kg', chips=[2, 4.5, 8]), _crit_field('minutes', '하루 시간', unit='분/일', maximum=1440, chips=[60, 120, 240])]),
    8: ('25kg 이상 들기', '25kg 이상 물체를 하루 10회 이상 드나요?', 'row',
        [_crit_field('load_mass_kg', '물체 무게', unit='kg', chips=[10, 25, 30]), _crit_field('lift_count_day', '하루 들기 횟수', unit='회/일', chips=[5, 10, 20])]),
    9: ('10kg 이상 불편한 위치 들기', '10kg 이상 물체를 무릎 아래나 어깨 위, 팔을 뻗은 위치에서 하루 25회 이상 드나요?', 'row',
        [_crit_field('load_mass_kg', '물체 무게', unit='kg', chips=[10, 15, 20]), _crit_field('below_knee_count_day', '무릎 아래에서 드는 횟수', unit='회/일', chips=[0, 10, 25]),
         _crit_field('above_shoulder_count_day', '어깨 위에서 드는 횟수', unit='회/일', chips=[0, 10, 25]), _crit_field('extended_arm_count_day', '팔을 뻗어 드는 횟수', unit='회/일', chips=[0, 10, 25]),
         _crit_field('union_count_day', '위 세 가지 합계(겹치는 횟수는 한 번만)', unit='회/일', chips=[0, 25, 50])]),
    10: ('반복 들기', '4.5kg 이상을 분당 2회 이상, 하루 120분(2시간) 이상 드나요?', 'row',
         [_crit_field('load_mass_kg', '물체 무게', unit='kg', chips=[4.5, 8, 15]), _crit_field('lift_rate_min', '1분에 드는 횟수', unit='회/분', chips=[1, 2, 4]),
          _crit_field('minutes', '하루 시간', unit='분/일', maximum=1440, chips=[60, 120, 240])]),
    11: ('손·무릎 충격', '손이나 무릎으로 물체를 때리는 실제 충격을 시간당 10회 이상, 하루 120분(2시간) 이상 가하나요?', 'row',
         [_crit_field('impact_verified', '실제로 물체에 충격이 가해지나요?', 'truth'), _crit_field('impact_rate_hour', '1시간에 가하는 횟수', unit='회/시간', chips=[5, 10, 20]),
          _crit_field('minutes', '하루 시간', unit='분/일', maximum=1440, chips=[60, 120, 240])]),
}


def criteria_questions(signals):
    """One card per statutory criterion. Each card asks present/absent first; values stay empty until answered."""
    hints = {3: signals.get('arm_raised'), 4: signals.get('trunk_flexed') or signals.get('neck_flexed'), 5: signals.get('knee_bent')}
    cards = []
    for number, (title, ask, kind, fields) in CRITERIA.items():
        group = '법정 기준 1~5호 (시간)' if number <= 5 else '법정 기준 6~11호 (무게·횟수)'
        cards.append({'id': f'crit_{number}', 'group': group, 'kind': 'criterion', 'criterion': number, 'text': f'{number}호 · {title}',
                      'ask': ask, 'help': '사진에서 이 자세가 보였어요.' if hints.get(number) else '', 'hint': bool(hints.get(number)),
                      'mode': kind, 'fields': fields, 'target': {'type': 'criterion_card', 'criterion': number}, 'show_if': None})
    return cards


def questions(views, measured, signals, front=()):
    """Rule-based questions for everything the photos could not settle, grouped into a few steps.

    views maps 'LEFT' / 'FRONT' / 'RIGHT' to that photo's guess (or None when no person was found).
    """
    have = {(m['scope'], m['field']): m['value'] for m in measured}
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
        q.append(_choice(field, '자세', BASE_TEXT[field], {'type': 'manual', 'scope': 'COMMON', 'field': field}, BASE_CHOICES[field],
                         '사진 각도를 쓰지 않으므로 직접 골라 주세요.' if measured_here else '사진에서 이 각도를 읽지 못했어요.',
                         show_if=photo_unusable if measured_here else None))
    for field in ('upper_arm_base', 'lower_arm_base'):
        seen = {side: have[(side, field)] for side in ('LEFT', 'RIGHT') if (side, field) in have}
        q.append(_choice(field, '자세', '양팔 ' + BASE_TEXT[field], {'type': 'manual', 'scope': 'BOTH', 'field': field}, BASE_CHOICES[field],
                         '사진 각도를 쓰지 않으므로 직접 골라 주세요.' if seen else '사진에서 이 각도를 읽지 못했어요.',
                         show_if=photo_unusable if seen else None))
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
        _choice('wrist_base', '자세', '손목은 얼마나 꺾이나요?', {'type': 'manual', 'scope': 'BOTH', 'field': 'wrist_base'},
                [{'value': 1, 'label': '15° 이내'}, {'value': 2, 'label': '15° 넘게'}]),
        _checklist('posture_flags', '자세', '해당하는 자세를 모두 골라 주세요.', [
            _flag('neck_turn', '목을 비틀거나 옆으로 기울임', ('COMMON', 'neck_twisted', 'YES', 'NO'), ('COMMON', 'neck_side_bent', None, 'NO')),
            _flag('trunk_turn', '몸통을 비틀거나 옆으로 기울임', ('COMMON', 'trunk_twisted', 'YES', 'NO'), ('COMMON', 'trunk_side_bent', None, 'NO')),
            _flag('wrist_twist', '손목을 비틀거나 옆으로 꺾음', ('BOTH', 'wrist_deviated_or_twisted', 'YES', 'NO')),
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
        for item in question.get('items', []):
            hint = hints.get(item['key'])
            item['suggested'] = bool(hint and hint['suggested'])
            item['evidence'] = f"정면·후면 사진 {hint['label']} {hint['value_deg']}°" if hint else None
    q += criteria_questions(signals)
    q += work_info_questions()
    return q
