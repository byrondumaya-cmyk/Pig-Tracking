"""
scripts/merge_datasets.py
Phase 3 — Dataset Merger

PURPOSE:
    Merges multiple YOLO datasets into one canonical dataset.
    Remaps class IDs based on config/class_map.yaml.
    Filters out dropped classes (e.g., 'Feeder').
    Pools images into train/valid/test splits (80/10/10 ratio).

USAGE:
    python scripts/merge_datasets.py
"""

from __future__ import annotations

import os
import random
import shutil
import sys
from collections import defaultdict
from pathlib import Path

import yaml



ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def load_config() -> tuple[dict, dict, list]:
    cfg_path = ROOT / "config" / "class_map.yaml"
    with open(cfg_path, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    
    return cfg["dataset_1_map"], cfg["dataset_2_map"], cfg["drop_classes"]


def process_dataset(
    dataset_dir: Path,
    mapping: dict[str, int],
    drop_classes: list[str],
    original_classes: list[str],
    out_dir: Path,
    img_list: list[tuple[Path, Path]]  # (src_img, src_txt)
) -> None:
    """Read all images/labels, remap classes, and collect them."""
    for split in ["train", "valid", "test"]:
        img_dir = dataset_dir / split / "images"
        lbl_dir = dataset_dir / split / "labels"
        
        if not img_dir.exists() or not lbl_dir.exists():
            continue
            
        for img_path in img_dir.glob("*.*"):
            if img_path.suffix.lower() not in [".jpg", ".jpeg", ".png", ".bmp"]:
                continue
                
            txt_path = lbl_dir / f"{img_path.stem}.txt"
            if not txt_path.exists():
                continue
                
            # Process label file directly in memory to filter
            lines = txt_path.read_text(encoding="utf-8").strip().splitlines()
            new_lines = []
            
            for line in lines:
                parts = line.split()
                if not parts:
                    continue
                old_id = int(parts[0])
                if old_id >= len(original_classes):
                    continue
                
                old_name = original_classes[old_id]
                
                # Check if dropped
                if old_name in drop_classes:
                    continue
                    
                # Map to new ID
                if old_name in mapping:
                    new_id = mapping[old_name]
                    new_lines.append(f"{new_id} {' '.join(parts[1:])}")
                else:
                    # If not mapped and not dropped, we print a warning
                    pass
            
            # If we have valid labels left, we save to a temporary file
            if new_lines:
                temp_txt = ROOT / "data" / f"temp_{dataset_dir.name}_{txt_path.name}"
                temp_txt.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
                img_list.append((img_path, temp_txt))


def main() -> None:
    print("\n============================================================")
    print(" SWINE HEALTH MONITOR — Dataset Merger (Phase 3)")
    print("============================================================\n")
    
    d1_map, d2_map, drop = load_config()
    
    d1_dir = ROOT / "datasets" / "dataset_1_pig-behavior-wlvku"
    d2_dir = ROOT / "datasets" / "dataset_2_pig-behavior-8xbgn"
    
    out_train_img = ROOT / "data" / "train" / "images"
    out_train_lbl = ROOT / "data" / "train" / "labels"
    out_valid_img = ROOT / "data" / "valid" / "images"
    out_valid_lbl = ROOT / "data" / "valid" / "labels"
    out_test_img  = ROOT / "data" / "test" / "images"
    out_test_lbl  = ROOT / "data" / "test" / "labels"
    
    # Clear output directories if they have contents
    for d in [out_train_img, out_train_lbl, out_valid_img, out_valid_lbl, out_test_img, out_test_lbl]:
        d.mkdir(parents=True, exist_ok=True)
        # We don't wipe entirely just in case, but warn
    
    # Get original classes
    with open(d1_dir / "data.yaml", "r", encoding="utf-8") as f:
        d1_classes = yaml.safe_load(f)["names"]
        if isinstance(d1_classes, dict): d1_classes = [d1_classes[i] for i in sorted(d1_classes.keys())]
        
    with open(d2_dir / "data.yaml", "r", encoding="utf-8") as f:
        d2_classes = yaml.safe_load(f)["names"]
        if isinstance(d2_classes, dict): d2_classes = [d2_classes[i] for i in sorted(d2_classes.keys())]
        
    all_images = []  # List of (source_img_path, temp_txt_path)
    
    print("Parsing Dataset 1...")
    process_dataset(d1_dir, d1_map, drop, d1_classes, ROOT / "data", all_images)
    
    print("Parsing Dataset 2...")
    process_dataset(d2_dir, d2_map, drop, d2_classes, ROOT / "data", all_images)
    
    # Shuffle randomly for split
    random.seed(42)  # For reproducibility
    random.shuffle(all_images)
    
    total = len(all_images)
    train_end = int(total * 0.8)
    valid_end = int(total * 0.9)
    
    splits = (
        all_images[:train_end],
        all_images[train_end:valid_end],
        all_images[valid_end:]
    )
    dirs = [
        (out_train_img, out_train_lbl),
        (out_valid_img, out_valid_lbl),
        (out_test_img, out_test_lbl)
    ]
    split_names = ["Train (80%)", "Valid (10%)", "Test (10%)"]
    
    print(f"\nMerging {total} valid image-label pairs...")
    
    # Prefix mapping to avoid filename collisions
    idx = 0
    for split_data, (d_img, d_lbl), sname in zip(splits, dirs, split_names):
        print(f"  Copying {sname} - {len(split_data)} images...")
        for src_img, src_txt in split_data:
            # Unique filename
            new_name = f"merge_{idx:06d}"
            
            # Copy image
            dest_img = d_img / f"{new_name}{src_img.suffix}"
            shutil.copy2(src_img, dest_img)
            
            # Copy label (and delete temp file)
            dest_txt = d_lbl / f"{new_name}.txt"
            shutil.copy2(src_txt, dest_txt)
            try:
                src_txt.unlink()
            except OSError:
                pass
            
            idx += 1
            
    print("\n✅ Dataset Merge Complete.")
    print("Data is ready for training in data/ directory.")

if __name__ == "__main__":
    main()
