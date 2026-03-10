import types
import unittest
from pathlib import Path

import numpy as np


class CreateSegmenterTests(unittest.TestCase):
    def test_composite_frame_darkens_uncertain_edges(self):
        from ghostcam.compositing import composite_frame

        img = np.full((2, 2, 3), 255, dtype=np.uint8)
        background = np.zeros((2, 2, 3), dtype=np.uint8)
        mask = np.array([[1.0, 0.55], [0.2, 0.0]], dtype=np.float32)

        output = composite_frame(img, mask, background)

        self.assertTrue(np.all(output[0, 0] >= 200))
        self.assertTrue(np.all(output[0, 1] < 120))
        self.assertTrue(np.all(output[1, 1] == 0))

    def test_build_foreground_alpha_drops_low_confidence_background(self):
        from ghostcam.compositing import build_foreground_alpha

        mask = np.array([[0.9, 0.5], [0.3, 0.0]], dtype=np.float32)

        alpha = build_foreground_alpha(mask)

        self.assertGreaterEqual(alpha[0, 0], 0.95)
        self.assertEqual(alpha[1, 1], 0.0)

    def test_prefers_legacy_selfie_segmentation_when_available(self):
        from ghostcam.segmentation import create_segmenter

        class FakeLegacySegmenter:
            def __init__(self, model_selection):
                self.model_selection = model_selection

            def process(self, image_rgb):
                return types.SimpleNamespace(segmentation_mask=image_rgb[:, :, 0])

        legacy_module = types.SimpleNamespace(SelfieSegmentation=FakeLegacySegmenter)

        def fake_import(name):
            if name == "mediapipe.solutions.selfie_segmentation":
                return legacy_module
            raise AssertionError(f"unexpected import: {name}")

        segmenter = create_segmenter(import_module=fake_import)
        image = np.ones((2, 3, 3), dtype=np.float32)

        mask = segmenter.process(image)

        self.assertEqual(segmenter.__class__.__name__, "LegacySelfieSegmenter")
        np.testing.assert_array_equal(mask, image[:, :, 0])

    def test_falls_back_to_tasks_api_when_legacy_api_is_missing(self):
        from ghostcam.segmentation import create_segmenter

        captured = {}
        expected_mask = np.array([[0.25, 0.75]], dtype=np.float32)
        returned_mask = expected_mask[:, :, np.newaxis]

        class FakeMaskImage:
            def numpy_view(self):
                return returned_mask

        class FakeSegmenterInstance:
            def __init__(self):
                self.calls = []

            def segment(self, image):
                self.calls.append(("image", image))
                return types.SimpleNamespace(confidence_masks=[FakeMaskImage()])

            def segment_for_video(self, image, timestamp_ms):
                self.calls.append(("video", image, timestamp_ms))
                return types.SimpleNamespace(confidence_masks=[FakeMaskImage()])

        class FakeImageSegmenter:
            @staticmethod
            def create_from_options(options):
                captured["options"] = options
                instance = FakeSegmenterInstance()
                captured["instance"] = instance
                return instance

        class FakeImageSegmenterOptions:
            def __init__(self, **kwargs):
                self.__dict__.update(kwargs)

        class FakeBaseOptions:
            def __init__(self, model_asset_path):
                self.model_asset_path = model_asset_path

        class FakeImage:
            def __init__(self, image_format, data):
                self.image_format = image_format
                self.data = data

        fake_mp = types.SimpleNamespace(
            Image=FakeImage,
            ImageFormat=types.SimpleNamespace(SRGB="srgb"),
        )
        fake_vision = types.SimpleNamespace(
            ImageSegmenter=FakeImageSegmenter,
            ImageSegmenterOptions=FakeImageSegmenterOptions,
            RunningMode=types.SimpleNamespace(IMAGE="image", VIDEO="video"),
        )
        fake_base_options_module = types.SimpleNamespace(BaseOptions=FakeBaseOptions)

        def fake_import(name):
            if name == "mediapipe.solutions.selfie_segmentation":
                raise ImportError("legacy api missing")
            if name == "mediapipe":
                return fake_mp
            if name == "mediapipe.tasks.python.vision":
                return fake_vision
            if name == "mediapipe.tasks.python.core.base_options":
                return fake_base_options_module
            raise AssertionError(f"unexpected import: {name}")

        segmenter = create_segmenter(
            streaming=True,
            import_module=fake_import,
            model_path_provider=lambda: "cached-model.tflite",
        )

        image = np.zeros((1, 2, 3), dtype=np.uint8)
        mask = segmenter.process(image, timestamp_ms=1234)

        self.assertEqual(segmenter.__class__.__name__, "TasksSelfieSegmenter")
        self.assertEqual(captured["options"].base_options.model_asset_path, "cached-model.tflite")
        self.assertEqual(captured["options"].running_mode, "video")
        self.assertEqual(captured["instance"].calls[0][0], "video")
        self.assertEqual(captured["instance"].calls[0][2], 1234)
        np.testing.assert_array_equal(mask, expected_mask)

    def test_raises_helpful_error_when_no_supported_mediapipe_api_is_available(self):
        from ghostcam.segmentation import MediaPipeSetupError, create_segmenter

        def fake_import(name):
            raise ImportError(name)

        with self.assertRaises(MediaPipeSetupError) as ctx:
            create_segmenter(import_module=fake_import)

        self.assertIn("MediaPipe", str(ctx.exception))
        self.assertIn("Tasks API", str(ctx.exception))

    def test_runtime_files_do_not_directly_import_legacy_mediapipe(self):
        repo_root = Path(__file__).resolve().parents[1]
        main_source = (repo_root / "src" / "ghostcam" / "main.py").read_text(encoding="utf-8")
        verify_source = (repo_root / "scripts" / "verify_headless.py").read_text(encoding="utf-8")

        self.assertNotIn("mediapipe.solutions", main_source)
        self.assertNotIn("mediapipe.solutions", verify_source)

    def test_runtime_does_not_force_ghostcam_virtual_device_name(self):
        repo_root = Path(__file__).resolve().parents[1]
        main_source = (repo_root / "src" / "ghostcam" / "main.py").read_text(encoding="utf-8")

        self.assertNotIn("device='GhostCam'", main_source)

    def test_runtime_initializes_input_before_entering_main_loop(self):
        repo_root = Path(__file__).resolve().parents[1]
        main_source = (repo_root / "src" / "ghostcam" / "main.py").read_text(encoding="utf-8")
        run_source = main_source.split("def run(self):", 1)[1].split("def cleanup", 1)[0]

        self.assertIn("is_idle = self.is_virtual_camera_idle()", run_source)
        self.assertIn("if is_idle:", run_source)
        self.assertIn("self.initialize_input()", run_source)

    def test_runtime_uses_stricter_mask_threshold(self):
        repo_root = Path(__file__).resolve().parents[1]
        compositing_source = (repo_root / "src" / "ghostcam" / "compositing.py").read_text(encoding="utf-8")

        self.assertIn("MASK_THRESHOLD = 0.58", compositing_source)
        self.assertIn("MORPH_OPEN_KERNEL = (3, 3)", compositing_source)
        self.assertIn("MORPH_ERODE_KERNEL = (3, 3)", compositing_source)
        self.assertNotIn("> 0.1", compositing_source)

    def test_pm2_config_sets_background_image(self):
        repo_root = Path(__file__).resolve().parents[1]
        ecosystem_source = (repo_root / "ecosystem.config.js").read_text(encoding="utf-8")

        self.assertIn("--background-mode", ecosystem_source)
        self.assertIn('"color"', ecosystem_source)
        self.assertIn("--background-color", ecosystem_source)
        self.assertIn("#ECE8E0", ecosystem_source)

    def test_cli_exposes_background_modes_and_color(self):
        repo_root = Path(__file__).resolve().parents[1]
        main_source = (repo_root / "src" / "ghostcam" / "main.py").read_text(encoding="utf-8")

        self.assertIn('choices=["blur", "color", "image"]', main_source)
        self.assertIn('--background-color', main_source)
        self.assertIn('--background-image', main_source)
        self.assertIn('--blur-strength', main_source)

    def test_windows_management_script_stop_handles_pm2_and_ghostcam(self):
        repo_root = Path(__file__).resolve().parents[1]
        script_source = (repo_root / "GhostCam.ps1").read_text(encoding="utf-8")

        self.assertIn("pm2 stop ghostcam", script_source)
        self.assertIn("pm2 delete ghostcam", script_source)
        self.assertIn("Get-Process ghostcam", script_source)


if __name__ == "__main__":
    unittest.main()
