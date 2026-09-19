"""
src/sensor_hub.py - Pi Backend for Hybrid Architecture

PURPOSE:
    This is the lightweight entry point for the Raspberry Pi when used in the 
    Hybrid AI architecture. It skips all ONNX/YOLO inference and Tracker logic.
    It simply reads the USB Camera and MLX90640 Thermal grid, and pumps the 
    raw data into the high-speed Websocket Server for the mobile app to process.

RUN:
    python3 src/sensor_hub.py
"""

from __future__ import annotations

import argparse
import logging
import signal
import sys
import time
from pathlib import Path

# Add project root to Python path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.config_loader import load_config
from src.api.websocket_server import SensorHubStreamer

logger = logging.getLogger(__name__)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Swine Health Sensor Hub (Hybrid Mode)")
    parser.add_argument("--config", type=str, default=None, help="Path to config.yaml")
    parser.add_argument("--debug", action="store_true", help="Enable DEBUG logging")
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    cfg = load_config(Path(args.config) if args.config else None)

    log_level = logging.DEBUG if args.debug else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    logger.info("Starting Sensor Hub (Hybrid Streaming Mode)...")

    # 1. Start Websocket Server
    # Usually we bind to 0.0.0.0 so the mobile app can connect over the Pi's AP
    ws_host = cfg.dashboard.host if hasattr(cfg.dashboard, 'host') else "0.0.0.0"
    ws_port = 8765 # Standard WS port
    
    streamer = SensorHubStreamer(host=ws_host, port=ws_port)
    streamer.start_in_background()

    # 2. Init Camera
    from src.hardware.async_camera import AsyncCamera
    camera = AsyncCamera(
        device_index=cfg.camera.device_index,
        width=cfg.camera.width,
        height=cfg.camera.height,
        fps=cfg.camera.fps,
    )
    if not camera.start():
        logger.error("Failed to start camera. Hub needs a camera to stream.")
        sys.exit(1)
        
    logger.info(f"Camera started (async). Streaming at {cfg.camera.width}x{cfg.camera.height}.")

    # 3. Init Thermal Reader
    thermal_reader = None
    if cfg.thermal.enabled:
        from src.thermal.thermal_reader import MLX90640Reader
        rotation_deg = getattr(cfg.thermal, 'display_rotation_deg', 0.0)
        thermal_reader = MLX90640Reader(
            i2c_address=cfg.thermal.i2c_address,
            refresh_hz=cfg.thermal.refresh_hz,
            i2c_bus=cfg.thermal.i2c_bus,
            rotation_deg=float(rotation_deg),
        )
        logger.info(f"Thermal reader initialized (rotation={rotation_deg}° CW).")

    running = True
    def _signal_handler(sig, frame):
        nonlocal running
        logger.info("Signal received. Shutting down...")
        running = False

    signal.signal(signal.SIGINT, _signal_handler)
    signal.signal(signal.SIGTERM, _signal_handler)

    # 4. Main Streaming Loop
    frame_count = 0
    fps_timer = time.time()
    
    try:
        while running:
            # Non-blocking camera read
            frame = camera.read()
            if frame is None:
                time.sleep(0.01)
                continue
                
            frame_count += 1
            
            # FPS tracking
            if frame_count % 30 == 0:
                elapsed = time.time() - fps_timer
                logger.debug(f"Sensor Hub capturing at {30/elapsed:.1f} FPS")
                fps_timer = time.time()

            # Optional Mirroring
            import cv2
            if cfg.camera.flip_horizontal:
                frame = cv2.flip(frame, 1)
            if cfg.camera.flip_vertical:
                frame = cv2.flip(frame, 0)

            # Grab thermal if enabled
            thermal_grid = None
            if thermal_reader:
                thermal_grid = thermal_reader.read()

            # Push to the websocket streamer
            streamer.update_sensor_data(frame, thermal_grid)
            
            # Tiny sleep to yield thread
            time.sleep(0.005)

    except KeyboardInterrupt:
        pass
    finally:
        camera.stop()
        logger.info("Sensor Hub shut down cleanly.")

if __name__ == "__main__":
    main()
