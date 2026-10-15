"""Adversarial checks for the general-task 2.0 burden rule engine."""
import copy
import unittest

from ergo.engine.burden_rules import calculate_v2
from ergo.engine.task_defaults import legal_inputs


def baseline():
    legal = legal_inputs()
    for item in legal['exposures']:
        item['minutes'] = 0
    for item in legal['criteria']:
        item['condition_present'] = 'NO'
        if item['criterion_no'] >= 6:
            item['rows_complete'] = 'YES'
    return {'one_off': 'NO', 'planned_duration_months': 12,
            'annual_work_days': 220, 'daily_work_min': 480}, legal


def judgment(conditions, legal, number):
    return calculate_v2(conditions, legal)['judgments'][number - 1]


def qualifying_case(number):
    conditions, legal = baseline()
    criterion = legal['criteria'][number - 1]
    criterion['condition_present'] = 'YES'
    exposures = {row['condition_code']: row for row in legal['exposures']}
    if number == 1:
        exposures['C1_KEYBOARD_FOCUSED']['minutes'] = 240
    elif number == 2:
        exposures['C2_WRIST']['minutes'] = 120
    elif number == 3:
        exposures['C3_UNION']['minutes'] = 120
    elif number == 4:
        criterion.update(unsupported='YES', posture_restricted='NO')
        exposures['C4_NECK_FLEX']['minutes'] = 120
        exposures['C4_UNION']['minutes'] = 120
    elif number == 5:
        exposures['C5_SQUAT']['minutes'] = 120
        exposures['C5_UNION']['minutes'] = 120
    else:
        row = {'row_id': f'r{number}', 'label': f'조건 {number}', 'evidence': {}}
        if number == 6:
            row.update(unsupported='YES', pinch_mass_kg=1, pinch_force_kg_equiv=0, minutes=120)
        elif number == 7:
            row.update(unsupported='YES', single_hand_mass_kg=4.5, grip_force_kg_equiv=0, minutes=120)
        elif number == 8:
            row.update(load_mass_kg=25, lift_count_day=10)
        elif number == 9:
            row.update(load_mass_kg=10, below_knee_count_day=25,
                       above_shoulder_count_day=0, extended_arm_count_day=0,
                       union_count_day=25)
        elif number == 10:
            row.update(load_mass_kg=4.5, lift_rate_min=2, minutes=120)
        elif number == 11:
            row.update(impact_verified='YES', impact_rate_hour=10, minutes=120)
        criterion['rows'] = [row]
        criterion['rows_complete'] = 'YES'
        if number == 9:
            criterion['totals'].update(
                below_knee_count_day=25, above_shoulder_count_day=0,
                extended_arm_count_day=0, union_count_day=25, row_ids=[row['row_id']])
        else:
            criterion['union'].update(row_ids=[row['row_id']],
                                      value=row.get('minutes', row.get('lift_count_day')))
    return conditions, legal


