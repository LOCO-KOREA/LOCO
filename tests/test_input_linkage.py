"""Adversarial ownership tests for same-operation input-to-photo links."""
import copy
import json
import unittest

from backend.intake import contract, facts
from backend.intake.input_links import synchronize


MASS='card.lift.load_mass_kg'
CONDITION='상자 1개당 20kg'
TEXT=('상자를 양손으로 들어 가까운 위치로 옮기는 작업입니다. '
      '사진 3장은 같은 작업을 정면과 서로 반대쪽 측면에서 촬영한 모습입니다. '
      '상자를 몸 앞에 잡고 있습니다. 테스트 조건은 상자 1개당 20kg입니다.')


def answer(target,value,condition='default'):
    return dict(target=target,value=value,condition=condition)


def scope(views):
    signature=json.dumps([[view,identity,f'hash-{identity}',f'identity-{identity}']
                          for view,identity in sorted(views.items())],ensure_ascii=False)
    return dict(photo_signature=signature,views=[dict(view=view,photo_id=identity)
                                               for view,identity in views.items()])


def add_message(session,message_id,text,*,source_scope=None):
    session['messages'].append(dict(message_id=message_id,text=text,answers=[]))
    session['turns'].append(dict(turn_id='turn-'+message_id,message_id=message_id,
        requests=[dict(phase='EXTRACT_AND_PLAN',context=dict(texts=[],message_ids=[],
            source_photo_scope=copy.deepcopy(source_scope or scope(session['views']))))]))


def session():
    saved=facts.apply_answers({},[answer('load','MEASURED'),answer(MASS,20,CONDITION)])
    saved[contract.key(MASS,CONDITION)].update(source='AI',quote='상자 1개당 20kg',updated_at='2026-10-27T01:34:33+00:00')
    saved[contract.key('load')].update(source='AI',quote='상자를 몸 앞에 잡고 있습니다.',updated_at='2026-10-27T01:34:33+00:00')
    views=dict(LEFT=9,FRONT=10,RIGHT=11)
    value=dict(facts=saved,views=views,photo_signature=scope(views)['photo_signature'],messages=[],turns=[])
    add_message(value,'m1',TEXT)
    return value


