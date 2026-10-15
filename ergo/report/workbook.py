"""One snapshot/overview for both the on-screen preview and four-sheet export."""
import json
from datetime import datetime, timedelta
from io import BytesIO
from ergo.engine.task_defaults import PHASE_NAMES
from .labels import input_label, reason_label, investigator_text

NOTICE='작업 분석 보조 보고서. 법정 유해요인조사표·증상조사표의 완성을 뜻하지 않습니다.'
HEADERS={
 'SUMMARY':['task_id','task_name','analysis_id','currentness','review_status','valid_pose_count','complete_reba_count','available_max','full_max','applicable_criteria','needs_input_count','needs_review_count','incomplete_reba_count','next_inputs'],
 'TASK_INPUTS':['task_id','analysis_id','input_revision','input_group','item_code','value','unit','source','evidence_text','observed_at'],
 'PHOTO_REBA':['task_id','analysis_id','slot_no','cycle_no','phase','pose_status','load_state','effective_load_kg','left_total','right_total','selected_side','total','risk','missing_fields','diagnostics','image'],
 'CRITERIA':['task_id','analysis_id','criterion_no','computed_status','investigator_status','effective_status','exclusion','comparison_values','source','evidence_text','review_reasons','missing_fields','investigator_reason','reviewer','reviewed_at','warning']}

def currentness(task,analysis):
    return 'NONE' if analysis is None else 'CURRENT' if task['input_revision']==analysis['input_revision'] and task['latest_analysis_id']==analysis['analysis_id'] else 'STALE'

def overview(snapshot):
    tasks=[]; survey=snapshot['survey']; review=survey['review']
    for task in snapshot['tasks']:
        a=next((a for a in snapshot['analyses'] if a['task_id']==task['task_id']),None)
        snap=a['snapshot'] if a else task; cur=currentness(task,a); pose=a.get('pose') if a else None; reba=a.get('reba') if a else None; judgment=a.get('judgment') if a else None
        judgments=judgment['judgments'] if judgment else []
        counts=dict(needs_input_count=sum(j['computed_status']=='NEEDS_INPUT' for j in judgments) if judgment else None,needs_review_count=sum(j['computed_status']=='NEEDS_REVIEW' for j in judgments) if judgment else None,incomplete_reba_count=15-reba['summary']['complete_count'] if reba else None)
        reviewed=bool(a and review['reviewed'] and a['analysis_id'] in review['reviewed_analysis_ids'])
        state=dict(reviewed=reviewed,review_current=reviewed and review['reviewed_metadata_revision']==survey['metadata_revision'] and cur=='CURRENT',has_incomplete=not a or not pose or pose['valid_count']<15 or not reba or reba['status']=='INCOMPLETE' or not judgment or any(j['computed_status'] in ['NEEDS_INPUT','NEEDS_REVIEW'] for j in judgments),has_stale=cur=='STALE')
        next_inputs=[]
        def add(module,kind,message,slot=None,criterion=None,fields=None,reasons=None):
            next_inputs.append(dict(module=module,kind=kind,slot_no=slot,criterion_no=criterion,field_paths=fields or [],reason_codes=reasons or [],message=message))
        if not a: add('ANALYSIS','NOT_CALCULATED','분석을 아직 수행하지 않았습니다')
        else:
            for module,value,label in [('POSE',pose,'포즈'),('REBA',reba,'REBA'),('BURDEN',judgment,'고시')]:
                if value is None: add(module,'NOT_CALCULATED',label+' 계산을 아직 수행하지 않았습니다')
            for slot in snap['capture']['slots']:
                no=slot['slot_no']; label=f"{slot['cycle_no']}회차 {PHASE_NAMES[(no-1)%5]}"
                p=next((p for p in (pose or {}).get('slots',[]) if p['slot_no']==no),None)
                r=next((r for r in (reba or {}).get('slots',[]) if r['slot_no']==no),None)
                if r and r['missing_fields']: add('REBA','MISSING_INPUT',label+': '+', '.join(input_label(f) for f in r['missing_fields'])+' 입력 필요',no,fields=r['missing_fields'])
                if p and p['status']!='VALID': add('POSE','REVIEW_REQUIRED',label+': '+' / '.join(d['message'] for d in p['diagnostics']),no,fields=list(dict.fromkeys(d['field_path'] for d in p['diagnostics'] if d.get('field_path'))),reasons=list(dict.fromkeys(d['code'] for d in p['diagnostics'])))
                if r:
                    rr=list(dict.fromkeys(r['left']['review_reasons']+r['right']['review_reasons']))
                    if rr: add('REBA','REVIEW_REQUIRED',label+': '+', '.join(reason_label(r) for r in rr),no,reasons=rr)
            for j in judgments:
                if j['missing_fields']: add('BURDEN','MISSING_INPUT',f"{j['criterion_no']}호: "+', '.join(input_label(f) for f in j['missing_fields'])+' 입력 필요',criterion=j['criterion_no'],fields=j['missing_fields'])
                if j['review_reasons']: add('BURDEN','REVIEW_REQUIRED',f"{j['criterion_no']}호: "+', '.join(reason_label(r) for r in j['review_reasons']),criterion=j['criterion_no'],reasons=j['review_reasons'])
        tasks.append(dict(task_id=task['task_id'],task_name=snap['task_name'],analysis_id=a['analysis_id'] if a else None,input_revision=snap['input_revision'],currentness=cur,state=state,review_status='NO_ANALYSIS' if not a else 'UNREVIEWED' if not reviewed else 'REVIEWED_CURRENT' if state['review_current'] else 'REVIEWED_HISTORY',counts=counts,next_inputs=next_inputs))
    state={key:bool(tasks) and all(t['state'][key] for t in tasks) if key in ['reviewed','review_current'] else any(t['state'][key] for t in tasks) for key in ['reviewed','review_current','has_incomplete','has_stale']}
    counts={key:sum(t['counts'][key] for t in tasks) if all(t['counts'][key] is not None for t in tasks) else None for key in ['needs_input_count','needs_review_count','incomplete_reba_count']}
    return dict(report_version='1.3',state=state,counts=counts,tasks=tasks)

