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
from ergo.engine.task_defaults import now,evidence,observation,capture,legal_inputs,task_input as new_task_input,upgrade_task,default_settings,exclusions,diagnostic,PREPROCESS_VERSION,EXPOSURE_V2
from ergo.engine.survey_defaults import normalize_survey
from ergo.engine.reba_scoring import calculate_reba
from ergo.engine.images import read_image
from ergo.engine.pose_tags import calculate_tags
from ergo.engine import burden_rules as burden
from ergo.engine import movenet as pose
from ergo.gpt import payload as gpt_payload
from ergo.gpt import client as gpt_client
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
    return upgrade_task(result) if name=='task' else result

def settings():
    value=store('get_settings')
    if value is None: value=default_settings(); store('update_settings',value)
    if value['analysis']['pose_model']['preprocess_version']!=PREPROCESS_VERSION:
        # Record the actual preprocessing implementation; preserve historical snapshots.
        value['analysis']['pose_model']['preprocess_version']=PREPROCESS_VERSION
        store('update_settings',value)
    return dict(value,gpt_key_present=bool(os.environ.get('OPENAI_API_KEY')))

def task_input(task):
    keys=['schema_version','task_kind','task_name','input_template','worker_count','conditions','legal','capture','manual','analysis_scope','legacy_input']
    return {key:copy.deepcopy(task[key]) for key in keys if key in task}

def save_task(task, *, force=False):
    current=require('task',task['task_id'])
    if force or task_input(current)!=task_input(task):
        store('update_task_input',task['task_id'],task_input(task),now())
    return require('task',task['task_id'])

def analysis(identity):
    result=require('analysis',identity); task=require('task',result['task_id']); result['currentness']=report.currentness(task,result)
    result.setdefault('module_states',dict(pose='NOT_CALCULATED' if result.get('pose') is None else 'COMPLETE' if result['pose'].get('status')=='DONE' else 'INCOMPLETE',tags='NOT_CALCULATED' if result.get('tags') is None else 'COMPLETE',reba='NOT_CALCULATED' if result.get('reba') is None else 'COMPLETE' if result['reba'].get('status')=='COMPLETE' else 'INCOMPLETE',judgment='NOT_CALCULATED' if result.get('judgment') is None else 'COMPLETE'))
    try:
        current_summary=gpt_payload.build_numeric_summary(result)
        for item in result.get('ai',[]): item['source_current']=item.get('input_summary')==current_summary
    except Exception: pass
    return result

def snapshot(task):
    return dict(schema_version=task.get('schema_version','1.3'),task_id=task['task_id'],input_revision=task['input_revision'],task_name=task['task_name'],task_kind=task.get('task_kind'),input_template=task.get('input_template'),worker_count=task.get('worker_count'),conditions=copy.deepcopy(task['conditions']),legal=copy.deepcopy(task['legal']),capture=copy.deepcopy(task['capture']),manual=copy.deepcopy(task['manual']),analysis_scope=copy.deepcopy(task.get('analysis_scope')),legacy_input=copy.deepcopy(task.get('legacy_input')),photos=store('list_photos',task['task_id']),settings=settings()['analysis'])

