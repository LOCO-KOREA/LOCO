"""Provider-independent pose configuration, topology and transport contract."""
import copy
import math
import os

VERSION='LOCO_POSE_V1'
COCO_NAMES=('nose','left_eye','right_eye','left_ear','right_ear','left_shoulder','right_shoulder','left_elbow','right_elbow','left_wrist','right_wrist','left_hip','right_hip','left_knee','right_knee','left_ankle','right_ankle')
MEDIAPIPE_NAMES=('nose','left_eye_inner','left_eye','left_eye_outer','right_eye_inner','right_eye','right_eye_outer','left_ear','right_ear','mouth_left','mouth_right','left_shoulder','right_shoulder','left_elbow','right_elbow','left_wrist','right_wrist','left_pinky','right_pinky','left_index','right_index','left_thumb','right_thumb','left_hip','right_hip','left_knee','right_knee','left_ankle','right_ankle','left_heel','right_heel','left_foot_index','right_foot_index')
COMMON_CONNECTIONS=(('left_shoulder','right_shoulder'),('left_hip','right_hip'))+tuple((side+'_'+a,side+'_'+b) for side in ('left','right') for a,b in (('ear','shoulder'),('shoulder','hip'),('shoulder','elbow'),('elbow','wrist'),('hip','knee'),('knee','ankle')))
HAND_FOOT_CONNECTIONS=tuple((side+'_'+a,side+'_'+b) for side in ('left','right') for a,b in (('wrist','thumb'),('wrist','index'),('wrist','pinky'),('index','pinky'),('ankle','heel'),('heel','foot_index'),('ankle','foot_index')))
MODELS={}
for variant,sha in (
    ('heavy','64437af838a65d18e5ba7a0d39b465540069bc8aae8308de3e318aad31fcbc7b'),
    ('full','5134a3aad27a58b93da0088d431f366da362b44e3ccfbe3462b3827a839011b1')):
    identity='mediapipe-'+variant
    MODELS[identity]=dict(model_id=identity,provider='mediapipe',variant=variant,name='MediaPipe Pose Landmarker '+variant.title(),version='1',
        preprocess_version='EXIF_MEDIAPIPE_IMAGE_V1',input_size=256,point_count=len(MEDIAPIPE_NAMES),confidence_kind='MIN_VISIBILITY_PRESENCE',
        model_path='models/pose_landmarker_'+variant+'.task',model_sha256=sha,
        url=f'https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_{variant}/float16/1/pose_landmarker_{variant}.task')
MODELS['movenet-lightning']=dict(model_id='movenet-lightning',provider='movenet',variant='lightning',name='MoveNet Lightning singlepose TFLite float16',version='4',
    preprocess_version='EXIF_OPENCV_LETTERBOX_V2',input_size=192,point_count=len(COCO_NAMES),confidence_kind='MOVENET_SCORE',
    model_path='models/movenet_lightning.tflite',model_sha256='0fac2226112d0371903ca86e3853cec24ef603a0b2f96f589b180f0ebdd135ab',
    url='https://tfhub.dev/google/lite-model/movenet/singlepose/lightning/tflite/float16/4?lite-format=tflite')
DEFAULT_MODEL='mediapipe-heavy'
NUM_POSES=1
FIELDS=(dict(key='model_id',label='자세 추론 모델',kind='choice',env='LOCO_POSE_MODEL_ID'),
        dict(key='model_path',label='모델 파일 경로',kind='text',env='LOCO_POSE_MODEL_PATH'),
        dict(key='model_sha256',label='모델 SHA-256',kind='text',env='LOCO_POSE_MODEL_SHA256'),
        dict(key='confidence_min',label='관절 사용 문턱',kind='number',default=0.5,minimum=0,maximum=1,env='LOCO_POSE_CONFIDENCE_MIN'),
        dict(key='detection_min',label='인물 검출 문턱',kind='number',default=0.5,minimum=0,maximum=1,env='LOCO_POSE_DETECTION_MIN'),
        dict(key='presence_min',label='자세 검출 문턱',kind='number',default=0.5,minimum=0,maximum=1,env='LOCO_POSE_PRESENCE_MIN'))
KEYS=tuple(field['key'] for field in FIELDS)
METADATA_KEYS=tuple(k for k in MODELS[DEFAULT_MODEL] if k not in KEYS and k!='url')
PHOTO_SOURCES=('POSE','MOVENET')
WORLD_ANGLES=(dict(code='ELBOW_FLEX_3D',label='팔꿈치 굽힘',joints=('shoulder','elbow','wrist')),
              dict(code='KNEE_FLEX_3D',label='무릎 굽힘',joints=('hip','knee','ankle')))
