# MLX90640 Thermal Camera Upgrade

## Goal
Update the thermal camera to the MLX90640 (32x24 grid) and display the temperature reading on the pig bounding boxes in the live video stream.

## Tasks
- [ ] Task 1: Update `requirements-pi.txt` → Verify: `adafruit-circuitpython-mlx90640` is present.
- [ ] Task 2: Update `config/config.yaml` → Verify: `thermal.i2c_address` is `0x33`, `zone_cols` is 32, `zone_rows` is 24.
- [ ] Task 3: Rewrite `src/thermal/thermal_reader.py` → Verify: `MLX90640Reader` fetches 24x32 grid and simulation works.
- [ ] Task 4: Update `src/thermal/thermal_mapper.py` → Verify: Grid dimensions are dynamically pulled from `thermal_grid.shape` instead of hardcoded 8x8.
- [ ] Task 5: Pass temperature map to stream buffer in `src/main.py` → Verify: `FrameBuffer.update` receives `temperature_map`.
- [ ] Task 6: Draw temperature on bounding boxes in `src/dashboard/stream.py` → Verify: `_annotate_frame` labels show temperature (e.g., `38.5C`).

## Done When
- [ ] The dashboard stream successfully displays bounding boxes with track ID, behavior, confidence, AND temperature.
- [ ] The system does not crash when processing the larger 24x32 thermal grid.

## Notes
- Needs clarification on the exact I2C address, FOV mapping differences, and optimal refresh rate for the MLX90640 sensor.