def reconcile_capture(task, capture_value):
    if not isinstance(capture_value,dict) or capture_value.get('protocol')!='GENERAL_STILLS_V1' or not isinstance(capture_value.get('slots'),list):
        raise ValueError('capture는 GENERAL_STILLS_V1 사진 행 목록이어야 합니다')
    photos={p['photo_id'] for p in store('list_photos',task['task_id'])}
    old={slot['slot_no']:slot for slot in task['capture'].get('slots',[])}
    seen=set(); new_slots=[]; changed=set()
    for slot in capture_value['slots']:
        if not isinstance(slot,dict): raise ValueError('사진 행 형식이 올바르지 않습니다')
        no=slot.get('slot_no'); photo_id=slot.get('photo_id')
        if isinstance(no,bool) or not isinstance(no,int) or no<1 or no in seen: raise ValueError('사진 행 번호는 중복 없는 양의 정수여야 합니다')
        if photo_id is not None and (isinstance(photo_id,bool) or not isinstance(photo_id,int) or photo_id not in photos): raise ValueError(f'{no}번 행의 사진이 이 작업에 속하지 않습니다')
        if not isinstance(slot.get('analysis_target'),bool): raise ValueError(f'{no}번 행의 분석대상은 참/거짓이어야 합니다')
        if slot.get('camera_side') not in (None,'LEFT','RIGHT','FRONT','OTHER') or slot.get('forward_direction') not in (None,'SCREEN_RIGHT','SCREEN_LEFT'):
            raise ValueError(f'{no}번 행의 카메라 방향 값이 올바르지 않습니다')
        if slot.get('side_view_verified') not in (None,'YES','NO','UNKNOWN'):
            raise ValueError(f'{no}번 행의 측면 확인 값이 올바르지 않습니다')
        previous=old.get(no)
        row=copy.deepcopy(slot)
        if previous is not None and any(row.get(key)!=previous.get(key) for key in ['photo_id','camera_side','forward_direction']):
            changed.add(no)
            row['side_view_verified']='UNKNOWN'
            row['observation']=dict(load_state='UNKNOWN',measured_load_kg=None,single_person='UNKNOWN',full_frame='UNKNOWN',normal_work='UNKNOWN',evidence=evidence())
        elif previous is not None and ('observation' not in slot or row.get('observation')==previous.get('observation')):
            # Preserve server-side observations when the caller did not edit them.
            row['observation']=copy.deepcopy(previous.get('observation') or row.get('observation'))
        if not isinstance(row.get('observation'),dict): raise ValueError(f'{no}번 행의 관찰값 형식이 올바르지 않습니다')
        obs=row['observation']
        if obs.get('load_state','UNKNOWN') not in ('UNKNOWN','UNLOADED','MEASURED'):
            raise ValueError(f'{no}번 행의 하중 상태 값이 올바르지 않습니다')
        for key in ('single_person','full_frame','normal_work'):
            if obs.get(key,'UNKNOWN') not in ('YES','NO','UNKNOWN'):
                raise ValueError(f'{no}번 행의 {key} 값이 올바르지 않습니다')
        measured=obs.get('measured_load_kg')
        if measured is not None and (isinstance(measured,bool) or not isinstance(measured,(int,float))):
            raise ValueError(f'{no}번 행의 측정 하중은 숫자 또는 비어 있음이어야 합니다')
        ev=obs.get('evidence')
        if ev is not None and (not isinstance(ev,dict) or any(ev.get(k) is not None and not isinstance(ev.get(k),str) for k in ('source','text','observed_at'))):
            raise ValueError(f'{no}번 행의 근거 형식이 올바르지 않습니다')
        seen.add(no); new_slots.append(row)
    removed=set(old)-seen
    task['manual']=[m for m in task['manual'] if m.get('slot_no') not in removed|changed]
    task['capture']=dict(protocol='GENERAL_STILLS_V1',slots=new_slots)

