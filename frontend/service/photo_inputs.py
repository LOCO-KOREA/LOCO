"""S04 capture adapter using the shared storage and the documented photo DTOs."""
import base64
from copy import deepcopy
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path

from ergo.db import storage
from task_inputs import INPUT_KEYS, observation, task_by_id


class PhotoError(Exception):
    pass


def read_image(file_path):
    try:
        from PIL import Image, ImageOps
    except ImportError as error:
        raise PhotoError('사진을 읽으려면 실행 중인 Python에 frontend/requirements.txt의 Pillow를 설치하세요.') from error
    try:
        with Image.open(file_path) as source:
            if source.format not in {'JPEG', 'PNG'}:
                raise PhotoError('JPG 또는 PNG 사진을 선택하세요.')
            return ImageOps.exif_transpose(source).convert('RGB')
    except (OSError, ValueError) as error:
        raise PhotoError(f'사진을 읽을 수 없습니다: {file_path} ({error})') from error


def save_input(task, data, db_path):
    if any(data[key] != task[key] for key in INPUT_KEYS):
        storage.update_task_input(task['task_id'], data, datetime.now(timezone.utc).isoformat(), db_path=db_path)
    return task_by_id(task['task_id'], db_path)


def dispatch_photo(method, params, db_path):
    if method == 'get_photo_preview':
        photo = params['photo']
        with read_image(photo['file_path']) as image:
            output = BytesIO()
            image.save(output, format='PNG')
            return dict(photo_id=photo['photo_id'], width_px=image.width, height_px=image.height,
                        data_url='data:image/png;base64,' + base64.b64encode(output.getvalue()).decode('ascii'))
    if method == 'import_photos':
        task_by_id(params['task_id'], db_path)
        added, unreadable = [], []
        for file_path in params['file_paths']:
            try:
                with read_image(file_path) as image:
                    metadata = dict(file_path=file_path, file_name=Path(file_path).name,
                                    width_px=image.width, height_px=image.height, consent='UNKNOWN', notes=[])
            except PhotoError as error:
                unreadable.append(dict(file_path=file_path, message=str(error)))
                continue
            photo_id = storage.create_photo(params['task_id'], metadata, db_path=db_path)
            added.append(storage.get_photo(photo_id, db_path=db_path))
        return dict(added=added, unreadable=unreadable, notes=[])
    if method == 'delete_photo':
        storage.delete_photo(params['photo_id'], db_path=db_path)
        return dict(message='사진 등록과 현재 배정을 삭제했습니다. 원본 파일은 유지됩니다.')
    if method == 'update_photo':
        photo = storage.get_photo(params['photo_id'], db_path=db_path)
        if photo is None:
            raise LookupError('사진을 찾을 수 없습니다.')
        metadata = {key:deepcopy(value) for key,value in photo.items() if key not in {'photo_id','task_id'}}
        changed_path = photo['file_path'] != params['file_path']
        if changed_path:
            with read_image(params['file_path']) as image:
                metadata.update(file_path=params['file_path'], file_name=Path(params['file_path']).name,
                                width_px=image.width, height_px=image.height, notes=[])
        metadata['consent'] = params['consent']
        if metadata != {key:value for key,value in photo.items() if key not in {'photo_id','task_id'}}:
            storage.update_photo(photo['photo_id'], metadata, db_path=db_path)
            if changed_path:
                task = task_by_id(photo['task_id'], db_path)
                if any(slot['photo_id'] == photo['photo_id'] for slot in task['capture']['slots']):
                    storage.update_task_input(task['task_id'], {key:deepcopy(task[key]) for key in INPUT_KEYS},
                                              datetime.now(timezone.utc).isoformat(), db_path=db_path)
        return storage.get_photo(photo['photo_id'], db_path=db_path)
    if method == 'set_capture':
        task = task_by_id(params['task_id'], db_path)
        data = {key:deepcopy(task[key]) for key in INPUT_KEYS}
        capture = deepcopy(params['capture'])
        camera_changed = any(capture[key] != task['capture'][key] for key in ['camera_side','forward_direction'])
        old_slots = {slot['slot_no']:slot for slot in task['capture']['slots']}
        replaced = {slot['slot_no'] for slot in capture['slots'] if slot['photo_id'] != old_slots[slot['slot_no']]['photo_id']}
        for slot in capture['slots']:
            if camera_changed or slot['slot_no'] in replaced:
                slot['observation'] = observation()
        data['manual'] = [] if camera_changed else [value for value in data['manual'] if value['slot_no'] not in replaced]
        data['capture'] = capture
        return save_input(task, data, db_path)
    raise LookupError('아직 연결하지 않은 사진 메서드입니다: ' + method)
