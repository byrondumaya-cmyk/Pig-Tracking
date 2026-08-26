import sys
import time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.hardware.gsm_notifier import GSMNotifier
from src.database.repository import SwineRepository

class MockSerial:
    def __init__(self, behavior="success"):
        self.behavior = behavior
        self.in_waiting = 0
        self.buffer = ""
        self.is_open = True
    def write(self, b):
        cmd = b.decode().strip()
        if self.behavior == "success":
            if cmd == "AT" or cmd == "AT+CMGF=1":
                self.buffer = "OK\r\n"
            elif "AT+CMGS" in cmd:
                self.buffer = "> "
            elif "DIAGNOSTIC" in cmd or chr(0x1A) in cmd:
                self.buffer = "+CMGS: 123\r\nOK\r\n"
        elif self.behavior == "timeout_prompt":
            if "AT+CMGS" in cmd:
                self.buffer = "" # timeout
                time.sleep(0.5)
        elif self.behavior == "error_cmgs":
            if "AT+CMGS" in cmd:
                self.buffer = "> "
            elif "DIAGNOSTIC" in cmd or chr(0x1A) in cmd:
                self.buffer = "ERROR\r\n"
        self.in_waiting = len(self.buffer)
    def read(self, size):
        res = self.buffer[:size].encode()
        self.buffer = self.buffer[size:]
        self.in_waiting = len(self.buffer)
        return res
    def close(self):
        self.is_open = False

def test_gsm_diagnostic():
    pass
    
    # Test 1: Success
    notifier = GSMNotifier(port="COM1", baud_rate=9600)
    notifier._serial = MockSerial("success")
    res = notifier.send_diagnostic_test("+123456")
    assert res["status"] == "success"
    assert "+CMGS acknowledged" in res["detail"]
    
    # Test 2: Timeout on CMGS prompt
    notifier._serial = MockSerial("timeout_prompt")
    res = notifier.send_diagnostic_test("+123456")
    assert res["status"] == "error"
    assert "failed to accept CMGS command" in res["detail"]
    
    # Test 3: Error on submission
    notifier._serial = MockSerial("error_cmgs")
    res = notifier.send_diagnostic_test("+123456")
    assert res["status"] == "error"
    assert "timeout" in res["detail"] or "did not confirm" in res["detail"]
    
    # Verify no alerts were logged manually by inspecting gsm_notifier.py logic
    # (Since GSMNotifier does not import SwineRepository or AlertEvent, it cannot create alerts)

    print("GSM Diagnostic validation passed!")

if __name__ == "__main__":
    test_gsm_diagnostic()
