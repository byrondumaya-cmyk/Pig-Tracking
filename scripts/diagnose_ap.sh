#!/bin/bash
# scripts/diagnose_ap.sh
# Diagnostic script to capture real-time NetworkManager, WPA Supplicant, and dnsmasq logs.
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

# Tail logs for NetworkManager, wpa_supplicant, and dnsmasq
journalctl -u NetworkManager -u wpa_supplicant -k -f --since "1 minute ago"
