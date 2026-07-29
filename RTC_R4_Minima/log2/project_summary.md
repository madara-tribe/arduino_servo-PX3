# 自動水やり装置プロジェクト サマリ

**構成**: Arduino UNO R4 Minima + DS3231 RTC (Adafruit product 3013) + SG90 Servo
**目的**: 1週間程度の旅行中、毎朝7:00にプランターへ自動給水

---

## 1. コマンド一覧（実行順）

### セットアップ（1回のみ）

```bash
# Arduino IDE で water_timer.ino をアップロード
# （#define USE_RTC を有効化した状態）

# シリアルポートのパーミッション付与（必要な場合）
sudo chmod 777 /dev/ttyACM0

# ポート確認
ls /dev/ttyACM*
```

### 動作確認・デバッグ用コマンド

```bash
# システム全体の自動検査（シリアル通信・RTC・サーボ）
python3 check_system.py /dev/ttyACM0

# RTCに現在時刻をセット + 給水パラメータ設定
python3 set_time.py /dev/ttyACM0

# 指定時刻にサーボを動かすテスト（RTC無しでもOK）
python3 test_trigger.py --time 07:26 --port /dev/ttyACM0

# 今からN秒後にテスト発火
python3 test_trigger.py --in 10 --port /dev/ttyACM0

# 毎日繰り返しテスト
python3 test_trigger.py --time 07:00 --repeat --port /dev/ttyACM0
```

### 本番運用移行

```bash
# 1. water_timer.ino の給水時刻を確認 (WATER_HOUR=7, WATER_MIN=0)
# 2. set_time.py で最終時刻同期
python3 set_time.py /dev/ttyACM0

# 3. PCのUSBケーブルを抜く
# 4. ArduinoをACアダプタ（USB-C, 5V/1A以上）に接続
#    → これで完全自律動作開始
```

### トラブルシューティング用

```bash
# シリアルポートを掴んでいるプロセスを確認・強制終了
lsof /dev/ttyACM0
fuser -k /dev/ttyACM0

# 停止中(Ctrl+Zされた)ジョブの確認・終了
jobs
kill %1

# 生のシリアル出力を直接確認
timeout 20 cat /dev/ttyACM0
```

---

## 2. 配線（Wiring）

### Arduino UNO R4 Minima ピン割当

| デバイス | ピン | Arduino側 | 備考 |
|---------|------|-----------|------|
| DS3231 RTC | VIN | 5V または 3.3V | product 3013 は3〜5V対応 |
| DS3231 RTC | GND | GND | |
| DS3231 RTC | SCL | SCL | I2Cクロック |
| DS3231 RTC | SDA | SDA | I2Cデータ |
| SG90 Servo | Signal(橙) | D9（PWM ~） | |
| SG90 Servo | VCC(赤) | 5V | |
| SG90 Servo | GND(茶) | GND | |

### 現在の配線図（テキスト）

```
        5V  <───> ブレッドボード <───> VIN(RTC)
                              └───> SERVO red(VCC)
Arduino GND <──> GND(RTC)
        GND <──> servo brown(GND)
        pin9 <─> SERVO yellow(Signal)
        SCL <──> SCL(RTC)
        SDA <──> SDA(RTC)
```

### ⚠️ 既知の問題点（要改善）

```
現状: RTCとServoが同じ5Vラインを共有している
問題: サーボ動作時の電流スパイクで電源電圧が揺れ、
      I2C通信（RTCとの通信）にノイズが乗る
症状: SETコマンドのACKタイムアウト・時刻の反映失敗・
      最終的にRTCがI2Cバス上でハングし「RTC not found」に

改善案:
  RTC VIN → 3.3V（Servoと電源ラインを分離）
  Servo VCC → 5V（そのまま）
  可能なら電源ラインに電解コンデンサ(100〜470µF)を追加
```

### バックアップ電池

```
使用電池: CR1220（3Vリチウムコイン電池）
挿入方向: ＋マークが見える向き（上向き）
注意: 逆挿入・VIN/GND逆接続は発熱・故障の原因になるため厳禁
```

---

## 3. スクリプトの役割

| ファイル | 役割 | 実行タイミング |
|---------|------|---------------|
| `water_timer.ino` | Arduino本体スケッチ。RTC監視・サーボ制御・シリアルコマンド処理 | Arduinoに書き込み |
| `set_time.py` | RTCへ現在時刻をセット + 給水時刻/サーボ角度/給水時間を設定 | 運用開始前に1回 |
| `test_trigger.py` | 指定時刻（またはN秒後）にTRIGGERコマンドを送りサーボを手動発火 | 動作テスト時 |
| `check_system.py` | シリアル通信・RTC進行・RTC設定・サーボ動作を自動で4項目検査 | トラブル時の診断 |

### water_timer.ino の主要コマンド（シリアル経由）

```
SET,YYYY,MM,DD,HH,mm,ss   → RTCに時刻を書き込む
CFG,HH,mm,OPEN,CLOSE,MS   → 給水時刻・サーボ角度・給水時間を設定
TRIGGER                   → 即座にサーボを1回動作（テスト用）
```

### water_timer.ino の主要設定値

```cpp
#define USE_RTC          // コメントアウトでRTC無しのテストモード

int  water_hour  = 7;     // 給水時刻（時）
int  water_min   = 0;     // 給水時刻（分）
int  servo_open  = 180;   // サーボOPEN角度
int  servo_close = 0;     // サーボCLOSE角度
long water_ms    = 2000;  // 給水時間 [ms]
```

---

## 4. その他の重要情報

### 発生した主なトラブルと原因（時系列）

| 症状 | 原因 | 対応 |
|------|------|------|
| コンパイルエラー `expected ',' or ';'` | `const int SERVO_PIN = 9` のセミコロン抜け | 追記して解決 |
| `struct SimpleTime does not name a type` | struct定義が使用箇所より後にあった | ファイル先頭に移動して解決 |
| Python書き込み時 `[Errno 5] I/O error` | DTR操作によるArduino自動リセットとの競合 | DTR操作を削除し `sleep(3)` のみに変更 |
| ACKタイムアウト（Python↔Arduino） | IDEシリアルモニタが同時に開いていてACKを横取り | シリアルモニタを閉じてから実行 |
| RTC時刻が0:00のまま | 旧版`set_time.py`のDTRリセットでSETコマンドがロスト | DTR対策版に修正 |
| RTC発熱・I2C応答なし | VIN/GND逆接続または電池逆挿入の疑い | 印字を直接読んで再配線、電池向き確認 |
| SET成功するが時刻が反映されない | RTCとServoの5V共有によるI2Cノイズ | 電源ライン分離が必要（未対応） |
| 最終的にRTC not found | I2Cバスの電気的ハング（サーボ電流スパイクの蓄積） | 電源分離後に全結線リセットして再検証必要 |

### 使用パーツ

```
Arduino UNO R4 Minima（USB-C, 3.3V I2C動作）
DS3231 RTC — Adafruit製 product 3013（I2Cアドレス0x68固定）
SG90 サーボモーター
CR1220 コイン電池（RTCバックアップ用）
```

### 現状のステータス（このログ時点）

```
✅ Arduino単体のコンパイル・アップロード成功
✅ サーボ単体動作確認済み
✅ RTC単体でのSET/CFG/TRIGGER動作は一時的に成功実績あり
❌ RTCとServoを同時運用すると電源ノイズでRTCがI2Cバスハング
→ 次のアクション: 電源ライン分離（RTCを3.3V化）してから再検証が必要
```
