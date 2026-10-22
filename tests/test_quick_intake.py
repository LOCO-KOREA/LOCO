"""One typed sentence about the work fills the question cards, but only with what the sentence really says."""
import unittest

from ergo.engine import quick_assess, quick_intake


def answer(target, number=None, text=None, quote=''):
    return {'target': target, 'number': number, 'text': text, 'quote': quote}


class Catalogue(unittest.TestCase):
    def setUp(self):
        self.catalogue = quick_intake.catalogue()
        self.by_target = {c['target']: c for c in self.catalogue}

    def test_targets_are_unique_and_cover_work_types_card_fields_and_a_few_work_facts(self):
        self.assertEqual(len(self.by_target), len(self.catalogue))
        questions = quick_assess.questions({}, [], {})
        work_types = {i['key'] for i in next(q for q in questions if q['id'] == 'work_types')['items']}
        self.assertEqual({c['gate'] for c in self.catalogue if c['kind'] == 'tick'}, work_types)
        for card in (q for q in questions if q['kind'] == 'criterion'):
            for field in card['fields']:
                self.assertIn(f"card.{card['gate']}.{field['key']}", self.by_target)
        for target in ('daily_work_min', 'annual_work_days', 'one_off', 'task_name'):
            self.assertIn(target, self.by_target)

    def test_what_a_sentence_cannot_settle_is_never_offered(self):
        # Photo angles, the load at the photo moment, who investigated and the survey follow-ups stay with the person or the photo.
        for target in self.by_target:
            self.assertNotRegex(target, r'trunk_base|knee_band|upper_arm|lower_arm|neck_base|wrist|^load|investigator|participation|symptom|situation|coupling')

    def test_every_target_names_its_question_and_has_a_plain_meaning(self):
        known = {q['id'] for q in quick_assess.questions({}, [], {})}
        for c in self.catalogue:
            self.assertIn(c['question_id'], known)
            self.assertTrue(c['label'])
            self.assertNotRegex(c['label'], r'\d+호', 'criterion numbers are never shown')

    def test_schema_is_strict_and_only_allows_catalogue_targets(self):
        schema = quick_intake.schema(self.catalogue)
        item = schema['properties']['answers']['items']
        self.assertFalse(schema['additionalProperties'])
        self.assertFalse(item['additionalProperties'])
        self.assertEqual(set(item['required']), set(item['properties']))
        self.assertEqual(set(item['properties']['target']['enum']), set(self.by_target))


