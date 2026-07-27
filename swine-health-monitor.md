# Offline AI Swine Health Monitoring System
## Project Master Plan · `swine-health-monitor.md`

> **Type:** BACKEND + EMBEDDED SYSTEMS + AI/ML
> **Platform:** Raspberry Pi 4B (deployment) · Windows PC (training)
> **Connectivity:** 100% Offline — No internet, no cloud, no external APIs
> **Created:** 2026-07-13

---

## Goal

Build a production-ready capstone system that uses YOLOv8n to detect pig behavioral abnormalities and elevated body temperature in real-time — running entirely offline on a Raspberry Pi 4B — and presents health risk scores through a local Flask dashboard.

---

## Success Criteria

- [ ] YOLOv8n detects pig behaviors with mAP50 ≥ 0.70 on the test set
- [ ] System runs at ≥ 5 FPS on Raspberry Pi 4B (CPU only, no TPU)
- [ ] Thermal camera integrates and associates temperatures with individual Pig IDs
- [ ] Health Risk Engine outputs one of 5 risk levels with textual explanation
- [ ] Flask dashboard is accessible on local network via browser
- [ ] All data persists in SQLite — zero data loss across reboots
- [ ] System runs 24/7 without intervention

---

## Project Type

**BACKEND / EMBEDDED AI** — Python monorepo, no JavaScript frontend frameworks.
- Training: Windows 11 PC · **NVIDIA RTX 4050** (CUDA 12.x) — batch=32, fast epochs
- Deployment: Raspberry Pi 4B · **Raspberry Pi OS Bookworm 64-bit** (Python 3.11)
- Thermal: **Adafruit AMG8833** (8×8 grid, I2C, addr 0x69) — zone-based temp mapping
- UI: Flask (server-side rendered HTML via Jinja2) — accessible via:
  - **LAN mode**: Phone/laptop on same router → `http://[pi-ip]:5000`
  - **AP mode**: Pi creates its own WiFi hotspot → user connects to `PigMonitor_AP` → `http://192.168.4.1:5000`

---

## Tech Stack

| Layer | Technology | Why Chosen |
|-------|-----------|------------|
| AI Model | YOLOv8n (Ultralytics) | Smallest YOLO variant; fits RPi4 CPU |
| Inference Runtime (Pi) | ONNX Runtime | Optimized CPU inference; no PyTorch needed on Pi |
| Tracking | SORT (Simple Online Realtime Tracking) | Lightweight; no GPU needed |
| Thermal Camera | **Adafruit AMG8833** (8×8 I2C, addr 0x69) | Offline, direct I2C GPIO; ~10Hz refresh |
| Database | SQLite 3 | Zero-server; embedded; offline |
| Dashboard | Flask + Jinja2 + Chart.js | Lightweight; no Node.js needed |
| Networking | **hostapd + dnsmasq** (AP mode) OR LAN mode | Pi creates standalone hotspot for farm use |
| Language | Python 3.11 (Bookworm default) | Best AI/ML ecosystem |
| Training | Ultralytics YOLOv8 + Albumentations (CUDA) | RTX 4050 accelerated |

---

## Repository Structure

