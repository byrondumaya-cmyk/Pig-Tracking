"""
scripts/inspect_datasets.py
Phase 2 — Dataset Inspection Tool

PURPOSE:
    Reads both downloaded Roboflow datasets and produces a detailed
    report on class distributions, image counts, label integrity,
    and potential issues BEFORE any merging happens.

USAGE:
    python scripts/inspect_datasets.py

OUTPUT:
    - Console table showing class counts for both datasets
    - Overlap analysis (classes that appear in both)
    - List of potential merge conflicts
    - Warnings for empty labels, missing images, corrupt boxes
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from collections import defaultdict
from typing import NamedTuple

import yaml


# -- Project root resolution ----------------------------------------------
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


# -- Constants ------------------------------------------------------------
DATASET_DIRS = {
    "Dataset 1 (wlvku)": ROOT / "datasets" / "dataset_1_pig-behavior-wlvku",
    "Dataset 2 (8xbgn)": ROOT / "datasets" / "dataset_2_pig-behavior-8xbgn",
}

SPLITS = ["train", "valid", "test"]

# Colors for terminal output
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
CYAN = "\033[96m"
RESET = "\033[0m"
BOLD = "\033[1m"


# -- Data structures ------------------------------------------------------
class DatasetStats(NamedTuple):
    name: str
    class_names: list[str]
    class_counts: dict[str, int]   # class_name -> total annotation count
    image_counts: dict[str, int]   # split -> image count
    issues: list[str]              # Warning messages


# -- Core inspection functions --------------------------------------------

def load_data_yaml(dataset_dir: Path) -> dict:
    """Load data.yaml from a dataset directory."""
    yaml_path = dataset_dir / "data.yaml"
    if not yaml_path.exists():
        raise FileNotFoundError(f"data.yaml not found in: {dataset_dir}")
    with open(yaml_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def parse_class_names(data: dict) -> list[str]:
    """Extract class names from a data.yaml dict (handles dict or list format)."""
    names = data.get("names", [])
    if isinstance(names, dict):
        return [names[i] for i in sorted(names.keys())]
    return list(names)


def count_images(dataset_dir: Path) -> dict[str, int]:
    """Count images per split."""
    counts: dict[str, int] = {}
    for split in SPLITS:
        img_dir = dataset_dir / split / "images"
        if img_dir.exists():
            counts[split] = len(list(img_dir.glob("*")))
        else:
            counts[split] = 0
    return counts


def inspect_labels(
    dataset_dir: Path,
    class_names: list[str],
) -> tuple[dict[str, int], list[str]]:
    """
    Scan all label files across all splits.

    Returns:
        class_counts: Mapping of class_name -> total annotation count
        issues: List of warning strings for problem files
    """
    class_counts: dict[str, int] = defaultdict(int)
    issues: list[str] = []
    nc = len(class_names)

    for split in SPLITS:
        label_dir = dataset_dir / split / "labels"
        img_dir = dataset_dir / split / "images"
        if not label_dir.exists():
            continue

        label_files = list(label_dir.glob("*.txt"))
        for label_file in label_files:
            # Check paired image exists
            stem = label_file.stem
            has_image = any(
                (img_dir / f"{stem}{ext}").exists()
                for ext in [".jpg", ".jpeg", ".png", ".bmp"]
            )
            if not has_image:
                issues.append(f"[{split}] Missing image for label: {label_file.name}")

            # Parse label file
            lines = label_file.read_text(encoding="utf-8").strip().splitlines()
            if not lines:
                issues.append(f"[{split}] Empty label file: {label_file.name}")
                continue

            for line_num, line in enumerate(lines, 1):
                parts = line.strip().split()
                if len(parts) != 5:
                    issues.append(
                        f"[{split}] Bad format (expected 5 values) "
                        f"{label_file.name}:{line_num}: '{line[:50]}'"
                    )
                    continue

                try:
                    cls_id = int(parts[0])
                    x, y, w, h = float(parts[1]), float(parts[2]), float(parts[3]), float(parts[4])
                except ValueError:
                    issues.append(f"[{split}] Non-numeric values in {label_file.name}:{line_num}")
                    continue

                # Validate class ID
                if cls_id < 0 or cls_id >= nc:
                    issues.append(
                        f"[{split}] Invalid class ID {cls_id} (max={nc-1}) "
                        f"in {label_file.name}:{line_num}"
                    )
                    continue

                # Validate bounding box ranges (YOLOv8 normalized 0–1)
                if not (0.0 <= x <= 1.0 and 0.0 <= y <= 1.0 and 0.0 < w <= 1.0 and 0.0 < h <= 1.0):
                    issues.append(
                        f"[{split}] Out-of-range bbox [{x:.3f},{y:.3f},{w:.3f},{h:.3f}] "
                        f"in {label_file.name}:{line_num}"
                    )

                class_counts[class_names[cls_id]] += 1

    return dict(class_counts), issues


def inspect_dataset(name: str, dataset_dir: Path) -> DatasetStats:
    """Run full inspection on a single dataset."""
    print(f"\n{CYAN}{'-' * 60}{RESET}")
    print(f"{BOLD}Inspecting: {name}{RESET}")
    print(f"  Path: {dataset_dir}")

    if not dataset_dir.exists():
        print(f"{RED}  FAIL Directory not found! Download this dataset first.{RESET}")
        return DatasetStats(
            name=name,
            class_names=[],
            class_counts={},
            image_counts={},
            issues=[f"Dataset directory not found: {dataset_dir}"],
        )

    data = load_data_yaml(dataset_dir)
    class_names = parse_class_names(data)
    image_counts = count_images(dataset_dir)
    class_counts, issues = inspect_labels(dataset_dir, class_names)

    print(f"  Classes ({len(class_names)}): {class_names}")
    print(f"  Images  -> train: {image_counts.get('train',0)}, "
          f"valid: {image_counts.get('valid',0)}, "
          f"test: {image_counts.get('test',0)}")

    return DatasetStats(
        name=name,
        class_names=class_names,
        class_counts=class_counts,
        image_counts=image_counts,
        issues=issues,
    )


# -- Report generation ----------------------------------------------------

def _pad(s: str, width: int) -> str:
    return str(s).ljust(width)


def print_class_comparison(stats_list: list[DatasetStats]) -> None:
    """Print a side-by-side class count table for all datasets."""
    all_classes = sorted(
        set(cls for s in stats_list for cls in s.class_names)
    )

    col_w = 22
    print(f"\n{BOLD}{'-' * 70}{RESET}")
    print(f"{BOLD}CLASS COMPARISON TABLE{RESET}")
    print(f"{'-' * 70}{RESET}")

    # Header
    header = _pad("Class Name", col_w)
    for s in stats_list:
        header += _pad(s.name[:col_w], col_w)
    print(BOLD + header + RESET)
    print("-" * 70)

    # Rows
    for cls in all_classes:
        row = _pad(cls, col_w)
        for s in stats_list:
            count = s.class_counts.get(cls, 0)
            color = GREEN if count > 0 else RED
            row += color + _pad(count, col_w) + RESET
        print(row)

    print("-" * 70)

    # Totals
    total_row = BOLD + _pad("TOTAL", col_w)
    for s in stats_list:
        total = sum(s.class_counts.values())
        total_row += _pad(total, col_w)
    print(total_row + RESET)


def print_overlap_analysis(stats_list: list[DatasetStats]) -> None:
    """Identify which classes appear in all vs. some datasets."""
    all_classes = set(cls for s in stats_list for cls in s.class_names)
    shared = set(stats_list[0].class_names)
    for s in stats_list[1:]:
        shared &= set(s.class_names)
    only_in = {s.name: set(s.class_names) - shared for s in stats_list}

    print(f"\n{BOLD}OVERLAP ANALYSIS{RESET}")
    print(f"  {GREEN}Shared in ALL datasets:{RESET} {sorted(shared)}")
    for name, unique in only_in.items():
        if unique:
            print(f"  {YELLOW}Only in {name}:{RESET} {sorted(unique)}")


def print_issues(stats_list: list[DatasetStats]) -> None:
    """Print all collected issues."""
    total_issues = sum(len(s.issues) for s in stats_list)
    print(f"\n{BOLD}LABEL INTEGRITY ISSUES ({total_issues} total){RESET}")
    if total_issues == 0:
        print(f"  {GREEN}OK No issues found!{RESET}")
        return

    for s in stats_list:
        if s.issues:
            print(f"\n  {YELLOW}{s.name}:{RESET}")
            for issue in s.issues[:20]:  # Cap display at 20
                print(f"    {RED}FAIL{RESET} {issue}")
            if len(s.issues) > 20:
                print(f"    ... and {len(s.issues) - 20} more.")


def print_recommendations(stats_list: list[DatasetStats]) -> None:
    """Print merge recommendations based on inspection results."""
    print(f"\n{BOLD}RECOMMENDATIONS{RESET}")
    print("-" * 70)

    canonical = [
        "lying", "standing", "walking", "sitting",
        "feeding", "drinking", "social_interaction", "aggression",
    ]
    print(f"  Target canonical class list ({len(canonical)} classes):")
    for i, cls in enumerate(canonical):
        print(f"    {i}: {cls}")

    print(f"\n  {CYAN}Next steps:{RESET}")
    print("  1. Review config/class_map.yaml — adjust mappings if needed")
    print("  2. Run: python scripts/merge_datasets.py")
    print("  3. Run: python scripts/validate_labels.py (on merged data)")


# -- Main -----------------------------------------------------------------

def main() -> None:
    print(f"\n{BOLD}{'=' * 70}")
    print("  SWINE HEALTH MONITOR — Dataset Inspector (Phase 2)")
    print(f"{'=' * 70}{RESET}")

    all_stats: list[DatasetStats] = []
    for name, path in DATASET_DIRS.items():
        stats = inspect_dataset(name, path)
        all_stats.append(stats)

    print_class_comparison(all_stats)
    print_overlap_analysis(all_stats)
    print_issues(all_stats)
    print_recommendations(all_stats)

    print(f"\n{BOLD}{'=' * 70}{RESET}")
    print("Inspection complete. Review the output above before proceeding.")
    print(f"{BOLD}{'=' * 70}{RESET}\n")


if __name__ == "__main__":
    main()
