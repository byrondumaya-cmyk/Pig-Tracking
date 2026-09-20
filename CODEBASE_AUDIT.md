# Codebase Audit

## 1. Executive Summary

**Project Summary:**
The codebase implements a comprehensive hardware-software tracking and health monitoring system for pigs. It runs on a Raspberry Pi using an ONNX-optimized YOLO model (via `onnxruntime`) to track pigs, measure ambient and zone temperatures (via MLX90640 and DHT22), analyze behavior, and log data. A Flask web dashboard and a Flutter mobile app consume this data.

**Overall Architecture:**
- **Hardware Integration Layer:** Interfaces with I2C (Thermal), GPIO (DHT22), and Serial (GSM900A) hardware.
- **Inference & Tracking:** YOLOv8n object detection (with letterboxing) fed into a SORT tracker for continuous object tracking.
- **Health Engine:** Dual-channel (Individual and Population) rule-based logic to detect fever or lethargy.
- **Data Persistence:** SQLite database acting in WAL mode for concurrent access, wrapped in a typed repository pattern.
- **APIs & Web:** Flask provides a REST API, settings interface, MJPEG streaming, and basic auth. An asyncio WebSocket server broadcasts high-speed frames to mobile clients.

**General Areas of Concern:**
Overall, the Python codebase is very structured and adheres to good architecture principles. The main risks observed center around **thread blocking**, **concurrency issues**, and **weak input validation**. The most significant risks are found in the integration of I2C/Serial hardware interfaces which may pause the main video processing loop, and the use of CPU-bound operations inside async event loops.

---

## 2. Codebase Structure

- `src/main.py`: Entry point orchestrating threads and initializing subsystems.
- `src/config_loader.py`: Typified configuration loader via PyYAML.
- `src/hardware/`: Modules for GSM, DHT22, and Thermal cameras.
- `src/inference/` & `src/tracking/`: ONNX runtime logic and SORT implementation.
- `src/dashboard/`: Flask backend and MJPEG streams.
- `src/api/websocket_server.py`: Asyncio websocket broadcaster for mobile devices.
- `src/health/`: Risk engine and behavior analysis rule sets.
- `src/database/`: SQLite wrapper.
- `mobile_app/`: Flutter mobile application.

---

## 3. Findings

### [ID-1] I2C Sensor Read Blocking Camera Relay Thread
**Severity:** High
**Confidence:** Confirmed
**Category:** Performance / Reliability
**File:** `src/main.py`
**Location:** `_start_camera_relay()` at line 238

**Problem:**
The camera relay thread attempts to pull thermal frames synchronously inside the camera loop via `self.thermal_reader.read()`.

**Why It Happens:**
MLX90640 reads over I2C are notoriously slow. Depending on the `refresh_hz` and bus speed, a single `.read()` can block for 30ms-125ms. Since this happens sequentially after pulling the camera frame, it will forcibly throttle the WebSocket streaming frame rate, causing a choppy video feed on the mobile app.

**Potential Impact:**
The video feed could drop from 30 FPS down to < 10 FPS because the thread is perpetually stalled waiting for I2C data.

**Evidence:**
```python
if self.cfg.thermal.enabled and self.thermal_reader:
    try:
        raw_thermal = self.thermal_reader.read() # Blocking IO operation
```

**Recommended Fix:**
Offload the `thermal_reader.read()` into its own background daemon thread that writes to a thread-safe shared state (like `ThermalBuffer`), and have the `_relay` thread just read the latest cached thermal state instantly without blocking.

**Structure Impact:** Can be fixed purely within `src/main.py` or `src/thermal_reader.py` without structural changes.
**Regression Risk:** Low

---

### [ID-2] Blocking Operations Inside Asyncio Event Loop
**Severity:** High
**Confidence:** Confirmed
**Category:** Performance
**File:** `src/api/websocket_server.py`
**Location:** `_broadcast_loop()` at line 68

**Problem:**
CPU-bound operations are executed directly inside the main `asyncio` event loop thread.

**Why It Happens:**
`cv2.imencode('.jpg', self._latest_frame, encode_param)` is a blocking, CPU-intensive C-extension call. When placed directly in an `async def` function running on the `asyncio` event loop, it halts all other async operations (like accepting new websocket connections or sending packets) until compression completes.