# Image-plane observability heuristics, not a clinical accuracy estimate. The
# scoring category/margin remain the existing REBA wrist contract (15 / 5 deg).
WRIST_JOINTS=dict(mediapipe=('elbow','wrist','index','pinky','thumb'),movenet=())
WRIST_POLICY=dict(version='WRIST_IMAGE_2D_V1',angle_code='WRIST_FLEX_2D',coordinate_space='ORIGINAL_IMAGE_2D',
    category_boundary_deg=15.0,boundary_margin_deg=5.0,confidence_min=0.85,frame_margin_px=2.0,
    forearm_min_px=24.0,hand_min_px=12.0,hand_forearm_min_ratio=0.12,hand_forearm_max_ratio=0.9,
    finger_length_min_ratio=0.55,finger_axis_max_difference_deg=12.0,hand_width_max_ratio=0.18,
    thumb_length_min_ratio=0.25,thumb_length_max_ratio=1.25,max_angle_deg=90.0,
    sensitivity_pixel_min=1.5,sensitivity_image_ratio=0.002,max_sensitivity_deg=8.0)
WRIST_REASONS=dict(
    WRIST_MISSING_POINTS='사진에서 손목과 손끝 위치를 충분히 찾지 못했어요.',
    WRIST_POINTS_LOW_CONFIDENCE='손이나 손끝이 가려져 손목 굽힘을 정확히 구분하기 어려워요.',
    WRIST_HAND_OUT_OF_FRAME='손목이나 손끝이 사진 밖 또는 가장자리에 있어 굽힘을 확인하기 어려워요.',
    WRIST_PROJECTION_SHORT='사진에서 손이나 팔이 너무 짧게 보여 손목 굽힘을 구분하기 어려워요.',
    WRIST_PLANE_UNCLEAR='손바닥 방향 때문에 굽힘과 옆으로 꺾임을 사진에서 구분하기 어려워요.',
    WRIST_FINGERS_DISAGREE='손가락 방향이 서로 달라 손목 굽힘을 안정적으로 구분하기 어려워요.',
    WRIST_UNSTABLE='손끝 위치의 작은 차이로 손목 각도가 크게 달라져 직접 확인이 필요해요.',
    WRIST_BOUNDARY='사진에서 잰 손목 굽힘이 15도 경계에 가까워 직접 확인이 필요해요.',
    WRIST_DIRECTION_UNCONFIRMED='손목의 옆모습이 분명하지 않아 굽힘과 옆으로 꺾임을 구분하기 어려워요.')


def for_model(identity):
    if identity not in MODELS: raise ValueError('등록되지 않은 자세 모델입니다: '+str(identity))
    value={k:v for k,v in MODELS[identity].items() if k!='url'}
    value.update({f['key']:f['default'] for f in FIELDS if 'default' in f})
    return value


def defaults():
    value=for_model(os.environ.get('LOCO_POSE_MODEL_ID',DEFAULT_MODEL))
    for field in FIELDS:
        if field['env'] in os.environ:
            raw=os.environ[field['env']];value[field['key']]=float(raw) if field['kind']=='number' else raw
    return normalize(value)


def normalize(value=None,*,reading=False):
    if value is None:return defaults()
    if not isinstance(value,dict):raise ValueError('자세 모델 설정은 객체여야 합니다')
    legacy='model_id' not in value and (value.get('point_count')==len(COCO_NAMES) or str(value.get('name','')).startswith('MoveNet'))
    identity='movenet-lightning' if legacy else value.get('model_id',DEFAULT_MODEL)
    result=for_model(identity)
    unknown=set(value)-set(result)
    if unknown:raise ValueError('지원하지 않는 자세 설정: '+', '.join(sorted(unknown)))
    for key in METADATA_KEYS:
        if not reading and key in value and value[key]!=result[key]:raise ValueError('자세 모델 메타데이터가 선택한 모델과 다릅니다: '+key)
    result.update({k:value[k] for k in KEYS if k in value})
    for field in FIELDS:
        item=result[field['key']]
        if field['kind']=='number':
            if type(item) not in (int,float) or not math.isfinite(item) or not field['minimum']<=item<=field['maximum']:
                raise ValueError(field['label']+'은 0~1의 유한 수여야 합니다')
        elif not isinstance(item,str):raise ValueError(field['label']+'은 문자열이어야 합니다')
    digest=result['model_sha256']
    if digest and (len(digest)!=64 or any(c not in '0123456789abcdef' for c in digest.lower())):raise ValueError('모델 SHA-256 형식이 올바르지 않습니다')
    if not result['model_path'].strip():raise ValueError('모델 파일 경로가 필요합니다')
    return result


def topology(provider):
    if provider=='mediapipe':return MEDIAPIPE_NAMES,COMMON_CONNECTIONS+HAND_FOOT_CONNECTIONS
    if provider=='movenet':return COCO_NAMES,COMMON_CONNECTIONS
    raise ValueError('등록되지 않은 자세 공급자입니다: '+str(provider))


def public_contract():
    fields=copy.deepcopy(list(FIELDS));fields[0]['choices']=[dict(value=k,label=v['name']) for k,v in MODELS.items()]
    return dict(version=VERSION,models={k:for_model(k) for k in MODELS},fields=fields,defaults=defaults(),
                landmarks={p:list(topology(p)[0]) for p in ('mediapipe','movenet')},
                connections={p:list(topology(p)[1]) for p in ('mediapipe','movenet')},world_angles=copy.deepcopy(WORLD_ANGLES),
                wrist_image_measurement=dict(policy=copy.deepcopy(WRIST_POLICY),joints=copy.deepcopy(WRIST_JOINTS),reasons=copy.deepcopy(WRIST_REASONS)))
