import tkinter as tk
import socket

ESP8266_IP = "192.168.10.115"
ESP8266_PORT = 1234

def send_angle(angle):
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(3)  # 応答がなければ3秒でタイムアウト
            s.connect((ESP8266_IP, ESP8266_PORT))
            s.sendall(f"{angle}\n".encode())
            response = s.recv(1024).decode().strip()
            status_label.config(text=f"送信成功: {angle}° → ESP応答: {response}")
    except Exception as e:
        status_label.config(text=f"送信失敗: {e}")

def on_slider_change(value):
    angle = int(float(value))
    angle_label.config(text=f"角度: {angle}°")
    send_angle(angle)

root = tk.Tk()
root.title("Wi-Fi サーボキャリブレーション")

slider = tk.Scale(root, from_=0, to=180, orient=tk.HORIZONTAL, command=on_slider_change, length=400)
slider.pack(padx=20, pady=10)

angle_label = tk.Label(root, text="角度: 90°", font=("Arial", 14))
angle_label.pack()

status_label = tk.Label(root, text="準備完了", fg="blue", font=("Arial", 12))
status_label.pack(pady=10)

root.mainloop()
