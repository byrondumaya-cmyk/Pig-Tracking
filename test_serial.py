import serial
import time
import sys

def test_serial(port='/dev/serial0', baud=9600):
    print(f"Testing serial port {port} at {baud} baud...")
    try:
        ser = serial.Serial(port, baud, timeout=2)
        print("Serial port opened successfully.")
    except Exception as e:
        print(f"FAILED to open {port}: {e}")
        sys.exit(1)

    # Clear any junk
    ser.reset_input_buffer()
    ser.reset_output_buffer()

    print("Sending 'AT'...")
    ser.write(b"AT\r\n")
    
    start_time = time.time()
    response = b""
    print("Waiting for response...")
    
    while time.time() - start_time < 3:
        if ser.in_waiting:
            chunk = ser.read(ser.in_waiting)
            response += chunk
            print(f"Received raw bytes: {chunk}")
        time.sleep(0.1)

    if not response:
        print("FAILED: No response received at all (Timeout).")
        print("This means the module is either powered off, TX/RX are backwards, or /dev/serial0 is disabled in OS.")
    else:
        print(f"SUCCESS! Received data: {response.decode(errors='ignore')}")

if __name__ == "__main__":
    baud = 9600
    if len(sys.argv) > 1:
         baud = int(sys.argv[1])
    test_serial(baud=baud)
