"""
Test Dashboard-Independent Monitoring (E2E)

Simulates the main application loop without a Flask dashboard client connected.
Injects mock camera frames and mock detections to trigger a health alert.
Verifies that:
1. Monitoring remains active and the alert is evaluated.
2. The event is persisted locally to SQLite.
3. A snapshot is saved to disk.
"""

import sys
import time
import cv2
import numpy as np
from pathlib import Path
import threading

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from src.main import SwineHealthMonitor, load_config

# 1. Monkey-patch cv2.VideoCapture to return a dummy camera
class DummyVideoCapture:
    def __init__(self, *args, **kwargs):
        self.is_opened = True
        self.frame_count = 0
    def isOpened(self):
        return self.is_opened
    def set(self, propId, value):
        pass
    def read(self):
        # Return a blank white frame 640x480
        self.frame_count += 1
        return True, np.ones((480, 640, 3), dtype=np.uint8) * 255
    def release(self):
        self.is_opened = False

cv2.VideoCapture = DummyVideoCapture

class MockThermalReader:
    def __init__(self, *args, **kwargs):
        pass
    def read(self):
        return np.ones((8, 8)) * 39.0

import src.thermal.thermal_reader
src.thermal.thermal_reader.AMG8833Reader = MockThermalReader

# 2. Setup monitor
cfg = load_config(None)
cfg.thermal.enabled = True  # Enable thermal to test fever
cfg.dht22.enabled = False    # Skip ambient hardware
cfg.gsm.enabled = False      # Skip GSM hardware
cfg.inference.model_path = "data/mock_model.onnx" # Fake model path so it doesn't crash if missing
cfg.database.path = "data/swine_monitor_test.db" # Force test DB
# Set snapshot directory to a test directory
test_snap_dir = Path("data/snapshots_test")
cfg.health.snapshot_dir = str(test_snap_dir)
cfg.health.save_snapshot_on_alert = True
test_snap_dir.mkdir(parents=True, exist_ok=True)

# Mock PigDetector so it doesn't need an ONNX file
class MockPigDetector:
    def __init__(self, *args, **kwargs):
        pass
    def detect(self, frame):
        # Always return 1 stationary pig in the middle
        # class_id 0 = lying (assuming class 0 is a stationary behavior)
        return [{"bbox": (100, 100, 200, 200), "confidence": 0.9, "class_id": 0}]

import src.inference.detector
src.inference.detector.PigDetector = MockPigDetector

def run_test():
    monitor = SwineHealthMonitor(cfg)
    
    # We don't want the Flask dashboard to actually bind to the port and block
    # so we mock _start_dashboard
    monitor._start_dashboard = lambda: print("[Test] Dashboard start bypassed.")
    
    # Setup
    try:
        monitor.setup()
    except Exception as e:
        print(f"Setup failed (mocked): {e}")
        # Even if setup fails because of missing files, we can forcefully inject what we need
        pass
    
    # Ensure dependencies are injected if setup failed midway
    monitor.repository = getattr(monitor, 'repository', None)
    if not monitor.repository:
        from src.database.repository import SwineRepository
        from src.database.schema import initialize_database
        db_path = Path("data/swine_monitor_test.db")
        initialize_database(db_path)
        monitor.repository = SwineRepository(db_path)
        monitor.repository.initialize_default_alert_config()
    
    # Force the DB config to what we want for the test
    # Force the DB config to what we want for the test
    import sqlite3
    with sqlite3.connect("data/swine_monitor_test.db") as conn:
        conn.execute("UPDATE alert_config SET value = '0' WHERE key = 'stationary_alert_minutes'")
        conn.execute("UPDATE alert_config SET value = '1' WHERE key = 'population_persist_seconds'")
        conn.execute("UPDATE alert_config SET value = '1.0' WHERE key = 'fever_delta_threshold_c'")
        conn.execute("UPDATE alert_config SET value = '5' WHERE key = 'cooldown_minutes'")
        conn.commit()
    
    monitor.detector = MockPigDetector()
    
    from src.tracking.pig_tracker import PigTracker
    monitor.tracker = PigTracker(max_age=30, min_hits=1, iou_threshold=0.3)
    
    from src.thermal.thermal_reader import AMG8833Reader
    from src.thermal.thermal_mapper import assign_temperatures
    monitor.thermal_reader = AMG8833Reader()
    monitor.thermal_mapper = assign_temperatures
    
    from src.analytics.behavior_analyzer import BehaviorAnalyzer
    # class_id 0 maps to whatever is in cfg.classes[0]. Let's say it's "lying".
    monitor.behavior_analyzer = BehaviorAnalyzer(stationary_behaviors={"lying"})
    
    from src.health.risk_engine import HerdRiskEngine
    # 0 minute threshold! So it alerts immediately.
    monitor.risk_engine = HerdRiskEngine(
        repository=monitor.repository,
        stationary_behaviors={"lying"},
        stationary_alert_minutes=0.0, 
        fever_delta_threshold_c=1.0,
        cooldown_minutes=5
    )
    
    # Make sure classes match what tracker expects
    monitor.cfg.classes = {0: "lying", 1: "standing", 2: "walking"}
    
    # Wrap risk engine evaluate to debug it
    orig_eval = monitor.risk_engine.evaluate
    def debug_eval(*args, **kwargs):
        alerts = orig_eval(*args, **kwargs)
        if kwargs.get('active_tracks') or args:
            tracks = kwargs.get('active_tracks') or args[0]
            if tracks:
                print(f"[DebugEval] Track 1: beh={tracks[0].behavior}, dur={tracks[0].stationary_duration_sec}, temp={tracks[0].thermal_zone_temp}, thresh={monitor.risk_engine._alert_minutes}")
        if alerts:
            print(f"[DebugEval] ALERTS GENERATED: {alerts}")
        return alerts
    monitor.risk_engine.evaluate = debug_eval
    
    # Start the run loop in a background thread
    t = threading.Thread(target=monitor.run, daemon=True)
    t.start()
    
    print("[Test] Monitor loop running...")
    time.sleep(3.0) # Let it run for 3 seconds (approx 90 frames at 30fps)
    
    monitor.shutdown()
    t.join(timeout=2.0)
    
    # Validation
    alerts = monitor.repository.get_recent_alerts(limit=10)
    print(f"[Test] Found {len(alerts)} alerts in DB")
    if not alerts:
        # Debug tracker and analyzer
        print(f"[Test] Track count: {monitor.pig_counter._current_count}")
        print(f"[Test] Behavior stats: {list(monitor.behavior_analyzer._pop_history)}")
        for track in monitor.behavior_analyzer._tracks.values():
            print(f"[Test] Track {track.track_id}: behavior={track.behavior}, duration={track.stationary_duration_sec}, temp={track.thermal_zone_temp}")
    
    assert len(alerts) > 0, "No alerts were persisted to the database!"
    
    alert = alerts[0]
    print(f"Alert generated: {alert['alert_type']} at {alert['timestamp']}")
    
    snap_path = alert['snapshot_path']
    assert snap_path, "Snapshot path was not recorded in DB"
    
    snap_file = Path(snap_path)
    assert snap_file.exists(), f"Snapshot file {snap_file} does not exist!"
    
    import os
    size = os.path.getsize(snap_file)
    assert size > 0, "Snapshot file is empty!"
    
    print("\nSUCCESS: E2E Pipeline verified.")
    print(f"- Alert saved to DB: ID {alert['id']}")
    print(f"- Snapshot saved to disk: {snap_file.name} ({size} bytes)")

if __name__ == "__main__":
    run_test()
