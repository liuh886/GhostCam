import argparse
import logging
import os
import sys
import time

import av
import cv2
import numpy as np
import pyvirtualcam

from .compositing import composite_frame
from .segmentation import create_segmenter

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("GhostCam")
DEFAULT_BACKGROUND_COLOR = "#222222"
BACKGROUND_MODES = ["blur", "color", "image"]

class GhostCam:
    def __init__(
        self,
        input_device='/dev/video0',
        width=1280,
        height=720,
        fps=30,
        background_mode="image",
        blur_strength=21,
        background_color=DEFAULT_BACKGROUND_COLOR,
        background_image=None,
    ):
        self.input_device = input_device
        self.width = width
        self.height = height
        self.fps = fps
        self.background_mode = background_mode
        self.blur_strength = _normalize_blur_strength(blur_strength)
        self.background_color = _parse_background_color(background_color)
        self.background_image_path = background_image
        self.bg_image = None
        
        self.segmentation = create_segmenter(streaming=True)
        
        self.container = None
        self.cam = None
        self.is_running = False

    def load_background(self):
        if self.background_mode == "image" and self.background_image_path and os.path.exists(self.background_image_path):
            img = cv2.imread(self.background_image_path)
            if img is not None:
                img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
                self.bg_image = cv2.resize(img, (self.width, self.height))
                logger.info(f"Background image loaded from {self.background_image_path}")
            else:
                logger.warning(f"Failed to load background image from {self.background_image_path}")
        elif self.background_mode == "image":
            logger.warning(
                "Background image mode requested but image was not found. Falling back to solid color background."
            )

    def resolve_background(self, img_rgb):
        if self.background_mode == "image" and self.bg_image is not None:
            return self.bg_image
        if self.background_mode == "blur":
            return cv2.GaussianBlur(img_rgb, (self.blur_strength, self.blur_strength), 0)
        return np.full((self.height, self.width, 3), self.background_color, dtype=np.uint8)

    def initialize_input(self):
        if self.container is not None:
            return
        try:
            # PyAV input (silent reading)
            if sys.platform.startswith('linux'):
                format_name = 'v4l2'
            elif sys.platform == 'darwin':
                format_name = 'avfoundation'
            else:
                format_name = 'dshow'
                
            self.container = av.open(self.input_device, format=format_name)
            logger.info(f"Input device {self.input_device} initialized successfully.")
        except Exception as e:
            logger.error(f"Failed to initialize input device: {e}")
            raise

    def release_input(self):
        if self.container:
            self.container.close()
            self.container = None

    def is_virtual_camera_idle(self):
        if not hasattr(self.cam, 'is_used'):
            return False
        try:
            return not self.cam.is_used
        except Exception:
            return False

    def process_frame(self, img_rgb):
        mask = self.segmentation.process(img_rgb, timestamp_ms=int(time.monotonic() * 1000))
        background = self.resolve_background(img_rgb)
        return composite_frame(img_rgb, mask, background)

    def run(self):
        self.load_background()
        
        try:
            self.cam = pyvirtualcam.Camera(width=self.width, height=self.height, fps=self.fps)
            logger.info(f"Virtual camera initialized: {self.cam.device}")
        except Exception as e:
            logger.error(f"Failed to initialize virtual camera: {e}")
            raise

        self.is_running = True
        idle_check_interval = 10.0  # seconds
        last_idle_check = 0
        idle_detection_supported = hasattr(self.cam, 'is_used')
        if not idle_detection_supported:
            logger.warning(
                "Virtual camera backend '%s' does not expose consumer detection. "
                "GhostCam cannot auto-release the physical camera while the service is running.",
                getattr(self.cam, "backend", "unknown"),
            )
        is_idle = self.is_virtual_camera_idle()
        if is_idle:
            logger.info("GhostCam is IDLE. Waiting for a consumer before opening the physical camera...")
        else:
            self.initialize_input()
        
        try:
            while self.is_running:
                current_time = time.time()
                
                # Smart Idle Detection
                if current_time - last_idle_check > idle_check_interval:
                    currently_idle = self.is_virtual_camera_idle()

                    if currently_idle != is_idle:
                        is_idle = currently_idle
                        if is_idle:
                            logger.info("GhostCam is IDLE. Releasing physical camera...")
                            self.release_input()
                        else:
                            logger.info("GhostCam is ACTIVE. Initializing physical camera...")
                            self.initialize_input()
                    last_idle_check = current_time

                if is_idle:
                    time.sleep(1.0)
                    continue

                # Frame processing
                try:
                    if self.container:
                        for packet in self.container.demux():
                            for frame in packet.decode():
                                if isinstance(frame, av.VideoFrame):
                                    img_rgb = frame.to_ndarray(format='rgb24')
                                    if img_rgb.shape[1] != self.width or img_rgb.shape[0] != self.height:
                                        img_rgb = cv2.resize(img_rgb, (self.width, self.height))
                                    
                                    output = self.process_frame(img_rgb)
                                    self.cam.send(output)
                                    self.cam.sleep_until_next_frame()
                                    break
                            else: continue
                            break
                    else:
                        time.sleep(0.1)
                except Exception as e:
                    logger.error(f"Processing error: {e}")
                    time.sleep(1.0)
        finally:
            self.cleanup()

    def cleanup(self):
        self.is_running = False
        self.release_input()
        if self.cam:
            self.cam.close()
            self.cam = None
        if hasattr(self, 'segmentation'):
            self.segmentation.close()
        logger.info("GhostCam resources released.")

