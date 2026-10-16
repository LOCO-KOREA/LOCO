"""Module boundaries and independent application state after the refactor."""
import ast
import tempfile
import unittest
from pathlib import Path
from ergo.service.application import create_service

ROOT=Path(__file__).resolve().parents[1]


class ModuleBoundaries(unittest.TestCase):
    def test_two_application_instances_keep_database_and_worker_state_separate(self):
        with tempfile.TemporaryDirectory() as folder:
            first=create_service(Path(folder)/'first.db'); second=create_service(Path(folder)/'second.db')
            first.dispatch('create_survey',{'draft':{'title':'first','survey_type':'INITIAL'}})
            second.dispatch('create_survey',{'draft':{'title':'second','survey_type':'REGULAR'}})
            self.assertEqual(first.dispatch('list_surveys',{})[0]['title'],'first')
            self.assertEqual(second.dispatch('list_surveys',{})[0]['title'],'second')
            self.assertIsNot(first.cancels,second.cancels)
            self.assertIsNot(first.db_lock,second.db_lock)

    def test_domain_modules_do_not_import_the_composition_root_or_electron(self):
        for path in (ROOT/'ergo/service').glob('*.py'):
            if path.name in ('application.py','json_lines.py'):continue
            for node in ast.walk(ast.parse(path.read_text(encoding='utf-8'))):
                if isinstance(node,ast.ImportFrom):
                    self.assertNotEqual(node.module,'ergo.service.application',str(path))
                    self.assertNotIn('application',[x.name for x in node.names],str(path))
            self.assertNotIn('frontend',path.read_text(encoding='utf-8'))

    def test_storage_modules_have_no_engine_or_ai_dependencies(self):
        for path in (ROOT/'ergo/db').glob('*.py'):
            for node in ast.walk(ast.parse(path.read_text(encoding='utf-8'))):
                if isinstance(node,ast.ImportFrom):
                    self.assertFalse(any(word in (node.module or '') for word in ('engine','gpt','service')),str(path))


if __name__=='__main__':unittest.main()
