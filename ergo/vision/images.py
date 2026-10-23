"""Encode the registered, already-cropped image without retaining EXIF metadata."""
import base64
import hashlib
import io
from pathlib import Path
from PIL import Image, ImageOps

def prepare(file_path,policy):
    source=Path(file_path).read_bytes()
    with Image.open(io.BytesIO(source)) as original:
        image=ImageOps.exif_transpose(original)
        source_size=image.size
        if image.mode in ('RGBA','LA') or 'transparency' in image.info:
            rgba=image.convert('RGBA');image=Image.new('RGB',rgba.size,'white');image.paste(rgba,mask=rgba.getchannel('A'))
        else:image=image.convert('RGB')
        image.thumbnail((policy['max_edge'],policy['max_edge']),Image.Resampling.LANCZOS)
        encoded=io.BytesIO();image.save(encoded,format='JPEG',quality=policy['jpeg_quality'],optimize=True)
        data=encoded.getvalue()
    metadata=dict(source_sha256=hashlib.sha256(source).hexdigest(),encoded_sha256=hashlib.sha256(data).hexdigest(),
        source_width=source_size[0],source_height=source_size[1],width=image.width,height=image.height,
        mime_type='image/jpeg',bytes=len(data),detail=policy['detail'],max_edge=policy['max_edge'],jpeg_quality=policy['jpeg_quality'])
    return metadata,'data:image/jpeg;base64,'+base64.b64encode(data).decode('ascii')
