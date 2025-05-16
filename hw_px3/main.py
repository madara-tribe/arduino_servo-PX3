import serial
import time
import pandas as pd

# === Load angle list from CSV ===
path = "/ros2_ws/space/src/hw_px3/resource/Angle_List_from_x_0_to_80.csv"
df = pd.read_csv(path)
angle_list = df["angle_deg"].tolist()
servo_angles = [int(max(0, min(180, angle))) for angle in angle_list]

# === Connect to Arduino ===
ser = serial.Serial('/dev/ttyACM0', 9600, timeout=1)
time.sleep(5)  # Wait for Arduino to reset

# === Set initial angle to 72 degrees ===
initial_angle = 72
last_angle = 124
ser.write(f"{initial_angle}\n".encode())
print(f"Initialized to angle: {initial_angle}")
time.sleep(1.5)  # Wait for servo to move

# === Sweep through angles forward and backward ===
try:
    while True:
        for angle in servo_angles:
            angle += initial_angle
            ser.write(f"{angle}\n".encode())
            print(f"Sent angle: {angle}")
            time.sleep(0.5)

        for angle in reversed(servo_angles):
            angle += initial_angle
            ser.write(f"{angle}\n".encode())
            print(f"Sent angle: {angle}")
            time.sleep(0.5)
except KeyboardInterrupt:
    print("Stopped by user")
finally:
    ser.close()
