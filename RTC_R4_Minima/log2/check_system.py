#!/usr/bin/env python3
"""
=============================================================
 check_system.py — サーボ・RTC 動作検査スクリプト
=============================================================
検査項目:
  [1] シリアル通信の生存確認 ([TIME]ログ受信)
  [2] RTC動作確認 (時刻が進んでいるか)
  [3] RTC時刻設定テスト (SET送信→時刻変化を確認)
  [4] サーボ動作テスト (TRIGGER送信→WATER応答確認)

使い方:
  python3 check_system.py                    # デフォルトポート
  python3 check_system.py /dev/ttyACM1       # ポート指定

⚠️ 実行前に Arduino IDE のシリアルモニタを必ず閉じること！
=============================================================
"""

import serial
import datetime
import sys
import time
import re

PORT     = sys.argv[1] if len(sys.argv) > 1 else "/dev/ttyACM0"
BAUDRATE = 9600

results = {}


def open_serial(port):
    print(f"[INFO] ポートオープン: {port}")
    ser = serial.Serial(port, BAUDRATE, timeout=1)
    print("[INFO] 接続安定待ち (3秒)...")
    time.sleep(3)
    ser.reset_input_buffer()
    return ser


def listen(ser, seconds, pattern=None):
    """指定秒数ログを収集。patternにマッチした行を返す"""
    lines = []
    matched = []
    deadline = time.time() + seconds
    while time.time() < deadline:
        line = ser.readline().decode(errors='replace').strip()
        if not line:
            continue
        lines.append(line)
        print(f"  [Arduino] {line}")
        if pattern and re.search(pattern, line):
            matched.append(line)
    return lines, matched


def parse_time_log(line):
    """'[TIME] 22:15  done_today=false' から (h, m) を抽出"""
    m = re.search(r"\[TIME\]\s+(\d+):(\d+)", line)
    if m:
        return int(m.group(1)), int(m.group(2))
    return None


# ═══════════════════════════════════════════
# 検査 [1] シリアル通信の生存確認
# ═══════════════════════════════════════════
def test1_serial_alive(ser):
    print("\n" + "=" * 50)
    print(" 検査[1] シリアル通信の生存確認 (15秒待機)")
    print("=" * 50)
    print("[INFO] Arduinoからの[TIME]ログを待っています...")
    lines, matched = listen(ser, 15, r"\[TIME\]")
    if matched:
        print("[PASS] シリアル通信OK。Arduinoは動作中。")
        results["serial"] = True
        return matched
    elif lines:
        print("[WARN] ログは受信できたが[TIME]が無い。")
        print("       → USE_RTCが無効(テストモード)の可能性。")
        results["serial"] = True
        return []
    else:
        print("[FAIL] 何も受信できない。")
        print("       → ポート違い / シリアルモニタ開きっぱなし /")
        print("         Arduino停止(RTC not found→while(1))を確認。")
        results["serial"] = False
        return []


# ═══════════════════════════════════════════
# 検査 [2] RTCが時を刻んでいるか
# ═══════════════════════════════════════════
def test2_rtc_ticking(ser, first_logs):
    print("\n" + "=" * 50)
    print(" 検査[2] RTC動作確認 (時刻が進んでいるか)")
    print("=" * 50)

    t1 = None
    for line in reversed(first_logs):
        t1 = parse_time_log(line)
        if t1:
            break

    if not t1:
        print("[SKIP] [TIME]ログが無いため検査不可。")
        results["rtc_tick"] = None
        return

    print(f"[INFO] 現在のRTC時刻: {t1[0]}:{t1[1]:02d}")
    if t1 == (0, 0):
        print("[WARN] RTC時刻が 0:00 → 時刻が未設定の状態。")
        print("       (RTC自体は生きているが SET が未達)")

    print("[INFO] 70秒待って時刻が進むか確認します...")
    lines, matched = listen(ser, 70, r"\[TIME\]")
    t2 = None
    for line in reversed(matched):
        t2 = parse_time_log(line)
        if t2:
            break

    if t2 and (t2 != t1):
        print(f"[PASS] RTCは時を刻んでいる: {t1[0]}:{t1[1]:02d} → {t2[0]}:{t2[1]:02d}")
        results["rtc_tick"] = True
    elif t2:
        print(f"[FAIL] 70秒経っても時刻が変わらない: {t2[0]}:{t2[1]:02d}")
        print("       → RTC水晶停止 or 電池問題の可能性。")
        results["rtc_tick"] = False
    else:
        print("[FAIL] [TIME]ログが取得できなかった。")
        results["rtc_tick"] = False


