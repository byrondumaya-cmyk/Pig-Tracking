"""
src/main.py — System Entry Point

Orchestrates all subsystems:
  Camera → Detector → Tracker → Thermal → Analytics → Health → Database → Dashboard

Run this on the Raspberry Pi:
    python3 src/main.py

Optional flags:
    --config path/to/config.yaml   Override default config path
    --no-thermal                   Skip AMG8833 (useful for testing without hardware)
    --debug                        Enable verbose logging
"""

from __future__ import annotations

import argparse
import logging
import signal
import sys
import threading
import time
from pathlib import Path

import cv2

# Add project root to Python path when run directly
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.config_loader import AppConfig, load_config


logger = logging.getLogger(__name__)


class SwineHealthMonitor:
    """
    Top-level system orchestrator.

    Manages the lifecycle of all subsystems and coordinates
    the main processing loop.
    """

    def __init__(self, cfg: AppConfig) -> None:
        self.cfg = cfg
        self._running = False
        self._threads: list[threading.Thread] = []

        # Subsystem references — populated in setup()
        self.detector = None
        self.tracker = None
        self.thermal_reader = None
        self.thermal_mapper = None
        self.behavior_analyzer = None
        self.risk_engine = None
        self.repository = None
        self.dashboard_app = None

    def setup(self) -> None:
        """Initialize all subsystems. Fails fast if critical components missing."""
        logger.info("Initializing subsystems...")

        from src.inference.detector import PigDetector
        from src.tracking.pig_tracker import PigTracker
        from src.analytics.behavior_analyzer import BehaviorAnalyzer
        from src.health.risk_engine import HerdRiskEngine
        from src.database.repository import SwineRepository
        from src.database.schema import initialize_database
        from src.hardware.dht22_sensor import DHT22Sensor
        from src.hardware.gsm_notifier import GSMNotifier

        # Database
        db_path = Path(self.cfg.database.path)
        db_path.parent.mkdir(parents=True, exist_ok=True)
        initialize_database(db_path)
        self.repository = SwineRepository(db_path)
        logger.info("Database ready: %s", db_path)

        # AI Detector
        model_path = Path(self.cfg.inference.model_path)
        if not model_path.exists():
            raise FileNotFoundError(
                f"ONNX model not found: {model_path}\n"
                "Run scripts/export_model.py on your training PC first."
            )
        self.detector = PigDetector(
            model_path=self.cfg.inference.model_path,
            confidence_threshold=self.cfg.inference.confidence_threshold,
            iou_threshold=self.cfg.inference.iou_threshold,
            input_size=self.cfg.inference.input_size,
            intra_op_threads=self.cfg.inference.intra_op_threads,
            inter_op_threads=self.cfg.inference.inter_op_threads,
        )
        logger.info("Detector loaded: %s", model_path)

        # SORT Tracker
        self.tracker = PigTracker(
            max_age=self.cfg.tracking.max_age,
            min_hits=self.cfg.tracking.min_hits,
            iou_threshold=self.cfg.tracking.iou_threshold,
        )
        logger.info("Tracker initialized.")

        # Thermal camera (optional)
        if self.cfg.thermal.enabled:
            try:
                from src.thermal.thermal_reader import AMG8833Reader
                from src.thermal.thermal_mapper import assign_temperatures
                self.thermal_reader = AMG8833Reader(
                    i2c_address=self.cfg.thermal.i2c_address,
                    refresh_hz=self.cfg.thermal.refresh_hz,
                )
                self.thermal_mapper = assign_temperatures
                logger.info("AMG8833 thermal camera initialized.")
            except Exception as exc:
                logger.warning("Thermal unavailable: %s. Continuing without.", exc)
                self.cfg.thermal.enabled = False

        # DHT22 Ambient Sensor
        self.dht_sensor = None
        if self.cfg.dht22.enabled:
            self.dht_sensor = DHT22Sensor(gpio_pin=self.cfg.dht22.gpio_pin)
            logger.info("DHT22 ambient sensor initialized.")

        # GSM Notifier
        self.gsm = None
        if self.cfg.gsm.enabled:
            self.gsm = GSMNotifier(
                port=self.cfg.gsm.serial_port,
                baud_rate=self.cfg.gsm.baud_rate,
                cooldown_minutes=self.cfg.gsm.cooldown_minutes,
            )
            logger.info("GSM900A notifier initialized.")

        # Hybrid Risk Engine
        h = self.cfg.health
        self.behavior_analyzer = BehaviorAnalyzer(
            stationary_behaviors=h.stationary_behaviors,
        )
        self.risk_engine = HerdRiskEngine(
            stationary_behaviors=h.stationary_behaviors,
            stationary_alert_minutes=h.stationary_alert_minutes,
            stationary_heat_stress_minutes=h.stationary_heat_stress_minutes,
            fever_delta_threshold_c=h.fever_delta_threshold_c,
            population_lethargy_ratio=h.population_lethargy_ratio,
            population_persist_seconds=h.population_persist_seconds,
            thi_heat_stress_threshold=h.thi_heat_stress_threshold,
        )
        logger.info("Hybrid risk engine ready.")

        Path(h.snapshot_dir).mkdir(parents=True, exist_ok=True)
        logger.info("All subsystems initialized.")

    def run(self) -> None:
        """Start the main processing loop and the Flask dashboard thread."""
        self._running = True
        self._start_dashboard()

        cap = cv2.VideoCapture(self.cfg.camera.device_index)
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.cfg.camera.width)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.cfg.camera.height)
        cap.set(cv2.CAP_PROP_FPS, self.cfg.camera.fps)

        if not cap.isOpened():
            logger.error("Cannot open camera at index %d.", self.cfg.camera.device_index)
            self.shutdown()
            return

        logger.info("Camera open. Target %d FPS. Ctrl+C to stop.", self.cfg.camera.fps)

        frame_count = 0
        fps_timer = time.time()
        fps_display = 0.0
        ambient = None
        dht_last_read = 0.0

        while self._running:
            ret, frame = cap.read()
            if not ret:
                logger.warning("Frame capture failed. Retrying...")
                time.sleep(0.1)
                continue

            frame_count += 1

            # FPS calculation
            if frame_count % 30 == 0:
                elapsed = time.time() - fps_timer
                fps_display = 30 / elapsed if elapsed > 0 else 0
                fps_timer = time.time()

            # Skip frames to reduce CPU load
            if frame_count % self.cfg.inference.frame_skip != 0:
                continue

            # --- DHT22: read ambient periodically ---
            now = time.time()
            if self.dht_sensor and (now - dht_last_read) >= self.cfg.dht22.sample_rate_sec:
                ambient = self.dht_sensor.read()
                dht_last_read = now
                if ambient and self.repository:
                    self.repository.insert_ambient(
                        ambient.temp_c, ambient.humidity_pct, ambient.thi
                    )

            # --- Detection ---
            detections = self.detector.detect(frame)

            # --- Tracking ---
            tracked_pigs = self.tracker.update(detections, self.cfg.classes)

            # --- Thermal mapping ---
            temperature_map: dict[int, float] = {}
            if self.cfg.thermal.enabled and self.thermal_reader:
                thermal_grid = self.thermal_reader.read()
                temperature_map = self.thermal_mapper(
                    thermal_grid, tracked_pigs, frame.shape
                )

            # --- Behavior analyzer: build detection dicts ---
            detection_dicts = [
                {
                    "track_id": pig.track_id,
                    "behavior": pig.behavior,
                    "centroid": pig.centroid,
                    "thermal_zone_temp": temperature_map.get(pig.track_id, 0.0),
                }
                for pig in tracked_pigs
            ]
            active_tracks, population_snapshot = self.behavior_analyzer.update(detection_dicts)
            persistent_ratio = self.behavior_analyzer.get_persistent_lethargy_ratio(
                self.cfg.health.population_persist_seconds
            )

            # --- Hybrid Risk Evaluation ---
            alerts = self.risk_engine.evaluate(
                active_tracks=active_tracks,
                population_snapshot=population_snapshot,
                persistent_lethargy_ratio=persistent_ratio,
                ambient=ambient,
            )

            # --- Persist detections ---
            for pig in tracked_pigs:
                self.repository.insert_detection(
                    pig.track_id, pig.behavior, pig.confidence, pig.bbox,
                    zone_temp_c=temperature_map.get(pig.track_id, 0.0),
                )

            # --- Handle alerts ---
            for alert in alerts:
                alert_id = self.repository.insert_alert(
                    alert_type=alert.alert_type.value,
                    trigger_reason=alert.trigger_reason,
                    ambient_temp_c=alert.ambient_temp_c,
                    ambient_rh=alert.ambient_rh,
                    ambient_thi=alert.ambient_thi,
                    pig_zone_temp_c=alert.pig_zone_temp_c,
                    stationary_duration_sec=alert.stationary_duration_sec,
                    stationary_count=alert.stationary_count,
                    total_pig_count=alert.total_pig_count,
                )
                if self.gsm and self.cfg.gsm.phone_numbers:
                    sent = self.gsm.send_alert(
                        phone_numbers=self.cfg.gsm.phone_numbers,
                        alert_type=alert.alert_type.value,
                        message=alert.sms_message(),
                    )
                    if sent:
                        self.repository.resolve_alert(alert_id)  # Mark notified

            # --- Update shared frame buffer for dashboard stream ---
            from src.dashboard.stream import FrameBuffer
            FrameBuffer.update(frame, tracked_pigs, fps_display)

        cap.release()
        logger.info("Camera released.")

    def _start_dashboard(self) -> None:
        """Start Flask dashboard in a daemon thread."""
        from src.dashboard.app import create_app

        flask_app = create_app(self.cfg, self.repository)

        def _run_flask():
            flask_app.run(
                host=self.cfg.dashboard.host,
                port=self.cfg.dashboard.port,
                debug=False,
                use_reloader=False,  # Must be False in threaded mode
                threaded=True,
            )

        t = threading.Thread(target=_run_flask, daemon=True, name="Flask-Dashboard")
        t.start()
        self._threads.append(t)
        logger.info(
            "Dashboard running at http://%s:%d",
            self.cfg.dashboard.host,
            self.cfg.dashboard.port,
        )

    def shutdown(self) -> None:
        """Gracefully stop all subsystems."""
        logger.info("Shutting down...")
        self._running = False


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Swine Health Monitor")
    parser.add_argument("--config", type=str, default=None, help="Path to config.yaml")
    parser.add_argument("--no-thermal", action="store_true", help="Disable thermal camera")
    parser.add_argument("--debug", action="store_true", help="Enable DEBUG logging")
    return parser.parse_args()


def main() -> None:
    args = _parse_args()

    log_level = logging.DEBUG if args.debug else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    cfg = load_config(Path(args.config) if args.config else None)
    if args.no_thermal:
        cfg.thermal.enabled = False

    monitor = SwineHealthMonitor(cfg)

    # Graceful Ctrl+C shutdown
    def _signal_handler(sig, frame):
        logger.info("Signal received. Shutting down gracefully...")
        monitor.shutdown()
        sys.exit(0)

    signal.signal(signal.SIGINT, _signal_handler)
    signal.signal(signal.SIGTERM, _signal_handler)

    try:
        monitor.setup()
        monitor.run()
    except FileNotFoundError as exc:
        logger.error("Startup failed: %s", exc)
        sys.exit(1)
    except Exception as exc:
        logger.exception("Unexpected error: %s", exc)
        sys.exit(1)


if __name__ == "__main__":
    main()
