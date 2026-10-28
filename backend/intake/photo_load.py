"""Resolve confirmed photo load without materializing aliases or changing ownership."""
from .contract import key


def photo_load(facts):
    def known(target):
        item = facts.get(key(target)) or {}
        return item.get('value') if item.get('state') == 'KNOWN' else None

    state, kg = known('load') or 'UNKNOWN', known('load_kg')
    masses = [f for f in facts.values() if f['target'] == 'card.lift.load_mass_kg']
    values = {f['value'] for f in masses if f['state'] == 'KNOWN'}
    # An explicit unknown/conflict or a different load state cannot be replaced
    # by a connection confirmed earlier. Distinct working conditions stay distinct.
    blocked = any((facts.get(key(t)) or {}).get('state') == 'CONFLICT'
                  or (facts.get(key(t)) or {}).get('state') == 'UNKNOWN'
                  and (facts.get(key(t)) or {}).get('source') == 'USER'
                  for t in ('load', 'load_kg'))
    if (known('load_link') == 'YES' and len(values) == 1 and not blocked
            and not any(f['state'] == 'CONFLICT' for f in masses)
            and state in ('UNKNOWN', 'MEASURED') and kg is None):
        state, kg = 'MEASURED', next(iter(values))
    if kg is not None and state == 'UNKNOWN' and key('load') not in facts:
        state = 'MEASURED'
    return state, kg if state == 'MEASURED' else None
