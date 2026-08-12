"""
src/database/repository.py
Typed SQLite Repository — CRUD Operations

PURPOSE:
    Provides clean, typed read/write functions for all database tables.
    Uses WAL mode (set in schema.py init) for concurrent read+write safety.
    All writes use context managers to auto-commit/rollback.
"""

from __future__ import annotations

import json
import logging
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Generator, Optional

logger = logging.getLogger(__name__)


def _ts() -> str:
    """Return current UTC timestamp as ISO 8601 string."""
    return datetime.utcnow().isoformat()


@contextmanager
def _conn(db_path: Path) -> Generator[sqlite3.Connection, None, None]:
    """Thread-safe context manager for SQLite connections."""
    con = sqlite3.connect(db_path, check_same_thread=False)
    con.row_factory = sqlite3.Row
    try:
        yield con
        con.commit()
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()


class SwineRepository:
    """
    Central data access layer for the Swine Health Monitor.
    All database operations go through this class.
    """

    def __init__(self, db_path: Path | str) -> None:
        self._path = Path(db_path)

    # ── Ambient Readings ────────────────────────────────────────────────

    def insert_ambient(self, temp_c: float, humidity_pct: float, thi: float) -> None:
        """Insert one DHT22 ambient reading."""
        with _conn(self._path) as con:
            con.execute(
                "INSERT INTO ambient_readings (timestamp, temp_c, humidity_pct, thi) VALUES (?,?,?,?)",
                (_ts(), temp_c, humidity_pct, thi),
            )

    def get_latest_ambient(self) -> Optional[dict]:
        """Return the most recent ambient reading."""
        with _conn(self._path) as con:
            row = con.execute(
                "SELECT * FROM ambient_readings ORDER BY id DESC LIMIT 1"
            ).fetchone()
            return dict(row) if row else None

    # ── Detections ──────────────────────────────────────────────────────

    def insert_detection(
        self,
        track_id: int,
        behavior: str,
        confidence: float,
        bbox: tuple,          # (x1, y1, x2, y2)
        zone_temp_c: float = 0.0,
    ) -> None:
        """Insert one detection record."""
        x1, y1, x2, y2 = bbox
        with _conn(self._path) as con:
            con.execute(
                """INSERT INTO detections
                   (timestamp, track_id, behavior, confidence, box_x1, box_y1, box_x2, box_y2, zone_temp_c)
                   VALUES (?,?,?,?,?,?,?,?,?)""",
                (_ts(), track_id, behavior, confidence, x1, y1, x2, y2, zone_temp_c),
            )

    # ── Pen Alerts ──────────────────────────────────────────────────────

    def insert_alert(
        self,
        alert_type: str,
        trigger_reason: str,
        ambient_temp_c: float,
        ambient_rh: float,
        ambient_thi: float,
        pig_zone_temp_c: Optional[float] = None,
        stationary_duration_sec: Optional[float] = None,
        stationary_count: Optional[int] = None,
        total_pig_count: Optional[int] = None,
        sms_sent: bool = False,
        sms_recipients: Optional[list] = None,
        snapshot_path: Optional[str] = None,
    ) -> int:
        """Insert a pen alert and return the new row id."""
        recipients_json = json.dumps(sms_recipients or [])
        with _conn(self._path) as con:
            cur = con.execute(
                """INSERT INTO pen_alerts
                   (timestamp, alert_type, trigger_reason,
                    ambient_temp_c, ambient_rh, ambient_thi,
                    pig_zone_temp_c, stationary_duration_sec,
                    stationary_count, total_pig_count,
                    sms_sent, sms_recipients, snapshot_path)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    _ts(), alert_type, trigger_reason,
                    ambient_temp_c, ambient_rh, ambient_thi,
                    pig_zone_temp_c, stationary_duration_sec,
                    stationary_count, total_pig_count,
                    int(sms_sent), recipients_json, snapshot_path,
                ),
            )
            return cur.lastrowid

    def get_recent_alerts(self, limit: int = 20) -> list[dict]:
        """Return recent alerts ordered by newest first."""
        with _conn(self._path) as con:
            rows = con.execute(
                "SELECT * FROM pen_alerts ORDER BY id DESC LIMIT ?", (limit,)
            ).fetchall()
            return [dict(r) for r in rows]

    def mark_sms_sent(self, alert_id: int, recipients: Optional[list] = None) -> None:
        """
        Mark an alert as having had an SMS dispatched.
        Sets sms_sent=1 and records recipient numbers.
        Does NOT set resolved — that requires farmer confirmation via the dashboard.
        """
        recipients_json = json.dumps(recipients or [])
        with _conn(self._path) as con:
            con.execute(
                "UPDATE pen_alerts SET sms_sent = 1, sms_recipients = ? WHERE id = ?",
                (recipients_json, alert_id),
            )

    def resolve_alert(self, alert_id: int) -> None:
        """
        Mark an alert as resolved (farmer has physically inspected the pen).
        Called via dashboard UI — NOT automatically after SMS.
        """
        with _conn(self._path) as con:
            con.execute(
                "UPDATE pen_alerts SET resolved = 1 WHERE id = ?", (alert_id,)
            )

    def has_unresolved_alerts(self) -> bool:
        """Return True if any alert is unresolved."""
        with _conn(self._path) as con:
            row = con.execute(
                "SELECT COUNT(*) FROM pen_alerts WHERE resolved = 0"
            ).fetchone()
            return row[0] > 0

    # ── Alert Recipients ────────────────────────────────────────────────

    def add_recipient(self, phone_number: str) -> int:
        """Add a new alert recipient. Returns the new row id."""
        with _conn(self._path) as con:
            cur = con.execute(
                """INSERT INTO alert_recipients (phone_number, enabled, created_at, updated_at)
                   VALUES (?,?,?,?)""",
                (phone_number, 1, _ts(), _ts()),
            )
            return cur.lastrowid

    def remove_recipient(self, recipient_id: int) -> None:
        """Delete a recipient by id."""
        with _conn(self._path) as con:
            con.execute("DELETE FROM alert_recipients WHERE id = ?", (recipient_id,))

    def get_all_recipients(self) -> list[dict]:
        """Return all recipients (enabled and disabled)."""
        with _conn(self._path) as con:
            rows = con.execute(
                "SELECT id, phone_number, enabled FROM alert_recipients ORDER BY id"
            ).fetchall()
            return [dict(r) for r in rows]

    def get_enabled_recipients(self) -> list[str]:
        """Return list of enabled phone numbers (for SMS dispatch)."""
        with _conn(self._path) as con:
            rows = con.execute(
                "SELECT phone_number FROM alert_recipients WHERE enabled = 1 ORDER BY id"
            ).fetchall()
            return [r["phone_number"] for r in rows]

    def toggle_recipient(self, recipient_id: int, enabled: bool) -> None:
        """Enable or disable a recipient."""
        with _conn(self._path) as con:
            con.execute(
                "UPDATE alert_recipients SET enabled = ?, updated_at = ? WHERE id = ?",
                (int(enabled), _ts(), recipient_id),
            )

    # ── Alert Configuration ────────────────────────────────────────────────

    def set_alert_config(self, key: str, value: str, data_type: str = "string", description: str = "") -> None:
        """Set or update an alert configuration parameter."""
        with _conn(self._path) as con:
            con.execute(
                """INSERT OR REPLACE INTO alert_config (key, value, data_type, description, updated_at)
                   VALUES (?,?,?,?,?)""",
                (key, value, data_type, description, _ts()),
            )

    def get_alert_config(self, key: str, default: str = "") -> str:
        """Get an alert configuration parameter."""
        with _conn(self._path) as con:
            row = con.execute(
                "SELECT value FROM alert_config WHERE key = ?", (key,)
            ).fetchone()
            return row["value"] if row else default

    def get_all_alert_config(self) -> dict:
        """Return all alert configuration as a dict."""
        with _conn(self._path) as con:
            rows = con.execute(
                "SELECT key, value, data_type FROM alert_config ORDER BY key"
            ).fetchall()
            result = {}
            for row in rows:
                key, value, dtype = row["key"], row["value"], row["data_type"]
                # Parse value by type
                if dtype == "float":
                    result[key] = float(value)
                elif dtype == "int":
                    result[key] = int(value)
                elif dtype == "bool":
                    result[key] = value.lower() in ("1", "true", "yes")
                else:
                    result[key] = value
            return result

    def get_herd_risk_engine_config(self) -> dict:
        """
        Load HerdRiskEngine configuration from database with built-in defaults.
        Used to initialize HerdRiskEngine at runtime.
        """
        defaults = {
            "stationary_alert_minutes": 15.0,
            "stationary_heat_stress_minutes": 30.0,
            "fever_delta_threshold_c": 2.0,
            "population_lethargy_ratio": 0.60,
            "population_persist_seconds": 3,
            "thi_heat_stress_threshold": 78.0,
            "cooldown_minutes": 5,
            "alert_individual_enabled": True,
            "alert_population_enabled": True,
        }
        
        config = self.get_all_alert_config()
        
        # Merge with defaults
        result = {}
        for key, default_value in defaults.items():
            if key in config:
                result[key] = config[key]
            else:
                result[key] = default_value
        
        return result

    def set_herd_risk_engine_config(self, config_dict: dict) -> None:
        """
        Save HerdRiskEngine configuration to database.
        Persists all engine parameters for runtime loading.
        """
        type_map = {
            "stationary_alert_minutes": "float",
            "stationary_heat_stress_minutes": "float",
            "fever_delta_threshold_c": "float",
            "population_lethargy_ratio": "float",
            "population_persist_seconds": "int",
            "thi_heat_stress_threshold": "float",
            "cooldown_minutes": "int",
            "alert_individual_enabled": "bool",
            "alert_population_enabled": "bool",
        }
        
        descriptions = {
            "stationary_alert_minutes": "Minutes before triggering individual sick pig alert",
            "stationary_heat_stress_minutes": "Extended alert time when THI > threshold",
            "fever_delta_threshold_c": "Temperature delta (C) to trigger fever alert",
            "population_lethargy_ratio": "Ratio of pigs stationary to trigger population alert",
            "population_persist_seconds": "Duration for population alert persistence",
            "thi_heat_stress_threshold": "Temperature Humidity Index heat stress threshold",
            "cooldown_minutes": "Minutes between repeated alerts of same type",
            "alert_individual_enabled": "Enable/disable individual pig fever alerts",
            "alert_population_enabled": "Enable/disable population lethargy alerts",
        }
        
        for key, value in config_dict.items():
            if key in type_map:
                data_type = type_map[key]
                description = descriptions.get(key, "")
                # Convert value to string for storage
                if isinstance(value, bool):
                    value_str = "1" if value else "0"
                else:
                    value_str = str(value)
                self.set_alert_config(key, value_str, data_type, description)

    def initialize_default_alert_config(self) -> None:
        """Initialize alert_config table with default values if empty."""
        config = self.get_all_alert_config()
        if not config:
            defaults = {
                "stationary_alert_minutes": 15.0,
                "stationary_heat_stress_minutes": 30.0,
                "fever_delta_threshold_c": 2.0,
                "population_lethargy_ratio": 0.60,
                "population_persist_seconds": 3,
                "thi_heat_stress_threshold": 78.0,
                "cooldown_minutes": 5,
                "alert_individual_enabled": True,
                "alert_population_enabled": True,
            }
            self.set_herd_risk_engine_config(defaults)