def validate_task_input_shape(value):
    if not isinstance(value,dict) or value.get('schema_version')!='2.0' or value.get('task_kind')!='GENERAL_TASK':
        raise ValueError('일반 작업 입력 2.0이 필요합니다')
    scope=value.get('analysis_scope')
    if not isinstance(scope,dict) or set(scope)!={'judgment','pose','tags','reba'} or any(type(v) is not bool for v in scope.values()):
        raise ValueError('analysis_scope는 네 모듈의 참/거짓 선택이어야 합니다')
    conditions=value.get('conditions')
    if not isinstance(conditions,dict): raise ValueError('작업조건 객체가 필요합니다')
    for key in ('work_intensity','work_frequency'):
        score=conditions.get(key)
        if score is not None and (isinstance(score,bool) or not isinstance(score,int) or not 1<=score<=5):
            raise ValueError(f'conditions.{key}는 1~5 또는 비어 있음이어야 합니다')
    for key in ('work_posture','method_description','hazard_factors','hazard_causes','improvement_recommendations'):
        if conditions.get(key) is not None and not isinstance(conditions.get(key),str):
            raise ValueError(f'conditions.{key}는 문자열이어야 합니다')
    legal=value.get('legal')
    criteria=legal.get('criteria') if isinstance(legal,dict) else None
    if not isinstance(criteria,list) or len(criteria)!=11 or any(not isinstance(x,dict) for x in criteria):
        raise ValueError('11개 기준 입력이 필요합니다')
    criterion_ids=[x.get('criterion_no') for x in criteria]
    if any(isinstance(x,bool) or not isinstance(x,int) for x in criterion_ids) or criterion_ids!=list(range(1,12)):
        raise ValueError('기준 번호는 1호부터 11호까지 한 번씩 있어야 합니다')
    exposures=legal.get('exposures')
    codes=[x.get('condition_code') for x in exposures] if isinstance(exposures,list) and all(isinstance(x,dict) for x in exposures) else None
    if codes!=EXPOSURE_V2:
        raise ValueError('일일 노출 입력 코드는 2.0 기준 목록과 일치해야 합니다')
    for number in range(6,12):
        criterion=criteria[number-1]; rows=criterion.get('rows')
        if not isinstance(rows,list): raise ValueError(f'{number}호 조건 행 목록이 필요합니다')
        ids=[row.get('row_id') for row in rows if isinstance(row,dict)]
        if len(ids)!=len(rows) or any(not isinstance(x,str) or not x for x in ids) or len(ids)!=len(set(ids)):
            raise ValueError(f'{number}호 조건 행 ID는 비어 있거나 중복될 수 없습니다')
        if number==9:
            if not isinstance(criterion.get('totals'),dict): raise ValueError('9호 합집합 입력이 필요합니다')
        elif not isinstance(criterion.get('union'),dict):
            raise ValueError(f'{number}호 합집합 입력이 필요합니다')
    capture_value=value.get('capture')
    if not isinstance(capture_value,dict) or capture_value.get('protocol')!='GENERAL_STILLS_V1' or not isinstance(capture_value.get('slots'),list):
        raise ValueError('일반 사진 행 목록이 필요합니다')
    slots=capture_value['slots']; slot_ids=[x.get('slot_no') for x in slots if isinstance(x,dict)]
    if len(slot_ids)!=len(slots) or any(isinstance(x,bool) or not isinstance(x,int) or x<1 for x in slot_ids) or len(slot_ids)!=len(set(slot_ids)):
        raise ValueError('사진 행 번호는 중복 없는 양의 정수여야 합니다')
    if any(type(x.get('analysis_target')) is not bool or not isinstance(x.get('observation'),dict) for x in slots):
        raise ValueError('사진 행의 분석대상과 관찰 입력 형식이 올바르지 않습니다')
    if not isinstance(value.get('manual'),list): raise ValueError('수동 관찰 입력은 목록이어야 합니다')

RESULT_KEYS=['module_states','pose','slot_tags','tags','reba','judgment','ai','notes']
def persist_analysis(a):
    with _db_lock:
        latest=storage.get_analysis(a['analysis_id'],db_path=DB)
        if latest:
            # Background pose progress must not roll back user edits made while it ran.
            merged={item.get('text_id'):copy.deepcopy(item) for item in latest.get('ai',[]) if item.get('text_id')}
            for item in a.get('ai',[]):
                identity=item.get('text_id')
                if not identity: continue
                if identity not in merged: merged[identity]=copy.deepcopy(item); continue
                saved=merged[identity]
                if item.get('edited_at') and (not saved.get('edited_at') or item['edited_at']>=saved['edited_at']): saved['edited_text']=item.get('edited_text'); saved['edited_at']=item['edited_at']
                if item.get('applied_at') and (not saved.get('applied_at') or item['applied_at']>=saved['applied_at']):
                    for key in ['applied_text','applied_kind','applied_at']: saved[key]=item.get(key)
            a['ai']=list(merged.values())
            newest={}
            for item in a['ai']:
                if item.get('applied_at') and (item.get('purpose') not in newest or item['applied_at']>newest[item['purpose']].get('applied_at','')): newest[item['purpose']]=item
            for item in a['ai']:
                item['is_active']=item.get('purpose') in newest and newest[item['purpose']].get('text_id')==item.get('text_id')
            prior={j.get('criterion_no'):j for j in (latest.get('judgment') or {}).get('judgments',[])}
            for item in (a.get('judgment') or {}).get('judgments',[]):
                old=prior.get(item.get('criterion_no'))
                if old and old.get('investigator',{}).get('status') is not None:
                    item['investigator']=copy.deepcopy(old['investigator'])
                    item['effective_status']=old.get('effective_status',item['computed_status'])
        storage.update_analysis(a['analysis_id'],a['status'],{key:a[key] for key in RESULT_KEYS},a['finished_at'],db_path=DB)

