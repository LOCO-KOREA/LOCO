"""Shared Application Service for API v1.5 / calculation DTO v1.3.

Storage is supplied by ergo.db; this module does not import the sample app.
"""
import base64
import copy
from io import BytesIO
import json
import os
from pathlib import Path
import sqlite3
import sys
import threading
import traceback

from ergo.db import storage
from ergo.engine.task_defaults import now,evidence,observation,capture,legal_inputs,default_settings,exclusions,diagnostic,PREPROCESS_VERSION
from ergo.engine.reba_scoring import calculate_reba
from ergo.engine.images import read_image
from ergo.engine.pose_tags import calculate_tags
from ergo.engine import burden_rules as burden
from ergo.engine import movenet as pose
from ergo.report import workbook as report
from ergo.db.connection import default_db_path

# The frontend launcher supplies its development DB with LOCO_DB_PATH.
# Direct service execution defaults to the canonical application DB location.
DB=os.environ.get('LOCO_DB_PATH') or str(default_db_path())
_db_lock=threading.RLock(); _cancels={}; _analysis_lock=threading.Lock()

def store(name,*args,**kwargs):
    with _db_lock: return getattr(storage,name)(*args,db_path=DB,**kwargs)

def require(name,identity):
    result=store('get_'+name,identity)
    if result is None: raise LookupError(f'{name} {identity}를 찾을 수 없습니다')
    return result

def settings():
    value=store('get_settings')
    if value is None: value=default_settings(); store('update_settings',value)
    if value['analysis']['pose_model']['preprocess_version']!=PREPROCESS_VERSION:
        # Record the actual preprocessing implementation; preserve historical snapshots.
        value['analysis']['pose_model']['preprocess_version']=PREPROCESS_VERSION
        store('update_settings',value)
        for survey in store('list_surveys'):
            for task in store('list_tasks',survey['survey_id']):
                task['manual']=[m for m in task['manual'] if m['source']!='AUTO_ACCEPTED']
                store('update_task_input',task['task_id'],task_input(task),now())
    return dict(value,gpt_key_present=bool(os.environ.get('OPENAI_API_KEY')))

def task_input(task):
    return {key:copy.deepcopy(task[key]) for key in ['task_kind','task_name','worker_count','conditions','legal','capture','manual']}

def save_task(task, *, force=False):
    current=require('task',task['task_id'])
    if force or task_input(current)!=task_input(task):
        store('update_task_input',task['task_id'],task_input(task),now())
    return require('task',task['task_id'])

def analysis(identity):
    result=require('analysis',identity); task=require('task',result['task_id']); result['currentness']=report.currentness(task,result)
    return result

def snapshot(task):
    return dict(schema_version='1.3',task_id=task['task_id'],input_revision=task['input_revision'],task_name=task['task_name'],conditions=copy.deepcopy(task['conditions']),legal=copy.deepcopy(task['legal']),capture=copy.deepcopy(task['capture']),manual=copy.deepcopy(task['manual']),photos=store('list_photos',task['task_id']),settings=settings()['analysis'])

RESULT_KEYS=['pose','slot_tags','tags','reba','judgment','ai','notes']
def persist_analysis(a):
    store('update_analysis',a['analysis_id'],a['status'],{key:a[key] for key in RESULT_KEYS},a['finished_at'])

def pose_inputs(snap):
    """Only dependencies of inference; load observations do not change coordinates."""
    cap=snap['capture']; assigned={s['photo_id'] for s in cap['slots'] if s['photo_id'] is not None}
    return dict(camera_side=cap['camera_side'],forward_direction=cap['forward_direction'],
        slots=[(s['slot_no'],s['photo_id']) for s in cap['slots']],
        photos=sorted((p['photo_id'],p['file_path'],p.get('width_px'),p.get('height_px')) for p in snap['photos'] if p['photo_id'] in assigned),
        context={k:snap['conditions'].get(k) for k in ['worker_code','method_description','shelf_height_cm']},
        model=snap['settings']['pose_model'])