**Potential Impact:**
At 30 FPS and high resolutions on a Raspberry Pi, JPEG compression could monopolize the async thread, leading to delayed websocket pings, dropped connections, or severe latency.

**Evidence:**
```python
# Encode frame to JPEG
encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), 60]
success, buffer = cv2.imencode('.jpg', self._latest_frame, encode_param)
```

**Recommended Fix:**
Wrap the `cv2.imencode` call in `await self.loop.run_in_executor(None, cv2.imencode, ...)` to offload the heavy computation to a worker thread, freeing the async loop to handle networking.

**Structure Impact:** Very minimal inline fix.
**Regression Risk:** Low

---

### [ID-3] GSM Module SMS Dispatch Blocks Inference
**Severity:** Medium
**Confidence:** Likely
**Category:** Performance / Blocking
**File:** `src/hardware/gsm_notifier.py`
**Location:** `_send_sms()` at line 190

**Problem:**
Sending an SMS halts the calling thread for up to 25 seconds.

**Why It Happens:**
The `_send_sms` method uses strict timeouts (`timeout=10.0` and `timeout=15.0`) to wait for AT command responses from the serial modem. If this is called synchronously when a risk is detected inside the main inference loop, the entire camera pipeline and AI detection will freeze until the SMS succeeds or times out.

**Potential Impact:**
Video stream freezes entirely, tracking IDs are lost, and pigs are missed for up to 25 seconds when an alert triggers.

**Evidence:**
```python
if not self._send_at(cmd, expected=">", timeout=10.0):
...
return self._send_at("", expected="+CMGS:", timeout=15.0)
```

**Recommended Fix:**
Dispatch the `send_alert()` method using a `threading.Thread` or a background task queue so the main loop can immediately resume inference.

**Structure Impact:** Minimal. Can be handled by the caller.
**Regression Risk:** Low

---

### [ID-4] Unhandled ValueError Exceptions on Settings Save
**Severity:** Medium
**Confidence:** Confirmed
**Category:** Reliability / Input Validation
**File:** `src/dashboard/routes.py`
**Location:** `settings()` at line 91

**Problem:**
The settings API directly casts user-provided JSON strings to `float()` and `int()` without type validation or specific exception handling.

**Why It Happens:**
If a user submits non-numeric input (e.g., `{"fever_delta_threshold_c": "abc"}`), Python throws a `ValueError`. The broad `except Exception as e:` block at the end of the method catches it, which is safe, but it returns a raw stringified Python exception to the frontend, which is poor API design.

**Potential Impact:**
Poor user experience on errors. It could also lead to partial updates if an exception is thrown halfway through mutating the `config` dictionary, resulting in a corrupted save to `config.yaml`.

**Evidence:**
```python
config['health'][key] = float(h[key])  # Will raise ValueError on bad data
```

**Recommended Fix:**
Validate and parse all input parameters into variables first. Only update the `config` dictionary if all parameters are valid.

**Structure Impact:** Local to the route.
**Regression Risk:** Low

---

### [ID-5] `timedatectl` Subprocess Input Validation
**Severity:** Low
**Confidence:** Confirmed
**Category:** Security / Reliability
**File:** `src/dashboard/routes.py`
**Location:** `sync_system_time()` at line 665

**Problem:**
The `new_time_str` parameter from the JSON request is passed directly into a `subprocess.run` command list.

**Why It Happens:**
Although `shell=False` protects against traditional shell injection (like `&& rm -rf /`), passing unvalidated user input directly into a system binary argument can sometimes cause unexpected behavior if the binary supports unforeseen flags or formats.

**Potential Impact:**
Low security risk, but a malformed date string will cause the binary to crash and return an ugly error message.

**Evidence:**
```python
result = subprocess.run(
    ["timedatectl", "set-time", new_time_str],
    capture_output=True, timeout=10
)
```

**Recommended Fix:**
Parse `new_time_str` into a Python `datetime` object first to ensure it's a valid date, then format it safely back to an ISO string before passing it to `timedatectl`.

**Structure Impact:** None.
**Regression Risk:** Low

---

