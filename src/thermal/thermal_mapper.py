"""
src/thermal/thermal_mapper.py
Zone-Based Thermal Mapper — Assigns AMG8833 zones to YOLO bounding boxes

PURPOSE:
    Bridges the AMG8833 8x8 thermal grid to the RGB camera frame.
    For each tracked pig detection, finds which thermal zone its centroid
    falls in and assigns the zone's average temperature to that track_id.

DESIGN:
    The 8x8 thermal grid is mapped proportionally to the RGB frame dimensions.
    Each thermal cell covers (frame_width/8) x (frame_height/8) pixels.
    The pig's bounding box centroid determines its thermal zone.

    This approach is intentionally herd-level — we get a temperature
    estimate per pig position, not per individual pig identity.
"""

from __future__ import annotations

import logging

import numpy as np

logger = logging.getLogger(__name__)

GRID_SIZE = 8  # AMG8833 is always 8x8


def assign_temperatures(
    thermal_grid: np.ndarray,   # 8x8 float array in Celsius
    tracked_detections: list,   # List of objects with .track_id and .bbox (x1,y1,x2,y2)
    frame_shape: tuple,         # (height, width, channels)
) -> dict[int, float]:
    """
    Map thermal zones to each tracked pig detection.

    Returns:
        Dict mapping track_id → estimated zone temperature (°C).
    """
    frame_h, frame_w = frame_shape[:2]
    cell_w = frame_w / GRID_SIZE
    cell_h = frame_h / GRID_SIZE

    temperature_map: dict[int, float] = {}

    for det in tracked_detections:
        # Get bounding box centroid
        x1, y1, x2, y2 = det.bbox
        cx = (x1 + x2) / 2.0
        cy = (y1 + y2) / 2.0

        # Map centroid to thermal grid cell
        col = int(min(cx / cell_w, GRID_SIZE - 1))
        row = int(min(cy / cell_h, GRID_SIZE - 1))

        # Average the 2x2 neighborhood around the zone for smoother estimation
        r0 = max(0, row - 1)
        r1 = min(GRID_SIZE, row + 1)
        c0 = max(0, col - 1)
        c1 = min(GRID_SIZE, col + 1)
        zone_temp = float(np.mean(thermal_grid[r0:r1, c0:c1]))

        temperature_map[det.track_id] = zone_temp

    return temperature_map
