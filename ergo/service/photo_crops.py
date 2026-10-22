"""Register a cropped copy without changing the selected source image."""
import base64
import hashlib
import json
from io import BytesIO
from pathlib import Path
from uuid import uuid4

from ergo.db import storage
from ergo.engine.images import read_image


def decoded_source(path, expected_hash=None):
    raw = Path(path).read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    if expected_hash is not None and digest != expected_hash:
        raise ValueError('선택한 원본 사진이 변경되었습니다. 사진을 다시 선택해 주세요.')
    return read_image(BytesIO(raw)), digest


def handle_preview(ctx, method, p):
    image, digest = decoded_source(p['file_path'])
    with image:
        output = BytesIO()
        image.save(output, format='PNG')
        return dict(data_url='data:image/png;base64,' + base64.b64encode(output.getvalue()).decode('ascii'),
                    width_px=image.width, height_px=image.height, source_sha256=digest)


def handle_import(ctx, method, p):
    with ctx.db_lock:
        database = str(ctx.db_path)
        task = ctx.require('task', p['task_id'])
        created_at = task['created_at']
        if p.get('task_created_at', created_at) != created_at:
            raise LookupError('사진을 등록할 작업이 삭제되었거나 바뀌었습니다.')
    if database == ':memory:':
        raise ValueError('크롭 사진을 보관하려면 파일 DB를 사용해 주세요.')
    image, digest = decoded_source(p['file_path'], p['source_sha256'])
    rect = p['crop']
    x, y, w, h = (rect[key] for key in ('x', 'y', 'width', 'height'))
    with image:
        if x + w > image.width or y + h > image.height:
            raise ValueError('선택 영역이 사진 범위를 벗어났습니다.')
        size = dict(width=image.width, height=image.height)
        output = BytesIO()
        with image.crop((x, y, x + w, y + h)) as cropped:
            cropped.save(output, format='PNG')
    destination = Path(database).resolve().parent / 'media' / 'photos' / (uuid4().hex + '.png')
    created = False
    try:
        # The original task lifetime and database stay fixed throughout decoding.
        with ctx.db_lock:
            if str(ctx.db_path) != database:
                raise LookupError('데이터 저장 위치가 바뀌었습니다. 사진을 다시 선택해 주세요.')
            current = ctx.require('task', p['task_id'])
            if current['created_at'] != created_at:
                raise LookupError('사진을 등록할 작업이 삭제되었거나 바뀌었습니다.')
            destination.parent.mkdir(parents=True, exist_ok=True)
            with destination.open('xb') as stream:
                created = True
                stream.write(output.getvalue())
            provenance = dict(source_path=str(Path(p['file_path']).resolve()), source_sha256=digest,
                              source_size=size, crop=rect, coordinates='EXIF_CORRECTED_PIXELS')
            meta = dict(file_path=str(destination), file_name=Path(p['file_path']).stem + '_crop.png',
                        width_px=w, height_px=h, consent='UNKNOWN',
                        notes=[dict(code='PHOTO_CROP', field_path=None,
                                    message=json.dumps(provenance, ensure_ascii=False))])
            identity = storage.create_photo(p['task_id'], meta, db_path=database)
            # Do not introduce a second fallible DB lookup after the committed insert.
            return dict(meta, photo_id=identity, task_id=p['task_id'])
    except Exception:
        if created:
            destination.unlink(missing_ok=True)
        raise
