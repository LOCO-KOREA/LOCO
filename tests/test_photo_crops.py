"""Real image pixels and temporary SQLite records for pre-registration cropping."""
import base64
import hashlib
import json
from io import BytesIO
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from PIL import Image
from ergo.engine.task_defaults import task_input
from ergo.service.application import create_service
from ergo.service import photo_crops


class PhotoCropTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.ctx=create_service(self.root/'case.db')
        self.survey=self.ctx.dispatch('create_survey',{'draft':{'title':'크롭 검증','survey_type':'REGULAR'}})
        self.task=self.create_task()
        self.source=self.root/'원본.png'
        with Image.new('RGB',(8,6)) as image:
            image.putdata([(x*20,y*30,10) for y in range(6) for x in range(8)])
            image.save(self.source)
        self.raw=self.source.read_bytes()

    def create_task(self):
        return self.ctx.dispatch('create_task',{'survey_id':self.survey['survey_id'],'draft':task_input({'task_name':'사진 작업'})})

    def params(self):
        return dict(task_id=self.task['task_id'],task_created_at=self.task['created_at'],file_path=str(self.source),
                    source_sha256=hashlib.sha256(self.raw).hexdigest(),crop=dict(x=2,y=1,width=3,height=2))

    def test_preview_does_not_register_and_crop_saves_only_selected_pixels(self):
        preview=self.ctx.dispatch('preview_photo_file',{'file_path':str(self.source)})
        self.assertEqual((preview['width_px'],preview['height_px']),(8,6))
        self.assertEqual(preview['source_sha256'],hashlib.sha256(self.raw).hexdigest())
        self.assertEqual(self.ctx.store('list_photos',self.task['task_id']),[])
        self.assertFalse((self.root/'media').exists())
        photo=self.ctx.dispatch('import_cropped_photo',self.params())
        with Image.open(photo['file_path']) as crop:
            self.assertEqual(crop.size,(3,2))
            self.assertEqual([crop.getpixel((x,y)) for y in range(2) for x in range(3)],[(40,30,10),(60,30,10),(80,30,10),(40,60,10),(60,60,10),(80,60,10)])
        self.assertEqual(self.source.read_bytes(),self.raw)
        self.assertEqual(json.loads(photo['notes'][0]['message'])['crop'],self.params()['crop'])
        registered=self.ctx.dispatch('get_task',{'task_id':self.task['task_id']})['photos']
        self.assertEqual([p['file_path'] for p in registered],[photo['file_path']])
        displayed=self.ctx.dispatch('get_photo_preview',{'photo':photo})
        with Image.open(BytesIO(base64.b64decode(displayed['data_url'].split(',')[1]))) as image:
            self.assertEqual(image.size,(3,2))
        analysis=self.ctx.new_analysis(self.ctx.require('task',self.task['task_id']),['pose'])
        self.assertEqual(analysis['snapshot']['photos'][0]['file_path'],photo['file_path'])

    def test_exif_orientation_is_applied_before_selection(self):
        with Image.new('RGB',(4,2)) as image:
            image.putdata([(x*40,y*90,0) for y in range(2) for x in range(4)])
            exif=image.getexif();exif[274]=6;image.save(self.source,exif=exif)
        preview=self.ctx.dispatch('preview_photo_file',{'file_path':str(self.source)})
        self.assertEqual((preview['width_px'],preview['height_px']),(2,4))
        p=self.params();p.update(source_sha256=preview['source_sha256'],crop=dict(x=0,y=0,width=1,height=2))
        photo=self.ctx.dispatch('import_cropped_photo',p)
        with Image.open(photo['file_path']) as cropped:
            self.assertEqual([cropped.getpixel((0,y)) for y in range(2)],[(0,90,0),(40,90,0)])

    def test_pdf_uses_cropped_pixels_when_this_photo_is_selected_as_representative(self):
        from ergo.service import pdf_exports
        from pypdf import PdfReader
        photo=self.ctx.dispatch('import_cropped_photo',self.params())
        mapper=pdf_exports.map_snapshot
        def selected(snapshot):
            model=mapper(snapshot)
            # Representative selection has its own REBA tests. Isolate the image
            # transport here: the selected photo must be the saved cropped copy.
            model['tasks'][0]['photo']=photo
            return model
        params=dict(survey_id=self.survey['survey_id'],spec=dict(task_ids=[self.task['task_id']],analysis_ids=[],include_representative=True))
        with patch.object(pdf_exports,'map_snapshot',side_effect=selected):
            prepared=pdf_exports.prepare(self.ctx,'preview_pdf',params)
        self.assertEqual(prepared['images'][self.task['task_id']],Path(photo['file_path']).read_bytes())
        result=pdf_exports.finish(prepared)
        reader=PdfReader(BytesIO(base64.b64decode(result['data_url'].split(',')[1])))
        picture=list(reader.pages[2].images)[0].image.convert('RGB')
        self.assertEqual(picture.size,(3,2))
        self.assertEqual(picture.getpixel((0,0)),(40,30,10))

    def test_invalid_rectangles_and_changed_source_do_not_register(self):
        for rect in [dict(x=-1,y=0,width=1,height=1),dict(x=0,y=0,width=0,height=1),
                     dict(x=0,y=0,width=1.5,height=1),dict(x=True,y=0,width=1,height=1),
                     dict(x=7,y=0,width=2,height=1),dict(x=0,y=6,width=1,height=1),{},None]:
            with self.subTest(rect=rect),self.assertRaises(ValueError):
                p=self.params();p['crop']=rect;self.ctx.dispatch('import_cropped_photo',p)
        with Image.new('RGB',(8,6),'blue') as image:image.save(self.source)
        with self.assertRaisesRegex(ValueError,'변경'):self.ctx.dispatch('import_cropped_photo',self.params())
        self.assertEqual(self.ctx.store('list_photos',self.task['task_id']),[])

    def test_full_image_and_multiple_crops_have_independent_paths(self):
        p=self.params();p['crop']=dict(x=0,y=0,width=8,height=6)
        a=self.ctx.dispatch('import_cropped_photo',p);b=self.ctx.dispatch('import_cropped_photo',p)
        self.assertNotEqual(a['file_path'],b['file_path'])
        self.ctx.dispatch('delete_photo',{'photo_id':a['photo_id']})
        self.assertTrue(Path(a['file_path']).exists(),'historical snapshots may still refer to this copy')
        with Image.open(b['file_path']) as image:self.assertEqual(image.size,(8,6))

    def test_registration_failure_removes_its_new_file(self):
        with patch.object(photo_crops.storage,'create_photo',side_effect=RuntimeError('DB failure')):
            with self.assertRaisesRegex(RuntimeError,'DB failure'):
                self.ctx.dispatch('import_cropped_photo',self.params())
        self.assertEqual(list((self.root/'media').rglob('*.png')),[])
        self.assertEqual(self.ctx.store('list_photos',self.task['task_id']),[])
        self.assertEqual(self.source.read_bytes(),self.raw)

    def test_deleted_task_reused_id_is_not_registered_to_new_task(self):
        real=photo_crops.decoded_source
        def replace(*args):
            result=real(*args)
            self.ctx.dispatch('delete_task',{'task_id':self.task['task_id']})
            replacement=self.create_task()
            self.assertEqual(replacement['task_id'],self.task['task_id'])
            return result
        with patch.object(photo_crops,'decoded_source',side_effect=replace):
            with self.assertRaises(LookupError):self.ctx.dispatch('import_cropped_photo',self.params())
        self.assertEqual(self.ctx.store('list_photos',self.task['task_id']),[])
        self.assertFalse((self.root/'media').exists())
        p=self.params();p['task_created_at']='deleted-task'
        with self.assertRaises(LookupError):self.ctx.dispatch('import_cropped_photo',p)


if __name__=='__main__':unittest.main()