class Validate(unittest.TestCase):
    TEXT = '20kg 상자를 바닥에서 들어 선반에 하루 30번쯤 옮기고, 오후엔 두 시간 키보드를 쳐요.'

    def check(self, answers, text=None):
        return quick_intake.validate(answers, text or self.TEXT)

    def test_numbers_with_their_own_words_in_the_text_are_accepted(self):
        items, dropped = self.check([answer('card.lift.load_mass_kg', 20, quote='20kg'), answer('card.lift.lift_count_day', 30, quote='하루 30번'),
                                     answer('card.keyboard.C1_KEYBOARD_FOCUSED', 120, quote='두 시간 키보드')])
        values = {i['target']: i['value'] for i in items}
        self.assertEqual(values['card.lift.load_mass_kg'], 20)
        self.assertEqual(values['card.lift.lift_count_day'], 30)
        self.assertEqual(values['card.keyboard.C1_KEYBOARD_FOCUSED'], 120, 'Korean number words count as evidence too')
        self.assertEqual(dropped, [])

    def test_a_follow_up_value_also_ticks_its_work_type(self):
        items, _ = self.check([answer('card.lift.load_mass_kg', 20, quote='20kg')])
        tick = next(i for i in items if i['target'] == 'work_type.lift')
        self.assertTrue(tick['value'])
        self.assertTrue(tick['inferred'])
        self.assertEqual(tick['quote'], '20kg')

    def test_a_yes_no_answer_only_counts_when_its_work_type_is_in_the_sentence(self):
        # "지지대 없이" must not tick the waist/neck work type by itself.
        items, dropped = self.check([answer('card.trunk_neck.unsupported', text='YES', quote='바닥에서')])
        self.assertEqual(items, [])
        self.assertEqual(dropped[0]['reason'], 'GATE_NOT_TICKED')
        items, dropped = self.check([answer('work_type.trunk_neck', quote='바닥에서 들어'), answer('card.trunk_neck.unsupported', text='YES', quote='선반에')])
        self.assertEqual({i['target']: i['value'] for i in items}, {'work_type.trunk_neck': True, 'card.trunk_neck.unsupported': 'YES'})
        self.assertEqual(dropped, [])
        items, _ = self.check([answer('card.trunk_neck.C4_TRUNK_FLEX', 30, quote='하루 30번'), answer('card.trunk_neck.unsupported', text='NO', quote='선반에')])
        self.assertIn('card.trunk_neck.unsupported', {i['target'] for i in items}, 'a number for the same work type does tick it')

    def test_a_quote_that_is_not_in_the_text_is_dropped(self):
        items, dropped = self.check([answer('card.lift.load_mass_kg', 25, quote='25kg 상자')])
        self.assertEqual(items, [])
        self.assertEqual(dropped[0]['reason'], 'QUOTE_NOT_IN_TEXT')

    def test_spacing_differences_in_the_quote_do_not_matter(self):
        items, _ = self.check([answer('card.lift.lift_count_day', 30, quote='하루30번')])
        self.assertEqual([i for i in items if i['target'] == 'card.lift.lift_count_day'][0]['value'], 30)

    def test_numbers_without_numeric_evidence_or_out_of_range_are_dropped(self):
        text = '하루 종일 키보드를 쳐요'
        items, dropped = self.check([answer('card.keyboard.C1_KEYBOARD_FOCUSED', 480, quote='하루 종일 키보드')], text)
        self.assertEqual((items, dropped[0]['reason']), ([], 'NO_NUMERIC_EVIDENCE'), 'the model must not invent "all day = 480"')
        items, dropped = self.check([answer('daily_work_min', 2000, quote='20kg')])
        self.assertEqual((items, dropped[0]['reason']), ([], 'OUT_OF_RANGE'))
        items, dropped = self.check([answer('daily_work_min', -5, quote='20kg')])
        self.assertEqual(dropped[0]['reason'], 'OUT_OF_RANGE')
        items, dropped = self.check([answer('daily_work_min', True, quote='20kg')])
        self.assertEqual(dropped[0]['reason'], 'BAD_VALUE')

    def test_unknown_targets_duplicates_and_bad_choices_are_dropped(self):
        items, dropped = self.check([answer('trunk_base', 3, quote='20kg'), answer('daily_work_min', 240, quote='두 시간'), answer('daily_work_min', 480, quote='20kg'),
                                     answer('one_off', text='MAYBE', quote='20kg')])
        self.assertEqual([i['target'] for i in items], ['daily_work_min'])
        self.assertEqual(items[0]['value'], 240, 'the first answer for a card wins')
        self.assertEqual({d['reason'] for d in dropped}, {'UNKNOWN_TARGET', 'DUPLICATE', 'BAD_VALUE'})

    def test_choices_and_names_come_through_when_valid(self):
        items, _ = self.check([answer('one_off', text='NO', quote='하루 30번'), answer('task_name', text='상자 옮기기', quote='상자를 바닥에서 들어 선반에')])
        got = {i['target']: i['value'] for i in items}
        self.assertEqual(got, {'one_off': 'NO', 'task_name': '상자 옮기기'})

    def test_items_follow_the_catalogue_order_and_carry_what_the_screen_needs(self):
        items, _ = self.check([answer('card.lift.lift_count_day', 30, quote='하루 30번'), answer('work_type.keyboard', quote='키보드를 쳐요')])
        self.assertEqual([i['target'] for i in items], [c['target'] for c in quick_intake.catalogue() if c['target'] in {i['target'] for i in items}])
        one = items[-1]
        for key in ('target', 'kind', 'question_id', 'field_key', 'gate', 'value', 'quote', 'label', 'unit'):
            self.assertIn(key, one)

    def test_garbage_from_the_model_never_raises(self):
        for raw in (None, 'text', [None], [{}], [{'target': 5}], [{'target': 'daily_work_min', 'number': 'abc', 'quote': 7}]):
            items, dropped = quick_intake.validate(raw, self.TEXT)
            self.assertEqual(items, [])


if __name__ == '__main__':
    unittest.main()


