"""Independent counterexamples for removed contracts and 2.0 runtime boundaries."""
import copy
import tempfile
import threading
import sqlite3
import unittest
from pathlib import Path
from unittest.mock import patch

from ergo import CONTRACT_VERSION
from ergo.contracts import validate_request
from ergo.db import storage
from ergo.engine import burden_rules
from ergo.engine.joint_angles import angles
from ergo.engine.movenet import NAMES
from ergo.engine.reba_scoring import calculate_reba, candidates
from ergo.engine.task_defaults import task_input
from ergo.service import application as app
from scripts.audit_contract import audit


class ContractCleanup(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.db=str(Path(self.temp.name)/'isolated.db')
        patcher=patch.object(app,'DB',self.db);patcher.start();self.addCleanup(patcher.stop)
        self.survey=app.dispatch('create_survey',{'draft':{'title':'isolated','survey_type':'REGULAR'}})
        self.task=app.dispatch('create_task',{'survey_id':self.survey['survey_id'],'draft':{}})

    def calculate(self):
        return app.dispatch('recalculate_judgments',{'task_id':self.task['task_id']})

    def test_document_registry_dispatch_and_renderer_use_one_contract(self):
        self.assertEqual(CONTRACT_VERSION,'2.0')
        self.assertEqual(audit()['documented_methods'],audit()['implemented_methods'])
        import ergo.service
        self.assertFalse(hasattr(ergo.service,'get_service'))

    def test_retired_methods_and_parameter_aliases_are_rejected(self):
        for method in ('create_unit_task','attach_still','confirm_survey','save_task_inputs'):
            with self.subTest(method=method),self.assertRaises(LookupError): app.dispatch(method,{})
        with self.assertRaises(ValueError): validate_request('apply_ai_text',{'analysis_id':1,'text_id':'x','edited_text':True})
        for wrong in (True,0,-1,'1'):
            with self.subTest(wrong=wrong),self.assertRaises(ValueError): validate_request('get_task',{'task_id':wrong})

    def test_legacy_creation_does_not_silently_drop_old_fields(self):
        for draft in ({'schema_version':'1.3','task_kind':'BOX_LIFT'}, {'task_kind':'BOX_LIFT'}, {'schema_version':'99'}):
            with self.subTest(draft=draft),self.assertRaises(ValueError):
                app.dispatch('create_task',{'survey_id':self.survey['survey_id'],'draft':draft})
        self.assertEqual(len(app.dispatch('list_tasks',{'survey_id':self.survey['survey_id']})),1)

    def test_narrow_setters_cannot_store_the_retired_legal_shape(self):
        before=app.require('task',self.task['task_id'])
        with self.assertRaises(ValueError): app.dispatch('set_legal_inputs',{'task_id':self.task['task_id'],'legal':{'lift_count_day':100}})
        self.assertEqual(app.require('task',self.task['task_id']),before)

    def test_manual_record_cannot_reference_a_foreign_or_removed_photo(self):
        with self.assertRaises(ValueError):
            app.dispatch('set_manual_values',{'task_id':self.task['task_id'],'manual':[dict(slot_no=7,photo_id=999,scope='COMMON',field='trunk_base',value=1)]})
        self.assertEqual(app.require('task',self.task['task_id'])['manual'],[])

    def test_manual_missing_value_is_rejected_before_any_partial_save(self):
        before=copy.deepcopy(app.require('task',self.task['task_id']))
        with self.assertRaisesRegex(ValueError,'value'):
            app.dispatch('set_manual_values',{'task_id':self.task['task_id'],'manual':[dict(slot_no=7,photo_id=1,scope='COMMON',field='trunk_base')]})
        self.assertEqual(app.require('task',self.task['task_id']),before)

    def test_retired_boolean_consent_and_string_review_flags_are_rejected(self):
        with self.assertRaises(ValueError):validate_request('update_photo',{'photo_id':1,'file_path':'photo.jpg','consent':True})
        with self.assertRaises(ValueError):app.dispatch('set_survey_review',{'survey_id':self.survey['survey_id'],'review':{'reviewed':'false'}})

    def test_unknown_calculation_versions_are_rejected_without_writing_settings(self):
        config=app.settings(); original=copy.deepcopy(config)
        config['analysis']['burden_rule']='MOEL_2020_12_V1'
        with self.assertRaises(ValueError):app.dispatch('update_settings',{'settings':config})
        self.assertEqual(app.settings(),original)

    def test_legacy_settings_are_read_without_rewrite_and_new_snapshot_names_actual_rules(self):
        config=app.settings(); config['analysis']['burden_rule']='MOEL_2020_12_V1'
        config['analysis']['pose_model']['preprocess_version']='OLD_PREPROCESS'
        storage.update_settings(config,db_path=self.db)
        original=copy.deepcopy(storage.get_settings(db_path=self.db))
        current=app.settings()
        self.assertEqual(current['analysis']['burden_rule'],'MOEL_2020_12_GENERAL_V2')
        self.assertEqual(storage.get_settings(db_path=self.db),original)
        self.assertEqual(self.calculate()['snapshot']['settings']['burden_rule'],'MOEL_2020_12_GENERAL_V2')

    def test_gpt_improvement_purpose_has_its_own_summary_and_currentness(self):
        a=self.calculate(); config=app.settings();config['gpt_enabled']=True
        app.dispatch('update_settings',{'settings':config})
        with patch.object(app.gpt_client,'generate',return_value=(None,'INJECTED_FAILURE')):
            ai=app.dispatch('generate_ai_text',{'analysis_id':a['analysis_id'],'purpose':'IMPROVEMENT_ADVICE'})
        self.assertEqual(ai['text']['input_summary']['purpose'],'IMPROVEMENT_ADVICE')
        self.assertTrue(ai['source_current'])
        self.assertTrue(app.analysis(a['analysis_id'])['ai'][0]['source_current'])

        current=app.require('task',self.task['task_id'])
        edited=app.task_input(current)
        edited['conditions']['method_description']='입력 변경 후 저장'
        app.dispatch('save_task_input',{'task_id':self.task['task_id'],'input':edited})
        historical=app.analysis(a['analysis_id'])
        self.assertEqual(historical['currentness'],'STALE')
        self.assertFalse(historical['ai'][0]['source_current'])

    def test_terminal_analysis_cannot_be_restored_by_a_delayed_worker(self):
        a=self.calculate()
        for terminal in ('FAILED','CANCELED'):
            a=app.new_analysis(self.task,['judgment'])
            storage.update_analysis_result(a['analysis_id'],lambda result: None,job=(terminal,'terminal'),db_path=self.db)
            app.persist_analysis(a)
            self.assertEqual(app.analysis(a['analysis_id'])['status'],terminal)

    def test_stale_running_object_cannot_roll_finished_job_back(self):
        a=app.new_analysis(self.task,['judgment']); stale=copy.deepcopy(a)
        app.run(a,['judgment'],threading.Event(),app._context.analysis_token(a['analysis_id'])); app.persist_analysis(stale)
        self.assertEqual(app.analysis(a['analysis_id'])['status'],'FINISHED')

    def test_historical_scores_are_read_without_an_old_calculation_entrypoint(self):
        with self.assertRaises(ValueError): burden_rules.calculate({}, {}, '1.3')
        with self.assertRaises(ValueError): calculate_reba({'schema_version':'1.3'},None)

    def test_photo_ratio_legacy_minutes_are_not_promoted_to_a_direct_measurement(self):
        from ergo.legacy.v13 import upgrade_task
        legacy=dict(schema_version='1.3',task_id=7,survey_id=1,input_revision=0,task_name='legacy',conditions={},manual=[],capture={'slots':[]},legal={'exposures':[dict(condition_code='C1_KEYBOARD_FOCUSED',minutes=240,source='PHOTO_RATIO')]})
        original=copy.deepcopy(legacy)
        converted=upgrade_task(legacy)
        self.assertIsNone(converted['legal']['exposures'][0]['minutes'])
        self.assertEqual(legacy,original)
        self.assertEqual(converted['legacy_input']['legal']['exposures'][0]['minutes'],240)

    def test_configured_confidence_threshold_is_used_at_the_exact_boundary(self):
        points=[dict(name=name,x_px=200+7*i,y_px=200+2*i,confidence=.7) for i,name in enumerate(NAMES)]
        self.assertTrue(all(x['value_deg'] is not None for x in angles(points,'SCREEN_RIGHT',1000,1000,.7)))
        self.assertTrue(all(x['value_deg'] is None for x in angles(points,'SCREEN_RIGHT',1000,1000,.70001)))
        slot=dict(slot_no=7,photo_id=1,camera_side='LEFT',forward_direction='SCREEN_RIGHT',side_view_verified='YES',observation=dict(single_person='YES',full_frame='YES',normal_work='YES'))
        pose={'angles':angles(points,'SCREEN_RIGHT',1000,1000,.5)}
        self.assertTrue(all(x['proposed_value'] is None for x in candidates(slot,pose,'LEFT',.8)))

    def test_multiple_tasks_and_survey_deletion_preserve_other_data_and_exports(self):
        self.calculate()
        receipt=app.dispatch('export_excel',{'survey_id':self.survey['survey_id'],'spec':{'destination':str(Path(self.temp.name)/'old.xlsx'),'analysis_ids':[],'include_representative':False,'comparisons':[]}})
        old_export=copy.deepcopy(storage.list_export_logs(self.survey['survey_id'],db_path=self.db)[0])
        other=app.dispatch('create_task',{'survey_id':self.survey['survey_id'],'draft':{'task_name':'other'}})
        separate=app.dispatch('create_survey',{'draft':{'title':'separate','survey_type':'INITIAL'}})
        app.dispatch('delete_task',{'task_id':self.task['task_id']})
        self.assertEqual(app.require('task',other['task_id'])['task_name'],'other')
        self.assertEqual(storage.list_export_logs(self.survey['survey_id'],db_path=self.db)[0],old_export)
        self.assertTrue(Path(receipt['file_path']).is_file())
        app.dispatch('delete_survey',{'survey_id':self.survey['survey_id']})
        self.assertEqual(app.dispatch('list_surveys',{})[0]['survey_id'],separate['survey_id'])

    def test_failed_export_does_not_claim_a_success_log(self):
        self.calculate()
        with patch.object(app.report,'render',side_effect=OSError('denied')),self.assertRaises(OSError):
            app.dispatch('export_excel',{'survey_id':self.survey['survey_id'],'spec':{'destination':'denied.xlsx','analysis_ids':[],'include_representative':False}})
        self.assertEqual(storage.list_export_logs(self.survey['survey_id'],db_path=self.db),[])

    def test_retired_relational_database_is_rejected_before_creating_new_tables(self):
        from ergo.db.connection import open_db
        path=Path(self.temp.name)/'retired.db'
        db=sqlite3.connect(path);db.execute('CREATE TABLE unit_task (unit_task_id INTEGER)');db.commit();db.close()
        before=path.read_bytes()
        with self.assertRaises(sqlite3.DatabaseError):open_db(path)
        self.assertEqual(path.read_bytes(),before)


if __name__=='__main__':unittest.main()
