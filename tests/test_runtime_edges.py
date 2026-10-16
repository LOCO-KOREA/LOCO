"""Failure and async counterexamples on isolated 2.0 services and real image files."""
import copy
import json
import os
import sqlite3
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch
from PIL import Image

from ergo.db import storage
from ergo.engine import movenet
from ergo.engine.images import read_image
from ergo.engine.reba_scoring import calculate_reba
from ergo.service.application import create_service
from tests.test_v2_reba import snapshot
from ergo.report.comparisons import build_comparisons
from ergo.engine.task_defaults import default_settings


class RuntimeEdges(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.folder=Path(self.temp.name);self.db=str(self.folder/'isolated.db')
        self.app=create_service(self.db)
        self.survey=self.app.dispatch('create_survey',{'draft':{'title':'edge','survey_type':'REGULAR'}})
        self.task=self.app.dispatch('create_task',{'survey_id':self.survey['survey_id'],'draft':{}})

    def test_exif_rotation_is_decoded_without_modifying_the_original(self):
        file=self.folder/'rotated.jpg'; exif=Image.Exif();exif[274]=6
        Image.new('RGB',(40,80),'red').save(file,exif=exif)
        original=file.read_bytes()
        with read_image(file) as image:self.assertEqual(image.size,(80,40))
        result=self.app.dispatch('import_photos',{'task_id':self.task['task_id'],'file_paths':[str(file)]})
        self.assertEqual((result['added'][0]['width_px'],result['added'][0]['height_px']),(80,40))
        self.assertEqual(file.read_bytes(),original)

    def test_corrupt_and_missing_photos_are_explicit_failures_without_rows(self):
        file=self.folder/'broken.jpg';file.write_bytes(b'not an image')
        result=self.app.dispatch('import_photos',{'task_id':self.task['task_id'],'file_paths':[str(file),str(self.folder/'missing.jpg')]})
        self.assertEqual(len(result['unreadable']),2);self.assertEqual(result['added'],[])
        self.assertEqual(self.app.dispatch('get_task',{'task_id':self.task['task_id']})['photos'],[])

    def test_zero_targets_are_not_reported_as_completed_optional_modules(self):
        self.app.dispatch('set_analysis_scope',{'task_id':self.task['task_id'],'scope':dict(judgment=True,pose=True,tags=True,reba=True)})
        modules=['pose','tags','reba','judgment']; a=self.app.new_analysis(self.task,modules)
        token=self.app.analysis_token(a['analysis_id'])
        self.app.run(a,modules,threading.Event(),token); saved=self.app.analysis(a['analysis_id'])
        self.assertEqual(saved['module_states']['pose'],'FAILED')
        self.assertEqual(saved['module_states']['tags'],'INCOMPLETE')
        self.assertEqual(saved['module_states']['reba'],'INCOMPLETE')
        self.assertIsNone(saved['reba']['summary']['full_max'])

    def test_duplicate_photo_targets_stay_in_the_denominator_and_cannot_complete(self):
        data=snapshot();slot=copy.deepcopy(data['capture']['slots'][0]);slot['slot_no']=7
        data['capture']['slots'].append(slot)
        result=calculate_reba(data,None)
        self.assertEqual(result['summary']['total_slot_count'],2)
        self.assertEqual(result['summary']['complete_count'],0)
        self.assertIsNone(result['summary']['full_max'])
        self.assertTrue(all('duplicate_photo_id' in s['missing_fields'] for s in result['slots']))

    def test_compatible_reba_difference_includes_the_actual_manual_and_observation_changes(self):
        before=snapshot();before['capture']['protocol']='GENERAL_STILLS_V1';before['settings']=default_settings()['analysis']
        after=copy.deepcopy(before)
        for item in before['manual']:
            if item['scope']=='COMMON' and item['field']=='trunk_base':item['value']=4
        after['capture']['slots'][0]['observation']['evidence']={'source':'DIRECT_OBSERVATION','text':'after'}
        b=dict(analysis_id=1,task_id=1,snapshot=before,reba=calculate_reba(before,None))
        a=dict(analysis_id=2,task_id=1,snapshot=after,reba=calculate_reba(after,None))
        result=build_comparisons(dict(analyses=[b,a],comparison_specs=[dict(before_analysis_id=1,after_analysis_id=2,note=None)]))[0]
        self.assertEqual((b['reba']['summary']['full_max'],a['reba']['summary']['full_max']),(3,1))
        self.assertTrue(result['sampling_compatible']);self.assertEqual(result['reba_max_delta'],-2)
        self.assertTrue(any(x['field_path']=='manual.1.COMMON.trunk_base.value' for x in result['condition_changes']))
        self.assertTrue(any(x['field_path'].startswith('capture.') for x in result['condition_changes']))

    def test_late_analysis_does_not_restore_the_previous_latest_pointer(self):
        old=self.app.new_analysis(self.task,['judgment']);original=copy.deepcopy(old['snapshot'])
        old_token=self.app.analysis_token(old['analysis_id'])
        latest=self.app.new_analysis(self.task,['judgment'])
        latest_token=self.app.analysis_token(latest['analysis_id'])
        self.app.run(latest,['judgment'],threading.Event(),latest_token)
        self.app.run(old,['judgment'],threading.Event(),old_token)
        self.assertEqual(self.app.require('task',self.task['task_id'])['latest_analysis_id'],latest['analysis_id'])
        self.assertEqual(self.app.analysis(old['analysis_id'])['currentness'],'STALE')
        self.assertEqual(self.app.analysis(old['analysis_id'])['snapshot'],original)

    def test_gpt_completion_after_task_deletion_cannot_recreate_any_row(self):
        a=self.app.dispatch('recalculate_judgments',{'task_id':self.task['task_id']})
        config=self.app.settings();config['gpt_enabled']=True;self.app.dispatch('update_settings',{'settings':config})
        entered=threading.Event();release=threading.Event();errors=[]
        def generate(*args):entered.set();release.wait(5);return None,'INJECTED_FAILURE'
        def work():
            try:self.app.dispatch('generate_ai_text',{'analysis_id':a['analysis_id']})
            except Exception as error:errors.append(error)
        with patch('ergo.gpt.client.generate',side_effect=generate):
            thread=threading.Thread(target=work);thread.start()
            try:
                self.assertTrue(entered.wait(5));self.app.dispatch('delete_task',{'task_id':self.task['task_id']})
            finally:release.set();thread.join(5)
        self.assertFalse(thread.is_alive());self.assertIsInstance(errors[0],LookupError)
        self.assertIsNone(storage.get_analysis(a['analysis_id'],db_path=self.db))
        self.assertEqual(storage.list_tasks(self.survey['survey_id'],db_path=self.db),[])

    def test_export_log_failure_reports_the_created_file_without_a_success_receipt(self):
        self.app.dispatch('recalculate_judgments',{'task_id':self.task['task_id']});file=self.folder/'created.xlsx'
        with patch.object(storage,'create_export_log',side_effect=sqlite3.DatabaseError('injected')):
            with self.assertRaisesRegex(sqlite3.DatabaseError,'로그 저장에 실패'):
                self.app.dispatch('export_excel',{'survey_id':self.survey['survey_id'],'spec':dict(destination=str(file),analysis_ids=[],include_representative=False)})
        self.assertTrue(file.is_file());self.assertEqual(storage.list_export_logs(self.survey['survey_id'],db_path=self.db),[])

    def test_legacy_export_receipt_and_snapshot_are_not_rewritten_by_reading(self):
        data={'schema_version':'1.3','report_version':'1.3','old_extension':{'value':17}}
        storage.create_export_log(self.survey['survey_id'],'historical.xlsx',data,{'sheets':['SUMMARY']},'old',db_path=self.db)
        before=copy.deepcopy(storage.list_export_logs(self.survey['survey_id'],db_path=self.db))
        logs=self.app.dispatch('list_export_logs',{'survey_id':self.survey['survey_id']})
        self.assertEqual(logs[0]['receipt']['report_version'],'1.3')
        self.assertEqual(storage.list_export_logs(self.survey['survey_id'],db_path=self.db),before)

    def test_nonofficial_model_bytes_return_a_model_error_without_fake_points(self):
        file=self.folder/'image.png';Image.new('RGB',(40,80)).save(file)
        model=self.folder/'wrong-model.tflite';model.write_bytes(b'wrong model')
        with patch.object(movenet,'_interpreter',None),patch.dict(os.environ,{'LOCO_MOVENET_MODEL':str(model)}):
            result=movenet.process(dict(slot_no=7,photo_id=1),{'photos':[dict(photo_id=1,file_path=str(file))],'capture':{}})
        self.assertEqual(result['status'],'ERROR');self.assertEqual(result['points'],[])
        self.assertEqual(result['diagnostics'][0]['code'],'MODEL_ERROR')


if __name__=='__main__':unittest.main()
