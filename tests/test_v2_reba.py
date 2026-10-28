"""REBA missing-input semantics and numeric boundary checks for schema 2.0."""
import unittest

from backend.engine.reba_scoring import calculate_reba


def snapshot(load_state="UNLOADED", measured=None):
    slot = {
        "slot_no": 1, "photo_id": 7, "analysis_target": True,
        "camera_side": "LEFT", "forward_direction": "SCREEN_RIGHT",
        "side_view_verified": "YES",
        "observation": {"load_state": load_state, "measured_load_kg": measured,
                        "single_person": "YES", "full_frame": "YES", "normal_work": "YES"},
    }
    common = {
        "trunk_base": 1, "trunk_twisted": "YES",  # side-bent is UNKNOWN; OR already resolves.
        "neck_base": 1, "neck_twisted": "NO", "neck_side_bent": "NO",
        "legs_support": "BILATERAL_STABLE", "seated": "YES",  # knee_band is not needed.
        "shock_force": "NO", "static_over_1min": "NO",
        "small_repeat_over_4min": "NO", "rapid_change_or_unstable": "NO",
    }
    manual = [dict(slot_no=1, photo_id=7, scope="COMMON", field=key, value=value)
              for key, value in common.items()]
    arm = {
        "upper_arm_base": 1, "arm_abducted_or_rotated": "NO", "shoulder_raised": "NO",
        "arm_supported_or_gravity_assisted": "YES", "lower_arm_base": 1,
        "wrist_base": 1, "wrist_deviated_or_twisted": "NO", "coupling": "NOT_APPLICABLE",
    }
    for side in ("LEFT", "RIGHT"):
        manual.extend(dict(slot_no=1, photo_id=7, scope=side, field=key, value=value)
                      for key, value in arm.items())
    return {"schema_version": "2.0", "capture": {"camera_side": "LEFT", "forward_direction": "SCREEN_RIGHT",
            "slots": [slot]}, "manual": manual}


class RebaBoundary(unittest.TestCase):
    def test_seated_case_and_confirmed_or_do_not_require_irrelevant_unknowns(self):
        result = calculate_reba(snapshot(), None)
        slot = result["slots"][0]
        self.assertEqual(result["status"], "COMPLETE")
        self.assertEqual(slot["total"], 1)
        self.assertNotIn("common.knee_band", slot["missing_fields"])
        self.assertNotIn("common.trunk_side_bent", slot["missing_fields"])

    def test_measured_load_without_value_is_reviewed_instead_of_crashing(self):
        slot = calculate_reba(snapshot("MEASURED", None), None)["slots"][0]
        self.assertEqual(slot["status"], "INCOMPLETE")
        self.assertIn("INPUT_CONFLICT", slot["left"]["review_reasons"])

    def test_huge_integer_load_is_reviewed_instead_of_overflowing(self):
        slot = calculate_reba(snapshot("MEASURED", 10 ** 1000), None)["slots"][0]
        self.assertEqual(slot["status"], "INCOMPLETE")
        self.assertIn("INPUT_CONFLICT", slot["left"]["review_reasons"])


if __name__ == "__main__":
    unittest.main()
