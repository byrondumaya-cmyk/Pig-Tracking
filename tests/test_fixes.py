"""
tests/test_fixes.py
Verification tests for the stabilization pass.

Run with: python -m pytest tests/ -v
"""

import json
import sys
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

# Ensure project root is on the path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


# ── Test 1: sms_message() does not crash when pig_zone_temp_c is None ─────────

def test_sms_message_individual_with_none_zone_temp():
    """Bug 6 fix: AlertEvent.sms_message() must not crash when pig_zone_temp_c is None."""
    from src.health.risk_engine import AlertEvent, AlertType

    event = AlertEvent(
        alert_type=AlertType.INDIVIDUAL,
        trigger_reason="stationary_fever",
        ambient_temp_c=30.0,
        ambient_rh=70.0,
        ambient_thi=75.0,
        pig_zone_temp_c=None,          # Thermal unavailable
        stationary_duration_sec=960.0,
        stationary_count=None,
        total_pig_count=None,
    )
    msg = event.sms_message()
    assert "N/A" in msg, f"Expected 'N/A' in SMS, got: {msg}"
    assert "SWINE ALERT" in msg


def test_sms_message_population_alert():
    """Population alerts must format correctly."""
    from src.health.risk_engine import AlertEvent, AlertType

    event = AlertEvent(
        alert_type=AlertType.POPULATION,
        trigger_reason="herd_lethargy",
        ambient_temp_c=32.0,
        ambient_rh=80.0,
        ambient_thi=79.0,
        pig_zone_temp_c=None,
        stationary_duration_sec=None,
        stationary_count=4,
        total_pig_count=6,
    )
    msg = event.sms_message()
    assert "4/6" in msg
    assert "SWINE ALERT" in msg


# ── Test 2: Engine-level cooldown prevents repeated alerts ────────────────────

def test_risk_engine_cooldown_suppresses_repeat_alerts():
    """Bug 5 fix: HerdRiskEngine must not emit the same alert within cooldown window."""
    from src.health.risk_engine import HerdRiskEngine
    from src.analytics.behavior_analyzer import TrackState, PopulationSnapshot

    engine = HerdRiskEngine(
        stationary_behaviors=["lying"],
        stationary_alert_minutes=0.0,   # Trigger immediately
        fever_delta_threshold_c=0.0,    # Any temp triggers fever
        cooldown_minutes=60,            # Long cooldown
    )

    # Mock a track that would trigger an individual alert
    track = MagicMock()
    track.behavior = "lying"
    track.stationary_duration_sec = 9999.0
    track.thermal_zone_temp = 99.0

    ambient = MagicMock()
    ambient.thi = 70.0
    ambient.temp_c = 30.0
    ambient.humidity_pct = 60.0

    snap = PopulationSnapshot(total_detected=1, stationary_count=1)

    alerts_first = engine.evaluate([track], snap, 0.0, ambient)
    alerts_second = engine.evaluate([track], snap, 0.0, ambient)  # Should be suppressed

    assert len(alerts_first) == 1, "First evaluation should produce an alert"
    assert len(alerts_second) == 0, "Second evaluation within cooldown window must be suppressed"


# ── Test 3: ThermalBuffer and BehaviorBuffer thread safety ────────────────────

def test_thermal_buffer_roundtrip():
    """Bug 3 fix: ThermalBuffer must accept numpy array and return list."""
    import numpy as np
    from src.dashboard.stream import ThermalBuffer

    grid = np.random.uniform(28.0, 40.0, (8, 8))
    ThermalBuffer.update(grid)
    result = ThermalBuffer.read()

    assert result is not None, "ThermalBuffer.read() returned None after update"
    assert len(result) == 8, "Grid must have 8 rows"
    assert len(result[0]) == 8, "Grid must have 8 columns"


