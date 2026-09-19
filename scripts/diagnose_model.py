"""
scripts/diagnose_model.py
Phase 2 — Diagnostic Script

PURPOSE:
    Runs inference on a folder of test images using the provided ONNX model.
    Outputs: detection counts, confidence histograms, and class frequency.
    Does not require a .pt file or a full test dataset configuration.
    
USAGE:
    python scripts/diagnose_model.py --image-dir data/test/images/
"""

import argparse
import sys
from pathlib import Path
import json

import cv2
import numpy as np
try:
    import onnxruntime as ort
except ImportError:
    print("onnxruntime not installed. Cannot run diagnosis.")
    sys.exit(1)

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.inference.detector import PigDetector
from config.class_map import get_class_names # Need to make sure this exists or just hardcode for diagnosis

def main():
    parser = argparse.ArgumentParser(description="Diagnose YOLOv8 ONNX Model")
    parser.add_argument("--image-dir", type=str, required=True, help="Path to test images")
    parser.add_argument("--model", type=str, default=str(ROOT / "models" / "best.onnx"), help="Path to ONNX model")
    parser.add_argument("--conf", type=float, default=0.25, help="Confidence threshold for diagnosis (use low to see distribution)")
    args = parser.parse_args()

    image_dir = Path(args.image_dir)
    if not image_dir.exists() or not image_dir.is_dir():
        print(f"Error: {image_dir} not found.")
        sys.exit(1)

    model_path = Path(args.model)
    if not model_path.exists():
        print(f"Error: {model_path} not found.")
        sys.exit(1)

    detector = PigDetector(
        model_path=str(model_path),
        confidence_threshold=args.conf,
        iou_threshold=0.45,
        input_size=640
    )

    image_files = list(image_dir.glob("*.jpg")) + list(image_dir.glob("*.png"))
    print(f"Found {len(image_files)} images for diagnosis.")

    if not image_files:
        print("No images to process.")
        sys.exit(0)

    stats = {
        "total_images": len(image_files),
        "total_detections": 0,
        "class_counts": {},
        "confidence_buckets": {
            "0.0-0.2": 0, "0.2-0.4": 0, "0.4-0.6": 0, "0.6-0.8": 0, "0.8-1.0": 0
        }
    }

    print(f"Running inference (conf >= {args.conf})...")
    
    for i, img_path in enumerate(image_files[:500]): # Limit to 500 for speed
        img = cv2.imread(str(img_path))
        if img is None:
            continue
            
        detections = detector.detect(img)
        stats["total_detections"] += len(detections)
        
        for d in detections:
            cid = d["class_id"]
            conf = d["confidence"]
            
            stats["class_counts"][cid] = stats["class_counts"].get(cid, 0) + 1
            
            if conf < 0.2: stats["confidence_buckets"]["0.0-0.2"] += 1
            elif conf < 0.4: stats["confidence_buckets"]["0.2-0.4"] += 1
            elif conf < 0.6: stats["confidence_buckets"]["0.4-0.6"] += 1
            elif conf < 0.8: stats["confidence_buckets"]["0.6-0.8"] += 1
            else: stats["confidence_buckets"]["0.8-1.0"] += 1
            
        if (i+1) % 50 == 0:
            print(f"Processed {i+1} images...")

    print("\n" + "="*40)
    print(" DIAGNOSIS REPORT ")
    print("="*40)
    print(json.dumps(stats, indent=2))
    print("="*40)

if __name__ == "__main__":
    main()
