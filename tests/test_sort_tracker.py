import numpy as np
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.tracking.sort_tracker import SORTTracker


def test_sort_tracker_returns_correct_shape_and_ids():
    tracker = SORTTracker(max_age=10, min_hits=1, iou_threshold=0.3)
    detections = np.array([[50.0, 50.0, 150.0, 150.0, 0.9]])

    output = tracker.update(detections)

    assert output.shape[1] == 5
    assert output.shape[0] == 1
    assert output[0, 4] == 1
    assert output[0, 0] >= 0
    assert output[0, 1] >= 0
    assert output[0, 2] > output[0, 0]
    assert output[0, 3] > output[0, 1]
