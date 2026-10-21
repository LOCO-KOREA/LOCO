"""Photo-first quick assessment service. Reads only; the task is saved by the usual input APIs."""
from ergo.engine import movenet
from ergo.engine import quick_assess

VIEWS = ('LEFT', 'FRONT', 'RIGHT')


def handle_quick_preview(ctx, method, p):
    task = ctx.require('task', p['task_id'])
    settings = ctx.settings()['analysis']
    confidence = settings['pose_model'].get('confidence_min', 0.5)
    views, rows_by_view, side_groups, front, diagnostics = {}, {}, [], [], []
    for view in VIEWS:
        if view not in p['views']:
            continue
        photo = ctx.require('photo', p['views'][view])
        if photo['task_id'] != task['task_id']:
            raise ValueError('사진이 이 작업에 등록되어 있지 않습니다')
        slot = {'slot_no': 1, 'photo_id': photo['photo_id'], 'camera_side': None, 'forward_direction': None,
                'side_view_verified': 'UNKNOWN', 'observation': {}}
        with ctx.analysis_lock:
            pose = movenet.process(slot, {'photos': [photo], 'settings': settings})
        guess = quick_assess.guess_view(pose['points'], confidence) if pose['points'] else None
        notes = [d for d in pose['diagnostics'] if d['code'] != 'INVALID_CAMERA']
        label = quick_assess.VIEW_KO[view]
        if not pose['points']:
            pass
        elif guess is None:
            notes.append(dict(code='VIEW_UNKNOWN', message=f'{label}에서 사람을 충분히 찾지 못했어요.', field_path=None))
        elif view == 'FRONT':
            if guess['orientation'] != 'FRONT':
                notes.append(dict(code='NOT_FRONT', message=f'{label}이 정면·후면이 아니라 옆모습으로 보여요. 기울임 제안을 쓰지 않아요.', field_path=None))
            else:
                front = quick_assess.front_measure(pose['points'], confidence)
        elif guess['orientation'] == 'FRONT':
            notes.append(dict(code='NOT_SIDE', message=f'{label}이 옆모습이 아니라 정면으로 보여요. 이 사진의 각도는 쓰지 않아요.', field_path=None))
        elif photo.get('width_px') and photo.get('height_px'):
            if guess['camera_side'] != view:
                other = quick_assess.VIEW_KO['RIGHT' if view == 'LEFT' else 'LEFT'].replace(' 사진', '')
                notes.append(dict(code='OTHER_SIDE', message=f'{label}인데 {other} 몸이 더 잘 보여요. 칸을 바꿔 넣었는지 확인해 주세요.', field_path=None))
            rows, measured = quick_assess.side_measure(pose['points'], photo['width_px'], photo['height_px'], settings, view, guess['forward_direction'])
            rows_by_view[view] = rows
            side_groups.append(measured)
        diagnostics += notes
        views[view] = dict(photo_id=photo['photo_id'], width_px=photo.get('width_px'), height_px=photo.get('height_px'),
                           points=pose['points'], guess=guess, diagnostics=notes)
    measured = quick_assess.merge_measured(*side_groups)
    signals = quick_assess.posture_signals(rows_by_view, settings['posture_profile'])
    score = quick_assess.provisional(measured, front, settings) if measured or any(f['suggested'] for f in front) else None
    return dict(views=views, measured=measured, front=front, score=score, signals=signals, diagnostics=diagnostics,
                questions=quick_assess.questions({v: views[v]['guess'] for v in views}, measured, signals, front))
