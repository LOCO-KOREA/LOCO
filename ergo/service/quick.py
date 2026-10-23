"""Photo-first quick assessment service. Reads only; the task is saved by the usual input APIs."""
import os

from ergo.pose import engine as pose_engine
from ergo.engine import quick_assess
from ergo.engine import quick_intake
from ergo.gpt import client as gpt_client

VIEWS = ('LEFT', 'FRONT', 'RIGHT')


def handle_quick_preview(ctx, method, p):
    task = ctx.require('task', p['task_id'])
    settings = ctx.settings()['analysis']
    confidence = settings['pose_model'].get('confidence_min', 0.5)
    views, rows_by_view, side_groups, front, diagnostics = {}, {}, [], [], []
    seated = overhead = False
    for view in VIEWS:
        if view not in p['views']:
            continue
        photo = ctx.require('photo', p['views'][view])
        if photo['task_id'] != task['task_id']:
            raise ValueError('사진이 이 작업에 등록되어 있지 않습니다')
        slot = {'slot_no': 1, 'photo_id': photo['photo_id'], 'camera_side': None, 'forward_direction': None,
                'side_view_verified': 'UNKNOWN', 'observation': {}}
        with ctx.analysis_lock:
            pose = pose_engine.process(slot, {'photos': [photo], 'settings': settings})
        guess = quick_assess.guess_view(pose['points'], confidence) if pose['points'] else None
        notes = [d for d in pose['diagnostics'] if d['code'] != 'INVALID_CAMERA']
        label = quick_assess.VIEW_KO[view]
        if not pose['points']:
            pass
        elif guess is None:
            notes.append(dict(code='VIEW_UNKNOWN', message=f'{label}에서 사람을 충분히 찾지 못했어요.', field_path=None))
        elif view == 'FRONT':
            # Nobody stands perfectly square to the camera: a slightly turned worker is still a front photo.
            if guess['orientation'] == 'SIDE':
                notes.append(dict(code='NOT_FRONT', message=f'{label}이 옆모습으로 보여요. 기울임 제안은 쓰지 않아요.', field_path=None))
            else:
                front = quick_assess.front_measure(pose['points'], confidence)
        elif guess['orientation'] == 'FRONT':
            notes.append(dict(code='NOT_SIDE', message=f'{label}이 옆모습이 아니라 정면으로 보여요. 이 사진의 각도는 쓰지 않아요.', field_path=None))
        elif photo.get('width_px') and photo.get('height_px'):
            near = guess['camera_side']
            if near != view:
                other = quick_assess.VIEW_KO[near].replace(' 사진', '')
                notes.append(dict(code='OTHER_SIDE', message=f'{label} 칸인데 {other} 몸이 더 잘 보여서 {other} 몸 기준으로 쟀어요. 칸이 맞는지 확인해 주세요.', field_path=None))
            rows, measured = quick_assess.side_measure(pose['points'], photo['width_px'], photo['height_px'], settings, near, guess['forward_direction'], view,
                                                       oblique=guess['orientation'] == 'OBLIQUE')
            seated = seated or quick_assess.seated_signal(pose['points'], near, confidence)
            rows_by_view.setdefault(near, []).extend(rows)
            side_groups.append(measured)
        overhead = overhead or bool(pose['points']) and quick_assess.arm_overhead_signal(pose['points'], confidence)
        diagnostics += notes
        views[view] = dict(photo_id=photo['photo_id'], width_px=photo.get('width_px'), height_px=photo.get('height_px'),
                           points=pose['points'], guess=guess, diagnostics=notes,engine=pose.get('engine'),
                           world_points=pose.get('world_points',[]),world_angles=pose.get('world_angles',[]),connections=pose.get('connections',[]),quality=pose.get('quality'))
    measured = quick_assess.merge_measured(*side_groups)
    signals = quick_assess.posture_signals(rows_by_view, settings['posture_profile'])
    if overhead:
        signals['arm_raised'] = True
    if seated:
        signals.update(seated=True, knee_bent=False)
    score = quick_assess.provisional(measured, front, settings, seated) if measured or any(f['suggested'] for f in front) else None
    return dict(views=views, measured=measured, front=front, score=score, signals=signals, diagnostics=diagnostics,
                questions=quick_assess.questions({v: views[v]['guess'] for v in views}, measured, signals, front))


def handle_quick_interpret(ctx, method, p):
    """Fill question boxes from one sentence. Reads only: nothing is saved, and only the sentence goes to the model."""
    text = p['text'].strip()
    settings = ctx.settings()
    if not (settings['gpt_enabled'] and settings.get('gpt_model')):
        return dict(items=[], dropped=[], reason='DISABLED')
    boxes = quick_intake.catalogue()
    raw, reason = gpt_client.interpret(text, quick_intake.prompt_targets(boxes), quick_intake.schema(boxes), settings['gpt_model'], os.environ.get('OPENAI_API_KEY'), settings)
    if reason:
        return dict(items=[], dropped=[], reason=reason)
    items, dropped = quick_intake.validate(raw, text)
    return dict(items=items, dropped=dropped, reason=None if items else 'NOTHING_FOUND')
