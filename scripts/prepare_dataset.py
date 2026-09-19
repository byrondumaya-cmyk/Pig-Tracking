"""
scripts/prepare_dataset.py
Phase 2 — Dataset Preparation (Symlink / Copy)

PURPOSE:
    Copies or symlinks the Roboflow-downloaded datasets from the Windows
    Downloads folder into the project's datasets/ directory so that
    merge_datasets.py can find them in the expected locations.

    Source datasets (from Downloads):
      - pig-behavior.v1i.yolov8    → datasets/dataset_1_pig-behavior-wlvku
      - Pig Behavior.v1i.yolov8   → datasets/dataset_2_pig-behavior-8xbgn

USAGE:
    python scripts/prepare_dataset.py
    python scripts/prepare_dataset.py --copy    # actual copy instead of symlink
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOWNLOADS = Path.home() / "Downloads"

DATASET_MAP = {
    "dataset_1_pig-behavior-wlvku": DOWNLOADS / "pig-behavior.v1i.yolov8",
    "dataset_2_pig-behavior-8xbgn": DOWNLOADS / "Pig Behavior.v1i.yolov8",
}


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepare datasets for merge_datasets.py")
    parser.add_argument("--copy", action="store_true", help="Copy files instead of symlinking")
    args = parser.parse_args()

    print("\n============================================================")
    print(" SWINE HEALTH MONITOR - Dataset Preparation")
    print("============================================================\n")

    datasets_dir = ROOT / "datasets"
    datasets_dir.mkdir(exist_ok=True)

    all_ok = True
    for dest_name, src_path in DATASET_MAP.items():
        dest_path = datasets_dir / dest_name
        
        if not src_path.exists():
            print(f"  ERROR: Source not found: {src_path}")
            print(f"         Please download the dataset from Roboflow first.")
            all_ok = False
            continue

        if dest_path.exists() or dest_path.is_symlink():
            print(f"  SKIP: {dest_name} already exists at {dest_path}")
            continue

        if args.copy:
            print(f"  Copying {src_path.name} -> datasets/{dest_name} ...")
            shutil.copytree(src_path, dest_path)
            print(f"    Done.")
        else:
            # Try symlink first (fast, space-efficient)
            try:
                dest_path.symlink_to(src_path)
                print(f"  Linked: {src_path.name} -> datasets/{dest_name}")
            except (OSError, NotImplementedError) as e:
                print(f"  Symlink failed ({e}), falling back to copy...")
                shutil.copytree(src_path, dest_path)
                print(f"  Copied: {src_path.name} -> datasets/{dest_name}")

    if all_ok:
        print("\nDataset preparation complete! You can now run:")
        print("    python scripts/merge_datasets.py")
    else:
        print("\nFix missing dataset paths above before proceeding.")
        sys.exit(1)


if __name__ == "__main__":
    main()
