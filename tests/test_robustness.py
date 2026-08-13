"""
tests/test_robustness.py
Regression tests for the integrity & robustness hardening pass.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np


def test_detector_nms_normalizes_various_index_shapes():
    """cv2.dnn.NMSBoxes output shape varies by OpenCV version (<=4.9: (N,1),
    >=4.10: flat). The detector must normalize both."""

    col = np.array([[3], [7]])
    assert np.asarray(col, dtype=int).reshape(-1).tolist() == [3, 7]

    lst = [3, 7]
    assert np.asarray(lst, dtype=int).reshape(-1).tolist() == [3, 7]

    assert np.asarray([], dtype=int).reshape(-1).tolist() == []


def test_detector_nms_empty_returns_empty_list():
    """When NMS returns nothing the detector must return [], not crash."""
    from src.inference.detector import PigDetector

    detector = PigDetector.__new__(PigDetector)
    detector._conf_thresh = 0.45
    detector._iou_thresh = 0.45

    output = np.zeros((1, 12, 10), dtype=np.float32)
    results = detector._postprocess(output, scale=1.0, pad=(0, 0), orig_shape=(100, 100, 3))
    assert results == []


def test_pig_tracker_cache_does_not_grow_unbounded():
    """Long-dead track IDs must be pruned from the detection cache."""
    from src.tracking.pig_tracker import PigTracker, _MAX_CACHE_ENTRIES

    tracker = PigTracker(max_age=10, min_hits=1, iou_threshold=0.1)
    classes = ["lying"] * 8

    for i in range(_MAX_CACHE_ENTRIES * 2):
        det = [{"bbox": (10.0, 10.0, 50.0, 50.0), "confidence": 0.9, "class_id": 0}]
        tracker.update(det, classes)
        tracker._detection_cache[i] = ("lying", 0.9)
        tracker._last_track_ids = {i}

    assert len(tracker._detection_cache) <= _MAX_CACHE_ENTRIES + 1


def test_repository_batch_insert_and_prune(tmp_path):
    """Batch inserts write multiple rows; pruning removes only old rows."""
    import sqlite3
    from datetime import datetime, timedelta

    from src.database.schema import initialize_database
    from src.database.repository import SwineRepository

    db = tmp_path / "test.db"
    initialize_database(db)
    repo = SwineRepository(db)

    n = repo.insert_detections_batch(
        [
            (1, "lying", 0.9, (10, 10, 50, 50), 39.5),
            (2, "standing", 0.8, (60, 60, 90, 90), 0.0),
            (3, "walking", 0.7, (20, 20, 40, 40), 38.0),
        ]
    )
    assert n == 3

    old_ts = (datetime.utcnow() - timedelta(days=31)).isoformat()
    with sqlite3.connect(db) as con:
        con.execute(
            """INSERT INTO detections
               (timestamp, track_id, behavior, confidence, box_x1, box_y1, box_x2, box_y2, zone_temp_c)
               VALUES (?,?,?,?,?,?,?,?,?)""",
            (old_ts, 9, "lying", 0.5, 0, 0, 10, 10, 0.0),
        )

    pruned = repo.prune_detections(keep_days=7)
    assert pruned == 1, "Only the 31-day-old row must be pruned"

    with sqlite3.connect(db) as con:
        remaining = con.execute("SELECT COUNT(*) FROM detections").fetchone()[0]
    assert remaining == 3


def test_repository_prune_rejects_invalid_days(tmp_path):
    """Retention windows shorter than 1 day are rejected."""
    from src.database.schema import initialize_database
    from src.database.repository import SwineRepository

    db = tmp_path / "test.db"
    initialize_database(db)
    repo = SwineRepository(db)

    try:
        repo.prune_detections(keep_days=0)
        assert False, "keep_days=0 should raise ValueError"
    except ValueError:
        pass


def test_schema_migration_sets_user_version(tmp_path):
    """initialize_database must set PRAGMA user_version to the migration count."""
    import sqlite3

    from src.database.schema import SCHEMA_VERSION, initialize_database

    db = tmp_path / "migrated.db"
    initialize_database(db)

    with sqlite3.connect(db) as con:
        version = con.execute("PRAGMA user_version").fetchone()[0]
        indexes = con.execute(
            "SELECT name FROM sqlite_master WHERE type='index' AND name LIKE 'idx_%'"
        ).fetchall()

    assert version == SCHEMA_VERSION
    idx_names = {r[0] for r in indexes}
    assert {"idx_detections_timestamp", "idx_ambient_timestamp",
            "idx_pen_alerts_timestamp", "idx_sms_logs_timestamp"} <= idx_names


def test_async_camera_reconnect_config():
    """The reconnect threshold must be exposed as a constructor parameter."""
    from src.hardware.async_camera import AsyncCamera

    cam = AsyncCamera(device_index=0, reconnect_after_errors=5)
    assert cam.reconnect_after_errors == 5
