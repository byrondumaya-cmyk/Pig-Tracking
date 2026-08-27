# Pig Tracking System: Complete Project History, Architecture, & Next Steps

This document serves as the **ultimate, comprehensive source of truth** for the Pig Tracking System. It details the complete history of the project from the ground up, the full architectural design, the datasets and models utilized, every major and minor refactoring/bug-fix action taken, and a clear, actionable roadmap for future maintainers.

---

## 1. Project Origins and Objectives

### The Problem
Traditional methods of monitoring swine health, particularly for highly contagious and fatal diseases like African Swine Fever (ASF), rely on manual inspection or expensive, invasive wearable sensors (e.g., RFID ear tags with thermistors). These methods are labor-intensive, stressful for the animals, and difficult to scale.

### The Solution
The Pig Tracking System is an autonomous, non-invasive **Edge AI IoT platform**. It aims to detect the earliest clinical signs of illness—**Lethargy** and **Fever**—using exclusively ambient sensors (cameras and thermal arrays). 

### Core Capabilities
1. **Behavioral Tracking**: Uses computer vision to classify what a pig is doing (e.g., lying, sitting, walking) and tracks how long they remain in that state.
2. **Thermal Mapping**: Reads the surface temperature of the pigs without physical contact.
3. **Environmental Context**: Monitors the barn's Temperature Humidity Index (THI) to distinguish between sickness lethargy and natural heat stress.
4. **Offline Alerting**: Operates entirely offline on a local edge device (Raspberry Pi) and alerts farmers via cellular SMS (GSM module) rather than relying on barn Wi-Fi.

---

## 2. Full System Architecture

The system is designed with a decoupled, object-oriented architecture to ensure stability, testability, and graceful degradation (if a sensor fails, the rest of the system continues operating).

### A. Hardware Stack
*   **Compute Node**: Raspberry Pi 4 (4GB+ RAM) running Raspberry Pi OS (Linux).
*   **Vision Sensor**: Standard Pi Camera Module (or USB Webcam) for high-resolution RGB video capture.
*   **Thermal Sensor**: AMG8833 I2C Infrared Array Sensor (provides an 8x8 grid of temperature readings).
*   **Environmental Sensor**: DHT22 GPIO Sensor (provides ambient temperature and relative humidity).
*   **Communication Module**: SIM800L GSM Module connected via UART (`/dev/serial0`) for sending SMS alerts over 2G/3G networks.

### B. Software Stack
*   **Language**: Python 3.9+
*   **Computer Vision**: Ultralytics YOLOv8 (Detection & Classification), OpenCV (Image processing), SORT (Simple Online and Realtime Tracking).
*   **Database**: SQLite3 (Local, lightweight relational database).
*   **Web Framework**: Flask (Serves the local dashboard and MJPEG video stream).

### C. System Components (Ground Up)

#### 1. Inference Engine (`src.inference`)
Uses a custom-trained YOLOv8 model. For every video frame, it detects pigs and assigns a behavioral class (`lying`, `sitting`, `standing`, `walking`, `feeding`, `drinking`, `social_interaction`, `aggression`). It returns bounding boxes and confidence scores.

#### 2. Tracking Engine (`src.tracking.sort_tracker`)
Because YOLO only detects objects in a single frame, SORT is used to link detections across time. It assigns a temporary `track_id` to each pig. If Pig #1 is `lying` in frame 1, and `lying` in frame 1000, SORT allows the system to calculate that Pig #1 has been stationary for `X` minutes. *Note: These IDs are session-scoped and spatial; if a pig leaves the camera view and returns, it receives a new ID.*

#### 3. Thermal Mapper (`src.thermal.thermal_mapper`)
The AMG8833 only provides an 8x8 grid of temperatures, while the camera provides a high-res (e.g., 640x480) image. The mapper projects the 8x8 grid onto the camera's resolution. It then intersects the YOLO bounding boxes with the upscaled thermal map to calculate the average and maximum skin temperature of each specific tracked pig.

#### 4. Hybrid Risk Engine (`src.health.risk_engine`)
This is the brain of the system. It takes the tracked behaviors, the thermal data, and the ambient DHT22 data, and evaluates risk across two channels:
*   **Channel 1 (Individual Anomaly):** Triggers if a single `track_id` is classified as `stationary` (lying/sitting) for **> 15 minutes** AND its mapped thermal temperature is **> 2.0°C** above the ambient barn temperature (Fever).
*   **Channel 2 (Population Lethargy):** Triggers if **>= 60%** of the entire detected herd is stationary simultaneously for > 3 seconds, indicating a widespread environmental issue or highly contagious spread.
*   **THI Adaptation:** If the DHT22 reports severe heat stress (THI > 78), the engine automatically extends the 15-minute lethargy timer to 30 minutes, knowing pigs naturally rest more in the heat.

