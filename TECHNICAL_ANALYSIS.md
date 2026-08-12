# Pig Tracking System - Root Cause Analysis & Optimization Plan

## Issue 1: FPS Performance (1.4 FPS → Target 20+ FPS)

### Root Cause Analysis
```
Finding: Actual measured FPS = 14.22 FPS (targeting 20 FPS)
Gap needed: 40.6% performance improvement
```

**Bottleneck Breakdown:**
```
Total loop time:         70.32 ms  (need ≤50 ms for 20 FPS)
  ├─ Camera capture:     43.44 ms  (61.77% of loop) - HIGH VARIANCE (0.05-227 ms)
  └─ Model inference:    53.18 ms  (75.63% of loop)
      ├─ Preprocess:      4.27 ms   (8% of inference)
      ├─ ONNX run:       48.05 ms   (90% of inference) ← PRIMARY BOTTLENECK
      └─ Postprocess:     0.45 ms   (1% of inference)
```

**Why 20 FPS is Challenging:**
- YOLOv8n at 640x640 requires significant CPU work per frame
- Raspberry Pi has limited CPU (4-8 cores max)
- No GPU/NPU acceleration available
- Model inference is fundamentally CPU-bound

**Hardware Reality:**
- 48 ms per frame inference = 20.8 FPS theoretical max (with ZERO overhead)
- Adding camera capture (43 ms) = 13.9 FPS max
- Current: 70.32 ms total = 14.2 FPS actual

### Recommended Solutions (In Order of Impact)

**1. Increase Frame Skip (FASTEST, -30-40% loop time)**
   - Current: frame_skip=2 (process 1 in 3 frames)
   - Proposal: frame_skip=3 (process 1 in 4 frames)
   - Expected: Loop time 70.32 → 35.16 ms (20 FPS achieved!)
   - Tradeoff: Tracking updates 4x/second instead of 10x/second
   - Impact: Minor latency increase, maintains real-time feel

**2. Asynchronous Camera Capture (SECONDARY, -30-50% capture time)**
   - Current: Blocking cv2.VideoCapture.read() in main loop
   - Proposal: Separate thread reads camera into ring buffer
   - Expected: Decouple 43 ms camera I/O from inference pipeline
   - Impact: Smooths out variance (227 ms max spike)
   - Implementation: threading.Thread + queue.Queue

**3. Detector Input Resolution (NOT RECOMMENDED)**
   - Cannot reduce 640→416 without model re-export
   - Model expects exactly 640x640 input (ONNX hard constraint)
   - Would require retraining + re-export

**4. Inference Backend Optimization (COMPLEX)**
   - ONNX Runtime already using ORT_ENABLE_ALL optimizations
   - TensorRT: Not available on Raspberry Pi (NVIDIA only)
   - OpenVINO: Could provide 20-30% speedup but adds complexity
   - Quantization (INT8): Would need quantized ONNX model

### Implementation Priority
1. **Immediate**: Increase frame_skip=2 → 3 (5 min implementation)
2. **Follow-up**: Add async camera thread (15 min implementation)
3. **Validation**: Measure FPS improvement
4. **If needed**: Consider OpenVINO or quantization

---

## Issue 2: Missing Behavior Labels

### Root Cause Analysis
```
Status: NOT MISSING - Already Implemented ✓
```

**Evidence:**
- File: src/dashboard/stream.py, line ~66
- Function: _annotate_frame() creates labels with format:
  `f"#{pig.track_id} {pig.behavior} {pig.confidence:.0%}"`
- Called in: main.py line 335 via FrameBuffer.update()
- Behavior colors defined: BEHAVIOR_COLORS dict with all 8 classes

**Label Pipeline:**
```
Detector output (class_id)
  ↓
PigTracker: class_names[class_id] → behavior string
  ↓
main.py: tracked_pigs include behavior
  ↓
FrameBuffer.update(): Calls _annotate_frame()
  ↓
Dashboard stream: Displays labels on MJPEG output
```

### Issue
Behavior labels ARE being drawn. Need to verify in live video that they appear.

### Action
Run live test with camera and observe:
- Check dashboard at http://[PI_IP]:5000/
- Verify behavior labels visible on video (Lying/Standing/Drinking)
- Check behavior API at http://[PI_IP]:5000/api/behavior_counts

---

## Issue 3: Pig Counting & Re-entry Duplicates

### Root Cause Analysis
```
Current Behavior: Pig count increments on every re-entry (WRONG)
Example: Pig leaves → count stays 1 → Pig re-enters → count becomes 2 (WRONG)
Expected: Persistent pig identity OR occupancy counting
```

**Why This Happens:**

