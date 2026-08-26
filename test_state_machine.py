"""
Test Alert Cooldown & State Machine Validation

Verifies the transition SAFE -> WARNING -> DANGER -> SAFE
and ensures cooldown prevents spam.
"""

import sys
import time
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from src.analytics.behavior_analyzer import TrackState, PopulationSnapshot
from src.health.risk_engine import HerdRiskEngine, AlertType

# We need a mock repository for HerdRiskEngine
class MockRepository:
    def get_alert_config(self):
        return {
            "stationary_alert_minutes": 15,
            "stationary_heat_stress_minutes": 30,
            "fever_delta_threshold_c": 2.0,
            "population_lethargy_ratio": 0.60,
            "population_persist_seconds": 3,
            "thi_heat_stress_threshold": 78.0,
            "cooldown_minutes": 5,
            "alert_individual_enabled": True,
            "alert_population_enabled": True,
        }

def test_state_machine():
    repo = MockRepository()
    config = repo.get_alert_config()
    engine = HerdRiskEngine(
        repository=repo,
        stationary_behaviors={"resting"},
        stationary_alert_minutes=config["stationary_alert_minutes"],
        stationary_heat_stress_minutes=config["stationary_heat_stress_minutes"],
        fever_delta_threshold_c=config["fever_delta_threshold_c"],
        population_lethargy_ratio=config["population_lethargy_ratio"],
        population_persist_seconds=config["population_persist_seconds"],
        thi_heat_stress_threshold=config["thi_heat_stress_threshold"],
        cooldown_minutes=0.1,  # Short cooldown for test: 6 seconds
    )
    
    # 1. SAFE -> SAFE (Noisy/repeated inputs)
    print("Testing SAFE boundaries...")
    track1 = TrackState(track_id=1, behavior="resting", thermal_zone_temp=38.5)
    track1.stationary_start = time.time() - (14 * 60) # 14 minutes, under 15 min threshold
    
    alerts = engine.evaluate([track1], PopulationSnapshot(), 0.0, None)
    assert not alerts, "Should be SAFE at 14 minutes"
    
    # 2. SAFE -> DANGER (15 minutes threshold crossed)
    print("Testing SAFE -> DANGER threshold...")
    track1.stationary_start = time.time() - (15.5 * 60) # 15.5 minutes
    alerts = engine.evaluate([track1], PopulationSnapshot(), 0.0, None)
    assert alerts, "Should trigger DANGER alert > 15 minutes"
    assert alerts[0].alert_type == AlertType.INDIVIDUAL
    
    # 3. DANGER -> DANGER (Cooldown prevents spam)
    print("Testing Cooldown lock...")
    alerts = engine.evaluate([track1], PopulationSnapshot(), 0.0, None)
    assert not alerts, "Cooldown should prevent second immediate alert"
    
    # 4. Wait for Cooldown -> Reminder
    print("Waiting for cooldown (6s)...")
    time.sleep(6.1) # Wait for 0.1 min (6s) cooldown
    alerts = engine.evaluate([track1], PopulationSnapshot(), 0.0, None)
    assert alerts, "Should trigger reminder after cooldown"
    assert alerts[0].alert_type == AlertType.INDIVIDUAL
    
    # 5. Recovery SAFE
    print("Testing recovery (Pig moved)...")
    track1.stationary_start = None
    alerts = engine.evaluate([track1], PopulationSnapshot(), 0.0, None)
    assert not alerts, "Should return to SAFE when pig moves"
    
    print("\nSUCCESS: State machine & Cooldown validated.")

if __name__ == "__main__":
    test_state_machine()