```
Pig_Tracking/
├── swine-health-monitor.md          ← This plan file
│
├── datasets/                        ← Raw downloaded datasets (NEVER commit to git)
│   ├── dataset_1_pig-behavior-wlvku/
│   │   ├── train/images/
│   │   ├── train/labels/
│   │   ├── valid/images/
│   │   ├── valid/labels/
│   │   └── data.yaml
│   └── dataset_2_pig-behavior-8xbgn/
│       ├── train/images/
│       ├── train/labels/
│       ├── valid/images/
│       ├── valid/labels/
│       └── data.yaml
│
├── data/                            ← Merged, cleaned, final dataset
│   ├── train/
│   │   ├── images/
│   │   └── labels/
│   ├── valid/
│   │   ├── images/
│   │   └── labels/
│   ├── test/
│   │   ├── images/
│   │   └── labels/
│   └── data.yaml                    ← Final unified class config
│
├── scripts/                         ← One-time utility scripts (PC only)
│   ├── inspect_datasets.py          ← Phase 2: Analyze class distributions
│   ├── merge_datasets.py            ← Phase 3: Merge + remap classes
│   ├── validate_labels.py           ← Phase 3: Check label integrity
│   ├── visualize_samples.py         ← Phase 3: Display annotated samples
│   ├── train.py                     ← Phase 4: Training entry point
│   ├── evaluate_model.py            ← Phase 5: Evaluation + confusion matrix
│   ├── export_model.py              ← Phase 6: Export to ONNX
│   └── benchmark_onnx.py            ← Phase 6: Benchmark inference speed
│
├── src/                             ← Production source (runs on Pi)
│   ├── inference/
│   │   ├── __init__.py
│   │   ├── detector.py              ← YOLOv8 ONNX inference wrapper
│   │   └── preprocessor.py          ← Frame preprocessing
│   ├── tracking/
│   │   ├── __init__.py
│   │   ├── sort_tracker.py          ← SORT algorithm
│   │   └── pig_tracker.py           ← Pig ID management + history
│   ├── thermal/
│   │   ├── __init__.py
│   │   ├── thermal_reader.py        ← Camera interface (MLX90640/FLIR)
│   │   └── thermal_mapper.py        ← Map temperatures to Pig IDs
│   ├── analytics/
│   │   ├── __init__.py
│   │   ├── behavior_analyzer.py     ← Activity index, durations
│   │   └── movement_tracker.py      ← Speed, distance, history
│   ├── health/
│   │   ├── __init__.py
│   │   └── risk_engine.py           ← Health Risk Score (explainable)
│   ├── database/
│   │   ├── __init__.py
│   │   ├── schema.py                ← SQLite table definitions
│   │   ├── repository.py            ← CRUD operations
│   │   └── migrations.py            ← Schema versioning
│   ├── dashboard/
│   │   ├── __init__.py
│   │   ├── app.py                   ← Flask application factory
│   │   ├── routes.py                ← API + page routes
│   │   ├── stream.py                ← MJPEG camera stream
│   │   └── templates/
│   │       ├── base.html
│   │       ├── index.html           ← Live dashboard
│   │       ├── pig_detail.html      ← Per-pig history
│   │       └── alerts.html          ← Alert center
│   └── main.py                      ← System entry point
│
├── models/                          ← Trained models (gitignored for size)
│   ├── best.pt                      ← Best PyTorch weights
│   └── best.onnx                    ← Exported ONNX model for Pi
│
├── runs/                            ← YOLOv8 training output (auto-generated)
│
├── data/swine_health.db             ← SQLite database (runtime, gitignored)
│
├── config/
│   ├── config.yaml                  ← System configuration
│   └── class_map.yaml               ← Final class name mapping
│
├── tests/                           ← Unit + integration tests
│   ├── test_detector.py
│   ├── test_tracker.py
│   ├── test_risk_engine.py
│   └── test_database.py
│
├── docs/                            ← Phase 16 documentation
│   ├── architecture.md
│   ├── installation_manual.md
│   ├── user_manual.md
│   └── developer_manual.md
│
├── requirements-train.txt           ← PC training dependencies
├── requirements-pi.txt              ← Raspberry Pi runtime dependencies
├── setup.py                         ← Package setup
├── .gitignore
└── README.md
```

---

## Phase Breakdown

### PHASE 1 — Project Setup & Environment
- [ ] T1.1: Create repository structure (all folders + `__init__.py` files)
  → Verify: `tree Pig_Tracking/` shows full structure
- [ ] T1.2: Create `requirements-train.txt` (ultralytics, torch, albumentations, opencv-python, matplotlib, seaborn, scipy, PyYAML, tqdm)
  → Verify: `pip install -r requirements-train.txt` completes without error
- [ ] T1.3: Create `requirements-pi.txt` (onnxruntime, opencv-python-headless, flask, numpy, smbus2, RPi.GPIO, filterpy)
  → Verify: List generated and reviewed
- [ ] T1.4: Create `config/config.yaml` with all runtime parameters
  → Verify: YAML parses correctly in Python
- [ ] T1.5: Create `.gitignore` (datasets/, models/, *.db, runs/, __pycache__/)
  → Verify: `git status` doesn't show ignored files

---

### PHASE 2 — Dataset Inspection & Class Standardization
- [ ] T2.1: Write `scripts/inspect_datasets.py` to count classes, images, labels in both datasets
  → Verify: Script outputs class distribution table for both datasets