class ServiceIntake(unittest.TestCase):
    """quick_interpret through the real dispatch, with the model call replaced by a fake."""

    def setUp(self):
        import os, tempfile
        from ergo.service.application import create_service
        self.ctx = create_service(os.path.join(tempfile.mkdtemp(), 'intake.db'))

    def enable(self, enabled=True, model='gpt-test'):
        settings = self.ctx.dispatch('get_settings', {})
        settings.pop('gpt_key_present', None)
        settings.update(gpt_enabled=enabled, gpt_model=model)
        self.ctx.dispatch('update_settings', {'settings': settings})

    def test_request_shape_is_checked(self):
        from ergo.contracts import validate_request
        validate_request('quick_interpret', {'text': '하루 4시간 키보드를 쳐요'})
        for bad in ({}, {'text': ''}, {'text': '   '}, {'text': 5}, {'text': 'x' * 601}, {'text': '문장', 'extra': 1}):
            with self.assertRaises(ValueError):
                validate_request('quick_interpret', bad)

    def test_disabled_ai_or_missing_key_returns_a_reason_and_nothing_to_fill(self):
        import os
        from unittest import mock
        self.enable(False)
        self.assertEqual(self.ctx.dispatch('quick_interpret', {'text': '하루 4시간 키보드를 쳐요'}), dict(items=[], dropped=[], reason='DISABLED'))
        self.enable(True)
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop('OPENAI_API_KEY', None)
            self.assertEqual(self.ctx.dispatch('quick_interpret', {'text': '하루 4시간 키보드를 쳐요'})['reason'], 'NO_API_KEY')

    def test_only_what_the_sentence_supports_comes_back(self):
        from unittest import mock
        self.enable()
        text = '20kg 상자를 하루 30번 들고 오후엔 4시간 키보드를 쳐요'
        fake = [answer('card.lift.load_mass_kg', 20, quote='20kg'), answer('card.lift.lift_count_day', 30, quote='하루 30번'),
                answer('card.keyboard.C1_KEYBOARD_FOCUSED', 240, quote='4시간 키보드'), answer('card.keyboard.C1_KEYBOARD_FOCUSED', 999, quote='4시간'),
                answer('annual_work_days', 220, quote='연 220일')]
        with mock.patch('ergo.gpt.client.interpret', return_value=(fake, None)) as call:
            result = self.ctx.dispatch('quick_interpret', {'text': text})
        sent_text, targets, schema_, model, _key, selected_settings = call.call_args.args
        self.assertEqual(selected_settings['gpt_model'], model)
        self.assertEqual((sent_text, model), (text, 'gpt-test'))
        self.assertTrue(all(t['target'] for t in targets))
        self.assertEqual(schema_['required'], ['answers'])
        got = {i['target']: i['value'] for i in result['items']}
        self.assertEqual(got, {'work_type.keyboard': True, 'work_type.lift': True, 'card.keyboard.C1_KEYBOARD_FOCUSED': 240, 'card.lift.load_mass_kg': 20, 'card.lift.lift_count_day': 30})
        self.assertEqual({d['reason'] for d in result['dropped']}, {'DUPLICATE', 'QUOTE_NOT_IN_TEXT'})
        self.assertIsNone(result['reason'])

    def test_model_failure_or_nothing_usable_is_reported_not_raised(self):
        from unittest import mock
        self.enable()
        with mock.patch('ergo.gpt.client.interpret', return_value=(None, 'TIMEOUT')):
            self.assertEqual(self.ctx.dispatch('quick_interpret', {'text': '하루 4시간 키보드를 쳐요'})['reason'], 'TIMEOUT')
        with mock.patch('ergo.gpt.client.interpret', return_value=([], None)):
            self.assertEqual(self.ctx.dispatch('quick_interpret', {'text': '그냥 일해요'})['reason'], 'NOTHING_FOUND')

    def test_nothing_is_saved(self):
        from unittest import mock
        self.enable()
        before = self.ctx.dispatch('list_surveys', {})
        with mock.patch('ergo.gpt.client.interpret', return_value=([answer('daily_work_min', 240, quote='4시간')], None)):
            self.ctx.dispatch('quick_interpret', {'text': '하루 4시간 일해요'})
        self.assertEqual(self.ctx.dispatch('list_surveys', {}), before)
