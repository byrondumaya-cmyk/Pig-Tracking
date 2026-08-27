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
    formatted_sms: Optional[str] = None

    def __post_init__(self) -> None:
        if self.timestamp == 0.0:
            self.timestamp = time.time()

    def sms_message(self, custom_template: Optional[str] = None) -> str:
        """Format a concise SMS message (target < 160 chars)."""
        barn = f"{self.ambient_temp_c:.1f}C/{self.ambient_rh:.0f}%"
        mins = int((self.stationary_duration_sec or 0) / 60)
        zone_str = f"{self.pig_zone_temp_c:.1f}C" if self.pig_zone_temp_c is not None else "N/A"
        
        if custom_template:
            msg = custom_template
            msg = msg.replace("{barn_temp}", f"{self.ambient_temp_c:.1f}")
            msg = msg.replace("{barn_humidity}", f"{self.ambient_rh:.0f}")
            msg = msg.replace("{barn_thi}", f"{self.ambient_thi:.1f}")
            msg = msg.replace("{zone_temp}", zone_str)
            msg = msg.replace("{duration}", str(mins))
            msg = msg.replace("{stationary_count}", str(self.stationary_count or 0))
            msg = msg.replace("{total_count}", str(self.total_pig_count or 0))
            return msg

        if self.alert_type == AlertType.INDIVIDUAL:
            return (
                f"SWINE ALERT: Sick pig in pen. "
                f"Stationary {mins}m, Zone:{zone_str}, "
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
    
    Configuration can be loaded from database (dynamic) or provided as constructor args (static).
    Database config takes precedence for any overlapping parameters.
    """

    def __init__(
        self,
        repository: Optional[object] = None,
        stationary_behaviors: Optional[List[str]] = None,
        stationary_alert_minutes: float = 15.0,
        stationary_heat_stress_minutes: float = 30.0,
        fever_delta_threshold_c: float = 2.0,
        population_lethargy_ratio: float = 0.60,
        population_persist_seconds: int = 3,
        thi_heat_stress_threshold: float = 78.0,
        cooldown_minutes: int = 5,
        alert_individual_enabled: bool = True,
        alert_population_enabled: bool = True,
    ) -> None:
        # If repository provided, load config from database (runtime-configurable)
        if repository:
            try:
                cfg = repository.get_herd_risk_engine_config()
                stationary_alert_minutes = cfg.get("stationary_alert_minutes", stationary_alert_minutes)
                stationary_heat_stress_minutes = cfg.get("stationary_heat_stress_minutes", stationary_heat_stress_minutes)
                fever_delta_threshold_c = cfg.get("fever_delta_threshold_c", fever_delta_threshold_c)
                population_lethargy_ratio = cfg.get("population_lethargy_ratio", population_lethargy_ratio)
                population_persist_seconds = cfg.get("population_persist_seconds", population_persist_seconds)
                thi_heat_stress_threshold = cfg.get("thi_heat_stress_threshold", thi_heat_stress_threshold)
                cooldown_minutes = cfg.get("cooldown_minutes", cooldown_minutes)
                alert_individual_enabled = cfg.get("alert_individual_enabled", alert_individual_enabled)
                alert_population_enabled = cfg.get("alert_population_enabled", alert_population_enabled)
                logger.info(f"[HerdRiskEngine] Loaded configuration from database")
            except Exception as e:
                logger.warning(f"[HerdRiskEngine] Failed to load config from database, using defaults: {e}")
        
        self._repository = repository
        self._stationary_behaviors = set(stationary_behaviors or {"lying", "sitting"})
        self._alert_minutes = stationary_alert_minutes
        self._heat_stress_minutes = stationary_heat_stress_minutes
        self._fever_delta = fever_delta_threshold_c
        self._pop_ratio = population_lethargy_ratio
        self._pop_persist = population_persist_seconds
        self._thi_threshold = thi_heat_stress_threshold
        self._cooldown_sec = cooldown_minutes * 60.0
        self._individual_alert_enabled = alert_individual_enabled
        self._population_alert_enabled = alert_population_enabled
        # Per-alert-type timestamp of last emitted alert, for engine-level deduplication
        self._last_alert_time: dict[str, float] = {}
        # Cached active SMS templates per alert type
        self._sms_templates: dict[str, str] = {}
        
        # Initial load of templates
        if self._repository:
            self._reload_sms_templates()

    def _reload_sms_templates(self) -> None:
        """Fetch the active SMS templates from the database."""
        if not self._repository:
            return
        try:
            t_indiv = self._repository.get_active_sms_template(AlertType.INDIVIDUAL.value)
            if t_indiv:
                self._sms_templates[AlertType.INDIVIDUAL.value] = t_indiv["message_body"]
                
            t_pop = self._repository.get_active_sms_template(AlertType.POPULATION.value)
            if t_pop:
                self._sms_templates[AlertType.POPULATION.value] = t_pop["message_body"]
        except Exception as e:
            logger.warning(f"[HerdRiskEngine] Failed to load SMS templates: {e}")

    def reload_config(self) -> None:
        """Reload runtime configuration from the database."""
        if not self._repository:
            return
            
        try:
            cfg = self._repository.get_herd_risk_engine_config()
            self._alert_minutes = cfg.get("stationary_alert_minutes", self._alert_minutes)
            self._heat_stress_minutes = cfg.get("stationary_heat_stress_minutes", self._heat_stress_minutes)
            self._fever_delta = cfg.get("fever_delta_threshold_c", self._fever_delta)
            self._pop_ratio = cfg.get("population_lethargy_ratio", self._pop_ratio)
            self._pop_persist = cfg.get("population_persist_seconds", self._pop_persist)
            self._thi_threshold = cfg.get("thi_heat_stress_threshold", self._thi_threshold)
            self._cooldown_sec = cfg.get("cooldown_minutes", self._cooldown_sec / 60.0) * 60.0
            self._individual_alert_enabled = cfg.get("alert_individual_enabled", self._individual_alert_enabled)
            self._population_alert_enabled = cfg.get("alert_population_enabled", self._population_alert_enabled)
            
            self._reload_sms_templates()
        except Exception as e:
            logger.warning(f"[HerdRiskEngine] Failed to reload config: {e}")

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
        Respects alert_type_enabled flags for runtime enable/disable control.
        """
        alerts: List[AlertEvent] = []
        ambient_temp = ambient.temp_c if ambient else 30.0
        ambient_rh = ambient.humidity_pct if ambient else 60.0
        ambient_thi = ambient.thi if ambient else 70.0

        threshold_sec = self._get_stationary_threshold(ambient)

        # ── Channel 1: Individual Anomaly ─────────────────────────────────────
        if self._individual_alert_enabled:
            for track in active_tracks:
                if (
                    track.behavior in self._stationary_behaviors
                    and track.stationary_duration_sec >= threshold_sec
                    and track.thermal_zone_temp > (ambient_temp + self._fever_delta)
                ):
                    # Engine-level cooldown: suppress repeat alert within cooldown window
                    last_t = self._last_alert_time.get(AlertType.INDIVIDUAL.value, 0.0)
                    if time.time() - last_t < self._cooldown_sec:
                        break  # Cooldown active — skip this cycle
                    self._last_alert_time[AlertType.INDIVIDUAL.value] = time.time()
                    alert = AlertEvent(
                        alert_type=AlertType.INDIVIDUAL,
                        trigger_reason="stationary_fever",
                        ambient_temp_c=ambient_temp,
                        ambient_rh=ambient_rh,
                        ambient_thi=ambient_thi,
                        pig_zone_temp_c=track.thermal_zone_temp,
                        stationary_duration_sec=track.stationary_duration_sec,
                        stationary_count=None,
                        total_pig_count=None,
                    )
                    alert.formatted_sms = alert.sms_message(self._sms_templates.get(AlertType.INDIVIDUAL.value))
                    alerts.append(alert)
                    logger.warning(
                        f"[Channel 1] Track {track.track_id} stationary "
                        f"{track.stationary_duration_sec/60:.1f}m, "
                        f"zone {track.thermal_zone_temp:.1f}°C. ALERT."
                    )
                    break   # One alert per evaluation cycle is enough

        # ── Channel 2: Population Lethargy ────────────────────────────────────
        if (
            self._population_alert_enabled
            and not alerts  # Don't double-alert in same cycle
            and persistent_lethargy_ratio >= self._pop_ratio
            and population_snapshot.total_detected >= 2  # Need at least 2 pigs to calc ratio
        ):
            # Engine-level cooldown for population alerts
            last_t = self._last_alert_time.get(AlertType.POPULATION.value, 0.0)
            if time.time() - last_t >= self._cooldown_sec:
                self._last_alert_time[AlertType.POPULATION.value] = time.time()
                alert = AlertEvent(
                    alert_type=AlertType.POPULATION,
                    trigger_reason="herd_lethargy",
                    ambient_temp_c=ambient_temp,
                    ambient_rh=ambient_rh,
                    ambient_thi=ambient_thi,
                    pig_zone_temp_c=None,
                    stationary_duration_sec=None,
                    stationary_count=population_snapshot.stationary_count,
                    total_pig_count=population_snapshot.total_detected,
                )
                alert.formatted_sms = alert.sms_message(self._sms_templates.get(AlertType.POPULATION.value))
                alerts.append(alert)
                logger.warning(
                    f"[Channel 2] {population_snapshot.stationary_count}/"
                    f"{population_snapshot.total_detected} pigs stationary. ALERT."
                )

        return alerts
