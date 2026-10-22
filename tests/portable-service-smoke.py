"""N05 development-PC smoke check. Native Electron GUI is not automated here.

Only the final frozen service is launched, with a Windows-only PATH and a new
temporary DB. The image is synthetic white pixels, not a real person or task.
"""
import hashlib
import json
import math
import os
from pathlib import Path
import queue
import subprocess
import tempfile
import threading
import time

from PIL import Image
from openpyxl import load_workbook

REPO = Path(__file__).resolve().parents[1]
PACKAGE = Path(os.environ.get('LOCO_VERIFY_PACKAGE') or (REPO / '.local/latest-package.txt').read_text(encoding='utf-8').strip())
EXE = PACKAGE / 'resources/backend/loco-service/loco-service.exe'
MODEL = PACKAGE / 'resources/models/movenet_lightning.tflite'
OUTPUT = Path(tempfile.mkdtemp(prefix='loco-n05-'))
DB = OUTPUT / '한글 공백 자료' / '배포 검증.db'
CHECKS = []


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def check(name, **details):
    CHECKS.append(dict(name=name, **details))
    print('PASS ' + name, flush=True)


class Worker:
    def __init__(self, model=MODEL, label='normal'):
        env = dict(os.environ)
        for key in ('PYTHONHOME', 'PYTHONPATH', 'LOCO_PYTHON', 'OPENAI_API_KEY', 'OPENAI_BASE_URL'):
            env.pop(key, None)
        windows = env.get('SystemRoot', r'C:\Windows')
        env.update(PATH=windows + r'\System32;' + windows,
                   LOCO_DB_PATH=str(DB), LOCO_MOVENET_MODEL=str(model),
                   PYTHONIOENCODING='utf-8', PYTHONDONTWRITEBYTECODE='1')
        self.stderr = (OUTPUT / (label + '-stderr.log')).open('w', encoding='utf-8')
        self.proc = subprocess.Popen([str(EXE)], cwd=OUTPUT, env=env,
                                     stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                     stderr=self.stderr, text=True, encoding='utf-8',
                                     creationflags=subprocess.CREATE_NO_WINDOW)
        self.responses = queue.Queue()
        self.sequence = 0
        def read():
            for line in self.proc.stdout:
                self.responses.put(json.loads(line))
        threading.Thread(target=read, daemon=True).start()

    def call(self, method, _expect_error=False, **params):
        self.sequence += 1
        request = dict(request_id=self.sequence, method=method, params=params)
        self.proc.stdin.write(json.dumps(request, ensure_ascii=False) + '\n')
        self.proc.stdin.flush()
        response = self.responses.get(timeout=30)
        assert response['request_id'] == self.sequence, response
        result = response['result']
        if _expect_error:
            assert result['ok'] is False, result
            return result['error']
        assert result['ok'], result
        return result['value']

    def finish(self, analysis_id):
        until = time.monotonic() + 45
        while time.monotonic() < until:
            value = self.call('get_analysis', analysis_id=analysis_id)
            if value['status'] != 'RUNNING':
                return value
            time.sleep(0.1)
        raise AssertionError('Analysis did not finish')

    def close(self):
        self.proc.stdin.close()
        try:
            code = self.proc.wait(timeout=10)
            assert code == 0, code
        finally:
            if self.proc.poll() is None:
                self.proc.kill()
            self.stderr.close()


def export(worker, survey_id, ids, name):
    target = OUTPUT / (name + '.xlsx')
    receipt = worker.call('export_excel', survey_id=survey_id,
                          spec=dict(analysis_ids=ids, include_representative=False,
                                    comparisons=[], destination=str(target)))
    assert Path(receipt['file_path']) == target and target.is_file()
    book = load_workbook(target, read_only=True, data_only=False)
    count = len(book.sheetnames)
    book.close()
    return count


