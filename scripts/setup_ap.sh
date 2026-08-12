#!/usr/bin/env bash
# =============================================================================
# scripts/setup_ap.sh
# Idempotent Access Point (AP) mode setup for Raspberry Pi 4B
#
# Run ONCE on the Raspberry Pi when deploying in field/AP mode.
# Safe to re-run — backs up existing configs before overwriting.
#
# Usage:
#   chmod +x scripts/setup_ap.sh
#   sudo ./scripts/setup_ap.sh
#
# After running:
#   - Pi broadcasts WiFi SSID from config/config.yaml
#   - Dashboard accessible at http://192.168.4.1:5000
#   - Connect phone/laptop to the AP SSID, then open the URL above
#
# To UNDO: restore from /etc/pig_monitor_backup/ and reboot.
# =============================================================================

set -euo pipefail

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; CYAN='\033[0;36m'; NC='\033[0m'
info()    { echo -e "${GREEN}[INFO]${NC}  $*"; }
warn()    { echo -e "${YELLOW}[WARN]${NC}  $*"; }
error()   { echo -e "${RED}[ERROR]${NC} $*"; exit 1; }
section() { echo -e "\n${CYAN}━━━ $* ━━━${NC}"; }

# ── Must be root ──────────────────────────────────────────────────────────────
[[ $EUID -ne 0 ]] && error "Run as root: sudo $0"

# ── Locate project + config ───────────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
CONFIG_FILE="$PROJECT_ROOT/config/config.yaml"

[[ -f "$CONFIG_FILE" ]] || error "config.yaml not found at $CONFIG_FILE"

# ── Parse SSID + password from config.yaml (simple grep/sed — no python needed)
AP_SSID=$(grep -A5 'ap:' "$CONFIG_FILE" | grep 'ssid:' | head -1 | sed "s/.*ssid: *['\"]*//" | sed "s/['\"].*//")
AP_PASS=$(grep -A5 'ap:' "$CONFIG_FILE" | grep 'password:' | head -1 | sed "s/.*password: *['\"]*//" | sed "s/['\"].*//")
AP_IP=$(grep -A5 'ap:' "$CONFIG_FILE" | grep 'ip:' | head -1 | sed "s/.*ip: *['\"]*//" | sed "s/['\"].*//")

AP_SSID="${AP_SSID:-PigMonitor_AP}"
AP_PASS="${AP_PASS:-CHANGE_ME}"
AP_IP="${AP_IP:-192.168.4.1}"
DHCP_START="192.168.4.10"
DHCP_END="192.168.4.50"

# Safety check on default password
if [[ "$AP_PASS" == "CHANGE_ME" ]]; then
    warn "AP password is still 'CHANGE_ME'."
    warn "Edit config/config.yaml → network.ap.password before deploying."
    read -rp "Continue anyway? (y/N): " CONTINUE
    [[ "$CONTINUE" =~ ^[Yy]$ ]] || { info "Aborted."; exit 0; }
fi

section "Configuration"
info "SSID     : $AP_SSID"
info "Password : [set in config.yaml]"
info "AP IP    : $AP_IP"
info "DHCP     : $DHCP_START – $DHCP_END"
echo ""
read -rp "Apply these settings? (y/N): " CONFIRM
[[ "$CONFIRM" =~ ^[Yy]$ ]] || { info "Aborted."; exit 0; }

# ── Backup existing configs ───────────────────────────────────────────────────
section "Backing up existing network configs"
BACKUP_DIR="/etc/pig_monitor_backup/$(date +%Y%m%d_%H%M%S)"
mkdir -p "$BACKUP_DIR"
for f in /etc/dhcpcd.conf /etc/hostapd/hostapd.conf /etc/dnsmasq.conf /etc/default/hostapd; do
    [[ -f "$f" ]] && cp "$f" "$BACKUP_DIR/" && info "Backed up $f"
done
info "Backups saved to $BACKUP_DIR"

