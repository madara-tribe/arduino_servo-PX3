#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AS5600 debug reader via Telemetrix (callback / poll)
- Telemetrix v1.43 など古い版でも動くように互換ラッパを実装
- poll モードは return_data が未サポートの版でも、
  callback を使った疑似同期でフォールバック可能
使い方:
  # まず callback で port=1
  python as5600_read_debug.py --serial /dev/ttyACM0 --i2c 1 --mode callback
  # ダメなら port=0
  python as5600_read_debug.py --serial /dev/ttyACM0 --i2c 0 --mode callback
  # さらに切り分け：poll
  python as5600_read_debug.py --serial /dev/ttyACM0 --i2c 1 --mode poll
"""
import time, argparse, threading
from telemetrix import telemetrix

ADDR = 0x36
REG_ANGLE_H = 0x0E

# ---- 互換ラッパ（min と同じ） ----
def i2c_init_compat(board, i2c_port):
    try:
        board.set_pin_mode_i2c(i2c_port=i2c_port, enable_pullups=True)
    except TypeError:
        try:
            board.set_pin_mode_i2c(i2c_port=i2c_port)
        except TypeError:
            board.set_pin_mode_i2c()
    time.sleep(0.1)

def i2c_read_compat(board, addr, reg, n, cb, i2c_port, return_data=False):
    try:
        return board.i2c_read(addr, reg, n, cb, i2c_port=i2c_port,
                              address_size=8, return_data=return_data)
    except TypeError:
        try:
            return board.i2c_read(addr, reg, n, cb, i2c_port=i2c_port,
                                  return_data=return_data)
        except TypeError:
            return board.i2c_read(addr, reg, n, cb)

def angle_from_data_tail2(data):
    hi = int(round(data[-2])) & 0xFF
    lo = int(round(data[-1])) & 0xFF
    val12 = ((hi << 8) | lo) & 0x0FFF
    return val12 * (360.0 / 4096.0)

def poll_once(board, i2c_port, timeout=0.2):
    """
    同期読み（return_data が使えない版でも疑似同期で返す）
    """
    # 1) try return_data path
    try:
        data = i2c_read_compat(board, ADDR, REG_ANGLE_H, 2, None,
                               i2c_port=i2c_port, return_data=True)
        if data and len(data) >= 2:
            return angle_from_data_tail2(data)
    except TypeError:
        pass

    # 2) fallback: callback + 短い待ち
    result = {"deg": None}
    evt = threading.Event()

    def cb(d):
        if d and len(d) >= 2:
            result["deg"] = angle_from_data_tail2(d)
            evt.set()

    i2c_read_compat(board, ADDR, REG_ANGLE_H, 2, cb, i2c_port=i2c_port)
    evt.wait(timeout)
    return result["deg"]

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--serial", default="/dev/ttyACM0")
    ap.add_argument("--i2c", type=int, default=1)
    ap.add_argument("--hz", type=float, default=50.0)
    ap.add_argument("--mode", choices=["callback","poll"], default="callback")
    args = ap.parse_args()

    board = telemetrix.Telemetrix(com_port=args.serial)
    i2c_init_compat(board, args.i2c)

    print(f"I2C ready (port={args.i2c}). Reading AS5600 @0x36 ({args.mode})")

    if args.mode == "poll":
        # 初回: ポインタ合わせ
        i2c_read_compat(board, ADDR, REG_ANGLE_H, 2, None, i2c_port=args.i2c)
        time.sleep(0.02)
        try:
            while True:
                deg = poll_once(board, args.i2c, timeout=0.2)
                if deg is not None:
                    print(f"{deg:8.3f} deg", end="\r")
                else:
                    print("no data   ", end="\r")
                time.sleep(1.0 / max(args.hz, 1.0))
        except KeyboardInterrupt:
            pass
        finally:
            board.shutdown(); print("\nBye.")
        return

    # callback
    angle = None
    def on_i2c(data):
        nonlocal angle
        if data and len(data) >= 2:
            angle = angle_from_data_tail2(data)

    i2c_read_compat(board, ADDR, REG_ANGLE_H, 2, on_i2c, i2c_port=args.i2c)
    time.sleep(0.02)

    try:
        while True:
            i2c_read_compat(board, ADDR, REG_ANGLE_H, 2, on_i2c, i2c_port=args.i2c)
            if angle is not None:
                print(f"{angle:8.3f} deg", end="\r")
            time.sleep(1.0 / max(args.hz, 1.0))
    except KeyboardInterrupt:
        pass
    finally:
        board.shutdown(); print("\nBye.")

if __name__ == "__main__":
    main()