- [ ] T2.2: Manually review class overlap between datasets and define **canonical 8-class list**:
  ```
  0: lying
  1: standing
  2: walking
  3: sitting
  4: feeding
  5: drinking
  6: social_interaction
  7: aggression
  ```
  → Verify: Class mapping documented in `config/class_map.yaml`
- [ ] T2.3: Write `scripts/validate_labels.py` to detect: empty labels, out-of-bound boxes, missing images
  → Verify: Script identifies all bad files; report generated
- [ ] T2.4: Update `data/data.yaml` with canonical class names
  → Verify: YAML loads correctly; nc=8

---

### PHASE 3 — Dataset Merging & Preparation
- [ ] T3.1: Write `scripts/merge_datasets.py` to:
  - Remap class IDs from both datasets to canonical list
  - Copy images + labels to `data/train`, `data/valid`, `data/test`
  - Apply 80/10/10 split
  → Verify: `data/train/` has images + labels, counts match
- [ ] T3.2: Run `scripts/validate_labels.py` on merged dataset
  → Verify: 0 corrupt labels; image-label pairs match
- [ ] T3.3: Write `scripts/visualize_samples.py` (draw bounding boxes on random samples)
  → Verify: 10 sample images displayed with correct class labels + colors

---

### PHASE 4 — YOLOv8n Training (PC/Laptop)
- [ ] T4.1: Write `scripts/train.py` with full parameter documentation
  - Model: `yolov8n.pt`
  - imgsz: 640
  - epochs: 100 (with early stopping patience=20)
  - batch: 16 (adjust based on VRAM; use 8 for CPU)
  - optimizer: Adam
  - lr0: 0.01, lrf: 0.01
  - augmentation: mosaic=1, flipud=0.5, fliplr=0.5, hsv_h=0.015
  → Verify: Training starts; loss decreasing after epoch 1
- [ ] T4.2: Monitor training — validate that mAP50 is increasing
  → Verify: `runs/detect/train/results.csv` shows improvement trend
- [ ] T4.3: Identify `best.pt` from `runs/detect/train/weights/`
  → Verify: `best.pt` exists and is larger than 0 bytes

---

### PHASE 5 — Model Evaluation
- [ ] T5.1: Write `scripts/evaluate_model.py` to run validation on test set
  → Verify: Outputs mAP50, mAP50-95, Precision, Recall per class
- [ ] T5.2: Generate and save: confusion matrix, P-R curve, F1 curve
  → Verify: PNG files saved to `runs/evaluate/`
- [ ] T5.3: Analyze failure cases — identify worst-performing classes
  → Verify: Written report of false positives/negatives

---

### PHASE 6 — ONNX Export & Benchmarking
- [ ] T6.1: Write `scripts/export_model.py` to export `best.pt` → `best.onnx`
  - opset=12 (RPi4 compatibility)
  - dynamic=False, simplify=True
  → Verify: `models/best.onnx` exists; file size ~6-8 MB
- [ ] T6.2: Write `scripts/benchmark_onnx.py` — measure inference time on PC
  → Verify: Reports ms/frame; compare to PyTorch baseline
- [ ] T6.3: Copy `models/best.onnx` to Raspberry Pi
  → Verify: File transfer complete; md5 checksum matches

---

### PHASE 7 — Raspberry Pi Deployment Setup
- [ ] T7.1: Update Pi and install system dependencies (Bookworm-specific):
  ```bash
  sudo apt update && sudo apt upgrade -y
  sudo apt install python3-pip python3-venv libopenblas-dev \
    python3-smbus i2c-tools libatlas-base-dev -y
  sudo raspi-config  # Enable I2C for AMG8833, Enable Serial for GSM900A
  ```
  → Verify: `python3 --version` shows 3.11.x; `i2cdetect -y 1` shows 0x69
- [ ] T7.2: Create Python venv on Pi, install `requirements-pi.txt`
  → Verify: `import onnxruntime; import adafruit_amg88xx; import adafruit_dht; import serial` all succeed
- [ ] T7.3: Write `src/inference/detector.py` — ONNX inference class with preprocessing
  → Verify: Single-image inference test; bounding boxes drawn correctly