def flatten(value,prefix=''):
    if isinstance(value,dict):
        for key,child in value.items(): yield from flatten(child,(prefix+'.' if prefix else '')+key)
    elif isinstance(value,list):
        for i,child in enumerate(value):
            identity=child.get('slot_no',child.get('criterion_no',child.get('condition_code',i))) if isinstance(child,dict) else i
            # Retain scope/field identity for repeated manual values/candidates.
            if isinstance(child,dict) and 'scope' in child: identity=str(identity)+'.'+child['scope']+'.'+child.get('field','')
            yield from flatten(child,prefix+'.'+str(identity))
    else: yield prefix,value

def render(snapshot,destination):
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment
    from openpyxl.utils import get_column_letter
    from openpyxl.drawing.image import Image as ExcelImage
    from ergo.engine.images import read_image
    ov=overview(snapshot); rows={key:[] for key in HEADERS}; survey=snapshot['survey']; representatives=[]
    for t in ov['tasks']:
        a=next((a for a in snapshot['analyses'] if a['task_id']==t['task_id']),None); current=next(x for x in snapshot['tasks'] if x['task_id']==t['task_id']); source=a['snapshot'] if a else current
        pose=a.get('pose') if a else None; reba=a.get('reba') if a else None; judgment=a.get('judgment') if a else None
        judgments=(judgment or {}).get('judgments',[]); aid=t['analysis_id']; tid=t['task_id']; summary=reba['summary'] if reba else {}
        applicable=', '.join(str(j['criterion_no'])+' ('+('INVESTIGATOR' if j['investigator']['status'] else 'COMPUTED')+')' for j in judgments if j['effective_status']=='APPLICABLE')
        rows['SUMMARY'].append([tid,t['task_name'],aid,t['currentness'],t['review_status'],pose['valid_count'] if pose else None,summary.get('complete_count'),summary.get('available_max'),summary.get('full_max'),applicable if judgment else None,*t['counts'].values(),'\n'.join(x['message'] for x in t['next_inputs'])])
        for group,key,value in [('CONDITIONS','conditions',source['conditions']),('LEGAL','legal',source['legal']),('CAPTURE','capture',source['capture']),('MANUAL','manual',source['manual']),('SETTINGS','settings',source.get('settings',{})),('RESULT_POSE','pose',pose),('RESULT_TAG','tags',dict(summary=a.get('tags'),slots=a.get('slot_tags')) if a else None),('RESULT_REBA','reba',reba),('EXPLANATION','ai',a.get('ai') if a else None)]:
            for code,v in flatten(value,key):
                unit='DEG' if code.endswith('value_deg') else 'PX' if code.endswith(('x_px','y_px')) else 'RATIO' if code.endswith(('confidence','min_confidence','sample_ratio')) else 'MIN_DAY' if code.endswith(('minutes','daily_work_min')) else 'KG' if code.endswith('kg') else None
                rows['TASK_INPUTS'].append([tid,aid,t['input_revision'],group,code,v,unit,None,None,None])
        for slot in source['capture']['slots']:
            p=next((p for p in (pose or {}).get('slots',[]) if p['slot_no']==slot['slot_no']),{})
            r=next((r for r in (reba or {}).get('slots',[]) if r['slot_no']==slot['slot_no']),{})
            representative=slot['slot_no']==summary.get('representative_slot_no')
            rows['PHOTO_REBA'].append([tid,aid,slot['slot_no'],slot['cycle_no'],slot['phase'],p.get('status','미계산'),r.get('load_state',slot['observation']['load_state']),r.get('effective_load_kg'),r.get('left',{}).get('total'),r.get('right',{}).get('total'),r.get('selected_side'),r.get('total'),r.get('risk'),'\n'.join(input_label(f) for f in r.get('missing_fields',[])),'\n'.join(d['message'] for d in p.get('diagnostics',[])),'대표 상세블록 참조' if representative else None])
        for number in range(1,12):
            j=next((j for j in judgments if j['criterion_no']==number),{}); inv=j.get('investigator',{}); ci=source['legal']['criteria'][number-1]
            comparison='\n'.join(' | '.join(str(b.get(k,'')) for k in ['item_code','value','unit','operator','threshold','source']) for b in j.get('basis',[])) or '비교근거 없음'
            rows['CRITERIA'].append([tid,aid,number,j.get('computed_status'),inv.get('status'),j.get('effective_status'),j.get('exclusion'),comparison,j.get('source'),ci['evidence']['text'],'\n'.join(reason_label(r) for r in j.get('review_reasons',[])),'\n'.join(input_label(f) for f in j.get('missing_fields',[])),investigator_text(inv),inv.get('reviewer'),inv.get('reviewed_at'),None if j else '고시 미계산'])
        if a:
            for code,v in flatten([j['investigator'] for j in judgments],'investigator'): rows['TASK_INPUTS'].append([tid,aid,t['input_revision'],'INVESTIGATOR',code,v,None,None,None,None])
        representatives.append((tid,aid,source,a,reba))
    wb=Workbook(); wb.remove(wb.active); exported=datetime.fromisoformat(snapshot['exported_at'])+timedelta(hours=9); exported=exported.replace(tzinfo=None)
    for name,headers in HEADERS.items():
        ws=wb.create_sheet(name); ws.append(['LOCO 작업 자세 분석 보고서 — '+name]); ws['A1'].font=Font(name='맑은 고딕',size=17,bold=True,color='1F3A5F')
        ws.append(['survey_id',survey['survey_id'],'report_version','1.3','schema_version','1.3','출력 시각',exported]); ws['H2'].number_format='yyyy-mm-dd hh:mm'
        ws.append(['조사',survey['title'],'조사자',survey['investigator'],'부서',survey['department'],'공정',survey['process']]); ws.append(['조사일',datetime.fromisoformat(survey['survey_date']) if survey['survey_date'] else None]); ws['B4'].number_format='yyyy-mm-dd'
        ws.append(headers); start=5
        for row in rows[name]: ws.append(row)
        end=max(start,ws.max_row); ws.auto_filter.ref=f'A{start}:{get_column_letter(len(headers))}{end}'; ws.freeze_panes='D6'; ws.print_title_rows='1:5'; ws.sheet_properties.pageSetUpPr.fitToPage=False; ws.page_setup.orientation='landscape'
        for i,h in enumerate(headers,1): ws.column_dimensions[get_column_letter(i)].width=48 if h in ['next_inputs','missing_fields','diagnostics','comparison_values','evidence_text','investigator_reason','item_code','value'] else 24 if h=='task_name' else 16
        for row in ws.iter_rows(min_row=5,max_row=end):
            height=26
            for cell in row:
                cell.font=Font(name='맑은 고딕',size=11,color='FFFFFF' if cell.row==5 else '25324A',bold=cell.row==5)
                cell.fill=PatternFill('solid',fgColor='1F3A5F' if cell.row==5 else 'F4F6F8' if cell.row%2==0 else 'FFFFFF'); cell.alignment=Alignment(vertical='top',wrap_text=True)
                if cell.row>5:
                    if cell.value in ['NEEDS_INPUT','INCOMPLETE']: cell.fill=PatternFill('solid',fgColor='FCE4D6')
                    elif cell.value=='NEEDS_REVIEW': cell.fill=PatternFill('solid',fgColor='FFF2CC')
                    height=max(height,18*(str(cell.value or '').count('\n')+max(1,len(str(cell.value or ''))//45)))
                    if isinstance(cell.value,str): cell.data_type='s'
            ws.row_dimensions[row[0].row].height=min(409,height)
        ws.append([]); ws.append([NOTICE]); ws.append(['사진15장의 비율은 하루 노출시간이 아닙니다. 미완료 점수는 0점이 아니며, 검토 표시는 법적 승인을 뜻하지 않습니다.'])
    ws=wb['SUMMARY']
    for key,label in [('needs_input_count','계산 입력 부족 기준 수'),('needs_review_count','추가 검토 기준 수'),('incomplete_reba_count','REBA 미완료 사진 수')]:
        ws.append([label,ov['counts'][key]])
    for key,label in [('reviewed','선택 결과 전체 검토 여부'),('review_current','검토 현재성'),('has_incomplete','미완전 결과 포함'),('has_stale','과거 결과 포함')]:
        ws.append([label,'예' if ov['state'][key] else '아니오'])
    for tid,aid,source,a,reba in representatives:
        ws.append([f'작업 {tid} / 분석 {aid} 상세'])
        t=next(t for t in ov['tasks'] if t['task_id']==tid)
        for item in t['next_inputs']: ws.append([item['message']])
        if a:
            for note in a['notes']: ws.append([note['code'],note['message']])
            for ai in a['ai']:
                if ai['purpose']=='TASK_EXPLANATION': ws.append(['적용 설명',ai['applied_text'],ai['applied_kind']])
        photo_ws=wb['PHOTO_REBA']; photo_ws.append([]); photo_ws.append([f'작업 {tid} / 분석 {aid} 대표 상세'])
        representative=(reba or {}).get('summary',{}).get('representative_slot_no')
        if representative is None: photo_ws.append(['대표 없음']); continue
        slot=source['capture']['slots'][representative-1]; result=reba['slots'][representative-1]
        photo_ws.append(['slot_no',representative,'cycle_no',slot['cycle_no'],'phase',slot['phase'],'photo_id',slot['photo_id']])
        photo_ws.append(['계산된 사진 중 최대',reba['summary']['available_max'],'15장 전체 최대',reba['summary']['full_max'],'대표 total',result['total']])
        for key in ['load_state','effective_load_kg','selected_side','total','risk']: photo_ws.append([key,result[key]])
        side=result.get(result['selected_side'].lower()) if result['selected_side'] else None
        for key,value in (side or {}).items(): photo_ws.append([key,json.dumps(value,ensure_ascii=False) if isinstance(value,list) else value])
        if snapshot['include_representative']:
            photo=next((p for p in source.get('photos',[]) if p['photo_id']==slot['photo_id']),None)
            try:
                image=read_image(photo['file_path']); image.thumbnail((300,240)); stream=BytesIO(); image.save(stream,format='PNG'); stream.seek(0)
                row=photo_ws.max_row+2; photo_ws.add_image(ExcelImage(stream),f'D{row}'); photo_ws.row_dimensions[row].height=190; photo_ws.cell(row,1,'대표사진')
            except Exception as error: photo_ws.append(['원본을 읽을 수 없음',str(error)])
        else: photo_ws.append(['이미지 제외'])
    for ws in wb:
        for row in ws.iter_rows(min_row=6):
            for cell in row:
                if isinstance(cell.value,str): cell.data_type='s'
                if not cell.has_style: cell.font=Font(name='맑은 고딕',size=11); cell.alignment=Alignment(wrap_text=True,vertical='top')
    wb.save(destination)
    return dict(file_path=destination,sheets=list(HEADERS),overview=ov)
