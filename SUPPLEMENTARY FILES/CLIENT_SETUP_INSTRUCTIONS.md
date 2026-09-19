# Pig Tracking — Client Setup Guide

Welcome to the **Pig Tracking System**! This guide covers how to connect to the system and use both the mobile app and the web dashboard.

> For credentials (WiFi password, dashboard password), see **[credentials.md](../credentials.md)** in the project root.

---

## Option A — Mobile App (Recommended for farmers)

### Step 1: Connect to the Pi's WiFi

1. On your Android phone, go to **Settings → WiFi**
2. Connect to: **`PigDashboard`**
3. Password: **`PigDashboard2026!`**

### Step 2: Install the App

Open your phone browser and go to:
```
https://github.com/byrondumaya-cmyk/Pig-Tracking/releases/latest/download/app-release.apk
```
Tap the downloaded file to install. If prompted, enable **"Install from unknown sources"**.

### Step 3: Connect the App to the Pi

1. Open **Pig Tracking** app
2. Enter the IP: **`192.168.4.1`**
3. Tap **Connect**
4. You will see the live pig detection feed and thermal overlay

---

## Option B — Web Dashboard (Browser)

### Step 1: Connect to the Pi's WiFi

Same as above — connect to `PigDashboard` with password `PigDashboard2026!`.

### Step 2: Open the Dashboard

Open any browser and go to:
```
http://192.168.4.1:5000
```

The dashboard shows:
- Live annotated YOLO feed (left panel)
- MLX90640 thermal heatmap (right panel)
- Real-time SMS alert log
- Ambient DHT22 temperature and humidity

### Step 3: Access Settings (Developer)

Click **Settings** in the dashboard. Enter the developer password:
```
PigDashboard2026!
```

From here you can adjust:
- GSM phone numbers for SMS alerts
- Alert cooldown timers
- Temperature thresholds
- Behavior detection confidence

---

## Option C — LAN Mode (Same router)

If the Pi is connected to the same router as your device (not in AP mode):

1. Find the Pi's IP address by running on the Pi: `hostname -I`
2. Open browser → `http://[pi-ip]:5000`
3. For the mobile app → enter `[pi-ip]` in the Connect screen

---

## Troubleshooting

| Problem | Solution |
|---------|---------|
| Can't find `PigDashboard` WiFi | Make sure `swine-monitor.service` is running on the Pi. SSH in and run `sudo systemctl status swine-monitor.service` |
| App can't connect | Confirm you are on the `PigDashboard` network, not your home WiFi |
| Dashboard not loading | Pi may be starting up — wait 30 seconds and refresh |
| No video feed in app | The TFLite model file (`best.tflite`) must be in `mobile_app/assets/` |
| SMS alerts not sending | Check GSM module UART connection; verify phone number in Settings |

---

## Raspberry Pi Management (Admin only)

SSH into the Pi:
```bash
ssh pigtracking@192.168.4.1
```

Common commands:
```bash
# Check service status
sudo systemctl status swine-monitor.service

# Restart the service
sudo systemctl restart swine-monitor.service

# View live logs
sudo journalctl -fu swine-monitor.service

# Pull latest code updates
cd ~/Pig_Tracking && git pull origin main
sudo systemctl restart swine-monitor.service
```
