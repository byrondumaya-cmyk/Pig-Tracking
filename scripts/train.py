"""
scripts/train.py
Phase 4 — YOLOv8 Model Training

PURPOSE:
    Trains the YOLOv8 model on the merged dataset.
    Uses configuration from scripts/retrain_config.yaml for complete reproducibility.
    Saves the best model weights for later export.

USAGE:
    python scripts/train.py
"""

from __future__ import annotations

import sys
from pathlib import Path
import argparse
import yaml

try:
    from ultralytics import YOLO
except ImportError:
    print("ultralytics YOLO not installed. Please pip install ultralytics.")
    sys.exit(1)

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

def main() -> None:
    parser = argparse.ArgumentParser(description="SWINE HEALTH MONITOR — YOLOv8 Training")
    parser.add_argument("--resume", action="store_true", help="Resume from last checkpoint")
    args = parser.parse_args()

    print("\n============================================================")
    print(" SWINE HEALTH MONITOR — YOLOv8 Training (Phase 4)")
    print("============================================================\n")

    config_path = ROOT / "scripts" / "retrain_config.yaml"
    if not config_path.exists():
        print(f"Error: {config_path} not found.")
        sys.exit(1)
        
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)

    data_yaml = ROOT / config['dataset']['path']
    if not data_yaml.exists():
        print(f"Error: {data_yaml} not found. Did you run the merge script?")
        sys.exit(1)

    # YOLOv8 path resolution can be tricky on Windows.
    # We dynamically create an absolute-pathed YAML for training.
    with open(data_yaml, "r") as f:
        data_cfg = yaml.safe_load(f)
    
    data_cfg["path"] = str(ROOT / "data")
    
    runtime_yaml = ROOT / "data" / "data_runtime.yaml"
    with open(runtime_yaml, "w") as f:
        yaml.safe_dump(data_cfg, f)

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

    model_name = config['model']['name']

    if args.resume:
        last_weights = ROOT / "runs" / "detect" / model_name / "weights" / "last.pt"
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
                epochs=config['training']['epochs'],
                patience=config['training']['patience'],
                batch=config['training']['batch'],
                imgsz=config['training']['imgsz'],
                device="cpu",
                project=str(ROOT / "runs" / "detect"),
                name=f"{model_name}_cpu_resume",
                exist_ok=True,
                optimizer="auto",
                verbose=True,
            )
        else:
            print("\nResuming training... (This will take a while, ensure you have GPU access)")
            results = model.train(resume=True)
    else:
        base_model = config['model']['base']
        print(f"Loading Base Model: {base_model}")
        model = YOLO(base_model)
        print("\nStarting training... (This will take a while, ensure you have GPU access)")

        # Train the model (new)
        results = model.train(
            data=str(runtime_yaml),
            epochs=config['training']['epochs'],
            patience=config['training']['patience'],
            batch=config['training']['batch'],
            imgsz=config['training']['imgsz'],
            optimizer=config['training']['optimizer'],
            lr0=config['training']['lr0'],
            device=device_arg,
            project=str(ROOT / "runs" / "detect"),
            name=model_name,
            exist_ok=True,
            verbose=True,
            workers=0,       # CRITICAL: Windows cannot fork DataLoader workers (cuDNN crash fix)
            amp=False,       # Disabled AMP: cuDNN execution failed with it enabled
            
            # Augmentations
            degrees=config['augmentation']['degrees'],
            flipud=config['augmentation']['flipud'],
            fliplr=config['augmentation']['fliplr'],
            mosaic=config['augmentation']['mosaic'],
            mixup=config['augmentation']['mixup'],
            hsv_h=config['augmentation']['hsv_h'],
            hsv_s=config['augmentation']['hsv_s'],
            hsv_v=config['augmentation']['hsv_v']
        )
    
    print("\n============================================================")
    print("✅ Training Complete!")
    print(f"Best model saved to: {ROOT / 'runs' / 'detect' / model_name / 'weights' / 'best.pt'}")
    print("Next step: Run python scripts/export_model.py (Phase 6)")
    print("============================================================\n")

if __name__ == "__main__":
    main()
