import socket

ESP8266_IP = "192.168.10.115"  
ESP8266_PORT = 1234

def send_angle(angle):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.connect((ESP8266_IP, ESP8266_PORT))
        s.sendall(f"{angle}\n".encode())
        response = s.recv(1024)
        print("Response:", response.decode())

send_angle(90)

