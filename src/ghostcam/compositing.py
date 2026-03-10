import numpy as np

try:
    import cv2
except ImportError:  # pragma: no cover - local test environments may not have OpenCV
    cv2 = None


MASK_THRESHOLD = 0.58
EDGE_BAND_LOW = 0.35
EDGE_BAND_HIGH = 0.75
EDGE_SHADOW_RGB = np.array([24, 24, 24], dtype=np.float32)
ALPHA_BLUR_KERNEL = (7, 7)
MORPH_OPEN_KERNEL = (3, 3)
MORPH_ERODE_KERNEL = (3, 3)


def build_foreground_alpha(mask: np.ndarray) -> np.ndarray:
    alpha = np.clip(mask.astype(np.float32), 0.0, 1.0)
    if cv2 is not None:
        open_kernel = np.ones(MORPH_OPEN_KERNEL, dtype=np.uint8)
        erode_kernel = np.ones(MORPH_ERODE_KERNEL, dtype=np.uint8)
        alpha = cv2.morphologyEx(alpha, cv2.MORPH_OPEN, open_kernel)
        alpha = cv2.erode(alpha, erode_kernel, iterations=1)
        alpha = cv2.GaussianBlur(alpha, ALPHA_BLUR_KERNEL, 0)
    alpha[alpha >= MASK_THRESHOLD] = 1.0
    alpha[alpha < EDGE_BAND_LOW] = 0.0
    return alpha


def composite_frame(img_rgb: np.ndarray, mask: np.ndarray, background_rgb: np.ndarray) -> np.ndarray:
    alpha = build_foreground_alpha(mask)
    alpha_3 = alpha[:, :, np.newaxis]

    # Darken uncertain edge pixels so hair and shoulder boundaries do not bloom white.
    edge_band = np.clip((EDGE_BAND_HIGH - alpha) / (EDGE_BAND_HIGH - EDGE_BAND_LOW), 0.0, 1.0)
    edge_band = edge_band[:, :, np.newaxis]
    styled_foreground = img_rgb.astype(np.float32) * (1.0 - edge_band) + EDGE_SHADOW_RGB * edge_band

    output = styled_foreground * alpha_3 + background_rgb.astype(np.float32) * (1.0 - alpha_3)
    return np.clip(output, 0, 255).astype(np.uint8)
