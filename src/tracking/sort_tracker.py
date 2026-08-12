"""
src/tracking/sort_tracker.py
SORT — Simple Online Realtime Tracking

Lightweight multi-object tracker based on Kalman filters and Hungarian assignment.
Adapted from the original SORT paper (Bewley et al., 2016).

Dependencies: filterpy, scipy (both in requirements-pi.txt)
"""

from __future__ import annotations

import numpy as np
from filterpy.kalman import KalmanFilter
from scipy.optimize import linear_sum_assignment


def _iou(bb_a: np.ndarray, bb_b: np.ndarray) -> float:
    """Compute Intersection over Union for two boxes [x1,y1,x2,y2]."""
    xa = max(bb_a[0], bb_b[0])
    ya = max(bb_a[1], bb_b[1])
    xb = min(bb_a[2], bb_b[2])
    yb = min(bb_a[3], bb_b[3])

    inter = max(0, xb - xa) * max(0, yb - ya)
    area_a = (bb_a[2] - bb_a[0]) * (bb_a[3] - bb_a[1])
    area_b = (bb_b[2] - bb_b[0]) * (bb_b[3] - bb_b[1])
    union = area_a + area_b - inter
    return inter / union if union > 0 else 0.0


def _box_to_z(box: np.ndarray) -> np.ndarray:
    """Convert [x1,y1,x2,y2] to [cx,cy,s,r] measurement vector."""
    w = box[2] - box[0]
    h = box[3] - box[1]
    cx = box[0] + w / 2.0
    cy = box[1] + h / 2.0
    s = w * h         # scale (area)
    r = w / float(h)  # aspect ratio
    return np.array([cx, cy, s, r]).reshape((4, 1))


def _x_to_box(x: np.ndarray) -> np.ndarray:
    """Convert Kalman state [cx,cy,s,r,...] to [x1,y1,x2,y2]."""
    w = np.sqrt(abs(x[2] * x[3]))
    h = x[2] / w if w != 0 else 0
    return np.array([
        x[0] - w / 2.0,
        x[1] - h / 2.0,
        x[0] + w / 2.0,
        x[1] + h / 2.0,
    ], dtype=float).reshape(4,)


class KalmanBoxTracker:
    """Single tracked object using a constant-velocity Kalman filter."""

    _count = 0

    def __init__(self, bbox: np.ndarray) -> None:
        self.kf = KalmanFilter(dim_x=7, dim_z=4)
        self.kf.F = np.array([
            [1, 0, 0, 0, 1, 0, 0],
            [0, 1, 0, 0, 0, 1, 0],
            [0, 0, 1, 0, 0, 0, 1],
            [0, 0, 0, 1, 0, 0, 0],
            [0, 0, 0, 0, 1, 0, 0],
            [0, 0, 0, 0, 0, 1, 0],
            [0, 0, 0, 0, 0, 0, 1],
        ])
        self.kf.H = np.array([
            [1, 0, 0, 0, 0, 0, 0],
            [0, 1, 0, 0, 0, 0, 0],
            [0, 0, 1, 0, 0, 0, 0],
            [0, 0, 0, 1, 0, 0, 0],
        ])
        self.kf.R[2:, 2:] *= 10.0
        self.kf.P[4:, 4:] *= 1000.0
        self.kf.P *= 10.0
        self.kf.Q[-1, -1] *= 0.01
        self.kf.Q[4:, 4:] *= 0.01
        self.kf.x[:4] = _box_to_z(bbox)

        self.time_since_update = 0
        self.id = KalmanBoxTracker._count
        KalmanBoxTracker._count += 1
        self.hit_streak = 0
        self.age = 0

    def update(self, bbox: np.ndarray) -> None:
        self.time_since_update = 0
        self.hit_streak += 1
        self.kf.update(_box_to_z(bbox))

    def predict(self) -> np.ndarray:
        if self.kf.x[6] + self.kf.x[2] <= 0:
            self.kf.x[6] = 0.0
        self.kf.predict()
        self.age += 1
        if self.time_since_update > 0:
            self.hit_streak = 0
        self.time_since_update += 1
        return _x_to_box(self.kf.x)

    def get_state(self) -> np.ndarray:
        return _x_to_box(self.kf.x)


def _associate_detections(
    detections: np.ndarray,
    trackers: np.ndarray,
    iou_threshold: float = 0.3,
) -> tuple:
    """Hungarian assignment of detections to trackers."""
    if len(trackers) == 0:
        return np.empty((0, 2), dtype=int), np.arange(len(detections)), np.empty(0, dtype=int)
    if len(detections) == 0:
        return np.empty((0, 2), dtype=int), np.empty(0, dtype=int), np.arange(len(trackers))

    iou_matrix = np.zeros((len(detections), len(trackers)))
    for d, det in enumerate(detections):
        for t, trk in enumerate(trackers):
            iou_matrix[d, t] = _iou(det, trk)

    row_ind, col_ind = linear_sum_assignment(-iou_matrix)
    matched = np.column_stack([row_ind, col_ind])
    unmatched_dets = [d for d in range(len(detections)) if d not in matched[:, 0]]
    unmatched_trks = [t for t in range(len(trackers)) if t not in matched[:, 1]]

    # Filter low-IoU matches
    good_matches = [m for m in matched if iou_matrix[m[0], m[1]] >= iou_threshold]
    for m in matched:
        if iou_matrix[m[0], m[1]] < iou_threshold:
            unmatched_dets.append(m[0])
            unmatched_trks.append(m[1])

    return (
        np.array(good_matches) if good_matches else np.empty((0, 2), dtype=int),
        np.array(unmatched_dets),
        np.array(unmatched_trks),
    )


class SORTTracker:
    """SORT multi-object tracker."""

    def __init__(self, max_age: int = 30, min_hits: int = 3, iou_threshold: float = 0.3) -> None:
        self.max_age = max_age
        self.min_hits = min_hits
        self.iou_threshold = iou_threshold
        self.trackers: list[KalmanBoxTracker] = []
        self.frame_count = 0

    def update(self, detections: np.ndarray) -> np.ndarray:
        """
        Update tracker state.

        Args:
            detections: numpy array of shape (N, 5) → [x1,y1,x2,y2,score]

        Returns:
            numpy array of shape (M, 5) → [x1,y1,x2,y2,track_id]
        """
        self.frame_count += 1
        predicted = np.array([t.predict() for t in self.trackers])

        matched, unmatched_dets, unmatched_trks = _associate_detections(
            detections[:, :4] if len(detections) > 0 else np.empty((0, 4)),
            predicted if len(predicted) > 0 else np.empty((0, 4)),
            self.iou_threshold,
        )

        for m in matched:
            self.trackers[m[1]].update(detections[m[0], :4])

        for d in unmatched_dets:
            self.trackers.append(KalmanBoxTracker(detections[d, :4]))

        results = []
        to_remove = []
        for i, trk in enumerate(self.trackers):
            state = trk.get_state()
            if (trk.time_since_update <= 1) and (trk.hit_streak >= self.min_hits or self.frame_count <= self.min_hits):
                results.append(np.concatenate([state.flatten(), [trk.id + 1]]))
            if trk.time_since_update > self.max_age:
                to_remove.append(i)

        for i in reversed(to_remove):
            self.trackers.pop(i)

        return np.array(results) if results else np.empty((0, 5))
