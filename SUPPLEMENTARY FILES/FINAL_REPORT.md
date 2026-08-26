# Pig Tracking System - Final Verification Report

## Overview
This report summarizes the final Phase 2 verification of the Pig Tracking System. The objective was to validate actual system functionality, strictly evaluate limitations, and provide an honest assessment of the system's deployment readiness.

## Verification Status Labels

| Component / Subsystem | Status | Notes |
| :--- | :--- | :--- |
| **Network AP/LAN Switching** | `CODE-INSPECTED` / `BLOCKED` | **Deployment Limitation**: Cannot test `hostapd` transitions physically on the current OS. Simulated fallback parsing works correctly. |
| **Dashboard Developer Auth** | `TESTED` | Authenticated testing verified. Default `"admin"` config bypass was removed. |
| **GSM/SMS Module Diagnostics** | `TESTED` (Logic) / `SIMULATED` (Hardware) | **Hardware Limitation**: Logic strictly verified to prevent false alerts. Hardware serial AT commands simulated. |
| **AI Detector (ONNX)** | `TESTED` | **Model/Dataset Limitation**: Evaluated on test dataset. Excellent performance on stationary behaviors, poor performance on social behaviors. |
| **Alert State Machine** | `TESTED` | State boundaries, cooldown, and recovery paths fully verified. |
| **Tracking Isolation** | `TESTED` | Lethargy state successfully isolated per tracking ID. |
| **Snapshot & DB Storage** | `CODE-INSPECTED` | **Architectural Limitation**: Detections are pruned, but Alert Snapshots and Alert DB records grow indefinitely. |

## Detailed Verification Findings

### 1. Developer Authentication & Security
- **Status:** **Actual Bug** (Fixed).
- **Finding:** The system previously defaulted to the developer password `"admin"` if omitted from `config.yaml`.
- **Resolution:** The default was changed to `"CHANGE_ME"`. The authentication logic (`auth.py`) was updated to strictly block access if the password remains `"admin"` or `"CHANGE_ME"`. Normal users cannot access `/settings` or backend developer APIs.

### 2. Network Information & Mode Switching
- **Status:** **Deployment / Hardware Limitation**.
- **Finding:** Physical AP/LAN switching via `hostapd` was not tested because the test environment lacks the Raspberry Pi networking stack.
- **Resolution:** The code was inspected. The parsing logic inside `sys_info.py` correctly falls back to safe defaults (`"unknown"`) without crashing the dashboard on non-Linux environments.

### 3. GSM Diagnostic Limitations
- **Status:** **Enhancement** (Verified).
- **Finding:** The Developer Diagnostic test accurately reports what the hardware module knows: whether the command was accepted and if `+CMGS:` was acknowledged by the network.
- **Resolution:** The test confirms that diagnostic runs bypass the `SwineRepository` and `AlertEvent` state machine entirely. No fake alert records are logged during tests. (It cannot report actual SMS delivery to the handset, as `AT+CNMI` delivery receipts are not implemented).

### 4. AI Detection and Classification
- **Status:** **Dataset Limitation**.
- **Finding:** Running `evaluate_model.py` on the test dataset yielded an overall mAP50 of `0.8272`.
    - **Strengths:** Excellent performance on risk-engine behaviors: `lying` (0.9701), `sitting` (0.9453), `feeding` (0.93).
    - **Weaknesses:** Poor performance on `social_interaction` (0.5719) and `walking` (0.62).
- **Resolution:** **No new model was created.** The current model is limited by its dataset's representation of dynamic interactions. However, the downstream risk engine primarily triggers off high-confidence stationary behaviors (`lying`, `sitting`), meaning the architectural logic compensates for this classification weakness.

### 5. Snapshot Retention Behavior
- **Status:** **Architectural Limitation**.
- **Finding:** While `SwineRepository` contains retention logic to delete old transient `detections` and `ambient_readings` (e.g., older than 7 days), there is **no retention limit** on `pen_alerts` or the physical `.jpg` snapshot files.
- **Resolution:** Left as-is. Storage footprints for alerts will grow indefinitely, bounded only by the SD card capacity. This requires manual maintenance or a future structural update.

## Remaining Limitations & Final Verdict

The system is structurally sound for field testing, but it is **NOT fully production-ready** for unsupervised, long-term deployment due to the following remaining limitations:

1. **Storage Growth (Architectural):** Alert snapshots will eventually fill the SD card.
2. **AI Interaction (Dataset):** The model cannot reliably distinguish complex social behaviors (like fighting vs playing), limiting future expansion without a dataset overhaul.
3. **Hardware Transitions (Deployment):** Physical AP/LAN network switching and physical GSM timeouts remain unproven on real silicon in adverse conditions.

**Recommendation:** Proceed to physical field testing to gather real hardware logs, but schedule a storage management overhaul before committing to long-term deployment.
