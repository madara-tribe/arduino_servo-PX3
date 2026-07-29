# Arduino シリアル通信デバッグレポート

**日付**: 2026-06-15  
**対象**: Arduino UNO R4 Minima + SG90 サーボ 自動水やり装置  
**症状**: Python から TRIGGER コマンドを送信してもサーボが動かない

---

## 問題

`test_trigger.py` を実行しても、サーボが動作しない。

### 症状のログ

```
[INFO] ポートオープン中: /dev/ttyACM0
[INFO] Arduino リセット → 起動完了を待機中 (最大6秒)...
[WARN] 起動ログ待ちタイムアウト。そのまま続行します。
[SEND] CFG: CFG,14,28,180,0,2000
[WARN] CFG ACKが返りませんでした。Arduinoが受信できていない可能性あり。
[WAIT] トリガーまで: 00:00:00  (14:28:00 に実行)

[FIRE] 14:28:00 — トリガー発火！
[SEND] TRIGGER コマンド
[WARN] Arduinoからの応答なし。TRIGGERが届いていない可能性あり。
[INFO] 1回実行完了。終了します。
```

### 切り分けで判明したこと

| 確認内容 | 結果 |
|---------|------|
| inoの書き込み | ✅ 正常 |
| サーボ配線 | ✅ 正常（RESETボタンで動作確認） |
| IDE シリアルモニタで `TRIGGER` 手入力 | ✅ サーボ動いた |
| Python コード実行 | ❌ サーボ動かない |

→ **Arduino 側・サーボ配線・ino コードはすべて正常**。  
→ 問題は **Python ↔ Arduino 間のシリアル通信**に絞られた。

---

## 原因

### 根本原因：DTR 操作が Arduino を意図せずリセットしていた

`test_trigger.py` の `open_serial_and_wait_boot()` 内で、
シリアル通信の同期を取る目的で以下の DTR 操作を行っていた。

```python
# 問題のコード
ser = serial.Serial(port, BAUDRATE, timeout=1)
ser.dtr = True   # DTR High → Arduino リセット開始
time.sleep(0.2)  # 0.2秒待機
ser.dtr = False  # DTR Low  → リセット解除
```

### 何が起きていたか（時系列）

```
Python 実行
    ↓
ser.dtr = True/False → Arduino R4 Minima がリセット開始
    ↓
Arduino 再起動中（実際には 2〜3 秒かかる）
    ↓
起動ログ待ち 6 秒タイムアウト（起動中のため何も返ってこない）
    ↓
CFG 送信 → Arduino まだ起動中 → 受信できない → ACK なし
    ↓
TRIGGER 送信 → 同上 → 応答なし
    ↓
Python 終了
    ↓
Arduino 起動完了（Python 終了後）
    ↓
内部タイマー（TEST_TRIGGER_SEC=10秒）が発火 → サーボ動く
```

### `elapsed=61秒` が証拠だった

```
[TEST] Trigger at elapsed=61sec
```

`TEST_TRIGGER_SEC = 10` のはずが **61 秒後**に発火。  
これは「Python 実行中に DTR でリセットされ、Python 終了後に
Arduino が起動完了し、そこから 10 秒後に内部タイマーが発火した」
ことを示している。

### R4 Minima 特有の挙動

| 項目 | UNO R3 | UNO R4 Minima |
|------|--------|---------------|
| DTR リセット | あり | あり（同様） |
| リセット→Serial初期化完了までの時間 | 約1〜2秒 | 約2〜3秒（やや長い） |
| 0.2秒待機で十分か | △ | ❌ 不十分 |

---

## 解決方法

### 方針：DTR 操作を完全に廃止する

Arduino がすでに起動済みであることを前提とし、
**DTR 操作なし・`time.sleep(3)` のみ**で接続する。

### 決定打となった検証コード

