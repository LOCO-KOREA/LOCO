"""Executable method boundary for docs/API_계약서.md, design 2.0.

SQLite rows are JSON DTOs, not the removed 0.3 relational Protocol.
"""
CONTRACT_VERSION = '2.0'
# method: (required parameter names, optional parameter names)
SERVICE_METHODS = {
    'list_surveys': ((), ()), 'get_settings': ((), ()),
    'create_survey': (('draft',), ()),
    'update_survey': (('survey_id','draft'), ()),
    'get_survey': (('survey_id',), ()), 'delete_survey': (('survey_id',), ()),
    'set_survey_review': (('survey_id','review'), ()),
    'list_tasks': (('survey_id',), ()),
    'create_task': (('survey_id','draft'), ()),
    'save_task_input': (('task_id','input'), ('expected_revision',)),
    'get_task': (('task_id',), ()), 'delete_task': (('task_id',), ()),
    'rename_task': (('task_id','task_name'), ()),
    'set_task_conditions': (('task_id','conditions'), ()),
    'set_task_profile': (('task_id','input_template'), ('worker_count',)),
    'set_legal_inputs': (('task_id','legal'), ()),
    'set_analysis_scope': (('task_id','scope'), ()),
    'import_photos': (('task_id','file_paths'), ()),
    'get_photo_preview': (('photo',), ()),
    'update_photo': (('photo_id','file_path','consent'), ()),
    'delete_photo': (('photo_id',), ()),
    'set_capture': (('task_id','capture'), ()),
    'set_manual_values': (('task_id','manual'), ()),
    'start_analysis': (('task_id',), ()),
    'get_analysis': (('analysis_id',), ()),
    'cancel_analysis': (('analysis_id',), ()),
    'recalculate_reba': (('task_id',), ()),
    'recalculate_judgments': (('task_id',), ()),
    'recalculate_tags': (('task_id',), ()),
    'list_analysis_history': (('task_id',), ()),
    'get_task_result': (('task_id',), ()),
    'select_representative': (('analysis_id','slot_no'), ()),
    'set_investigator_conclusion': (('analysis_id','conclusion'), ()),
    'generate_ai_text': (('analysis_id',), ('purpose',)),
    'edit_ai_text': (('analysis_id','text_id','text'), ()),
    'apply_ai_text': (('analysis_id','text_id','use_edited'), ()),
    'preview_excel': (('survey_id',), ('analysis_ids','comparisons')),
    'preview_excel_sheets': (('survey_id',), ('analysis_ids','comparisons')),
    'export_excel': (('survey_id','spec'), ()),
    'preview_pdf': (('survey_id','spec'), ()),
    'export_pdf': (('survey_id','spec'), ()),
    'list_export_logs': (('survey_id',), ()),
    'update_settings': (('settings',), ()),
    'quick_preview': (('task_id','views'), ()),
    'quick_interpret': (('text',), ()),
}


def validate_request(method, params):
    if not isinstance(method, str) or method not in SERVICE_METHODS:
        raise LookupError('연결되지 않은 2.0 서비스 메서드: '+str(method))
    if not isinstance(params, dict): raise ValueError('params는 객체여야 합니다')
    required, optional = SERVICE_METHODS[method]
    missing=set(required)-params.keys(); extra=params.keys()-set(required)-set(optional)
    if missing or extra: raise ValueError(f'2.0 매개변수 불일치: 누락 {sorted(missing)}, 지원하지 않음 {sorted(extra)}')
    for key in ('survey_id','task_id','photo_id','analysis_id','slot_no'):
        if key in params and (type(params[key]) is not int or params[key]<1):
            raise ValueError(f'{key}는 양의 정수여야 합니다')
    if 'expected_revision' in params and (type(params['expected_revision']) is not int or params['expected_revision']<0):
        raise ValueError('expected_revision은 0 이상 정수여야 합니다')
    if 'purpose' in params and params['purpose'] not in ('TASK_EXPLANATION','IMPROVEMENT_ADVICE'):
        raise ValueError('지원하지 않는 설명 목적입니다')
    if method=='apply_ai_text' and type(params['use_edited']) is not bool:
        raise ValueError('use_edited는 참/거짓이어야 합니다')
    if method=='edit_ai_text' and not isinstance(params['text'],str):
        raise ValueError('설명 편집문은 문자열이어야 합니다')
    if method=='update_photo' and (params['consent'] not in ('YES','NO','UNKNOWN') or not isinstance(params['file_path'],str)):
        raise ValueError('사진 경로는 문자열, 동의는 YES/NO/UNKNOWN이어야 합니다')
    if method=='quick_preview' and (not isinstance(params['views'],dict) or not params['views'] or set(params['views'])-{'LEFT','FRONT','RIGHT'} or any(type(v) is not int or v<1 for v in params['views'].values())):
        raise ValueError('views는 LEFT·FRONT·RIGHT 중 하나 이상의 사진 ID여야 합니다')
    if method=='quick_interpret' and (not isinstance(params['text'],str) or not 1<=len(params['text'].strip())<=600):
        raise ValueError('작업 설명은 1~600자 문장이어야 합니다')
    if method=='set_survey_review' and (not isinstance(params['review'],dict) or type(params['review'].get('reviewed')) is not bool):
        raise ValueError('검토 여부는 참/거짓이어야 합니다')
    if method in ('preview_pdf','export_pdf'):
        spec=params['spec']
        required={'task_ids','analysis_ids','include_representative'}
        if method=='export_pdf':required.add('destination')
        if not isinstance(spec,dict) or set(spec)!=required:
            raise ValueError('PDF 출력 옵션이 올바르지 않습니다.')
        for key in ('task_ids','analysis_ids'):
            values=spec[key]
            if (not isinstance(values,list) or any(type(x) is not int or x<1 for x in values)
                    or len(values)!=len(set(values)) or key=='task_ids' and not values):
                raise ValueError('작업·분석 선택은 중복 없는 양의 정수 목록이어야 합니다.')
        if type(spec['include_representative']) is not bool:
            raise ValueError('대표 사진 포함 여부는 참/거짓이어야 합니다.')
        if method=='export_pdf' and (not isinstance(spec['destination'],str)
                or not spec['destination'].strip() or not spec['destination'].lower().endswith('.pdf')):
            raise ValueError('PDF 저장 경로를 선택해 주세요.')
