"""
Test Tracking ID & Lethargy Validation

Verifies that when Track A disappears and Track B appears in the same place,
Track B does not inherit Track A's inactivity state.
"""

import sys
import time
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from src.analytics.behavior_analyzer import BehaviorAnalyzer
from src.health.risk_engine import HerdRiskEngine
from src.database.repository import SwineRepository

def test_tracking_isolation():
    # Setup
    analyzer = BehaviorAnalyzer(stationary_behaviors={"resting", "sleeping", "stationary"})
    
    # Simulate a run
    # Frame 1: Pig A appears, resting
    active_tracks, snap1 = analyzer.update([{
        "track_id": 1,
        "behavior": "resting",
        "centroid": (100, 100),
        "thermal_zone_temp": 38.5
    }])
    track1 = next((t for t in active_tracks if t.track_id == 1), None)
    print(f"Frame 1: Track 1 duration = {track1.stationary_duration_sec:.1f}s")
    
    # Fast forward 10 minutes
    time.sleep(0.1) # small pause just to ensure monotonic clock ticks
    
    # We will hack the analyzer's start time to simulate 10 minutes passing
    track1.stationary_start = time.time() - 600
    
    active_tracks, snap2 = analyzer.update([{
        "track_id": 1,
        "behavior": "resting",
        "centroid": (100, 100),
        "thermal_zone_temp": 38.5
    }])
    track1 = next((t for t in active_tracks if t.track_id == 1), None)
    duration_A = track1.stationary_duration_sec
    print(f"Frame 2 (10 min later): Track 1 duration = {duration_A:.1f}s")
    assert duration_A >= 600, "Track A should have accumulated 10 mins"

    # Frame 3: Pig A drops (not in detection list)
    print("Frame 3: Track 1 drops")
    active_tracks, snap3 = analyzer.update([])
    track1_check = next((t for t in active_tracks if t.track_id == 1), None)
    assert track1_check is None, "Track 1 should be gone"
    
    # Frame 4: Pig B appears in exact same spot, resting
    active_tracks, snap4 = analyzer.update([{
        "track_id": 2,  # New tracker ID assigned by SORT
        "behavior": "resting",
        "centroid": (100, 100),
        "thermal_zone_temp": 38.5
    }])
    track2 = next((t for t in active_tracks if t.track_id == 2), None)
    duration_B = track2.stationary_duration_sec
    print(f"Frame 4: Track 2 appears in same spot. Duration = {duration_B:.1f}s")
    
    assert duration_B < 1.0, f"Track B inherited Track A's duration! Got {duration_B}"
    print("\nSUCCESS: Tracking ID isolation verified. Lethargy state is NOT inherited.")

if __name__ == "__main__":
    test_tracking_isolation()
