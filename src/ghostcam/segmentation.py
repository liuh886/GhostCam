from __future__ import annotations

import importlib
import os
from pathlib import Path
from typing import Callable
from urllib.error import URLError
from urllib.request import urlretrieve

import numpy as np


SELFIE_SEGMENTER_MODEL_URL = (
    "https://storage.googleapis.com/mediapipe-models/"
    "image_segmenter/selfie_segmenter_landscape/float16/latest/"
    "selfie_segmenter_landscape.tflite"
)


class MediaPipeSetupError(RuntimeError):
    pass


class LegacySelfieSegmenter:
    def __init__(self, selfie_segmentation_module):
        self._segmenter = selfie_segmentation_module.SelfieSegmentation(model_selection=1)

    def process(self, image_rgb, timestamp_ms=None):
        del timestamp_ms
        return self._segmenter.process(image_rgb).segmentation_mask

    def close(self):
        close = getattr(self._segmenter, "close", None)
        if callable(close):
            close()


class TasksSelfieSegmenter:
    def __init__(self, mp_module, vision_module, base_options_cls, model_asset_path, streaming):
        running_mode = vision_module.RunningMode.VIDEO if streaming else vision_module.RunningMode.IMAGE
        options = vision_module.ImageSegmenterOptions(
            base_options=base_options_cls(model_asset_path=model_asset_path),
            running_mode=running_mode,
            output_confidence_masks=True,
            output_category_mask=False,
        )
        self._streaming = streaming
        self._mp = mp_module
        self._segmenter = vision_module.ImageSegmenter.create_from_options(options)

    def process(self, image_rgb, timestamp_ms=None):
        mp_image = self._mp.Image(image_format=self._mp.ImageFormat.SRGB, data=image_rgb)
        if self._streaming:
            if timestamp_ms is None:
                raise ValueError("timestamp_ms is required for streaming segmentation")
            result = self._segmenter.segment_for_video(mp_image, int(timestamp_ms))
        else:
            result = self._segmenter.segment(mp_image)
        return _extract_mask(result)

    def close(self):
        close = getattr(self._segmenter, "close", None)
        if callable(close):
            close()


def _extract_mask(result) -> np.ndarray:
    confidence_masks = getattr(result, "confidence_masks", None)
    if confidence_masks:
        return _normalize_mask(confidence_masks[0].numpy_view())

    category_mask = getattr(result, "category_mask", None)
    if category_mask is not None:
        return _normalize_mask(category_mask.numpy_view()).astype(np.float32)

    raise MediaPipeSetupError("MediaPipe returned no segmentation mask.")


def _normalize_mask(mask) -> np.ndarray:
    array = np.array(mask, copy=True)
    if array.ndim == 3 and array.shape[-1] == 1:
        return array[:, :, 0]
    return array


def _default_model_path() -> str:
    cache_root = Path(os.getenv("LOCALAPPDATA") or Path.home() / ".cache")
    model_path = cache_root / "GhostCam" / "models" / "selfie_segmenter_landscape.tflite"
    model_path.parent.mkdir(parents=True, exist_ok=True)

    if not model_path.exists():
        try:
            urlretrieve(SELFIE_SEGMENTER_MODEL_URL, model_path)
        except URLError as exc:
            raise MediaPipeSetupError(
                "MediaPipe Tasks API is available, but GhostCam could not download the "
                f"selfie segmenter model from {SELFIE_SEGMENTER_MODEL_URL}."
            ) from exc

    return str(model_path)


def create_segmenter(
    streaming: bool = False,
    import_module: Callable[[str], object] | None = None,
    model_path_provider: Callable[[], str] | None = None,
):
    importer = import_module or importlib.import_module
    model_path_provider = model_path_provider or _default_model_path

    try:
        legacy_module = importer("mediapipe.solutions.selfie_segmentation")
        return LegacySelfieSegmenter(legacy_module)
    except ImportError:
        pass

    try:
        mp_module = importer("mediapipe")
        vision_module = importer("mediapipe.tasks.python.vision")
        base_options_module = importer("mediapipe.tasks.python.core.base_options")
    except ImportError as exc:
        raise MediaPipeSetupError(
            "MediaPipe is installed, but neither the legacy SelfieSegmentation API nor the "
            "supported Tasks API imports are available."
        ) from exc

    return TasksSelfieSegmenter(
        mp_module=mp_module,
        vision_module=vision_module,
        base_options_cls=base_options_module.BaseOptions,
        model_asset_path=model_path_provider(),
        streaming=streaming,
    )
