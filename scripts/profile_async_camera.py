"""
scripts/profile_async_camera.py

Test async camera performance vs synchronous camera.

Run: python scripts/profile_async_camera.py
"""

import time
import sys
from pathlib import Path
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.config_loader import load_config
from src.hardware.async_camera import AsyncCamera

try:
    import cv2
except ImportError:
    print("ERROR: cv2 not available")
    sys.exit(1)


def profile_sync_camera(cfg, frames=100):
    """Profile traditional synchronous camera capture."""
    print("\n" + "=" * 80)
    print("SYNCHRONOUS CAMERA PROFILE (blocking reads)")
    print("=" * 80)

    cap = cv2.VideoCapture(cfg.camera.device_index)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, cfg.camera.width)
    cap.set(cv2.CAP_PROP_HEIGHT, cfg.camera.height)
    cap.set(cv2.CAP_PROP_FPS, cfg.camera.fps)

    if not cap.isOpened():
        print("Cannot open camera")
        return

    times = []
    dropped_frames = 0

    for i in range(frames):
        t0 = time.perf_counter()
        ret, frame = cap.read()
        elapsed = time.perf_counter() - t0
        times.append(elapsed * 1000)

        if not ret:
            dropped_frames += 1

    cap.release()

    times = np.array(times)
    print(f"Captured {frames} frames, {dropped_frames} dropped")
    print(f"Average read time:   {np.mean(times):7.2f} ms")
    print(f"Min read time:       {np.min(times):7.2f} ms")
    print(f"Max read time:       {np.max(times):7.2f} ms")
    print(f"Std dev:             {np.std(times):7.2f} ms")
    print(f"95th percentile:     {np.percentile(times, 95):7.2f} ms")
    print("=" * 80)


def profile_async_camera(cfg, frames=100):
    """Profile asynchronous camera capture."""
    print("\n" + "=" * 80)
    print("ASYNCHRONOUS CAMERA PROFILE (non-blocking with background thread)")
    print("=" * 80)

    camera = AsyncCamera(
        device_index=cfg.camera.device_index,
        width=cfg.camera.width,
        height=cfg.camera.height,
        fps=cfg.camera.fps,
    )

    if not camera.start():
        print("Cannot start async camera")
        return

    # Warmup
    time.sleep(0.5)

    times = []
    dropped_frames = 0

    for i in range(frames):
        t0 = time.perf_counter()
        frame = camera.read()
        elapsed = time.perf_counter() - t0
        times.append(elapsed * 1000)

        if frame is None:
            dropped_frames += 1
        else:
            time.sleep(0.01)  # Simulate some processing

    camera.stop()

    times = np.array(times)
    stats = camera.get_stats()

    print(f"Captured {stats['frame_count']} frames, {dropped_frames} None reads")
    print(f"Average read time:   {np.mean(times):7.2f} ms")
    print(f"Min read time:       {np.min(times):7.2f} ms")
    print(f"Max read time:       {np.max(times):7.2f} ms")
    print(f"Std dev:             {np.std(times):7.2f} ms")
    print(f"95th percentile:     {np.percentile(times, 95):7.2f} ms")
    print("=" * 80)


def main():
    print("\nLoading configuration...")
    cfg = load_config()

    print("\nComparing camera capture performance...")
    print(f"Device: {cfg.camera.device_index}")
    print(f"Resolution: {cfg.camera.width}x{cfg.camera.height}")
    print(f"Target FPS: {cfg.camera.fps}")

    profile_sync_camera(cfg, frames=100)
    time.sleep(0.5)  # Brief pause between tests
    profile_async_camera(cfg, frames=100)

    print("\n" + "=" * 80)
    print("ANALYSIS")
    print("=" * 80)
    print("Async camera allows non-blocking reads.")
    print("Expected benefit:")
    print("  - Main thread not blocked waiting for camera I/O")
    print("  - Can run inference immediately while camera continues capturing")
    print("  - Reduces variance and jitter in processing loop")
    print("=" * 80 + "\n")


if __name__ == "__main__":
    main()
