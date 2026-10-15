"""Contract boundaries for the schema 2.0 application."""
import unittest

from ergo.engine.movenet import NAMES
from ergo.engine.task_defaults import EXPOSURE_V2, legal_inputs, task_input
from ergo.gpt.payload import explanation_schema
from ergo.service.application import validate_task_input_shape


class V2ContractBoundaries(unittest.TestCase):
    def test_movenet_keypoint_order_has_seventeen_unique_points(self):
        self.assertEqual(len(NAMES), 17)
        self.assertEqual(len(set(NAMES)), 17)

    def test_exposure_contract_has_fifteen_unique_daily_inputs(self):
        self.assertEqual(len(EXPOSURE_V2), 15)
        self.assertEqual(len(set(EXPOSURE_V2)), 15)
        self.assertEqual(len(legal_inputs()['criteria']), 11)

    def test_task_boundary_rejects_duplicate_criterion_and_exposure_codes(self):
        value = task_input({})
        value['legal']['criteria'][1]['criterion_no'] = 1
        with self.assertRaises(ValueError):
            validate_task_input_shape(value)
        value = task_input({})
        value['legal']['exposures'][1]['condition_code'] = value['legal']['exposures'][0]['condition_code']
        with self.assertRaises(ValueError):
            validate_task_input_shape(value)

    def test_gpt_schema_disallows_unlisted_fields(self):
        schema = explanation_schema()
        self.assertIs(schema['additionalProperties'], False)
        self.assertIs(schema['properties']['criteria']['items']['additionalProperties'], False)
        self.assertEqual(set(schema['required']), {'summary', 'criteria', 'check_items', 'improvement_options'})


if __name__ == '__main__':
    unittest.main()
