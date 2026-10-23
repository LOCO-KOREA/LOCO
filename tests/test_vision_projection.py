"""Visual fallback provenance, removal and later measurement priority."""
import copy
import unittest

from ergo.engine.task_defaults import task_input
from ergo.intake import contract, facts, photo_facts
from tests.test_photo_fact_ownership import observation, preview


class VisionProjection(unittest.TestCase):
    def visual(self, target, value):
        field = next(f for f in contract.fields() if f['target'] == target)
        condition = photo_facts.condition(101) if target.startswith('manual.') else 'default'
        item = facts.fact(field, value, 'VISION', '몸의 모습이 분명히 보여요.', condition)
        item.update(photo_id=101, view='LEFT', vision_signature='original-image-signature',
                    vision_observation='activity', vision_proof=dict(value=value))
        return item

    def test_visual_inputs_have_automatic_source_and_owned_proof(self):
        item = self.visual('manual.COMMON.seated', 'YES')
        saved = {contract.key(item['target'], item['condition']): item}
        task = facts.project(task_input({}), saved, dict(LEFT=101), preview([], dict(LEFT=101)))
        row = task['manual'][0]
        self.assertEqual(row['source'], 'AUTO_ACCEPTED')
        self.assertEqual(row['evidence']['source'], 'OTHER')
        self.assertIn('original-image-signature', row['evidence']['text'])
        self.assertNotIn('angles', row['evidence']['text'])

    def test_removed_visual_facts_cannot_leave_calculator_values_behind(self):
        saved = {}
        for target in ('manual.COMMON.seated', 'work_type.knee'):
            item = self.visual(target, 'YES')
            saved[contract.key(target, item['condition'])] = item
        views = dict(LEFT=101); data = preview([], views)
        task = facts.project(task_input({}), saved, views, data)
        task['conditions'][contract.SESSION_KEY] = dict(facts=copy.deepcopy(saved))
        self.assertEqual(task['legal']['criteria'][4]['condition_present'], 'YES')
        cleared = facts.project(task, {}, views, data)
        self.assertEqual(cleared['legal']['criteria'][4]['condition_present'], 'UNKNOWN')
        self.assertFalse(cleared['manual'])
        self.assertEqual(task['legal']['criteria'][4]['condition_present'], 'YES')

    def test_same_value_person_edit_is_never_erased_as_a_visual_projection(self):
        item = self.visual('manual.COMMON.seated', 'YES')
        saved = {contract.key(item['target'], item['condition']): item}
        views = dict(LEFT=101); data = preview([], views)
        task = facts.project(task_input({}), saved, views, data)
        task['conditions'][contract.SESSION_KEY] = dict(facts=saved)
        task['manual'][0].update(source='INTERVIEW', evidence=dict(source='INTERVIEW', text='사람이 따로 확인', observed_at=None))
        self.assertEqual(facts.project(task, {}, views, data)['manual'][0], task['manual'][0])

    def test_reliable_measurement_replaces_fallback_but_uncertainty_does_not(self):
        for low_confidence, boundary in ((False, False), (True, False), (False, True)):
            with self.subTest(low_confidence=low_confidence, boundary=boundary):
                item = self.visual('manual.COMMON.trunk_base', 2)
                saved = {contract.key(item['target'], item['condition']): item}
                row = observation('LEFT', 'COMMON', 'trunk_base', 3, 40)
                row.update(low_confidence=low_confidence, boundary_review=boundary)
                actual = facts.add_photo_facts(saved, preview([row], dict(LEFT=101)), dict(LEFT=101))
                fact = actual[contract.key(item['target'], item['condition'])]
                self.assertEqual(fact['source'], 'VISION' if low_confidence or boundary else 'POSE')
                self.assertEqual(fact['value'], 2 if low_confidence or boundary else 3)


if __name__ == '__main__':
    unittest.main()
