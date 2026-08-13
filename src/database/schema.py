"""
src/database/schema.py
SQLite Schema Definitions

PURPOSE:
    Defines the SQLite database schema for offline tracking.
    Initializes tables if they do not exist and applies
    forward migrations via PRAGMA user_version.
"""

import logging
import sqlite3
from pathlib import Path

logger = logging.getLogger(__name__)

SCHEMA_SQL = """
-- Ambient sensor readings from DHT22
CREATE TABLE IF NOT EXISTS ambient_readings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    temp_c REAL,
    humidity_pct REAL,
    thi REAL
);

-- Pen-level health alert events
CREATE TABLE IF NOT EXISTS pen_alerts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    alert_type TEXT NOT NULL,       -- "individual" | "population"
    trigger_reason TEXT,            -- e.g., "stationary_fever", "herd_lethargy"
    ambient_temp_c REAL,
    ambient_rh REAL,
    ambient_thi REAL,
    pig_zone_temp_c REAL,
    stationary_duration_sec REAL,
    stationary_count INTEGER,
    total_pig_count INTEGER,
    sms_sent INTEGER DEFAULT 0,
    sms_recipients TEXT,            -- JSON list of numbers SMS was sent to
    resolved INTEGER DEFAULT 0,
    snapshot_path TEXT
);

-- Raw detection logs (sampled periodically for analytics)
CREATE TABLE IF NOT EXISTS detections (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    track_id INTEGER,
    behavior TEXT,
    confidence REAL,
    box_x1 INTEGER,
    box_y1 INTEGER,
    box_x2 INTEGER,
    box_y2 INTEGER,
    zone_temp_c REAL
);

-- Alert recipients (phone numbers for SMS dispatch)
CREATE TABLE IF NOT EXISTS alert_recipients (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    phone_number TEXT NOT NULL UNIQUE,
    enabled INTEGER DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

-- Alert system configuration (editable via dashboard)
CREATE TABLE IF NOT EXISTS alert_config (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    data_type TEXT,          -- 'float' | 'int' | 'string' | 'bool'
    description TEXT,
    updated_at TEXT NOT NULL
);

-- SMS message templates (for customizing alert notifications)
CREATE TABLE IF NOT EXISTS sms_templates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    alert_type TEXT NOT NULL,          -- 'individual' | 'population'
    name TEXT NOT NULL UNIQUE,         -- Template name (e.g., "Individual Fever Alert")
    message_body TEXT NOT NULL,        -- Message template with {variables}
    enabled INTEGER DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

-- SMS message send logs (history of all SMS alerts sent)
CREATE TABLE IF NOT EXISTS sms_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    alert_type TEXT NOT NULL,         -- 'individual' | 'population'
    recipient_phone TEXT NOT NULL,
    message_body TEXT NOT NULL,
    status TEXT DEFAULT 'sent',       -- 'sent' | 'failed' | 'pending'
    error_message TEXT,
    pen_alert_id INTEGER,             -- Reference to pen_alerts table
    FOREIGN KEY(pen_alert_id) REFERENCES pen_alerts(id)
);

-- System time sync log (for tracking AP time synchronization)
CREATE TABLE IF NOT EXISTS time_sync_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    source_type TEXT,                 -- 'manual' | 'ntp' | 'phone' | 'ap'
    source_ip TEXT,
    old_time TEXT,
    new_time TEXT,
    status TEXT DEFAULT 'success'    -- 'success' | 'failed'
);
"""

# ── Forward migrations ──────────────────────────────────────────────────────
# Applied in order after the base schema. Each entry is a SQL script.
# Never edit an existing entry — append a new one.
MIGRATIONS: list[str] = [
    # v1: performance indexes for timestamp-based retention pruning & queries.
    """
    CREATE INDEX IF NOT EXISTS idx_detections_timestamp ON detections(timestamp);
    CREATE INDEX IF NOT EXISTS idx_ambient_timestamp ON ambient_readings(timestamp);
    CREATE INDEX IF NOT EXISTS idx_pen_alerts_timestamp ON pen_alerts(timestamp);
    CREATE INDEX IF NOT EXISTS idx_sms_logs_timestamp ON sms_logs(timestamp);
    """,
]

SCHEMA_VERSION = len(MIGRATIONS)


def _apply_migrations(conn: sqlite3.Connection) -> None:
    """Apply pending forward migrations recorded in PRAGMA user_version."""
    current = conn.execute("PRAGMA user_version").fetchone()[0]
    if current < 0:
        current = 0
    for i in range(current + 1, len(MIGRATIONS) + 1):
        script = MIGRATIONS[i - 1]
        conn.executescript(script)
        conn.execute(f"PRAGMA user_version = {i}")
        logger.info("Applied database migration v%d", i)


def initialize_database(db_path: str | Path) -> None:
    """Create database tables if they do not exist and apply migrations."""
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        with sqlite3.connect(db_path, timeout=10.0) as conn:
            # Enable WAL mode for better concurrency (dashboard reads while inference writes)
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute("PRAGMA foreign_keys=ON;")
            conn.execute("PRAGMA busy_timeout=5000;")
            conn.executescript(SCHEMA_SQL)
            _apply_migrations(conn)
        logger.info("Database initialized at %s (schema v%d)", db_path, SCHEMA_VERSION)
    except sqlite3.Error as e:
        logger.error("Failed to initialize database: %s", e)
        raise