def verify_headless():
    logger.info("👻 GhostCam Headless Verification")
    logger.info("------------------------------------")
    
    segmentation = create_segmenter(streaming=False)
    
    # 1. Create a high-contrast test image (1280x720 RGB)
    h, w = 720, 1280
    image = np.zeros((h, w, 3), dtype=np.uint8)
    # Blue-ish gradient background
    for y in range(h):
        image[y, :, 2] = int(y / h * 200) + 55 # B
    
    # Bright Green "Person" Circle
    cv2.circle(image, (w//2, h//2), 250, (0, 255, 0), -1)
    cv2.circle(image, (w//2-80, h//2-50), 30, (255, 255, 255), -1) # Eye
    cv2.circle(image, (w//2+80, h//2-50), 30, (255, 255, 255), -1) # Eye
    
    # 2. Process
    logger.info("[*] Running MediaPipe Segmentation...")
    mask = segmentation.process(image)
    
    # 3. Render
    logger.info("[*] Applying Vectorized Blur...")
    background = cv2.GaussianBlur(image, (99, 99), 0)
    output = composite_frame(image, mask, background)
    
    # 4. Save (OpenCV imwrite expects BGR)
    output_path = "ghostcam_verify.jpg"
    cv2.imwrite(output_path, cv2.cvtColor(output, cv2.COLOR_RGB2BGR))
    logger.info(f"[+] SUCCESS! Image saved to: {os.path.abspath(output_path)}")
    segmentation.close()

def main():
    parser = argparse.ArgumentParser(description="GhostCam: Headless Background Removal VCam")
    parser.add_argument("--verify", action="store_true", help="Run a headless verification and save a test image")
    
    if sys.platform.startswith('linux'): default_input = '/dev/video0'
    elif sys.platform == 'win32': default_input = 'video=Integrated Camera'
    else: default_input = '0'
        
    parser.add_argument("--input", default=default_input, help="Input device")
    parser.add_argument("--width", type=int, default=1280)
    parser.add_argument("--height", type=int, default=720)
    parser.add_argument("--fps", type=int, default=30)
    parser.add_argument("--background-mode", choices=["blur", "color", "image"], default="image")
    parser.add_argument("--blur-strength", "--blur", dest="blur_strength", type=int, default=21)
    parser.add_argument("--background-color", default=DEFAULT_BACKGROUND_COLOR)
    parser.add_argument("--background-image", "--image", dest="background_image", help="Background image path")
    
    args = parser.parse_args()
    
    if args.verify:
        verify_headless()
        return

    ghost_cam = GhostCam(
        input_device=args.input, 
        width=args.width, height=args.height, fps=args.fps, 
        background_mode=args.background_mode,
        blur_strength=args.blur_strength,
        background_color=args.background_color,
        background_image=args.background_image,
    )
    
    try: ghost_cam.run()
    except KeyboardInterrupt: logger.info("Stopped by user.")
    except Exception as e: logger.error(f"Crashed: {e}")
    finally: ghost_cam.cleanup()

if __name__ == "__main__":
    main()


def _normalize_blur_strength(value):
    if value < 1:
        return 1
    if value % 2 == 0:
        return value + 1
    return value


def _parse_background_color(value):
    color = value.lstrip("#")
    if len(color) != 6:
        raise ValueError("background color must be a 6-digit hex value like #222222")
    try:
        return np.array([int(color[i:i+2], 16) for i in (0, 2, 4)], dtype=np.uint8)
    except ValueError as exc:
        raise ValueError("background color must be a valid hex value like #222222") from exc