SORT Tracker (src/tracking/sort_tracker.py):
- Uses Hungarian algorithm to match detections to existing tracks by IoU
- When a pig leaves camera: Track ages out after max_age=30 frames
- When pig re-enters: New detection gets NEW track_id (no memory of past)
- System counts: "number of active tracks" = "number of distinct pigs seen"

**Architectural Limitation:**
- SORT is appearance-agnostic (pure spatial matching)
- No re-identification capability (no Person Re-ID model)
- No persistent ID storage across sessions
- Cannot distinguish: "same pig returned" vs "new pig entered"

### Why It Matters
- If goal is OCCUPANCY: Count should be ≤ max physical pigs in pen
- If goal is ANALYTICS: Need to distinguish new vs returning pigs

### Possible Solutions

**Option A: Occupancy Counting (Simple)**
- Track current active tracks (don't increment on re-entry)
- Display: "Pigs currently in view: 3"
- Implementation: Count len(tracked_pigs) at each frame
- Limitation: Cannot tell if pig left and returned

**Option B: Persistent ID Mapping (Medium Complexity)**
- Assign stable IDs based on first-seen timestamp + appearance
- Store pig identity in database with appearance fingerprint
- Limitation: Still can't guarantee re-identification without re-ID model

**Option C: Accept Session-Scoped IDs (Transparent)**
- Rename "pig count" to "pig visits" or "unique detections"
- Display per-session stats only
- Limitation: Analytics across sessions become complex

**Option D: Add Appearance Model (Complexity + Training)**
- Implement person re-identification model (e.g., DeiT, ViT)
- Requires additional GPU training and model
- Would significantly increase inference time

### Recommendation
**Implement Option A (Occupancy) immediately:**
- Use `len(tracked_pigs)` for current count
- Most intuitive for farm monitoring (how many pigs here NOW)
- No false increments on re-entry
- Clear and accurate for immediate use case

---

## Issue 4: Health Indicator Cross-Reference

### Current Implementation Review

**File: src/health/risk_engine.py**

**Channel 1: Individual Fever Alert**
```
Triggers when:
  1. Single pig stationary ≥ 15 min
  2. AND zone_temp > ambient + 2.0°C
  3. With THI adaptation: If THI > 78, extends to 30 min
```

**Channel 2: Population Lethargy Alert**
```
Triggers when:
  1. ≥ 60% of detected pigs stationary
  2. For ≥ 3 consecutive seconds
  3. Persists across 30-frame window
```

**Cross-reference Analysis:**
✓ Channel 1 correctly combines: behavior + thermal + ambient context
✓ Channel 2 correctly combines: population behavior + persistence
✓ THI adaptation prevents false alarms in hot weather
✗ Missing: Thermal sensor FAILURE handling (falls back to 0°C)
✗ Missing: Detailed logging of alert trigger reasoning

### Issues Found

1. **Thermal Sensor Fallback:**
   - If thermal sensor unavailable: zone_temp = 0.0 (not None)
   - Condition `zone_temp > ambient + 2.0` will always fail when temp unavailable
   - Should handle None or use "unavailable" flag

2. **False Positive Risk:**
   - Hot weather + high activity → THI high, all pigs lying → could trigger pop alert
   - Missing: Check if lying is expected in heat stress context

3. **SMS Message Format:**
   - Includes zone temp which may be None or 0
   - Dashboard displays "-" for missing temps (OK)
   - SMS format could be improved

### Fixes Needed
1. Handle thermal sensor unavailability properly
2. Add context to alerts (reason logging)
3. Test with various scenarios

---

## Issue 5: Code Actually Being Executed

### Verification Needed
- [ ] Confirm latest code is in use (no old copies)
- [ ] Verify model file path is correct
- [ ] Check Python environment has all dependencies
- [ ] Ensure changes actually saved in files
- [ ] Run with debug logging to trace execution

### Already Verified ✓
- ONNX model loads correctly
- Config file syntax valid
- Database schema creates successfully
- Flask app starts without errors

---

## Summary of Required Actions

### HIGH PRIORITY (Performance)
- [ ] Increase frame_skip from 2 to 3
- [ ] Add async camera thread
- [ ] Measure new FPS

### MEDIUM PRIORITY (Functionality)
- [ ] Verify behavior labels visible in live output
- [ ] Implement occupancy-based counting (don't recount re-entries)
- [ ] Fix thermal sensor None handling

### LOW PRIORITY (Polish)
- [ ] Improve SMS message formatting
- [ ] Add debug logging for alert triggers
- [ ] Document system limitations

---

## Expected Outcomes After Fixes

**Before:** 14.22 FPS, re-entry duplicates, thermal None handling bugs
**After:**
- ≥ 20 FPS (with frame_skip=3 + async camera)
- Behavior labels visible on all detected pigs
- Occupancy counting (no re-entry duplicates)
- Proper thermal sensor handling
- Clear health indicator logic
