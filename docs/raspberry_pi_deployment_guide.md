# Raspberry Pi Deployment Guide

This guide walks through deploying the Pig Tracking system on a Raspberry Pi 4 running Raspberry Pi OS Bookworm (64-bit). It includes the exact commands to run on the Pi.

## 1. Prepare the Raspberry Pi OS

1. Flash Raspberry Pi OS Bookworm 64-bit to your SD card.
2. Boot the Pi and connect via HDMI/keyboard or SSH.
3. Update the system:

```bash
sudo apt update && sudo apt upgrade -y
```

4. Install required OS packages:

```bash
sudo apt install python3-pip python3-venv libopenblas-dev python3-smbus i2c-tools libatlas-base-dev libavcodec-dev libavformat-dev libswscale-dev -y
```

## 2. Enable Raspberry Pi hardware interfaces

1. Open raspi-config:

```bash
sudo raspi-config
```

2. Enable these interfaces:
- Interface Options → I2C → Enable
- Interface Options → Serial Port → Enable serial port hardware, disable login shell over serial

3. Reboot the Pi:

```bash
sudo reboot
```

## 3. Verify I2C device connectivity

After reboot, check that the AMG8833 thermal camera is visible on I2C bus 1:

```bash
i2cdetect -y 1
```

You should see `0x69` in the scan output.

## 4. Clone the repository to the Pi (preferred over USB transfer)

On the Pi, use Git to pull the repo directly. This is the preferred method instead of copying files by USB drive.

```bash
cd ~
rm -rf Pig_Tracking
git clone https://github.com/byrondumaya-cmyk/Pig-Tracking.git Pig_Tracking
cd Pig_Tracking
```

Note: `models/best.onnx` is now tracked in Git, so it should be present after a fresh clone or `git pull`.

If the file is still missing after cloning, refresh the branch and retry the clone.

## 5. Create and activate the Python environment

```bash
python3 -m venv venv
source venv/bin/activate
```

## 6. Install Python runtime dependencies

```bash
pip install -r requirements-pi.txt
```

## 7. Confirm model file and config

1. Confirm the ONNX model exists:

```bash
ls models/best.onnx
```

2. Confirm `config/config.yaml` contains the correct runtime settings:

```bash
grep -n "network:" -n config/config.yaml
grep -n "model_path:" -n config/config.yaml
```

3. Ensure the model path points to ONNX:

```yaml
inference:
  model_path: "models/best.onnx"
```

4. If you want AP mode, set:

```yaml
network:
  mode: "ap"
  ap:
    ssid: "PigMonitor_AP"
    password: "pigmonitor123"
    ip: "192.168.4.1"
    subnet: "192.168.4.0/24"
```

> Do not commit a real production password into source control.

## 8. Install AP-mode packages (optional)

If you want the Pi to act as its own WiFi hotspot, install these packages:

```bash
sudo apt install hostapd dnsmasq -y
```

### 8.1 Configure static IP for AP mode

Edit `/etc/dhcpcd.conf` and add:

```ini
interface wlan0
    static ip_address=192.168.4.1/24
    nohook wpa_supplicant
```

### 8.2 Create `/etc/hostapd/hostapd.conf`

```ini
interface=wlan0
ssid=PigMonitor_AP
hw_mode=g
channel=6
wmm_enabled=1
macaddr_acl=0
auth_algs=1
ignore_broadcast_ssid=0
wpa=2
wpa_passphrase=pigmonitor123
wpa_key_mgmt=WPA-PSK
wpa_pairwise=TKIP
rsn_pairwise=CCMP
```

Then set the daemon config path in `/etc/default/hostapd`:

```bash
sudo sed -i 's|#DAEMON_CONF=""|DAEMON_CONF="/etc/hostapd/hostapd.conf"|' /etc/default/hostapd
```

### 8.3 Configure `/etc/dnsmasq.conf`

Add these lines at the end of the file:

```ini
interface=wlan0
dhcp-range=192.168.4.2,192.168.4.20,255.255.255.0,24h
```

### 8.4 Start AP services

```bash
sudo systemctl unmask hostapd
sudo systemctl enable hostapd
sudo systemctl enable dnsmasq
sudo systemctl restart dhcpcd
sudo systemctl restart hostapd
sudo systemctl restart dnsmasq
```

> Note: On a Raspberry Pi with a single wireless radio, `wlan0` normally cannot act as both a Wi-Fi client and a hotspot at the same time. Switching `wlan0` into AP mode will drop any existing Wi-Fi client connection. If you need remote access while the Pi is in AP mode, use Ethernet or a second USB Wi-Fi adapter.
>
> The automatic app service is separate from AP mode. Create and enable the service after your network mode is configured and working. It does not need to be done before configuring `hostapd`/`dnsmasq`.

