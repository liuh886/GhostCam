import av
import numpy as np
import cv2
import os
import sys

from ghostcam.segmentation import create_segmenter

def verify():
    print("👻 GhostCam Headless Verification")
    print("------------------------------------")
    
    # 1. Initialize AI
    segmentation = create_segmenter(streaming=False)
    
    # 2. Create a dummy frame (1280x720 RGB) or try to grab one
    # For a pure software test, we'll create a synthetic gradient frame
    print("[*] Generating synthetic test frame...")
    h, w = 720, 1280
    image = np.zeros((h, w, 3), dtype=np.uint8)
    for y in range(h):
        image[y, :, 0] = int(y / h * 255) # Red gradient
        image[y, :, 1] = 128               # Green flat
        image[y, :, 2] = int((1 - y / h) * 255) # Blue gradient

    # Add a "person" shape (a white circle)
    cv2.circle(image, (w//2, h//2), 200, (255, 255, 255), -1)
    
    # 3. Process with MediaPipe
    print("[*] Running MediaPipe Segmentation...")
    image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
    mask = segmentation.process(image_rgb)
    
    # 4. Apply Blur
    print("[*] Applying Vectorized Blur...")
    condition = np.stack((mask,) * 3, axis=-1) > 0.1
    background = cv2.GaussianBlur(image, (51, 51), 0)
    output = np.where(condition, image, background)
    
    # 5. Save output
    output_path = "ghostcam_verify.jpg"
    cv2.imwrite(output_path, output)
    print(f"[+] SUCCESS! Verification image saved to: {os.path.abspath(output_path)}")
    print("[i] Check this image to see the background removal effect.")
    segmentation.close()

if __name__ == "__main__":
    verify()
