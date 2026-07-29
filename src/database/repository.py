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
