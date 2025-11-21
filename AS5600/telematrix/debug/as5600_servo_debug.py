#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AS5600 + Servo Debug (Telemetrix)
- Reads AS5600 angle over I2C and (optionally) drives a servo.
- Modes:
    read   : just print angle
    sweep  : sweep servo 0<->180 deg and print angle
    mirror : map AS5600 0..360 deg -> servo 0..180 deg (angle/2)

Prereqs:
  1) Flash Telemetrix4Arduino to your Arduino (see Telemetrix docs).
  2) pip install telemetrix

How to run (examples):
  python as5600_servo_debug.py --serial /dev/ttyACM0 --i2c 1 --addr 0x36 --mode read
  python as5600_servo_debug.py --serial COM3         --i2c 1 --mode sweep --servo-pin 9
  python as5600_servo_debug.py --serial /dev/ttyACM0 --i2c 1 --mode mirror --hz 25

Wiring quick ref (UNO/Nano):
  AS5600: VCC->3.3V or 5V, GND->GND, SDA->A4, SCL->A5
  Servo : SIG->D9, V+->external 5V, GND->common with Arduino & AS5600
"""

import time
import argparse
from telemetrix import telemetrix

# --- AS5600 registers (ANGLE is fine for display/servo mapping) ---
REG_STATUS      = 0x0B
REG_ANGLE_H     = 0x0E       # ANGLE high byte (ANGLE_L = 0x0F)
ADDR_DEFAULT    = 0x36

def i2c_init(board, port):
    # Minimal, compatible init
    board.set_pin_mode_i2c(i2c_port=port)
    time.sleep(0.10)

def i2c_read(board, addr, reg, n, i2c_port, timeout=1.0):
    """
    Read n bytes from (addr, reg) and return a list of n bytes.
    Compatible with Telemetrix callback style; extracts last n bytes.
    """
    box = {"data": None}
    def cb(data):
        if data:
            # Force to 0..255 ints; take last n items
            tail = [int(round(x)) & 0xFF for x in data[-n:]]
            box["data"] = tail

    board.i2c_read(addr, reg, n, cb, i2c_port=i2c_port)

    t0 = time.time()
    while time.time() - t0 < timeout:
        if box["data"] is not None:
            return box["data"]
        time.sleep(0.005)
    return None

def read_angle_deg(board, addr, i2c_port):
    """Read 12-bit ANGLE (0..4095) and convert to degrees (0..360)."""
    b = i2c_read(board, addr, REG_ANGLE_H, 2, i2c_port=i2c_port, timeout=1.0)
    if not b or len(b) < 2:
        return None
    raw12 = ((b[0] << 8) | b[1]) & 0x0FFF
    return raw12 * (360.0 / 4096.0)

def find_sensor(board, prefer_port, addr):
    """Try prefer_port then the other (0/1). Return (port) or None."""
    for p in ([prefer_port, 1 - prefer_port] if prefer_port in (0,1) else [1,0]):
        try:
            i2c_init(board, p)
            deg = read_angle_deg(board, addr, p)
            if deg is not None:
                return p
        except Exception:
            pass
    return None

def attach_servo(board, pin, min_pulse=544, max_pulse=2400):
    board.set_pin_mode_servo(pin, min_pulse=min_pulse, max_pulse=max_pulse)

def write_servo(board, pin, angle):
    # Clamp 0..180
    a = int(max(0, min(180, angle)))
    board.servo_write(pin, a)

def main():
    ap = argparse.ArgumentParser(description="AS5600 + Servo debug via Telemetrix")
    ap.add_argument("--serial", default="/dev/ttyACM0", help="Arduino serial port (e.g., /dev/ttyACM0 or COM3)")
    ap.add_argument("--i2c", type=int, default=1, help="I2C port to try first (0 or 1)")
    ap.add_argument("--addr", type=lambda x:int(x,0), default=ADDR_DEFAULT, help="I2C address (AS5600=0x36, AS5600L=0x40...)")
    ap.add_argument("--servo-pin", type=int, default=9, help="Servo signal pin (e.g., 9)")
    ap.add_argument("--mode", choices=["read","sweep","mirror"], default="read", help="read=sensor only; sweep=servo sweep; mirror=sensor->servo")
    ap.add_argument("--hz", type=float, default=25.0, help="update/print rate")
    args = ap.parse_args()

    print(f"[INFO] Connecting Telemetrix @ {args.serial} ...", flush=True)
    board = telemetrix.Telemetrix(com_port=args.serial)

    # Find the sensor (try i2c 1 then 0)
    port = find_sensor(board, args.i2c, args.addr)
    if port is None:
        print("[ERROR] No AS5600 response on I2C port 1 or 0 (addr 0x%02X)." % args.addr)
        print("        Check VCC/GND/SDA/SCL, address, magnet, and --i2c setting.")
        try: board.shutdown()
        finally: return

    print(f"[OK] AS5600 detected on I2C port {port}, addr=0x{args.addr:02X}")

    # Servo setup if needed
    if args.mode in ("sweep","mirror"):
        attach_servo(board, args.servo_pin)
        # Set to a safe mid position first
        write_servo(board, args.servo_pin, 90)
        time.sleep(0.3)

    period = 1.0 / max(args.hz, 1.0)

    try:
        if args.mode == "read":
            print("[INFO] Streaming angle (deg). CTRL+C to stop.")
            while True:
                deg = read_angle_deg(board, args.addr, port)
                if deg is not None:
                    print(f"{time.time():.3f}, {deg:8.3f} deg")
                else:
                    print(f"{time.time():.3f}, READ_FAIL")
                time.sleep(period)

        elif args.mode == "sweep":
            print("[INFO] Sweeping servo 0<->180 while reading AS5600. CTRL+C to stop.")
            direction = 1
            pos = 0
            while True:
                write_servo(board, args.servo_pin, pos)
                deg = read_angle_deg(board, args.addr, port)
                print(f"{time.time():.3f}, servo={pos:3d}°, sensor={deg:8.3f} deg" if deg is not None
                      else f"{time.time():.3f}, servo={pos:3d}°, READ_FAIL")
                pos += direction * 5
                if pos >= 180: direction, pos = -1, 180
                if pos <=   0: direction, pos =  1,   0
                time.sleep(period)

        elif args.mode == "mirror":
            print("[INFO] Mirroring sensor angle to servo (deg/2). CTRL+C to stop.")
            while True:
                deg = read_angle_deg(board, args.addr, port)
                if deg is not None:
                    servo_angle = deg / 2.0   # 0..360 -> 0..180
                    write_servo(board, args.servo_pin, servo_angle)
                    print(f"{time.time():.3f}, sensor={deg:8.3f} deg, servo={servo_angle:6.1f}°")
                else:
                    print(f"{time.time():.3f}, READ_FAIL")
                time.sleep(period)

    except KeyboardInterrupt:
        pass
    finally:
        try:
            board.shutdown()
        except Exception:
            pass
        print("[INFO] Bye.")
        
if __name__ == "__main__":
    main()

