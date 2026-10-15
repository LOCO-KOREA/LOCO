"""Initial survey API adapter for A's Electron integration.

Uses the shared storage without changing ergo/. Replace via LOCO_SERVICE_ENTRY
when the team's Application Service is ready. No analysis methods are simulated.
"""
import json
import os
import sqlite3
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from ergo.db import storage
from task_inputs import dispatch_task
from photo_inputs import PhotoError, dispatch_photo

DB_PATH = os.environ.get('LOCO_DB_PATH') or str(Path(__file__).resolve().parents[1] / '.local' / 'loco_frontend.db')

def now():
    return datetime.now(timezone.utc).isoformat()

def get_survey(survey_id):
    survey = storage.get_survey(survey_id, db_path=DB_PATH)
    if survey is None:
        raise LookupError('조사를 찾을 수 없습니다.')
    return survey

def dispatch(method, params):
    if method in {'import_photos', 'get_photo_preview', 'update_photo', 'delete_photo', 'set_capture'}:
        return dispatch_photo(method, params, DB_PATH)
    if method in {'create_task', 'get_task', 'delete_task', 'rename_task', 'set_task_conditions', 'set_legal_inputs'}:
        return dispatch_task(method, params, DB_PATH)
    if method == 'list_surveys':
        summaries = []
        for survey in reversed(storage.list_surveys(db_path=DB_PATH)):
            tasks = storage.list_tasks(survey['survey_id'], db_path=DB_PATH)
            review = survey.get('review') or {}
            # Current review requires an existing current analysis for every task.
            current = bool(tasks) and bool(review.get('reviewed')) and review.get('reviewed_metadata_revision') == survey['metadata_revision']
            reviewed_ids = review.get('reviewed_analysis_ids') or []
            for task in tasks:
                analysis = storage.get_analysis(task['latest_analysis_id'], db_path=DB_PATH) if task.get('latest_analysis_id') else None
                current = current and bool(analysis) and analysis['analysis_id'] in reviewed_ids and analysis['input_revision'] == task['input_revision']
            summaries.append(dict(survey_id=survey['survey_id'], title=survey.get('title', ''), survey_date=survey.get('survey_date', ''), task_count=len(tasks), reviewed=bool(review.get('reviewed')), review_current=bool(current)))
        return summaries
    if method == 'get_survey':
        return get_survey(params['survey_id'])
    if method == 'create_survey':
        timestamp = now()
        review = dict(reviewed=False, reviewed_analysis_ids=[], reviewed_metadata_revision=None, reviewer=None, reviewed_at=None, note=None)
        survey_id = storage.create_survey(params['draft'], review, timestamp, timestamp, db_path=DB_PATH)
        return get_survey(survey_id)
    if method == 'update_survey':
        get_survey(params['survey_id'])
        storage.update_survey_metadata(params['survey_id'], params['draft'], now(), db_path=DB_PATH)
        return get_survey(params['survey_id'])
    if method == 'delete_survey':
        get_survey(params['survey_id'])
        storage.delete_survey(params['survey_id'], db_path=DB_PATH)
        return dict(message='조사를 삭제했습니다.')
    if method == 'list_tasks':
        get_survey(params['survey_id'])
        return storage.list_tasks(params['survey_id'], db_path=DB_PATH)
    raise LookupError('아직 연결하지 않은 서비스 메서드입니다: ' + method)

for line in sys.stdin:
    request_id = None
    try:
        request = json.loads(line)
        request_id = request['request_id']
        value = dispatch(request['method'], request.get('params', {}))
        result = dict(ok=True, value=value)
    except PhotoError as error:
        result = dict(ok=False, error=dict(code='FILE_ERROR', message=str(error)))
    except LookupError as error:
        result = dict(ok=False, error=dict(code='NOT_FOUND', message=str(error)))
    except (sqlite3.Error, OSError) as error:
        result = dict(ok=False, error=dict(code='DB_ERROR', message=str(error)))
    except Exception:
        traceback.print_exc(file=sys.stderr)
        result = dict(ok=False, error=dict(code='DB_ERROR', message='요청 처리 중 오류가 발생했습니다. Python 로그를 확인하세요.'))
    print(json.dumps(dict(request_id=request_id, result=result), ensure_ascii=False), flush=True)
