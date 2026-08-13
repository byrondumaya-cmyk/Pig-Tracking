"""
src/hardware/async_camera.py

Asynchronous camera capture using a background thread.

PURPOSE:
    Decouple camera I/O latency from the main inference loop.
    Avoids blocking on slow camera reads (which cause variance 0.05-227ms).

USAGE:
    camera = AsyncCamera(device_index=0, width=320, height=240, fps=30)
    camera.start()
    frame = camera.read()  # Non-blocking, always gets most recent frame
    camera.stop()
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Optional

import cv2
import numpy as np

logger = logging.getLogger(__name__)


class AsyncCamera:
    """
    Non-blocking camera wrapper that maintains a background thread
    continuously reading frames from cv2.VideoCapture.

    Main thread calls read() to get the latest frame without blocking.
    """

    def __init__(
        self,
        device_index: int = 0,
        width: int = 320,
        height: int = 240,
        fps: int = 30,
        buffer_size: int = 2,
        reconnect_after_errors: int = 60,
    ) -> None:
        """
        Initialize async camera.

        Args:
            device_index: OpenCV device index (0 for USB, -1 for default)
            width: Capture width
            height: Capture height
            fps: Target capture FPS
            buffer_size: Max frames to keep in buffer (1-2 recommended)
            reconnect_after_errors: Consecutive read failures before the capture
                loop tears down and reopens the device (USB self-healing).
        """
        self.device_index = device_index
        self.width = width
        self.height = height
        self.fps = fps
        self.reconnect_after_errors = reconnect_after_errors

        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._frame_buffer: Optional[np.ndarray] = None
        self._lock = threading.Lock()
        self._frame_count = 0
        self._error_count = 0

    def start(self) -> bool:
        """
        Start background capture thread.

        Returns:
            True if successful, False if camera cannot be opened.
        """
        if self._running:
            logger.warning("Camera already running.")
            return True

        # Test camera can open
        cap = cv2.VideoCapture(self.device_index)
        if not cap.isOpened():
            logger.error(f"Cannot open camera at index {self.device_index}")
            return False

        cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
        cap.set(cv2.CAP_PROP_FPS, self.fps)
        cap.release()

        self._running = True
        self._frame_count = 0
        self._error_count = 0
        self._thread = threading.Thread(target=self._capture_loop, daemon=True)
        self._thread.start()

        logger.info(
            f"Async camera started: device={self.device_index} "
            f"{self.width}x{self.height} @ {self.fps} FPS"
        )
        return True

    def read(self) -> Optional[np.ndarray]:
        """
        Get the latest captured frame.

        Returns:
            Latest frame (BGR), or None if not yet available.
            Always returns immediately without blocking.
        """
        with self._lock:
            if self._frame_buffer is None:
                return None
            return self._frame_buffer.copy()

    def stop(self) -> None:
        """Stop the background capture thread and release camera."""
        if not self._running:
            return

        self._running = False
        if self._thread:
            self._thread.join(timeout=5.0)
            self._thread = None

        logger.info(
            f"Async camera stopped. Captured {self._frame_count} frames, "
            f"{self._error_count} errors."
        )

    def get_stats(self) -> dict:
        """Return capture statistics."""
        return {
            "frame_count": self._frame_count,
            "error_count": self._error_count,
            "running": self._running,
        }

    def _capture_loop(self) -> None:
        """Background thread: continuously read frames."""
        cap = cv2.VideoCapture(self.device_index)
        if not cap.isOpened():
            logger.error("Background thread: Cannot open camera")
            self._running = False
            return

        cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
        cap.set(cv2.CAP_PROP_FPS, self.fps)

        consecutive_errors = 0

        try:
            while self._running:
                ret, frame = cap.read()
                if ret and frame is not None:
                    consecutive_errors = 0
                    with self._lock:
                        self._frame_buffer = frame
                        self._frame_count += 1
                else:
                    consecutive_errors += 1
                    self._error_count += 1
                    # Self-heal: if the camera stalls (USB dropout, suspend,
                    # unplug/replug), release the device and reopen it.
                    # Without this the live feed freezes permanently.
                    if consecutive_errors >= self.reconnect_after_errors:
                        logger.warning("Camera read failing; reopening device...")
                        cap.release()
                        time.sleep(2.0)
                        cap = cv2.VideoCapture(self.device_index)
                        if cap.isOpened():
                            cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
                            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
                            cap.set(cv2.CAP_PROP_FPS, self.fps)
                            consecutive_errors = 0
                        else:
                            logger.error("Camera reopen failed; will retry.")
                            time.sleep(5.0)
                    else:
                        time.sleep(0.01)  # Brief pause on error

        except Exception as e:
            logger.error(f"Camera capture exception: {e}")
            self._running = False
        finally:
            cap.release()
