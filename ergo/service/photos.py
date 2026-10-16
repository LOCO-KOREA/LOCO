"""LOCO 2.0 photos service. Dependencies are supplied by Runtime."""
import base64
from io import BytesIO
from pathlib import Path
from ergo.engine.images import read_image

def handle_import_photos(ctx, method, p):
    ctx.require('task', p['task_id'])
    added = []
    unreadable = []
    for path in p['file_paths']:
        try:
            image = read_image(path)
            meta = dict(file_path=str(Path(path).resolve()), file_name=Path(path).name, width_px=image.width, height_px=image.height, consent='UNKNOWN', notes=[])
            identity = ctx.store('create_photo', p['task_id'], meta)
            added.append(ctx.require('photo', identity))
        except Exception as error:
            unreadable.append(dict(file_path=path, message=str(error)))
    return dict(added=added, unreadable=unreadable, notes=[])

def handle_get_photo_preview(ctx, method, p):
    photo = p['photo']
    image = read_image(photo['file_path'])
    output = BytesIO()
    image.save(output, format='PNG')
    return dict(photo_id=photo['photo_id'], data_url='data:image/png;base64,' + base64.b64encode(output.getvalue()).decode('ascii'), width_px=image.width, height_px=image.height)

def handle_update_photo(ctx, method, p):
    photo = ctx.require('photo', p['photo_id'])
    path_changed = photo['file_path'] != p['file_path']
    if path_changed:
        with read_image(p['file_path']) as image:
            photo.update(file_name=Path(p['file_path']).name, width_px=image.width, height_px=image.height, notes=[])
    photo.update(file_path=p['file_path'], consent=p['consent'])
    ctx.store('update_photo', photo['photo_id'], {k: v for k, v in photo.items() if k not in ['photo_id', 'task_id']})
    task = ctx.require('task', photo['task_id'])
    if path_changed and any((s['photo_id'] == photo['photo_id'] for s in task['capture']['slots'])):
        ctx.save_task(task, force=True)
    return photo

def handle_delete_photo(ctx, method, p):
    ctx.store('delete_photo', p['photo_id'])
    return dict(message='사진 참조를 삭제했습니다. 원본은 유지됩니다.')
