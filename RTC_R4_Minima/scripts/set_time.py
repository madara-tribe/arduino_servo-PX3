#!/usr/bin/env python3
"""
=============================================================
 set_time.py  — RTC時刻設定 + サーボ・給水パラメータ設定
=============================================================
使い方:
  python set_time.py                        # デフォルト設定
  python set_time.py --port /dev/ttyUSB0   # ポート指定
  python set_time.py --port COM3           # Windows

送信コマンド一覧 (Arduinoへのシリアル):
  SET,YYYY,MM,DD,HH,mm,ss  → RTC時刻設定
  CFG,HH,mm,OPEN,CLOSE,MS  → 給水時刻・サーボ角度・給水時間設定
=============================================================
"""

import serial
import datetime
import sys
import time
import argparse

# ===== デフォルト設定 =====
DEFAULT_PORT      = "/dev/ttyUSB0"
BAUDRATE          = 9600

DEFAULT_HOUR      = 7     # 給水時刻（時）
DEFAULT_MIN       = 0     # 給水時刻（分）
DEFAULT_OPEN_DEG  = 180   # サーボOPEN角度
DEFAULT_CLOSE_DEG = 0     # サーボCLOSE角度
DEFAULT_WATER_MS  = 2000  # 給水時間 [ms]


def parse_args():
    parser = argparse.ArgumentParser(description="Arduino水やり装置 設定ツール")
    parser.add_argument("--port",      default=DEFAULT_PORT,      help="シリアルポート (default: /dev/ttyUSB0)")
    parser.add_argument("--hour",      type=int, default=DEFAULT_HOUR,      help="給水時刻 時 (0-23, default: 7)")
    parser.add_argument("--min",       type=int, default=DEFAULT_MIN,       help="給水時刻 分 (0-59, default: 0)")
    parser.add_argument("--open-deg",  type=int, default=DEFAULT_OPEN_DEG,  help="サーボOPEN角度 (0-180, default: 180)")
    parser.add_argument("--close-deg", type=int, default=DEFAULT_CLOSE_DEG, help="サーボCLOSE角度 (0-180, default: 0)")
    parser.add_argument("--water-ms",  type=int, default=DEFAULT_WATER_MS,  help="給水時間ms (default: 2000)")
    parser.add_argument("--time-only", action="store_true", help="RTC時刻設定のみ（CFG送信しない）")
    parser.add_argument("--cfg-only",  action="store_true", help="CFG設定のみ（SET送信しない）")
    return parser.parse_args()


def validate(args):
    errors = []
    if not (0 <= args.hour <= 23):
        errors.append(f"--hour は 0〜23 で指定 (got {args.hour})")
    if not (0 <= args.min <= 59):
        errors.append(f"--min は 0〜59 で指定 (got {args.min})")
    if not (0 <= args.open_deg <= 180):
        errors.append(f"--open-deg は 0〜180 で指定 (got {args.open_deg})")
    if not (0 <= args.close_deg <= 180):
        errors.append(f"--close-deg は 0〜180 で指定 (got {args.close_deg})")
    if args.water_ms < 100:
        errors.append(f"--water-ms は 100ms 以上で指定 (got {args.water_ms})")
    if errors:
        for e in errors:
            print(f"[ERROR] {e}")
        sys.exit(1)


def send_and_wait(ser, cmd, label, timeout=3):
    """コマンド送信してACKを待つ"""
    print(f"[SEND] {label}: {cmd.strip()}")
    ser.write(cmd.encode())
    deadline = time.time() + timeout
    while time.time() < deadline:
        line = ser.readline().decode(errors='replace').strip()
        if not line:
            continue
        print(f"  [Arduino] {line}")
        if "ACK" in line:
            print(f"  [OK] {label} 完了")
            return True
    print(f"  [WARN] {label}: ACKタイムアウト")
    return False


def main():
    args = parse_args()
    validate(args)

    print("=" * 50)
    print(" 自動水やり装置 設定ツール")
    print("=" * 50)
    print(f" ポート      : {args.port}")
    if not args.cfg_only:
        now = datetime.datetime.now()
        print(f" RTC時刻設定 : {now.strftime('%Y-%m-%d %H:%M:%S')}")
    if not args.time_only:
        print(f" 給水時刻    : {args.hour:02d}:{args.min:02d}")
        print(f" サーボOPEN  : {args.open_deg}°")
        print(f" サーボCLOSE : {args.close_deg}°")
        print(f" 給水時間    : {args.water_ms}ms ({args.water_ms/1000:.1f}秒)")
    print("=" * 50)

    try:
        with serial.Serial(args.port, BAUDRATE, timeout=3) as ser:
            print(f"\n[INFO] 接続中... (Arduino リセット待ち 2秒)")
            time.sleep(2)

            # --- SET: RTC時刻設定 ---
            if not args.cfg_only:
                now = datetime.datetime.now()
                set_cmd = now.strftime("SET,%Y,%m,%d,%H,%M,%S\n")
                send_and_wait(ser, set_cmd, "RTC時刻設定(SET)")
                time.sleep(0.5)

            # --- CFG: サーボ・給水パラメータ設定 ---
            if not args.time_only:
                cfg_cmd = (
                    f"CFG,"
                    f"{args.hour},"
                    f"{args.min},"
                    f"{args.open_deg},"
                    f"{args.close_deg},"
                    f"{args.water_ms}\n"
                )
                send_and_wait(ser, cfg_cmd, "パラメータ設定(CFG)")

            print("\n[INFO] 設定完了。PCを切断してACアダプタのみで動作します。")

    except serial.SerialException as e:
        print(f"\n[ERROR] シリアル接続失敗: {e}")
        print("  ポート確認: ls /dev/tty* (Linux/Mac) or デバイスマネージャ (Win)")
        sys.exit(1)


if __name__ == "__main__":
    main()