class GeneralCriteria(unittest.TestCase):
    def test_each_of_the_eleven_criteria_can_reach_a_positive_draft(self):
        for number in range(1, 12):
            with self.subTest(criterion=number):
                conditions, legal = qualifying_case(number)
                result = judgment(conditions, legal, number)
                self.assertEqual(result['computed_status'], 'APPLICABLE')
                self.assertEqual(result['missing_fields'], [])

    def test_each_of_the_eleven_criteria_can_be_confirmed_absent(self):
        conditions, legal = baseline()
        for criterion in legal['criteria']:
            criterion['condition_present'] = 'NO'
            if criterion['criterion_no'] >= 6:
                criterion['rows_complete'] = 'YES'
        for exposure in legal['exposures']:
            exposure['minutes'] = 0
        for number in range(1, 12):
            with self.subTest(criterion=number):
                self.assertEqual(judgment(conditions, legal, number)['computed_status'], 'NOT_APPLICABLE')

    def test_each_of_the_eleven_criteria_reports_missing_required_measurements(self):
        for number in range(1, 12):
            with self.subTest(criterion=number):
                conditions, legal = baseline()
                criterion = legal['criteria'][number - 1]
                criterion['condition_present'] = 'YES'
                if number == 4:
                    criterion.update(unsupported='YES', posture_restricted='NO')
                if number <= 5:
                    codes = {1: ['C1_KEYBOARD_FOCUSED'],
                             2: ['C2_NECK', 'C2_SHOULDER', 'C2_ELBOW', 'C2_WRIST', 'C2_HAND'],
                             3: ['C3_UNION'],
                             4: ['C4_NECK_FLEX', 'C4_TRUNK_FLEX', 'C4_NECK_TWIST', 'C4_TRUNK_TWIST', 'C4_UNION'],
                             5: ['C5_SQUAT', 'C5_KNEEL', 'C5_UNION']}[number]
                    for exposure in legal['exposures']:
                        if exposure['condition_code'] in codes:
                            exposure['minutes'] = None
                else:
                    row = {'row_id': f'missing-{number}', 'label': '입력 미완성', 'evidence': {}}
                    if number == 6:
                        row.update(unsupported='YES', pinch_mass_kg=1, pinch_force_kg_equiv=0, minutes=None)
                    elif number == 7:
                        row.update(unsupported='YES', single_hand_mass_kg=4.5, grip_force_kg_equiv=0, minutes=None)
                    elif number == 8:
                        row.update(load_mass_kg=25, lift_count_day=None)
                    elif number == 9:
                        row.update(load_mass_kg=10, below_knee_count_day=None,
                                   above_shoulder_count_day=None, extended_arm_count_day=None,
                                   union_count_day=None)
                    elif number == 10:
                        row.update(load_mass_kg=4.5, lift_rate_min=2, minutes=None)
                    else:
                        row.update(impact_verified='YES', impact_rate_hour=10, minutes=None)
                    criterion['rows'] = [row]
                    criterion['rows_complete'] = 'YES'
                    if number == 9:
                        criterion['totals']['row_ids'] = [row['row_id']]
                    else:
                        criterion['union'].update(row_ids=[row['row_id']], value=None)
                self.assertEqual(judgment(conditions, legal, number)['computed_status'], 'NEEDS_INPUT')

    def test_each_of_the_eleven_criteria_flags_a_measurement_conflicting_with_absence(self):
        for number in range(1, 12):
            with self.subTest(criterion=number):
                conditions, legal = qualifying_case(number)
                legal['criteria'][number - 1]['condition_present'] = 'NO'
                result = judgment(conditions, legal, number)
                self.assertEqual(result['computed_status'], 'NEEDS_REVIEW')
                self.assertIn('INPUT_CONFLICT', result['review_reasons'])

    def test_unknowns_are_not_converted_to_zero_and_have_actionable_paths(self):
        conditions, legal = baseline()
        first = legal['criteria'][0]
        first['condition_present'] = 'YES'
        legal['exposures'][0]['minutes'] = None
        result = judgment(conditions, legal, 1)
        self.assertEqual(result['computed_status'], 'NEEDS_INPUT')
        self.assertIn('exposures.C1_KEYBOARD_FOCUSED.minutes', result['missing_fields'])

    def test_explicit_absence_is_not_applicable_but_conflicting_measurement_needs_review(self):
        conditions, legal = baseline()
        legal['exposures'][0]['minutes'] = 10
        result = judgment(conditions, legal, 1)
        self.assertEqual(result['computed_status'], 'NEEDS_REVIEW')
        self.assertIn('INPUT_CONFLICT', result['review_reasons'])

    def test_union_claim_cannot_disagree_with_a_single_qualifying_row(self):
        conditions, legal = qualifying_case(8)
        legal['criteria'][7]['union']['value'] = 9
        result = judgment(conditions, legal, 8)
        self.assertEqual(result['computed_status'], 'NEEDS_REVIEW')
        self.assertIn('INPUT_CONFLICT', result['review_reasons'])

    def test_c9_combination_rule_requires_the_selected_eligible_rows(self):
        conditions, legal = qualifying_case(9)
        criterion = legal['criteria'][8]
        criterion['rows'][0].update(below_knee_count_day=10, above_shoulder_count_day=10,
                                    extended_arm_count_day=10, union_count_day=20)
        criterion['totals'].update(below_knee_count_day=10, above_shoulder_count_day=10,
                                   extended_arm_count_day=10, union_count_day=30, row_ids=[])
        result = judgment(conditions, legal, 9)
        self.assertEqual(result['computed_status'], 'NEEDS_INPUT')
        self.assertIn('criteria.9.totals.row_ids', result['missing_fields'])

    def test_c9_totals_cannot_assert_counts_without_selected_qualifying_rows(self):
        conditions, legal = qualifying_case(9)
        criterion = legal['criteria'][8]
        criterion['rows'][0].update(below_knee_count_day=0, above_shoulder_count_day=0,
                                    extended_arm_count_day=0, union_count_day=0)
        criterion['totals'].update(
            below_knee_count_day=25, above_shoulder_count_day=0,
            extended_arm_count_day=0, union_count_day=25, row_ids=[])
        result = judgment(conditions, legal, 9)
        self.assertEqual(result['computed_status'], 'NEEDS_INPUT')
        self.assertIn('criteria.9.totals.row_ids', result['missing_fields'])

    def test_nonfinite_and_boolean_numbers_are_reviewed_without_crashing(self):
        for value in (float('nan'), float('inf'), True, -1):
            with self.subTest(value=value):
                conditions, legal = baseline()
                legal['criteria'][0]['condition_present'] = 'YES'
                legal['exposures'][0]['minutes'] = value
                result = judgment(conditions, legal, 1)
                self.assertEqual(result['computed_status'], 'NEEDS_REVIEW')
                self.assertIn('INPUT_CONFLICT', result['review_reasons'])

    def test_huge_integer_input_is_rejected_as_conflict_not_an_overflow(self):
        conditions, legal = baseline()
        legal['criteria'][0]['condition_present'] = 'YES'
        legal['exposures'][0]['minutes'] = 10 ** 1000
        result = judgment(conditions, legal, 1)
        self.assertEqual(result['computed_status'], 'NEEDS_REVIEW')


