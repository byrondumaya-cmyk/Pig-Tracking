# AP Mode & Networking Guide
# Swine Health Monitor

---

## Overview

The Swine Health Monitor supports two networking modes:

| Mode | When to use | Dashboard URL |
|------|-------------|---------------|
| **AP mode** (Access Point) | Field deployment — no router available | `http://192.168.4.1:5000` |
| **LAN mode** | Lab/development — connected to a router | `http://<Pi-IP>:5000` |

**Important:** These modes are mutually exclusive. The Pi does **not** simultaneously run an AP and connect to an external Wi-Fi network, because sharing the single BCM43455 radio causes AP instability in field conditions.

---

## AP Mode (Field Deployment)

In AP mode, the Pi creates its own Wi-Fi hotspot. Farmers and technicians connect their phone or laptop directly to this hotspot — no router or internet needed.

### Setup (run once after deploying code to the Pi)

```bash
# On the Raspberry Pi terminal:
cd /home/pi/Pig_Tracking

# 1. Edit AP credentials in config first:
nano config/config.yaml
#   → Set network.ap.ssid and network.ap.password

# 2. Run the AP setup script (requires sudo):
chmod +x scripts/setup_ap.sh
sudo scripts/setup_ap.sh
# Follow the prompts. Reboot when asked.
```

### After reboot

1. On your phone/laptop: search for Wi-Fi network **`PigMonitor_AP`** (or your configured SSID).
2. Connect using the password from `config.yaml`.
3. Open a browser and go to: **`http://192.168.4.1:5000`**

### What the script does

The `setup_ap.sh` script:
- Installs `hostapd` and `dnsmasq` (AP daemon + DHCP server)
- Sets a static IP (`192.168.4.1`) on the `wlan0` interface
- Configures DHCP to hand out addresses `192.168.4.10–50` to connecting clients
- Adds a DNS wildcard rule so any domain typed into the browser resolves to the Pi (captive-portal-like behaviour)
- Backs up existing network configuration to `/etc/pig_monitor_backup/`
- Updates `config/config.yaml` to `network.mode: "ap"`

The script is **idempotent** — safe to run multiple times.

---

## LAN Mode (Lab / Development)

In LAN mode, the Pi connects to your router via Ethernet or Wi-Fi credentials. This is the default for development.

### Setup

```bash
# In config/config.yaml:
network:
  mode: "lan"
```

The Pi will use its existing network connection (set up via `raspi-config` or `/etc/wpa_supplicant/wpa_supplicant.conf`).

Find the Pi's IP address:

```bash
# On the Pi:
hostname -I

# Or from your router's device list / mDNS:
ping raspberrypi.local
```

Access the dashboard: `http://<PI_IP>:5000`

---

## Switching Between Modes

### LAN → AP

```bash
sudo scripts/setup_ap.sh
```

### AP → LAN

```bash
# 1. Disable AP services
sudo systemctl disable hostapd dnsmasq
sudo systemctl stop hostapd dnsmasq

# 2. Remove the static IP block from dhcpcd.conf
sudo nano /etc/dhcpcd.conf
# Delete the lines between "# BEGIN pig_monitor_ap" and "# END pig_monitor_ap"

# 3. Update config.yaml
nano config/config.yaml
# Set: network.mode: "lan"

# 4. Reconnect to your router (via raspi-config or wpa_supplicant)
sudo raspi-config
# → System Options → Wireless LAN → enter your router credentials

# 5. Reboot
sudo reboot
```

---

## Recovering Dashboard Access

### Scenario: Forgot AP password / wrong password in config

```bash
# Restore from backup (timestamp shown during setup_ap.sh run):
ls /etc/pig_monitor_backup/
sudo cp /etc/pig_monitor_backup/<timestamp>/hostapd.conf /etc/hostapd/hostapd.conf
sudo systemctl restart hostapd
```

Or re-run `setup_ap.sh` with corrected credentials.

### Scenario: Pi IP unknown (LAN mode)

Connect a monitor + keyboard directly to the Pi and run:

```bash
hostname -I
```

Or connect via Ethernet if Wi-Fi is misconfigured.

---

## Viewing Logs

```bash
# Application logs (real-time):
journalctl -u swine-monitor -f

# Last 100 lines:
journalctl -u swine-monitor -n 100

# AP daemon logs:
journalctl -u hostapd -n 50

# DHCP server logs:
journalctl -u dnsmasq -n 50
```

---

## Known Limitations

- **No simultaneous AP + internet** — the Pi 4B's single radio cannot reliably run both. If internet connectivity is needed (e.g., NTP time sync), temporarily switch to LAN mode.
- **Time sync in AP mode** — use the dashboard's manual time sync feature (`/settings` → System tab → Time Sync). The browser-to-Pi time sync endpoint (`/api/time_sync`) handles this without internet.
- **Channel selection** — AP defaults to channel 7 (2.4 GHz). If local interference is a problem, edit `/etc/hostapd/hostapd.conf` → `channel=<1-13>` and restart `hostapd`.
