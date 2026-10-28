"""LOCO 2.0 reports service. Dependencies are supplied by Runtime."""
import sqlite3
from backend.db import storage
from backend.legacy.v13 import upgrade_task
from backend.engine.task_defaults import now
from backend.engine.survey_defaults import read_survey
from backend.report import workbook as report

def export_snapshot(ctx, survey_id, analysis_ids, include=True, comparisons=None):
    with ctx.db_lock, storage.read_snapshot(ctx.db_path):
        return ctx._export_snapshot(survey_id, analysis_ids, include, comparisons)

def _export_snapshot(ctx, survey_id, analysis_ids, include=True, comparisons=None):
    survey = read_survey(ctx.require('survey', survey_id))
    tasks = [upgrade_task(t) for t in ctx.store('list_tasks', survey_id)]
    chosen = []
    unanalysed = []
    if not isinstance(analysis_ids, list) or any((isinstance(x, bool) or not isinstance(x, int) or x < 1 for x in analysis_ids)):
        raise ValueError('analysis_ids는 양의 정수 목록이어야 합니다')
    if len(analysis_ids) != len(set(analysis_ids)):
        raise ValueError('같은 분석 ID를 두 번 선택할 수 없습니다')
    selected = [ctx.analysis(i) for i in analysis_ids]
    selected_by_task = {}
    for item in selected:
        owner = ctx.require('task', item['task_id'])
        if owner['survey_id'] != survey_id:
            raise ValueError('선택한 분석은 이 조사에 속하지 않습니다')
        if item['task_id'] in selected_by_task:
            raise ValueError('일반 보고서에서는 작업당 분석 하나만 선택할 수 있습니다')
        selected_by_task[item['task_id']] = item
    for task in tasks:
        a = selected_by_task.get(task['task_id']) or (ctx.analysis(task['latest_analysis_id']) if task['latest_analysis_id'] else None)
        if a:
            chosen.append(a)
        else:
            unanalysed.append(task['task_id'])
    comparison_specs = []
    comparison_analyses = []
    comparison_ids = set()
    if comparisons is None:
        comparisons = []
    if not isinstance(comparisons, list):
        raise ValueError('comparisons는 목록이어야 합니다')
    for spec in comparisons:
        if not isinstance(spec, dict):
            raise ValueError('비교 입력 형식이 올바르지 않습니다')
        before_id = spec.get('before_analysis_id')
        after_id = spec.get('after_analysis_id')
        note = spec.get('note')
        if any((isinstance(x, bool) or not isinstance(x, int) or x < 1 for x in (before_id, after_id))) or before_id == after_id:
            raise ValueError('비교에는 서로 다른 양의 분석 ID 두 개가 필요합니다')
        if note is not None and (not isinstance(note, str)):
            raise ValueError('비교 메모는 문자열 또는 비어 있음이어야 합니다')
        pair = []
        for identity in (before_id, after_id):
            item = ctx.analysis(identity)
            owner = ctx.require('task', item['task_id'])
            if owner['survey_id'] != survey_id:
                raise ValueError('비교 분석은 같은 조사에 속해야 합니다')
            pair.append(item)
            if identity not in comparison_ids:
                comparison_analyses.append(item)
                comparison_ids.add(identity)
        comparison_specs.append(dict(before_analysis_id=before_id, after_analysis_id=after_id, note=note))
    return dict(schema_version='2.0', report_version='2.0', survey=survey, tasks=tasks, analyses=chosen, unanalysed_task_ids=unanalysed, include_representative=bool(include), comparison_specs=comparison_specs, comparison_analyses=comparison_analyses, exported_at=now())

def handle_preview_excel(ctx, method, p):
    return report.overview(ctx.export_snapshot(p['survey_id'], p.get('analysis_ids', []), comparisons=p.get('comparisons', [])))

def handle_preview_excel_sheets(ctx, method, p):
    """The plain sheets exactly as the Excel file will contain them. Reads only: nothing is saved or logged."""
    snapshot = ctx.export_snapshot(p['survey_id'], p.get('analysis_ids', []), comparisons=p.get('comparisons', []))
    return dict(sheets=report.plain_sheets(snapshot, report.overview(snapshot)))

def handle_export_excel(ctx, method, p):
    spec = p['spec']
    snap = ctx.export_snapshot(p['survey_id'], spec['analysis_ids'], spec['include_representative'], spec.get('comparisons', []))
    output = report.render(snap, spec['destination'])
    state = output['overview']['state']
    try:
        identity = ctx.store('create_export_log', p['survey_id'], output['file_path'], snap, dict(report_version='2.0', sheets=output['sheets'], **state), snap['exported_at'])
    except Exception as error:
        raise sqlite3.DatabaseError(f'Excel 파일은 생성됐지만 출력 로그 저장에 실패했습니다: {output['file_path']} / {error}') from error
    return dict(export_id=identity, file_path=output['file_path'], sheets=output['sheets'], created_at=snap['exported_at'], report_version='2.0', **state)

def handle_list_export_logs(ctx, method, p):
    ctx.require('survey', p['survey_id'])
    result = []
    for item in ctx.store('list_export_logs', p['survey_id']):
        receipt = dict(item['receipt'], export_id=item['export_id'], file_path=item['file_path'], created_at=item['created_at'])
        receipt.setdefault('report_version', item['snapshot'].get('report_version', item['snapshot'].get('schema_version', '1.3')))
        result.append(dict(export_id=item['export_id'], survey_id=item['survey_id'], file_path=item['file_path'], created_at=item['created_at'], receipt=receipt))
    return result
