"""Storage facade for the unchanged six JSON tables. Entity implementations are independent modules."""
from .storage_common import open_db, read_snapshot
from .surveys import create_survey, get_survey, list_surveys, update_survey_metadata, set_survey_review, delete_survey
from .tasks import create_task, get_task, list_tasks, update_task_input, delete_task
from .photos import create_photo, get_photo, list_photos, update_photo, delete_photo
from .analyses import create_analysis, get_analysis, list_analyses, update_analysis_result
from .settings import get_settings, update_settings
from .exports import create_export_log, list_export_logs
