#!/usr/bin/env python3
"""
=============================================================
 test_trigger.py — RTC無し・PC時刻でサーボ動作テスト
=============================================================
使い方:
  python test_trigger.py --in 10                # 今から10秒後
  python test_trigger.py --time 14:30           # 14:30 にトリガー
  python test_trigger.py --time 07:00 --repeat  # 毎日繰り返し
  python test_trigger.py --time 14:30 --port COM3         # Windows
  python test_trigger.py --time 14:30 --port /dev/ttyACM0 # Linux/Mac
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
    parser = argparse.ArgumentParser(
        description="RTC無し・PC時刻でArduinoサーボをテスト起動"
    )
    parser.add_argument("--port",      default=DEFAULT_PORT)
    parser.add_argument("--time",      default=None,
                        help="トリガー時刻 HH:MM 形式 (例: 07:00)")
    parser.add_argument("--in",        dest="in_sec", type=int, default=None,
                        help="今からN秒後にトリガー (例: --in 10)")
    parser.add_argument("--repeat",    action="store_true",
                        help="毎日同じ時刻に繰り返す")
    parser.add_argument("--open-deg",  type=int, default=180)
    parser.add_argument("--close-deg", type=int, default=0)
    parser.add_argument("--water-ms",  type=int, default=2000)
    return parser.parse_args()


def calc_trigger_time(args):
    now = datetime.datetime.now()
    if args.in_sec is not None:
        return now + datetime.timedelta(seconds=args.in_sec), False
    if args.time:
        try:
            hh, mm = map(int, args.time.split(":"))
        except ValueError:
            print(f"[ERROR] --time の形式が不正: {args.time} (例: 07:00)")
            sys.exit(1)
        trigger = now.replace(hour=hh, minute=mm, second=0, microsecond=0)
        if trigger <= now:
            trigger += datetime.timedelta(days=1)
            print(f"[INFO] 指定時刻は過去のため翌日に設定: "
                  f"{trigger.strftime('%Y-%m-%d %H:%M:%S')}")
        return trigger, args.repeat
    trigger = (now.replace(minute=0, second=0, microsecond=0)
               + datetime.timedelta(hours=1))
    return trigger, False


def open_serial_and_wait_boot(port):
    """
    DTR操作なしでシリアルポートをオープンし、
    Arduinoが起動済みであることを前提に通信を開始する。

    【原因確定済み】
    DTR操作（ser.dtr=True/False）はArduino R4 Minimaを
    リセットさせてしまい、コマンド送信タイミングと競合する。
    DTR操作なし・sleep(3)のみで安定動作することを確認済み。
    """
    print(f"[INFO] ポートオープン中: {port}")

    # DTR操作なし・そのままオープン
    ser = serial.Serial(port, BAUDRATE, timeout=1)

    # オープン直後の小さなグリッチを吸収するため3秒待機
    print(f"[INFO] 接続安定待ち (3秒)...")
    time.sleep(3)
    ser.reset_input_buffer()
    print(f"[INFO] 接続完了: {port}")
    return ser


def safe_write(ser, data: bytes, label=""):
    try:
        ser.reset_output_buffer()
        ser.write(data)
        ser.flush()
        if label:
            print(f"[SEND] {label}")
        return True
    except serial.SerialException as e:
        print(f"[ERROR] 送信失敗 ({label}): {e}")
        return False


def read_response(ser, timeout=5, stop_on=("Done", "ACK", "ERROR")):
    deadline = time.time() + timeout
    lines = []
    while time.time() < deadline:
        try:
            line = ser.readline().decode(errors='replace').strip()
        except serial.SerialException as e:
            print(f"[ERROR] 読み取り失敗: {e}")
            break
        if not line:
            continue
        lines.append(line)
        print(f"  [Arduino] {line}")
        if any(kw in line for kw in stop_on):
            break
    return lines


def send_cfg(ser, args, trigger_time):
    cfg = (f"CFG,{trigger_time.hour},{trigger_time.minute},"
           f"{args.open_deg},{args.close_deg},{args.water_ms}\n")
    if safe_write(ser, cfg.encode(), f"CFG: {cfg.strip()}"):
        resp = read_response(ser, timeout=3, stop_on=("ACK", "ERROR"))
        if not any("ACK" in l for l in resp):
            print("[WARN] CFG ACKが返りませんでした。Arduinoが受信できていない可能性あり。")


def send_trigger(ser):
    ser.reset_input_buffer()
    ser.reset_output_buffer()
    time.sleep(0.05)
    if safe_write(ser, b"TRIGGER\n", "TRIGGER コマンド"):
        resp = read_response(ser, timeout=8,
                             stop_on=("Done", "ERROR", "WATER"))
        if not resp:
            print("[WARN] Arduinoからの応答なし。TRIGGERが届いていない可能性あり。")


def countdown(trigger_time):
    last_msg = ""
    while True:
        now = datetime.datetime.now()
        remaining = (trigger_time - now).total_seconds()
        if remaining <= 0:
            print()
            return
        h = int(remaining // 3600)
        m = int((remaining % 3600) // 60)
        s = int(remaining % 60)
        msg = (f"\r[WAIT] トリガーまで: {h:02d}:{m:02d}:{s:02d}"
               f"  ({trigger_time.strftime('%H:%M:%S')} に実行)")
        if msg != last_msg:
            print(msg, end="", flush=True)
            last_msg = msg
        time.sleep(0.5)


def main():
    args = parse_args()
    trigger_time, repeat = calc_trigger_time(args)

    print("=" * 55)
    print(" Arduino サーボ 時刻指定テストツール (RTC無し)")
    print("=" * 55)
    print(f" ポート       : {args.port}")
    print(f" トリガー時刻 : {trigger_time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f" サーボOPEN   : {args.open_deg}°")
    print(f" サーボCLOSE  : {args.close_deg}°")
    print(f" 給水時間     : {args.water_ms}ms ({args.water_ms/1000:.1f}秒)")
    print(f" 繰り返し     : {'ON (毎日)' if repeat else 'OFF (1回のみ)'}")
    print("=" * 55)
    print("[INFO] Ctrl+C で終了\n")

    try:
        ser = open_serial_and_wait_boot(args.port)

        send_cfg(ser, args, trigger_time)

        while True:
            countdown(trigger_time)

            now = datetime.datetime.now()
            print(f"\n[FIRE] {now.strftime('%H:%M:%S')} — トリガー発火！")
            send_trigger(ser)

            if not repeat:
                print("[INFO] 1回実行完了。終了します。")
                break

            trigger_time += datetime.timedelta(days=1)
            print(f"[INFO] 次回トリガー: "
                  f"{trigger_time.strftime('%Y-%m-%d %H:%M:%S')}\n")

        ser.close()

    except serial.SerialException as e:
        print(f"\n[ERROR] シリアル接続失敗: {e}")
        print("  ポート確認: ls /dev/tty* (Linux/Mac) or デバイスマネージャ (Win)")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\n[INFO] ユーザーによる終了。")


if __name__ == "__main__":
    main()
