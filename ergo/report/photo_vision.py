"""Render only the photo observations owned by the selected immutable input."""
from ergo.intake.contract import SESSION_KEY
from ergo.intake.photo_facts import VIEW_LABELS
from ergo.user_language import user_text


def observation_rows(task_name, source):
    saved = (source.get('conditions') or {}).get(SESSION_KEY) or {}
    vision = saved.get('photo_vision') or {}
    photos = vision.get('photos') or []
    if not photos:
        return []
    from ergo.vision.contract import OBSERVATION_LABELS, OBSERVATION_STATUS_LABELS
    owners = {slot.get('photo_id') for slot in (source.get('capture') or {}).get('slots', [])}
    rows = []
    seen = set()
    for photo in photos:
        owner = photo.get('photo_id')
        if owner not in owners or owner in seen or photo.get('photo_active') is False:
            continue
        seen.add(owner)
        name = VIEW_LABELS.get(photo.get('view'), '등록한 사진')
        observations = photo.get('observations') or {}
        for key, label in OBSERVATION_LABELS.items():
            item = observations.get(key)
            if not isinstance(item, dict):
                continue
            status = OBSERVATION_STATUS_LABELS.get(item.get('status'), '확인이 필요해요')
            value = item.get('value') or status
            evidence = list(dict.fromkeys(text for text in (item.get('evidence'), item.get('reason')) if text))
            rows.append([task_name, name, label, user_text(value), status,
                         user_text(' · '.join(evidence))])
    return rows


def observation_sheet(context):
    rows = [row for task in context['tasks']
            for row in observation_rows(task['name'], task['source'])]
    if not rows:
        return None
    return dict(name='AI 사진 관찰', title='AI 사진 관찰',
        lead='AI가 이 사진에서 보이는 자세와 동작을 정리했어요. 측정한 관절 각도는 자세 분석(REBA) 시트에서 확인할 수 있어요.',
        tables=[dict(heading=None, columns=['작업', '사진', '관찰 항목', '사진에서 본 모습', '확인 상태', '근거·확인할 부분'],
                     rows=rows, widths=[22, 24, 20, 52, 26, 72])], notes=[])
