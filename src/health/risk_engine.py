"""
src/health/risk_engine.py
Hybrid Herd-Level Health Risk Engine

PURPOSE:
    Implements the "Hybrid Option C" dual-channel anomaly detection system.

    Channel 1 — Individual Anomaly (SORT-based):
        Triggers when any single tracked object (temporary pig ID within session)
        is stationary (lying/sitting) for >= 15 minutes AND its thermal zone
        reads fever temperature (> ambient + 2.0°C delta).

    Channel 2 — Population Lethargy (Frame-based):
        Triggers when >= 60% of detected pigs are simultaneously stationary
        for 3+ consecutive seconds.

    THI Adaptive Thresholds:
        If the barn's Temperature Humidity Index > 78 (severe heat stress),
        the stationary timer is automatically extended to 30 minutes to avoid
        false positives (pigs are naturally more lethargic in extreme heat).

NOTE:
    Pig IDs here are SORT track_ids — temporary, session-scoped.
    We do NOT report "Pig #3 is sick" — we report "the pen is at risk."
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from enum import Enum
from typing import List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from src.analytics.behavior_analyzer import TrackState, PopulationSnapshot
    from src.hardware.dht22_sensor import AmbientReading

logger = logging.getLogger(__name__)


class AlertType(str, Enum):
    INDIVIDUAL = "individual"       # One stationary + fever pig detected
    POPULATION = "population"       # Herd-wide lethargy event


@dataclass
class AlertEvent:
    """Describes a triggered health alert event."""
    alert_type: AlertType
    trigger_reason: str
    ambient_temp_c: float
    ambient_rh: float
    ambient_thi: float
    pig_zone_temp_c: Optional[float]    # None for population alerts
    stationary_duration_sec: Optional[float]
    stationary_count: Optional[int]
    total_pig_count: Optional[int]
    timestamp: float = 0.0

    def __post_init__(self) -> None:
        if self.timestamp == 0.0:
            self.timestamp = time.time()

    def sms_message(self) -> str:
        """Format a concise SMS message (target < 160 chars)."""
        barn = f"{self.ambient_temp_c:.1f}C/{self.ambient_rh:.0f}%"
        if self.alert_type == AlertType.INDIVIDUAL:
            mins = int((self.stationary_duration_sec or 0) / 60)
            return (
                f"SWINE ALERT: Sick pig in pen. "
                f"Stationary {mins}m, Zone:{self.pig_zone_temp_c:.1f}C, "
                f"Barn:{barn}. Inspect now."
            )
        else:
            return (
                f"SWINE ALERT: Herd lethargy event. "
                f"{self.stationary_count}/{self.total_pig_count} pigs down. "
                f"Barn:{barn} THI:{self.ambient_thi:.1f}. Inspect pen."
            )


class HerdRiskEngine:
    """
    Hybrid dual-channel health risk engine.
    Evaluates per-track and population-level signals to detect pen-level risk.
    """

    def __init__(
        self,
        stationary_behaviors: Optional[List[str]] = None,
        stationary_alert_minutes: float = 15.0,
        stationary_heat_stress_minutes: float = 30.0,
        fever_delta_threshold_c: float = 2.0,
        population_lethargy_ratio: float = 0.60,
        population_persist_seconds: int = 3,
        thi_heat_stress_threshold: float = 78.0,
    ) -> None:
        self._stationary_behaviors = set(stationary_behaviors or {"lying", "sitting"})
        self._alert_minutes = stationary_alert_minutes
        self._heat_stress_minutes = stationary_heat_stress_minutes
        self._fever_delta = fever_delta_threshold_c
        self._pop_ratio = population_lethargy_ratio
        self._pop_persist = population_persist_seconds
        self._thi_threshold = thi_heat_stress_threshold

    def _get_stationary_threshold(self, ambient: Optional["AmbientReading"]) -> float:
        """Return the stationary threshold in seconds, adapted for THI."""
        if ambient and ambient.thi > self._thi_threshold:
            minutes = self._heat_stress_minutes
        else:
            minutes = self._alert_minutes
        return minutes * 60.0

    def evaluate(
        self,
        active_tracks: List["TrackState"],
        population_snapshot: "PopulationSnapshot",
        persistent_lethargy_ratio: float,
        ambient: Optional["AmbientReading"],
    ) -> List[AlertEvent]:
        """
        Evaluate all detection channels and return triggered alerts.
        Returns an empty list when everything is normal.
        """
        alerts: List[AlertEvent] = []
        ambient_temp = ambient.temp_c if ambient else 30.0
        ambient_rh = ambient.humidity_pct if ambient else 60.0
        ambient_thi = ambient.thi if ambient else 70.0

        threshold_sec = self._get_stationary_threshold(ambient)

        # ── Channel 1: Individual Anomaly ─────────────────────────────────────
        for track in active_tracks:
            if (
                track.behavior in self._stationary_behaviors
                and track.stationary_duration_sec >= threshold_sec
                and track.thermal_zone_temp > (ambient_temp + self._fever_delta)
            ):
                alerts.append(AlertEvent(
                    alert_type=AlertType.INDIVIDUAL,
                    trigger_reason="stationary_fever",
                    ambient_temp_c=ambient_temp,
                    ambient_rh=ambient_rh,
                    ambient_thi=ambient_thi,
                    pig_zone_temp_c=track.thermal_zone_temp,
                    stationary_duration_sec=track.stationary_duration_sec,
                    stationary_count=None,
                    total_pig_count=None,
                ))
                logger.warning(
                    f"[Channel 1] Track {track.track_id} stationary "
                    f"{track.stationary_duration_sec/60:.1f}m, "
                    f"zone {track.thermal_zone_temp:.1f}°C. ALERT."
                )
                break   # One alert per evaluation cycle is enough

        # ── Channel 2: Population Lethargy ────────────────────────────────────
        if (
            not alerts  # Don't double-alert in same cycle
            and persistent_lethargy_ratio >= self._pop_ratio
            and population_snapshot.total_detected >= 2  # Need at least 2 pigs to calc ratio
        ):
            alerts.append(AlertEvent(
                alert_type=AlertType.POPULATION,
                trigger_reason="herd_lethargy",
                ambient_temp_c=ambient_temp,
                ambient_rh=ambient_rh,
                ambient_thi=ambient_thi,
                pig_zone_temp_c=None,
                stationary_duration_sec=None,
                stationary_count=population_snapshot.stationary_count,
                total_pig_count=population_snapshot.total_detected,
            ))
            logger.warning(
                f"[Channel 2] {population_snapshot.stationary_count}/"
                f"{population_snapshot.total_detected} pigs stationary. ALERT."
            )

        return alerts
