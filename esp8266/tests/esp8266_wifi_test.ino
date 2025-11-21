#include <ESP8266WiFi.h>

const char* ssid = "aterm-1e967a-g";         // ← ここにWi-FiのSSIDを入力
const char* password = "00e13cbb72530"; // ← ここにWi-Fiのパスワードを入力

void setup() {
  Serial.begin(74880);          // シリアルモニタ開始
  delay(1000);                   // 安定化待ち
  Serial.println("Connecting to Wi-Fi...");

  WiFi.begin(ssid, password);    // Wi-Fi接続開始

  int retry = 0;
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
    retry++;
    if (retry > 30) {  // 約15秒でタイムアウト
      Serial.println("\nConnection Failed.");
      return;
    }
  }

  // 接続成功時の処理
  Serial.println("\n✅ success!");
  Serial.print("IP Address: ");
  Serial.println(WiFi.localIP());
}

void loop() {
  // 特に処理しない
}