# ── Install hostapd + dnsmasq ─────────────────────────────────────────────────
section "Installing hostapd and dnsmasq"
apt-get update -qq
apt-get install -y hostapd dnsmasq
systemctl stop hostapd dnsmasq 2>/dev/null || true

# ── Configure static IP for wlan0 (via dhcpcd) ───────────────────────────────
section "Configuring static IP on wlan0"
DHCPCD_CONF="/etc/dhcpcd.conf"
# Remove any existing pig_monitor block
sed -i '/# BEGIN pig_monitor_ap/,/# END pig_monitor_ap/d' "$DHCPCD_CONF"
cat >> "$DHCPCD_CONF" <<EOF

# BEGIN pig_monitor_ap — managed by scripts/setup_ap.sh
interface wlan0
    static ip_address=${AP_IP}/24
    nohook wpa_supplicant
# END pig_monitor_ap
EOF
info "dhcpcd.conf updated with static $AP_IP on wlan0"

# ── Configure hostapd ─────────────────────────────────────────────────────────
section "Writing hostapd configuration"
mkdir -p /etc/hostapd
cat > /etc/hostapd/hostapd.conf <<EOF
# Managed by scripts/setup_ap.sh — Swine Health Monitor AP
interface=wlan0
driver=nl80211
ssid=${AP_SSID}
hw_mode=g
channel=7
ieee80211n=1
wmm_enabled=0
macaddr_acl=0
auth_algs=1
ignore_broadcast_ssid=0
wpa=2
wpa_passphrase=${AP_PASS}
wpa_key_mgmt=WPA-PSK
wpa_pairwise=TKIP
rsn_pairwise=CCMP
EOF

# Point /etc/default/hostapd to the config
sed -i 's|#DAEMON_CONF=.*|DAEMON_CONF="/etc/hostapd/hostapd.conf"|' /etc/default/hostapd
info "hostapd configured for SSID: $AP_SSID"

# ── Configure dnsmasq (DHCP server) ──────────────────────────────────────────
section "Writing dnsmasq configuration"
# Preserve existing dnsmasq.conf if it has other entries
DNSMASQ_CONF="/etc/dnsmasq.conf"
sed -i '/# BEGIN pig_monitor_ap/,/# END pig_monitor_ap/d' "$DNSMASQ_CONF"
cat >> "$DNSMASQ_CONF" <<EOF

# BEGIN pig_monitor_ap — managed by scripts/setup_ap.sh
interface=wlan0
dhcp-range=${DHCP_START},${DHCP_END},255.255.255.0,24h
# Captive portal redirect: send all DNS to the dashboard IP
address=/#/${AP_IP}
# END pig_monitor_ap
EOF
info "dnsmasq configured: DHCP $DHCP_START–$DHCP_END, all DNS → $AP_IP"

# ── Update config.yaml to use ap mode ────────────────────────────────────────
section "Updating config.yaml network mode to 'ap'"
sed -i "s/^  mode: .*/  mode: \"ap\"/" "$CONFIG_FILE"
info "config.yaml → network.mode = ap"

# ── Enable services ───────────────────────────────────────────────────────────
section "Enabling services"
systemctl unmask hostapd
systemctl enable hostapd dnsmasq
info "hostapd and dnsmasq enabled."

section "Summary"
echo ""
echo -e "  ${GREEN}✓${NC} Static IP   : wlan0 = $AP_IP"
echo -e "  ${GREEN}✓${NC} SSID        : $AP_SSID"
echo -e "  ${GREEN}✓${NC} DHCP range  : $DHCP_START – $DHCP_END"
echo -e "  ${GREEN}✓${NC} Dashboard   : http://$AP_IP:5000 (after reboot)"
echo ""
warn "A REBOOT IS REQUIRED for changes to take effect."
read -rp "Reboot now? (y/N): " REBOOT
if [[ "$REBOOT" =~ ^[Yy]$ ]]; then
    info "Rebooting in 3 seconds..."
    sleep 3
    reboot
else
    info "Reboot manually when ready: sudo reboot"
fi
