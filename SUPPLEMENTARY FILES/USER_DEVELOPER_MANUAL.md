# Pig Tracking System - User & Developer Manual

## Part 1: User Manual (For Farmers & Operators)

### 1. Connecting to the System
The Pig Tracking System acts as its own Wi-Fi router in the barn.
1. Stand near the Raspberry Pi in the barn.
2. Open your smartphone or laptop Wi-Fi settings.
3. Connect to the network named **SwineMonitor** (Password: `SwineAdmin`).
4. Open a web browser and navigate to `http://10.0.0.1:5000`.

### 2. Dashboard Overview
- **Live Stream:** Watch the live camera feed with real-time bounding boxes showing pig behavior and temperatures.
- **Alert History:** Review past alerts. Each alert includes the date, time, reason (e.g., *Individual Anomaly* or *Population Lethargy*), and a snapshot image captured exactly when the alert was triggered.
- **System Info:** Check the current barn temperature, humidity, THI, and camera connection status.

### 3. Understanding Alerts
The system sends SMS texts directly to your registered phone number.
- **Individual Alert:** Triggered if a specific pig lies down or sits continuously for more than 15 minutes AND has a high skin temperature (>2.0°C above barn temperature).
- **Population Alert:** Triggered if more than 60% of the pigs in the pen are lying down simultaneously, which can indicate disease spread or poor ventilation.
- *Note on Heat Stress:* On very hot days (THI > 78), pigs naturally lie down more. The system automatically waits 30 minutes before alerting to prevent false alarms.

### 4. Alert Cooldown
When an alert fires, the system enters a **5-minute cooldown** period. During this time, it will not send repetitive text messages for the same pen, allowing you time to inspect the animals without SMS spam.

### 5. Managing SMS Recipients
1. Connect to the dashboard.
2. Navigate to the **Settings** page.
3. Enter the developer password (provided by your technician).
4. Under the SMS section, you can add or remove phone numbers that will receive alerts. Include the country code (e.g., `+1234567890`).

---

## Part 2: Developer Manual (For Maintainers)

### 1. System Requirements & Setup
- **Hardware:** Raspberry Pi 4 (4GB+ RAM recommended), Pi Camera, AMG8833 I2C, DHT22 GPIO, SIM800L UART (`/dev/serial0`).
- **OS:** Raspberry Pi OS (Bullseye/Bookworm).
- **Environment:**
    ```bash
    python3 -m venv venv
    source venv/bin/activate
    pip install -r requirements-pi.txt
    ```

### 2. Developer Mode & Security
Sensitive endpoints (Settings, GSM diagnostics) are protected by `@dev_required` in `src/dashboard/auth.py`. 
- The password is read from `config/config.yaml` (`developer_password`).
- **Security Constraint:** The system will reject the default passwords `"admin"` or `"CHANGE_ME"`. You MUST change this in `config.yaml` before deployment to access the settings UI.

### 3. GSM Diagnostics
To verify cellular connectivity without waiting for a pig to get sick:
1. Log into the Dashboard Settings using Developer Mode.
2. Click **Run GSM Diagnostic Test**.
3. The system will issue raw AT commands to the SIM800L module. It verifies that the module responds and that the SMS payload is accepted by the network (`+CMGS:` response).
4. **Note:** This diagnostic test bypasses the `SwineRepository` and Alert Risk Engine. It will not corrupt the database with fake alert events.

### 4. Storage Architecture
- **Database:** SQLite3 (`data/swine_health.db`).
- **Pruning:** Transient data (`detections`, `ambient_readings`) is automatically pruned by the DB initialization routine (`delete_detections_older_than(7)`).
- **Snapshot Limitation:** `pen_alerts` and their associated `.jpg` files saved in `data/snapshots/` are **kept indefinitely** by design to preserve historical health data.
- **Data Integrity:** `src/main.py` explicitly verifies `cv2.imwrite` returns `True`. If the SD card is full, it will log a warning and save a clean `None` to the database rather than a broken file path. Ensure routine manual backup/clearance of the SD card.

### 5. AI Model Updates
- Place the best exported `.pt` (or `.onnx` for Pi optimization) in the `models/` directory.
- Update `config.yaml` > `vision.model_path` to point to the new weights.
- The system heavily relies on `lying` and `sitting` classes for the Risk Engine. While `social_interaction` classifications may have low mAP, do not over-tune if it degrades the stationary classes.
