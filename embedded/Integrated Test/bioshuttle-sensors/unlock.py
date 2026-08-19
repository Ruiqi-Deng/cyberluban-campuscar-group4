"""Send unlock command to ESP32 over USB serial.

Close PlatformIO Serial Monitor first, or COM7 will be busy.
Usage:  python unlock.py
"""

import serial
import time

PORT = "COM7"
BAUD = 115200

ser = serial.Serial(PORT, BAUD, timeout=1)
time.sleep(0.2)
ser.write(b"CTRL,0,0,1,0,0\n")
print("Sent CTRL,0,0,1,0,0 to", PORT)

time.sleep(1.2)
while ser.in_waiting:
    line = ser.readline().decode("utf-8", errors="ignore").strip()
    if line:
        print(line)

ser.close()
print("Done")
