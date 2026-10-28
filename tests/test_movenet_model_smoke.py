"""Optional real-runtime check for the locally downloaded official MoveNet model."""
import gc
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from backend.engine import movenet

MODEL = Path(__file__).resolve().parents[1] / "models" / "movenet_lightning.tflite"


@unittest.skipUnless(MODEL.is_file(), "download the official model with scripts/download_movenet.ps1")
class MoveNetModelSmoke(unittest.TestCase):
    def test_official_model_runs_through_the_application_inference_path(self):
        with tempfile.TemporaryDirectory(prefix="loco_movenet_smoke_") as temporary:
            image_path = Path(temporary) / "blank.png"
            Image.new("RGB", (640, 480), "white").save(image_path)
            slot = {
                "slot_no": 1, "photo_id": 1, "camera_side": "LEFT",
                "forward_direction": "SCREEN_RIGHT", "side_view_verified": "YES",
                "observation": {"single_person": "YES", "full_frame": "YES", "normal_work": "YES"},
            }
            result = movenet.process(slot, {
                "photos": [{"photo_id": 1, "file_path": str(image_path)}], "capture": {},
            })
            self.assertNotEqual(result["status"], "ERROR", result["diagnostics"])
            self.assertEqual(len(result["points"]), 17)
        movenet._interpreter = None
        gc.collect()


if __name__ == "__main__":
    unittest.main()
