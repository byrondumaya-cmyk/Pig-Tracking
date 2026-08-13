#!/bin/bash
# Restore wlan0 to NetworkManager control after PigMonitor AP mode.

set -euo pipefail

[[ $EUID -eq 0 ]] || { echo "Run as root: sudo $0"; exit 1; }

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CONFIG_FILE="$PROJECT_ROOT/config/config.yaml"

echo "Stopping the PigMonitor access point..."
systemctl disable --now hostapd dnsmasq 2>/dev/null || true

echo "Removing AP-only network configuration..."
rm -f /etc/NetworkManager/conf.d/99-unmanaged-devices.conf
rm -f /etc/network/interfaces.d/wlan0
rm -f /etc/systemd/system/hostapd.service.d/pig-monitor.conf
rm -f /etc/systemd/system/dnsmasq.service.d/pig-monitor.conf
systemctl daemon-reload

if [[ -f "$CONFIG_FILE" ]]; then
    sed -i 's/^  mode: .*/  mode: "lan"/' "$CONFIG_FILE"
fi

if ! systemctl list-unit-files NetworkManager.service --no-legend | grep -q NetworkManager.service; then
    echo "NetworkManager is not installed. Use raspi-config to configure Wi-Fi."
    exit 1
fi

echo "Returning wlan0 to NetworkManager..."
rfkill unblock wifi || true
systemctl enable --now NetworkManager
systemctl restart NetworkManager
sleep 3

nmcli radio wifi on
nmcli device set wlan0 managed yes || true
nmcli device wifi rescan ifname wlan0 || true

echo ""
echo "Available Wi-Fi networks:"
nmcli --fields SSID,SECURITY,SIGNAL device wifi list ifname wlan0
echo ""
echo "Connect with:"
echo "  nmcli device wifi connect 'YOUR_WIFI_NAME' password 'YOUR_WIFI_PASSWORD' ifname wlan0"
