"""
scripts/benchmark_onnx.py
Phase 6 — Benchmarking

PURPOSE:
    Measures and compares the inference speed of the original PyTorch model
    and the exported ONNX model to verify performance gains for CPU deployment.

USAGE:
    python scripts/benchmark_onnx.py
"""

from __future__ import annotations

import sys
import time
import cv2
import numpy as np
from pathlib import Path
from ultralytics import YOLO

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

def generate_dummy_image(size=(640, 640, 3)):
    """Generate a random noise image simulating camera input."""
    return np.random.randint(0, 255, size, dtype=np.uint8)

def benchmark_model(model_path: Path, model_type: str, num_warmup=10, num_runs=100):
    print(f"\nLoading {model_type} model from {model_path}...")
    model = YOLO(str(model_path), task="detect")
    
    dummy_img = generate_dummy_image()
    
    print(f"Running {num_warmup} warmup iterations...")
    for _ in range(num_warmup):
        model.predict(dummy_img, verbose=False, device="cpu")
        
    print(f"Benchmarking {model_type} over {num_runs} iterations (CPU only)...")
    start_time = time.perf_counter()
    
    for _ in range(num_runs):
        model.predict(dummy_img, verbose=False, device="cpu")
        
    end_time = time.perf_counter()
    
    total_time = end_time - start_time
    avg_time_ms = (total_time / num_runs) * 1000
    fps = 1000 / avg_time_ms if avg_time_ms > 0 else 0
    
    print(f"Results for {model_type}:")
    print(f"  Average Inference Time: {avg_time_ms:.2f} ms/frame")
    print(f"  Estimated FPS: {fps:.2f} FPS")
    
    return avg_time_ms

def main() -> None:
    print("\n============================================================")
    print(" SWINE HEALTH MONITOR — Phase 6: ONNX Benchmark")
    print("============================================================\n")

    pt_model = ROOT / "models" / "best.pt"
    onnx_model = ROOT / "models" / "best.onnx"
    
    if not pt_model.exists() or not onnx_model.exists():
        print(f"Error: Models not found in {ROOT}/models/")
        print("Please run export_model.py first.")
        sys.exit(1)
        
    print("NOTE: This benchmark forces CPU execution to simulate the Raspberry Pi environment.")
    print("Actual performance on the Raspberry Pi 4B will be slower than this PC CPU.\n")
        
    pt_time = benchmark_model(pt_model, "PyTorch")
    onnx_time = benchmark_model(onnx_model, "ONNX")
    
    print("\n============================================================")
    print(" BENCHMARK SUMMARY")
    print("============================================================")
    print(f"PyTorch Time: {pt_time:.2f} ms")
    print(f"ONNX Time:    {onnx_time:.2f} ms")
    
    if onnx_time < pt_time:
        speedup = (pt_time / onnx_time) - 1
        print(f"\n✅ ONNX is {speedup:.1%} faster than PyTorch on CPU.")
    else:
        print("\n⚠️ ONNX did not show speedup on this specific PC CPU.")
        print("   However, ONNX Runtime is still strictly required on the Raspberry Pi")
        print("   to avoid the heavy PyTorch dependency.")

if __name__ == "__main__":
    main()
