"""
scripts/validate_labels.py
Phase 3 — Label Validator

PURPOSE:
    Runs after the dataset merge to ensure the final dataset
    (in data/) is 100% clean and ready for YOLOv8 training.
    
    Checks for:
    - Empty label files
    - Label files missing images
    - Image files missing labels
    - Out of bounds bounding boxes (<0 or >1)
    - Invalid class IDs (must be 0-7)

USAGE:
    python scripts/validate_labels.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def validate_dataset(data_yaml_path: Path) -> None:
    if not data_yaml_path.exists():
        print(f"Error: {data_yaml_path} not found.")
        return
        
    with open(data_yaml_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
        
    nc = data.get("nc", 8)
    data_dir = data_yaml_path.parent
    
    issues = []
    
    for split in ["train", "valid", "test"]:
        img_dir = data_dir / split / "images"
        lbl_dir = data_dir / split / "labels"
        
        if not img_dir.exists() or not lbl_dir.exists():
            continue
            
        imgs = set(p.stem for p in img_dir.glob("*.*") if p.suffix.lower() in [".jpg", ".png", ".jpeg"])
        lbls = set(p.stem for p in lbl_dir.glob("*.txt"))
        
        missing_lbls = imgs - lbls
        missing_imgs = lbls - imgs
        
        for m in missing_lbls:
            issues.append(f"[{split}] Image missing label file: {m}")
        for m in missing_imgs:
            issues.append(f"[{split}] Label missing image file: {m}.txt")
            
        for txt_path in lbl_dir.glob("*.txt"):
            if txt_path.stem in missing_imgs:
                continue
                
            content = txt_path.read_text(encoding="utf-8").strip()
            if not content:
                issues.append(f"[{split}] Empty label file: {txt_path.name}")
                # Remove empty labels and their images to keep things clean?
                continue
                
            for i, line in enumerate(content.splitlines(), 1):
                parts = line.split()
                if len(parts) != 5:
                    issues.append(f"[{split}] {txt_path.name}:{i} - Bad format, need 5 values")
                    continue
                    
                cls_id = int(parts[0])
                if cls_id < 0 or cls_id >= nc:
                    issues.append(f"[{split}] {txt_path.name}:{i} - Invalid class ID {cls_id} (max {nc-1})")
                    
                try:
                    x, y, w, h = map(float, parts[1:])
                    if not (0.0 <= x <= 1.0 and 0.0 <= y <= 1.0 and 0.0 < w <= 1.0 and 0.0 < h <= 1.0):
                        issues.append(f"[{split}] {txt_path.name}:{i} - Out of bounds box: {x},{y},{w},{h}")
                except ValueError:
                    issues.append(f"[{split}] {txt_path.name}:{i} - Non-float values for bbox")

    print("\n============================================================")
    print(" SWINE HEALTH MONITOR — Final Label Validator")
    print("============================================================\n")
    if not issues:
        print("✅ VALIDATION PASSED: 0 errors found.")
        print("Dataset is 100% clean and ready for YOLOv8.")
    else:
        print(f"❌ VALIDATION FAILED: {len(issues)} errors found.\n")
        for issue in issues[:30]:
            print(f"  - {issue}")
        if len(issues) > 30:
            print(f"  ... and {len(issues) - 30} more.")

if __name__ == "__main__":
    validate_dataset(ROOT / "data" / "data.yaml")
