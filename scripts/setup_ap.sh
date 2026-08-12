#!/usr/bin/env bash
# =============================================================================
# scripts/setup_ap.sh
# Idempotent Access Point (AP) mode setup for Raspberry Pi (Bullseye & Bookworm)
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
chmod 700 "$BACKUP_DIR" # Security: Protect backed-up passwords
for f in /etc/dhcpcd.conf /etc/hostapd/hostapd.conf /etc/dnsmasq.conf /etc/default/hostapd; do
    [[ -f "$f" ]] && cp "$f" "$BACKUP_DIR/" && info "Backed up $f"
done
info "Backups saved to $BACKUP_DIR"

# ── Unblock WiFi ──────────────────────────────────────────────────────────────
# Ensure rfkill isn't soft-blocking the WiFi radio
if command -v rfkill &> /dev/null; then
    rfkill unblock wifi
    info "WiFi radio unblocked via rfkill"
fi

# ── Detect Network Manager (Bookworm vs Bullseye) ─────────────────────────────
if command -v nmcli &> /dev/null && systemctl is-active --quiet NetworkManager; then
    # =========================================================================
    # MODERN PATH: Raspberry Pi OS Bookworm (NetworkManager)
    # =========================================================================
    section "Applying NetworkManager AP Configuration (Bookworm)"
    
    # 1. Clean up old connections named PigMonitor_AP
    if nmcli con show "PigMonitor_AP" &> /dev/null; then
        nmcli con delete "PigMonitor_AP"
        info "Removed old NetworkManager AP profile."
    fi
    
    # 2. Stop hostapd/dnsmasq if they were accidentally installed and running
    systemctl stop hostapd dnsmasq 2>/dev/null || true
    systemctl disable hostapd dnsmasq 2>/dev/null || true
    # 2.5 Ensure dnsmasq-base is installed for the shared IP method
    apt-get update -qq && apt-get install -y dnsmasq-base

    # 3. Create the Hotspot
    info "Creating NetworkManager Hotspot connection..."
    # Create the base connection
    nmcli con add type wifi ifname wlan0 mode ap con-name PigMonitor_AP ssid "$AP_SSID" ipv4.method shared ipv4.addresses "$AP_IP/24"
    
    # Apply security and radio fixes for maximum phone compatibility:
    # - wifi-sec.pmf 1        : Disable Protected Management Frames (fixes iPhone connection drops)
    # - 802-11-wireless.band bg : Force 2.4GHz band (prevents 5GHz driver crashes on Pi)
    nmcli con modify PigMonitor_AP wifi-sec.key-mgmt wpa-psk wifi-sec.psk "$AP_PASS" wifi-sec.pmf 1 802-11-wireless.band bg
    
    # Optional: ensure NM automatically starts it on boot
    nmcli con modify PigMonitor_AP connection.autoconnect yes

    # Security: Ensure NM connection files are restricted
    chmod 600 /etc/NetworkManager/system-connections/PigMonitor_AP.nmconnection 2>/dev/null || true
    
    info "Activating Hotspot..."
    nmcli con up PigMonitor_AP

    info "NetworkManager AP configured successfully."

else
    # =========================================================================
    # LEGACY PATH: Raspberry Pi OS Bullseye (dhcpcd + hostapd + dnsmasq)
    # =========================================================================
    section "Applying Legacy AP Configuration (Bullseye)"
    
    info "Installing hostapd and dnsmasq..."
    apt-get update -qq
    apt-get install -y hostapd dnsmasq
    systemctl stop hostapd dnsmasq 2>/dev/null || true

    # ── Configure static IP for wlan0 (via dhcpcd) ───────────────────────────
    DHCPCD_CONF="/etc/dhcpcd.conf"
    if [[ -f "$DHCPCD_CONF" ]]; then
        sed -i '/# BEGIN pig_monitor_ap/,/# END pig_monitor_ap/d' "$DHCPCD_CONF"
        cat >> "$DHCPCD_CONF" <<EOF

# BEGIN pig_monitor_ap — managed by scripts/setup_ap.sh
interface wlan0
    static ip_address=${AP_IP}/24
    nohook wpa_supplicant
# END pig_monitor_ap
EOF
        info "dhcpcd.conf updated with static $AP_IP on wlan0"
    fi

    # ── Configure hostapd ────────────────────────────────────────────────────
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
    chmod 600 /etc/hostapd/hostapd.conf # Security

    sed -i 's|#DAEMON_CONF=.*|DAEMON_CONF="/etc/hostapd/hostapd.conf"|' /etc/default/hostapd
    
    # Fix Race Condition: Ensure hostapd waits for network online target
    mkdir -p /etc/systemd/system/hostapd.service.d
    cat > /etc/systemd/system/hostapd.service.d/override.conf <<EOF
[Unit]
After=network-online.target
Wants=network-online.target

[Service]
Restart=on-failure
RestartSec=5
EOF
    systemctl daemon-reload

    info "hostapd configured for SSID: $AP_SSID"

    # ── Configure dnsmasq (DHCP server) ──────────────────────────────────────
    DNSMASQ_CONF="/etc/dnsmasq.conf"
    sed -i '/# BEGIN pig_monitor_ap/,/# END pig_monitor_ap/d' "$DNSMASQ_CONF"
    cat >> "$DNSMASQ_CONF" <<EOF

# BEGIN pig_monitor_ap — managed by scripts/setup_ap.sh
interface=wlan0
dhcp-range=${DHCP_START},${DHCP_END},255.255.255.0,24h
address=/#/${AP_IP}
# END pig_monitor_ap
EOF
    info "dnsmasq configured."

    # ── Enable services ──────────────────────────────────────────────────────
    systemctl unmask hostapd
    systemctl enable hostapd dnsmasq
    info "Legacy services enabled."
fi

# ── Update config.yaml to use ap mode ────────────────────────────────────────
section "Updating config.yaml network mode to 'ap'"
sed -i "s/^  mode: .*/  mode: \"ap\"/" "$CONFIG_FILE"
info "config.yaml → network.mode = ap"

section "Summary"
echo ""
echo -e "  ${GREEN}✓${NC} AP Mode Configuration Applied"
echo -e "  ${GREEN}✓${NC} SSID        : $AP_SSID"
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
