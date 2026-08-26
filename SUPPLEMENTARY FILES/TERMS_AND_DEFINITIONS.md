# Pig Tracking System - Terms and Definitions

To ensure clarity between developers, operators, and veterinary staff, the following specific terms are used throughout the system's architecture and UI.

### AlertEvent
A database record and corresponding SMS notification indicating that a health risk condition has been met in the pen. There are two types: `individual` and `population`.

### Channel 1 / Channel 2
Refers to the two distinct logical pathways in the `HerdRiskEngine`. 
- **Channel 1:** Monitors individual pigs for combined lethargy and fever.
- **Channel 2:** Monitors the entire herd simultaneously for widespread lethargy (e.g., indicating poor air quality or highly contagious spread).

### Cooldown
A 5-minute suppression window that activates immediately after an alert is sent. During this window, the system continues to monitor the pigs and save data, but it will **not** send duplicate SMS messages for the same alert type to prevent spamming the farmer.

### Developer Mode
A privileged access tier in the Web Dashboard. Actions like adding/removing SMS recipient phone numbers or running GSM Diagnostic Tests require a developer password.

### Fever Delta
The difference between a pig's estimated surface temperature and the ambient barn temperature. The system uses a delta (default `>2.0°C`) rather than a fixed absolute temperature (e.g., `>39°C`) to reduce false alarms caused by hot barn environments.

### Lethargy
In the context of this system, lethargy is strictly defined as a behavioral state where a tracked object remains in a `stationary` classification for an abnormal duration (e.g., > 15 minutes). It is a behavioral observation, not a medical diagnosis.

### Snapshot
A `.jpg` image frame captured from the camera feed at the exact second an `AlertEvent` is triggered. Snapshots include bounding boxes and temperature overlays to provide visual evidence to the farmer.

### Stationary
A grouping of specific YOLO behavioral classifications that imply lack of movement. By default, this includes the model classes `lying` and `sitting`.

### THI (Temperature Humidity Index)
A bioclimatic index calculated from the DHT22 sensor readings (ambient temperature and relative humidity). It represents the level of heat stress experienced by the pigs. The system uses this to automatically adapt its thresholds (e.g., THI > 78 extends the lethargy timeout to 30 minutes because pigs naturally rest more in severe heat).

### Track ID (Object ID)
A temporary integer assigned by the SORT tracking algorithm to a specific pig in the camera frame. 
- **Important:** These IDs are *session-scoped* and *spatial*. They are not persistent biometrics. If Pig 1 walks behind a wall and returns 2 hours later, it will be assigned a new ID (e.g., Pig 45). Lethargy tracking relies on the pig remaining in view for the duration of the timeout.
