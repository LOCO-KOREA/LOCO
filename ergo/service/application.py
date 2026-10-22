"""Compose per-application domain services. The external contract is dispatch only."""
import os
from ergo.contracts import validate_request
from ergo.db import storage
from ergo.db.connection import default_db_path
from ergo.engine import movenet as pose
from ergo.gpt import client as gpt_client
from ergo.report import workbook as report
from .runtime import Runtime
from . import task_inputs as _task_inputs
from . import settings as _settings
from . import analysis_records as _analysis_records
from . import analysis_jobs as _analysis_jobs
from . import reports as _reports
from . import surveys as _surveys
from . import photos as _photos
from . import explanations as _explanations
from . import quick as _quick
from . import intake as _intake
from functools import partial

RECALCULATION_METHODS = _analysis_jobs.RECALCULATION_METHODS

DB=os.environ.get('LOCO_DB_PATH') or str(default_db_path())
_HANDLERS = {'apply_ai_text': _explanations.handle_generate_ai_text, 'cancel_analysis': _analysis_jobs.handle_cancel_analysis, 'create_survey': _surveys.handle_create_survey, 'create_task': _task_inputs.handle_create_task, 'delete_photo': _photos.handle_delete_photo, 'delete_survey': _task_inputs.handle_delete_survey, 'delete_task': _task_inputs.handle_delete_survey, 'edit_ai_text': _explanations.handle_generate_ai_text, 'export_excel': _reports.handle_export_excel, 'generate_ai_text': _explanations.handle_generate_ai_text, 'get_analysis': _analysis_records.handle_get_analysis, 'get_photo_preview': _photos.handle_get_photo_preview, 'get_settings': _settings.handle_get_settings, 'get_survey': _surveys.handle_get_survey, 'get_task': _task_inputs.handle_get_task, 'get_task_result': _analysis_records.handle_get_task_result, 'import_photos': _photos.handle_import_photos, 'list_analysis_history': _analysis_records.handle_list_analysis_history, 'list_export_logs': _reports.handle_list_export_logs, 'list_surveys': _surveys.handle_list_surveys, 'list_tasks': _task_inputs.handle_list_tasks, 'preview_excel': _reports.handle_preview_excel, 'preview_excel_sheets': _reports.handle_preview_excel_sheets, 'recalculate_judgments': _analysis_jobs.handle_recalculate_reba, 'recalculate_reba': _analysis_jobs.handle_recalculate_reba, 'recalculate_tags': _analysis_jobs.handle_recalculate_reba, 'rename_task': _task_inputs.handle_rename_task, 'save_task_input': _task_inputs.handle_save_task_input, 'select_representative': _analysis_records.handle_select_representative, 'set_analysis_scope': _task_inputs.handle_set_analysis_scope, 'set_capture': _task_inputs.handle_rename_task, 'set_investigator_conclusion': _analysis_records.handle_set_investigator_conclusion, 'set_legal_inputs': _task_inputs.handle_rename_task, 'set_manual_values': _task_inputs.handle_rename_task, 'set_survey_review': _surveys.handle_set_survey_review, 'set_task_conditions': _task_inputs.handle_rename_task, 'set_task_profile': _task_inputs.handle_set_task_profile, 'start_analysis': _analysis_jobs.handle_start_analysis, 'update_photo': _photos.handle_update_photo, 'update_settings': _settings.handle_update_settings, 'update_survey': _surveys.handle_update_survey, 'quick_preview': _quick.handle_quick_preview, 'quick_interpret': _quick.handle_quick_interpret, 'intake_contract': _intake.handle_intake_session, 'intake_session': _intake.handle_intake_session, 'intake_turn': _intake.handle_intake_turn}

_BINDINGS={
    'task_input': _task_inputs.task_input,
    'save_task': _task_inputs.save_task,
    'reconcile_capture': _task_inputs.reconcile_capture,
    'validate_task_input_shape': _task_inputs.validate_task_input_shape,
    'settings': _settings.settings,
    'validate_settings': _settings.validate_settings,
    'analysis': _analysis_records.analysis,
    'snapshot': _analysis_records.snapshot,
    'persist_analysis': _analysis_records.persist_analysis,
    'edit_result': _analysis_records.edit_result,
    'pose_inputs': _analysis_records.pose_inputs,
    'new_analysis': _analysis_jobs.new_analysis,
    '_new_analysis': _analysis_jobs._new_analysis,
    'run': _analysis_jobs.run,
    'export_snapshot': _reports.export_snapshot,
    '_export_snapshot': _reports._export_snapshot,
}

class PreparedCall:
    """Prepared work and cleanup if its background thread cannot start."""
    def __init__(self, operation, on_start_error=None):
        self.operation = operation
        self.on_start_error = on_start_error

    def __call__(self):
        return self.operation()

    def start_failed(self, error):
        if self.on_start_error is not None:
            self.on_start_error(error)


def create_service(database):
    """Compose an isolated service for one explicit database or path provider."""
    provider=database if callable(database) else lambda:str(database)
    ctx=Runtime(provider)
    for name,function in _BINDINGS.items(): setattr(ctx,name,partial(function,ctx))
    def call(method,params):
        validate_request(method,params)
        return _HANDLERS[method](ctx,method,params)
    def prepare_call(method, params):
        validate_request(method, params)
        if method in RECALCULATION_METHODS:
            a, modules, cancel, token = _analysis_jobs.prepare_recalculation(ctx, method, params)
            return PreparedCall(
                partial(_analysis_jobs.finish_recalculation, ctx, a, modules, cancel, token),
                partial(_analysis_jobs.fail_recalculation_start, ctx, a, cancel, token),
            )
        if method == 'generate_ai_text':
            prepared = _explanations.prepare_explanation(ctx, params)
            return PreparedCall(partial(_explanations.handle_generate_ai_text, ctx, method, params, prepared=prepared))
        return PreparedCall(partial(call, method, params))
    ctx.dispatch=call
    ctx.prepare_dispatch=prepare_call
    return ctx

_context=create_service(lambda:DB)
store=_context.store
require=_context.require
for _name in _BINDINGS: globals()[_name]=getattr(_context,_name)
dispatch=_context.dispatch
prepare_dispatch=_context.prepare_dispatch