def pose_inputs(snap):
    """Only dependencies of inference; load observations do not change coordinates."""
    cap=snap['capture']; assigned={s['photo_id'] for s in cap['slots'] if s['photo_id'] is not None and s.get('analysis_target',True)}
    return dict(slots=[(s['slot_no'],s['photo_id'],s.get('analysis_target'),s.get('camera_side'),s.get('forward_direction')) for s in cap['slots']],
        photos=sorted((p['photo_id'],p['file_path'],p.get('width_px'),p.get('height_px')) for p in snap['photos'] if p['photo_id'] in assigned),
        context={k:snap['conditions'].get(k) for k in ['worker_code','method_description','work_height_cm']},
        model=snap['settings']['pose_model'])

def new_analysis(task,modules):
    settings()
    task=require('task',task['task_id'])
    snap=snapshot(task); old=store('get_analysis',task['latest_analysis_id']) if task['latest_analysis_id'] else None
    result=dict(module_states={key:'RUNNING' if key in modules else 'NOT_REQUESTED' for key in ['pose','tags','reba','judgment']},pose=None,slot_tags=[],tags=None,reba=None,judgment=None,ai=[],notes=[])
    if old and old.get('snapshot',{}).get('schema_version')==snap.get('schema_version') and modules!=['pose','tags','reba','judgment']:
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
        if pose_same and same(['manual','capture','conditions']) and previous['settings']['reba_rule']==snap['settings']['reba_rule']: result['reba']=old['reba']
        if same(['conditions','legal']) and previous['settings']['burden_rule']==snap['settings']['burden_rule']:
            result['judgment']=copy.deepcopy(old['judgment'])
            if result['judgment']:
                for j in result['judgment']['judgments']:
                    j['investigator']=dict(criterion_no=j['criterion_no'],status=None,reason=None,evidence=evidence(),reviewer=None,reviewed_at=None); j['effective_status']=j['computed_status']
        for module,key in [('pose','pose'),('reba','reba'),('judgment','judgment')]:
            if module not in modules and result[key] is None: result['notes'].append(diagnostic('RECALCULATE_REQUIRED',module+' 결과가 없거나 관련 입력이 달라 재계산이 필요합니다'))
    targets=[s for s in snap['capture']['slots'] if s.get('analysis_target') and s.get('photo_id') is not None]
    if not modules: raise ValueError('분석 범위를 하나 이상 선택하세요')
    if not targets and 'tags' in modules: result['notes'].append(diagnostic('NO_ANALYSIS_TARGET','자세 기술태그를 계산할 분석대상 사진이 없습니다'))
    if not targets and 'reba' in modules: result['notes'].append(diagnostic('NO_ANALYSIS_TARGET','REBA를 계산할 분석대상 사진이 없습니다'))
    if 'pose' in modules:
        result['pose']=dict(status='RUNNING' if targets else 'FAILED',valid_count=0,total_slot_count=len(targets),terminal_error=None if targets else 'NO_ANALYSIS_TARGET',slots=[dict(slot_no=s['slot_no'],photo_id=s['photo_id'],status='PENDING',diagnostics=[],points=[],angles=[]) for s in targets])
        if not targets: result['module_states']['pose']='FAILED'
    ids=[s['photo_id'] for s in targets]
    if len(ids)!=len(set(ids)): result['notes'].append(diagnostic('DUPLICATE_PHOTO','같은 사진이 여러 분석대상 슬롯에 배정되었습니다.'))
    identity=store('create_analysis',task['task_id'],task['input_revision'],'RUNNING',snap,now(),result=result)
    return require('analysis',identity)

