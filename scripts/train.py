"""
scripts/train.py
Phase 4 — YOLOv8 Model Training

PURPOSE:
    Trains the YOLOv8n model on the merged dataset using the PC's GPU.
    Uses configuration from data/data.yaml.
    Saves the best model weights for later export.

USAGE:
    python scripts/train.py
"""

from __future__ import annotations

import sys
from pathlib import Path
from ultralytics import YOLO
import argparse

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

def main() -> None:
    parser = argparse.ArgumentParser(description="SWINE HEALTH MONITOR — YOLOv8 Training")
    parser.add_argument("--resume", action="store_true", help="Resume from last checkpoint")
    args = parser.parse_args()

    print("\n============================================================")
    print(" SWINE HEALTH MONITOR — YOLOv8 Training (Phase 4)")
    print("============================================================\n")

    data_yaml = ROOT / "data" / "data.yaml"
    if not data_yaml.exists():
        print(f"Error: {data_yaml} not found. Did you run the merge script?")
        sys.exit(1)

    # YOLOv8 path resolution can be tricky on Windows.
    # We dynamically create an absolute-pathed YAML for training.
    import yaml
    with open(data_yaml, "r") as f:
        cfg = yaml.safe_load(f)
    
    cfg["path"] = str(ROOT / "data")
    
    runtime_yaml = ROOT / "data" / "data_runtime.yaml"
    with open(runtime_yaml, "w") as f:
        yaml.safe_dump(cfg, f)

    import torch
    if not torch.cuda.is_available():
        print("\n" + "!"*60)
        print("WARNING: CUDA GPU not detected by PyTorch!")
        print("Training will fall back to CPU, which is VERY slow.")
        print("To fix this, cancel (Ctrl+C) and run:")
        print("pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121")
        print("!"*60 + "\n")
        device_arg = "cpu"
    else:
        device_arg = 0  # Use first GPU

    if args.resume:
        last_weights = ROOT / "runs" / "detect" / "swine_behavior_v1" / "weights" / "last.pt"
        if not last_weights.exists():
            print(f"Error: Checkpoint {last_weights} not found. Cannot resume.")
            sys.exit(1)
        print(f"Loading checkpoint for resumption: {last_weights}")
        model = YOLO(str(last_weights))
        
        if device_arg == "cpu":
            print("\nWARNING: CPU detected. We cannot strictly 'resume' the optimizer state from a GPU checkpoint.")
            print("Falling back to CPU mode: epochs will reset to 0, but the learned weights are retained.")
            results = model.train(
                data=str(runtime_yaml),
                epochs=27,            # 100 - 73 epochs remaining
                patience=20,
                batch=16,
                imgsz=640,
                device="cpu",
                project=str(ROOT / "runs" / "detect"),
                name="swine_behavior_v1_cpu_resume",
                exist_ok=True,
                optimizer="auto",
                verbose=True,
            )
        else:
            print("\nResuming training... (This will take a while, ensure you have GPU access)")
            # Train the model (resuming)
            results = model.train(resume=True)
    else:
        print("Loading YOLOv8n base model...")
        # Using the nano model as required for Raspberry Pi performance
        model = YOLO("yolov8n.pt") 
        print("\nStarting training... (This will take a while, ensure you have GPU access)")

        # Train the model (new)
        # Adjust epochs, batch size, and imgsz based on your GPU capabilities
        results = model.train(
            data=str(runtime_yaml),
            epochs=100,           # Good baseline for custom datasets
            patience=20,          # Early stopping
            batch=16,             # Adjust down if CUDA out of memory
            imgsz=640,            # Standard YOLOv8 resolution
            device=device_arg,    # Auto-detected device
            project=str(ROOT / "runs" / "detect"),
            name="swine_behavior_v1",
            exist_ok=True,        # Overwrite if exists
            optimizer="auto",
            verbose=True,
        )
    
    print("\n============================================================")
    print("✅ Training Complete!")
    print(f"Best model saved to: {ROOT / 'runs' / 'detect' / 'swine_behavior_v1' / 'weights' / 'best.pt'}")
    print("Next step: Run python scripts/export_model.py (Phase 6)")
    print("============================================================\n")

if __name__ == "__main__":
    main()
