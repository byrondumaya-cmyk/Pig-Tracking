"""
src/analytics/pig_counter.py

Occupancy-based pig counting (NOT session-cumulative counting).

PURPOSE:
    Track current pig count based on active SORT tracks.
    Does NOT increment on re-entry (pig returns with new track ID).
    
    Solves: "Pig count should represent pigs currently visible, not total entries"

DESIGN:
    - Count = len(active tracks)
    - No persistent ID assignment (would require re-ID model)
    - Session-scoped tracking only
    - Tracks marked inactive when age > max_age

USAGE:
    counter = PigCounter()
    count = counter.update(tracked_pigs)  # Returns current occupancy
    stats = counter.get_stats()  # Get historical stats
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import List

logger = logging.getLogger(__name__)


@dataclass
class CountingStats:
    """Statistics about pig occupancy."""
    current_count: int = 0              # Pigs currently in view
    peak_count: int = 0                 # Max pigs seen in one frame (this session)
    total_unique_tracks: int = 0        # Total distinct SORT track IDs observed
    frames_with_pigs: int = 0           # Frames where count > 0
    frames_without_pigs: int = 0        # Frames where count == 0


class PigCounter:
    """
    Tracks occupancy-based pig counting.

    Key difference from naive counting:
    - Occupancy = current frame detections
    - Does NOT re-count when pig leaves and returns (prevents inflated counts)
    - Distinguishes between "pigs currently visible" vs "pig visits"
    """

    def __init__(self) -> None:
        self._active_track_ids: set[int] = set()
        self._all_track_ids_seen: set[int] = set()
        self._current_count = 0
        self._peak_count = 0
        self._frames_with_pigs = 0
        self._frames_without_pigs = 0

    def update(self, tracked_pigs: List) -> int:
        """
        Update counter with current frame's tracked pigs.

        Args:
            tracked_pigs: List of TrackedPig objects from tracker.update()

        Returns:
            Current occupancy count (number of pigs in view)
        """
        current_track_ids = {pig.track_id for pig in tracked_pigs}

        # Update stats
        self._active_track_ids = current_track_ids
        self._all_track_ids_seen.update(current_track_ids)
        self._current_count = len(tracked_pigs)
        self._peak_count = max(self._peak_count, self._current_count)

        if self._current_count > 0:
            self._frames_with_pigs += 1
        else:
            self._frames_without_pigs += 1

        return self._current_count

    def get_current_count(self) -> int:
        """Return current pig occupancy."""
        return self._current_count

    def get_peak_count(self) -> int:
        """Return peak occupancy seen this session."""
        return self._peak_count

    def get_stats(self) -> CountingStats:
        """Return comprehensive counting statistics."""
        return CountingStats(
            current_count=self._current_count,
            peak_count=self._peak_count,
            total_unique_tracks=len(self._all_track_ids_seen),
            frames_with_pigs=self._frames_with_pigs,
            frames_without_pigs=self._frames_without_pigs,
        )

    def reset(self) -> None:
        """Reset all counters (useful for multi-session tracking)."""
        self._active_track_ids.clear()
        self._all_track_ids_seen.clear()
        self._current_count = 0
        self._peak_count = 0
        self._frames_with_pigs = 0
        self._frames_without_pigs = 0
        logger.info("Pig counter reset.")
