# Mobile App & System Refinement Plan

## 1. Issue Analysis
* **FPS & Accuracy**: Currently, the Pi sends *raw* video frames to the app, expecting the app to run TFLite inference. However, the app's TFLite isolate is a stub, causing the app to display raw video with **zero detections**. This is why accuracy seems "off" — it's not actually detecting anything on the phone! 
* **Thermal Grid Orientation**: The thermal grid needs to be rotated 45 degrees clockwise.
* **Thermal Grid Aesthetics**: The thermal grid on the app looks blocky and "not good".
* **Dev Settings**: The settings are currently only accessible via the web dashboard browser, but the user wants them inside the app.

## 2. Proposed Implementation

### A. Fix Accuracy & Inference (Backend)
Instead of forcing the phone to run inference (which drains battery and disconnects from the Pi's GSM alert logic), we will **change the Pi to broadcast the fully annotated frames** to the WebSocket. 
* **Action**: Modify src/main.py and src/api/websocket_server.py to broadcast nnotated_frame instead of aw_frame.
* **Result**: The mobile app will display exactly what the Pi detects, instantly fixing the accuracy issue and keeping the GSM alerts 100% perfectly synced with the app display.

### B. Thermal Grid Fixes (Backend & Frontend)
* **Action**: Update config.yaml to set 	hermal.display_rotation_deg: 45.0 so the Pi sends the correctly rotated thermal grid.
* **Action**: Update mobile_app/lib/widgets/thermal_grid_widget.dart to apply a smooth gradient/blur filter (ImageFilter.blur(sigmaX: 4, sigmaY: 4)) so the thermal overlay looks like a high-end smooth heat map instead of blocky pixels.

### C. Dev Settings in Mobile App (Frontend)
* **Action**: Add a "Settings" button to the app's Dashboard screen.
* **Action**: Tapping it will open a Flutter WebView pointing directly to the Pi's http://[ip]:5000/settings endpoint. This gives the app full native access to the existing dashboard settings (GSM numbers, thresholds) without rewriting all the API endpoints in Dart.

## 3. User Review Required
> [!IMPORTANT]
> Since we are switching the WebSocket to broadcast the **annotated frame** from the Pi, the mobile app's frame rate will match the Pi's inference speed (~2-5 FPS). This guarantees perfect accuracy and saves your phone's battery. Is this acceptable, or do you strictly need the phone to run its own independent 30 FPS inference using the TFLite model? 

> [!NOTE]
> Do you approve this plan to proceed with the fixes?
