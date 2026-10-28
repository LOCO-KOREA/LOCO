"""Actual service/SQLite/Excel, with synthetic landmarks ONLY at provider.infer.

The synthetic success is transport/geometry proof, not model accuracy. An actual
MediaPipe photo path is separately evaluated without any patched inference.
"""
import argparse
import copy
import json
import math
import os
from pathlib import Path
import sqlite3
import sys
import threading
import xml.etree.ElementTree as ET
import zipfile
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from PIL import Image
from backend.pose_contract import MEDIAPIPE_NAMES
from backend.service.application import create_service
from backend.intake import contract, planner


def synthetic():
    points={name:dict(point_no=i,name=name,x_px=508,y_px=150,confidence=.3,visibility=.3,presence=.3,z_normalized=0) for i,name in enumerate(MEDIAPIPE_NAMES)}
    known=dict(nose=(450,130),left_ear=(490,130),left_shoulder=(500,180),left_elbow=(500,300),left_wrist=(300,300),
        left_hip=(500,500),left_knee=(500,640),left_ankle=(500,760),right_shoulder=(508,180),right_hip=(508,500))
    for joint,length,spread in [('index',80,2),('pinky',75.2,-2),('thumb',48,0)]:
        a=math.radians(30);known['left_'+joint]=(300-length*math.cos(a)+spread*math.sin(a),300+length*math.sin(a)+spread*math.cos(a))
    for name,(x,y) in known.items():points[name].update(x_px=x,y_px=y,confidence=.99,visibility=.99,presence=.99)
    rows=list(points.values())
    return dict(points=rows,world_points=[dict(point_no=p['point_no'],name=p['name'],x_m=0,y_m=0,z_m=0,confidence=p['confidence']) for p in rows],quality=dict(detected=True,detected_persons=1))


def make_service(directory,photo,view):
    directory.mkdir(parents=True,exist_ok=True);ctx=create_service(str(directory/'loco.db'))
    assert not ctx.settings()['gpt_enabled']
    survey=ctx.dispatch('create_survey',dict(draft=dict(survey_type='REGULAR',survey_date='2026-10-23',title='손목 저장 연결 검증')))
    task=ctx.dispatch('create_task',dict(survey_id=survey['survey_id'],draft=dict(task_name='손목 굽힘 연결 검증')))
    added=ctx.dispatch('import_photos',dict(task_id=task['task_id'],file_paths=[str(photo)]))['added'][0]
    state=ctx.dispatch('intake_session',dict(task_id=task['task_id'],views={view:added['photo_id']}))
    state=ctx.dispatch('intake_turn',dict(task_id=task['task_id'],answers=[dict(target='context',value='YES')],plan=False))
    return ctx,survey,task,added,state


def stored(ctx,task_id):
    with sqlite3.connect(f'file:{Path(ctx.db_path).as_posix()}?mode=ro',uri=True) as db:
        return db.execute('SELECT input_revision,input_json FROM TASK WHERE task_id=?',(task_id,)).fetchone()


def assert_read_only_reopen(ctx,task_id):
    before=stored(ctx,task_id)
    for _ in range(3):ctx.dispatch('intake_session',dict(task_id=task_id));assert stored(ctx,task_id)==before,'query changed revision or input JSON bytes'
    return dict(revision=before[0],json_bytes=len(before[1].encode('utf-8')),reads=3,unchanged=True)


def cells(filename):
    ns={'s':'http://schemas.openxmlformats.org/spreadsheetml/2006/main'};result=[]
    with zipfile.ZipFile(filename) as archive:
        shared=[]
        if 'xl/sharedStrings.xml' in archive.namelist():shared=[''.join(row.itertext()) for row in ET.fromstring(archive.read('xl/sharedStrings.xml'))]
        targets={row.attrib['Id']:row.attrib['Target'].lstrip('/') for row in ET.fromstring(archive.read('xl/_rels/workbook.xml.rels'))}
        for sheet in ET.fromstring(archive.read('xl/workbook.xml')).find('s:sheets',ns):
            target=targets[sheet.attrib['{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id']];target=target if target.startswith('xl/') else 'xl/'+target
            for row in ET.fromstring(archive.read(target)).findall('.//s:row',ns):
                values=[]
                for cell in row.findall('s:c',ns):
                    kind=cell.attrib.get('t');inline=cell.find('s:is',ns)
                    value=(''.join(inline.itertext()) if inline is not None else '') if kind=='inlineStr' else cell.findtext('s:v',default='',namespaces=ns)
                    if kind=='s':value=shared[int(value)]
                    values.append(dict(cell=cell.attrib['r'],value=value))
                if any('손목' in item['value'] for item in values):result.append(dict(sheet=sheet.attrib['name'],cells=values))
    return result


