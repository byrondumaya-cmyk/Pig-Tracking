"""
src/dashboard/stream.py
MJPEG Camera Stream

PURPOSE:
    Provides a shared thread-safe frame buffer that the main inference loop
    writes annotated frames into, and the Flask route reads from.
    Serves an MJPEG stream endpoint for live browser viewing.

USAGE (in routes.py):
    from src.dashboard.stream import FrameBuffer, generate_mjpeg

    @app.route('/video_feed')
    def video_feed():
        return Response(generate_mjpeg(), mimetype='multipart/x-mixed-replace; boundary=frame')
"""

from __future__ import annotations

import threading
import time
from typing import Generator, Optional

import cv2
import numpy as np

# Class-level color palette for behavior labels
BEHAVIOR_COLORS = {
    "lying":             (0,   0,   255),  # Red
    "sitting":           (0,  165, 255),   # Orange
    "standing":          (0,  255,   0),   # Green
    "walking":           (255, 255,   0),  # Cyan
    "feeding":           (255,   0, 255),  # Magenta
    "drinking":          (255, 255, 255),  # White
    "social_interaction":(255, 165,   0),  # Blue-ish
    "aggression":        (0,   0, 128),    # Dark Red
    "unknown":           (128, 128, 128),  # Gray
}


class FrameBuffer:
    """Thread-safe singleton buffer for sharing annotated frames between threads."""

    _lock = threading.Lock()
    _frame: Optional[np.ndarray] = None
    _fps: float = 0.0
    _pig_count: int = 0

    @classmethod
    def update(cls, frame: np.ndarray, tracked_pigs: list, fps: float) -> None:
        """
        Write a new annotated frame to the buffer.
        Called from the main inference loop thread.
        """
        annotated = _annotate_frame(frame.copy(), tracked_pigs, fps)
        with cls._lock:
            cls._frame = annotated
            cls._fps = fps
            cls._pig_count = len(tracked_pigs)

    @classmethod
    def read(cls) -> Optional[np.ndarray]:
        """Read the latest frame. Returns None if no frame is available yet."""
        with cls._lock:
            return cls._frame.copy() if cls._frame is not None else None


def _annotate_frame(frame: np.ndarray, tracked_pigs: list, fps: float) -> np.ndarray:
    """Draw bounding boxes, track IDs, and behavior labels on the frame."""
    for pig in tracked_pigs:
        x1, y1, x2, y2 = [int(v) for v in pig.bbox]
        color = BEHAVIOR_COLORS.get(pig.behavior, (128, 128, 128))
        label = f"#{pig.track_id} {pig.behavior} {pig.confidence:.0%}"

        cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
        (lw, lh), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
        cv2.rectangle(frame, (x1, y1 - lh - 8), (x1 + lw, y1), color, -1)
        cv2.putText(frame, label, (x1, y1 - 4), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1)

    cv2.putText(frame, f"FPS: {fps:.1f}", (10, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
    cv2.putText(frame, f"Pigs: {len(tracked_pigs)}", (10, 50), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
    return frame


def generate_mjpeg(quality: int = 70) -> Generator[bytes, None, None]:
    """
    Generator function for MJPEG streaming.
    Yields JPEG-encoded frames in multipart HTTP format.
    """
    while True:
        frame = FrameBuffer.read()
        if frame is None:
            time.sleep(0.05)
            continue

        _, buffer = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, quality])
        yield (
            b"--frame\r\n"
            b"Content-Type: image/jpeg\r\n\r\n"
            + buffer.tobytes()
            + b"\r\n"
        )
        time.sleep(0.033)  # ~30 FPS max for stream
