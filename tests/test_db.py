"""Persistence tests for the canonical six-table JSON DTO store."""
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from backend.db import open_db, storage
from backend.engine.task_defaults import task_input


class StorageTests(unittest.TestCase):
    def test_schema_contains_exactly_the_six_documented_tables(self):
        connection = open_db(':memory:')
        try:
            tables = {row[0] for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")}
        finally:
            connection.close()
        self.assertEqual(tables, {'SURVEY', 'TASK', 'PHOTO', 'ANALYSIS', 'APP_SETTINGS', 'EXPORT_LOG'})

    def test_file_database_reopens_and_task_revision_increments_once(self):
        with tempfile.TemporaryDirectory() as root:
            path = str(Path(root) / 'loco.db')
            survey_id = storage.create_survey({'title': '조사'}, {'reviewed': False}, 'now', 'now', db_path=path)
            task_id = storage.create_task(survey_id, task_input({'task_name': '상자 들기'}), 'now', 'now', db_path=path)
            before = storage.get_task(task_id, db_path=path)
            changed = task_input({'task_name': '조립 작업'})
            revision = storage.update_task_input(task_id, changed, 'later', db_path=path)
            after = storage.get_task(task_id, db_path=path)
            self.assertEqual(revision, before['input_revision'] + 1)
            self.assertEqual(after['input_revision'], revision)
            self.assertEqual(after['task_name'], '조립 작업')
            connection = open_db(path)
            try:
                self.assertEqual(connection.execute('SELECT COUNT(*) FROM TASK').fetchone()[0], 1)
            finally:
                connection.close()

    def test_deleting_photo_clears_v2_reference_observation_and_manual_input(self):
        with tempfile.TemporaryDirectory() as root:
            path = str(Path(root) / 'loco.db')
            survey_id = storage.create_survey({'title': '조사'}, {'reviewed': False}, 'now', 'now', db_path=path)
            data = task_input({'task_name': '작업'})
            task_id = storage.create_task(survey_id, data, 'now', 'now', db_path=path)
            photo_id = storage.create_photo(task_id, {'file_path': 'photo.jpg', 'file_name': 'photo.jpg'}, db_path=path)
            data['capture']['slots'] = [{'slot_no': 5, 'photo_id': photo_id, 'analysis_target': True,
                'observation': {'load_state': 'MEASURED', 'measured_load_kg': 12, 'single_person': 'YES',
                    'full_frame': 'YES', 'normal_work': 'YES'}}]
            data['manual'] = [{'slot_no': 5, 'photo_id': photo_id, 'scope': 'COMMON', 'field': 'trunk_base', 'value': 2}]
            storage.update_task_input(task_id, data, 'later', db_path=path)
            before_revision = storage.get_task(task_id, db_path=path)['input_revision']
            storage.delete_photo(photo_id, db_path=path)
            after = storage.get_task(task_id, db_path=path)
            slot = after['capture']['slots'][0]
            self.assertEqual(after['input_revision'], before_revision + 1)
            self.assertIsNone(slot['photo_id'])
            self.assertFalse(slot['analysis_target'])
            self.assertEqual(slot['observation']['load_state'], 'UNKNOWN')
            self.assertEqual(after['manual'], [])
            self.assertIsNone(storage.get_photo(photo_id, db_path=path))


if __name__ == '__main__':
    unittest.main()
