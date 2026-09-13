"""
src/thermal/thermal_mapper.py
Zone-Based Thermal Mapper — Assigns thermal zones to YOLO bounding boxes

PURPOSE:
    Bridges the thermal grid to the RGB camera frame.
    For each tracked pig detection, finds which thermal zone its centroid
    falls in and assigns the zone's average temperature to that track_id.
"""

from __future__ import annotations

import logging

import numpy as np

logger = logging.getLogger(__name__)


def assign_temperatures(
    thermal_grid: np.ndarray,   # 2D float array in Celsius
    tracked_detections: list,   # List of objects with .track_id and .bbox (x1,y1,x2,y2)
    frame_shape: tuple,         # (height, width, channels)
) -> dict[int, float]:
    """
    Map thermal zones to each tracked pig detection.

    Returns:
        Dict mapping track_id → estimated zone temperature (°C).
    """
    frame_h, frame_w = frame_shape[:2]
    rows, cols = thermal_grid.shape
    
    cell_w = frame_w / cols
    cell_h = frame_h / rows

    temperature_map: dict[int, float] = {}

    for det in tracked_detections:
        # Get bounding box centroid
        x1, y1, x2, y2 = det.bbox
        cx = (x1 + x2) / 2.0
        cy = (y1 + y2) / 2.0

        # Map centroid to thermal grid cell
        col = int(min(cx / cell_w, cols - 1))
        row = int(min(cy / cell_h, rows - 1))

        # Average the 3x3 neighborhood around the zone for smoother estimation
        r0 = max(0, row - 1)
        r1 = min(rows, row + 2)
        c0 = max(0, col - 1)
        c1 = min(cols, col + 2)
        zone_temp = float(np.mean(thermal_grid[r0:r1, c0:c1]))

        temperature_map[det.track_id] = zone_temp

    return temperature_map
