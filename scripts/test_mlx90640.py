#!/usr/bin/env python3
"""
Test script for the MLX90640 thermal camera.
Run this on the Raspberry Pi to verify hardware wiring and data acquisition.
"""

import time
import board
import busio
import adafruit_mlx90640

def main():
    print("Initializing I2C bus...")
    try:
        i2c = busio.I2C(board.SCL, board.SDA, frequency=400000)
    except Exception as e:
        print(f"Failed to initialize I2C: {e}")
        return

    print("Connecting to MLX90640...")
    try:
        mlx = adafruit_mlx90640.MLX90640(i2c)
        print("MLX90640 found!")
        print(f"Serial number: {mlx.serial_number}")
        
        # We set the refresh rate. MLX90640 supports up to 64Hz, 
        # but 4Hz, 8Hz or 16Hz is usually stable on Pi.
        mlx.refresh_rate = adafruit_mlx90640.RefreshRate.REFRESH_8_HZ
        print(f"Refresh rate set to: {mlx.refresh_rate}")
    except Exception as e:
        print(f"Failed to connect to MLX90640: {e}")
        return

    print("\nReading thermal frames (Ctrl+C to exit)...")
    frame = [0] * 768 # 32 x 24 = 768
    
    try:
        while True:
            try:
                mlx.getFrame(frame)
                min_temp = min(frame)
                max_temp = max(frame)
                avg_temp = sum(frame) / len(frame)
                # Center pixel (row 12, col 16 -> index 12 * 32 + 16)
                center_temp = frame[12 * 32 + 16]
                
                print(f"Min: {min_temp:.1f}°C | Max: {max_temp:.1f}°C | Avg: {avg_temp:.1f}°C | Center: {center_temp:.1f}°C")
            except ValueError:
                # these happen sometimes when reading, just retry
                pass
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nExiting.")

if __name__ == "__main__":
    main()
