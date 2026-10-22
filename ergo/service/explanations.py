"""LOCO 2.0 explanations service. Dependencies are supplied by Runtime."""
import os
from ergo.engine.task_defaults import now
from ergo.gpt import payload as gpt_payload
from ergo.gpt import client as gpt_client

def prepare_explanation(ctx, p):
    """Capture the target before the IPC loop can accept deletion requests."""
    with ctx.db_lock:
        a = ctx.analysis(p['analysis_id'])
        return a, ctx.analysis_token(a['analysis_id'])


def handle_generate_ai_text(ctx, method, p, *, prepared=None):
    a, token = prepared if prepared is not None else prepare_explanation(ctx, p)
    purpose = p.get('purpose') or next((x.get('purpose') for x in a['ai'] if x.get('text_id') == p.get('text_id')), None) or 'TASK_EXPLANATION'
    if method == 'generate_ai_text':
        saved_settings = ctx.settings()
        summary = gpt_payload.build_numeric_summary(a, purpose)
        result = 'DISABLED'
        content = None
        reason = None
        if saved_settings['gpt_enabled']:
            content, reason = gpt_client.generate(summary, saved_settings.get('gpt_model'), os.environ.get('OPENAI_API_KEY'), saved_settings)
            result = 'GENERATED' if content else 'FALLBACK'
        ai = dict(text_id=__import__('uuid').uuid4().hex, is_active=False, purpose=purpose, result=result, generated_text=gpt_client.content_text(content) if content else '수치 요약의 입력 누락과 추가 확인 항목을 검토하세요. 사진 표본 비율은 하루 노출시간이 아니며, 계산 결과와 조사자 결론은 별도로 확인해야 합니다.', edited_text=None, applied_text=None, applied_kind=None, content=content, input_summary=summary, model=saved_settings.get('gpt_model', ''), prompt_version=gpt_client.PROMPT_VERSION, created_at=now(), edited_at=None, applied_at=None, fallback_reason=reason)
        ai['reasoning_effort']=saved_settings['gpt_reasoning_effort']
        ai['connection']=content.pop('_connection',None) if content else None
        with ctx.db_lock:
            ctx.edit_result(a['analysis_id'], lambda result: result.setdefault('ai', []).append(ai), token=token)
            current = gpt_payload.build_numeric_summary(ctx.analysis(a['analysis_id']), purpose)
            return dict(text=ai, source_current=current == summary)
    else:

        def update(result):
            ai = next((x for x in result.get('ai', []) if x.get('text_id') == p.get('text_id')), None)
            if ai is None:
                raise LookupError('해당 설명 이력을 찾을 수 없습니다')
            if method == 'edit_ai_text':
                ai['edited_text'] = str(p['text'])
                ai['edited_at'] = now()
            else:
                target = p['use_edited']
                chosen = ai.get('edited_text') if target else ai.get('generated_text')
                if ai['result'] == 'DISABLED' or not chosen:
                    raise LookupError('비활성 또는 빈 설명은 적용할 수 없습니다')
                for old in result.get('ai', []):
                    if old.get('purpose') == ai['purpose']:
                        old['is_active'] = False
                ai.update(is_active=True, applied_text=chosen, applied_kind='INVESTIGATOR' if target else 'MODEL' if ai['result'] == 'GENERATED' else 'FALLBACK', applied_at=now())
        with ctx.db_lock:
            ctx.edit_result(a['analysis_id'], update, token=token)
            saved = ctx.analysis(a['analysis_id'])
            ai = next((x for x in saved['ai'] if x['text_id'] == p['text_id']))
            current = gpt_payload.build_numeric_summary(saved, ai['purpose'])
            return dict(text=ai, source_current=current == ai.get('input_summary'))
