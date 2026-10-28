"""Real temporary SQLite -> prepared snapshot -> original-form PDF counterexamples."""
from copy import deepcopy
from io import BytesIO
from pathlib import Path
import base64
import sqlite3
import tempfile
import threading
import unittest
from unittest.mock import patch

import pdfplumber
from pypdf import PdfReader
from backend.contracts import validate_request
from backend.engine.task_defaults import task_input
from backend.service.application import create_service
from backend.service import pdf_exports
from backend.report.form_mapping import map_snapshot


class PdfExportTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        self.ctx=create_service(self.root/'case.db')
        self.survey=self.ctx.dispatch('create_survey',{'draft':{
            'survey_type':'REGULAR','survey_date':'2026-10-22','investigator':'검증 조사자',
            'department':'검증 부서','process':'포장 공정','title':'임시 DB 검증'}})
        self.task=self.task_create('원래 작업')
        self.other=self.task_create('포함하면 안 되는 다른 작업')

    def task_create(self,name):
        draft=task_input({'task_name':name,'conditions':{'work_intensity':3,'work_frequency':2,
             'method_description':'상자를 옮기는 입력 원문','hazard_factors':'허리 굽힘',
             'hazard_causes':'바닥에 놓인 상자를 듦','one_off':'NO','annual_work_days':220,'daily_work_min':480}})
        return self.ctx.dispatch('create_task',{'survey_id':self.survey['survey_id'],'draft':draft})

    def params(self,**changes):
        spec={'task_ids':[self.task['task_id']],'analysis_ids':[],'include_representative':False}
        spec.update(changes)
        return {'survey_id':self.survey['survey_id'],'spec':spec}

    def preview(self,**changes):
        return self.ctx.prepare_dispatch('preview_pdf',self.params(**changes))()

    def test_preview_is_actual_pdf_without_file_or_log_and_filters_other_task(self):
        result=self.preview()
        data=base64.b64decode(result['data_url'].split(',',1)[1])
        self.assertTrue(data.startswith(b'%PDF-'))
        self.assertEqual(result['page_count'],4)
        reader=PdfReader(BytesIO(data))
        texts=[p.extract_text() for p in reader.pages]
        self.assertIn('원래 작업',texts[0])
        self.assertNotIn('포함하면 안 되는 다른 작업','\n'.join(texts))
        self.assertTrue(result['warnings'],'warnings remain available outside the PDF')
        self.assertNotIn('홍길동','\n'.join(texts))
        self.assertEqual(self.ctx.dispatch('list_export_logs',{'survey_id':self.survey['survey_id']}),[])
        self.assertEqual(list(self.root.glob('*.pdf')),[])
        self.assertEqual(result['format'],'PDF')
        with pdfplumber.open(BytesIO(data)) as doc:
            self.assertEqual(doc.pages[1].crop((436,472,518,498)).extract_text(),'6')

    def test_export_appends_one_log_with_original_selected_snapshot(self):
        destination=self.root/'result.pdf'
        params=self.params(destination=str(destination))
        prepared=self.ctx.prepare_dispatch('export_pdf',params)
        self.ctx.dispatch('rename_task',{'task_id':self.task['task_id'],'task_name':'나중 이름'})
        result=prepared()
        self.assertTrue(destination.exists())
        text=PdfReader(destination).pages[0].extract_text()
        self.assertIn('원래 작업',text)
        self.assertNotIn('나중 이름',text)
        logs=self.ctx.store('list_export_logs',self.survey['survey_id'])
        self.assertEqual(len(logs),1)
        self.assertEqual(logs[0]['receipt']['format'],'PDF')
        self.assertEqual([t['task_id'] for t in logs[0]['snapshot']['tasks']],[self.task['task_id']])
        self.assertEqual(result['export_id'],logs[0]['export_id'])

    def test_invalid_selection_and_spec_rejected(self):
        for changes in ({'task_ids':[]},{'task_ids':[True]},{'task_ids':[1,1]},
                        {'include_representative':'YES'},{'comparison':{}},
                        {'analysis_ids':[False]}):
            with self.subTest(changes=changes),self.assertRaises(ValueError):
                validate_request('preview_pdf',self.params(**changes))
        for destination in ('bad.xlsx','',False):
            with self.assertRaises(ValueError):
                validate_request('export_pdf',self.params(destination=destination))
        with self.assertRaises(ValueError):self.preview(task_ids=[99999])

    def test_analysis_from_unselected_task_rejected(self):
        analysis=self.ctx.new_analysis(self.other,['judgment'])
        with self.assertRaises(ValueError):self.preview(analysis_ids=[analysis['analysis_id']])

    def test_old_selected_analysis_does_not_borrow_current_input(self):
        analysis=self.ctx.new_analysis(self.task,['judgment'])
        self.ctx.run(analysis,['judgment'],threading.Event(),self.ctx.analysis_token(analysis['analysis_id']))
        self.ctx.dispatch('rename_task',{'task_id':self.task['task_id'],'task_name':'현재 이름'})
        result=self.preview(analysis_ids=[analysis['analysis_id']])
        text=PdfReader(BytesIO(base64.b64decode(result['data_url'].split(',',1)[1]))).pages[0].extract_text()
        self.assertIn('원래 작업',text)
        self.assertNotIn('현재 이름',text)
        self.assertTrue(result['has_stale'])

    def test_missing_scores_stay_empty_not_zero_and_snapshot_unchanged(self):
        snap=self.ctx.export_snapshot(self.survey['survey_id'],[],False)
        snap['tasks'][0]['conditions']['work_intensity']=None
        before=deepcopy(snap)
        model=map_snapshot(snap)
        self.assertIsNone(model['tasks'][0]['total'])
        self.assertEqual(model['tasks'][0]['frequency'],2)
        self.assertEqual(snap,before)
        for value in (0,6,True,'3',3.0):
            broken=deepcopy(snap);broken['tasks'][0]['conditions']['work_intensity']=value
            with self.assertRaises(ValueError):map_snapshot(broken)

    def test_multi_task_has_separate_three_page_groups(self):
        result=self.preview(task_ids=[self.other['task_id'],self.task['task_id']])
        pages=PdfReader(BytesIO(base64.b64decode(result['data_url'].split(',',1)[1]))).pages
        self.assertIn(self.other['task_name'],pages[0].extract_text())
        self.assertIn(self.task['task_name'],pages[3].extract_text())
        self.assertIn('작성방법',pages[6].extract_text())
        self.assertEqual(len(pages),7,'three pages per task, instructions once, no automatic appendix')

    def test_analysis_details_do_not_create_appendix(self):
        analysis=self.ctx.new_analysis(self.task,['judgment'])
        self.ctx.run(analysis,['judgment'],threading.Event(),self.ctx.analysis_token(analysis['analysis_id']))
        result=self.preview(analysis_ids=[analysis['analysis_id']])
        reader=PdfReader(BytesIO(base64.b64decode(result['data_url'].split(',',1)[1])))
        self.assertEqual(len(reader.pages),4)
        text='\n'.join(p.extract_text() for p in reader.pages)
        for unwanted in ('자세 분석(REBA)','기준별 초안과 조사자 결론','출력 기준','필요한 입력:','입력 원문·보완사항'):
            self.assertNotIn(unwanted,text)
        self.assertEqual(self.ctx.dispatch('list_export_logs',{'survey_id':self.survey['survey_id']}),[])

    def test_file_write_failure_does_not_log_or_leave_temp_file(self):
        destination=self.root/'nonexistent'/'result.pdf'
        with self.assertRaises(OSError):
            self.ctx.prepare_dispatch('export_pdf',self.params(destination=str(destination)))()
        self.assertEqual(self.ctx.store('list_export_logs',self.survey['survey_id']),[])
        self.assertEqual(list(self.root.rglob('.loco-pdf-*')),[])

    def test_render_failure_preserves_existing_file(self):
        destination=self.root/'result.pdf';destination.write_bytes(b'old complete file')
        with patch.object(pdf_exports.pdf,'render',side_effect=RuntimeError('render failed')):
            with self.assertRaises(RuntimeError):
                self.ctx.prepare_dispatch('export_pdf',self.params(destination=str(destination)))()
        self.assertEqual(destination.read_bytes(),b'old complete file')
        self.assertEqual(self.ctx.store('list_export_logs',self.survey['survey_id']),[])

    def test_log_failure_reports_existing_file(self):
        destination=self.root/'result.pdf'
        with patch.object(pdf_exports.storage,'create_export_log',side_effect=sqlite3.DatabaseError('log failed')):
            with self.assertRaisesRegex(sqlite3.DatabaseError,'PDF.*result.pdf'):
                self.ctx.prepare_dispatch('export_pdf',self.params(destination=str(destination)))()
        self.assertTrue(destination.read_bytes().startswith(b'%PDF-'))

    def test_preparation_binds_database_and_copies_request(self):
        current=[str(self.root/'case.db')]
        self.ctx.db_provider=lambda:current[0]
        params=self.params(destination=str(self.root/'bound.pdf'))
        prepared=self.ctx.prepare_dispatch('export_pdf',params)
        params['spec']['task_ids']=[self.other['task_id']]
        current[0]=str(self.root/'different.db')
        prepared()
        self.assertFalse(Path(current[0]).exists())
        current[0]=str(self.root/'case.db')
        logs=self.ctx.store('list_export_logs',self.survey['survey_id'])
        self.assertEqual(logs[0]['receipt']['task_ids'],[self.task['task_id']])

    def test_deleted_survey_cannot_get_a_late_or_reused_id_export_log(self):
        params=self.params(destination=str(self.root/'deleted.pdf'))
        prepared=self.ctx.prepare_dispatch('export_pdf',params)
        self.ctx.dispatch('delete_survey',{'survey_id':self.survey['survey_id']})
        replacement=self.ctx.dispatch('create_survey',{'draft':{'title':'다른 조사'}})
        self.assertEqual(replacement['survey_id'],self.survey['survey_id'])
        with self.assertRaisesRegex(LookupError,'PDF.*삭제'):
            prepared()
        self.assertEqual(self.ctx.store('list_export_logs',replacement['survey_id']),[])

    def test_pdf_json_lines_worker_does_not_block_following_lookup(self):
        from backend.service import json_lines
        import io,json
        started,release=threading.Event(),threading.Event()
        threads=[];real_thread=threading.Thread;original_render=pdf_exports.pdf.render
        def render(*args,**kwargs):
            started.set()
            if not release.wait(3):raise RuntimeError('test timeout')
            return original_render(*args,**kwargs)
        def thread(*args,**kwargs):
            worker=real_thread(*args,**kwargs);threads.append(worker);return worker
        output=io.StringIO()
        with patch.object(json_lines,'prepare_dispatch',self.ctx.prepare_dispatch),patch.object(json_lines,'dispatch',self.ctx.dispatch),patch.object(json_lines.threading,'Thread',side_effect=thread),patch.object(pdf_exports.pdf,'render',side_effect=render),patch('sys.stdout',output):
            try:
                json_lines.handle({'request_id':1,'method':'preview_pdf','params':self.params()})
                self.assertTrue(started.wait(2))
                json_lines.handle({'request_id':2,'method':'get_survey','params':{'survey_id':self.survey['survey_id']}})
                first=json.loads(output.getvalue().splitlines()[0]);self.assertEqual(first['request_id'],2)
            finally:
                release.set()
                for worker in threads:worker.join(5)
        responses=[json.loads(s) for s in output.getvalue().splitlines()]
        self.assertEqual([r['request_id'] for r in responses],[2,1])
        self.assertTrue(all(r['result']['ok'] for r in responses))

    def test_pdf_thread_start_failure_and_invalid_input_error_boundary(self):
        from backend.service import json_lines
        import io,json
        output=io.StringIO()
        with patch.object(json_lines,'prepare_dispatch',self.ctx.prepare_dispatch),patch.object(json_lines.threading.Thread,'start',side_effect=RuntimeError('start failed')),patch('sys.stdout',output):
            json_lines.handle({'request_id':3,'method':'preview_pdf','params':self.params()})
        response=json.loads(output.getvalue())
        self.assertEqual(response['request_id'],3)
        self.assertEqual(response['result']['error']['code'],'EXPORT_ERROR')
        output=io.StringIO()
        with patch.object(json_lines,'prepare_dispatch',self.ctx.prepare_dispatch),patch('sys.stdout',output):
            json_lines.handle({'request_id':4,'method':'preview_pdf','params':self.params(task_ids=[])})
        self.assertEqual(json.loads(output.getvalue())['result']['error']['code'],'FILE_ERROR')

    def test_long_original_text_is_preserved_in_appendix_not_clipped(self):
        import re
        text='긴 원문 보존 검증 ' * 250 + '마지막문장확인'
        draft=task_input({'task_name':'긴 설명 작업','conditions':{'method_description':text}})
        task=self.ctx.dispatch('create_task',{'survey_id':self.survey['survey_id'],'draft':draft})
        result=self.preview(task_ids=[task['task_id']])
        reader=PdfReader(BytesIO(base64.b64decode(result['data_url'].split(',',1)[1])))
        self.assertIn('별첨 참조',reader.pages[1].extract_text())
        alltext='\n'.join(p.extract_text() for p in reader.pages[4:])
        self.assertIn(re.sub(r'\s+','',text),re.sub(r'\s+','',alltext))

    def test_unavailable_glyph_does_not_overwrite_existing_output(self):
        draft=task_input({'task_name':'글꼴 검증','conditions':{'method_description':'지원 안 되는 문자 '+chr(0x10ffff)}})
        task=self.ctx.dispatch('create_task',{'survey_id':self.survey['survey_id'],'draft':draft})
        destination=self.root/'old.pdf';destination.write_bytes(b'existing')
        with self.assertRaisesRegex(ValueError,'글꼴'):
            self.ctx.prepare_dispatch('export_pdf',self.params(task_ids=[task['task_id']],destination=str(destination)))()
        self.assertEqual(destination.read_bytes(),b'existing')
        self.assertEqual(self.ctx.store('list_export_logs',self.survey['survey_id']),[])

    def test_photo_bytes_fixed_in_preparation_and_no_file_read_when_excluded(self):
        from PIL import Image
        image_path=self.root/'photo.png';Image.new('RGB',(20,40),(255,0,0)).save(image_path)
        mapper=pdf_exports.map_snapshot
        def mapped(snap):
            model=mapper(snap)
            model['tasks'][0]['photo']={'file_path':str(image_path)}
            return model
        with patch.object(pdf_exports,'map_snapshot',side_effect=mapped):
            prepared=pdf_exports.prepare(self.ctx,'preview_pdf',self.params(include_representative=True))
        original_bytes=prepared['images'][self.task['task_id']]
        Image.new('RGB',(20,40),(0,0,255)).save(image_path)
        self.assertNotEqual(image_path.read_bytes(),original_bytes)
        result=pdf_exports.finish(prepared)
        page=PdfReader(BytesIO(base64.b64decode(result['data_url'].split(',',1)[1]))).pages[2]
        image=list(page.images)[0].image.convert('RGB')
        self.assertEqual(image.getpixel((10,20)),(255,0,0))
        with patch.object(pdf_exports,'map_snapshot',side_effect=mapped),patch.object(Path,'read_bytes',side_effect=AssertionError('must not read photo')):
            no_photo=pdf_exports.prepare(self.ctx,'preview_pdf',self.params(include_representative=False))
        self.assertEqual(no_photo['images'],{})


if __name__=='__main__':unittest.main()
