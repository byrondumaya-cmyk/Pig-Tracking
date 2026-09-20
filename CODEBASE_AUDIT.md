# Codebase Audit

## 1. Executive Summary

This repository appears to implement an offline swine health monitoring system for Raspberry Pi deployment, with a Python backend for video capture, ONNX inference, tracking, thermal/ambient sensing, alerting, persistence, and a Flask dashboard, plus a separate Flutter mobile client for a hybrid streaming mode.

The backend architecture is centered around `/src/main.py`, which orchestrates camera capture, object detection, SORT-based tracking, thermal mapping, behavioral analytics, herd risk evaluation, SQLite persistence, SMS alerts, and dashboard frame buffering. The dashboard is a Flask app under `/src/dashboard`, persistence is in `/src/database`, hardware integrations are in `/src/hardware` and `/src/thermal`, and the mobile client lives under `/mobile_app`.

The most important risks found are:

- the Flutter mobile inference path is currently non-functional and returns no detections;
- the hybrid WebSocket streamer stalls when thermal data is absent;
- committed credentials and unauthenticated dashboard APIs expose sensitive operational data;
- sensor “simulation mode” can silently feed fake thermal/ambient data into production alert logic;
- retention pruning uses fragile timestamp comparisons that can leave old data behind.

Overall, the repository shows clear architectural intent and useful test scaffolding, but several correctness, security, and deployment-readiness issues remain in core runtime paths.

---

## 2. Codebase Structure

### Main directories

- `src/` — Python production code for the Pi runtime
  - `main.py` — primary end-to-end runtime entry point
  - `sensor_hub.py` — hybrid-mode streaming entry point for mobile processing
  - `inference/` — ONNX detector and confirmation filter
  - `tracking/` — SORT tracker and tracked pig adapter
  - `thermal/` — MLX90640 reader and thermal zone mapping
  - `hardware/` — async camera, DHT22, GSM notifier
  - `analytics/` — behavior/state analysis and counting
  - `health/` — herd risk engine
  - `database/` — SQLite schema and repository layer
  - `dashboard/` — Flask app, routes, auth, stream buffers, system info helpers
- `mobile_app/` — Flutter mobile client and Android/iOS/desktop scaffolding
  - `lib/main.dart` — app entry point
  - `lib/screens/` — current UI screens
  - `lib/services/` — WebSocket and TFLite integration
  - `android/` — Android/Gradle build configuration
- `config/` — runtime YAML configuration
- `tests/` — Python unit/integration tests and Playwright E2E tests
- `scripts/` — deployment, diagnostics, profiling, dataset, and training utilities
- `.github/workflows/` — CI workflow definitions

### Important files and entry points

- `src/main.py` — main production path: camera → detector → tracker → thermal → analytics → risk engine → DB/SMS/dashboard
- `src/sensor_hub.py` — alternative runtime path for streaming raw camera + thermal data to mobile clients over WebSocket
- `src/dashboard/routes.py` — dashboard HTTP/JSON surface area
- `src/database/repository.py` and `src/database/schema.py` — persistence model and schema
- `mobile_app/lib/services/tflite_service.dart` — mobile inference path
- `mobile_app/lib/services/websocket_service.dart` — mobile streaming client
- `config/config.yaml` — deployed runtime settings, alert thresholds, credentials, AP config
- `.github/workflows/build.yml` — current CI pipeline

### Key dependency relationships

- `src/main.py` depends on nearly every backend subsystem and is the central coordinator.
- `src/dashboard/routes.py` depends on app-injected config/repository state and reads shared frame/thermal/behavior buffers from `src/dashboard/stream.py`.
- `src/health/risk_engine.py` depends on analytics output and ambient/thermal data provided by `src/main.py`.
- `src/sensor_hub.py` depends on `src/api/websocket_server.py` plus camera and thermal readers.
- The Flutter client depends on the Python hybrid streaming backend via `ws://<pi>:8765`.

---

## 3. Findings

### [AUD-001] Committed plaintext credentials are used as live runtime settings

