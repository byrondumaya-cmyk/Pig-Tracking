"""
scripts/export_model.py
Phase 6 — ONNX Export

PURPOSE:
    Exports the trained PyTorch YOLOv8 model (best.pt) to ONNX format.
    Optimizes for Raspberry Pi 4 CPU with opset=12 and simplification.

USAGE:
    python scripts/export_model.py
"""

from __future__ import annotations

import sys
import shutil
from pathlib import Path
from ultralytics import YOLO

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

def main() -> None:
    print("\n============================================================")
    print(" SWINE HEALTH MONITOR — Phase 6: ONNX Export")
    print("============================================================\n")

    # Use v2 weights (fresh training run)
    weights_path = ROOT / "runs" / "detect" / "swine_behavior_v2" / "weights" / "best.pt"
    if not weights_path.exists():
        print(f"Error: Could not find weights at {weights_path}")
        print("Did you complete training with: python scripts/train.py ?")
        sys.exit(1)

    print(f"Loading PyTorch model: {weights_path}")
    model = YOLO(str(weights_path))

    print("\nExporting model to ONNX...")
    print("Settings: format='onnx', imgsz=640")

    # Export to ONNX (Supported on Windows)
    # TFLite/LiteRT export via Ultralytics is currently only supported on Linux/macOS
    model.export(
        format="onnx",
        simplify=True,
        imgsz=640,
    )

    # Ultralytics saves the exported model next to the .pt file
    onnx_path = weights_path.with_suffix(".onnx")

    # Ensure models/ directory exists
    models_dir = ROOT / "models"
    models_dir.mkdir(exist_ok=True)

    final_dest = models_dir / "best.onnx"
    pt_dest = models_dir / "best.pt"

    # Copy best.pt to models/ for safekeeping
    shutil.copy(weights_path, pt_dest)
    print(f"   Copied best.pt → {pt_dest}")

    # Move ONNX to models/
    if onnx_path.exists():
        shutil.move(str(onnx_path), str(final_dest))

        # Write model_info.json — consumed by Flask API and Flutter app
        import json
        from datetime import datetime
        info = {
            "model_name": "swine_behavior_v2",
            "model_version": "2.0.0",
            "base_model": "yolov8n",
            "training_run": "swine_behavior_v2",
            "onnx_file": "best.onnx",
            "pt_file": "best.pt",
            "input_size": 640,
            "num_classes": 8,
            "class_names": [
                "lying", "standing", "walking", "sitting",
                "feeding", "drinking", "social_interaction", "aggression"
            ],
            "map50_val": 0.7409,
            "export_date": datetime.now().isoformat(),
            "format": "ONNX"
        }
        with open(models_dir / "model_info.json", "w") as f:
            json.dump(info, f, indent=2)

        print(f"\n✅ Successfully exported ONNX model!")
        print(f"   Size: {final_dest.stat().st_size / (1024 * 1024):.2f} MB")
        print(f"   Saved to: {final_dest}")
    else:
        print("\n❌ Error: Export failed or ONNX file not found.")
        sys.exit(1)

if __name__ == "__main__":
    main()
