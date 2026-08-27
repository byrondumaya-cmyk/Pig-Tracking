"""
src/hardware/gsm_notifier.py
GSM900A SMS Alert Dispatcher

PURPOSE:
    Sends offline SMS alerts via GSM900A module using AT commands over UART.
    Implements 5-minute cooldown to prevent alert fatigue.
    Supports multiple recipient phone numbers (editable from Dashboard Settings Panel).

WIRING (Raspberry Pi 4B):
    GSM900A TX  → RPi GPIO15 / RXD0 (Pin 10)
    GSM900A RX  → RPi GPIO14 / TXD0 (Pin 8)
    GSM900A GND → GND (Pin 14)
    GSM900A VCC → External 5V / 2A supply (NOT from Pi 5V pin — GSM draws too much current)

PREREQUISITES:
    sudo raspi-config → Interface Options → Serial Port
    → Enable serial hardware, disable login shell over serial

VERIFY:
    python3 -c "import serial; s=serial.Serial('/dev/serial0',9600,timeout=1); print(s.readline())"
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timedelta
from typing import Optional

logger = logging.getLogger(__name__)

try:
    import serial
    _SERIAL_AVAILABLE = True
except ImportError:
    _SERIAL_AVAILABLE = False
    logger.warning("pyserial not available — GSM will run in simulation mode.")


class GSMNotifier:
    """
    Dispatches SMS alerts via GSM900A module.
    Enforces a configurable cooldown between repeated alerts.
    
    Can receive phone numbers either:
    1. From config.gsm.phone_numbers (legacy, for backward compatibility)
    2. Dynamically from database via repository (new, preferred)
    """

    def __init__(
        self,
        port: str = "/dev/serial0",
        baud_rate: int = 9600,
        cooldown_minutes: int = 5,
        repository = None,  # Optional: SwineRepository for dynamic recipient lookup
    ) -> None:
        self._port = port
        self._baud_rate = baud_rate
        self._cooldown = timedelta(minutes=cooldown_minutes)
        self._last_sent: dict[str, datetime] = {}   # alert_type → last sent time
        self._serial: Optional[object] = None
        self._repository = repository  # For dynamic recipient lookup
        
        import threading
        self._lock = threading.Lock()

        if _SERIAL_AVAILABLE:
            try:
                self._serial = serial.Serial(port, baud_rate, timeout=3)
                time.sleep(1.0)     # GSM module boot delay
                self._init_module()
                logger.info(f"GSM900A ready on {port}")
            except Exception as e:
                logger.error(f"GSM init failed: {e}. Running in simulation mode.")
        else:
            logger.info("GSM running in simulation mode.")

    def _init_module(self) -> None:
        """Configure GSM module to text mode."""
        self._send_at("AT", expected="OK")
        self._send_at("AT+CMGF=1", expected="OK")   # Set SMS text mode

    def _send_at(self, command: str, expected: str = "OK", timeout: float = 5.0) -> bool:
        """Send an AT command and check for expected response."""
        if not self._serial:
            return True
        with self._lock:
            try:
                self._serial.write((command + "\r\n").encode())
                deadline = time.time() + timeout
                response = ""
                while time.time() < deadline:
                    if self._serial.in_waiting:
                        response += self._serial.read(self._serial.in_waiting).decode(errors="ignore")
                    if expected in response:
                        return True
                    time.sleep(0.1)
                logger.warning(f"AT command '{command}' timed out. Response: {response!r}")
                return False
            except Exception as e:
                logger.error(f"AT command error: {e}")
                return False

    def send_diagnostic_test(self, number: str) -> dict:
        """
        Send a diagnostic test SMS and return exact delivery confirmation level.
        Does not interact with alert cooldowns or normal alert state.
        Returns: {"status": str, "detail": str}
        """
        if not self._serial:
            logger.info(f"[SIM] Diagnostic test SMS to {number}")
            return {"status": "simulated", "detail": "GSM module running in simulation mode. SMS acknowledged by simulator."}
            
        try:
            cmd = f'AT+CMGS="{number}"'
            if not self._send_at(cmd, expected=">", timeout=10.0):
                return {"status": "error", "detail": "GSM module failed to accept CMGS command."}
            
            message = "DIAGNOSTIC TEST: Pig Tracking System GSM module is responding."
            with self._lock:
                self._serial.write((message + chr(0x1A)).encode())
            
            # We wait for +CMGS: which means the module successfully transmitted it to the network.
            # Real delivery receipts (AT+CNMI) are not currently implemented, so we state what we know.
            success = self._send_at("", expected="+CMGS:", timeout=15.0)
            
            if success:
                return {"status": "success", "detail": "Message submitted to GSM network (+CMGS acknowledged)."}
            else:
                return {"status": "error", "detail": "Module did not confirm submission (+CMGS timeout)."}
        except Exception as e:
            logger.error(f"Diagnostic test failed: {e}")
            return {"status": "error", "detail": f"Exception occurred: {str(e)}"}

    def _is_cooled_down(self, alert_type: str) -> bool:
        """Check if enough time has passed since the last alert of this type."""
        last = self._last_sent.get(alert_type)
        if last is None:
            return True
        return datetime.now() - last >= self._cooldown

    def send_alert(
        self,
        phone_numbers: list[str] | None = None,
        alert_type: str = "alert",
        message: str = "",
        force: bool = False,
    ) -> bool:
        """
        Send an SMS alert to configured recipients.

        Args:
            phone_numbers: Optional list of recipient numbers. If not provided, uses repository.
            alert_type: Alert category key for cooldown tracking (e.g. 'individual', 'population').
            message: SMS body text (keep under 160 chars for single SMS).
            force: Bypass cooldown (use sparingly, e.g. manual test from dashboard).

        Returns:
            True if at least one SMS was sent successfully.
        """
        # Determine recipients: explicit list, repository, or fallback to empty
        if phone_numbers is None:
            if self._repository:
                phone_numbers = self._repository.get_enabled_recipients()
            else:
                phone_numbers = []
        
        if not phone_numbers:
            logger.warning("No recipients configured for SMS alert.")
            return False

        if not force and not self._is_cooled_down(alert_type):
            remaining = self._cooldown - (datetime.now() - self._last_sent[alert_type])
            logger.info(f"SMS cooldown active for '{alert_type}'. {remaining.seconds}s remaining.")
            return False

        success = False
        for number in phone_numbers:
            if self._send_sms(number, message):
                success = True

        if success:
            self._last_sent[alert_type] = datetime.now()
            logger.info(f"SMS alert sent [{alert_type}] to {len(phone_numbers)} recipient(s).")

        return success

    def _send_sms(self, number: str, message: str) -> bool:
        """Send a single SMS to one recipient."""
        # Sanitize message for GSM 7-bit / ASCII compatibility
        # Replace common degree symbol first, then strip anything else non-ASCII
        safe_msg = message.replace('°', ' deg')
        safe_msg = safe_msg.encode('ascii', 'ignore').decode('ascii')

        if not self._serial:
            # Simulation: log what would have been sent
            logger.info(f"[SIM] SMS to {number}: {safe_msg}")
            return True

        try:
            cmd = f'AT+CMGS="{number}"'
            if not self._send_at(cmd, expected=">", timeout=10.0):
                return False
            # Send message body followed by Ctrl+Z (0x1A) to send
            self._serial.write((safe_msg + chr(0x1A)).encode('ascii'))
            return self._send_at("", expected="+CMGS:", timeout=15.0)
        except Exception as e:
            logger.error(f"SMS send to {number} failed: {e}")
            return False

    def test_connection(self) -> bool:
        """Test if the GSM module is responding. Used by the dashboard status check."""
        return self._send_at("AT", expected="OK")

    def close(self) -> None:
        """Close the serial port."""
        if self._serial:
            try:
                self._serial.close()
            except Exception:
                pass