**Severity:** High  
**Confidence:** Confirmed  
**Category:** Security  
**File:** `config/config.yaml`, `src/dashboard/auth.py`  
**Location:** Dashboard credentials and AP configuration

**Problem:**
The repository contains non-placeholder credentials in the runtime config, and the dashboard authentication layer uses the configured developer password directly.

**Why It Happens:**
`config/config.yaml` stores both `dashboard.developer_password` and `network.ap.password` as plaintext values, while `src/dashboard/auth.py` accepts any configured developer password that is not `admin` or `CHANGE_ME`.

**Potential Impact:**
Anyone with repository access, deployment artifact access, or config file access can learn the dashboard credential and AP password. If these values are reused in the field, developer-only routes and the Wi‑Fi network become easier to compromise.

**Evidence:**
- `config/config.yaml:139-153` contains concrete configured values for the dashboard password and AP password rather than placeholders.
- `src/dashboard/auth.py:11-18` reads `cfg.dashboard.developer_password` and accepts it directly for HTTP Basic Auth.

**Recommended Fix:**
Move credentials out of committed config, load them from deployment-only secrets or device-local overrides, and fail startup when production credentials are missing or still default.

**Structure Impact:**
This can preserve the existing structure by keeping the same config model while changing only the credential source and startup validation behavior.

**Regression Risk:** Low

**Notes:**
This is a confirmed security concern regardless of whether the current values are “example” values, because the code path treats them as real runtime credentials.

### [AUD-002] Several dashboard APIs expose sensitive operational data without developer authentication

**Severity:** High  
**Confidence:** Confirmed  
**Category:** Security  
**File:** `src/dashboard/routes.py`, `src/dashboard/static/js/dashboard.js`  
**Location:** `/api/ap-info`, `/api/recipients`, `/api/sms_logs`, `/api/sms_templates`, `/api/time_sync`

**Problem:**
Multiple read endpoints return sensitive information without `@dev_required`, including AP credentials, recipient phone numbers, SMS log contents, and time-sync history.

**Why It Happens:**
Only mutating routes are consistently protected. Several GET routes return operational or personal data without any authentication decorator.

**Potential Impact:**
Users on the same network can enumerate recipient phone numbers, inspect alert message history, and retrieve the AP password and QR payload. This increases the exposure of credentials and PII.

**Evidence:**
- `src/dashboard/routes.py:743-769` returns AP SSID, password, IP, and Wi‑Fi QR data without `@dev_required`.
- `src/dashboard/routes.py:322-329` returns all alert recipients without `@dev_required`.
- `src/dashboard/routes.py:494-503`, `572-599`, and `628-644` expose SMS templates, SMS logs, and time-sync logs without `@dev_required`.
- `src/dashboard/static/js/dashboard.js:246-265` reads `/api/ap-info` and renders the returned password directly in the UI.

**Recommended Fix:**
Apply developer authentication to all endpoints that expose credentials, phone numbers, message history, or diagnostic history, and reduce the returned fields to the minimum required by the UI.

**Structure Impact:**
This is a targeted route-hardening change that preserves the current Flask blueprint and frontend structure.

**Regression Risk:** Medium

**Notes:**
Some of these endpoints may have been left open for ease of setup on AP mode, so frontend flows should be checked before tightening access.

### [AUD-003] Flutter mobile inference is stubbed and always returns no detections

**Severity:** Critical  
**Confidence:** Confirmed  
**Category:** Bug  
**File:** `mobile_app/lib/services/tflite_service.dart`  
**Location:** `_inferenceWorker()`

**Problem:**
The mobile inference path does not actually run model inference and always returns an empty list.

**Why It Happens:**
The isolate worker builds a resized input tensor but does not create or use an interpreter inside the isolate. The method ends with an unconditional `return [];`.

**Potential Impact:**
The core mobile hybrid experience cannot show detections or behavior overlays, so the application appears connected but functionally incomplete.

**Evidence:**
- `mobile_app/lib/services/tflite_service.dart:120-127` allocates an output structure but then explicitly returns `[]`.
- `mobile_app/lib/screens/dashboard_screen.dart:35-49` depends on `runInferenceAsync()` to populate `_currentDetections`.

