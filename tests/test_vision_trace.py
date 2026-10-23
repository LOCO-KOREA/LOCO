import base64
import hashlib
import importlib.util
from pathlib import Path
import unittest

class VisionTrace(unittest.TestCase):
    def test_images_are_hashed_without_changing_the_original_request(self):
        file=Path(__file__).parent/'vision_trace/sitecustomize.py';spec=importlib.util.spec_from_file_location('vision_trace_safe',file);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        raw=b'fixture-image-bytes';uri='data:image/jpeg;base64,'+base64.b64encode(raw).decode()
        original=dict(model='gpt-6-luna',input=[dict(role='user',content=[dict(type='input_image',image_url=uri,detail='high')])],extra_headers={'Authorization':'never log'})
        recorded=module.safe_record(original);image=recorded['input'][0]['content'][0]
        self.assertEqual(original['input'][0]['content'][0]['image_url'],uri)
        self.assertEqual(image['type'],'input_image');self.assertEqual(image['image_url']['raw_sha256'],hashlib.sha256(raw).hexdigest());self.assertEqual(image['image_url']['data_uri_sha256'],hashlib.sha256(uri.encode()).hexdigest())
        self.assertEqual(image['image_url']['raw_bytes'],len(raw));self.assertNotIn('extra_headers',recorded);self.assertNotIn(uri,str(recorded))

if __name__=='__main__':unittest.main()
