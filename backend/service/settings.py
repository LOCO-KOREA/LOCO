"""LOCO 2.0 settings service. Dependencies are supplied by Runtime."""
import copy
import os
import math
from backend.legacy.v13 import upgrade_task
from backend.engine.task_defaults import default_settings, PREPROCESS_VERSION
from backend import ai_config
from backend import pose_contract

def settings(ctx):
    value = ctx.store('get_settings')
    if value is None:
        value = default_settings()
        ctx.store('update_settings', value)
    # An old settings record is read without rewriting user data. New snapshots
    # always name the actual current engine and preprocessing implementation.
    current = default_settings()
    current.update(ai_config.values(value))
    ui=value.get('ui') or {}
    if type(ui.get('loco_visible')) is bool: current['ui']['loco_visible']=ui['loco_visible']
    if ui.get('loco_mode') in ('normal','quiet'): current['ui']['loco_mode']=ui['loco_mode']
    old=value.get('analysis') or {}
    if old.get('pose_model') is not None:current['analysis']['pose_model']=pose_contract.normalize(old['pose_model'],reading=True)
    profile=old.get('posture_profile') or {}
    for key in current['analysis']['posture_profile']:
        v=profile.get(key)
        if key!='version' and isinstance(v,(int,float)) and not isinstance(v,bool) and math.isfinite(v):
            current['analysis']['posture_profile'][key]=v
    return dict(current, gpt_key_present=bool(os.environ.get('OPENAI_API_KEY')),gpt_contract=ai_config.public_contract(),pose_contract=pose_contract.public_contract())

def validate_settings(ctx, value):
    if not isinstance(value, dict) or not isinstance(value.get('analysis'), dict):
        raise ValueError('2.0 분석 설정이 필요합니다')
    config = value['analysis']
    baseline = default_settings()['analysis']
    if set(config) != set(baseline):
        raise ValueError('분석 설정 키가 2.0 계약과 다릅니다')
    for key in ('burden_rule', 'reba_rule'):
        if config[key] != baseline[key]:
            raise ValueError('지원하지 않는 계산 규칙 버전입니다')
    model = config['pose_model']
    profile = config['posture_profile']
    pose_contract.normalize(model)
    if not isinstance(profile, dict) or set(profile) != set(baseline['posture_profile']) or profile['version'] != baseline['posture_profile']['version']:
        raise ValueError('자세 기술태그 설정 계약이 다릅니다')
    if any((isinstance(v, bool) or not isinstance(v, (int, float)) or (not math.isfinite(v)) for k, v in profile.items() if k != 'version')):
        raise ValueError('기술각도는 유한 수여야 합니다')
    ai_config.values(value)
    ui = value.get('ui')
    if not isinstance(ui, dict) or type(ui.get('loco_visible')) is not bool or ui.get('loco_mode') not in ('normal', 'quiet'):
        raise ValueError('안내 위젯 설정 형식이 올바르지 않습니다')

def handle_get_settings(ctx, method, p):
    return ctx.settings()

def handle_update_settings(ctx, method, p):
    ctx.validate_settings(p['settings'])
    value = copy.deepcopy(p['settings'])
    value['analysis']['pose_model']=pose_contract.normalize(value['analysis']['pose_model'])
    old = ctx.settings()
    changed = {key for key in old['analysis'] if value['analysis'].get(key) != old['analysis'][key]}
    affected = {}
    if changed:
        for s in ctx.store('list_surveys'):
            for raw in ctx.store('list_tasks', s['survey_id']):
                t = upgrade_task(raw)
                if t.get('schema_version') != '2.0' or raw.get('schema_version') != '2.0':
                    continue
                scope = t.get('analysis_scope') or {}
                relevant = 'burden_rule' in changed and scope.get('judgment') or ('reba_rule' in changed and scope.get('reba')) or ('posture_profile' in changed and scope.get('tags')) or ('pose_model' in changed and any((scope.get(k) for k in ('pose', 'tags', 'reba'))))
                if 'pose_model' in changed:
                    manual = [m for m in t['manual'] if m.get('source') != 'AUTO_ACCEPTED']
                    relevant = relevant or manual != t['manual']
                    t['manual'] = manual
                if relevant:
                    affected[t['task_id']] = ctx.task_input(t)
    ctx.store('update_settings', value, task_inputs=affected)
    return ctx.settings()