- [ ] T7.4: Write camera test script — open USB camera, display FPS
  → Verify: Camera opens; ≥ 10 FPS raw capture confirmed
- [ ] T7.5: Configure network access (choose mode in `config.yaml`):
  - **LAN mode** (default): Dashboard accessible at `http://[pi-ip]:5000`
  - **AP mode**: Install `hostapd` + `dnsmasq`; Pi broadcasts `PigMonitor_AP`;
    user connects → accesses `http://192.168.4.1:5000`
  - Write `scripts/setup_ap_mode.sh` (automated AP setup script)
  → Verify (AP mode): Phone sees `PigMonitor_AP` SSID; browser opens dashboard

---

### PHASE 8 — Object Tracking (SORT)
- [ ] T8.1: Write `src/tracking/sort_tracker.py` (Kalman filter + Hungarian algorithm)
  → Verify: `filterpy` imported; tracker assigns consistent IDs frame-to-frame
- [ ] T8.2: Write `src/tracking/pig_tracker.py` — per-ID state machine:
  - Movement history (deque of positions)
  - Walking speed (pixels/frame → cm/s via calibration)
  - Activity duration timer
  - Idle duration timer
  → Verify: After 100 frames, each pig has a populated history dict

---

### PHASE 9 — Thermal & Ambient Sensing (AMG8833 + DHT22)

> **Sensor Reality Check:** The AMG8833 outputs an **8×8 grid**. We use a 4x4 zone mapper to align with YOLO centroids. The DHT22 acts as the ambient baseline, measuring THI (Temperature Humidity Index).

- [ ] T9.1: Wire AMG8833 to I2C and DHT22 to GPIO4
  → Verify: `i2cdetect -y 1` shows 0x69; `import adafruit_dht` works
- [ ] T9.2: Write `src/hardware/dht22_sensor.py`
  - Calculates THI for heat stress detection
- [ ] T9.3: Write `src/thermal/thermal_mapper.py`
  - Maps 8x8 grid into zones for YOLO bounding boxes
- [ ] T9.4: Define thresholds in `config.yaml`
  → Verify: `fever_delta_threshold_c` ensures fever alerts are relative to DHT22 baseline

---

### PHASE 10 — Behavior Analytics
- [ ] T10.1: Write `src/analytics/behavior_analyzer.py`
  - Track `stationary_duration_sec` for each SORT track_id
  - Compute `lethargy_ratio` for the whole frame (Channel 2 support)
  → Verify: Timer resets when bounding box centroid moves > 20px
- [ ] T10.2: Write `src/analytics/movement_tracker.py`
  - Walking frequency (direction changes per minute)
  - Velocity smoothing (EMA filter)
  → Verify: Speed output is non-negative; spikes filtered

---

### PHASE 11 — Health Risk Engine (Hybrid Logic + SMS)
- [ ] T11.1: Write `src/hardware/gsm_notifier.py`
  - Sends AT commands over UART to GSM900A module; enforces 5-min cooldown
- [ ] T11.2: Write `src/health/risk_engine.py` (Hybrid Channel Engine)
  - **Channel 1 (Individual)**: Any track stationary > 15m AND zone temp > ambient + 2.0C
  - **Channel 2 (Population)**: >= 60% of pigs are stationary
  - **THI Adaptive**: If THI > 78 (heat stress), stationary timer extends to 30m
  → Verify: GSM sends appropriate SMS text when either channel triggers

---

### PHASE 12 — Offline SQLite Database
- [ ] T12.1: Write `src/database/schema.py` — define tables:
  - `ambient_readings` (id, timestamp, temp_c, humidity_pct, thi)
  - `pen_alerts` (id, timestamp, alert_type, trigger_reason, sms_sent, ...)
  - `detections` (id, track_id, timestamp, behavior, confidence, bbox, zone_temp_c)
  → Verify: `schema.py` creates DB; `.tables` shows all 3 tables
- [ ] T12.2: Write `src/database/repository.py` — typed CRUD functions
  → Verify: Insert + query cycle completes without error
- [ ] T12.3: Test database under 8-hour continuous write load
  → Verify: DB size grows linearly; no lock errors

---

### PHASE 13 — Offline Flask Dashboard
- [ ] T13.1: Write `src/dashboard/app.py` and `routes.py`
  → Verify: `flask run` starts on port 5000; endpoints return JSON