def run(a,modules,cancel):
    try:
        with _analysis_lock:
            targets=[s for s in a['snapshot']['capture']['slots'] if s.get('analysis_target') and s.get('photo_id') is not None]
            if 'pose' in modules:
                assigned=[slot['photo_id'] for slot in targets]
                duplicates={identity for identity in assigned if assigned.count(identity)>1}
                for i,slot in enumerate(targets):
                    if cancel.is_set():
                        for rest in a['pose']['slots'][i:]: rest.update(status='CANCELED',diagnostics=[diagnostic('CANCELED','분석이 취소되었습니다')])
                        break
                    a['pose']['slots'][i]=pose.process(slot,a['snapshot'])
                    if slot['photo_id'] in duplicates:
                        a['pose']['slots'][i]['status']='INVALID'
                        a['pose']['slots'][i].setdefault('diagnostics',[]).append(diagnostic('DUPLICATE_PHOTO','같은 사진이 다른 분석대상 행에도 배정되어 별도 표본으로 계산하지 않습니다'))
                    a['pose']['valid_count']=sum(p['status']=='VALID' for p in a['pose']['slots']); persist_analysis(a)
                count=a['pose']['valid_count']; statuses=[p['status'] for p in a['pose']['slots']]
                all_errors=bool(statuses) and all(status=='ERROR' for status in statuses)
                a['pose']['status']='CANCELED' if cancel.is_set() else 'DONE' if count==len(targets) and count else 'FAILED' if all_errors else 'PARTIAL_REVIEW'
                a['module_states']['pose']='CANCELED' if cancel.is_set() else 'COMPLETE' if count==len(targets) and count else 'FAILED' if all_errors else 'INCOMPLETE'
            if cancel.is_set():
                for key in modules:
                    if a['module_states'].get(key)=='RUNNING': a['module_states'][key]='CANCELED'
                a['status']='CANCELED'; a['finished_at']=now(); persist_analysis(a); return
            if 'tags' in modules:
                tags=calculate_tags(a['snapshot'],a['pose']); a['slot_tags']=tags['slots']; a['tags']=tags['summary']
                unique_targets=len({s['photo_id'] for s in targets})==len(targets)
                a['module_states']['tags']='COMPLETE' if targets and unique_targets and all(x['observed_count']==len(targets) for x in tags['summary']) else 'INCOMPLETE'
            if cancel.is_set():
                for key in modules:
                    if a['module_states'].get(key)=='RUNNING': a['module_states'][key]='CANCELED'
                a['status']='CANCELED'; a['finished_at']=now(); persist_analysis(a); return
            if 'reba' in modules:
                a['reba']=calculate_reba(a['snapshot'],a['pose']); a['module_states']['reba']='COMPLETE' if targets and a['reba']['status']=='COMPLETE' else 'INCOMPLETE'
            if cancel.is_set():
                for key in modules:
                    if a['module_states'].get(key)=='RUNNING': a['module_states'][key]='CANCELED'
                a['status']='CANCELED'; a['finished_at']=now(); persist_analysis(a); return
            if 'judgment' in modules:
                a['judgment']=burden.calculate(a['snapshot']['conditions'],a['snapshot']['legal'],a['snapshot'].get('schema_version','1.3'))
                a['module_states']['judgment']='INCOMPLETE' if any(j['computed_status'] in ['NEEDS_INPUT','NEEDS_REVIEW'] for j in a['judgment']['judgments']) else 'COMPLETE'
            a['status']='CANCELED' if cancel.is_set() else 'FINISHED'; a['finished_at']=now(); persist_analysis(a)
    except Exception as error:
        traceback.print_exc(file=sys.stderr); a['status']='FAILED'; a['finished_at']=now(); a['notes'].append(diagnostic('ANALYSIS_ERROR',str(error)))
        for key,state in a.get('module_states',{}).items():
            if state=='RUNNING': a['module_states'][key]='FAILED'
        if a['pose']:
            a['pose']['status']='FAILED'; a['pose']['terminal_error']=str(error)
            for slot in a['pose']['slots']:
                if slot['status']=='PENDING': slot.update(status='NOT_PROCESSED',diagnostics=[diagnostic('ANALYSIS_ERROR',str(error))])
        try: persist_analysis(a)
        except Exception: traceback.print_exc(file=sys.stderr)
    finally: _cancels.pop(a['analysis_id'],None)

