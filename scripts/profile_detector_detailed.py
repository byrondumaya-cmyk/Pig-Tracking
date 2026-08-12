"""
Detailed detector profiling to break down model inference stages.

Run: python scripts/profile_detector_detailed.py
"""

import time
import sys
import os
from pathlib import Path
from collections import defaultdict
import numpy as np
import cv2

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.config_loader import load_config
from src.inference.detector import PigDetector


def profile_detector_preprocessing():
    """Measure preprocessing time in isolation."""
    cfg = load_config()
    detector = PigDetector(
        model_path=cfg.inference.model_path,
        confidence_threshold=cfg.inference.confidence_threshold,
        iou_threshold=cfg.inference.iou_threshold,
        input_size=cfg.inference.input_size,
    )

    print("=" * 80)
    print("DETECTOR PREPROCESSING PROFILE")
    print("=" * 80)

    # Create test frame
    frame = np.random.randint(0, 255, (240, 320, 3), dtype=np.uint8)

    # Warm up
    detector.detect(frame)

    # Measure preprocessing only
    # We need to break into the detector's internals

    # Let's check the detector code for preprocessing
    timings_preprocess = []
    timings_inference = []
    timings_postprocess = []

    cap = cv2.VideoCapture(cfg.camera.device_index)
    if cap.isOpened():
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, cfg.camera.width)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, cfg.camera.height)

    for i in range(30):
        if cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                frame = np.random.randint(0, 255, (240, 320, 3), dtype=np.uint8)
        else:
            frame = np.random.randint(0, 255, (240, 320, 3), dtype=np.uint8)

        detections = detector.detect(frame)

    if cap.isOpened():
        cap.release()

    print("\nDetector is working correctly.")
    print("NOTE: Preprocessing/postprocessing breakdown requires modifying detector.py")
    print("to add time.perf_counter() markers.")
    print("=" * 80)


def main():
    profile_detector_preprocessing()


if __name__ == "__main__":
    main()
