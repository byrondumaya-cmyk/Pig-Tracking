"""
src/inference/detector.py
YOLOv8n ONNX Inference Wrapper

PURPOSE:
    Loads the exported best.onnx model and runs inference on camera frames.
    Returns a list of detection dicts for each detected object in the frame.

DESIGN:
    - Uses ONNX Runtime for CPU-optimized inference (no PyTorch on Pi)
    - Pre-processes frames to 640x640 with letterboxing (preserves aspect ratio)
    - Applies NMS (Non-Maximum Suppression) internally

VERIFY:
    python3 -c "import onnxruntime; print(onnxruntime.__version__)"
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import List

import cv2
import numpy as np

logger = logging.getLogger(__name__)

try:
    import onnxruntime as ort
    _ORT_AVAILABLE = True
except ImportError:
    _ORT_AVAILABLE = False
    logger.error("onnxruntime not installed. Run: pip install onnxruntime")


class PigDetector:
    """
    Runs YOLOv8n ONNX inference on camera frames.
    Returns structured detection dicts compatible with PigTracker.
    """

    def __init__(
        self,
        model_path: str | Path,
        confidence_threshold: float = 0.45,
        iou_threshold: float = 0.45,
        input_size: int = 640,
        intra_op_threads: int = 4,
        inter_op_threads: int = 1,
    ) -> None:
        self._conf_thresh = confidence_threshold
        self._iou_thresh = iou_threshold
        self._input_size = input_size
        self._session = None

        if not _ORT_AVAILABLE:
            logger.error("ONNX Runtime unavailable. Detector will return empty results.")
            return

        model_path = Path(model_path)
        if not model_path.exists():
            raise FileNotFoundError(f"ONNX model not found: {model_path}")

        opts = ort.SessionOptions()
        opts.intra_op_num_threads = intra_op_threads
        opts.inter_op_num_threads = inter_op_threads
        opts.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL

        self._session = ort.InferenceSession(str(model_path), sess_options=opts)
        self._input_name = self._session.get_inputs()[0].name
        logger.info(f"ONNX model loaded from {model_path}")

    def detect(self, frame: np.ndarray) -> List[dict]:
        """
        Run inference on a BGR OpenCV frame.

        Returns:
            List of dicts: [{'bbox': (x1,y1,x2,y2), 'confidence': float, 'class_id': int}]
        """
        if self._session is None:
            return []

        img, scale, pad = self._preprocess(frame)
        outputs = self._session.run(None, {self._input_name: img})
        return self._postprocess(outputs[0], scale, pad, frame.shape)

    def _preprocess(self, frame: np.ndarray) -> tuple:
        """Letterbox resize + normalize to [0,1] + NCHW format."""
        h, w = frame.shape[:2]
        scale = min(self._input_size / h, self._input_size / w)
        new_w, new_h = int(w * scale), int(h * scale)
        resized = cv2.resize(frame, (new_w, new_h))

        pad_w = (self._input_size - new_w) // 2
        pad_h = (self._input_size - new_h) // 2
        padded = cv2.copyMakeBorder(resized, pad_h, pad_h, pad_w, pad_w, cv2.BORDER_CONSTANT, value=114)
        padded = padded[:self._input_size, :self._input_size]  # Ensure exact size

        img = padded.astype(np.float32) / 255.0
        img = img[:, :, ::-1]           # BGR → RGB
        img = img.transpose(2, 0, 1)    # HWC → CHW
        img = np.expand_dims(img, 0)    # → NCHW
        return img, scale, (pad_w, pad_h)

    def _postprocess(
        self,
        output: np.ndarray,
        scale: float,
        pad: tuple,
        orig_shape: tuple,
    ) -> List[dict]:
        """
        Parse YOLOv8 output [1, 4+num_classes, num_anchors].
        Applies confidence filter + NMS.
        """
        # YOLOv8 ONNX output: (1, 4+C, 8400) → transpose to (8400, 4+C)
        preds = output[0].T  # → (8400, 4+num_classes)

        boxes = preds[:, :4]           # cx, cy, w, h
        scores = preds[:, 4:]          # class scores

        class_ids = np.argmax(scores, axis=1)
        confidences = scores[np.arange(len(scores)), class_ids]

        # Filter by confidence
        mask = confidences >= self._conf_thresh
        boxes = boxes[mask]
        confidences = confidences[mask]
        class_ids = class_ids[mask]

        if len(boxes) == 0:
            return []

        # Convert cx,cy,w,h → x1,y1,x2,y2 in original frame coords
        pad_w, pad_h = pad
        x1 = (boxes[:, 0] - boxes[:, 2] / 2 - pad_w) / scale
        y1 = (boxes[:, 1] - boxes[:, 3] / 2 - pad_h) / scale
        x2 = (boxes[:, 0] + boxes[:, 2] / 2 - pad_w) / scale
        y2 = (boxes[:, 1] + boxes[:, 3] / 2 - pad_h) / scale

        # Clip to frame bounds
        orig_h, orig_w = orig_shape[:2]
        x1 = np.clip(x1, 0, orig_w)
        y1 = np.clip(y1, 0, orig_h)
        x2 = np.clip(x2, 0, orig_w)
        y2 = np.clip(y2, 0, orig_h)

        # NMS using OpenCV (CPU, no torch needed)
        indices = cv2.dnn.NMSBoxes(
            bboxes=[[float(x1[i]), float(y1[i]), float(x2[i] - x1[i]), float(y2[i] - y1[i])] for i in range(len(x1))],
            scores=confidences.tolist(),
            score_threshold=self._conf_thresh,
            nms_threshold=self._iou_thresh,
        )

        results = []
        for idx in (indices.flatten() if len(indices) > 0 else []):
            results.append({
                "bbox": (float(x1[idx]), float(y1[idx]), float(x2[idx]), float(y2[idx])),
                "confidence": float(confidences[idx]),
                "class_id": int(class_ids[idx]),
            })
        return results