## 9. Run the Pig Tracking app

With the virtual environment active:

```bash
cd ~/Pig_Tracking
source venv/bin/activate
python3 src/main.py
```

If you want to disable the thermal sensor while testing, use:

```bash
python3 src/main.py --no-thermal
```

### 9.1 Runtime logs and tracking semantics

- The app stores runtime data in `data/swine_health.db`.
- The SQLite database contains:
  - `detections` — every tracked detection, including `track_id`, `behavior`, `confidence`, and bounding box coordinates.
  - `pen_alerts` — alert events, trigger reason, ambient/thermal context, and resolution state.
- These are the primary runtime logs for behavior analytics and alert history.
- The app does not create a separate file-based log by default; runtime messages are written to stdout/stderr.
  - If you run the app directly, monitor the terminal output.
  - If you run it as a service, follow the service logs with:

```bash
sudo journalctl -u pig_tracking.service -f
```
- For more verbose diagnostics, start the app with debug logging:

```bash
python3 src/main.py --debug
```

> Note: Track IDs shown in the dashboard (for example `#5 lying`) are temporary SORT tracker IDs for the current session only. If a pig leaves the camera frame and later re-enters, it may receive a new track ID. This is expected behavior for this tracker design and does not necessarily mean the system has detected a different animal.

## 10. Access the dashboard

- If using LAN mode: open `http://<pi-ip>:5000`
- If using AP mode: connect to `PigMonitor_AP` and open `http://192.168.4.1:5000`

## 11. Verify the live feed and status

From any device connected to the network, open the dashboard and confirm:
- live camera stream is visible on `/video_feed`
- thermal grid updates on `/api/thermal_feed`
- behavior counts update on `/api/behavior_counts`
- system status shows `network_mode` and AP metadata

## 12. Notes on models

- Use `models/best.onnx` on the Pi.
- `best.pt` is for training and export only.
- The Pi runtime uses ONNX Runtime and will not use `best.pt` for live inference.
- The trained ONNX file is excluded from Git in this repository, so a fresh clone may not include it. Copy `models/best.onnx` manually if it is not present.

## 13. Performance tuning

The Pi can improve frame throughput by reducing image size and processing fewer frames. Do not disable thermal or DHT sensors unless you are explicitly testing a sensor-free mode; keep them enabled for the full system functionality.

### Recommended tuning presets

1. Balanced throughput

```yaml
camera:
  width: 320
  height: 240
  fps: 30

inference:
  input_size: 320
  frame_skip: 2
```

- Best for stable live video on Raspberry Pi 4.
- Keeps the thermal and ambient sensors active.
- Processes every other frame to reduce CPU load.

2. Performance-first

```yaml
camera:
  width: 320
  height: 240
  fps: 30

inference:
  input_size: 256
  frame_skip: 3
```

- Lower resolution and smaller model input for maximum speed.
- Use this when the app struggles to keep up with real-time inference.

3. Quality-first

```yaml
camera:
  width: 640
  height: 480
  fps: 20

inference:
  input_size: 640
  frame_skip: 1
```

- Higher image quality and more accurate detections.
- Use this when you have enough CPU headroom and want the best visual output.

### How to apply tuning

1. Edit `config/config.yaml`.
2. Update the `camera` and `inference` sections with one of the presets above.
3. Restart the app:

```bash
cd ~/Pig_Tracking
source venv/bin/activate
python3 src/main.py
```

### What affects FPS most

- Camera resolution and model input size are the biggest factors.
- `frame_skip` reduces how often the app performs inference.
- The app’s actual dashboard update rate depends on the full inference loop, not only the camera FPS.

## 14. Optional: Automatic service start

Later, you can create a systemd service to launch the app automatically at boot. This service is independent of AP mode and should be enabled after the Pi network mode is configured.

Create `/etc/systemd/system/pig_tracking.service` with:

```ini
[Unit]
Description=Pig Tracking Dashboard
After=network.target

[Service]
Type=simple
User=pi
WorkingDirectory=/home/pi/Pig_Tracking
ExecStart=/home/pi/Pig_Tracking/venv/bin/python3 /home/pi/Pig_Tracking/src/main.py
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

Then enable and start it:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now pig_tracking.service
sudo systemctl status pig_tracking.service
```

If you want to follow live startup logs:

```bash
sudo journalctl -u pig_tracking.service -f
```

If you later switch the Pi back to normal Wi-Fi client mode from AP mode, the service can remain enabled. It will start the app after boot once the network is configured.