def export_snapshot(survey_id,analysis_ids,include=True,comparisons=None):
    survey=require('survey',survey_id); survey.update(normalize_survey(survey)); tasks=[upgrade_task(t) for t in store('list_tasks',survey_id)]; chosen=[]; unanalysed=[]
    if not isinstance(analysis_ids,list) or any(isinstance(x,bool) or not isinstance(x,int) or x<1 for x in analysis_ids): raise ValueError('analysis_ids는 양의 정수 목록이어야 합니다')
    if len(analysis_ids)!=len(set(analysis_ids)): raise ValueError('같은 분석 ID를 두 번 선택할 수 없습니다')
    selected=[analysis(i) for i in analysis_ids]
    selected_by_task={}
    for item in selected:
        owner=require('task',item['task_id'])
        if owner['survey_id']!=survey_id: raise ValueError('선택한 분석은 이 조사에 속하지 않습니다')
        if item['task_id'] in selected_by_task: raise ValueError('일반 보고서에서는 작업당 분석 하나만 선택할 수 있습니다')
        selected_by_task[item['task_id']]=item
    for task in tasks:
        a=selected_by_task.get(task['task_id']) or (analysis(task['latest_analysis_id']) if task['latest_analysis_id'] else None)
        if a: chosen.append(a)
        else: unanalysed.append(task['task_id'])
    comparison_specs=[]; comparison_analyses=[]; comparison_ids=set()
    if comparisons is None: comparisons=[]
    if not isinstance(comparisons,list): raise ValueError('comparisons는 목록이어야 합니다')
    for spec in comparisons:
        if not isinstance(spec,dict): raise ValueError('비교 입력 형식이 올바르지 않습니다')
        before_id=spec.get('before_analysis_id'); after_id=spec.get('after_analysis_id'); note=spec.get('note')
        if any(isinstance(x,bool) or not isinstance(x,int) or x<1 for x in (before_id,after_id)) or before_id==after_id: raise ValueError('비교에는 서로 다른 양의 분석 ID 두 개가 필요합니다')
        if note is not None and not isinstance(note,str): raise ValueError('비교 메모는 문자열 또는 비어 있음이어야 합니다')
        pair=[]
        for identity in (before_id,after_id):
            item=analysis(identity); owner=require('task',item['task_id'])
            if owner['survey_id']!=survey_id: raise ValueError('비교 분석은 같은 조사에 속해야 합니다')
            pair.append(item)
            if identity not in comparison_ids: comparison_analyses.append(item); comparison_ids.add(identity)
        comparison_specs.append(dict(before_analysis_id=before_id,after_analysis_id=after_id,note=note))
    return dict(schema_version='2.0',report_version='2.0',survey=survey,tasks=tasks,analyses=chosen,unanalysed_task_ids=unanalysed,include_representative=bool(include),comparison_specs=comparison_specs,comparison_analyses=comparison_analyses,exported_at=now())

