# Pig Tracking System — System Summary

**Version:** 2.0 (swine_behavior_v2) · **Status:** ✅ Production Ready · **Updated:** 2026-09-20

---

## Project Objective

The **Pig Tracking System** is an edge-AI IoT platform that detects early signs of illness in swine populations using computer vision and thermal imaging. It operates 100% autonomously on a Raspberry Pi 4B — no internet, no cloud, no wearable sensors.

The system targets **African Swine Fever (ASF)** and other illnesses by detecting two primary symptoms:
1. **Lethargy / Inactivity** — pigs stationary for unnatural durations
2. **Fever** — elevated surface temperature above the ambient baseline

---

## What the System Delivers

| Component | What it does |
|-----------|-------------|
| **AI Model (YOLOv8n → ONNX)** | Detects 8 pig behaviors (lying, standing, walking, sitting, feeding, drinking, social_interaction, aggression) — mAP50 **0.8272** |
| **SORT Tracker** | Assigns persistent IDs to individual pigs across frames |
| **MLX90640 Thermal Camera** | 32×24 IR grid maps pig temperatures to bounding boxes |
| **DHT22 Ambient Sensor** | Measures barn temperature + humidity → computes THI |
| **Hybrid Risk Engine** | Dual-channel health alerting with THI-adaptive thresholds |
| **GSM900A SMS Module** | Sends offline SMS alerts directly to farmer's phone |
| **Flask Web Dashboard** | Browser-accessible live feed, thermal overlay, alert log, settings |
| **Flutter Mobile App** | Android app ("Pig Tracking") connects to Pi via WebSocket for real-time feed |
| **SQLite Database** | All data stored locally; zero data loss across reboots |
| **WiFi Access Point** | Pi broadcasts its own hotspot — no router required in the field |

---

## Hardware Stack

| Component | Specification |
|-----------|--------------|
| Edge Computer | Raspberry Pi 4B (4GB RAM) |
| OS | Raspberry Pi OS Bookworm 64-bit |
| Vision Camera | USB UVC-compatible webcam |
| Thermal Sensor | **MLX90640** (32×24 IR grid, I2C `0x33`) |
| Ambient Sensor | DHT22 (GPIO4) |
| SMS Module | GSM900A (UART `/dev/serial0`) |
| Training PC | Windows 11 + NVIDIA RTX 4050 |

---

## Software Architecture

### 1. Vision & Tracking
- `src/inference/detector.py` — YOLOv8n ONNX inference (ONNX Runtime, no PyTorch on Pi)
- `src/tracking/` — SORT tracker assigns `track_id` per pig frame-to-frame

### 2. Sensor Fusion
- `src/thermal/thermal_reader.py` — MLX90640 32×24 grid reader
- `src/thermal/thermal_mapper.py` — Maps thermal zones to YOLO bounding boxes
- `src/sensor_hub.py` — Fuses camera + thermal + DHT22 streams

### 3. Hybrid Risk Engine (`src/health/risk_engine.py`)
| Channel | Trigger |
|---------|---------|
| **Channel 1 (Individual)** | Single pig stationary ≥ 15 min AND zone temp > ambient + 2.0°C |
| **Channel 2 (Population)** | ≥ 60% of detected pigs stationary simultaneously |
| **THI Adaptive** | If barn THI > 78 (heat stress), Channel 1 threshold extends to 30 min |

### 4. Mobile App (NEW in v2)
- Flutter Android app: **"Pig Tracking"**
- Connects to Pi via WebSocket (port 8765)
- Shows live annotated feed, thermal heatmap, and pig health status
- Download: `https://github.com/byrondumaya-cmyk/Pig-Tracking/releases/latest/download/app-release.apk`

### 5. Dashboard & Database
- `src/dashboard/` — Flask + Jinja2 web interface on port 5000
- `src/api/websocket_server.py` — WebSocket bridge for mobile app
- `data/swine_health.db` — SQLite database (detections, alerts, ambient, SMS logs)

---

## AI Model Details

| Property | Value |
|----------|-------|
| Architecture | YOLOv8n |
| Training run | `swine_behavior_v2` |
| Dataset | 8,515 images (2 merged Roboflow datasets) |
| Classes | 8 pig behaviors |
| mAP50 | **0.8272** |
| Deployed format | ONNX (12 MB) + TFLite INT8 (3.2 MB for mobile) |
| Inference runtime (Pi) | ONNX Runtime (CPU) |
| Inference runtime (mobile) | TFLite via Flutter |

---

## Access Points

| Interface | Address |
|-----------|---------|
| Web Dashboard (AP Mode) | `http://192.168.4.1:5000` |
| Web Dashboard (LAN Mode) | `http://[pi-local-ip]:5000` |
| WebSocket (mobile app) | `ws://[pi-ip]:8765` |
| AP WiFi SSID | `PigDashboard` |
| AP WiFi Password | `pigdashboard123` |

---

## Known Limitations (Post-Field-Trial)

1. **Alert storage** — Alert records and snapshots currently retained indefinitely. Add automated cleanup if SD card space is a concern.
2. **Model confusion** — `social_interaction` vs `aggression` classes are occasionally confused. System mitigates this by alerting primarily off stationary states.
3. **AP ↔ LAN switching** — Relies on `hostapd`/`dnsmasq` OS-level config; requires field testing on real hardware.
4. **TFLite calibration** — INT8 quantization uses `coco8.yaml` for calibration (farm-specific data would improve precision).