def main():
    manifest = json.loads((PACKAGE / 'build-manifest.json').read_text(encoding='utf-8'))
    # A committed-source build (false) is the delivery candidate; a build with local changes (true) is a development check.
    assert isinstance(manifest['source_has_local_changes'], bool)
    print('build source:', manifest['source_commit'][:8], 'local changes:', manifest['source_has_local_changes'], flush=True)
    assert digest(MODEL) == manifest['model_sha256'] == '0fac2226112d0371903ca86e3853cec24ef603a0b2f96f589b180f0ebdd135ab'
    frontend_count = 0
    for relative, expected in manifest['source_sha256'].items():
        assert digest(REPO / relative) == expected, relative
        if relative.startswith('frontend/') or relative == 'docs/ui/loco-guide.js':
            assert digest(PACKAGE / 'resources/app' / relative) == expected, relative
            frontend_count += 1
    assert not (PACKAGE / 'resources/app/frontend/.local').exists()
    assert not (PACKAGE / 'resources/app/frontend/node_modules').exists()
    assert not list((PACKAGE / 'resources/app').rglob('*.db'))
    check('package code/model hashes match current source; no app DB or frontend node_modules copied', frontend_files=frontend_count)
    image = OUTPUT / 'synthetic-white.png'
    Image.new('RGB', (640, 480), 'white').save(image)
    worker = Worker()
    try:
        assert worker.call('list_surveys') == []
        survey = worker.call('create_survey', draft=dict(title='포터블 합성 검증', survey_type='REGULAR'))
        task = worker.call('create_task', survey_id=survey['survey_id'], draft=dict(task_name='합성 입력'))
        task_id = task['task_id']
        direct = worker.call('recalculate_judgments', task_id=task_id)
        assert len(direct['judgment']['judgments']) == 11
        assert direct['module_states']['pose'] == 'NOT_REQUESTED'
        check('frozen service creates Korean-path DB and calculates direct-input draft without system Python/Node')
        photo = worker.call('import_photos', task_id=task_id, file_paths=[str(image)])['added'][0]
        slot = dict(slot_no=1, photo_id=photo['photo_id'], analysis_target=True, label='합성 흰 이미지',
                    camera_side='LEFT', forward_direction='SCREEN_RIGHT', side_view_verified='YES',
                    observation=dict(load_state='UNKNOWN', measured_load_kg=None, single_person='YES',
                                     full_frame='YES', normal_work='YES', evidence=dict(source=None, text=None, observed_at=None)))
        worker.call('set_capture', task_id=task_id, capture=dict(protocol='GENERAL_STILLS_V1', slots=[slot]))
        worker.call('set_analysis_scope', task_id=task_id, scope=dict(judgment=True, pose=True, tags=True, reba=True))
        handle = worker.call('start_analysis', task_id=task_id)
        analysis = worker.finish(handle['analysis_id'])
        pose = analysis['pose']['slots'][0]
        assert pose['status'] != 'ERROR', pose['diagnostics']
        assert len(pose['points']) == 17, pose
        assert all(math.isfinite(p[key]) for p in pose['points'] for key in ('x_px', 'y_px', 'confidence'))
        assert 'MODEL_ERROR' not in [d['code'] for d in pose['diagnostics']]
        check('packaged official model executes real CPU inference and returns 17 finite points',
              synthetic_image=True, pose_status=pose['status'], module_states=analysis['module_states'])
        disabled = worker.call('generate_ai_text', analysis_id=analysis['analysis_id'])['text']
        assert disabled['result'] == 'DISABLED'
        blocked = worker.call('apply_ai_text', _expect_error=True, analysis_id=analysis['analysis_id'], text_id=disabled['text_id'], use_edited=False)
        assert blocked['code'] == 'NOT_FOUND'
        settings = worker.call('get_settings')
        settings.update(gpt_enabled=True, gpt_model='local-no-key-verification')
        settings.pop('gpt_key_present', None)
        worker.call('update_settings', settings=settings)
        ai = worker.call('generate_ai_text', analysis_id=analysis['analysis_id'])['text']
        assert ai['result'] == 'FALLBACK' and ai['fallback_reason'] == 'NO_API_KEY'
        worker.call('edit_ai_text', analysis_id=analysis['analysis_id'], text_id=ai['text_id'], text='합성 자료 · 현장 확인 필요')
        worker.call('apply_ai_text', analysis_id=analysis['analysis_id'], text_id=ai['text_id'], use_edited=True)
        check('disabled explanation cannot be applied; no-key local fallback can be edited/applied without external GPT call')
        assert export(worker, survey['survey_id'], [analysis['analysis_id']], 'regular-7-sheets') == 7
        occasional = worker.call('create_survey', draft=dict(title='수시 합성 검증', survey_type='OCCASIONAL', occasional_cause='DISEASE_CASE'))
        assert export(worker, occasional['survey_id'], [], 'occasional-6-sheets') == 6
        check('frozen service exports readable official-form workbooks (7 sheets with the applied explanation, 6 without tasks)')
        saved = worker.call('get_analysis', analysis_id=analysis['analysis_id'])
    finally:
        worker.close()
    reopened = Worker(label='reopened')
    try:
        assert reopened.call('get_task', task_id=task_id)['task']['task_id'] == task_id
        restored = reopened.call('get_analysis', analysis_id=analysis['analysis_id'])
        assert restored['snapshot'] == saved['snapshot']
        assert restored['pose']['slots'][0]['points'] == saved['pose']['slots'][0]['points']
        assert restored['ai'] == saved['ai']
        check('frozen service restart preserves task, immutable snapshot, 17 points and applied explanation')
    finally:
        reopened.close()
    broken_model = OUTPUT / 'incorrect-model.tflite'
    broken_model.write_bytes(b'not the official model')
    rejected = Worker(model=broken_model, label='incorrect-model')
    try:
        # A new worker is required so a prior interpreter cannot mask the failure.
        handle = rejected.call('start_analysis', task_id=task_id)
        invalid = rejected.finish(handle['analysis_id'])['pose']['slots'][0]
        assert invalid['status'] == 'ERROR' and invalid['points'] == []
        assert 'MODEL_ERROR' in [d['code'] for d in invalid['diagnostics']]
        check('separate frozen worker rejects an incorrect model with MODEL_ERROR and no fabricated points')
    finally:
        rejected.close()
    report = dict(kind='development-PC frozen-service smoke check; GUI, external GPT and separate PC not verified',
                  package_name=PACKAGE.name, source_commit=manifest['source_commit'], source_has_local_changes=True,
                  app_exe_sha256=digest(PACKAGE / 'LOCO.exe'), service_exe_sha256=digest(EXE),
                  model_sha256=digest(MODEL), checks=CHECKS)
    (OUTPUT / 'receipt.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print('Artifacts: ' + str(OUTPUT), flush=True)
    print('PASS ' + str(len(CHECKS)) + ' portable-service checks; clean separate Windows PC and native GUI remain unverified', flush=True)


if __name__ == '__main__':
    main()
