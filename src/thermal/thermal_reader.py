"""
src/thermal/thermal_reader.py
MLX90640 Thermal Grid Reader

PURPOSE:
    Reads the 32x24 temperature grid from the MLX90640 sensor via I2C.
    Returns a numpy 24x32 array of temperatures in Celsius.

    ROTATION NOTE:
    The physical MLX90640 sensor is mounted 45° off-axis (incorrect orientation).
    A rotation_deg parameter (default 45° CW) is applied to the raw grid
    BEFORE it is returned — this corrects both the visual display AND the
    zone-to-bounding-box temperature mapping, since both use the rotated grid.

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
from typing import Optional

import numpy as np
from scipy.ndimage import rotate as ndimage_rotate

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

    The raw 24x32 sensor grid is rotated by `rotation_deg` degrees CLOCKWISE
    before being stored. This corrects for a physically mis-mounted camera so
    that both the dashboard heatmap display AND the thermal zone-to-pig mapping
    both receive a properly oriented grid.
    """

    ROWS = 24
    COLS = 32

    def __init__(
        self,
        i2c_address: int = 0x33,
        refresh_hz: int = 8,
        i2c_bus: int = 1,
        rotation_deg: float = 45.0,
    ) -> None:
        self._sensor = None
        self._refresh_interval = 1.0 / refresh_hz
        self._rotation_deg = rotation_deg
        # Initialise with a plausible ambient temperature grid
        self._last_grid: np.ndarray = np.full((self.ROWS, self.COLS), 30.0)
        self._last_rotated_grid: np.ndarray = self._apply_rotation(self._last_grid)
        self._running = True
        self._thread = None

        if _MLX_AVAILABLE:
            try:
                self._i2c_bus = i2c_bus
                i2c = busio.I2C(board.SCL, board.SDA, frequency=400000)
                self._sensor = adafruit_mlx90640.MLX90640(i2c)

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

                time.sleep(0.5)
                logger.info(
                    "MLX90640 initialized at I2C bus %d, address 0x%02X at %dHz (rotation=%.1f° CW)",
                    i2c_bus, i2c_address, refresh_hz, rotation_deg,
                )
            except Exception as e:
                logger.error("MLX90640 init failed: %s. Running in simulation mode.", e)
        else:
            logger.info("MLX90640 running in simulation mode (rotation=%.1f° CW).", rotation_deg)

        self._thread = threading.Thread(
            target=self._poll_sensor, daemon=True, name="MLX90640-Thread"
        )
        self._thread.start()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _apply_rotation(self, grid: np.ndarray) -> np.ndarray:
        """
        Rotate the raw thermal grid clockwise by self._rotation_deg degrees.

        scipy.ndimage.rotate uses counter-clockwise convention, so we negate
        the angle. reshape=True grows the output array to fit the rotated
        content without clipping; mode='nearest' extrapolates border pixels
        rather than filling with a cold zero that could confuse the zone mapper.
        """
        if self._rotation_deg == 0:
            return grid
        rotated = ndimage_rotate(
            grid,
            -self._rotation_deg,   # negative = clockwise
            reshape=True,
            mode="nearest",
        )
        return rotated.astype(np.float32)

    def _poll_sensor(self) -> None:
        """Background loop: continuously reads thermal frames and stores the rotated grid."""
        frame = [0.0] * 768
        while self._running:
            if self._sensor:
                try:
                    self._sensor.getFrame(frame)
                    raw = np.array(frame).reshape((self.ROWS, self.COLS))
                    self._last_grid = raw
                    self._last_rotated_grid = self._apply_rotation(raw)
                except ValueError:
                    # ValueErrors occur if I2C baudrate is too slow (needs 400 kHz)
                    pass
                except Exception as e:
                    logger.warning("MLX90640 read error: %s", e)
                time.sleep(self._refresh_interval / 2)
            else:
                # Simulation mode: warm centre blob, cooler edges
                base = np.random.uniform(28.0, 32.0, (self.ROWS, self.COLS))
                base[10:14, 14:18] = np.random.uniform(38.0, 41.0, (4, 4))
                self._last_grid = base
                self._last_rotated_grid = self._apply_rotation(base)
                time.sleep(self._refresh_interval)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def read(self) -> np.ndarray:
        """
        Return the orientation-corrected thermal grid (rotated by rotation_deg° CW).

        Use this for BOTH temperature zone mapping and dashboard display.
        The rotation corrects for the physically mis-mounted camera, so the
        returned grid is already in the correct orientation.
        """
        return self._last_rotated_grid

    def read_raw(self) -> np.ndarray:
        """
        Return the unrotated 24×32 sensor grid.
        Only needed for debugging or calibration purposes.
        """
        return self._last_grid

    def read_upscaled(self, output_size: int = 64) -> np.ndarray:
        """
        Return the rotated grid upscaled for visualization.
        Shape will differ from 24×32 when rotation_deg != 0/90.
        """
        from PIL import Image
        grid = self.read()
        h, w = grid.shape
        img = Image.fromarray(grid.astype(np.float32))
        # Preserve aspect ratio of the rotated output
        scale = output_size / max(h, w)
        new_w, new_h = int(w * scale), int(h * scale)
        img = img.resize((new_w, new_h), Image.BILINEAR)
        return np.array(img)