class SameOperationInputLinks(unittest.TestCase):
    def test_the_reported_same_operation_weight_is_linked_without_an_extra_answer(self):
        source=session();before=copy.deepcopy(source)
        linked=synchronize(source)
        kg=linked[contract.key('load_kg')]
        self.assertEqual((kg['value'],kg['state'],kg['source'],kg['origin']),(20,'KNOWN','AI','INPUT_LINK'))
        proof=kg['input_link']
        self.assertEqual(proof['source_identity'],contract.key(MASS,CONDITION))
        self.assertEqual(proof['source_condition'],CONDITION)
        self.assertEqual(proof['source_value'],20)
        self.assertEqual(proof['source_message_id'],'m1')
        self.assertEqual(proof['photo_signature'],source['photo_signature'])
        self.assertEqual(set(proof['photo_ids']),{9,10,11})
        self.assertIn(proof['relation_quote'],TEXT)
        self.assertIn('같은 작업',proof['relation_quote'])
        self.assertEqual(source,before,'linking must not mutate the source session or an analysis snapshot')
        self.assertNotIn(contract.key('load_link'),linked,'the link is derived from the original statement, not a fabricated user answer')

    def test_repeated_sync_is_idempotent_and_preserves_all_actual_facts(self):
        source=session();first=synchronize(source)
        source['facts']=copy.deepcopy(first)
        second=synchronize(source)
        self.assertEqual(first,second)
        for identity,item in session()['facts'].items():
            self.assertEqual(second[identity],item)

    def test_two_conditions_are_not_one_object_even_when_the_numbers_match(self):
        source=session()
        extra=facts.apply_answers({},[answer(MASS,20,'다른 물건')])
        source['facts'].update(extra)
        self.assertNotIn(contract.key('load_kg'),synchronize(source))

    def test_distinct_or_unresolved_mass_conditions_do_not_select_a_maximum(self):
        for number in (None,30):
            with self.subTest(number=number):
                source=session()
                source['facts'].update(facts.apply_answers({},[answer(MASS,number,'다른 작업')]))
                self.assertNotIn(contract.key('load_kg'),synchronize(source))

    def test_explicit_photo_inputs_and_refusals_take_priority(self):
        for target,value in [('load','UNLOADED'),('load',None),('load_kg',None),
                             ('load_kg',0),('load_kg',30),('load_link','NO'),('load_link',None)]:
            with self.subTest(target=target,value=value):
                source=session()
                source['facts']=facts.apply_answers(source['facts'],[answer(target,value)])
                before=copy.deepcopy(source)
                linked=synchronize(source)
                self.assertEqual(linked,source['facts'])
                self.assertEqual(source,before)

    def test_an_existing_ai_photo_weight_is_not_replaced_by_a_work_weight(self):
        source=session()
        kg=facts.apply_answers({},[answer('load_kg',7)])[contract.key('load_kg')]
        kg.update(source='AI',quote='사진 속 물건은 7kg입니다.')
        source['facts'][contract.key('load_kg')]=kg
        self.assertEqual(synchronize(source)[contract.key('load_kg')],kg)

    def test_grounding_and_relationship_must_come_from_the_actual_scoped_message(self):
        for fault in ('missing_quote','wrong_number','no_relation','no_views','no_scope','wrong_scope'):
            with self.subTest(fault=fault):
                source=session()
                if fault=='missing_quote':source['facts'][contract.key(MASS,CONDITION)]['quote']='문장에 없는 중량'
                elif fault=='wrong_number':source['facts'][contract.key(MASS,CONDITION)]['value']=30
                elif fault=='no_relation':source['messages'][0]['text']='상자를 몸 앞에 잡고 있습니다. 상자 1개당 20kg입니다.'
                elif fault=='no_views':source['views']={}
                elif fault=='no_scope':source['turns'][0]['requests']=[]
                else:source['turns'][0]['requests'][0]['context']['source_photo_scope']=scope(dict(LEFT=99))
                self.assertNotIn(contract.key('load_kg'),synchronize(source))

    def test_only_derived_values_are_invalidated_on_photo_replacement(self):
        source=session();source['facts']=synchronize(source)
        self.assertEqual(source['facts'][contract.key('load_kg')]['value'],20)
        source['views']=dict(LEFT=99,RIGHT=100)
        source['photo_signature']=scope(source['views'])['photo_signature']
        linked=synchronize(source)
        self.assertNotIn(contract.key('load_kg'),linked,'the old same-work statement must not bind different photos')
        self.assertEqual(linked[contract.key(MASS,CONDITION)],source['facts'][contract.key(MASS,CONDITION)])
        self.assertEqual(linked[contract.key('load')],source['facts'][contract.key('load')])

    def test_a_changed_source_rederives_from_its_new_scoped_statement(self):
        source=session();source['facts']=synchronize(source)
        item=source['facts'][contract.key(MASS,CONDITION)]
        item.update(value=30,quote='상자 1개당 30kg',updated_at='2026-10-27T02:00:00+00:00')
        add_message(source,'m2','사진은 같은 작업을 촬영한 모습입니다. 상자 1개당 30kg입니다.')
        linked=synchronize(source)
        self.assertEqual(linked[contract.key('load_kg')]['value'],30)
        self.assertEqual(linked[contract.key('load_kg')]['input_link']['source_value'],30)
        self.assertEqual(linked[contract.key('load_kg')]['input_link']['source_message_id'],'m2')

    def test_conflicting_source_is_not_promoted_to_a_photo_measurement(self):
        source=session()
        source['facts'][contract.key(MASS,CONDITION)].update(state='CONFLICT',conflict=dict(value=30))
        self.assertNotIn(contract.key('load_kg'),synchronize(source))

    def test_direct_user_mass_uses_the_scoped_answer_without_a_numeric_text_quote(self):
        source=session()
        source['facts']=facts.apply_answers(source['facts'],[
            answer('context','YES'),answer(MASS,20,CONDITION)])
        source['messages']=[dict(message_id='direct',text='',answers=[answer(MASS,20,CONDITION)],
                                 source_photo_scope=scope(source['views']))]
        source['turns']=[]
        self.assertEqual(source['facts'][contract.key(MASS,CONDITION)]['quote'],'직접 입력')
        before=copy.deepcopy(source)
        linked=synchronize(source)
        self.assertEqual(linked[contract.key('load_kg')]['value'],20)
        self.assertEqual(linked[contract.key('load_kg')]['input_link']['source_message_id'],'direct')
        self.assertEqual(source,before)

    def test_advanced_user_mass_links_without_inventing_a_message_or_changing_a_snapshot(self):
        source=session()
        source['facts']=facts.apply_answers(source['facts'],[
            answer('context','YES'),answer(MASS,20,CONDITION)])
        source['messages']=[];source['turns']=[]
        old_snapshot=dict(conditions=dict(intake_session=source))
        before=copy.deepcopy(old_snapshot)
        linked=synchronize(source)
        kg=linked[contract.key('load_kg')]
        self.assertEqual(kg['value'],20)
        self.assertIsNone(kg['input_link']['source_message_id'],'advanced form input must not fabricate an original text message')
        self.assertEqual(kg['input_link']['source_identity'],contract.key(MASS,CONDITION))
        self.assertEqual(old_snapshot,before,'propagating an actual input must not rewrite an old analysis snapshot')
        saved=copy.deepcopy(source)
        saved['facts'][contract.key(MASS,CONDITION)]['source']='SAVED'
        self.assertEqual(synchronize(saved)[contract.key('load_kg')]['value'],20,'a persisted direct input is still an actual work weight')
        invalidated=copy.deepcopy(source)
        invalidated['facts'][contract.key('context')]['reask']=True
        self.assertNotIn(contract.key('load_kg'),synchronize(invalidated),'a stale photo confirmation cannot bind an advanced input')

    def test_confirmed_photo_context_does_not_override_an_explicit_different_work_statement(self):
        for statement in ('사진은 다른 작업을 촬영한 모습입니다.',
                          '사진은 같은 작업이 아닙니다.',
                          '사진은 같은 작업을 찍은 게 아닙니다.',
                          'These photos are not the same task.',
                          'These photos do not show the same task.'):
            with self.subTest(statement=statement):
                source=session()
                source['facts']=facts.apply_answers(source['facts'],[answer('context','YES')])
                source['messages'][0]['text']=statement+' 상자 1개당 20kg입니다.'
                self.assertNotIn(contract.key('load_kg'),synchronize(source),
                    'normal-work/full-frame confirmation is not proof that a different operation has this photo load')

    def test_saying_no_other_work_does_not_negate_the_same_work_relation(self):
        for statement in ('사진은 같은 작업이며 다른 작업은 없어요.',
                          '사진은 같은 작업이며 다른 작업은 아닙니다.'):
            with self.subTest(statement=statement):
                source=session()
                source['messages'][0]['text']=statement+' 상자 1개당 20kg입니다.'
                linked=synchronize(source)
                self.assertEqual(linked[contract.key('load_kg')]['value'],20,
                                 'a negated different-work clause must not discard an affirmative same-work relation')

    def test_later_explicit_relation_refusal_invalidates_only_the_derived_link(self):
        source=session();source['facts']=synchronize(source)
        source['facts']=facts.apply_answers(source['facts'],[answer('load_link','NO')])
        linked=synchronize(source)
        self.assertNotIn(contract.key('load_kg'),linked)
        self.assertEqual(linked[contract.key('load_link')]['value'],'NO')
        self.assertEqual(linked[contract.key(MASS,CONDITION)]['value'],20)

    def test_a_later_scoped_different_work_statement_does_not_reuse_the_old_affirmation(self):
        source=session();source['facts']=synchronize(source)
        add_message(source,'different','사진은 설명한 것과 다른 작업입니다.')
        self.assertNotIn(contract.key('load_kg'),synchronize(source),
                         'the earlier same-work statement cannot win over its later explicit correction')

    def test_a_decimal_mass_does_not_split_the_explicit_same_work_sentence(self):
        source=session()
        source['facts'].pop(contract.key(MASS,CONDITION))
        source['facts'].update(facts.apply_answers({},[answer(MASS,20.5,'상자')]))
        source['facts'][contract.key(MASS,'상자')].update(source='AI',quote='20.5kg 상자')
        source['messages'][0]['text']='사진은 20.5kg 상자를 다루는 동일한 작업입니다.'
        self.assertEqual(synchronize(source)[contract.key('load_kg')]['value'],20.5)


if __name__=='__main__':
    unittest.main()