# ═══════════════════════════════════════════
# 検査 [3] RTC時刻設定テスト
# ═══════════════════════════════════════════
def test3_rtc_set(ser):
    print("\n" + "=" * 50)
    print(" 検査[3] RTC時刻設定テスト (SET送信)")
    print("=" * 50)

    now = datetime.datetime.now()
    cmd = now.strftime("SET,%Y,%m,%d,%H,%M,%S\n")
    print(f"[SEND] {cmd.strip()}")
    ser.reset_input_buffer()
    ser.write(cmd.encode())
    ser.flush()

    lines, matched = listen(ser, 5, r"ACK.*[Tt]ime")
    if matched:
        print("[PASS] SET成功。ACK受信。")
        results["rtc_set"] = True
    else:
        print("[FAIL] SETのACKが返らない。")
        results["rtc_set"] = False
        return

    # 設定後の時刻を確認
    print(f"[INFO] 設定した時刻 {now.hour}:{now.minute:02d} が反映されるか確認...")
    lines, matched = listen(ser, 15, r"\[TIME\]")
    for line in reversed(matched):
        t = parse_time_log(line)
        if t:
            if abs(t[0] - now.hour) == 0 and abs(t[1] - now.minute) <= 1:
                print(f"[PASS] RTC時刻が正しく反映: {t[0]}:{t[1]:02d}")
                results["rtc_reflect"] = True
            else:
                print(f"[FAIL] 時刻が反映されていない: {t[0]}:{t[1]:02d}")
                results["rtc_reflect"] = False
            return
    print("[WARN] 反映確認用の[TIME]ログが取れなかった。")
    results["rtc_reflect"] = None


# ═══════════════════════════════════════════
# 検査 [4] サーボ動作テスト
# ═══════════════════════════════════════════
def test4_servo(ser):
    print("\n" + "=" * 50)
    print(" 検査[4] サーボ動作テスト (TRIGGER送信)")
    print("=" * 50)
    print("[INFO] サーボが動くか目視で確認してください！")

    ser.reset_input_buffer()
    ser.write(b"TRIGGER\n")
    ser.flush()
    print("[SEND] TRIGGER")

    lines, matched = listen(ser, 10, r"WATER.*Done|Done")
    started = any("Start" in l for l in lines)
    done    = any("Done" in l for l in lines)

    if started and done:
        print("[PASS] サーボ制御シーケンス完了 (Start→Done)。")
        results["servo"] = True
    elif started:
        print("[WARN] Startは出たがDoneが確認できず。")
        results["servo"] = None
    else:
        print("[FAIL] TRIGGERへの応答なし。")
        results["servo"] = False


# ═══════════════════════════════════════════
# メイン
# ═══════════════════════════════════════════
def main():
    print("=" * 50)
    print(" 水やり装置 システム検査ツール")
    print("=" * 50)
    print(f" ポート: {PORT}")
    print("⚠️  IDEシリアルモニタは閉じましたか？")
    print("=" * 50)

    try:
        ser = open_serial(PORT)
    except serial.SerialException as e:
        print(f"[ERROR] 接続失敗: {e}")
        print(f"  ls /dev/ttyACM* でポートを確認してください")
        sys.exit(1)

    first_logs = test1_serial_alive(ser)
    if results.get("serial"):
        test2_rtc_ticking(ser, first_logs)
        test3_rtc_set(ser)
        test4_servo(ser)

    ser.close()

    # ═══ 最終レポート ═══
    print("\n" + "=" * 50)
    print(" 検査結果サマリ")
    print("=" * 50)
    names = {
        "serial":      "[1] シリアル通信",
        "rtc_tick":    "[2] RTC時刻進行",
        "rtc_set":     "[3] RTC時刻設定(SET)",
        "rtc_reflect": "[3+] 設定時刻の反映",
        "servo":       "[4] サーボ動作",
    }
    for key, name in names.items():
        v = results.get(key)
        mark = "✅ PASS" if v else ("❌ FAIL" if v is False else "⚠️  SKIP/WARN")
        print(f"  {name:<22} {mark}")
    print("=" * 50)

    if all(v for v in results.values() if v is not None):
        print("🎉 全検査パス。本番運用に進めます。")
    else:
        print("⚠️  FAILがある場合は各検査のメッセージを確認してください。")


if __name__ == "__main__":
    main()
