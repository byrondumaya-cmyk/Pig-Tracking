# ============================================================
# README.md — Offline AI Swine Health Monitoring System
# ============================================================

# 🐷 Offline AI Swine Health Monitoring System

An edge-AI capstone project that detects **pig behavioral abnormalities** and **elevated body temperature** in real-time using a Raspberry Pi 4B, USB camera, and AMG8833 thermal sensor — entirely **offline**, no internet required.

---

## 🎯 What It Does

| Feature | Description |
|---------|-------------|
| **Pig Detection** | YOLOv8n detects and classifies 8 pig behaviors (lying, standing, walking, etc.) |
| **Multi-Pig Tracking** | SORT tracker assigns unique Pig IDs across frames |
| **Thermal Sensing** | AMG8833 maps body temperature to individual pigs via zone-based mapping |
| **Health Risk Score** | Explainable 5-level risk engine combining behavior + temperature + history |
| **Live Dashboard** | Flask web dashboard — view live feed, alerts, and pig history from your phone |
| **SQLite Database** | All data stored locally; survives reboots |
| **AP Mode** | Pi creates its own WiFi hotspot — no router needed in the field |

---

## 🔧 Hardware Requirements

| Component | Specification |
|-----------|--------------|
| Single-Board Computer | Raspberry Pi 4B (4GB RAM recommended) |
| OS | Raspberry Pi OS **Bookworm 64-bit** |
| USB Camera | Any UVC-compatible USB webcam |
| Thermal Sensor | **Adafruit AMG8833** (8×8 IR grid, I2C) |
| Storage | microSD Card ≥ 32GB (Class 10 / A1) |
| Training PC | Windows 11 + NVIDIA GPU (RTX 4050 used in development) |

---

## 🚀 Quickstart

### 1. Clone & Set Up (Training PC)

```powershell
git clone <your-repo-url> Pig_Tracking
cd Pig_Tracking

# Create virtual environment
python -m venv venv
venv\Scripts\activate

# Install training dependencies
pip install -r requirements-train.txt
```

### 2. Prepare Datasets (Phase 2–3)

```powershell
# Download datasets from Roboflow and place in datasets/ folder
# See docs/installation_manual.md for step-by-step instructions

python scripts/inspect_datasets.py    # Analyze class distributions
python scripts/merge_datasets.py      # Merge + remap to 8 canonical classes
python scripts/validate_labels.py     # Check label integrity
```

### 3. Train YOLOv8n (Phase 4)

```powershell
python scripts/train.py
# Model will be saved to: runs/detect/train/weights/best.pt
```

### 4. Export to ONNX (Phase 6)

```powershell
python scripts/export_model.py
# Output: models/best.onnx  (~6-8 MB)
```

### 5. Deploy to Raspberry Pi (Phase 7)

```bash
# On Raspberry Pi:
sudo apt update && sudo apt upgrade -y
sudo apt install python3-pip python3-venv libopenblas-dev \
  python3-smbus i2c-tools libatlas-base-dev -y

# Enable I2C for AMG8833
sudo raspi-config  # Interface Options → I2C → Enable

# Verify AMG8833 is wired correctly
i2cdetect -y 1   # Should show 0x69

# Create venv and install
python3 -m venv venv
source venv/bin/activate
pip install -r requirements-pi.txt

# Copy model
scp models/best.onnx pi@raspberrypi.local:~/Pig_Tracking/models/

# Run the system
python3 src/main.py
```

### 6. Access Dashboard

- **LAN mode**: Open browser → `http://[pi-ip-address]:5000`
- **AP mode**: Connect to WiFi `PigMonitor_AP` → Open `http://192.168.4.1:5000`

---

## 📁 Project Structure

```
Pig_Tracking/
├── config/           # Runtime configuration (config.yaml, class_map.yaml)
├── data/             # Merged dataset + SQLite database
├── datasets/         # Raw downloaded datasets (not in git)
├── docs/             # Documentation
├── models/           # Trained model files (not in git)
├── scripts/          # One-time PC utility scripts (training, eval, export)
├── src/              # Production source code (runs on Pi)
│   ├── inference/    # YOLOv8 ONNX detector
│   ├── tracking/     # SORT multi-object tracker
│   ├── thermal/      # AMG8833 thermal camera integration
│   ├── analytics/    # Behavior + movement analytics
│   ├── health/       # Health risk scoring engine
│   ├── database/     # SQLite persistence layer
│   └── dashboard/    # Flask web dashboard
├── tests/            # Unit + integration tests
├── requirements-train.txt   # PC training dependencies
└── requirements-pi.txt      # Raspberry Pi runtime dependencies
```

---

## 🐖 Behavior Classes

| ID | Class | Description |
|----|-------|-------------|
| 0 | `lying` | Pig resting flat on ground |
| 1 | `standing` | Pig stationary and upright |
| 2 | `walking` | Pig in motion |
| 3 | `sitting` | Pig in seated position |
| 4 | `feeding` | Pig at feeding station |
| 5 | `drinking` | Pig at water source |
| 6 | `social_interaction` | Pig interacting with others |
| 7 | `aggression` | Pig showing aggressive behavior |

---

## ⚕️ Health Risk Levels

| Level | Score | Meaning |
|-------|-------|---------|
| 🟢 NORMAL | 0–20 | No concerns |
| 🟡 LOW RISK | 21–40 | Monitor this pig |
| 🟠 MODERATE RISK | 41–60 | Increased monitoring recommended |
| 🔴 HIGH RISK | 61–80 | Inspection recommended |
| 🚨 CRITICAL | 81–100 | **Immediate inspection required** |

---

## 📚 Documentation

- [Installation Manual](docs/installation_manual.md)
- [User Manual](docs/user_manual.md)
- [Developer Manual](docs/developer_manual.md)
- [System Architecture](docs/architecture.md)

---

## 📋 Development Status

See [`swine-health-monitor.md`](swine-health-monitor.md) for the full phase-by-phase plan and progress tracker.

---

*Built for capstone/thesis research. Does NOT diagnose diseases — detects behavioral + thermal anomalies for farmer inspection.*