def new_analysis(task,modules):
    settings()
    task=require('task',task['task_id'])
    snap=snapshot(task); old=store('get_analysis',task['latest_analysis_id']) if task['latest_analysis_id'] else None
    result=dict(pose=None,slot_tags=[],tags=[],reba=None,judgment=None,ai=[],notes=[])
    if old and modules!=['pose','tags','reba','judgment']:
        previous=old['snapshot']
        def same(keys): return all(previous.get(k)==snap.get(k) for k in keys)
        pose_same=pose_inputs(previous)==pose_inputs(snap)
        pose_source=old if pose_same and old['pose'] is not None else None
        if pose_source is None:
            for candidate in reversed(store('list_analyses',task['task_id'])):
                if candidate['pose'] is not None and candidate['status']=='FINISHED' and pose_inputs(candidate['snapshot'])==pose_inputs(snap):
                    pose_source=candidate; break
        if pose_source is not None:
            result['pose']=copy.deepcopy(pose_source['pose'])
            tag_fields={'neck_twisted','trunk_twisted','hand_above_head','elbow_above_shoulder','elbow_behind_trunk','squat','kneel'}
            def tag_manual(data):
                return sorted((m['slot_no'],m['photo_id'],m['scope'],m['field'],str(m['value'])) for m in data['manual'] if m['scope']=='COMMON' and m['field'] in tag_fields)
            if tag_manual(pose_source['snapshot'])==tag_manual(snap) and pose_source['snapshot']['settings']['posture_profile']==snap['settings']['posture_profile']:
                result['slot_tags']=copy.deepcopy(pose_source['slot_tags']); result['tags']=copy.deepcopy(pose_source['tags'])
        if pose_same and same(['manual','capture']) and previous['conditions'].get('box_mass_kg')==snap['conditions'].get('box_mass_kg') and previous['settings']['reba_rule']==snap['settings']['reba_rule']: result['reba']=old['reba']
        if same(['conditions','legal']) and previous['settings']['burden_rule']==snap['settings']['burden_rule']:
            result['judgment']=copy.deepcopy(old['judgment'])
            if result['judgment']:
                for j in result['judgment']['judgments']:
                    j['investigator']=dict(criterion_no=j['criterion_no'],status=None,reason=None,evidence=evidence(),reviewer=None,reviewed_at=None); j['effective_status']=j['computed_status']
        for module,key in [('pose','pose'),('reba','reba'),('judgment','judgment')]:
            if module not in modules and result[key] is None: result['notes'].append(diagnostic('RECALCULATE_REQUIRED',module+' 결과가 없거나 관련 입력이 달라 재계산이 필요합니다'))
    if 'pose' in modules:
        result['pose']=dict(status='RUNNING',valid_count=0,total_slot_count=15,terminal_error=None,slots=[dict(slot_no=s['slot_no'],photo_id=s['photo_id'],status='PENDING',diagnostics=[],points=[],angles=[]) for s in snap['capture']['slots']])
    ids=[s['photo_id'] for s in snap['capture']['slots'] if s['photo_id'] is not None]
    if len(ids)!=len(set(ids)): result['notes'].append(diagnostic('DUPLICATE_PHOTO','동일 사진이 여러 슬롯에 사용되었습니다. 서로 다른 15장을 권장합니다.'))
    identity=store('create_analysis',task['task_id'],task['input_revision'],'RUNNING',snap,now(),result=result)
    return require('analysis',identity)

def run(a,modules,cancel):
    try:
        with _analysis_lock:
            if 'pose' in modules:
                for i,slot in enumerate(a['snapshot']['capture']['slots']):
                    if cancel.is_set():
                        for rest in a['pose']['slots'][i:]: rest.update(status='CANCELED',diagnostics=[diagnostic('CANCELED','분석이 취소되었습니다')])
                        break
                    a['pose']['slots'][i]=pose.process(slot,a['snapshot'])
                    a['pose']['valid_count']=sum(p['status']=='VALID' for p in a['pose']['slots']); persist_analysis(a)
                count=a['pose']['valid_count']; a['pose']['status']='CANCELED' if cancel.is_set() else 'DONE' if count==15 else 'PARTIAL_REVIEW' if count else 'FAILED'
            if 'tags' in modules:
                tags=calculate_tags(a['snapshot'],a['pose']); a['slot_tags']=tags['slots']; a['tags']=tags['summary']
            if 'reba' in modules: a['reba']=calculate_reba(a['snapshot'],a['pose'])
            if 'judgment' in modules: a['judgment']=burden.calculate(a['snapshot']['conditions'],a['snapshot']['legal'])
            a['status']='CANCELED' if cancel.is_set() else 'FINISHED'; a['finished_at']=now(); persist_analysis(a)
    except Exception as error:
        traceback.print_exc(file=sys.stderr); a['status']='FAILED'; a['finished_at']=now(); a['notes'].append(diagnostic('ANALYSIS_ERROR',str(error)))
        if a['pose']:
            a['pose']['status']='FAILED'; a['pose']['terminal_error']=str(error)
            for slot in a['pose']['slots']:
                if slot['status']=='PENDING': slot.update(status='NOT_PROCESSED',diagnostics=[diagnostic('ANALYSIS_ERROR',str(error))])
        try: persist_analysis(a)
        except Exception: traceback.print_exc(file=sys.stderr)
    finally: _cancels.pop(a['analysis_id'],None)

