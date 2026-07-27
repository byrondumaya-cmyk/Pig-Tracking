"""
src/analytics/behavior_analyzer.py
Behavior Analytics & Stationary Duration Tracker

PURPOSE:
    Tracks per-SORT-track behavioral durations within a session.
    Flags stationary tracks (lying/sitting) when they exceed the configured threshold.
    Provides population-level behavior distribution for Channel 2 (lethargy ratio) detection.

NOTE ON TRACKING:
    SORT track_ids are temporary and session-scoped. They are NOT permanent pig identifiers.
    If a pig walks off-screen and returns, it gets a new track_id and its timer resets.
    This is by design — the system logic is herd-level, not per-pig persistent ID.
"""

from __future__ import annotations

import logging
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

# Behaviors considered "stationary" for health risk purposes
STATIONARY_BEHAVIORS = {"lying", "sitting"}

# Centroid movement threshold to detect "pig has moved" (pixels)
MOVEMENT_THRESHOLD_PX = 20


@dataclass
class TrackState:
    """Runtime state for one SORT-tracked object within the current session."""
    track_id: int
    behavior: str = "unknown"
    stationary_start: Optional[float] = None   # Unix timestamp when stationary began
    last_centroid: Optional[tuple] = None
    thermal_zone_temp: float = 0.0

    @property
    def stationary_duration_sec(self) -> float:
        """Seconds this track has been continuously stationary (0 if moving)."""
        if self.stationary_start is None:
            return 0.0
        return time.time() - self.stationary_start

    @property
    def is_stationary(self) -> bool:
        return self.behavior in STATIONARY_BEHAVIORS


@dataclass
class PopulationSnapshot:
    """Aggregate behavioral stats for the whole pen at one point in time."""
    total_detected: int = 0
    stationary_count: int = 0
    behavior_counts: Dict[str, int] = field(default_factory=dict)

    @property
    def lethargy_ratio(self) -> float:
        """Fraction of detected pigs that are stationary (0.0 – 1.0)."""
        if self.total_detected == 0:
            return 0.0
        return self.stationary_count / self.total_detected


class BehaviorAnalyzer:
    """
    Tracks behavioral state and stationary duration for all active SORT tracks.
    Also computes population-level statistics for Channel 2 detection.
    """

    def __init__(self, stationary_behaviors: Optional[List[str]] = None) -> None:
        self._stationary_behaviors = set(stationary_behaviors or STATIONARY_BEHAVIORS)
        self._tracks: Dict[int, TrackState] = {}
        # Ring buffer of recent population snapshots for Channel 2 persistence check
        self._pop_history: deque = deque(maxlen=30)   # ~30 seconds at 1 FPS

    def update(
        self,
        detections: List[Dict],  # Each: {track_id, behavior, centroid: (cx, cy), thermal_zone_temp}
    ) -> tuple[List[TrackState], PopulationSnapshot]:
        """
        Update tracker state with fresh detections from the current frame.

        Args:
            detections: List of detection dicts from SORT + YOLO + thermal mapper.

        Returns:
            (active_tracks, population_snapshot)
        """
        active_ids = set()
        snapshot = PopulationSnapshot()
        snapshot.total_detected = len(detections)

        for det in detections:
            tid = det["track_id"]
            behavior = det.get("behavior", "unknown")
            centroid = det.get("centroid")
            zone_temp = det.get("thermal_zone_temp", 0.0)
            active_ids.add(tid)

            # Create state for new tracks
            if tid not in self._tracks:
                self._tracks[tid] = TrackState(track_id=tid)

            state = self._tracks[tid]
            state.behavior = behavior
            state.thermal_zone_temp = zone_temp

            # Check if pig has moved significantly
            has_moved = False
            if centroid and state.last_centroid:
                dx = centroid[0] - state.last_centroid[0]
                dy = centroid[1] - state.last_centroid[1]
                has_moved = (dx**2 + dy**2) ** 0.5 > MOVEMENT_THRESHOLD_PX
            state.last_centroid = centroid

            # Update stationary timer
            if behavior in self._stationary_behaviors and not has_moved:
                if state.stationary_start is None:
                    state.stationary_start = time.time()
            else:
                # Reset timer — pig moved or changed behavior
                state.stationary_start = None

            # Population stats
            behavior_key = behavior or "unknown"
            snapshot.behavior_counts[behavior_key] = snapshot.behavior_counts.get(behavior_key, 0) + 1
            if behavior in self._stationary_behaviors:
                snapshot.stationary_count += 1

        # Remove stale tracks (not in latest frame)
        stale = [tid for tid in self._tracks if tid not in active_ids]
        for tid in stale:
            del self._tracks[tid]

        self._pop_history.append(snapshot)
        active_tracks = list(self._tracks.values())
        return active_tracks, snapshot

    def get_persistent_lethargy_ratio(self, persist_seconds: int = 3) -> float:
        """
        Returns the lethargy ratio only if it has persisted for at least
        `persist_seconds` consecutive seconds. Used for Channel 2 (population alert).
        """
        if len(self._pop_history) < persist_seconds:
            return 0.0
        recent = list(self._pop_history)[-persist_seconds:]
        ratios = [s.lethargy_ratio for s in recent]
        # All recent snapshots must show elevated ratio
        return min(ratios)
