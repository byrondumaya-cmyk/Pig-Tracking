"""
Comprehensive performance profiler for the Swine Health Monitor pipeline.

Measures each stage of the processing pipeline to identify bottlenecks.

Run: python scripts/profile_pipeline.py
"""

import time
import sys
import os
from pathlib import Path
from collections import defaultdict
import numpy as np

# Ensure project root is on path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.config_loader import load_config
from src.inference.detector import PigDetector
from src.tracking.pig_tracker import PigTracker
from src.analytics.behavior_analyzer import BehaviorAnalyzer
from src.hardware.dht22_sensor import DHT22Sensor
import cv2


class PipelineProfiler:
    """Profiles each stage of the pipeline."""

    def __init__(self):
        self.timings = defaultdict(list)
        self.frame_count = 0

    def measure(self, stage_name):
        """Context manager for measuring stage execution time."""
        class Timer:
            def __init__(self, profiler, name):
                self.profiler = profiler
                self.name = name
                self.t0 = None

            def __enter__(self):
                self.t0 = time.perf_counter()
                return self

            def __exit__(self, *args):
                elapsed = time.perf_counter() - self.t0
                self.profiler.timings[self.name].append(elapsed)

        return Timer(self, stage_name)

    def report(self):
        """Print a summary of all measurements."""
        print("\n" + "=" * 80)
        print("PIPELINE PERFORMANCE PROFILE")
        print("=" * 80)
        print(f"Total frames processed: {self.frame_count}\n")

        stages = [
            "capture",
            "preprocess",
            "inference",
            "postprocess",
            "tracking",
            "behavior",
            "thermal",
            "dht",
            "loop_total",
        ]

        for stage in stages:
            if stage not in self.timings or not self.timings[stage]:
                continue

            times = self.timings[stage]
            avg_ms = np.mean(times) * 1000
            min_ms = np.min(times) * 1000
            max_ms = np.max(times) * 1000
            print(f"{stage:20s}: {avg_ms:8.2f} ms (min: {min_ms:6.2f}, max: {max_ms:6.2f})")

        # Calculate FPS
        if "loop_total" in self.timings and self.timings["loop_total"]:
            avg_loop_time = np.mean(self.timings["loop_total"])
            fps = 1.0 / avg_loop_time if avg_loop_time > 0 else 0
            print(f"\n{'ACTUAL FPS':20s}: {fps:8.2f} FPS")
            print(f"{'TARGET FPS':20s}: 20.00 FPS")
            print(f"{'GAP':20s}: {20 - fps:8.2f} FPS (need {(20-fps)/fps*100:.1f}% improvement)")

        # Breakdown
        print("\n" + "-" * 80)
        print("STAGE BREAKDOWN (% of loop time):")
        print("-" * 80)
        if "loop_total" in self.timings:
            loop_avg = np.mean(self.timings["loop_total"])
            for stage in stages[:-1]:
                if stage in self.timings and self.timings[stage]:
                    stage_avg = np.mean(self.timings[stage])
                    pct = (stage_avg / loop_avg) * 100 if loop_avg > 0 else 0
                    print(f"{stage:20s}: {pct:6.2f}%")

        print("=" * 80 + "\n")


def main():
    print("Loading configuration...")
    cfg = load_config()

    # Disable optional sensors for testing
    cfg.thermal.enabled = False
    cfg.dht22.enabled = False
    cfg.gsm.enabled = False
    cfg.dashboard.debug = False

    profiler = PipelineProfiler()

    # Initialize components
    print("Initializing detector...")
    detector = PigDetector(
        model_path=cfg.inference.model_path,
        confidence_threshold=cfg.inference.confidence_threshold,
        iou_threshold=cfg.inference.iou_threshold,
        input_size=cfg.inference.input_size,
        intra_op_threads=cfg.inference.intra_op_threads,
        inter_op_threads=cfg.inference.inter_op_threads,
        enable_profiling=True,
    )

    print("Initializing tracker...")
    tracker = PigTracker(
        max_age=cfg.tracking.max_age,
        min_hits=cfg.tracking.min_hits,
        iou_threshold=cfg.tracking.iou_threshold,
    )

    print("Initializing behavior analyzer...")
    behavior_analyzer = BehaviorAnalyzer()

    print("Opening camera...")
    cap = cv2.VideoCapture(cfg.camera.device_index)
    if not cap.isOpened():
        print("ERROR: Cannot open camera")
        sys.exit(1)

    cap.set(cv2.CAP_PROP_FRAME_WIDTH, cfg.camera.width)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, cfg.camera.height)
    cap.set(cv2.CAP_PROP_FPS, cfg.camera.fps)

    print("\nStarting profiling loop (60 frames)...")
    print("-" * 80)

    frame_count = 0
    max_frames = 60

    try:
        while frame_count < max_frames:
            with profiler.measure("loop_total"):
                # Capture
                with profiler.measure("capture"):
                    ret, frame = cap.read()
                    if not ret:
                        print("End of stream or camera error")
                        break

                frame_count += 1
                profiler.frame_count = frame_count

                # Skip frames if configured
                if frame_count % cfg.inference.frame_skip != 0:
                    continue

                # Apply camera flips
                if cfg.camera.flip_horizontal:
                    frame = cv2.flip(frame, 1)
                if cfg.camera.flip_vertical:
                    frame = cv2.flip(frame, 0)

                # Detection
                with profiler.measure("inference"):
                    with profiler.measure("preprocess"):
                        pass  # Preprocessing happens inside detector.detect()

                    detections = detector.detect(frame)

                    with profiler.measure("postprocess"):
                        pass  # Postprocessing happens inside detector.detect()

                # Tracking
                with profiler.measure("tracking"):
                    tracked_pigs = tracker.update(detections, cfg.classes)

                # Behavior analysis
                with profiler.measure("behavior"):
                    detection_dicts = [
                        {
                            "track_id": pig.track_id,
                            "behavior": pig.behavior,
                            "centroid": pig.centroid,
                            "thermal_zone_temp": 0.0,
                        }
                        for pig in tracked_pigs
                    ]
                    active_tracks, population_snapshot = behavior_analyzer.update(detection_dicts)

                # Thermal (simulated as disabled)
                with profiler.measure("thermal"):
                    pass

                # DHT (simulated as disabled)
                with profiler.measure("dht"):
                    pass

                # Logging
                if frame_count % 10 == 0:
                    print(f"Processed {frame_count} frames...")

    except KeyboardInterrupt:
        print("\nInterrupted by user")
    finally:
        cap.release()
        print("\nCamera released")

    # Get detector timing stats
    detector_stats = detector.get_timing_stats()

    profiler.report()

    # Report detailed detector breakdown
    print("\n" + "=" * 80)
    print("DETECTOR INTERNAL TIMING")
    print("=" * 80)
    for stage, stats in detector_stats.items():
        print(
            f"{stage:20s}: {stats['mean_ms']:8.2f} ms "
            f"(min: {stats['min_ms']:6.2f}, max: {stats['max_ms']:6.2f}, n={stats['count']})"
        )
    print("=" * 80)


if __name__ == "__main__":
    main()
