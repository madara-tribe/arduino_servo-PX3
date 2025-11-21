#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AS5600 + Servo dual test via Telemetrix (v1.43-safe, CSV logging)
Modes:
  follow : AS5600角度 -> サーボ角 (リアルタイム)
  sweep  : サーボ正弦スイープ（AS5600同時読出）

Telemetrix v1.43 対応:
- i2c_read は callback 必須（return_data / address_size なし）
- I2C ポートは 1 を強制（0 は不整合が出やすい）

CSV ロギング:
  --csv <path>    : CSV へ追記保存（ヘッダ含む）
  --csv-rate <Hz> : ログ出力の最大頻度（毎ループ記録だとファイルが大きい場合の間引き用）
  --csv-flush     : 各行 flush（障害時の取りこぼし防止）

例:
  python as5600_servo_dual_test.py --serial /dev/ttyACM0 --i2c 1 --mode follow --scale 0.5 \
    --csv run_follow.csv --csv-rate 20 --csv-flush
  python as5600_servo_dual_test.py --serial /dev/ttyACM0 --i2c 1 --mode sweep --min 60 --max 120 \
    --csv run_sweep.csv --period 3.0
"""

import time, math, argparse, threading, csv, sys
from telemetrix import telemetrix

# ---- AS5600 Registers ----
ADDR = 0x36
REG_ANGLE_H = 0x0E  # ANGLE high (0x0E/0x0F)
REG_STATUS  = 0x0B  # STATUS 1 byte (MD/ML/MH)

# ---- v1.43-safe: I2C init & one-shot read (callback mandatory) ----
def i2c_init(board, i2c_port):
    try:
        board.set_pin_mode_i2c(i2c_port=i2c_port)  # v1.43 OK
    except TypeError:
        board.set_pin_mode_i2c()
    time.sleep(0.1)

def i2c_read_once_sync(board, addr, reg, n, i2c_port, timeout=0.2):
    """callback必須のv1.43向け。Eventで疑似同期。末尾nバイトを返す。"""
    res = {"buf": None}
    evt = threading.Event()
    def cb(data):
        if data and len(data) >= n:
            res["buf"] = [int(round(x)) & 0xFF for x in data[-n:]]
            evt.set()
    try:
        board.i2c_read(addr, reg, n, cb, i2c_port=i2c_port)
    except TypeError:
        board.i2c_read(addr, reg, n, cb)
    evt.wait(timeout)
    return res["buf"]

def read_angle_deg(board, i2c_port, timeout=0.2):
    b = i2c_read_once_sync(board, ADDR, REG_ANGLE_H, 2, i2c_port, timeout)
    if not b: return None
    hi, lo = b
    val12 = ((hi << 8) | lo) & 0x0FFF
    return val12 * (360.0 / 4096.0)

def read_status(board, i2c_port, timeout=0.2):
    b = i2c_read_once_sync(board, ADDR, REG_STATUS, 1, i2c_port, timeout)
    if not b: return None, None, None
    st = b[0]
    md = (st >> 5) & 1  # Magnet detected
    ml = (st >> 4) & 1  # Magnet too low
    mh = (st >> 3) & 1  # Magnet too high
    return md, ml, mh

# ---- helpers ----
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
    ap.add_argument("--i2c", type=int, default=1)
    ap.add_argument("--servo-pin", type=int, default=9)
    ap.add_argument("--mode", choices=["follow","sweep"], default="follow")
    # follow mapping
    ap.add_argument("--scale", type=float, default=0.5, help="servo = as5600*scale + bias")
    ap.add_argument("--bias",  type=float, default=0.0)
    # sweep params
    ap.add_argument("--min", type=float, default=60.0)
    ap.add_argument("--max", type=float, default=120.0)
    ap.add_argument("--period", type=float, default=3.0)
    # loop
    ap.add_argument("--rate", type=float, default=40.0)
    # CSV logging
    ap.add_argument("--csv", default="", help="CSV path to save logs (optional)")
    ap.add_argument("--csv-rate", type=float, default=0.0,
                    help="Max CSV logging rate [Hz] (0=every loop)")
    ap.add_argument("--csv-flush", action="store_true", help="Flush each CSV line")
    args = ap.parse_args()

    # v1.43 安全のため i2c_port=1 を強制
    if args.i2c != 1:
        print(f"[WARN] Telemetrix v1.43 expects i2c_port=1. Forcing to 1 (was {args.i2c}).", flush=True)
        args.i2c = 1

    board = telemetrix.Telemetrix(com_port=args.serial)
    board.set_pin_mode_servo(args.servo_pin)
    i2c_init(board, args.i2c)

    # status snapshot
    md, ml, mh = read_status(board, args.i2c, 0.3)
    if md is not None:
        print(f"[INFO] STATUS: MD={md} ML={ml} MH={mh}", flush=True)
        if md == 0:
            print("[WARN] Magnet not detected (MD=0). Adjust magnet gap/centering.", flush=True)

    # CSV 準備
    csv_writer = None
    csv_file   = None
    next_csv_ts = 0.0
    if args.csv:
        try:
            csv_file = open(args.csv, "w", newline="")
            csv_writer = csv.writer(csv_file)
            csv_writer.writerow(["t_s","mode","servo_deg","as5600_deg","multi_deg","MD","ML","MH","i2c_port"])
            if args.csv_flush: csv_file.flush()
            print(f"[INFO] CSV logging to: {args.csv}", flush=True)
        except Exception as e:
            print(f"[ERROR] CSV open failed: {e}", flush=True)

    # ループ準備
    mt = MultiTurn()
    center = 0.5 * (args.min + args.max)
    amp    = 0.5 * (args.max - args.min)
    period = max(0.2, args.period)
    last_servo = None
    dt = 1.0 / max(args.rate, 1.0)
    t0 = time.time()

    print(f"[INFO] I2C ready (port={args.i2c}), servo pin D{args.servo_pin}, mode={args.mode}", flush=True)
    try:
        while True:
            # 1) read AS5600
            angle_deg = read_angle_deg(board, args.i2c, timeout=0.15)

            # 2) compute servo command
            if args.mode == "sweep":
                t = time.time() - t0
                servo_deg = center + amp * math.sin(2.0 * math.pi * t / period)
            else:  # follow
                if angle_deg is None:
                    servo_deg = last_servo if last_servo is not None else 90.0
                else:
                    servo_deg = angle_deg * args.scale + args.bias

            servo_deg = clamp(servo_deg, 0.0, 180.0)

            # 3) write servo
            s_int = int(round(servo_deg))
            if s_int != last_servo:
                board.servo_write(args.servo_pin, s_int)
                last_servo = s_int

            # 4) compute multi-turn & status (statusは重いのでたまに）
            multi = None
            if angle_deg is not None:
                multi = mt.update(angle_deg)

            now = time.time()
            # statusは0.5秒ごとに更新
            if int((now - t0)*2) != int((now - t0 - dt)*2):
                md, ml, mh = read_status(board, args.i2c, 0.15)

            # 5) console
            if angle_deg is not None:
                print(f"servo={servo_deg:6.1f}°  as5600={angle_deg:7.2f}°  multi={multi:9.2f}°   ",
                      end="\r", flush=True)
            else:
                print(f"servo={servo_deg:6.1f}°  as5600=---                             ",
                      end="\r", flush=True)

            # 6) CSV logging
            if csv_writer:
                if args.csv_rate <= 0.0 or now >= next_csv_ts:
                    row = [f"{now-t0:.3f}", args.mode,
                           f"{servo_deg:.3f}",
                           ("" if angle_deg is None else f"{angle_deg:.3f}"),
                           ("" if multi    is None else f"{multi:.3f}"),
                           ("" if md is None else md),
                           ("" if ml is None else ml),
                           ("" if mh is None else mh),
                           1]
                    csv_writer.writerow(row)
                    if args.csv_flush: csv_file.flush()
                    if args.csv_rate > 0.0:
                        next_csv_ts = now + 1.0/args.csv_rate

            time.sleep(dt)
    except KeyboardInterrupt:
        pass
    finally:
        try:
            if csv_file: csv_file.close()
        except Exception:
            pass
        board.shutdown()
        print("\nBye.", flush=True)

if __name__ == "__main__":
    # 行バッファが効かない環境向けのフォールバック
    try:
        sys.stdout.reconfigure(line_buffering=False)
    except Exception:
        pass
    main()

