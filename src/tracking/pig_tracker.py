"""
src/tracking/pig_tracker.py
Pig Tracker — Wraps SORT and adds behavior context

PURPOSE:
    Wraps the SORTTracker and enriches each tracked detection with:
    - behavior class from the YOLO classification head
    - bounding box in (x1, y1, x2, y2) format
    - confidence score
    - centroid coordinates

This is the data bridge between raw YOLO detections and the BehaviorAnalyzer / RiskEngine.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import List, Optional

import numpy as np

from src.tracking.sort_tracker import SORTTracker

logger = logging.getLogger(__name__)

# Beyond this many cached track entries, prune dead track IDs.
# SORT track_ids come from a monotonic counter and are never reused,
# so forgetting old entries is always safe.
_MAX_CACHE_ENTRIES = 256


@dataclass
class TrackedPig:
    """A SORT-tracked pig with enriched behavioral context."""
    track_id: int
    behavior: str
    confidence: float
    bbox: tuple          # (x1, y1, x2, y2)

    @property
    def centroid(self) -> tuple:
        """(cx, cy) of the bounding box."""
        x1, y1, x2, y2 = self.bbox
        return ((x1 + x2) / 2.0, (y1 + y2) / 2.0)


class PigTracker:
    """
    Enriches raw detections from the ONNX detector with SORT tracking IDs
    and packages them into TrackedPig objects for downstream processing.
    """

    def __init__(self, max_age: int = 30, min_hits: int = 3, iou_threshold: float = 0.3) -> None:
        self._sort = SORTTracker(
            max_age=max_age,
            min_hits=min_hits,
            iou_threshold=iou_threshold,
        )
        self._detection_cache: dict[int, tuple] = {}  # track_id → (behavior, confidence)
        self._last_track_ids: set[int] = set()        # Track IDs from the previous update

    def update(self, detections: List[dict], class_names: List[str]) -> List[TrackedPig]:
        # Prune cache entries for track IDs not seen in the last update.
        # SORT track_ids come from a monotonic counter and are never reused,
        # so forgetting old entries is always safe. This prevents unbounded
        # memory growth on long-running deployments.
        if len(self._detection_cache) > _MAX_CACHE_ENTRIES:
            for tid in list(self._detection_cache):
                if tid not in self._last_track_ids:
                    del self._detection_cache[tid]

        """
        Update tracker with new YOLO detections.

        Args:
            detections: List of dicts with keys: bbox, confidence, class_id
            class_names: Ordered list of class names from config (e.g. ['lying','standing',...])

        Returns:
            List of TrackedPig objects with stable track IDs.
        """
        # Build (N,5) array for SORT: [x1,y1,x2,y2,confidence]
        det_array = np.array(
            [[*d["bbox"], d["confidence"]] for d in detections],
            dtype=float,
        ) if detections else np.empty((0, 5), dtype=float)

        sort_output = self._sort.update(det_array)  # → [x1,y1,x2,y2,track_id]

        # Match SORT outputs back to original detections by IoU
        tracked = []
        current_ids = set()
        for track in sort_output:
            x1, y1, x2, y2, track_id = track
            track_id = int(track_id)
            current_ids.add(track_id)

            # Find best matching detection for this track by spatial proximity
            best_idx = _closest_detection(detections, (x1, y1, x2, y2))
            if best_idx is not None:
                d = detections[best_idx]
                behavior = class_names[d["class_id"]] if d["class_id"] < len(class_names) else "unknown"
                conf = d["confidence"]
                self._detection_cache[track_id] = (behavior, conf)
            else:
                # Coasted track — use cached behavior from last matched detection.
                behavior, conf = self._detection_cache.get(track_id, ("unknown", 0.0))

            tracked.append(TrackedPig(
                track_id=track_id,
                behavior=behavior,
                confidence=conf,
                bbox=(x1, y1, x2, y2),
            ))

        self._last_track_ids = current_ids
        return tracked


def _closest_detection(detections: List[dict], box: tuple) -> Optional[int]:
    """Find index of detection with highest IoU to a given box."""
    from src.tracking.sort_tracker import _iou
    best_iou = 0.0
    best_idx = None
    box_arr = np.array(box)
    for i, d in enumerate(detections):
        iou = _iou(np.array(d["bbox"]), box_arr)
        if iou > best_iou:
            best_iou = iou
            best_idx = i
    return best_idx if best_iou > 0.1 else None
