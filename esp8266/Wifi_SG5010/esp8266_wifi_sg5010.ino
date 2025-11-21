#include <ESP8266WiFi.h>
#include <Servo.h>

const char* ssid = "aterm-1e967a-g";         // Wi-Fi SSID
const char* password = "00e13cbb72530";     // Wi-Fi Password

WiFiServer server(1234);

Servo myservo;

void setup() {
  Serial.begin(115200);

  // Wi-Fi接続開始
  WiFi.begin(ssid, password);
  Serial.print("Wi-Fi接続中");
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }

  // 接続成功
  Serial.println();
  Serial.print("接続成功！IPアドレス：");
  Serial.println(WiFi.localIP());  // このIPをPythonで使用

  server.begin();

  myservo.attach(5);  // GPIO5 (NodeMCU D1) にサーボ信号線を接続
  Serial.println("サーバ起動完了。待機中...");
}

void loop() {
  WiFiClient client = server.available();
  if (client) {
    Serial.println("クライアント接続");

    String input = "";
    while (client.connected()) {
      while (client.available()) {
        char c = client.read();
        if (c == '\n') {
          int angle = input.toInt();
          angle = constrain(angle, 0, 180);  // 角度制限
          myservo.write(angle);
          Serial.print("角度設定: ");
          Serial.println(angle);
          client.println("OK");  // クライアントに返事
          input = "";
        } else {
          input += c;
        }
      }
    }

    client.stop();
    Serial.println("クライアント切断");
  }
}

