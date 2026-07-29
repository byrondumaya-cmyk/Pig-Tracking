"""
src/thermal/thermal_reader.py
AMG8833 (Adafruit) Thermal Grid Reader

PURPOSE:
    Reads the 8x8 temperature grid from the AMG8833 sensor via I2C.
    Returns a numpy 8x8 array of temperatures in Celsius.
    Provides bilinear upscaling to 32x32 for visualization.

WIRING (Raspberry Pi 4B):
    AMG8833 VIN  → 3.3V (Pin 1)
    AMG8833 GND  → GND (Pin 6)
    AMG8833 SDA  → GPIO2/SDA1 (Pin 3)
    AMG8833 SCL  → GPIO3/SCL1 (Pin 5)

VERIFY:
    i2cdetect -y 1    (should show device at 0x69)
"""

from __future__ import annotations

import logging
import time

import numpy as np

logger = logging.getLogger(__name__)

try:
    import board
    import busio
    import adafruit_amg88xx
    _AMG_AVAILABLE = True
except (ImportError, NotImplementedError):
    _AMG_AVAILABLE = False
    logger.warning("adafruit_amg88xx not available — ThermalReader running in simulation mode.")


class AMG8833Reader:
    """
    Reads the AMG8833 8x8 thermal grid.
    Falls back to a simulation grid on PC/development environments.
    """

    ROWS = 8
    COLS = 8

    def __init__(self, i2c_address: int = 0x69, refresh_hz: int = 10, i2c_bus: int = 1) -> None:
        self._sensor = None
        self._refresh_interval = 1.0 / refresh_hz
        self._last_read = 0.0
        self._last_grid: np.ndarray = np.full((self.ROWS, self.COLS), 30.0)

        if _AMG_AVAILABLE:
            try:
                # Use busio with explicit SCL/SDA — i2c_bus is bus 1 on all RPi4 boards.
                # Stored for documentation; busio on RPi always uses the hardware I2C pins.
                self._i2c_bus = i2c_bus
                i2c = busio.I2C(board.SCL, board.SDA)
                self._sensor = adafruit_amg88xx.AMG88XX(i2c, addr=i2c_address)
                time.sleep(0.5)  # Sensor startup time
                logger.info(
                    f"AMG8833 initialized at I2C bus {i2c_bus}, address 0x{i2c_address:02X}"
                )
            except Exception as e:
                logger.error(f"AMG8833 init failed: {e}. Running in simulation mode.")
        else:
            logger.info("AMG8833 running in simulation mode.")

    def read(self) -> np.ndarray:
        """
        Returns an 8x8 numpy array of temperatures in Celsius.
        Rate-limited to sensor refresh rate. Returns last known grid on fast calls.
        """
        now = time.time()
        if now - self._last_read < self._refresh_interval:
            return self._last_grid

        if self._sensor:
            try:
                grid = np.array(self._sensor.pixels)   # Already 8x8
                self._last_grid = grid
                self._last_read = now
            except Exception as e:
                logger.warning(f"AMG8833 read error: {e}. Returning last grid.")
        else:
            # Simulation: warm center, cooler edges
            base = np.random.uniform(28.0, 32.0, (8, 8))
            base[3:5, 3:5] = np.random.uniform(38.0, 41.0, (2, 2))  # Simulate pig body heat
            self._last_grid = base
            self._last_read = now

        return self._last_grid

    def read_upscaled(self, output_size: int = 32) -> np.ndarray:
        """
        Returns a bilinearly upscaled version of the 8x8 grid for visualization.
        """
        from PIL import Image
        grid = self.read()
        img = Image.fromarray(grid.astype(np.float32))
        img = img.resize((output_size, output_size), Image.BILINEAR)
        return np.array(img)
