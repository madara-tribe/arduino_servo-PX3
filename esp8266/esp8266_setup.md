
# 📡 ESP8266 リモート操作セットアップ手順（PX4対応）

## ✅ 使用機器
- 商品名：ESP-WROOM-02 開発ボード  
- 販売コード：112236  
- 型番：AE-ESP-WROOM-02-DEV  

---

## 1. Arduino IDE の環境構築（ESP8266 書き込み用）

### 1.1 ボードマネージャの設定

**Arduino IDE > 基本設定** → 「追加のボードマネージャのURL」に以下を追加：

```
https://arduino.esp8266.com/stable/package_esp8266com_index.json
https://raw.githubusercontent.com/espressif/arduino-esp32/gh-pages/package_esp32_index.json
```

### 1.2 インストール項目

- 「ツール > ボード > ボードマネージャ」から  
  **ESP8266 by ESP8266 Community** をインストール
  ツール > ライブラリを管理… で「**Telemetrix4ESP8266**」を検索してインストール
  
- スケッチ例から ESP8266 用サーバを開く
  ファイル > スケッチ例 > Telemetrix4ESP8266 > Telemetrix4ESP8266WiFi などを選ぶ

### 1.3 ツール設定の例（Generic ESP8266 Module）

| 項目 | 設定値 |
|------|--------|
| ボード | Generic ESP8266 Module |
| ポート | 例：/dev/cu.usbserial-XXXX |
| Upload Speed | 115200 |
| Crystal Frequency | 26 MHz |
| Flash Size | 1MB or 4MB（ボード依存） |
| Flash Frequency | 40MHz または 80MHz |
| Flash Mode | QIO |
| Debug port | Disabled |
| Reset Method | dtr (nodemcu) |
| CPU Frequency | 80 MHz |
| Erase Flash | Only Sketch または All Flash Contents（初期化したい場合） |

---

## 2. ESP8266 の Wi-Fi 接続確認

### 2.1 接続確認用スケッチ

```cpp
#include <ESP8266WiFi.h>

const char* ssid = "YOUR_SSID";
const char* password = "YOUR_PASSWORD";

void setup() {
  Serial.begin(115200);
  delay(10);

  WiFi.begin(ssid, password);
  Serial.print("Connecting to ");
  Serial.println(ssid);
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }

  Serial.println("");
  Serial.println("WiFi connected");
  Serial.print("IP address: ");
  Serial.println(WiFi.localIP());
}

void loop() {}
```

### 2.2 書き込み時の操作手順

1. Arduino IDEで「**書き込み**」ボタンを押す  
2. 同時に ESP8266 の **[PGM(Boot)]** ボタンと **[RST(Reset)]** ボタンを押す  
3. **RST を先に離す**  
4. **PGM を後から離す** → 書き込みモードに入る  

---

### 2.3 メッセージの確認方法

- **シリアルモニターの設定**
  - **ボーレート**: `115200`  
    - ※文字化けが発生する場合は、`Serial.begin(74880);` に設定し、シリアルモニタのボーレートも `74880` に変更してください。
  - **通信終了文字**: `Both NL & CR`（または `CR and LF`）

### 3. ESP8266 の SSID と IP アドレスの確認方法

以下のスケッチを書き込んで、ESP8266 が Wi-Fi に接続された際の IP アドレスを確認します。

```cpp
#include <ESP8266WiFi.h>

const char* ssid = "aterm-1e967a-g";         // Wi-Fi SSID
const char* password = "00e13cbb72530";      // Wi-Fi Password

void setup() {
  Serial.begin(74880);  // 文字化け防止のため 74880bps を使用
  delay(10);
  Serial.println('\n');

  WiFi.begin(ssid, password);
  Serial.print("Connecting to ");
  Serial.print(ssid); Serial.println(" ...");

  int i = 0;
  while (WiFi.status() != WL_CONNECTED) {
    delay(1000);
    Serial.print(++i); Serial.print(' ');
  }

  Serial.println('\n');
  Serial.println("Connection established!");  
  Serial.print("IP address:\t");
  Serial.println(WiFi.localIP());
}

void loop() {}
```

#### 実行手順

1. 上記コードを ESP8266 に書き込む  
2. シリアルモニターを 74880bps に設定  
3. ESP8266 の **[RST]** ボタンを押す  
4. 以下のようなログが表示される：

```
Connecting to aterm-1e967a-g ...
1 2 3 4 
Connection established!
IP address: 192.168.10.115
```

この `192.168.10.115` は、PC から TCP 通信や HTTP アクセスする際に使用するアドレスです（例：ping コマンドで確認可能）。

```sh
ping 192.168.10.115
```

---

### 4. ESP8266 と SG5010 サーボモーターの配線

| SG5010（サーボ） | ESP8266（開発ボード） |
|------------------|------------------------|
| VCC（赤）        | 5V0ピン または外部5V電源 |
| GND（茶 or 黒）   | GNDピン（共通GND）       |
| Signal（橙 or 黄）| GPIO5（ピン番号5）       |

#### ESP8266 の主な端子一覧（例）

```
3V3, EN, 11, 12, 13, 14, 15, 2, 0,
GND, 5V0, GND, 16, T0, RST, 5, GND, TXD, RXD, 4, CB0
```


### 5. Wi-Fi 経由のサーボ制御（リモート制御）

####  ESP8266 側スケッチ（Wi-Fi TCPサーバ）

```cpp
#include <ESP8266WiFi.h>
#include <Servo.h>

const char* ssid = "aterm-1e967a-g";
const char* password = "00e13cbb72530";

WiFiServer server(1234);
Servo myservo;

void setup() {
  Serial.begin(115200);
  WiFi.begin(ssid, password);

  Serial.print("Connecting to Wi-Fi");
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }

  Serial.println();
  Serial.print("Connected! IP address: ");
  Serial.println(WiFi.localIP());

  server.begin();
  myservo.attach(5);  // GPIO5
}

void loop() {
  WiFiClient client = server.available();
  if (client) {
    Serial.println("Client connected");

    String input = "";
    while (client.connected()) {
      while (client.available()) {
        char c = client.read();
        if (c == '\n') {
          int angle = input.toInt();
          angle = constrain(angle, 0, 180);
          myservo.write(angle);
          Serial.print("Set angle to: ");
          Serial.println(angle);
          client.println("OK");
          input = "";
        } else {
          input += c;
        }
      }
    }
    client.stop();
    Serial.println("Client disconnected");
  }
}
```

####  PC 側 Python GUI（tkinter + socket）

```python
import tkinter as tk
import socket

ESP8266_IP = "192.168.10.115"
ESP8266_PORT = 1234

def send_angle(angle):
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(3)
            s.connect((ESP8266_IP, ESP8266_PORT))
            s.sendall(f"{angle}\n".encode())
            response = s.recv(1024).decode().strip()
            status_label.config(text=f"送信成功: {angle}° → ESP応答: {response}")
    except Exception as e:
        status_label.config(text=f"送信失敗: {e}")

def on_slider_change(value):
    angle = int(float(value))
    angle_label.config(text=f"角度: {angle}°")
    send_angle(angle)

root = tk.Tk()
root.title("Wi-Fi サーボキャリブレーション")

slider = tk.Scale(root, from_=0, to=180, orient=tk.HORIZONTAL, command=on_slider_change, length=400)
slider.pack(padx=20, pady=10)

angle_label = tk.Label(root, text="角度: 90°", font=("Arial", 14))
angle_label.pack()

status_label = tk.Label(root, text="準備完了", fg="blue", font=("Arial", 12))
status_label.pack(pady=10)

root.mainloop()
```
