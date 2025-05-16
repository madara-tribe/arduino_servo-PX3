import serial
import time

wait_second = 5.0
total_number = 10

ser = serial.Serial("/dev/ttyACM0", 9600, timeout=1)  # specify baudrate!

time.sleep(wait_second)  # wait for Arduino reset

for i in range(total_number):
    line = ser.readline()
    print(line)

ser.close()