**Recommended Fix:**
Either initialize a fresh TFLite interpreter inside the worker isolate or move inference back to a controlled synchronous path until isolate-safe model loading is implemented.

**Structure Impact:**
This can be fixed within the existing service layer without architectural change.

**Regression Risk:** Medium

**Notes:**
This is the clearest mobile correctness issue in the repository because the code explicitly acknowledges the limitation and still ships the empty return path.

### [AUD-004] Hybrid WebSocket streaming stalls entirely when thermal data is absent

**Severity:** High  
**Confidence:** Confirmed  
**Category:** Bug  
**File:** `src/api/websocket_server.py`, `src/sensor_hub.py`  
**Location:** `_broadcast_loop()` and `main()`

**Problem:**
The hybrid streamer refuses to send frames unless both RGB and thermal data are present, but `sensor_hub.py` passes `None` when thermal is disabled or unavailable.

**Why It Happens:**
`SensorHubStreamer._broadcast_loop()` waits while either `_latest_frame` or `_latest_thermal` is `None`, yet `sensor_hub.py` sets `thermal_grid = None` whenever no thermal reader is active.

**Potential Impact:**
The mobile client can connect successfully but never receive any streamed frames when thermal hardware is disabled, not installed, or temporarily unavailable.

**Evidence:**
- `src/api/websocket_server.py:60-62` skips broadcasting if `_latest_frame is None or _latest_thermal is None`.
- `src/sensor_hub.py:124-129` sets `thermal_grid = None` when no reader is active and still calls `update_sensor_data(frame, thermal_grid)`.

**Recommended Fix:**
Allow frame-only payloads when thermal data is unavailable, and send an explicit empty grid or availability flag rather than blocking the entire stream.

**Structure Impact:**
This is a small protocol adjustment within the current WebSocket architecture.

**Regression Risk:** Medium

**Notes:**
This issue is especially important because the Flutter client already handles empty or missing thermal grids gracefully.

### [AUD-005] Android release manifest lacks Internet permission for WebSocket connectivity

**Severity:** High  
**Confidence:** Confirmed  
**Category:** Configuration  
**File:** `mobile_app/android/app/src/main/AndroidManifest.xml`, `mobile_app/lib/services/websocket_service.dart`  
**Location:** Android app manifest

**Problem:**
The production Android manifest does not declare `android.permission.INTERNET` even though the app opens a WebSocket connection to the Pi.

**Why It Happens:**
The app’s runtime depends on `WebSocketChannel.connect(Uri.parse('ws://...'))`, but the main manifest contains only the application/activity declarations and query block.

**Potential Impact:**
Release builds may fail to establish the WebSocket connection even when the backend is healthy, breaking the primary mobile data path.

**Evidence:**
- `mobile_app/lib/services/websocket_service.dart:73-79` connects to `ws://$ip:8765`.
- `mobile_app/android/app/src/main/AndroidManifest.xml:1-45` contains no `<uses-permission android:name="android.permission.INTERNET" />`.

**Recommended Fix:**
Declare Internet permission in the main Android manifest and verify release behavior on a device.

**Structure Impact:**
This is a minimal manifest fix that preserves the current mobile architecture.

**Regression Risk:** Low

**Notes:**
The repository should verify this in an actual release build because debug manifests can mask permission gaps during local development.

### [AUD-006] Sensor fallback “simulation mode” can silently drive production alerts with fake data

**Severity:** High  
**Confidence:** Confirmed  
**Category:** Reliability  
**File:** `src/thermal/thermal_reader.py`, `src/hardware/dht22_sensor.py`, `src/main.py`  
**Location:** Thermal and ambient sensor initialization/read paths

**Problem:**
If thermal or ambient libraries/hardware are unavailable, the system silently substitutes synthetic readings rather than clearly marking the sensor unavailable.

