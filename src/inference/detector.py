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
import time
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
        enable_profiling: bool = False,
    ) -> None:
        self._conf_thresh = confidence_threshold
        self._iou_thresh = iou_threshold
        self._input_size = input_size
        self._session = None
        self._enable_profiling = enable_profiling
        self._timing_stats = {"preprocess": [], "inference": [], "postprocess": []}

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

        # Validate that the model input size aligns with the configured input_size.
        input_shape = self._session.get_inputs()[0].shape
        if len(input_shape) != 4 or input_shape[1] != 3:
            raise ValueError(
                f"Unsupported ONNX input shape {input_shape}. Expected [1,3,H,W]."
            )
        if input_shape[2] != input_shape[3]:
            raise ValueError(
                f"ONNX model input must be square, got {input_shape[2]}x{input_shape[3]}"
            )
        model_size = int(input_shape[2])
        if self._input_size != model_size:
            raise ValueError(
                f"Configured input_size={self._input_size} does not match ONNX model size={model_size}."
            )

        logger.info(f"ONNX model loaded from {model_path} with input size {model_size}.")

    def get_timing_stats(self) -> dict:
        """Return timing statistics if profiling was enabled."""
        import numpy as np
        stats = {}
        for key, times in self._timing_stats.items():
            if times:
                stats[key] = {
                    "mean_ms": np.mean(times) * 1000,
                    "min_ms": np.min(times) * 1000,
                    "max_ms": np.max(times) * 1000,
                    "count": len(times),
                }
        return stats

    def detect(self, frame: np.ndarray) -> List[dict]:
        """
        Run inference on a BGR OpenCV frame.

        Returns:
            List of dicts: [{'bbox': (x1,y1,x2,y2), 'confidence': float, 'class_id': int}]
        """
        if self._session is None:
            return []

        if self._enable_profiling:
            t0 = time.perf_counter()
        img, scale, pad = self._preprocess(frame)
        if self._enable_profiling:
            self._timing_stats["preprocess"].append(time.perf_counter() - t0)
            t0 = time.perf_counter()

        outputs = self._session.run(None, {self._input_name: img})
        if self._enable_profiling:
            self._timing_stats["inference"].append(time.perf_counter() - t0)
            t0 = time.perf_counter()

        results = self._postprocess(outputs[0], scale, pad, frame.shape)
        if self._enable_profiling:
            self._timing_stats["postprocess"].append(time.perf_counter() - t0)

        return results

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
