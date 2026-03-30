import sys
import time
from datetime import datetime

from telemetrix import telemetrix
from serial.tools import list_ports


PIR_PIN = 2


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


def pir_callback(data):
    now = datetime.now().strftime("%H:%M:%S")
    print(f"[{now}] raw callback data: {data}")

    pin = None
    value = None

    if isinstance(data, (list, tuple)) and len(data) >= 3:
        pin = data[1]
        value = data[2]

    if pin is None or value is None:
        print(f"[{now}] callback format is unexpected")
        return

    if value == 1:
        print(f"[{now}] PIR DETECTED (pin={pin})")
    else:
        print(f"[{now}] PIR NOT_DETECTED (pin={pin})")


def main():
    port = "/dev/ttyACM0"

    print("Starting Telemetrix PIR test...")
    print(f"Using port: {port}")

    board = telemetrix.Telemetrix(com_port=port)

    try:
        board.set_pin_mode_digital_input(PIR_PIN, callback=pir_callback)

        print(f"PIR monitoring started on D{PIR_PIN}")
        print("Move in front of the sensor. Press Ctrl+C to stop.")

        while True:
            time.sleep(0.1)

    except KeyboardInterrupt:
        print("\nStopping...")
    finally:
        try:
            board.shutdown()
        except Exception as e:
            print(f"Shutdown warning: {e}")


if __name__ == "__main__":
    main()
