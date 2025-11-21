#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AS5600 + Servo dual test via Telemetrix (v1.43-safe, force i2c_port=1)
- follow : AS5600角度 -> サーボ角
- sweep  : サーボ正弦スイープ（AS5600は同時読出）
- v1.43 対応: i2c_readはcallback必須/return_dataなし/address_sizeなし
"""

import time, math, argparse, threading
from telemetrix import telemetrix

ADDR = 0x36
REG_ANGLE_H = 0x0E  # ANGLE high (0x0E/0x0F)

def sanitize_i2c_port(arg_port: int) -> int:
    # Telemetrix v1.43 既定は 1。0は不正/未定義動作になりがちなので 1 に固定。
    if arg_port != 1:
        print(f"[WARN] Telemetrix v1.43 expects i2c_port=1. Forcing to 1 (was {arg_port}).")
    return 1

def i2c_init_compat(board, i2c_port):
    try:
        board.set_pin_mode_i2c(i2c_port=i2c_port)  # v1.43でOK
    except TypeError:
        board.set_pin_mode_i2c()
    time.sleep(0.1)

def i2c_read_once_sync(board, addr, reg, n, i2c_port, timeout=0.2):
    """
    v1.43 仕様: callback必須。Eventで疑似同期。
    戻り: (hi, lo) または None
    """
    res = {"tail2": None}
    evt = threading.Event()

    def cb(data):
        if data and len(data) >= 2:
            hi = int(round(data[-2])) & 0xFF
            lo = int(round(data[-1])) & 0xFF
            res["tail2"] = (hi, lo)
            evt.set()

    try:
        board.i2c_read(addr, reg, n, cb, i2c_port=i2c_port)
    except TypeError:
        board.i2c_read(addr, reg, n, cb)

    evt.wait(timeout)
    return res["tail2"]

def angle_from_tail2(tail2):
    hi, lo = tail2
    val12 = ((hi << 8) | lo) & 0x0FFF
    return val12 * (360.0 / 4096.0)

class MultiTurn:
    def __init__(self):
        self.prev = None
        self.acc  = 0.0
    def update(self, now_deg):
        if self.prev is None:
            self.prev = now_deg
            return self.acc
        d = now_deg - self.prev
        if d >  180.0: d -= 360.0
        if d < -180.0: d += 360.0
        self.acc += d
        self.prev = now_deg
        return self.acc

def clamp(v, lo, hi):
    return lo if v < lo else hi if v > hi else v

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--serial", default="/dev/ttyACM0")
    ap.add_argument("--i2c", type=int, default=1)  # ユーザ入力は受けるが最終的に 1 に強制
    ap.add_argument("--servo-pin", type=int, default=9)
    ap.add_argument("--mode", choices=["follow","sweep"], default="follow")
    ap.add_argument("--scale", type=float, default=0.5)
    ap.add_argument("--bias",  type=float, default=0.0)
    ap.add_argument("--min", type=float, default=60.0)
    ap.add_argument("--max", type=float, default=120.0)
    ap.add_argument("--period", type=float, default=3.0)
    ap.add_argument("--rate", type=float, default=40.0)  # 少し下げてバスに余裕
    args = ap.parse_args()

    # v1.43 安全のため i2c_port=1 を強制
    args.i2c = sanitize_i2c_port(args.i2c)

    board = telemetrix.Telemetrix(com_port=args.serial)
    board.set_pin_mode_servo(args.servo_pin)
    i2c_init_compat(board, args.i2c)

    # ポインタ合わせ（捨て読み）
    _ = i2c_read_once_sync(board, ADDR, REG_ANGLE_H, 2, args.i2c, timeout=0.1)
    time.sleep(0.02)

    mt = MultiTurn()
    center = 0.5 * (args.min + args.max)
    amp    = 0.5 * (args.max - args.min)
    period = max(0.2, args.period)

    last_servo = None
    dt = 1.0 / max(args.rate, 1.0)
    t0 = time.time()

    print(f"[INFO] I2C ready (port={args.i2c}), servo pin D{args.servo_pin}, mode={args.mode}")
    try:
        while True:
            tail2 = i2c_read_once_sync(board, ADDR, REG_ANGLE_H, 2, args.i2c, timeout=0.1)
            angle_deg = angle_from_tail2(tail2) if tail2 is not None else None

            if args.mode == "sweep":
                t = time.time() - t0
                servo_deg = center + amp * math.sin(2.0 * math.pi * t / period)
            else:  # follow
                if angle_deg is None:
                    servo_deg = last_servo if last_servo is not None else 90.0
                else:
                    servo_deg = angle_deg * args.scale + args.bias

            servo_deg = clamp(servo_deg, 0.0, 180.0)
            s_int = int(round(servo_deg))
            if s_int != last_servo:
                board.servo_write(args.servo_pin, s_int)
                last_servo = s_int

            if angle_deg is not None:
                acc = mt.update(angle_deg)
                print(f"servo={servo_deg:6.1f}°  as5600={angle_deg:7.2f}°  multi={acc:9.2f}°   ", end="\r")
            else:
                print(f"servo={servo_deg:6.1f}°  as5600=---                             ", end="\r")

            time.sleep(dt)
    except KeyboardInterrupt:
        pass
    finally:
        board.shutdown()
        print("\nBye.")

if __name__ == "__main__":
    main()

