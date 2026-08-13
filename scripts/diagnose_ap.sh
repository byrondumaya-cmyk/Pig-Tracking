#!/bin/bash
# scripts/diagnose_ap.sh
# Diagnostic script to capture AP status and real-time hostapd/DHCP logs.
# Run this script while attempting to connect a phone to the AP.

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

if [[ $EUID -ne 0 ]]; then
   echo -e "${RED}This script must be run as root (use sudo).${NC}" 
   exit 1
fi

echo -e "${CYAN}====================================================${NC}"
echo -e "${CYAN}      PigMonitor AP Connection Diagnostic Tool      ${NC}"
echo -e "${CYAN}====================================================${NC}"
echo ""
echo -e "${YELLOW}INSTRUCTIONS:${NC}"
echo -e "1. Please forget the 'PigMonitor_AP' network on your phone."
echo -e "2. Keep this script running."
echo -e "3. Attempt to connect your phone to the 'PigMonitor_AP' network using the password from the dashboard."
echo -e "4. Watch the logs below for errors."
echo -e "5. Press ${RED}Ctrl+C${NC} to stop capturing logs."
echo ""
echo -e "${GREEN}Starting log capture. Waiting for connection attempts...${NC}"
echo -e "----------------------------------------------------"

echo -e "${CYAN}Current AP status:${NC}"
echo ""
systemctl --no-pager --full status networking hostapd dnsmasq || true
echo ""
ip -brief link show wlan0 || true
ip -brief address show wlan0 || true
iw dev wlan0 info 2>&1 || true
echo ""
echo -e "${CYAN}Configuration checks:${NC}"
# systemd's startup log is the safe hostapd configuration check. Do not invoke
# hostapd directly here: doing so would contend with the running AP daemon.
grep -E '^(interface|ssid|country_code|hw_mode|channel|wpa)=' /etc/hostapd/hostapd.conf 2>&1 || true
dnsmasq --test 2>&1 || true
echo ""
echo -e "${GREEN}Starting log capture. Attempt the phone connection now...${NC}"
echo -e "----------------------------------------------------"

# hostapd records authentication/association failures; dnsmasq records DHCP.
# NetworkManager is included only to expose accidental wlan0 ownership.
journalctl -u networking -u hostapd -u dnsmasq -u NetworkManager -k -f --since "5 minutes ago"