```python
python3 -c "
import serial, time
ser = serial.Serial('/dev/ttyACM0', 9600, timeout=3)
time.sleep(3)   # Arduino 自然起動待ち（DTR 操作なし）
print('sending...')
ser.write(b'TRIGGER\n')
time.sleep(5)
while ser.in_waiting:
    print(ser.readline().decode().strip())
ser.close()
"
```

このコードでサーボが動いたことで **DTR 操作が原因と確定**。

### 修正前のコード

```python
def open_serial_and_wait_boot(port):
    ser = serial.Serial(port, BAUDRATE, timeout=1)

    # ❌ DTR 操作でリセットを引き起こしていた
    ser.dtr = True
    time.sleep(0.2)
    ser.dtr = False
    ser.reset_input_buffer()

    # 起動ログ待ち（リセット中のため何も返らずタイムアウト）
    deadline = time.time() + BOOT_TIMEOUT
    while time.time() < deadline:
        line = ser.readline().decode(errors='replace').strip()
        if "Config:" in line or "RTC mode" in line:
            return ser

    print("[WARN] 起動ログ待ちタイムアウト。そのまま続行します。")
    return ser
```

### 修正後のコード

```python
def open_serial_and_wait_boot(port):
    """
    DTR 操作なしでシリアルポートをオープンする。

    【原因確定済み】
    DTR 操作（ser.dtr=True/False）は Arduino R4 Minima を
    リセットさせてしまい、コマンド送信タイミングと競合する。
    DTR 操作なし・sleep(3) のみで安定動作することを確認済み。
    """
    print(f"[INFO] ポートオープン中: {port}")

    # ✅ DTR 操作なし・そのままオープン
    ser = serial.Serial(port, BAUDRATE, timeout=1)

    # オープン直後の小さなグリッチを吸収するため 3 秒待機
    print(f"[INFO] 接続安定待ち (3秒)...")
    time.sleep(3)
    ser.reset_input_buffer()
    print(f"[INFO] 接続完了: {port}")
    return ser
```

---

## 解決後のログ

```
[INFO] ポートオープン中: /dev/ttyACM0
[INFO] 接続安定待ち (3秒)...
[INFO] 接続完了: /dev/ttyACM0
[SEND] CFG: CFG,14,30,180,0,2000
  [Arduino] [ACK] CFG applied: 14:30 open=180deg close=0deg ms=2000
[WAIT] トリガーまで: 00:01:45  (14:30:00 に実行)
...
[FIRE] 14:30:00 — トリガー発火！
[SEND] TRIGGER コマンド
  [Arduino] [TRIGGER] Manual trigger received.
  [Arduino] [WATER] Start.
  [Arduino] [WATER] Done.
[INFO] 1回実行完了。終了します。
```

---

## 教訓

### DTR 操作は「諸刃の剣」

| 用途 | 効果 |
|------|------|
| Arduino IDE のスケッチ Upload | DTR でリセット → Bootloader 起動 → 書き込み |
| 通常のシリアル通信 | DTR 操作は不要・むしろリセットを引き起こして有害 |

Arduino IDE が Upload 時に DTR を使うのは  
「Bootloader を起動するため」という特殊な用途であり、  
**通常のシリアル通信では DTR 操作は行わない**のが正しい。

### `time.sleep()` の適切な値

```python
# Arduino リセット後に起動を待つ場合（Upload直後など）
time.sleep(2)  # 最低 2 秒

# 起動済み Arduino に接続する通常ケース
time.sleep(3)  # オープン直後のグリッチ吸収に 3 秒で十分
```

### シリアル通信デバッグの手順

```
1. IDE シリアルモニタで手動コマンド送信 → Arduino側の確認
2. 最小限の Python コードで確認（DTR 操作なし）
3. 問題を1つずつ切り分ける
```

---

## 変更ファイル

| ファイル | 変更内容 |
|---------|---------|
| `test_trigger.py` | `open_serial_and_wait_boot()` の DTR 操作を削除し `time.sleep(3)` のみに変更 |
| `water_timer.ino` | 変更なし |
| `set_time.py` | 変更なし |