**Why It Happens:**
The MLX90640 reader and DHT22 sensor both fall back to simulation behavior. The thermal reader generates artificial grids, including a hot central blob, and `main.py` accepts the reader as successfully initialized because no exception is raised.

**Potential Impact:**
A deployment with broken hardware or missing libraries can continue “working” while generating false temperatures, incorrect THI, and potentially false fever or lethargy alerts.

**Evidence:**
- `src/thermal/thermal_reader.py:42-45` enters simulation mode when imports fail.
- `src/thermal/thermal_reader.py:152-157` generates a random base grid plus a 38–41°C hot center blob.
- `src/main.py:152-167` logs the thermal camera as initialized if the reader object is constructed successfully.
- `src/hardware/dht22_sensor.py:94-97` returns a synthetic ambient reading when `_device is None`.

**Recommended Fix:**
Differentiate development simulation from production runtime explicitly. In production mode, failed sensor initialization should mark the sensor unavailable and prevent simulated values from entering health logic unless an operator has intentionally enabled simulation.

**Structure Impact:**
This can be implemented inside the existing sensor classes and startup logic without changing the broader architecture.

**Regression Risk:** Medium

**Notes:**
This is one of the highest-leverage robustness fixes because it affects alert correctness rather than just UI behavior.

### [AUD-007] Retention pruning uses fragile text comparisons for timestamps

**Severity:** Medium  
**Confidence:** Confirmed  
**Category:** Reliability  
**File:** `src/database/repository.py`  
**Location:** `prune_detections()` and `prune_ambient_readings()`

**Problem:**
Old records are pruned by comparing raw timestamp text to `datetime('now', ?)` rather than normalizing stored timestamps through SQLite date functions.

**Why It Happens:**
The repository stores timestamps via `datetime.utcnow().isoformat()` (e.g. ISO timestamps with `T` and fractional seconds), but the delete query compares those strings directly against SQLite’s `datetime()` output.

**Potential Impact:**
Rows near the day/time cutoff can be retained incorrectly, causing storage growth and inconsistent retention behavior.

**Evidence:**
- `src/database/repository.py:24-26` stores timestamps using `datetime.utcnow().isoformat()`.
- `src/database/repository.py:137-150` deletes rows with `WHERE timestamp < datetime('now', ?)` rather than `datetime(timestamp) < datetime('now', ?)`.

**Recommended Fix:**
Normalize both sides of the comparison in SQL using SQLite datetime functions, or store timestamps in a single SQLite-native format consistently.

**Structure Impact:**
This is a localized repository query fix and does not require schema redesign unless stricter timestamp typing is desired.

**Regression Risk:** Low

**Notes:**
Existing tests cover pruning broadly, but not same-date boundary behavior with ISO strings.

### [AUD-008] Time-sync error details are accepted by the repository API but never persisted

**Severity:** Medium  
**Confidence:** Confirmed  
**Category:** Maintainability  
**File:** `src/database/schema.py`, `src/database/repository.py`, `src/dashboard/routes.py`  
**Location:** Time sync logging

**Problem:**
The code records time-sync failures with an `error_message` argument, but the database schema and insert statement do not store it.

**Why It Happens:**
`SwineRepository.log_time_sync()` accepts `error_message`, while `time_sync_log` lacks an `error_message` column and the insert query writes only six fields.

**Potential Impact:**
Failure diagnostics for time synchronization are lost, making support and field troubleshooting harder.

**Evidence:**
- `src/database/schema.py:102-111` defines `time_sync_log` without an `error_message` column.
- `src/database/repository.py:556-572` accepts `error_message` but inserts only `(timestamp, source_type, source_ip, old_time, new_time, status)`.
- `src/dashboard/routes.py:672-703` passes detailed failure information to `repo.log_time_sync(...)`.

**Recommended Fix:**
Add an `error_message` column via migration and persist it from `log_time_sync()`.

**Structure Impact:**
This preserves the existing repository and route structure; it only requires a small schema migration and repository update.

**Regression Risk:** Medium

**Notes:**
This is not a crash bug, but it directly weakens post-failure observability.

### [AUD-009] Included E2E pipeline script is stale and references removed thermal classes

