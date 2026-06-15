# Arduino IDE Setup — UNO R4 Minima

## Step 1: Download Arduino IDE 2

[https://www.arduino.cc/en/software](https://www.arduino.cc/en/software)

Download and install for your OS (Windows / Mac / Linux).
Arduino IDE 2 (最新版) を推奨。

---

## Step 2: Install UNO R4 Board Package

```
Arduino IDE を開く
  → 左サイドバー「Boards Manager」アイコンをクリック
  → 検索欄に「Arduino UNO R4」と入力
  → 「Arduino UNO R4 Boards」が表示される
  → 「Install」をクリック
```

---

## Step 3: Install RTClib Library

```
左サイドバー「Library Manager」アイコンをクリック
  → 検索欄に「RTClib」と入力
  → 「RTClib by Adafruit」を選択
  → 「Install」をクリック
  （依存ライブラリのインストールを聞かれたら「Install All」）
```

---

## Step 4: Connect the Board

USB-Cケーブルで UNO R4 Minima をPCに接続する。
接続すると電源LEDが点灯する。

⚠️ R4 Minimaは **USB-C** です（R3のUSB-Bとは異なる）。

---

## Step 5: Select Board & Port

```
Tools → Board → Arduino UNO R4 Boards → Arduino UNO R4 Minima
Tools → Port  → COM# (Arduino UNO R4 Minima)
               ※Macは /dev/cu.usbmodem...
               ※Linuxは /dev/ttyACM0 など
```

---

## Step 6: Verify with Blink Test

```
File → Examples → 01.Basics → Blink
  → 「→」（Upload）ボタンをクリック
  → 「Done uploading.」が表示されればOK
  → オンボードLEDが1秒毎に点滅する
```

---

## Step 7: Upload water_timer.ino

```
File → Open → water_timer.ino を選択
  → 「→」（Upload）ボタンをクリック
  → Tools → Serial Monitor（9600 baud）で動作確認
```

---

## セットアップ手順まとめ

| Step | 内容 |
|------|------|
| 1 | Arduino IDE 2 インストール |
| 2 | Board Package「Arduino UNO R4 Boards」インストール |
| 3 | Library「RTClib by Adafruit」インストール |
| 4 | USB-Cで接続・電源LED確認 |
| 5 | Board: UNO R4 Minima / Port 選択 |
| 6 | Blinkでテスト → LED点滅確認 |
| 7 | water_timer.ino をUpload |

---

## RTC有効化（DS3231購入後）

`water_timer.ino` の先頭1行のコメントを外す:

```cpp
// 変更前（テストモード）
// #define USE_RTC

// 変更後（本番）
#define USE_RTC
```

その後 `set_time.py` を1回実行:

```bash
python set_time.py /dev/ttyACM0   # Linux/Mac
python set_time.py COM3            # Windows
```

PCを外してACアダプタのみ接続 → 完全自律動作開始。
