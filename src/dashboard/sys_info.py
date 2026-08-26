"""
src/dashboard/sys_info.py
Utility to read actual OS-level network and system information.
"""

import subprocess
import shutil
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

def get_network_mode(fallback: str = "unknown") -> str:
    """Returns 'ap' if hostapd is active, else 'lan'. Falls back if not Linux."""
    try:
        res = subprocess.run(["systemctl", "is-active", "hostapd"], capture_output=True, text=True, timeout=2)
        if res.stdout.strip() == "active":
            return "ap"
        return "lan"
    except (FileNotFoundError, subprocess.TimeoutExpired):
        # likely on Windows or Mac during development
        return fallback

def get_ap_ssid(fallback: str = None) -> str:
    """Extracts SSID from hostapd config if available."""
    try:
        if Path("/etc/hostapd/hostapd.conf").exists():
            with open("/etc/hostapd/hostapd.conf", "r") as f:
                for line in f:
                    if line.startswith("ssid="):
                        return line.strip().split("=")[1]
    except Exception as e:
        logger.debug(f"Could not read hostapd.conf: {e}")
    return fallback

def get_current_ip(interface: str = "wlan0", fallback: str = None) -> str:
    """Returns the current IP address of the given interface."""
    try:
        res = subprocess.run(["ip", "-4", "addr", "show", interface], capture_output=True, text=True, timeout=2)
        for line in res.stdout.split('\n'):
            if "inet " in line:
                return line.strip().split(" ")[1].split("/")[0]
    except (FileNotFoundError, subprocess.TimeoutExpired):
        # Handle Windows dev environment via ipconfig
        try:
            res = subprocess.run(["ipconfig"], capture_output=True, text=True, timeout=2)
            # Just grab the first IPv4 address for dev purposes
            for line in res.stdout.split('\n'):
                if "IPv4 Address" in line:
                    return line.split(":")[1].strip()
        except Exception:
            pass
    except Exception as e:
        logger.debug(f"Could not read IP address: {e}")
    
    return fallback

def get_storage_usage_pct(path: str = ".") -> str:
    try:
        usage = shutil.disk_usage(Path(path))
        used_pct = int(usage.used / usage.total * 100)
        return f"{used_pct}%"
    except Exception:
        return "unknown"
