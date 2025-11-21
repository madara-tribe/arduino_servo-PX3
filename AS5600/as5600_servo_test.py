#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
as5600_servo_test.py

- Talks to the Arduino sketch 'as5600_servo_serial.ino'.
- Sends servo angles (S <angle>) and reads back AS5600 angle (R).
- Used to test:
    * AS5600 wiring
    * servo wiring & power
    * AS5600 movement vs servo movement

Usage examples:
  python3 as5600_servo_test.py --serial /dev/ttyACM0 --sweep
  python3 as5600_servo_test.py --serial /dev/ttyACM0 --fixed 90
"""

import time
import argparse
import serial

def open_port(port, baudrate=9600, timeout=1.0):
    ser = serial.Serial(port, baudrate=baudrate, timeout=timeout)
    # Give Arduino time to reset
    time.sleep(2.0)
    # Flush any reset messages
    ser.reset_input_buffer()
    ser.reset_output_buffer()
    return ser

def send_cmd(ser, cmd, expect_reply=True):
    """Send a line command, return one line of reply (str) or ''."""
    line = (cmd.strip() + "\n").encode("utf-8")
    ser.write(line)
    ser.flush()
    if not expect_reply:
        return ""
    reply = ser.readline().decode("utf-8", errors="replace").strip()
    return reply

def parse_angle_reply(text):
    """
    Parse "ANGLE raw=1234 deg=108.750 servo= 90" into dict.
    Very simple parser; just for debug.
    """
    result = {}
    parts = text.split()
    for p in parts:
        if p.startswith("raw="):
            try:
                result["raw"] = int(p.split("=",1)[1])
            except ValueError:
                pass
        elif p.startswith("deg="):
            try:
                result["deg"] = float(p.split("=",1)[1])
            except ValueError:
                pass
        elif p.startswith("servo="):
            try:
                result["servo"] = int(p.split("=",1)[1])
            except ValueError:
                pass
    return result

def sweep_test(ser, min_deg=0, max_deg=180, step=15, wait=0.3):
    """
    Sweep servo from min_deg to max_deg and back.
    After each move, ask Arduino to report AS5600 angle.
    """
    print("[INFO] Sweep test start.")
    try:
        while True:
            # Up
            for d in range(min_deg, max_deg + 1, step):
                reply_set = send_cmd(ser, f"S {d}")
                time.sleep(wait)
                reply_read = send_cmd(ser, "R")
                info = parse_angle_reply(reply_read)
                print(f"SET={d:3d}, REPLY='{reply_read}', PARSED={info}")
            # Down
            for d in range(max_deg, min_deg - 1, -step):
                reply_set = send_cmd(ser, f"S {d}")
                time.sleep(wait)
                reply_read = send_cmd(ser, "R")
                info = parse_angle_reply(reply_read)
                print(f"SET={d:3d}, REPLY='{reply_read}', PARSED={info}")
    except KeyboardInterrupt:
        print("\n[INFO] Sweep test stopped by user.")

def fixed_test(ser, angle=90, wait=0.5):
    """
    Set servo to a fixed angle and repeatedly read the AS5600.
    You can manually move the shaft/magnet and see the angle change.
    """
    send_cmd(ser, f"S {angle}")
    print(f"[INFO] Fixed angle test: servo set to {angle} deg. CTRL+C to stop.")
    try:
        while True:
            reply = send_cmd(ser, "R")
            info = parse_angle_reply(reply)
            print(f"REPLY='{reply}', PARSED={info}")
            time.sleep(wait)
    except KeyboardInterrupt:
        print("\n[INFO] Fixed test stopped by user.")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--serial", required=True, help="Arduino serial port (e.g., /dev/ttyACM0 or COM3)")
    ap.add_argument("--baud", type=int, default=9600)
    ap.add_argument("--sweep", action="store_true", help="Run sweep test (servo 0<->180)")
    ap.add_argument("--fixed", type=int, default=None, help="Run fixed-angle test (e.g., --fixed 90)")
    ap.add_argument("--step", type=int, default=15, help="Sweep step size in degrees")
    ap.add_argument("--wait", type=float, default=0.3, help="Wait time after move (seconds)")
    args = ap.parse_args()

    if not args.sweep and args.fixed is None:
        ap.error("Specify either --sweep or --fixed <angle>")

    ser = open_port(args.serial, baudrate=args.baud)
    print(f"[INFO] Connected to {args.serial} @ {args.baud}.")

    # Read any greeting lines from Arduino
    time.sleep(0.5)
    while True:
        line = ser.readline().decode("utf-8", errors="replace").strip()
        if not line:
            break
        print("[ARDUINO]", line)

    if args.sweep:
        sweep_test(ser, min_deg=0, max_deg=180, step=args.step, wait=args.wait)
    else:
        fixed_test(ser, angle=args.fixed, wait=args.wait)

    ser.close()

if __name__ == "__main__":
    main()

