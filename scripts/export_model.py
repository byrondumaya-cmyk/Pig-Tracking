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

    weights_path = ROOT / "runs" / "detect" / "swine_behavior_v1_cpu_resume" / "weights" / "best.pt"
    if not weights_path.exists():
        print(f"Error: Could not find weights at {weights_path}")
        sys.exit(1)

    print(f"Loading PyTorch model: {weights_path}")
    model = YOLO(str(weights_path))

    print("\nExporting model to ONNX...")
    print("Settings: format='onnx', opset=12, dynamic=False, simplify=True")
    
    # Export to ONNX
    exported_path_str = model.export(
        format="onnx",
        opset=12,
        dynamic=False,
        simplify=True
    )
    
    exported_path = Path(exported_path_str)
    
    # Ensure models/ directory exists
    models_dir = ROOT / "models"
    models_dir.mkdir(exist_ok=True)
    
    # Move the exported model to the models directory
    final_dest = models_dir / "best.onnx"
    
    # Copy best.pt as well for safekeeping
    shutil.copy(weights_path, models_dir / "best.pt")
    
    # Move the ONNX file
    if exported_path.exists():
        shutil.move(str(exported_path), str(final_dest))
        print(f"\n✅ Successfully exported ONNX model!")
        print(f"   Size: {final_dest.stat().st_size / (1024 * 1024):.2f} MB")
        print(f"   Saved to: {final_dest}")
    else:
        print("\n❌ Error: Export failed or ONNX file not found.")
        sys.exit(1)

if __name__ == "__main__":
    main()