#### 5. Storage & Database (`src.database.repository`)
An SQLite database (`swine_health.db`) stores:
*   Transient detections (pruned after 7 days).
*   Ambient readings (pruned after 7 days).
*   Alert Events (Kept indefinitely).
*   System Configuration (Thresholds, SMS recipients).

#### 6. GSM Notifier (`src.hardware.gsm_notifier`)
Constructs and sends raw AT commands to the SIM800L module to dispatch SMS messages to the farmer when the Risk Engine triggers an alert.

#### 7. Dashboard (`src.dashboard`)
A Flask web application served locally on the Pi. It provides:
*   An MJPEG live stream with drawn bounding boxes, track IDs, and temperatures.
*   An Alert History view with snapshot images captured at the exact moment of the alert.
*   A Developer Settings page to manage SMS recipients and run hardware diagnostics.

---

## 3. Datasets and AI Model Training

### The Dataset
The model was trained on custom-annotated datasets consisting of deployment-like footage of swine populations. 
*   **Classes**: `lying`, `sitting`, `standing`, `walking`, `feeding`, `drinking`, `social_interaction`, `aggression`.
*   **Format**: YOLO format `.txt` annotations paired with `.jpg`/`.png` images.
*   **Data Splits**: Configured via `data/data_runtime.yaml` (Train, Valid, Test splits).

### Training and Performance
The YOLOv8 model was trained over 54+ epochs. 
*   **Overall mAP50**: `0.8272`
*   **Strengths**: The model is highly accurate at detecting stationary behaviors crucial to the risk engine. (`lying`: 0.97, `sitting`: 0.94).
*   **Weaknesses**: The model struggles with dynamic interactions (`social_interaction`: 0.57, `walking`: 0.62). 
*   **Architectural Mitigation**: Because ASF and severe illness are indicated by *lethargy*, the Hybrid Risk Engine relies almost entirely on the highly accurate `lying` and `sitting` classes. The model's weakness in dynamic interactions does not compromise the core alerting logic.

---

## 4. Comprehensive Action Log (What We Did)

Over the course of development, the system evolved from a monolithic script into a modular, testable architecture. Below is the detailed record of major and minor actions, refactors, and bug fixes applied to reach the current stable state.

### Phase 1: Foundation & Training (Pre-Refactor)
*   **Action**: Collected and labeled the dataset.
*   **Action**: Wrote `scripts/train.py` and executed the initial YOLOv8 training runs.
*   **Action**: Created the baseline hardware interface scripts (`dht22_sensor.py`, `amg8833_reader.py`, `gsm_notifier.py`).
*   **Action**: Proved the concept of thermal mapping (8x8 to high-res projection).

### Phase 2: Architectural Refactoring
*   **Major Refactor**: Broke the monolithic pipeline into discrete modules (`src.inference`, `src.tracking`, `src.health`, etc.) using Dependency Injection to allow for unit testing.
*   **Major Feature**: Implemented the `HerdRiskEngine` to introduce the Dual-Channel (Individual vs. Population) alerting logic, moving away from simple single-frame triggers.
*   **Major Feature**: Implemented the `SwineRepository` (SQLite) to persist events offline across reboots.
*   **Minor Fix**: Added hardware simulation fallbacks. If the AMG8833 or DHT22 are disconnected, the system safely falls back to generating simulated data rather than crashing the camera loop.

### Phase 3: Final Verification & Closeout Passes (The Final Polish)
During the final review phases, the system was subjected to rigorous code inspection and regression testing, resulting in several critical fixes:

1.  **Security & Authentication (Major Fix)**:
    *   *Bug*: The system originally defaulted to the password `"admin"` if no password was set, allowing silent, unauthorized access to the Settings dashboard.
    *   *Fix*: Changed the fallback to `"CHANGE_ME"`. Updated `src/dashboard/auth.py` to intercept requests. If the password is `"admin"` or `"CHANGE_ME"`, the dashboard returns a strict `401 Unauthorized`.
    *   *Test*: Verified via `test_auth.py`.

