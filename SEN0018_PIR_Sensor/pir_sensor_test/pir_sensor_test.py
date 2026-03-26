import sys
import time
from datetime import datetime

import serial
from serial.tools import list_ports


def choose_port():
    ports = list(list_ports.comports())
    if not ports:
        print("No serial ports found.")
        sys.exit(1)

    print("Available ports:")
    for i, p in enumerate(ports):
        print(f"[{i}] {p.device}  {p.description}")

    if len(sys.argv) >= 2:
        return sys.argv[1]

    idx = int(input("Select port index: ").strip())
    return ports[idx].device


def main():
    port = choose_port()
    baudrate = 115200

    print(f"Open: {port}")
    ser = serial.Serial(port, baudrate, timeout=1)

    # Uno resets when serial opens
    time.sleep(2)

    print("Listening... Ctrl+C to stop.")
    try:
        while True:
            line = ser.readline().decode(errors="replace").strip()
            if not line:
                continue

            now = datetime.now().strftime("%H:%M:%S")
            print(f"[{now}] {line}")

    except KeyboardInterrupt:
        print("Stopped.")
    finally:
        ser.close()


if __name__ == "__main__":
    main()
