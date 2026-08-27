"""
Shared configuration loader for the Swine Health Monitor.

Loads config/config.yaml once and exposes it as a typed
dataclass hierarchy so every module gets IDE autocompletion
and catches typos at import time rather than at runtime.
"""

from __future__ import annotations

import typing
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, get_type_hints

import yaml


# ── Locate project root (parent of this file's directory) ──────────────
PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = PROJECT_ROOT / "config" / "config.yaml"


# ── Typed config dataclasses ────────────────────────────────────────────

@dataclass
class CameraConfig:
    device_index: int = 0
    width: int = 640
    height: int = 480
    fps: int = 30
    flip_horizontal: bool = False
    flip_vertical: bool = False


@dataclass
class InferenceConfig:
    model_path: str = "models/best.onnx"
    confidence_threshold: float = 0.45
    iou_threshold: float = 0.45
    input_size: int = 640
    frame_skip: int = 1
    intra_op_threads: int = 4
    inter_op_threads: int = 1


@dataclass
class TrackingConfig:
    max_age: int = 30
    min_hits: int = 3
    iou_threshold: float = 0.3


@dataclass
class ThermalConfig:
    enabled: bool = True
    i2c_bus: int = 1
    i2c_address: int = 0x69
    refresh_hz: int = 10
    normal_range: list[float] = field(default_factory=lambda: [35.0, 39.5])
    alert_temp_celsius: float = 40.0
    zone_cols: int = 8
    zone_rows: int = 8


@dataclass
class DHT22Config:
    enabled: bool = True
    gpio_pin: int = 4
    sample_rate_sec: int = 30


@dataclass
class GSMConfig:
    enabled: bool = True
    serial_port: str = "/dev/serial0"
    baud_rate: int = 9600
    phone_numbers: list = field(default_factory=list)
    cooldown_minutes: int = 5


@dataclass
class HybridHealthConfig:
    """Hybrid Risk Engine thresholds (replaces old weighted-score model)."""
    stationary_behaviors: list = field(default_factory=lambda: ["lying", "sitting"])
    stationary_alert_minutes: float = 15.0
    stationary_heat_stress_minutes: float = 30.0
    fever_delta_threshold_c: float = 2.0
    population_lethargy_ratio: float = 0.60
    population_persist_seconds: int = 3
    thi_heat_stress_threshold: float = 78.0
    cooldown_minutes: int = 5
    save_snapshot_on_alert: bool = True
    snapshot_dir: str = "data/snapshots"


@dataclass
class DatabaseConfig:
    path: str = "data/swine_health.db"
    wal_mode: bool = True
    flush_interval_seconds: int = 5


@dataclass
class StorageConfig:
    detections_retention_days: int = 7
    ambient_retention_days: int = 30
    snapshots_retention_days: int = 7


@dataclass
class DashboardConfig:
    host: str = "0.0.0.0"
    port: int = 5000
    debug: bool = False
    stream_jpeg_quality: int = 70
    chart_window_minutes: int = 30
    developer_password: str = "CHANGE_ME"  # Must be set securely before deployment


@dataclass
class SystemConfig:
    name: str = "Swine Health Monitor"
    version: str = "1.0.0"
    log_level: str = "INFO"


@dataclass
class APConfig:
    ssid: str = "PigMonitor_AP"
    password: str = "CHANGE_ME"     # Must be set in config.yaml before deployment
    country_code: str = "PH"
    ip: str = "192.168.4.1"
    subnet: str = "192.168.4.0/24"


@dataclass
class NetworkConfig:
    mode: str = "lan"
    ap: APConfig = field(default_factory=APConfig)


@dataclass
class AppConfig:
    """Root configuration object — access all settings from here."""
    system: SystemConfig = field(default_factory=SystemConfig)
    camera: CameraConfig = field(default_factory=CameraConfig)
    inference: InferenceConfig = field(default_factory=InferenceConfig)
    tracking: TrackingConfig = field(default_factory=TrackingConfig)
    thermal: ThermalConfig = field(default_factory=ThermalConfig)
    dht22: DHT22Config = field(default_factory=DHT22Config)
    gsm: GSMConfig = field(default_factory=GSMConfig)
    health: HybridHealthConfig = field(default_factory=HybridHealthConfig)
    database: DatabaseConfig = field(default_factory=DatabaseConfig)
    storage: StorageConfig = field(default_factory=StorageConfig)
    dashboard: DashboardConfig = field(default_factory=DashboardConfig)
    network: NetworkConfig = field(default_factory=NetworkConfig)
    classes: list = field(default_factory=list)


# ── Loader ──────────────────────────────────────────────────────────────

def _dict_to_dataclass(cls, data: dict):
    """
    Recursively hydrate a dataclass from a dict, ignoring unknown keys.

    Uses typing.get_type_hints() to resolve string annotations introduced by
    `from __future__ import annotations` (PEP 563) back to actual class objects
    so that nested dataclasses are correctly detected and hydrated.
    """
    if not isinstance(data, dict):
        return data

    # Resolve forward references / PEP 563 string annotations to real types
    try:
        type_hints = get_type_hints(cls)
    except Exception:
        type_hints = {f.name: f.type for f in cls.__dataclass_fields__.values()}

    kwargs = {}
    for f in cls.__dataclass_fields__.values():
        if f.name not in data:
            continue
        val = data[f.name]
        resolved_type = type_hints.get(f.name)
        # Recurse into nested dataclasses
        if (
            resolved_type is not None
            and hasattr(resolved_type, "__dataclass_fields__")
            and isinstance(val, dict)
        ):
            kwargs[f.name] = _dict_to_dataclass(resolved_type, val)
        else:
            kwargs[f.name] = val
    return cls(**kwargs)


def load_config(path: Optional[Path] = None) -> AppConfig:
    """Load and parse config.yaml into a typed AppConfig object.

    Args:
        path: Optional custom path to config YAML. Defaults to
              config/config.yaml relative to project root.

    Returns:
        Fully populated AppConfig dataclass.

    Raises:
        FileNotFoundError: If the config file does not exist.
        yaml.YAMLError: If the config file contains invalid YAML.
    """
    config_path = path or CONFIG_PATH
    if not config_path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")

    with open(config_path, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f)

    cfg = AppConfig()

    # Hydrate each section if present
    # Sections with direct dataclass mapping
    simple_sections = {
        "system": SystemConfig,
        "camera": CameraConfig,
        "inference": InferenceConfig,
        "tracking": TrackingConfig,
        "thermal": ThermalConfig,
        "database": DatabaseConfig,
        "storage": StorageConfig,
        "dashboard": DashboardConfig,
    }
    for key, cls in simple_sections.items():
        if key in raw:
            setattr(cfg, key, _dict_to_dataclass(cls, raw[key]))

    # DHT22 config
    if "dht22" in raw:
        cfg.dht22 = _dict_to_dataclass(DHT22Config, raw["dht22"])

    # GSM config
    if "gsm" in raw:
        cfg.gsm = _dict_to_dataclass(GSMConfig, raw["gsm"])

    # Hybrid Health config (replaces old weighted model)
    if "health" in raw:
        cfg.health = _dict_to_dataclass(HybridHealthConfig, raw["health"])

    # Network config (has nested AP config)
    if "network" in raw:
        n = raw["network"]
        ap = APConfig(**n.get("ap", {}))
        cfg.network = NetworkConfig(mode=n.get("mode", "lan"), ap=ap)

    cfg.classes = raw.get("classes", [])
    return cfg


# ── Module-level singleton (import once, use everywhere) ────────────────────
config: AppConfig = load_config()