class ThresholdBoundaries(unittest.TestCase):
    def test_threshold_boundary_values_for_all_eleven_criteria(self):
        for number in range(1, 12):
            with self.subTest(criterion=number, side='at'):
                conditions, legal = qualifying_case(number)
                self.assertEqual(judgment(conditions, legal, number)['computed_status'], 'APPLICABLE')
            with self.subTest(criterion=number, side='below'):
                conditions, legal = qualifying_case(number)
                criterion = legal['criteria'][number - 1]
                if number == 1:
                    legal['exposures'][0]['minutes'] = 239
                elif number == 2:
                    next(x for x in legal['exposures'] if x['condition_code']=='C2_WRIST')['minutes'] = 119
                elif number == 3:
                    next(x for x in legal['exposures'] if x['condition_code']=='C3_UNION')['minutes'] = 119
                elif number == 4:
                    next(x for x in legal['exposures'] if x['condition_code']=='C4_NECK_FLEX')['minutes'] = 119
                    next(x for x in legal['exposures'] if x['condition_code']=='C4_UNION')['minutes'] = 119
                elif number == 5:
                    next(x for x in legal['exposures'] if x['condition_code']=='C5_SQUAT')['minutes'] = 119
                    next(x for x in legal['exposures'] if x['condition_code']=='C5_UNION')['minutes'] = 119
                elif number in (6, 7, 10, 11):
                    criterion['rows'][0]['minutes'] = 119
                    criterion['union']['value'] = 119
                elif number == 8:
                    criterion['rows'][0]['lift_count_day'] = 9
                    criterion['union']['value'] = 9
                else:
                    criterion['rows'][0].update(below_knee_count_day=24, above_shoulder_count_day=0,
                                                extended_arm_count_day=0, union_count_day=24)
                    criterion['totals'].update(below_knee_count_day=24, above_shoulder_count_day=0,
                                               extended_arm_count_day=0, union_count_day=24)
                self.assertEqual(judgment(conditions, legal, number)['computed_status'], 'NOT_APPLICABLE')


if __name__ == '__main__':
    unittest.main()
