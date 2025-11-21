import socket
import time
import pandas as pd

ESP8266_IP = 192.168.10.115
ESP8266_PORT = 1234

path = "/ros2_ws/space/src/hw_px3/resource/Angle_List_from_x_0_to_80.csv"
df = pd.read_csv(path)
angle_list = df["angle_deg"].tolist()
servo_angles = [int(max(0, min(180, angle))) for angle in angle_list]

initial_angle = 72
last_angle = 124

def send_angle(angle):
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(3)  # 応答がなければ3秒でタイムアウト
            s.connect((ESP8266_IP, ESP8266_PORT))
            s.sendall(f"{angle}\n".encode())
            response = s.recv(1024).decode().strip()
            print(f"Sent: {angle}°, Response: {response}")
    except Exception as e:
        print(f"Error sending angle {angle}: {e}")

# === 最初に初期角度を送信 ===
send_angle(initial_angle)
time.sleep(1.5)  # サーボが動くのを待つ

# === 角度を往復で送信 ===
try:
    while True:
        for angle in servo_angles:
            angle += initial_angle
            angle = max(0, min(180, angle))  # 念のため制限
            send_angle(angle)
            time.sleep(0.5)

        for angle in reversed(servo_angles):
            angle += initial_angle
            angle = max(0, min(180, angle))
            send_angle(angle)
            time.sleep(0.5)

except KeyboardInterrupt:
    print("Stopped by user")