def export_snapshot(survey_id,analysis_ids,include=True):
    survey=require('survey',survey_id); tasks=store('list_tasks',survey_id); chosen=[]; unanalysed=[]
    selected=[analysis(i) for i in analysis_ids]
    for task in tasks:
        options=[a for a in selected if a['task_id']==task['task_id']]
        a=options[0] if options else analysis(task['latest_analysis_id']) if task['latest_analysis_id'] else None
        if a: chosen.append(a)
        else: unanalysed.append(task['task_id'])
    return dict(schema_version='1.3',report_version='1.3',survey=survey,tasks=tasks,analyses=chosen,unanalysed_task_ids=unanalysed,include_representative=include,exported_at=now())

def dispatch(method,p):
    if method=='get_settings': return settings()
    if method=='update_settings':
        value=p['settings']; old=settings()
        if value['analysis']!=old['analysis']:
            for s in store('list_surveys'):
                for t in store('list_tasks',s['survey_id']):
                    if value['analysis']['pose_model']!=old['analysis']['pose_model']: t['manual']=[m for m in t['manual'] if m['source']!='AUTO_ACCEPTED']
                    save_task(t,force=True)
        store('update_settings',value); return settings()
    if method=='list_surveys':
        summaries=[]
        for s in store('list_surveys'):
            ov=report.overview(export_snapshot(s['survey_id'],[])); summaries.append(dict(survey_id=s['survey_id'],title=s['title'],survey_date=s['survey_date'],task_count=len(ov['tasks']),reviewed=s['review']['reviewed'],review_current=ov['state']['review_current']))
        return summaries
    if method=='create_survey':
        review=dict(reviewed=False,reviewed_analysis_ids=[],reviewed_metadata_revision=None,reviewer=None,reviewed_at=None,note=None)
        identity=store('create_survey',p['draft'],review,now(),now()); return require('survey',identity)
    if method=='get_survey': return require('survey',p['survey_id'])
    if method=='update_survey':
        require('survey',p['survey_id'])
        store('update_survey_metadata',p['survey_id'],p['draft'],now())
        return require('survey',p['survey_id'])
    if method=='set_survey_review':
        s=require('survey',p['survey_id']); review=p['review']; review['reviewed_metadata_revision']=s['metadata_revision']; store('set_survey_review',s['survey_id'],review,now()); return require('survey',s['survey_id'])
    if method in ['delete_survey','delete_task']:
        identity=p['survey_id'] if method=='delete_survey' else p['task_id']
        require('survey' if method=='delete_survey' else 'task',identity)
        tasks=store('list_tasks',identity) if method=='delete_survey' else [require('task',identity)]
        for t in tasks:
            for a in store('list_analyses',t['task_id']):
                if a['analysis_id'] in _cancels: _cancels[a['analysis_id']].set()
        store(method,identity); return dict(message='기록을 삭제했습니다. 원본 사진과 Excel은 유지됩니다.')
    if method=='list_tasks':
        require('survey',p['survey_id'])
        return store('list_tasks',p['survey_id'])
    if method=='create_task':
        require('survey',p['survey_id'])
        draft=p['draft']; data=dict(task_kind='FLOOR_TO_SHELF_BOX_SINGLE_PERSON',task_name=draft['task_name'],conditions=copy.deepcopy(draft['conditions']),worker_count=1,legal=legal_inputs(),capture=capture(),manual=[])
        identity=store('create_task',p['survey_id'],data,now(),now()); return require('task',identity)
    if method=='get_task':
        analysis_settings=settings()['analysis']
        task=require('task',p['task_id']); return dict(task=task,exclusions=exclusions(task['conditions']),photos=store('list_photos',task['task_id']),settings=analysis_settings)
    if method in ['rename_task','set_task_conditions','set_legal_inputs','set_capture','set_manual_values']:
        task=require('task',p['task_id']); key={'rename_task':'task_name','set_task_conditions':'conditions','set_legal_inputs':'legal','set_capture':'capture','set_manual_values':'manual'}[method]; value=p[key]
        reset=key=='conditions' and any(task['conditions'].get(f)!=value.get(f) for f in ['worker_code','method_description','shelf_height_cm']) or key=='capture' and any(task['capture'].get(f)!=value.get(f) for f in ['camera_side','forward_direction'])
        if key=='capture':
            replaced=[new['slot_no'] for new,old in zip(value['slots'],task['capture']['slots']) if new['photo_id']!=old['photo_id']]
            task['manual']=[m for m in task['manual'] if m['slot_no'] not in replaced]
            for slot in value['slots']:
                if slot['slot_no'] in replaced: slot['observation']=observation()
        task[key]=value
        if reset:
            task['manual']=[]
            for slot in task['capture']['slots']: slot['observation']=observation()
        return save_task(task)
    if method=='import_photos':
        require('task',p['task_id']); added=[]; unreadable=[]
        for path in p['file_paths']:
            try:
                image=read_image(path); meta=dict(file_path=str(Path(path).resolve()),file_name=Path(path).name,width_px=image.width,height_px=image.height,consent='UNKNOWN',notes=[])
                identity=store('create_photo',p['task_id'],meta); added.append(require('photo',identity))
            except Exception as error: unreadable.append(dict(file_path=path,message=str(error)))
        return dict(added=added,unreadable=unreadable,notes=[])
    if method=='get_photo_preview':
        photo=p['photo']; image=read_image(photo['file_path']); output=BytesIO(); image.save(output,format='PNG')
        return dict(photo_id=photo['photo_id'],data_url='data:image/png;base64,'+base64.b64encode(output.getvalue()).decode('ascii'),width_px=image.width,height_px=image.height)
    if method=='update_photo':
        photo=require('photo',p['photo_id']); path_changed=photo['file_path']!=p['file_path']
        if path_changed:
            with read_image(p['file_path']) as image:
                photo.update(file_name=Path(p['file_path']).name,width_px=image.width,height_px=image.height,notes=[])
        photo.update(file_path=p['file_path'],consent=p['consent']); store('update_photo',photo['photo_id'],{k:v for k,v in photo.items() if k not in ['photo_id','task_id']})
        task=require('task',photo['task_id'])
        if path_changed and any(s['photo_id']==photo['photo_id'] for s in task['capture']['slots']):
            task['manual']=[m for m in task['manual'] if m['photo_id']!=photo['photo_id']]
            for slot in task['capture']['slots']:
                if slot['photo_id']==photo['photo_id']: slot['observation']=observation()
            save_task(task,force=True)
        return photo
    if method=='delete_photo':
        require('photo',p['photo_id'])
        store('delete_photo',p['photo_id']); return dict(message='사진 참조를 삭제했습니다. 원본은 유지됩니다.')
    if method=='start_analysis':
        a=new_analysis(require('task',p['task_id']),['pose','tags','reba','judgment']); cancel=threading.Event(); _cancels[a['analysis_id']]=cancel
        threading.Thread(target=run,args=(a,['pose','tags','reba','judgment'],cancel),daemon=True).start()
        return dict(analysis_id=a['analysis_id'],task_id=a['task_id'],status='RUNNING')
    if method=='get_analysis': return analysis(p['analysis_id'])
    if method=='cancel_analysis':
        a=analysis(p['analysis_id']); cancel=_cancels.get(a['analysis_id'])
        if cancel: cancel.set()
        return dict(analysis_id=a['analysis_id'],task_id=a['task_id'],status=a['status'])
    if method in ['recalculate_reba','recalculate_judgments','recalculate_tags']:
        modules={'recalculate_reba':['reba'],'recalculate_judgments':['judgment'],'recalculate_tags':['tags']}[method]
        a=new_analysis(require('task',p['task_id']),modules); run(a,modules,threading.Event()); return analysis(a['analysis_id'])
    if method=='list_analysis_history': return [analysis(a['analysis_id']) for a in reversed(store('list_analyses',p['task_id']))]
    if method=='get_task_result':
        task=require('task',p['task_id']); a=analysis(task['latest_analysis_id']) if task['latest_analysis_id'] else None; ov=report.overview(export_snapshot(task['survey_id'],[])); t=next(t for t in ov['tasks'] if t['task_id']==task['task_id'])
        warnings=[dict(criterion_no=j['criterion_no'],from_='INVESTIGATOR' if j['investigator']['status'] else 'COMPUTED',message='부담작업 해당 후보입니다') for j in (a or {}).get('judgment',{}).get('judgments',[]) if j['effective_status']=='APPLICABLE'] if a and a.get('judgment') else []
        for w in warnings: w['from']=w.pop('from_')
        return dict(task=task,currentness=t['currentness'],analysis=a,warnings=warnings,review_current=t['state']['review_current'])
    if method=='select_representative':
        a=analysis(p['analysis_id']); reba=a['reba']; slot=next((s for s in (reba or {}).get('slots',[]) if s['slot_no']==p['slot_no']),None)
        if slot and slot['status']=='COMPLETE': reba['summary'].update(representative_slot_no=slot['slot_no'],selection='MANUAL')
        else: a['notes'].append(diagnostic('INCOMPLETE_REPRESENTATIVE','완전 REBA 사진만 점수 대표로 선택할 수 있습니다. 미리보기는 가능합니다.'))
        persist_analysis(a); return analysis(a['analysis_id'])
    if method=='set_investigator_conclusion':
        a=analysis(p['analysis_id']); conclusion=p['conclusion']
        if a['judgment'] is None: raise LookupError('고시 초안 계산을 먼저 실행하세요')
        j=next(j for j in a['judgment']['judgments'] if j['criterion_no']==conclusion['criterion_no']); j['investigator']=conclusion; j['effective_status']=conclusion['status'] or j['computed_status']; persist_analysis(a)
        t=require('task',a['task_id']); s=require('survey',t['survey_id']); s['review']['reviewed']=False; store('set_survey_review',s['survey_id'],s['review'],now()); return analysis(a['analysis_id'])
    if method in ['generate_ai_text','edit_ai_text','apply_ai_text']:
        a=analysis(p['analysis_id']); purpose=p['purpose']; ai=next((x for x in a['ai'] if x['purpose']==purpose),None)
        if method=='generate_ai_text':
            # This sample never calls an external model; preserve transparent fallback.
            ai=dict(purpose=purpose,result='FALLBACK' if settings()['gpt_enabled'] else 'DISABLED',generated_text='현재 결과의 입력 부족·추가 검토 항목을 확인하세요. 사진 빈도는 하루 노출시간이 아니며 조사자 검토는 법적 승인을 뜻하지 않습니다.',edited_text=None,applied_text=None,applied_kind=None,model='',prompt_version='SAMPLE_FIXED_V1',created_at=now())
            a['ai']=[x for x in a['ai'] if x['purpose']!=purpose]+[ai]
        elif ai is None: raise LookupError('설명을 먼저 생성하세요')
        elif method=='edit_ai_text': ai['edited_text']=p['text']
        else: ai['applied_text']=ai['edited_text'] if p['use_edited'] and ai['edited_text'] is not None else ai['generated_text']; ai['applied_kind']='INVESTIGATOR' if p['use_edited'] and ai['edited_text'] is not None else 'FALLBACK'
        persist_analysis(a); return ai
    if method=='preview_excel': return report.overview(export_snapshot(p['survey_id'],p['analysis_ids']))
    if method=='export_excel':
        spec=p['spec']; snap=export_snapshot(p['survey_id'],spec['analysis_ids'],spec['include_representative']); output=report.render(snap,spec['destination']); state=output['overview']['state']
        try: identity=store('create_export_log',p['survey_id'],output['file_path'],snap,dict(sheets=output['sheets'],**state),snap['exported_at'])
        except Exception as error: raise sqlite3.DatabaseError(f'Excel 파일은 생성됐지만 출력 로그 저장에 실패했습니다: {output["file_path"]} / {error}') from error
        return dict(export_id=identity,file_path=output['file_path'],sheets=output['sheets'],created_at=snap['exported_at'],**state)
    raise LookupError('연결되지 않은 서비스 메서드: '+method)
