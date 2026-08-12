3# Raspberry Pi Deployment Tracker
*Swine Health Monitoring System*

This tracker is designed for you to follow along as we move from the PC development environment to the physical Raspberry Pi hardware.

## Phase 7: Hardware & OS Setup
*Objective: Get the Raspberry Pi running and connected.*

- [ ] **Step 1: Flash the OS**
  - Download [Raspberry Pi Imager](https://www.raspberrypi.com/software/).
  - Select **Raspberry Pi OS (64-bit)** (Bookworm).
  - Select your MicroSD card and write the image.
  - *Tip: Use the advanced settings (gear icon) in the Imager to set your WiFi credentials and enable SSH so you can access it headlessly.*

- [ ] **Step 2: Connect Hardware**
  - Insert the flashed MicroSD card into the Pi.
  - Connect the USB Webcam to any USB 3.0 (blue) port.
  - Wire the **AMG8833 Thermal Camera**:
    - VIN → 3.3V (Pin 1)
    - GND → GND (Pin 6)
    - SDA → GPIO2 / SDA1 (Pin 3)
    - SCL → GPIO3 / SCL1 (Pin 5)
  - Wire the **DHT22 Sensor**:
    - VCC → 3.3V or 5V
    - GND → GND
    - DATA → GPIO4 (Pin 7) - *Requires a 10k pull-up resistor to VCC if not on a breakout board.*
  - Wire the **GSM900A Module**:
    - TX → RXD / GPIO15 (Pin 10)
    - RX → TXD / GPIO14 (Pin 8)
    - GND → GND
    - *Note: Power the GSM module externally or ensure your Pi power supply can handle the 2A peak current bursts.*
  - Power on the Raspberry Pi.

## Phase 8: Software Deployment
*Objective: Move our completed code to the Pi and install dependencies.*

- [ ] **Step 1: Transfer Files**
  - Copy the `Pig_Tracking` folder (excluding `datasets/`, `runs/`, and `.venv/`) from your PC to the Raspberry Pi. You can use a USB drive, `scp`, or GitHub.
  
- [ ] **Step 2: Enable Hardware Interfaces**
  - Open a terminal on the Pi and run: `sudo raspi-config`
  - Go to **Interface Options**.
  - Enable **I2C** (for the thermal camera).
  - Enable **Serial Port** (for the GSM module). Disable the login shell over serial, but enable the serial port hardware.
  - Reboot the Pi.

- [ ] **Step 3: Setup Python Environment**
  - Navigate to the project folder: `cd Pig_Tracking`
  - Create a virtual environment: `python3 -m venv .venv`
  - Activate it: `source .venv/bin/activate`
  - Install dependencies: `pip install -r requirements-pi.txt`
  - *Note: ONNX Runtime and OpenCV on the Pi might take a moment to install.*

## Phase 9: Testing & Optimization
*Objective: Verify everything works together.*

- [ ] **Step 1: Test Sensors Individually**
  - Verify I2C is working: `i2cdetect -y 1` (You should see `69` for the AMG8833).
  - Run the main system in debug mode: `python src/main.py --debug`
  
- [ ] **Step 2: Test the Dashboard**
  - Open a web browser on a device connected to the same network.
  - Navigate to `http://<RASPBERRY_PI_IP>:5000`.
  - Check if the video feed is running and sensors are updating.
  
- [ ] **Step 3: Optimize (If needed)**
  - If the FPS is too low, we will edit `config/config.yaml` to increase `frame_skip` or adjust ONNX `intra_op_threads`.

## Phase 10: Standalone Setup (AP Mode)
*Objective: Make the Pi broadcast its own WiFi network for the farm.*

- [ ] **Step 1: Configure hostapd & dnsmasq**
  - Set up the Pi as an Access Point so you can connect your phone directly to `PigMonitor_AP` without needing a router.
  - *We will do this via terminal commands once the base system is verified.*
  
- [ ] **Step 2: Enable Auto-Start**
  - Create a `systemd` service to run `src/main.py` automatically whenever the Pi is plugged in.
