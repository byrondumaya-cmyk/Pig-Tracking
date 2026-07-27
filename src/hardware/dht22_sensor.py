"""
src/hardware/dht22_sensor.py
DHT22 Ambient Temperature & Humidity Sensor

PURPOSE:
    Reads ambient temperature and humidity from a DHT22 sensor via GPIO.
    Calculates the Temperature Humidity Index (THI) for livestock heat stress assessment.
    Used by the Health Risk Engine as the ambient baseline for fever detection.

WIRING (Raspberry Pi 4B):
    DHT22 VCC  → 3.3V (Pin 1)
    DHT22 DATA → GPIO4 (Pin 7) — with 10kΩ pull-up to 3.3V
    DHT22 GND  → GND (Pin 6)

VERIFY:
    python3 -c "import adafruit_dht; print('DHT library OK')"
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)

# Graceful import — library only available on Raspberry Pi
try:
    import adafruit_dht
    import board
    _DHT_AVAILABLE = True
except (ImportError, NotImplementedError):
    _DHT_AVAILABLE = False
    logger.warning("adafruit_dht not available — DHT22 will run in simulation mode.")


@dataclass
class AmbientReading:
    """Snapshot of ambient environmental conditions."""
    temp_c: float
    humidity_pct: float
    thi: float          # Temperature Humidity Index (livestock heat stress)

    @property
    def is_heat_stress(self) -> bool:
        """THI > 78 indicates heat stress conditions for pigs."""
        return self.thi > 78.0

    def __str__(self) -> str:
        return (
            f"{self.temp_c:.1f}°C / {self.humidity_pct:.1f}% RH "
            f"/ THI: {self.thi:.1f}"
            + (" ⚠ HEAT STRESS" if self.is_heat_stress else "")
        )


def _calculate_thi(temp_c: float, humidity_pct: float) -> float:
    """
    Calculate Temperature Humidity Index (THI) for pigs.
    Formula: THI = T - (0.55 - 0.0055 * RH) * (T - 14.5)
    THI > 72 = mild stress, > 78 = severe stress, > 84 = danger.
    """
    return temp_c - (0.55 - 0.0055 * humidity_pct) * (temp_c - 14.5)


class DHT22Sensor:
    """
    Driver for DHT22 ambient temperature and humidity sensor.
    Provides THI calculation for livestock heat stress monitoring.
    Falls back to simulation mode when hardware is unavailable.
    """

    def __init__(self, gpio_pin: int = 4) -> None:
        self._gpio_pin = gpio_pin
        self._device = None
        self._last_reading: Optional[AmbientReading] = None

        if _DHT_AVAILABLE:
            try:
                pin = getattr(board, f"D{gpio_pin}")
                self._device = adafruit_dht.DHT22(pin, use_pulseio=False)
                logger.info(f"DHT22 initialized on GPIO{gpio_pin}")
            except Exception as e:
                logger.error(f"DHT22 init failed: {e}")
        else:
            logger.info("DHT22 running in simulation mode (no hardware).")

    def read(self) -> Optional[AmbientReading]:
        """
        Read current ambient conditions from the DHT22.
        Returns None on hardware failure — caller must handle gracefully.
        """
        if self._device is None:
            # Simulation fallback for development/testing on PC
            return AmbientReading(temp_c=28.5, humidity_pct=65.0, thi=72.4)

        # DHT22 can fail intermittently — retry once
        for attempt in range(2):
            try:
                temp = self._device.temperature
                rh = self._device.humidity
                if temp is not None and rh is not None:
                    thi = _calculate_thi(temp, rh)
                    reading = AmbientReading(temp_c=temp, humidity_pct=rh, thi=thi)
                    self._last_reading = reading
                    return reading
            except RuntimeError as e:
                if attempt == 0:
                    time.sleep(2.0)    # DHT22 minimum sampling interval
                else:
                    logger.warning(f"DHT22 read failed after retry: {e}")

        return self._last_reading  # Return stale reading on failure

    def close(self) -> None:
        """Release hardware resources."""
        if self._device:
            try:
                self._device.exit()
            except Exception:
                pass
