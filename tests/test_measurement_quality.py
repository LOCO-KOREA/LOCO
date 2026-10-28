import copy
import math
import unittest
from backend.engine.measurement_quality import from_analysis, from_points
from backend.pose_contract import COCO_NAMES, MEDIAPIPE_NAMES


def points(names=MEDIAPIPE_NAMES, confidence=0.9):
    return [dict(name=name, x_px=10 + i, y_px=20 + i, confidence=confidence) for i, name in enumerate(names)]


class MeasurementQuality(unittest.TestCase):
    def test_coverage_uses_unique_finite_coordinates_and_the_snapshot_threshold(self):
        rows = points()
        rows[0]['confidence'] = 0.49
        rows[1]['x_px'] = math.inf
        rows[2]['confidence'] = float('nan')
        rows.append(dict(rows[3]))
        rows.append(dict(name='not_a_landmark', x_px=1, y_px=1, confidence=1))
        before = copy.deepcopy(rows)
        quality = from_points(rows, {'provider': 'mediapipe'}, 0.5)
        self.assertEqual((quality['measured_points'], quality['total_points']), (29, 33))
        self.assertEqual(quality['confidence_level'], 'HIGH')
        self.assertEqual(len(rows), len(before))

    def test_a_single_confident_point_does_not_make_coverage_high(self):
        quality = from_points(points()[:1])
        self.assertEqual((quality['measured_points'], quality['total_points'], quality['confidence_level']), (1, 33, 'LOW'))

    def test_no_measurement_stays_missing_without_a_confidence_percentage(self):
        self.assertEqual(from_points([]), dict(measured_points=0, total_points=33, mean_confidence=None, confidence_level='MISSING'))
        invalid = points(confidence=True)
        self.assertEqual(from_points(invalid)['measured_points'], 0)

    def test_legacy_movenet_uses_seventeen_landmarks(self):
        quality = from_points(points(COCO_NAMES), {'model_id': 'movenet-lightning'})
        self.assertEqual((quality['measured_points'], quality['total_points']), (17, 17))

    def test_quality_is_bound_to_the_selected_photo_and_does_not_modify_analysis(self):
        analysis = dict(snapshot=dict(schema_version='2.0', settings=dict(pose_model=dict(provider='mediapipe', confidence_min=0.8)),
            capture=dict(slots=[dict(slot_no=1, photo_id=10, analysis_target=True), dict(slot_no=2, photo_id=11, analysis_target=False)])),
            pose=dict(slots=[dict(slot_no=1, photo_id=99, points=points()), dict(slot_no=2, photo_id=11, points=points())]))
        before = copy.deepcopy(analysis)
        quality = from_analysis(analysis)
        self.assertEqual((quality['measured_points'], quality['total_points']), (0, 33))
        self.assertEqual(len(quality['slots']), 1)
        self.assertEqual(quality['slots'][0]['photo_id'], 10)
        self.assertEqual(analysis, before)

    def test_quality_bands_require_both_coverage_and_confidence(self):
        self.assertEqual(from_points(points(confidence=0.6))['confidence_level'], 'MEDIUM')
        self.assertEqual(from_points(points()[:20])['confidence_level'], 'MEDIUM')
        self.assertEqual(from_points(points(confidence=0.4))['confidence_level'], 'MISSING')


if __name__ == '__main__':
    unittest.main()
