"""
scripts/evaluate_model.py
Phase 5 — Model Evaluation

PURPOSE:
    Evaluates the trained YOLOv8 model specifically on the test dataset.
    Generates performance metrics, confusion matrix, and analyzes failure cases.

USAGE:
    python scripts/evaluate_model.py
"""

from __future__ import annotations

import sys
from pathlib import Path
from ultralytics import YOLO

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

def main() -> None:
    print("\n============================================================")
    print(" SWINE HEALTH MONITOR — Phase 5: Model Evaluation")
    print("============================================================\n")

    weights_path = ROOT / "runs" / "detect" / "swine_behavior_v1_cpu_resume" / "weights" / "best.pt"
    if not weights_path.exists():
        print(f"Error: Could not find weights at {weights_path}")
        sys.exit(1)

    print(f"Loading model: {weights_path}")
    model = YOLO(str(weights_path))

    data_yaml = ROOT / "data" / "data_runtime.yaml"
    if not data_yaml.exists():
        print(f"Error: {data_yaml} not found. Please ensure training data exists.")
        sys.exit(1)

    print("\nRunning evaluation on TEST set...")
    
    # Run validation on the test split
    metrics = model.val(
        data=str(data_yaml),
        split="test",
        project=str(ROOT / "runs" / "evaluate"),
        name="test_evaluation",
        exist_ok=True,
        plots=True, # Ensure confusion matrix, PR curves etc are generated
        verbose=True
    )
    
    print("\n============================================================")
    print(" EVALUATION RESULTS SUMMARY")
    print("============================================================")
    
    # Extract overall metrics
    map50 = metrics.box.map50
    map50_95 = metrics.box.map
    precision = metrics.box.p.mean()
    recall = metrics.box.r.mean()

    print(f"\nOverall Metrics:")
    print(f"  mAP50:      {map50:.4f}")
    print(f"  mAP50-95:   {map50_95:.4f}")
    print(f"  Precision:  {precision:.4f}")
    print(f"  Recall:     {recall:.4f}")

    print("\nPer-Class Analysis:")
    
    class_names = metrics.names
    ap50_per_class = metrics.box.ap50
    
    # Identify the worst performing class
    worst_class_idx = -1
    worst_ap50 = 1.0
    
    for i, class_name in class_names.items():
        if i < len(ap50_per_class):
            ap50 = ap50_per_class[i]
            print(f"  {class_name}: mAP50 = {ap50:.4f}")
            if ap50 < worst_ap50:
                worst_ap50 = ap50
                worst_class_idx = i

    if worst_class_idx != -1:
        worst_class_name = class_names[worst_class_idx]
        print(f"\n[FAILURE ANALYSIS]")
        print(f"The worst performing class is '{worst_class_name}' with mAP50 of {worst_ap50:.4f}.")
        print("Please check the confusion_matrix.png in runs/evaluate/test_evaluation/ to see where it is being misclassified.")

    print(f"\nCharts and evaluation data saved to: {ROOT / 'runs' / 'evaluate' / 'test_evaluation'}")
    print("Phase 5 evaluation script complete!")

if __name__ == "__main__":
    main()