**Severity:** Medium  
**Confidence:** Confirmed  
**Category:** Maintainability  
**File:** `test_e2e_pipeline.py`  
**Location:** Thermal reader mocking and monitor setup

**Problem:**
The root-level E2E pipeline script still references `AMG8833Reader`, but the backend has moved to `MLX90640Reader`.

**Why It Happens:**
The script was not updated after the thermal hardware integration changed from the older 8x8 sensor assumptions to the MLX90640 flow.

**Potential Impact:**
Anyone relying on this script as a verification path will get import/setup failures or misleading results, reducing confidence in regression testing.

**Evidence:**
- `test_e2e_pipeline.py:48-50` monkey-patches `src.thermal.thermal_reader.AMG8833Reader`.
- `test_e2e_pipeline.py:116-119` imports and instantiates `AMG8833Reader`.
- `src/thermal/thermal_reader.py:47-47` defines `MLX90640Reader`, not `AMG8833Reader`.

**Recommended Fix:**
Update the E2E script to the current thermal reader abstraction or remove the obsolete test path if it is no longer intended to run.

**Structure Impact:**
This is a contained test/tooling correction and does not affect runtime architecture.

**Regression Risk:** Low

**Notes:**
This is also a signal that some documentation and verification artifacts still reference the previous sensor generation.

### [AUD-010] The current CI workflow only builds the Flutter APK and does not validate the Python backend

**Severity:** Medium  
**Confidence:** Confirmed  
**Category:** Maintainability  
**File:** `.github/workflows/build.yml`  
**Location:** Entire workflow

**Problem:**
The only configured GitHub Actions workflow installs Flutter dependencies and builds the Android APK. It does not run backend tests, dashboard tests, or static verification for the Python runtime.

**Why It Happens:**
The workflow was scoped around the mobile build and currently has no Python job.

**Potential Impact:**
Backend regressions in the Pi runtime, Flask dashboard, repository layer, or test suite can reach `main` without automated detection.

**Evidence:**
- `.github/workflows/build.yml:1-39` contains a single `build` job with `flutter pub get` and `flutter build apk --release` only.
- The repository includes Python tests under `tests/` and additional root-level verification scripts that are not exercised in CI.

**Recommended Fix:**
Add a separate Python CI job that installs runtime/test dependencies and runs the backend test suite, keeping the Flutter build as a separate concern.

**Structure Impact:**
This preserves the current repository layout and only expands CI coverage.

**Regression Risk:** Low

**Notes:**
This does not prove the backend is broken, but it materially increases the chance that backend defects remain undetected.

### [AUD-011] Mobile test and dead-code paths are already drifting from the active app implementation

**Severity:** Low  
**Confidence:** Confirmed  
**Category:** Maintainability  
**File:** `mobile_app/test/widget_test.dart`, `mobile_app/lib/ui/dashboard.dart`, `mobile_app/lib/main.dart`  
**Location:** Flutter test and duplicate dashboard UI

**Problem:**
The Flutter test references a non-existent `MyApp`, and the repository still contains an older dashboard implementation that is not referenced by the current entry point.

**Why It Happens:**
The mobile app evolved from an earlier dashboard structure, but older code and template tests were retained.

**Potential Impact:**
This increases maintenance overhead and reduces trust in the test suite because dead or stale paths can diverge silently.

**Evidence:**
- `mobile_app/test/widget_test.dart:11-18` imports `main.dart` but pumps `const MyApp()` even though `mobile_app/lib/main.dart:23-53` defines `SwineHealthApp`.
- `mobile_app/lib/ui/dashboard.dart:1-140` defines another `DashboardScreen`, while `mobile_app/lib/main.dart:48` routes to `mobile_app/lib/screens/dashboard_screen.dart`.
- `rg` inspection shows no active import of `mobile_app/lib/ui/dashboard.dart` from the current app entry path.

**Recommended Fix:**
Update or replace the widget test to target the current app entry point and remove or quarantine obsolete UI implementations.