def run(directory,real_photo):
    directory.mkdir(parents=True,exist_ok=True)
    for name in list(os.environ):
        if 'OPENAI' in name and ('KEY' in name or name=='OPENAI_BASE_URL'):os.environ.pop(name)
    image=directory/'synthetic-input.png';Image.new('RGB',(800,800),'white').save(image)
    receipt=dict(kind='synthetic provider landmarks; actual service APIs/SQLite/MediaPipe-contract/analysis/Excel; no AI calls',checks=[])
    with patch('backend.pose.providers.mediapipe.infer',side_effect=lambda *args:copy.deepcopy(synthetic())):
        ctx,survey,task,photo,state=make_service(directory/'synthetic',image,'LEFT')
        target='manual.LEFT.wrist_base';saved=state['task']['conditions'][contract.SESSION_KEY]['facts'];wrist=saved[contract.key(target)]
        assert wrist['value']==2 and wrist['state']=='KNOWN' and wrist['source']=='POSE',wrist
        manual=next(row for row in state['task']['manual'] if row['scope']=='LEFT' and row['field']=='wrist_base')
        assert manual['source']=='AUTO_ACCEPTED' and manual['value']==2 and manual['photo_id']==photo['photo_id']
        pending=planner.assess(state['task'],saved,dict(LEFT=photo['photo_id']))['candidates']
        assert target not in {row['target'] for row in pending}
        assert 'manual.LEFT.wrist_deviated_or_twisted' in {row['target'] for row in pending}
        assert not any(row['target'].endswith('wrist_deviated_or_twisted') for row in saved.values())
        receipt['synthetic']=dict(fact=wrist,manual=manual,reopen=assert_read_only_reopen(ctx,task['task_id']))
        ctx.dispatch('set_analysis_scope',dict(task_id=task['task_id'],scope=dict(pose=True,tags=False,reba=True,judgment=True)))
        started=ctx.dispatch('start_analysis',dict(task_id=task['task_id']))
        while True:
            analysis=ctx.dispatch('get_analysis',dict(analysis_id=started['analysis_id']))
            if analysis['status']!='RUNNING':break
            threading.Event().wait(.02)
        assert analysis['status']=='FINISHED',analysis['status']
        assert any(row['angle_code']=='WRIST_FLEX_2D' and row['value_deg'] is not None for row in analysis['pose']['slots'][0]['angles'])
        original=copy.deepcopy(ctx.store('get_analysis',analysis['analysis_id']))
        workbook=directory/'synthetic'/'wrist.xlsx'
        ctx.dispatch('export_excel',dict(survey_id=survey['survey_id'],spec=dict(destination=str(workbook),analysis_ids=[analysis['analysis_id']],include_representative=False,comparisons=[])))
        matches=cells(workbook);matched=[row for row in matches if row['sheet']=='입력한 값' and any('15° 넘게'==cell['value'] for cell in row['cells'])]
        assert matched,matches
        with sqlite3.connect(str(directory/'synthetic'/'loco.db')) as db:
            assert len(db.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall())==6
            snap=json.loads(db.execute('SELECT snapshot_json FROM EXPORT_LOG ORDER BY export_id DESC LIMIT 1').fetchone()[0])
            exported=next(row for row in snap['analyses'][0]['snapshot']['manual'] if row['scope']=='LEFT' and row['field']=='wrist_base')
            assert exported==manual
        ctx.dispatch('intake_turn',dict(task_id=task['task_id'],answers=[dict(target=target,value=1)],plan=False))
        state=ctx.dispatch('intake_session',dict(task_id=task['task_id']))
        assert state['task']['conditions'][contract.SESSION_KEY]['facts'][contract.key(target)]['source']=='USER'
        assert next(row for row in state['task']['manual'] if row['scope']=='LEFT' and row['field']=='wrist_base')['value']==1
        assert ctx.store('get_analysis',analysis['analysis_id'])==original
        receipt['synthetic'].update(workbook=str(workbook),analysis_id=analysis['analysis_id'],excel_rows=matched,other_unknowns_remain_incomplete=analysis['reba']['status']=='INCOMPLETE')
        receipt['checks'].append('synthetic provider only -> wrist2 -> existing AUTO_ACCEPTED DB field -> no flexion re-question -> real pose/REBA analysis -> actual Excel cells; direct edit and immutable snapshot preserved')
    occluded=synthetic();point=next(point for point in occluded['points'] if point['name']=='left_index');point.update(confidence=.2,visibility=.2)
    with patch('backend.pose.providers.mediapipe.infer',side_effect=lambda *args:copy.deepcopy(occluded)):
        ctx,survey,task,photo,state=make_service(directory/'synthetic-low-quality',image,'LEFT')
        item=next(row for row in state['facts'] if row['target']=='manual.LEFT.wrist_base')
        assert item['state']=='UNKNOWN' and item['measurement_diagnostic']=='WRIST_POINTS_LOW_CONFIDENCE'
        assert not any(row['field']=='wrist_base' for row in state['task']['manual'])
        pending=planner.assess(state['task'],state['task']['conditions'][contract.SESSION_KEY]['facts'],dict(LEFT=photo['photo_id']))['candidates']
        assert 'manual.LEFT.wrist_base' in {row['target'] for row in pending}
        receipt['synthetic_low_quality']=dict(fact=item,reopen=assert_read_only_reopen(ctx,task['task_id']))
        state=ctx.dispatch('intake_turn',dict(task_id=task['task_id'],answers=[dict(target='manual.LEFT.wrist_base',value=None)],plan=False))
        ctx.dispatch('intake_session',dict(task_id=task['task_id']))
        assert state['task']['conditions'][contract.SESSION_KEY]['facts'][contract.key('manual.LEFT.wrist_base')]['source']=='USER'
        receipt['checks'].append('synthetic occluded hand stays UNKNOWN/pending without manual zero; 3 API queries leave revision and exact input JSON unchanged; direct unknown remains USER')
    ctx,survey,task,photo,state=make_service(directory/'real-model',real_photo,'RIGHT')
    issues=state['preview']['measurement_issues'];assert issues,'actual model must expose why this fixture is not measurable'
    actual_target='manual.'+issues[0]['scope']+'.wrist_base'
    item=next(row for row in state['facts'] if row['target']==actual_target)
    assert item['value'] is None and item['state']=='UNKNOWN' and item['source']=='POSE',item
    pending=planner.assess(state['task'],state['task']['conditions'][contract.SESSION_KEY]['facts'],dict(RIGHT=photo['photo_id']))['candidates']
    question=next(row for row in pending if row['target']==actual_target);assert question['reason']!='결과 계산에 필요한 정보가 아직 없어요.'
    receipt['real_model']=dict(path=str(real_photo),issues=issues,fact=item,question=question,reopen=assert_read_only_reopen(ctx,task['task_id']),measurable_success=False)
    receipt['checks'].append('unpatched actual MediaPipe fixture abstains with explicit ordinary-language reason; 3 queries preserve DB revision and exact input_json bytes')
    (directory/'receipt.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(dict(checks=receipt['checks'],synthetic_excel=receipt['synthetic']['excel_rows'],real_model_reason=question['reason']),ensure_ascii=False))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--directory',type=Path,required=True);parser.add_argument('--real-photo',type=Path,default=ROOT/'.local/fixtures/tensorflow-movenet-example.jpeg');args=parser.parse_args()
    run(args.directory.resolve(),args.real_photo.resolve())
