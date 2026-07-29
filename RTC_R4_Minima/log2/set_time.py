#!/usr/bin/env python3
"""
=============================================================
 set_time.py  — RTC時刻設定 + サーボ・給水パラメータ設定
 (DTRリセット対策済み版)
=============================================================
使い方:
  python3 set_time.py                       # デフォルトポート
  python3 set_time.py /dev/ttyACM0          # ポート指定
  python3 set_time.py --port /dev/ttyACM0 --hour 7 --min 0
=============================================================
⚠️ 実行前に Arduino IDE のシリアルモニタを必ず閉じること！
   （開いたままだとACKを横取りされてタイムアウトになる）
=============================================================
"""

import serial
import datetime
import sys
import time
import argparse

DEFAULT_PORT = "/dev/ttyACM0"
BAUDRATE     = 9600


def parse_args():
    p = argparse.ArgumentParser(description="水やり装置 設定ツール")
    # 位置引数でもポート指定できるように（旧互換）
    p.add_argument("port_pos", nargs="?", default=None,
                   help="シリアルポート（位置引数・省略可）")
    p.add_argument("--port",      default=None)
    p.add_argument("--hour",      type=int, default=7)
    p.add_argument("--min",       type=int, default=0)
    p.add_argument("--open-deg",  type=int, default=180)
    p.add_argument("--close-deg", type=int, default=0)
    p.add_argument("--water-ms",  type=int, default=2000)
    p.add_argument("--time-only", action="store_true")
    p.add_argument("--cfg-only",  action="store_true")
    a = p.parse_args()
    a.port = a.port or a.port_pos or DEFAULT_PORT
    return a


def open_serial_no_reset(port):
    """
    DTR操作なしでオープンし、sleep(3)で安定を待つ。
    （DTRリセット問題の対策：serial_debug_report.md参照）
    ※オープン自体でリセットがかかる環境もあるため、
      オープン後は長め(3秒)に待つ。
    """
    print(f"[INFO] ポートオープン: {port}")
    ser = serial.Serial(port, BAUDRATE, timeout=1)
    print("[INFO] 接続安定待ち (3秒)...")
    time.sleep(3)
    ser.reset_input_buffer()
    return ser


def send_and_wait(ser, cmd, label, timeout=4, retry=2):
    """コマンド送信してACKを待つ。失敗時はリトライ"""
    for attempt in range(1, retry + 1):
        print(f"[SEND] {label} (試行{attempt}/{retry}): {cmd.strip()}")
        ser.reset_input_buffer()
        ser.write(cmd.encode())
        ser.flush()

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
        time.sleep(1)
    return False


def main():
    args = parse_args()

    print("=" * 50)
    print(" 自動水やり装置 設定ツール (DTR対策版)")
    print("=" * 50)
    print(f" ポート      : {args.port}")
    if not args.cfg_only:
        print(f" RTC時刻設定 : PC現在時刻を送信")
    if not args.time_only:
        print(f" 給水時刻    : {args.hour:02d}:{args.min:02d}")
        print(f" サーボOPEN  : {args.open_deg}°")
        print(f" サーボCLOSE : {args.close_deg}°")
        print(f" 給水時間    : {args.water_ms}ms")
    print("=" * 50)
    print("⚠️  IDEシリアルモニタは閉じましたか？\n")

    try:
        ser = open_serial_no_reset(args.port)

        ok_set = True
        ok_cfg = True

        # --- SET: RTC時刻設定 ---
        if not args.cfg_only:
            # 送信直前に時刻取得してズレ最小化
            now = datetime.datetime.now()
            set_cmd = now.strftime("SET,%Y,%m,%d,%H,%M,%S\n")
            ok_set = send_and_wait(ser, set_cmd, "RTC時刻設定(SET)")
            time.sleep(0.5)

        # --- CFG: パラメータ設定 ---
        if not args.time_only:
            cfg_cmd = (f"CFG,{args.hour},{args.min},"
                       f"{args.open_deg},{args.close_deg},"
                       f"{args.water_ms}\n")
            ok_cfg = send_and_wait(ser, cfg_cmd, "パラメータ設定(CFG)")

        ser.close()

        print()
        if ok_set and ok_cfg:
            print("[SUCCESS] 全設定完了。PCを切断してACアダプタで運用できます。")
        else:
            print("[FAILED] 設定に失敗しました。以下を確認:")
            print("  1. IDEシリアルモニタが閉じているか")
            print("  2. ポートが正しいか (ls /dev/ttyACM*)")
            print("  3. Arduinoの電源・USB接続")
            sys.exit(1)

    except serial.SerialException as e:
        print(f"[ERROR] シリアル接続失敗: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