def dispatch(method,p):
    if method=='get_settings': return settings()
    if method=='update_settings':
        value=p['settings']; old=settings()
        if value['analysis']['pose_model']!=old['analysis']['pose_model']:
            for s in store('list_surveys'):
                for raw in store('list_tasks',s['survey_id']):
                    t=upgrade_task(raw)
                    if t.get('schema_version')!='2.0' or raw.get('schema_version')!='2.0': continue
                    original=t['manual']; t['manual']=[m for m in original if m.get('source')!='AUTO_ACCEPTED']
                    if len(t['manual'])!=len(original): save_task(t)
        store('update_settings',value); return settings()
    if method=='list_surveys':
        summaries=[]
        for s in store('list_surveys'):
            ov=report.overview(export_snapshot(s['survey_id'],[])); summaries.append(dict(survey_id=s['survey_id'],title=s['title'],survey_date=s['survey_date'],task_count=len(ov['tasks']),reviewed=s['review']['reviewed'],review_current=ov['state']['review_current']))
        return summaries
    if method=='create_survey':
        review=dict(reviewed=False,reviewed_analysis_ids=[],reviewed_metadata_revision=None,reviewer=None,reviewed_at=None,note=None)
        draft=normalize_survey(p['draft'],require_occasional_cause=True)
        identity=store('create_survey',draft,review,now(),now()); return require('survey',identity)
    if method=='get_survey':
        result=require('survey',p['survey_id']); result.update(normalize_survey(result)); return result
    if method=='update_survey':
        require('survey',p['survey_id'])
        draft=normalize_survey(p['draft'],require_occasional_cause=True)
        store('update_survey_metadata',p['survey_id'],draft,now())
        result=require('survey',p['survey_id']); result.update(normalize_survey(result)); return result
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
        return [upgrade_task(t) for t in store('list_tasks',p['survey_id'])]
    if method=='create_task':
        require('survey',p['survey_id'])
        data=new_task_input(p['draft'])
        validate_task_input_shape(data)
        identity=store('create_task',p['survey_id'],data,now(),now()); return require('task',identity)
    if method=='save_task_input':
        task=require('task',p['task_id']); raw=store('get_task',p['task_id']); incoming=p.get('input')
        validate_task_input_shape(incoming)
        old_conditions=task['conditions']
        for key in ['task_name','input_template','worker_count','conditions','legal','manual','analysis_scope','legacy_input']:
            if key not in incoming: raise ValueError(f'필수 입력 누락: {key}')
            task[key]=copy.deepcopy(incoming[key])
        reconcile_capture(task,incoming.get('capture'))
        if any(old_conditions.get(f)!=task['conditions'].get(f) for f in ['worker_code','method_description','work_height_cm']):
            task['manual']=[]
            for slot in task['capture']['slots']: slot['observation']=dict(load_state='UNKNOWN',measured_load_kg=None,single_person='UNKNOWN',full_frame='UNKNOWN',normal_work='UNKNOWN',evidence=evidence())
        return save_task(task,force=raw.get('schema_version')!='2.0')
    if method=='get_task':
        analysis_settings=settings()['analysis']
        task=require('task',p['task_id']); return dict(task=task,source_schema_version=task.get('source_schema_version','2.0'),exclusions=exclusions(task['conditions']),photos=store('list_photos',task['task_id']),settings=analysis_settings)
    if method in ['rename_task','set_task_conditions','set_legal_inputs','set_capture','set_manual_values']:
        task=require('task',p['task_id']); key={'rename_task':'task_name','set_task_conditions':'conditions','set_legal_inputs':'legal','set_capture':'capture','set_manual_values':'manual'}[method]; value=p[key]
        reset=key=='conditions' and any(task['conditions'].get(f)!=value.get(f) for f in ['worker_code','method_description','work_height_cm'])
        if key=='capture': reconcile_capture(task,value)
        else: task[key]=value
        if reset:
            task['manual']=[]
            for slot in task['capture']['slots']: slot['observation']=dict(load_state='UNKNOWN',measured_load_kg=None,single_person='UNKNOWN',full_frame='UNKNOWN',normal_work='UNKNOWN',evidence=evidence())
        return save_task(task)
    if method=='set_task_profile':
        task=require('task',p['task_id']); task['input_template']=p['input_template']; task['worker_count']=p.get('worker_count'); return save_task(task)
    if method=='set_analysis_scope':
        task=require('task',p['task_id']); task['analysis_scope']=p['scope']; return save_task(task)
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
        if path_changed and any(s['photo_id']==photo['photo_id'] for s in task['capture']['slots']): save_task(task,force=True)
        return photo
    if method=='delete_photo':
        require('photo',p['photo_id'])
        store('delete_photo',p['photo_id']); return dict(message='사진 참조를 삭제했습니다. 원본은 유지됩니다.')
    if method=='start_analysis':
        task=require('task',p['task_id']); scope=task.get('analysis_scope') or dict(judgment=True,pose=False,tags=False,reba=False)
        modules=[key for key in ['pose','tags','reba','judgment'] if scope.get(key)]
        a=new_analysis(task,modules); cancel=threading.Event(); _cancels[a['analysis_id']]=cancel
        threading.Thread(target=run,args=(a,modules,cancel),daemon=True).start()
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
        a=analysis(p['analysis_id']); purpose=p.get('purpose') or next((x.get('purpose') for x in a['ai'] if x.get('text_id')==p.get('text_id')),None) or 'TASK_EXPLANATION'
        if method=='generate_ai_text':
            saved_settings=settings(); summary=gpt_payload.build_numeric_summary(a); result='DISABLED'; content=None; reason=None
            if saved_settings['gpt_enabled']:
                content,reason=gpt_client.generate(summary,saved_settings.get('gpt_model'),os.environ.get('OPENAI_API_KEY'))
                result='GENERATED' if content else 'FALLBACK'
            ai=dict(text_id=__import__('uuid').uuid4().hex,is_active=False,purpose=purpose,result=result,generated_text=gpt_client.content_text(content) if content else '수치 요약의 입력 누락과 추가 확인 항목을 검토하세요. 사진 표본 비율은 하루 노출시간이 아니며, 계산 결과와 조사자 결론은 별도로 확인해야 합니다.',edited_text=None,applied_text=None,applied_kind=None,content=content,input_summary=summary,model=saved_settings.get('gpt_model',''),prompt_version=gpt_client.PROMPT_VERSION,created_at=now(),edited_at=None,applied_at=None,fallback_reason=reason)
            a.setdefault('ai',[]).append(ai); persist_analysis(a); return dict(text=ai,source_current=True)
        else:
            ai=next((x for x in a.get('ai',[]) if x.get('text_id')==p.get('text_id')),None)
            if ai is None: raise LookupError('해당 설명 이력을 찾을 수 없습니다')
            if method=='edit_ai_text':
                ai['edited_text']=str(p['text']); ai['edited_at']=now()
            else:
                target=p.get('edited_text',p.get('use_edited',False))
                chosen=ai.get('edited_text') if target else ai.get('generated_text')
                if ai['result']=='DISABLED' or not chosen: raise LookupError('비활성 또는 빈 설명은 적용할 수 없습니다')
                for old in a.get('ai',[]):
                    if old.get('purpose')==ai['purpose']: old['is_active']=False
                ai['is_active']=True; ai['applied_text']=chosen; ai['applied_kind']='INVESTIGATOR' if target and ai.get('edited_text') is not None else 'MODEL' if ai['result']=='GENERATED' else 'FALLBACK'; ai['applied_at']=now()
            persist_analysis(a)
            current=gpt_payload.build_numeric_summary(analysis(a['analysis_id']))
            return dict(text=ai,source_current=current==ai.get('input_summary'))
    if method=='preview_excel': return report.overview(export_snapshot(p['survey_id'],p.get('analysis_ids',[]),comparisons=p.get('comparisons',[])))
    if method=='export_excel':
        spec=p['spec']; snap=export_snapshot(p['survey_id'],spec['analysis_ids'],spec['include_representative'],spec.get('comparisons',[])); output=report.render(snap,spec['destination']); state=output['overview']['state']
        try: identity=store('create_export_log',p['survey_id'],output['file_path'],snap,dict(sheets=output['sheets'],**state),snap['exported_at'])
        except Exception as error: raise sqlite3.DatabaseError(f'Excel 파일은 생성됐지만 출력 로그 저장에 실패했습니다: {output["file_path"]} / {error}') from error
        return dict(export_id=identity,file_path=output['file_path'],sheets=output['sheets'],created_at=snap['exported_at'],**state)
    raise LookupError('연결되지 않은 서비스 메서드: '+method)
