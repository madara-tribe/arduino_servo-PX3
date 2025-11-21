#include <Servo.h>

Servo myservo;
String inputString = "";
bool stringComplete = false;

void setup() {
  Serial.begin(115200);          // ESP8266とPCの通信
  myservo.attach(5);             // GPIO5 にサーボ信号を接続
  inputString.reserve(10);       // メモリ予約
  Serial.println("Ready");
}

void loop() {
  // 文字列受信済みなら処理
  if (stringComplete) {
    int angle = inputString.toInt();
    angle = constrain(angle, 0, 180);  // 範囲制限
    myservo.write(angle);
    Serial.print("Angle set to: ");
    Serial.println(angle);
    inputString = "";
    stringComplete = false;
  }
}

// 1文字ずつ読み込み
void serialEvent() {
  while (Serial.available()) {
    char inChar = (char)Serial.read();
    if (inChar == '\n') {
      stringComplete = true;
    } else {
      inputString += inChar;
    }
  }
}
