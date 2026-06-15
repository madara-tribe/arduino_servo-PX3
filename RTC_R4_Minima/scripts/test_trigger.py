#!/usr/bin/env python3
"""
=============================================================
 test_trigger.py — RTC無し・PC時刻でサーボ動作テスト
=============================================================
PCのシステム時刻を監視し、指定時刻になったら
シリアル経由でArduinoにトリガーコマンドを送信する。

使い方:
  python test_trigger.py                      # デフォルト: 次の毎時0分
  python test_trigger.py --time 14:30         # 14:30 にトリガー
  python test_trigger.py --time 14:30 --port COM3        # Windows
  python test_trigger.py --time 14:30 --port /dev/ttyACM0  # Linux/Mac
  python test_trigger.py --time 14:30 --repeat           # 毎日繰り返し
  python test_trigger.py --in 10             # 今から10秒後にトリガー（秒指定）

送信コマンド: "TRIGGER\n"
Arduino側が "TRIGGER" を受信したら doWater() を即時実行する。
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
    parser.add_argument("--port",   default=DEFAULT_PORT,
                        help="シリアルポート (default: /dev/ttyACM0)")
    parser.add_argument("--time",   default=None,
                        help="トリガー時刻 HH:MM 形式 (例: 07:00)")
    parser.add_argument("--in",     dest="in_sec", type=int, default=None,
                        help="今からN秒後にトリガー (例: --in 10)")
    parser.add_argument("--repeat", action="store_true",
                        help="毎日同じ時刻に繰り返す")
    parser.add_argument("--open-deg",  type=int, default=180,
                        help="サーボOPEN角度 (default: 180)")
    parser.add_argument("--close-deg", type=int, default=0,
                        help="サーボCLOSE角度 (default: 0)")
    parser.add_argument("--water-ms",  type=int, default=2000,
                        help="給水時間ms (default: 2000)")
    return parser.parse_args()


def calc_trigger_time(args):
    """トリガー時刻を決定する"""
    now = datetime.datetime.now()

    # --in N: N秒後
    if args.in_sec is not None:
        return now + datetime.timedelta(seconds=args.in_sec), False

    # --time HH:MM
    if args.time:
        try:
            hh, mm = map(int, args.time.split(":"))
        except ValueError:
            print(f"[ERROR] --time の形式が不正です: {args.time} (例: 07:00)")
            sys.exit(1)
        trigger = now.replace(hour=hh, minute=mm, second=0, microsecond=0)
        if trigger <= now:
            trigger += datetime.timedelta(days=1)
            print(f"[INFO] 指定時刻は過去のため翌日に設定: {trigger.strftime('%Y-%m-%d %H:%M:%S')}")
        return trigger, args.repeat

    # デフォルト: 次の毎時0分
    trigger = now.replace(minute=0, second=0, microsecond=0) + datetime.timedelta(hours=1)
    return trigger, False


def send_trigger(ser):
    """TRIGGERコマンドをArduinoに送信"""
    ser.write(b"TRIGGER\n")
    print(f"[SEND] TRIGGER コマンド送信")
    time.sleep(0.5)
    lines = []
    deadline = time.time() + 5
    while time.time() < deadline:
        line = ser.readline().decode(errors='replace').strip()
        if not line:
            break
        lines.append(line)
        print(f"  [Arduino] {line}")
        if "Done" in line or "WATER" in line:
            break
    return lines


def countdown(trigger_time):
    """トリガー時刻までカウントダウン表示"""
    last_print = ""
    while True:
        now = datetime.datetime.now()
        remaining = (trigger_time - now).total_seconds()
        if remaining <= 0:
            print()
            return
        h = int(remaining // 3600)
        m = int((remaining % 3600) // 60)
        s = int(remaining % 60)
        msg = f"\r[WAIT] トリガーまで: {h:02d}:{m:02d}:{s:02d}  ({trigger_time.strftime('%H:%M:%S')} に実行)"
        if msg != last_print:
            print(msg, end="", flush=True)
            last_print = msg
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
        with serial.Serial(args.port, BAUDRATE, timeout=3) as ser:
            print(f"[INFO] 接続完了: {args.port}")
            time.sleep(2)  # Arduino reset待ち

            # CFG送信（サーボ角度・給水時間を設定）
            cfg = (f"CFG,{trigger_time.hour},{trigger_time.minute},"
                   f"{args.open_deg},{args.close_deg},{args.water_ms}\n")
            ser.write(cfg.encode())
            time.sleep(0.5)
            line = ser.readline().decode(errors='replace').strip()
            if line:
                print(f"[Arduino] {line}")

            while True:
                countdown(trigger_time)

                now = datetime.datetime.now()
                print(f"\n[FIRE] {now.strftime('%H:%M:%S')} — トリガー発火！")
                send_trigger(ser)

                if not repeat:
                    print("[INFO] 1回実行完了。終了します。")
                    break

                # 繰り返し: 翌日同じ時刻
                trigger_time += datetime.timedelta(days=1)
                print(f"[INFO] 次回トリガー: {trigger_time.strftime('%Y-%m-%d %H:%M:%S')}\n")

    except serial.SerialException as e:
        print(f"\n[ERROR] シリアル接続失敗: {e}")
        print("  ポート確認: ls /dev/tty* (Linux/Mac) or デバイスマネージャ (Win)")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\n[INFO] ユーザーによる終了。")


if __name__ == "__main__":
    main()