**Structure Impact:**
This is a low-risk cleanup that does not require architectural change.

**Regression Risk:** Low

**Notes:**
The duplicate dashboard file may still contain useful prototype logic, so it should be compared carefully before deletion.

### [AUD-012] Dashboard inference is triggered from `build()`, causing repeated async work and avoidable UI overhead

**Severity:** Medium  
**Confidence:** Likely  
**Category:** Performance  
**File:** `mobile_app/lib/screens/dashboard_screen.dart`  
**Location:** `build()` and `_processFrame()`

**Problem:**
The screen kicks off inference as a side effect of every rebuild whenever `latestData` is present.

**Why It Happens:**
`build()` calls `_processFrame(ws.latestData!)` directly instead of reacting to frame changes via a listener, stream transformer, or controlled scheduler.

**Potential Impact:**
Frequent provider-driven rebuilds can trigger repeated async inference attempts, produce unnecessary UI churn, and make performance sensitive to rendering cadence rather than frame cadence.

**Evidence:**
- `mobile_app/lib/screens/dashboard_screen.dart:35-49` defines async frame processing.
- `mobile_app/lib/screens/dashboard_screen.dart:56-59` calls `_processFrame(ws.latestData!)` inside `build()`.

**Recommended Fix:**
Move inference triggering out of `build()` and into a listener or frame-change handler keyed by new `SensorData` arrivals.

**Structure Impact:**
This can be fixed within the existing `ChangeNotifier`/screen structure.

**Regression Risk:** Medium

**Notes:**
Because the current TFLite service is also stubbed, this is partly masked today; it becomes more important once real mobile inference is restored.

---

## 4. Possible Bugs & Logic Issues

The most important logic issues found are:

- **[AUD-003]** The mobile inference worker returns an empty detection list unconditionally, so the hybrid mobile flow does not perform its primary task.
- **[AUD-004]** The hybrid streamer requires thermal data before broadcasting any frame, which blocks the entire feed when thermal is disabled or absent.
- **[AUD-007]** Retention pruning uses raw text comparison between differing timestamp formats, which can produce incorrect keep/delete decisions near cutoffs.
- **[AUD-011]** The Flutter widget test and older dashboard implementation are already out of sync with the active app structure.
- **[AUD-012]** The dashboard screen performs side effects during `build()`, which is a fragile place to trigger async work.

Additional lower-confidence logic risks observed during inspection:

- `src/main.py:314` uses `frame_count % self.cfg.inference.frame_skip` without validating `frame_skip > 0`, so a bad config could crash the loop.
- `src/dashboard/routes.py:340-347` accepts any non-empty recipient string, so invalid phone data can be persisted and later passed straight to the GSM module.

---

## 5. Possible Errors & Failure Points

Key runtime failure points include:

- **[AUD-005]** Android release networking may fail because Internet permission is absent from the main manifest.
- **[AUD-006]** Missing thermal or ambient hardware can silently degrade into fake data instead of a visible unavailable state.
- **[AUD-008]** Time-sync failures lose their diagnostic details, weakening troubleshooting.
- `src/api/websocket_server.py:17-20, 96-96` suppresses `ImportError` for `websockets` but later uses the module unconditionally; if the dependency is missing, server startup can fail at runtime rather than at initialization.
- `tests/conftest.py:13-15` contains a placeholder branch that does not build a minimal config when the expected file is missing, so the comment and code behavior differ.

---

## 6. Security Concerns

The strongest security concerns are:

- **[AUD-001]** Committed plaintext credentials used as runtime values.
- **[AUD-002]** Unauthenticated APIs exposing AP credentials, recipient phone numbers, SMS templates/logs, and diagnostic history.

Additional security observations:

- `src/dashboard/auth.py` uses HTTP Basic Auth only; if the dashboard is ever exposed outside a trusted local network, transport protection becomes important.
- `src/dashboard/routes.py:665-704` performs privileged time-setting operations based on user input after authentication. The subprocess call avoids shell injection, but input format validation is still light.
- `scripts/setup_ap.sh:123-139, 193-195` writes the AP password to system config and echoes it in the terminal summary. That is normal for local provisioning but should be treated as a sensitive administrative flow.