- [ ] T13.2: Write MJPEG stream endpoint (`src/dashboard/stream.py`)
  → Verify: `http://pi-ip:5000/video_feed` shows live annotated video in browser
- [ ] T13.3: Build `templates/index.html` (Main Dashboard):
  - Side-by-Side UI: RGB YOLO Live Feed on Left, Thermal Canvas Heatmap on Right
  - Live SMS Alert Log (updates every 5s)
  - Ambient DHT22 Stat Cards
- [ ] T13.4: Build `templates/settings.html` (Live Settings Panel):
  - Editable form for GSM numbers, cooldown, alert timers, and thresholds
  - POST API to update `config.yaml` live without restarting Pi

---

### PHASE 14 — Performance Optimization (Raspberry Pi)
- [ ] T14.1: Profile CPU usage with `cProfile` — identify top 3 bottlenecks
  → Verify: Profile output shows bottlenecks; optimization targets identified
- [ ] T14.2: Implement frame-skipping (process every Nth frame for tracking)
  → Verify: FPS improves while tracking accuracy remains acceptable
- [ ] T14.3: Use threading — camera capture thread separated from inference thread
  → Verify: No frame stutter; CPU load distributed across cores
- [ ] T14.4: Optimize ONNX session options (inter/intra op threads = 4)
  → Verify: Inference time per frame ≤ 150ms on RPi4

---

### PHASE 15 — Testing
- [ ] T15.1: Write unit tests for: detector, tracker, risk_engine, repository
  → Verify: `pytest tests/` passes with ≥ 80% coverage
- [ ] T15.2: Integration test: full pipeline (camera → inference → tracker → DB → dashboard)
  → Verify: End-to-end run for 60 seconds; no crashes; data in DB
- [ ] T15.3: Stress test: 8-hour continuous run
  → Verify: Memory stable; DB grows linearly; FPS ≥ 5 throughout
- [ ] T15.4: Multi-pig test: ≥ 3 pigs in frame simultaneously
  → Verify: Each pig gets unique ID; IDs remain stable ≥ 30 seconds

---

### PHASE 16 — Documentation
- [ ] T16.1: `docs/architecture.md` — System diagram, data flow, Health Risk formula
- [ ] T16.2: `docs/installation_manual.md` — Step-by-step from zero to running
- [ ] T16.3: `docs/user_manual.md` — How to use the dashboard, interpret risk levels
- [ ] T16.4: `docs/developer_manual.md` — Module descriptions, how to extend
- [ ] T16.5: `README.md` — Project overview, quickstart, hardware list
  → Verify: Each doc reviewed; no placeholder sections remain

---

## Agent Assignment Matrix

| Phase | Primary Agent | Supporting Agent | Key Skill |
|-------|--------------|-----------------|-----------|
| 1–3 (Setup, Data) | `backend-specialist` | `project-planner` | `python-patterns` |
| 4–5 (Training, Eval) | `backend-specialist` | `performance-optimizer` | `python-patterns` |
| 6–7 (Export, Pi Setup) | `devops-engineer` | `backend-specialist` | `deployment-procedures` |
| 8–11 (Core Pipeline) | `backend-specialist` | `performance-optimizer` | `python-patterns` |
| 12 (Database) | `database-architect` | `backend-specialist` | `database-design` |
| 13 (Dashboard) | `backend-specialist` | `frontend-specialist` | `frontend-architecture` |
| 14 (Optimization) | `performance-optimizer` | `backend-specialist` | `performance-profiling` |
| 15 (Testing) | `test-engineer` | `backend-specialist` | `testing-patterns` |
| 16 (Docs) | `documentation-writer` | — | `documentation-templates` |

---

