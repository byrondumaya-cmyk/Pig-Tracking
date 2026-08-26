import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.dashboard.sys_info import get_network_mode, get_current_ip, get_ap_ssid

print("Mode:", get_network_mode("unknown"))
print("IP:", get_current_ip(fallback="unknown"))
print("SSID:", get_ap_ssid("unknown"))
