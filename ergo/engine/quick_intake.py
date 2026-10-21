"""One typed sentence about the work fills question cards, but only with what the sentence really says.

The model never decides anything. It copies facts from the sentence into named boxes (the catalogue), and every
copied value must come with the exact words it was copied from. Anything the sentence does not support is dropped,
so a made-up number can never reach the calculation. The person sees each value with its quote and can change it.
"""
import math
import re

from . import quick_assess

MAX_ITEMS = 60
DEFAULT_MAXIMUM = 1000
# A number only counts when the quoted words carry a number: digits or a Korean count word (두 시간, 한 시간 반, ...).
NUMERIC_EVIDENCE = re.compile(r'[0-9]|한|두|세|네|다섯|여섯|일곱|여덟|아홉|열|스무|반')
SIMPLE_TARGETS = (('daily_work_min', 'number'), ('annual_work_days', 'number'), ('one_off', 'choice'), ('task_name', 'text'))
NOT_ASKED = {'UNKNOWN'}


def catalogue():
    """Every box a sentence may fill: work types, the follow-up card fields, and a few facts about the work."""
    questions = quick_assess.questions({}, [], {})
    by_id = {q['id']: q for q in questions}
    boxes = []
    for item in by_id['work_types']['items']:
        boxes.append(dict(target=f"work_type.{item['key']}", kind='tick', question_id='work_types', field_key=None, gate=item['key'],
                          label=item['label'], unit=None, maximum=None, choices=None))
    for card in (q for q in questions if q['kind'] == 'criterion'):
        for field in card['fields']:
            truth = field['type'] == 'truth'
            boxes.append(dict(target=f"card.{card['gate']}.{field['key']}", kind='choice' if truth else 'number', question_id=card['id'],
                              field_key=field['key'], gate=card['gate'], label=f"{card['text']} - {field['label']}",
                              unit=field.get('unit') or None, maximum=None if truth else (field.get('maximum') or DEFAULT_MAXIMUM),
                              choices=['YES', 'NO'] if truth else None))
    for qid, kind in SIMPLE_TARGETS:
        q = by_id[qid]
        choices = [c['value'] for c in q.get('choices', []) if c['value'] not in NOT_ASKED] if kind == 'choice' else None
        boxes.append(dict(target=qid, kind=kind, question_id=qid, field_key=None, gate=None, label=q['text'], unit=q.get('unit') or None,
                          maximum=(q.get('maximum') or DEFAULT_MAXIMUM) if kind == 'number' else None, choices=choices,
                          maxlength=q.get('maxlength') if kind == 'text' else None))
    return boxes


def prompt_targets(boxes):
    """What the model is told about each box. No photo data, no question numbers."""
    out = []
    for box in boxes:
        row = {'target': box['target'], 'meaning': box['label'], 'kind': box['kind']}
        if box['unit']:
            row['unit'] = box['unit']
        if box['maximum']:
            row['max'] = box['maximum']
        if box['choices']:
            row['choices'] = box['choices']
        out.append(row)
    return out


def schema(boxes):
    """Strict structured-output schema: a list of {target, number, text, quote}."""
    item = {'type': 'object', 'additionalProperties': False, 'required': ['target', 'number', 'text', 'quote'],
            'properties': {'target': {'type': 'string', 'enum': [b['target'] for b in boxes]},
                           'number': {'type': ['number', 'null']}, 'text': {'type': ['string', 'null']}, 'quote': {'type': 'string'}}}
    return {'type': 'object', 'additionalProperties': False, 'required': ['answers'],
            'properties': {'answers': {'type': 'array', 'maxItems': MAX_ITEMS, 'items': item}}}


def _squash(value):
    return re.sub(r'\s+', '', value)


def _value(box, raw):
    """(value, None) or (None, reason) for one answer against its box."""
    kind = box['kind']
    if kind == 'tick':
        return True, None
    if kind == 'number':
        number = raw.get('number')
        if isinstance(number, bool) or not isinstance(number, (int, float)) or not math.isfinite(number):
            return None, 'BAD_VALUE'
        if number < 0 or number > box['maximum']:
            return None, 'OUT_OF_RANGE'
        return number, None
    text = raw.get('text')
    if not isinstance(text, str):
        return None, 'BAD_VALUE'
    text = text.strip()
    if kind == 'choice':
        return (text, None) if text in box['choices'] else (None, 'BAD_VALUE')
    if not text or len(text) > (box.get('maxlength') or 40):
        return None, 'BAD_VALUE'
    return text, None


def validate(raw_answers, text):
    """Keep only answers the sentence supports. Returns (items in catalogue order, dropped [{target, reason}])."""
    boxes = {b['target']: b for b in catalogue()}
    order = list(boxes)
    squashed = _squash(text if isinstance(text, str) else '')
    accepted, dropped = {}, []
    for raw in raw_answers if isinstance(raw_answers, list) else []:
        name = raw.get('target') if isinstance(raw, dict) else None
        if not isinstance(name, str) or name not in boxes:
            dropped.append({'target': name if isinstance(name, str) else None, 'reason': 'UNKNOWN_TARGET'})
            continue
        target, box, quote = raw['target'], boxes[raw['target']], raw.get('quote')
        if target in accepted:
            dropped.append({'target': target, 'reason': 'DUPLICATE'})
            continue
        if not isinstance(quote, str) or len(_squash(quote)) < 2:
            dropped.append({'target': target, 'reason': 'BAD_VALUE'})
            continue
        if _squash(quote) not in squashed:
            dropped.append({'target': target, 'reason': 'QUOTE_NOT_IN_TEXT'})
            continue
        value, reason = _value(box, raw)
        if reason:
            dropped.append({'target': target, 'reason': reason})
            continue
        if box['kind'] == 'number' and not NUMERIC_EVIDENCE.search(quote):
            dropped.append({'target': target, 'reason': 'NO_NUMERIC_EVIDENCE'})
            continue
        accepted[target] = dict(box, value=value, quote=quote.strip(), inferred=False)
    # A time, count or weight given for a follow-up card means the person does that kind of work: tick it, quoting the same words.
    # A yes/no answer alone does not ("지지대 없이" says nothing about bending), so it needs its work type from the sentence.
    for item in list(accepted.values()):
        tick = f"work_type.{item['gate']}" if item['gate'] and item['kind'] == 'number' else None
        if tick and tick not in accepted:
            accepted[tick] = dict(boxes[tick], value=True, quote=item['quote'], inferred=True)
    ticked = {item['gate'] for item in accepted.values() if item['kind'] == 'tick'}
    for target, item in list(accepted.items()):
        if item['kind'] == 'choice' and item['gate'] and item['gate'] not in ticked:
            dropped.append({'target': target, 'reason': 'GATE_NOT_TICKED'})
            del accepted[target]
    return [accepted[target] for target in order if target in accepted], dropped