def test_behavior_buffer_roundtrip():
    """Bug 4 fix: BehaviorBuffer must return correct live counts."""
    from src.dashboard.stream import BehaviorBuffer

    counts = {"lying": 2, "walking": 1, "standing": 3}
    BehaviorBuffer.update(counts, total=6)
    result = BehaviorBuffer.read()

    assert result["lying"] == 2
    assert result["walking"] == 1
    assert result["total"] == 6


def test_behavior_buffer_returns_zeros_when_empty():
    """BehaviorBuffer.read() on a fresh state returns a usable dict."""
    from src.dashboard.stream import BehaviorBuffer
    # Reset buffer
    BehaviorBuffer.update({}, 0)
    result = BehaviorBuffer.read()
    assert result.get("total", 0) == 0


# ── Test 4: Repository mark_sms_sent does not set resolved=1 ─────────────────

def test_mark_sms_sent_does_not_resolve_alert(tmp_path):
    """Bug 2 fix: mark_sms_sent() must NOT set resolved=1."""
    import sqlite3
    from src.database.schema import initialize_database
    from src.database.repository import SwineRepository

    db = tmp_path / "test.db"
    initialize_database(db)
    repo = SwineRepository(db)

    alert_id = repo.insert_alert(
        alert_type="individual",
        trigger_reason="stationary_fever",
        ambient_temp_c=30.0,
        ambient_rh=70.0,
        ambient_thi=75.0,
    )

    repo.mark_sms_sent(alert_id, ["+63XXXXXXXXXX"])

    with sqlite3.connect(db) as con:
        row = con.execute(
            "SELECT sms_sent, resolved, sms_recipients FROM pen_alerts WHERE id=?",
            (alert_id,)
        ).fetchone()

    sms_sent, resolved, recipients_json = row
    assert sms_sent == 1, "sms_sent must be 1 after mark_sms_sent()"
    assert resolved == 0, "resolved must stay 0 — farmer has not inspected yet"
    recipients = json.loads(recipients_json)
    assert "+63XXXXXXXXXX" in recipients


def test_resolve_alert_sets_resolved(tmp_path):
    """resolve_alert() must set resolved=1 independently of sms_sent."""
    import sqlite3
    from src.database.schema import initialize_database
    from src.database.repository import SwineRepository

    db = tmp_path / "test.db"
    initialize_database(db)
    repo = SwineRepository(db)

    alert_id = repo.insert_alert(
        alert_type="population",
        trigger_reason="herd_lethargy",
        ambient_temp_c=32.0,
        ambient_rh=80.0,
        ambient_thi=79.0,
    )

    repo.mark_sms_sent(alert_id)
    repo.resolve_alert(alert_id)

    with sqlite3.connect(db) as con:
        row = con.execute(
            "SELECT sms_sent, resolved FROM pen_alerts WHERE id=?",
            (alert_id,)
        ).fetchone()

    sms_sent, resolved = row
    assert sms_sent == 1
    assert resolved == 1


def test_detector_raises_when_input_size_mismatches_model():
    """PigDetector should validate config input_size against the ONNX model."""
    from src.config_loader import load_config
    from src.inference.detector import PigDetector

    cfg = load_config()
    wrong_size = cfg.inference.input_size + 1
    try:
        PigDetector(
            model_path=cfg.inference.model_path,
            input_size=wrong_size,
            confidence_threshold=cfg.inference.confidence_threshold,
            iou_threshold=cfg.inference.iou_threshold,
            intra_op_threads=cfg.inference.intra_op_threads,
            inter_op_threads=cfg.inference.inter_op_threads,
        )
        assert False, "PigDetector instantiated with wrong input_size and should have raised ValueError"
    except ValueError as exc:
        assert "input_size" in str(exc)


# ── Test 5: config_loader loads without crashing ─────────────────────────────

def test_config_loads_successfully():
    """Config loader must produce an AppConfig without errors."""
    from src.config_loader import load_config, AppConfig
    cfg = load_config()
    assert isinstance(cfg, AppConfig)
    assert len(cfg.classes) == 8  # 8 canonical pig behavior classes
    assert cfg.thermal.i2c_bus == 1
    assert cfg.health.cooldown_minutes == 5
