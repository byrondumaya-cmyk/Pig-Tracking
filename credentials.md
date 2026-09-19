# 🔐 Pig Tracking System — Credentials & Access Reference
> **PRIVATE — Do not share or commit this file publicly.**
> All credentials below are sourced from `config/config.yaml`.

---

## 📶 WiFi Access Point (AP Mode)

The Raspberry Pi broadcasts its own WiFi hotspot when in AP mode.

| Field | Value |
|-------|-------|
| **Network Name (SSID)** | `PigDashboard` |
| **Password** | `PigDashboard2026!` |
| **Pi IP (after connecting)** | `192.168.4.1` |
| **Subnet** | `192.168.4.0/24` |
| **Country Code** | `PH` |

> 📱 **How to connect:** Go to your phone/laptop's WiFi settings → find `PigDashboard` → enter password → open browser → go to `http://192.168.4.1:5000`

---

## 🌐 Flask Web Dashboard

Accessible via browser on any device connected to the Pi's network.

| Field | Value |
|-------|-------|
| **URL (AP Mode)** | `http://192.168.4.1:5000` |
| **URL (LAN Mode)** | `http://[pi-local-ip]:5000` |
| **Developer Password** | `PigDashboard2026!` |
| **Port** | `5000` |

> 💡 The developer password is required to access the **Settings** page where you can edit thresholds, GSM numbers, and system parameters live without restarting the Pi.

---

## 📱 Mobile App (Pig Tracking)

| Field | Value |
|-------|-------|
| **App Name** | `Pig Tracking` |
| **Download Link** | `https://github.com/byrondumaya-cmyk/Pig-Tracking/releases/latest/download/app-release.apk` |
| **WebSocket IP (AP Mode)** | `192.168.4.1` |
| **WebSocket IP (LAN Mode)** | `[pi-local-ip]` |
| **WebSocket Port** | `8765` |

> 📲 **How to use:** Install APK → open app → enter Pi IP → tap Connect.

---

## 🖥️ Raspberry Pi SSH Access

| Field | Value |
|-------|-------|
| **Hostname** | `raspi` |
| **Username** | `pigtracking` |
| **SSH command (LAN)** | `ssh pigtracking@[pi-local-ip]` |
| **Project directory** | `/home/pigtracking/Pig_Tracking` |
| **Virtual environment** | `~/pig_venv` |

---

## ⚙️ Service Management (Pi Terminal)

```bash
# Start/stop/restart the monitoring service
sudo systemctl start swine-monitor.service
sudo systemctl stop swine-monitor.service
sudo systemctl restart swine-monitor.service

# View live logs
sudo journalctl -fu swine-monitor.service

# Check status
sudo systemctl status swine-monitor.service
```

---

## 🔑 Changing Credentials

All credentials live in **`config/config.yaml`**:

```yaml
dashboard:
  developer_password: "PigDashboard2026!"   # ← Change this

network:
  ap:
    ssid: "PigDashboard"               # ← Change this
    password: "PigDashboard2026!"          # ← Change this
```

After editing `config.yaml`, restart the service on the Pi:
```bash
sudo systemctl restart swine-monitor.service
```

---

> ⚠️ **Security Note:** These are default credentials intended for a closed, offline farm network. If you ever connect the Pi to the public internet, change all passwords immediately.