---

## 7. Performance & Scalability Concerns

Primary performance/scalability concerns are:

- **[AUD-012]** Mobile inference scheduling is tied to Flutter rebuilds rather than explicit frame lifecycle events.
- `src/api/websocket_server.py:64-90` JPEG-encodes and base64-encodes full frames continuously for every active stream loop. This is acceptable for a single operator device but may become CPU/network heavy with multiple clients.
- `src/dashboard/stream.py:54-58` and `src/hardware/async_camera.py:114-117` make frame copies for isolation safety; this is reasonable, but it adds memory bandwidth overhead on constrained hardware.
- `src/thermal/thermal_reader.py:127-133, 152-157` rotates full thermal grids in the polling thread every cycle. That is not necessarily wrong, but it should be measured on target hardware rather than assumed negligible.

---

## 8. Error Handling & Reliability

Reliability concerns include:

- **[AUD-006]** Silent simulation fallback can mask broken hardware and produce believable-but-false runtime data.
- **[AUD-007]** Retention pruning may quietly fail to remove stale data.
- **[AUD-008]** Time-sync failure details are discarded.
- `src/api/websocket_server.py:47-48, 81-84` swallows send/receive exceptions with minimal logging, which reduces observability when mobile connectivity is unstable.
- `src/hardware/async_camera.py:170-182` retries reconnects indefinitely, which is often useful, but repeated hardware flapping could cause long noisy retry loops without escalation.

---

## 9. Maintainability & Technical Debt

Important maintainability issues:

- **[AUD-009]** Root E2E verification script still targets removed thermal classes.
- **[AUD-010]** CI only covers one slice of the repository.
- **[AUD-011]** The Flutter app contains duplicate/stale UI code and a broken default widget test.
- `README.md:177-180` links to `docs/installation_manual.md`, `docs/user_manual.md`, `docs/developer_manual.md`, and `docs/architecture.md`, but those files are missing from `docs/`.
- README and comments still contain older AMG8833 references even though runtime code now targets the MLX90640 (`README.md:87-91, 136`, `requirements-pi.txt:21`).

These items are low-to-medium severity individually, but together they make onboarding and safe modification harder.

---

## 10. Improvements

### Improvement A — Make runtime sensor availability explicit

**What should improve:** Avoid silent substitution of simulated data in production-like runs.  
**Why it matters:** False thermal or ambient inputs directly affect alert quality.  
**Suggested approach:** Add an explicit simulation/development mode flag and fail or mark components unavailable when hardware initialization fails unexpectedly.  
**Can this be done without changing the existing structure?** Yes.  
**Potential regression risk:** Medium.

### Improvement B — Harden dashboard data exposure

**What should improve:** Restrict access to operational secrets and PII.  
**Why it matters:** The dashboard currently leaks Wi‑Fi credentials, phone numbers, and message history through unauthenticated endpoints.  
**Suggested approach:** Apply `@dev_required` more broadly and reduce payload fields for read endpoints.  
**Can this be done without changing the existing structure?** Yes.  
**Potential regression risk:** Medium.

### Improvement C — Restore end-to-end mobile functionality

**What should improve:** Make the mobile app actually perform inference and receive degraded-but-valid data when thermal is unavailable.  
**Why it matters:** The hybrid path currently looks wired together but does not deliver its intended functionality.  
**Suggested approach:** Fix `TFLiteService`, add the Android Internet permission, and let the backend stream frame-only payloads.  
**Can this be done without changing the existing structure?** Yes.  
**Potential regression risk:** Medium.

### Improvement D — Improve timestamp and observability hygiene

**What should improve:** Make data retention and failure logging trustworthy.  
**Why it matters:** Quiet retention drift and missing error details cause operational blind spots.  
**Suggested approach:** Normalize timestamp storage/comparison and persist full time-sync error details.  
**Can this be done without changing the existing structure?** Yes.  
**Potential regression risk:** Low to Medium.

