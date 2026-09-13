"""
src/thermal/thermal_reader.py
MLX90640 Thermal Grid Reader

PURPOSE:
    Reads the 32x24 temperature grid from the MLX90640 sensor via I2C.
    Returns a numpy 24x32 array of temperatures in Celsius.

WIRING (Raspberry Pi 4B):
    MLX90640 VIN  → 3.3V (Pin 1)
    MLX90640 GND  → GND (Pin 6)
    MLX90640 SDA  → GPIO2/SDA1 (Pin 3)
    MLX90640 SCL  → GPIO3/SCL1 (Pin 5)

VERIFY:
    i2cdetect -y 1    (should show device at 0x33)
"""

from __future__ import annotations

import logging
import time
import threading

import numpy as np

logger = logging.getLogger(__name__)

try:
    import board
    import busio
    import adafruit_mlx90640
    _MLX_AVAILABLE = True
except (ImportError, NotImplementedError):
    _MLX_AVAILABLE = False
    logger.warning("adafruit_mlx90640 not available — ThermalReader running in simulation mode.")


class MLX90640Reader:
    """
    Reads the MLX90640 32x24 thermal grid.
    Runs in a background thread to prevent blocking the main YOLO loop.
    Falls back to a simulation grid on PC/development environments.
    """

    ROWS = 24
    COLS = 32

    def __init__(self, i2c_address: int = 0x33, refresh_hz: int = 8, i2c_bus: int = 1) -> None:
        self._sensor = None
        self._refresh_interval = 1.0 / refresh_hz
        self._last_grid: np.ndarray = np.full((self.ROWS, self.COLS), 30.0)
        self._running = True
        self._thread = None

        if _MLX_AVAILABLE:
            try:
                # Use busio with explicit SCL/SDA
                self._i2c_bus = i2c_bus
                # MLX90640 needs a higher baudrate, typically 400kHz or 1MHz
                i2c = busio.I2C(board.SCL, board.SDA, frequency=400000)
                self._sensor = adafruit_mlx90640.MLX90640(i2c)
                
                # Configure refresh rate
                if refresh_hz <= 2:
                    self._sensor.refresh_rate = adafruit_mlx90640.RefreshRate.REFRESH_2_HZ
                elif refresh_hz <= 4:
                    self._sensor.refresh_rate = adafruit_mlx90640.RefreshRate.REFRESH_4_HZ
                elif refresh_hz <= 8:
                    self._sensor.refresh_rate = adafruit_mlx90640.RefreshRate.REFRESH_8_HZ
                elif refresh_hz <= 16:
                    self._sensor.refresh_rate = adafruit_mlx90640.RefreshRate.REFRESH_16_HZ
                elif refresh_hz <= 32:
                    self._sensor.refresh_rate = adafruit_mlx90640.RefreshRate.REFRESH_32_HZ
                else:
                    self._sensor.refresh_rate = adafruit_mlx90640.RefreshRate.REFRESH_64_HZ

                time.sleep(0.5)  # Sensor startup time
                logger.info(
                    f"MLX90640 initialized at I2C bus {i2c_bus}, address 0x{i2c_address:02X} at {refresh_hz}Hz"
                )
            except Exception as e:
                logger.error(f"MLX90640 init failed: {e}. Running in simulation mode.")
        else:
            logger.info("MLX90640 running in simulation mode.")

        # Start background polling thread
        self._thread = threading.Thread(target=self._poll_sensor, daemon=True, name="MLX90640-Thread")
        self._thread.start()

    def _poll_sensor(self) -> None:
        """Background loop to continuously read thermal frames."""
        frame = [0.0] * 768
        while self._running:
            if self._sensor:
                try:
                    self._sensor.getFrame(frame)
                    grid = np.array(frame).reshape((self.ROWS, self.COLS))
                    self._last_grid = grid
                except ValueError:
                    # ValueErrors occur if I2C baudrate is too slow (needs 400kHz in config.txt)
                    pass
                except Exception as e:
                    logger.warning(f"MLX90640 read error: {e}")
                
                # Don't spin wildly if there are I2C errors
                time.sleep(self._refresh_interval / 2)
            else:
                # Simulation mode: warm center, cooler edges
                base = np.random.uniform(28.0, 32.0, (self.ROWS, self.COLS))
                base[10:14, 14:18] = np.random.uniform(38.0, 41.0, (4, 4))
                self._last_grid = base
                time.sleep(self._refresh_interval)

    def read(self) -> np.ndarray:
        """
        Returns a 24x32 numpy array of temperatures in Celsius instantly.
        """
        return self._last_grid

    def read_upscaled(self, output_size: int = 64) -> np.ndarray:
        """
        Returns an upscaled version of the grid for visualization.
        """
        from PIL import Image
        grid = self.read()
        img = Image.fromarray(grid.astype(np.float32))
        img = img.resize((output_size, output_size), Image.BILINEAR)
        return np.array(img)
