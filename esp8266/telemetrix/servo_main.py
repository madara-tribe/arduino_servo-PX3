from telemetrix import telemetrix
import time

# ========= CONFIG ==========
port = "/dev/ttyUSB3"
SERVO_PIN = 12  # GPIO14 (D5 on many ESP8266 boards)
# ===========================

def main():
    # Connect to ESP8266 Telemetrix Server
    board = telemetrix.Telemetrix(com_port=port)
    board.set_pin_mode_servo(SERVO_PIN, 100, 3000)
    time.sleep(1)

    print("Moving servo...")
    # Sweep demo
    for angle in range(0, 181, 10):
        board.servo_write(SERVO_PIN, angle)
        print(f"Angle = {angle}")
        time.sleep(0.4)

    for angle in range(180, -1, -10):
        board.servo_write(SERVO_PIN, angle)
        print(f"Angle = {angle}")
        time.sleep(0.4)

    # center
    board.servo_write(SERVO_PIN, 90)
    print("Centered at 90°")

    board.shutdown()

if __name__ == "__main__":
    main()

