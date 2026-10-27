"""Explicit human criterion confirmation. AI proposals never write facts themselves."""
import copy
from uuid import uuid4
from ergo.engine.task_defaults import now
from ergo.gpt import criterion_review as review
from ergo.gpt.payload import validate_content


def handle_confirm_criterion_review(ctx,method,p):
    with ctx.db_lock:
        analysis=ctx.analysis(p['analysis_id'])
        task=ctx.require('task',analysis['task_id'])
        if (analysis['currentness']!='CURRENT' or analysis['status']!='FINISHED' or
                task['input_revision']!=p['expected_input_revision']):
            raise ValueError('작업 입력이나 분석이 바뀌었습니다. 현재 결과를 다시 확인해 주세요.')
        if not analysis.get('judgment'):
            raise ValueError('호별 계산 결과를 먼저 확인해 주세요.')
        source_id=p.get('source_text_id')
        source=next((item for item in analysis.get('ai',[]) if item.get('text_id')==source_id),None) if source_id else None
        if source_id and (source is None or source.get('purpose')!='TASK_EXPLANATION' or source.get('result')!='GENERATED' or
                not validate_content(source.get('content'),source.get('input_summary'),allow_legacy=False) or
                not (source.get('source_current') or source.get('confirmation_current'))):
            raise ValueError('선택한 AI 설명이 현재 결과와 다릅니다. 현재 설명을 다시 확인해 주세요.')
        token=ctx.analysis_token(analysis['analysis_id'])
        reviewed_at=now();reviewer=p.get('reviewer')
        submitted=copy.deepcopy(p['conclusions'])

        def update(result):
            by_number={item['criterion_no']:item for item in result['judgment']['judgments']}
            previous=result.get('criterion_review')
            frame={**analysis,**result,'currentness':'CURRENT'}
            merged={number:dict(criterion_no=number,status=item['investigator']['status']) for number,item in by_number.items()
                    if (item.get('investigator') or {}).get('status') in review.BINARY_STATUSES}
            if review.confirmation_current(frame):
                merged.update({item['criterion_no']:copy.deepcopy(item) for item in previous.get('conclusions',[])})
            for choice in submitted:
                number,status=choice['criterion_no'],choice['status']
                if number not in by_number:raise ValueError('현재 분석에 없는 호를 확정할 수 없습니다.')
                judgment=by_number[number]
                if status!='UNDETERMINED':
                    judgment['investigator']=dict(criterion_no=number,status=status,
                        reason='호별 검토 화면에서 직접 확정' if status is not None else '호별 검토 화면에서 직접 결론 해제',
                        evidence=dict(source='OTHER',text='AI 참고 선택과 계산 초안을 검토해 직접 선택' if source_id else '계산 초안을 검토해 직접 선택',observed_at=reviewed_at),
                        reviewer=reviewer,reviewed_at=reviewed_at)
                    judgment['effective_status']=status or judgment['computed_status']
                merged[number]=dict(criterion_no=number,status=status)
            if previous:result.setdefault('criterion_review_history',[]).append(copy.deepcopy(previous))
            receipt=dict(version=review.VERSION,review_id=uuid4().hex,analysis_id=analysis['analysis_id'],
                input_revision=analysis['input_revision'],source_text_id=source_id,
                reviewer=reviewer,reviewed_at=reviewed_at,conclusions=[merged[number] for number in sorted(merged)],
                submitted_criteria=[item['criterion_no'] for item in submitted])
            if source:
                receipt.update(source_summary_digest=review.digest(source.get('input_summary')),
                    source_text_digest=review.digest({key:source.get(key) for key in ('content','generated_text','prompt_version')}))
            receipt['context_digest']=review.context_digest({**analysis,**result,'currentness':'CURRENT'})
            result['criterion_review']=receipt
        ctx.edit_result(analysis['analysis_id'],update,invalidate_review=True,token=token)
        return ctx.analysis(analysis['analysis_id'])
