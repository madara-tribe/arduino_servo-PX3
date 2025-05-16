import serial
import time

# Open serial port
ser = serial.Serial('/dev/ttyACM0', 9600, timeout=1)  # Change to your port!
time.sleep(2)  # wait for Arduino reset

try:
    while True:
        # Input angle from user
        angle = input("Enter angle (0-180, or 'q' to quit): ")
        
        if angle.lower() == 'q':
            break
        
        try:
            angle_value = int(angle)
            if 0 <= angle_value <= 180:
                ser.write(f"{angle_value}\n".encode())  # send angle with newline
            else:
                print("Angle must be between 0 and 180.")
        except ValueError:
            print("Please input a number.")
            
except KeyboardInterrupt:
    pass
finally:
    ser.close()
    print("Serial port closed.")

