"""Read field provenance from the selected immutable snapshot, with legacy fallback.

Only display metadata is resolved here. No input values or judgments are changed.
"""
from ergo.intake.contract import SESSION_KEY,fields

SOURCE_NAMES={'AI':'작업 설명(AI 정리)','USER':'직접 입력','SAVED':'저장된 입력','POSE':'사진 자동 측정','MOVENET':'사진 자동 측정','VISION':'AI 사진 관찰'}

class InputTrace:
    def __init__(self,source):
        session=source.get('conditions',{}).get(SESSION_KEY) or {}
        current=source.get('input_revision')
        self.facts=session.get('facts',{}) if current is None or current==session.get('projected_revision') else {}
        self.catalogue={field['target']:field for field in fields()}
        self.primary_photo=next((slot.get('photo_id') for slot in (source.get('capture') or {}).get('slots',[]) if slot.get('analysis_target')),None)

    def lookup(self,kind,value,*,field=None,criterion=None,condition=None,scope=None,view=None,photo_id=None):
        for fact in self.facts.values():
            if fact.get('alias_of'):continue
            definition=self.catalogue.get(fact.get('target'))
            if not definition:continue
            destination=definition['destination']
            if destination['type']!=kind:continue
            if kind=='manual':
                from ergo.intake.photo_facts import photo_id as owner_of
                owner=owner_of(fact,{'LEFT':self.primary_photo})
                if owner!=(photo_id if photo_id is not None else self.primary_photo):continue
            if criterion is not None and criterion not in destination.get('criteria',[]):continue
            if condition is not None and fact['condition']!=condition:continue
            if scope is not None and destination.get('scope')!=scope:continue
            if view is not None and destination.get('view')!=view:continue
            key=destination.get('field')
            if kind=='criterion':
                mapping=destination['mapping'];key=mapping.get('exposure') or mapping.get('criterion') or mapping.get('lift') or mapping.get('row')
            if field is not None and field!=key:continue
            if fact['value']!=value and not (fact['value'] is None and value=='UNKNOWN'):continue
            label=SOURCE_NAMES.get(fact['source'],'저장된 입력')
            prefix='AI' if fact['source']=='AI' else label
            return label,f"{prefix}: {fact.get('quote','')}"
        return None
