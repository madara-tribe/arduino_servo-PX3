#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AS5600 minimal reader via Telemetrix (callback)
- Telemetrix v1.43 など古い版でも動くように互換ラッパを実装
- I2C 初期化: set_pin_mode_i2c(i2c_port=◯) だけを最低限呼ぶ
- 読み取り: i2c_read(..., i2c_port=◯) だけを最低限呼ぶ
- 末尾2バイトは int にキャストして 12bit 化（環境差対策）
使い方:
  python as5600_read_min.py --serial /dev/ttyACM0 --i2c 1 --hz 50
  # もし 1 でダメなら:
  python as5600_read_min.py --i2c 0
"""
import time, argparse
from telemetrix import telemetrix

ADDR = 0x36
REG_ANGLE_H = 0x0E  # ANGLE high

# ---------- 互換ラッパ ----------
def i2c_init_compat(board, i2c_port):
    board.set_pin_mode_i2c(i2c_port=i2c_port)
    time.sleep(0.1)

def i2c_read_compat(board, addr, reg, n, cb, i2c_port, return_data=False):
    return board.i2c_read(addr, reg, n, cb, i2c_port=i2c_port)
        
# ---------- 角度変換 ----------
def angle_from_data_tail2(data):
    # 末尾2要素を int 化（float が来る環境があるため）
    hi = int(round(data[-2])) & 0xFF
    lo = int(round(data[-1])) & 0xFF
    val12 = ((hi << 8) | lo) & 0x0FFF
    return val12 * (360.0 / 4096.0)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--serial", default="/dev/ttyACM0", help="Arduino serial port")
    ap.add_argument("--i2c", type=int, default=1, help="Telemetrix I2C port (try 1, else 0)")
    ap.add_argument("--hz", type=float, default=50.0, help="read rate (Hz)")
    args = ap.parse_args()

    board = telemetrix.Telemetrix(com_port=args.serial)
    i2c_init_compat(board, args.i2c)

    print(f"I2C ready (port={args.i2c}). Reading AS5600 @0x36 (CTRL+C to stop)")

    # callback
    angle = None
    def on_i2c(data):
        nonlocal angle
        if data and len(data) >= 2:
            angle = angle_from_data_tail2(data)

    # 初回: レジスタポインタ合わせ
    i2c_read_compat(board, ADDR, REG_ANGLE_H, 2, on_i2c, i2c_port=args.i2c)
    time.sleep(0.02)

    period = 1.0 / max(args.hz, 1.0)
    try:
        while True:
            i2c_read_compat(board, ADDR, REG_ANGLE_H, 2, on_i2c, i2c_port=args.i2c)
            if angle is not None:
                print(f"{angle:8.3f} deg", end="\r")
            time.sleep(period)
    except KeyboardInterrupt:
        pass
    finally:
        board.shutdown(); print("\nBye.")

if __name__ == "__main__":
    main()