### Improvement E — Expand automated verification

**What should improve:** Cover backend and dashboard behavior in CI.  
**Why it matters:** The current workflow can report green even when the Pi runtime or tests are broken.  
**Suggested approach:** Add Python test jobs and refresh stale test artifacts.  
**Can this be done without changing the existing structure?** Yes.  
**Potential regression risk:** Low.

---

## 11. Recommended Fix Order

### 1. Critical fixes

1. **[AUD-003]** Restore working mobile inference instead of returning empty results.

### 2. High-priority fixes

1. **[AUD-001]** Remove committed runtime credentials and enforce secure deployment-time secrets.
2. **[AUD-002]** Protect sensitive dashboard read endpoints.
3. **[AUD-004]** Allow frame-only hybrid streaming when thermal is unavailable.
4. **[AUD-005]** Add Android Internet permission verification for release builds.
5. **[AUD-006]** Stop using silent simulated sensor data in production-like runs.

### 3. Medium-priority fixes

1. **[AUD-007]** Fix retention pruning timestamp handling.
2. **[AUD-008]** Persist time-sync error details.
3. **[AUD-009]** Refresh or remove stale E2E pipeline tooling.
4. **[AUD-010]** Add Python/backend CI coverage.
5. **[AUD-012]** Move mobile inference triggering out of `build()`.

### 4. Low-priority improvements

1. **[AUD-011]** Clean up duplicate Flutter dashboard code and stale tests.
2. Repair missing README-linked documentation files.
3. Align old AMG8833 references with current MLX90640 terminology.
4. Tighten recipient and settings input validation.

---

## 12. Items Requiring Further Verification

The following concerns are credible but need runtime or environment-specific verification:

- **Android release networking behavior** for **[AUD-005]** should be tested on a real release APK to confirm the manifest gap is user-visible in deployment.
- **Sensor fallback behavior** for **[AUD-006]** should be tested on a Pi with intentionally disconnected DHT22/MLX90640 hardware to verify exactly how alerts degrade today.
- **Retention boundary behavior** for **[AUD-007]** should be tested with timestamps near same-day cutoffs to confirm the exact pruning error surface.
- **Mobile performance impact** for **[AUD-012]** should be profiled after real TFLite inference is restored, because the current stub masks part of the cost.
- **Dashboard endpoint exposure risk** for **[AUD-002]** should be verified against the intended threat model for AP-only deployments versus LAN deployments.
- **WebSocket dependency failure path** should be tested on a system where the `websockets` package is absent to confirm the observed startup failure mode.

---

## 13. Areas That Should NOT Be Changed Casually

### Android Java/Kotlin 17 build alignment

The Android build is currently standardized on Java 17 and Kotlin JVM 17 for the app module and Android library subprojects (`mobile_app/android/build.gradle.kts`, `mobile_app/android/app/build.gradle.kts`). This should not be changed casually because recent CI failures were caused by mismatched JVM targets across Flutter plugins.

### Thermal rotation handling

`src/thermal/thermal_reader.py` applies a configurable clockwise rotation to the thermal grid before mapping and display. This may look unusual, but comments and config indicate it is compensating for a physical mounting issue. Changing it without recalibrating thermal-to-RGB alignment could break both visualization and alert logic.

### Session-scoped SORT tracking behavior

`src/analytics/behavior_analyzer.py` and `src/tracking/` intentionally treat track IDs as temporary session-scoped identities. This can look simplistic, but it matches the herd-level alert design. Changing it toward persistent individual identity would have broader architectural implications.

### Shared dashboard buffers

`src/dashboard/stream.py` uses singleton-like shared buffers for frames, thermal data, and behavior counts across threads. This is a deliberate cross-thread communication mechanism; replacing it casually could introduce race conditions or streaming regressions.

### AP setup strategy that bypasses NetworkManager

`scripts/setup_ap.sh` explicitly unmanages `wlan0` and uses `hostapd`/`dnsmasq` directly. This is likely a compatibility workaround for Raspberry Pi deployment. Reworking it without field testing could easily regress AP reliability.

