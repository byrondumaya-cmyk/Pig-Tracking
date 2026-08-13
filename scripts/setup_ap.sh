#!/bin/bash
# scripts/setup_ap.sh
# Configures the Raspberry Pi as a Wi-Fi Access Point using hostapd & dnsmasq.
# This explicitly BYPASSES NetworkManager to avoid known wpa_supplicant bugs on Bookworm.

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

info()  { echo -e "  ${GREEN}[INFO]${NC}  $1"; }
warn()  { echo -e "  ${YELLOW}[WARN]${NC}  $1"; }
error() { echo -e "  ${RED}[ERROR]${NC} $1"; exit 1; }
section() { echo ""; echo -e "${CYAN}━━━ $1 ━━━${NC}"; }

[[ $EUID -ne 0 ]] && error "Run as root: sudo $0"

# ── Locate project + config ───────────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
CONFIG_FILE="$PROJECT_ROOT/config/config.yaml"

[[ -f "$CONFIG_FILE" ]] || error "config.yaml not found at $CONFIG_FILE"

# ── Parse SSID + password from config.yaml ────────────────────────────────────
AP_SSID=$(grep -A5 'ap:' "$CONFIG_FILE" | grep 'ssid:' | head -1 | sed "s/.*ssid: *['\"]*//" | sed "s/['\"].*//")
AP_PASS=$(grep -A5 'ap:' "$CONFIG_FILE" | grep 'password:' | head -1 | sed "s/.*password: *['\"]*//" | sed "s/['\"].*//")
AP_IP=$(grep -A5 'ap:' "$CONFIG_FILE" | grep 'ip:' | head -1 | sed "s/.*ip: *['\"]*//" | sed "s/['\"].*//")

AP_SSID="${AP_SSID:-PigMonitor_AP}"
AP_PASS="${AP_PASS:-CHANGE_ME}"
AP_IP="${AP_IP:-192.168.4.1}"
DHCP_START="192.168.4.10"
DHCP_END="192.168.4.50"

# Safety check on default password
if [[ "$AP_PASS" == "CHANGE_ME" || -z "$AP_PASS" ]]; then
    warn "AP password is not securely set."
    warn "Edit config/config.yaml → network.ap.password before deploying."
    read -rp "Continue anyway? (y/N): " CONTINUE
    [[ "$CONTINUE" =~ ^[Yy]$ ]] || { info "Aborted."; exit 0; }
fi

section "Configuration (Hostapd/Legacy Stack)"
info "SSID     : $AP_SSID"
info "Password : [set in config.yaml]"
info "AP IP    : $AP_IP"
info "DHCP     : $DHCP_START – $DHCP_END"

echo ""
read -rp "Apply these settings? (y/N): " APPLY
if [[ ! "$APPLY" =~ ^[Yy]$ ]]; then
    info "Setup aborted."
    exit 0
fi

# ── Set Wi-Fi Country Code (Critical for hostapd) ───────────────────────────
section "Setting Wi-Fi Country Code"
if command -v raspi-config &> /dev/null; then
    raspi-config nonint do_wifi_country US
    info "Country code set to US (maximizes channel compatibility)."
else
    warn "raspi-config not found, skipping country code."
fi

# ── Install hostapd, dnsmasq, and ifupdown ──────────────────────────────────
section "Installing required packages"
export DEBIAN_FRONTEND=noninteractive
# Wait for apt lock if running in background
while fuser /var/lib/dpkg/lock-frontend >/dev/null 2>&1; do
    warn "Waiting for other apt-get process to finish..."
    sleep 5
done

apt-get update -qq
apt-get install -y hostapd dnsmasq ifupdown

# Stop them while we configure
systemctl stop hostapd || true
systemctl stop dnsmasq || true

# ── Unmanage wlan0 from NetworkManager ──────────────────────────────────────
section "Bypassing NetworkManager for wlan0"
if systemctl is-active --quiet NetworkManager; then
    # Delete any existing PigMonitor_AP connections to prevent conflicts
    if nmcli con show "PigMonitor_AP" &> /dev/null; then
        nmcli con delete "PigMonitor_AP" || true
        info "Removed old NetworkManager AP profile."
    fi

    mkdir -p /etc/NetworkManager/conf.d
    cat > /etc/NetworkManager/conf.d/99-unmanaged-devices.conf <<EOF
[keyfile]
unmanaged-devices=interface-name:wlan0
EOF
    info "Created /etc/NetworkManager/conf.d/99-unmanaged-devices.conf"
    systemctl restart NetworkManager
    sleep 3
fi

# ── Configure Static IP ─────────────────────────────────────────────────────
section "Configuring Static IP"
rfkill unblock wifi || true

mkdir -p /etc/network/interfaces.d
cat > /etc/network/interfaces.d/wlan0 <<EOF
allow-hotplug wlan0
iface wlan0 inet static
    address $AP_IP
    netmask 255.255.255.0
EOF
info "Static IP configured in /etc/network/interfaces.d/wlan0"

# ── Configure hostapd ───────────────────────────────────────────────────────
section "Configuring Hostapd"
cat > /etc/hostapd/hostapd.conf <<EOF
interface=wlan0
driver=nl80211
ssid=$AP_SSID
hw_mode=g
channel=6
macaddr_acl=0
auth_algs=1
ignore_broadcast_ssid=0
wpa=2
wpa_passphrase=$AP_PASS
wpa_key_mgmt=WPA-PSK
wpa_pairwise=CCMP
rsn_pairwise=CCMP
EOF
info "hostapd.conf written."

# Point default hostapd to our conf
sed -i 's|^#DAEMON_CONF=.*|DAEMON_CONF="/etc/hostapd/hostapd.conf"|' /etc/default/hostapd || echo 'DAEMON_CONF="/etc/hostapd/hostapd.conf"' >> /etc/default/hostapd

# ── Configure dnsmasq ───────────────────────────────────────────────────────
section "Configuring Dnsmasq"
mv /etc/dnsmasq.conf /etc/dnsmasq.conf.orig 2>/dev/null || true
cat > /etc/dnsmasq.conf <<EOF
interface=wlan0
bind-interfaces
server=8.8.8.8
domain-needed
bogus-priv
dhcp-range=$DHCP_START,$DHCP_END,255.255.255.0,24h
address=/#/$AP_IP
EOF
info "dnsmasq.conf written."

# ── Enable Services ─────────────────────────────────────────────────────────
section "Enabling Services"
systemctl unmask hostapd || true
systemctl enable hostapd dnsmasq

# ── Update config.yaml to use ap mode ───────────────────────────────────────
section "Updating config.yaml network mode to 'ap'"
sed -i "s/^  mode: .*/  mode: \"ap\"/" "$CONFIG_FILE"
info "config.yaml → network.mode = ap"

section "Summary"
echo ""
echo -e "  ${GREEN}✓${NC} Hostapd AP Mode Configuration Applied"
echo -e "  ${GREEN}✓${NC} SSID        : $AP_SSID"
echo -e "  ${GREEN}✓${NC} Password    : $AP_PASS"
echo -e "  ${GREEN}✓${NC} Dashboard   : http://$AP_IP:5000 (after reboot)"
echo ""
warn "A REBOOT IS REQUIRED for changes to take effect reliably."
read -rp "Reboot now? (y/N): " REBOOT
if [[ "$REBOOT" =~ ^[Yy]$ ]]; then
    info "Rebooting in 3 seconds..."
    sleep 3
    reboot
else
    info "Reboot manually when ready: sudo reboot"
fi
