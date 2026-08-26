# Pig Tracking System - Comprehensive System Summary

## Project Objective
The Pig Tracking System is an edge-AI IoT platform designed to detect early signs of illness in swine populations using computer vision and thermal imaging. It operates autonomously on a local edge device (Raspberry Pi) without requiring a continuous internet connection or wearable sensors on the animals.

The system specifically targets **African Swine Fever (ASF)** and other severe illnesses by identifying two primary symptoms:
1. **Lethargy / Inactivity:** Pigs remaining stationary for unnatural durations.
2. **Fever:** Elevated surface temperatures compared to the ambient environment.

## Hardware Stack
- **Compute:** Raspberry Pi (Edge deployment)
- **Vision:** RGB Camera module (for YOLO object detection)
- **Thermal:** AMG8833 (8x8 IR Thermal array for fever detection)
- **Environmental:** DHT22 (Ambient Temperature & Humidity for THI calculation)
- **Communication:** GSM/SMS Module (SIM800L over Serial/UART)

## Software Architecture

### 1. Vision & Tracking (`src.inference`, `src.tracking`)
- **YOLOv8 Model:** Detects pigs and classifies behaviors (e.g., `lying`, `sitting`, `standing`, `walking`, `feeding`).
- **SORT Tracker:** Assigns temporary, session-based IDs (`track_id`) to individual pigs across consecutive video frames to measure how long a specific pig has been stationary.

### 2. Sensor Fusion (`src.thermal`, `src.hardware`)
- **Thermal Mapper:** Maps the low-resolution 8x8 thermal grid from the AMG8833 onto the high-resolution RGB bounding boxes to assign a specific temperature to each tracked pig.
- **DHT22 Reader:** Continuously polls ambient conditions to calculate the Temperature Humidity Index (THI).

### 3. Hybrid Risk Engine (`src.health.risk_engine`)
Evaluates the fused data streams to determine if the pen is at risk, using a dual-channel approach:
- **Channel 1 (Individual Anomaly):** Triggers if a single tracked pig is stationary (e.g., lying/sitting) for >15 minutes AND its thermal zone reads >2.0°C above ambient temperature.
- **Channel 2 (Population Lethargy):** Triggers if >= 60% of the entire detected population is stationary simultaneously.
- **Adaptive THI Threshold:** If the barn is experiencing severe heat stress (THI > 78), pigs naturally become lethargic. The engine automatically extends the stationary timeout to 30 minutes to prevent false alarms.

### 4. Alerting & Dashboard (`src.database`, `src.dashboard`)
- **SQLite Database:** Stores historical detections, ambient readings, configuration, SMS logs, and Alert events locally.
- **GSM Notifier:** Sends SMS text alerts directly to farmers via the cellular network when a risk is detected, avoiding the need for barn Wi-Fi.
- **Flask Web Dashboard:** Provides a local web interface (accessed via the Pi's local Wi-Fi AP) to view live streams, review historical alerts, see snapshot evidence, and configure system parameters.

## Current System Status & Verified Limitations
As of the Phase 2 Final Verification, the system is structurally sound for field trials and categorized as **PRODUCTION READY WITH LIMITATIONS**. 

**Known Limitations to address post-field-trial:**
1. **Storage Growth:** Detections are pruned automatically, but Alert records and snapshot `.jpg` files are currently retained indefinitely. The system will eventually consume all SD card space without manual clearance or future automated retention logic.
2. **Dataset Classification:** The YOLO model performs exceptionally well on stationary behaviors (`lying`, `sitting`) but struggles to distinguish dynamic `social_interaction` from `aggression`. The architecture mitigates this by alerting primarily off reliable stationary states.
3. **Hardware Transitions:** The automatic switching between local LAN and physical HostAPD (broadcasting its own Wi-Fi network) relies on OS-level Linux commands and `dnsmasq`/`hostapd` configurations that require rigorous field-testing on real Raspberry Pi silicon.
