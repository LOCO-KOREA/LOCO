"""LOCO 2.0 explanations service. Dependencies are supplied by Runtime."""
import os
from ergo.engine.task_defaults import now
from ergo.gpt import payload as gpt_payload
from ergo.gpt import client as gpt_client
from ergo.report import workbook as report

def prepare_explanation(ctx, p):
    """Capture the target before the IPC loop can accept deletion requests."""
    with ctx.db_lock:
        a = ctx.analysis(p['analysis_id'])
        currentness = report.currentness(ctx.require('task', a['task_id']), a)
        return a, ctx.analysis_token(a['analysis_id']), currentness


def handle_generate_ai_text(ctx, method, p, *, prepared=None):
    a, token, currentness = prepared if prepared is not None else prepare_explanation(ctx, p)
    purpose = p.get('purpose') or next((x.get('purpose') for x in a['ai'] if x.get('text_id') == p.get('text_id')), None) or 'TASK_EXPLANATION'
    if method == 'generate_ai_text':
        saved_settings = ctx.settings()
        provisional = gpt_payload.normalize_provisional_reba_input(a, p.get('provisional_reba'))
        summary = gpt_payload.build_numeric_summary(a, purpose, provisional_reba=provisional, analysis_currentness=currentness)
        result = 'DISABLED'
        content = None
        reason = None
        if saved_settings['gpt_enabled']:
            content, reason = gpt_client.generate(summary, saved_settings.get('gpt_model'), os.environ.get('OPENAI_API_KEY'), saved_settings)
            result = 'GENERATED' if content else 'FALLBACK'
        generated = gpt_client.content_text(content) if content else gpt_client.fallback_text(summary)
        ai = dict(text_id=__import__('uuid').uuid4().hex, is_active=False, purpose=purpose, result=result, generated_text=generated, edited_text=None, applied_text=None, applied_kind=None, content=content, input_summary=summary, model=saved_settings.get('gpt_model', ''), prompt_version=gpt_client.PROMPT_VERSION, created_at=now(), edited_at=None, applied_at=None, fallback_reason=reason)
        if provisional is not None: ai['provisional_reba_input'] = provisional
        ai['reasoning_effort']=saved_settings['gpt_reasoning_effort']
        ai['connection']=content.pop('_connection',None) if content else None
        with ctx.db_lock:
            ctx.edit_result(a['analysis_id'], lambda result: result.setdefault('ai', []).append(ai), token=token)
            latest=ctx.analysis(a['analysis_id'])
            latest_currentness=report.currentness(ctx.require('task', latest['task_id']), latest)
            current=gpt_payload.build_numeric_summary(latest, purpose, provisional_reba=provisional, analysis_currentness=latest_currentness)
            return dict(text=ai, source_current=latest_currentness=='CURRENT' and current==summary)
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
            currentness=report.currentness(ctx.require('task', saved['task_id']), saved)
            current=gpt_payload.build_numeric_summary(saved, ai['purpose'], provisional_reba=ai.get('provisional_reba_input'), analysis_currentness=currentness)
            return dict(text=ai, source_current=currentness=='CURRENT' and current==ai.get('input_summary'),confirmation_current=ai.get('confirmation_current',False))