### [ID-6] Inconsistent Config State via Caching
**Severity:** Medium
**Confidence:** Confirmed
**Category:** State Management
**File:** `src/dashboard/routes.py`
**Location:** `settings()` at line 116

**Problem:**
The settings page writes updates directly to the `config.yaml` file but does not update the live `current_app.config["SHM_CONFIG"]` in memory.

**Why It Happens:**
The `settings()` endpoint dumps the YAML to disk and instructs the user to "restart". However, since the Flask app and the inference pipeline share the same process, modifying the disk file does not affect the currently running AI pipeline until the process is manually killed and restarted.

**Potential Impact:**
Users will change confidence thresholds or GSM numbers, see them successfully saved, but the system will continue operating on the old rules indefinitely until rebooted.

**Recommended Fix:**
Either provide an automatic soft-reload hook that reloads the PyYAML config and updates `app.config["SHM_CONFIG"]` (and the `HerdRiskEngine` which has a `reload_config()` method already!), or provide an explicit "Reboot System" button.

**Structure Impact:** Requires plumbing a reload hook into the running `SwineHealthMonitor` instance.
**Regression Risk:** Medium (modifying live configuration can cause race conditions if not thread-safe).

---

## 4. Possible Bugs & Logic Issues
*   **Websocket Frame Sync:** The `SensorHubStreamer.update_sensor_data` method overwrites `_latest_frame` via a reference swap. This is atomic in Python, but passing it directly to `cv2.imencode` in the background thread means if the matrix memory is modified externally (e.g. by OpenCV drawing bounding boxes on it concurrently), it could segfault or distort the image. The camera loop should pass a `.copy()` of the frame (it currently does, so it's safe, but worth noting for future edits).

## 5. Security Concerns
*   **Hardcoded Fallback Credentials:** The `auth.py` checks against `admin:CHANGE_ME`. It forces the user to change it, which is excellent. However, there are no rate limits on the basic auth endpoints, making the system vulnerable to brute-force attacks if exposed on an open AP.
*   **Open Websocket Port:** The WebSocket server running on `0.0.0.0:8765` requires no authentication. Anyone on the local network can connect and view the live camera feed and thermal grid.

## 6. Error Handling & Reliability
*   **Database Pruning Silently Fails:** `prune_snapshots` catches `Exception as e` if file deletion fails, logs a warning, and continues. This is safe, but there is no mechanism to alert the user if the disk is full and pruning permissions are broken.

## 7. Recommended Fix Order
1.  **Critical / High:** Fix the `cv2.imencode` blocking the `asyncio` event loop in `websocket_server.py`. (Use `run_in_executor`).
2.  **High:** Fix the `thermal_reader.read()` blocking the camera relay loop in `main.py`.
3.  **Medium:** Wrap the `_send_sms` call in a background thread to prevent halting the inference pipeline during alerts.
4.  **Medium:** Add a live-reload mechanism to `routes.py` so settings apply instantly instead of requiring a manual restart.
5.  **Low:** Add `datetime` parsing to `timedatectl` to sanitize time sync inputs.
6.  **Low:** Add type validation inside the `settings` POST payload parser.

## 8. Items Requiring Further Verification
*   **GSM Serial Stability:** Ensure that the 5V/2A power supply is actually isolated. If the GSM module spikes and draws power from the Pi's UART pins accidentally, it could brown out the Pi.
*   **Mobile App Polling:** The Flutter app uses `Timer.periodic(Duration(seconds: 5))` to poll `/api/pen_alerts` with a `timeout: Duration(seconds: 4)`. If the network drops packets and timeouts stack, does Flutter clean up the HTTP requests cleanly, or do they leak sockets?

## 9. Areas That Should NOT Be Changed Casually
*   **Database WAL Mode Initialization:** The `_conn()` context manager uses `PRAGMA busy_timeout=5000`. Do not remove this or lower the timeout. Because Flask threads and the Inference thread access the SQLite database concurrently, removing this will instantly cause `database is locked` exceptions in production.
*   **SORT Tracking IDs:** The `PigTracker` relies heavily on SORT's monotonic ID generation. Do not try to "reset" IDs to 0, as the `HerdRiskEngine` caches states against these IDs.