## Key Engineering Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Model Format on Pi | ONNX | No PyTorch overhead; ORT is CPU-optimized |
| Tracking Algorithm | SORT | Runs at 100+ FPS overhead; pure Python |
| Database | SQLite WAL mode | Zero-server; reliable; concurrent read+write |
| Dashboard Framework | Flask | Minimal RAM; no Node.js; offline |
| Thermal Sensor | AMG8833 (I2C 0x69) | Available hardware; zone-based mapping strategy |
| Ambient Sensor | DHT22 (GPIO4) | Calculates THI; prevents false alerts during heat waves |
| SMS Module | GSM900A (UART) | 100% offline alerts; reliable hardware AT commands |
| Health Logic | Pen-Level (Hybrid) | Avoids SORT ID loss issues; monitors herd vs individual |
| Networking | hostapd AP mode | Pi standalone hotspot; no router needed in field |
| Training GPU | RTX 4050 + CUDA | 10–20× faster than CPU training |
| Class Count | 8 classes | Removes duplicates/rare classes for better accuracy |
| Image Size | 640×640 | YOLOv8 default; trade-off between speed and accuracy |
| Training Batch | 32 (RTX 4050) | Fits comfortably in 6GB VRAM |

---

## Risk Register

| Risk | Likelihood | Mitigation |
|------|-----------|------------|
| Low mAP50 due to small dataset | Medium | Augmentation + transfer learning from `yolov8n.pt` |
| Pi CPU too slow for real-time | Medium | Frame-skipping + threading + ONNX optimization |
| AMG8833 zone misalignment | Medium | Camera placement calibration + config offset params |
| AMG8833 too low-res for multi-pig | High | Zone assignment by centroid; acceptable for group temp |  
| SQLite write lock under load | Low | WAL mode enabled; batch inserts |
| Pig ID switching (tracking loss) | High | SORT re-identification; backup by zone |
| AP mode conflicts with LAN mode | Low | Config flag selects mode; only one active at a time |

---

## Phase X: Verification Checklist (Final Gate)

- [ ] mAP50 ≥ 0.70 on test set
- [ ] ONNX inference ≤ 150ms/frame on RPi4 (`benchmark_onnx.py`)
- [ ] `pytest tests/` passes (≥ 80% coverage)
- [ ] 8-hour stress test passes (no crash, no memory leak)
- [ ] Dashboard loads at `http://[pi-ip]:5000` from another device on LAN
- [ ] All 5 risk levels trigger correctly with correct explanations
- [ ] AMG8833 wiring verified: `i2cdetect -y 1` shows 0x69
- [ ] AP mode tested: phone connects to `PigMonitor_AP`; dashboard loads
- [ ] Security scan: `python .agents/skills/vulnerability-scanner/scripts/security_scan.py .`
- [ ] All documentation complete — no placeholder sections

---

## Progress Tracker

| Phase | Status | Notes |
|-------|--------|-------|
| Phase 1: Setup | ✅ Complete | Structure, configs, requirements created |
| Phase 2: Dataset Inspection | ✅ Complete | Class names validated and mapped |
| Phase 3: Dataset Merging | ✅ Complete | 8,515 images pooled and standardized to 8 classes |
| Phase 4: Training | ✅ Complete | Finished successfully on CPU resume |
| Phase 5: Evaluation | ✅ Complete | Finished successfully (mAP50 0.827) |
| Phase 6: ONNX Export | ✅ Complete | Exported 11.7MB ONNX (57.2% CPU speedup) |
| Phase 7: Pi Setup | ⏳ Pending | Hardware provisioning required (OS flash, venv, pip install) |
| Phase 8: Tracking | ✅ Complete | `sort_tracker.py` + `pig_tracker.py` fully implemented |
| Phase 9: Thermal & Ambient | ✅ Complete | `thermal_reader.py`, `thermal_mapper.py`, `dht22_sensor.py` done |
| Phase 10: Analytics | ✅ Complete | `behavior_analyzer.py` with stationary timer + lethargy ratio |
| Phase 11: Risk Engine | ✅ Complete | Hybrid Channel 1 + 2, THI-adaptive, `gsm_notifier.py` |
| Phase 12: Database | ✅ Complete | `schema.py` + `repository.py` with full CRUD |
| Phase 13: Dashboard | ✅ Complete | `app.py`, `routes.py`, `stream.py`, templates fully implemented |
| Phase 14: Optimization | ⏳ Pending | Frame-skip, threading, ONNX thread tuning (on Pi hardware) |
| Phase 15: Testing | ⏳ Pending | Unit tests + integration tests (on Pi hardware) |
| Phase 16: Documentation | ⏳ Pending | |

---

*Plan file: `swine-health-monitor.md` · Project root: `c:\Users\Byron Dumaya\Downloads\Pig_Tracking\`*
