"""Prepared PDF requests. The original snapshot and DB destination remain fixed."""
from copy import deepcopy
from pathlib import Path
from tempfile import NamedTemporaryFile
import base64
import os
import sqlite3

from backend.db import storage
from backend.report import pdf
from backend.report.form_mapping import map_snapshot


def prepare(ctx, method, params):
    spec=deepcopy(params['spec'])
    with ctx.db_lock:
        database=str(ctx.db_path)
        snap=ctx.export_snapshot(params['survey_id'],spec['analysis_ids'],spec['include_representative'])
        task_by_id={t['task_id']:t for t in snap['tasks']}
        selected=set(spec['task_ids'])
        if selected-set(task_by_id):raise ValueError('선택한 작업은 이 조사에 속하지 않습니다.')
        explicit=set(spec['analysis_ids'])
        if any(a['analysis_id'] in explicit and a['task_id'] not in selected for a in snap['analyses']):
            raise ValueError('선택하지 않은 작업의 분석이 포함되어 있습니다.')
        snap['tasks']=[task_by_id[i] for i in spec['task_ids']]
        snap['analyses']=[a for a in snap['analyses'] if a['task_id'] in selected]
        snap['unanalysed_task_ids']=[i for i in snap['unanalysed_task_ids'] if i in selected]
        # All other tasks, including their photos and notes, are absent from the log.
        snap=deepcopy(snap)
    model=map_snapshot(snap)
    images={}
    if spec['include_representative']:
        for task in model['tasks']:
            if task['photo'] is None:continue
            try:
                raw=Path(task['photo']['file_path']).read_bytes()
                # Decode once in preparation: failures become explicit warnings.
                from PIL import Image
                from io import BytesIO
                with Image.open(BytesIO(raw)) as image:image.verify()
                images[task['task_id']]=raw
            except (OSError,ValueError,KeyError) as error:
                model['warnings'].append(task['name']+': 선택된 대표 사진을 읽지 못했습니다. 다른 사진으로 대체하지 않았습니다.')
    return dict(method=method,spec=spec,snapshot=snap,model=model,images=images,db_path=database)


def finish(prepared):
    snap=prepared['snapshot']
    result=pdf.render(snap,prepared['images'],prepared['model'])
    receipt=dict(report_version='2.0',format='PDF',template_version=result['template_version'],
                 template_sha256=result['template_sha256'],page_count=result['page_count'],
                 task_ids=[t['task_id'] for t in snap['tasks']],
                 analysis_ids=[a['analysis_id'] for a in snap['analyses']],
                 warnings=result['warnings'],**result['state'])
    if prepared['method']=='preview_pdf':
        return dict(receipt,overview=prepared['model']['overview'],
                    data_url='data:application/pdf;base64,'+base64.b64encode(result['data']).decode('ascii'))
    destination=Path(prepared['spec']['destination']).absolute()
    temporary=None
    try:
        with NamedTemporaryFile(dir=destination.parent,prefix='.loco-pdf-',suffix='.pdf',delete=False) as stream:
            temporary=Path(stream.name);stream.write(result['data'])
        os.replace(temporary,destination)
    finally:
        if temporary is not None:temporary.unlink(missing_ok=True)
    try:
        export_id=storage.create_export_log(snap['survey']['survey_id'],str(destination),snap,receipt,
                                           snap['exported_at'],db_path=prepared['db_path'],
                                           expected_survey_created_at=snap['survey'].get('created_at'))
    except LookupError as error:
        raise LookupError(f'PDF 파일은 생성됐지만 대상 조사가 삭제·교체되어 이력을 연결하지 않았습니다: {destination}') from error
    except sqlite3.Error as error:
        raise sqlite3.DatabaseError(f'PDF 파일은 생성됐지만 출력 이력 저장에 실패했습니다: {destination} / {error}') from error
    return dict(receipt,export_id=export_id,file_path=str(destination),created_at=snap['exported_at'])


def handle(ctx,method,params):
    return finish(prepare(ctx,method,params))