2.  **Snapshot Storage Integrity (Major Fix)**:
    *   *Bug*: In `src/main.py`, the snapshot save function (`cv2.imwrite`) failed silently if the SD card was full. It returned `False`, but the system blindly wrote the broken image path to the database.
    *   *Fix*: Implemented a check on the `success` boolean returned by `imwrite()`. If the disk is full, it logs a clear warning and saves `None` to the database, preventing broken UI links.

3.  **GSM Indentation and Diagnostics (Minor Fix & Feature)**:
    *   *Bug*: Fixed a critical indentation error in `gsm_notifier.py` inside `_send_at()` that would have caused exceptions during AT command parsing.
    *   *Feature*: Implemented a Developer Diagnostic route (`/api/developer/gsm-test`). Wrote `test_gsm_diag.py` to prove that running diagnostics accurately tests the hardware serial port without accidentally polluting the database with fake `AlertEvent` records.

4.  **Tracking Isolation & Cooldown (Regression Proof)**:
    *   *Test*: Executed `test_tracking_isolation.py`. Proved that if Pig A lies down for 10 minutes and leaves, and Pig B enters the same spot, Pig B does *not* inherit Pig A's lethargy timer.
    *   *Test*: Executed `test_state_machine.py`. Proved the 5-minute Alert Cooldown correctly suppresses redundant SMS messages while continuing to log data.

5.  **Network AP Switching (Analysis)**:
    *   *Limitation Documented*: The scripts to switch the Pi between an Access Point (`hostapd`) and local LAN (`switch_to_lan.sh`) were analyzed. Because the development environment (Windows PC) lacked the Linux networking stack, this was marked as `BLOCKED/SIMULATED`. `sys_info.py` was verified to safely return `"unknown"` rather than crashing.

---

## 5. Next Steps and Roadmap

The system is currently categorized as **PRODUCTION READY WITH LIMITATIONS**. It is structurally sound and logically verified. To achieve unsupervised, long-term deployment in actual barns, the following roadmap must be executed:

### Step 1: Physical Hardware Validation (Immediate Priority)
The software has been verified via simulation and unit tests. It must now be tested on the target silicon.
*   **Task**: Deploy the codebase to a physical Raspberry Pi 4.
*   **Task**: Test the physical `hostapd` Wi-Fi switching scripts (`setup_ap.sh`, `switch_to_lan.sh`). Verify that a farmer can stand in a barn without internet, connect to the `SwineMonitor` network, and load the dashboard.
*   **Task**: Connect the physical SIM800L module with an active SIM card. Run the Developer GSM Diagnostic test to measure actual cellular network AT command latencies and fix any UART baud-rate mismatches.

### Step 2: Storage Management Policy (Mid-Term)
Because Alert Snapshots (`.jpg` files) and `pen_alerts` database rows are currently kept forever by design (to preserve historical evidence), the SD card will eventually fill up. The recent data integrity fix prevents crashes when this happens, but it must be managed.
*   **Task**: Decide on a business-logic retention policy for snapshots (e.g., "Delete snapshots older than 30 days" or "Delete oldest when disk is 90% full").
*   **Task**: Implement a scheduled background job or a "Clear Old Data" button in the Settings Dashboard to execute this policy.

### Step 3: UI End-to-End Testing (Mid-Term)
While the backend pipelines and risk engines are heavily unit-tested, the Flask web dashboard relies on manual code inspection.
*   **Task**: Implement a lightweight UI testing framework (e.g., Playwright or Selenium) to programmatically test the Settings page configuration flow, password rejection, and the MJPEG video stream rendering.

### Step 4: Dataset Augmentation for Social Behaviors (Long-Term)
If future features require alerting based on aggressive or socially irregular behavior (e.g., tail biting).
*   **Task**: Collect and label significantly more deployment-like footage of `social_interaction` and `aggression`. The current dataset is heavily biased towards resting pigs, leading to the low `0.57 mAP50` for interactions.

### Step 5: Persistent Identity / ReID (Future Expansion)
Currently, SORT assigns temporary IDs per session based on spatial bounding boxes. If a pig leaves the camera view and returns, it gets a new ID, resetting its 15-minute lethargy timer.
*   **Task**: Research and integrate a visual Re-Identification (ReID) model. This would extract visual embeddings of the pigs to track specific animals longitudinally over multiple days, allowing for much more advanced health analytics.
