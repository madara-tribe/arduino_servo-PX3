#include <Servo.h>
#include <Wire.h>
#include <AS5600.h>

AS5600 as5600;
Servo servo;

const uint8_t SERVO_PIN = 9;

// PX系（RC標準）相当のパルス幅レンジ
const int SERVO_MIN_US = 1000;
const int SERVO_MAX_US = 2000;

const uint16_t SETTLE_MS = 300; // サーボ移動後の待機

void setup() {
  Serial.begin(9600);
  Wire.begin();
  as5600.begin();

  // パルス幅を明示してアタッチ（PX/RCスタイル）
  servo.attach(SERVO_PIN, SERVO_MIN_US, SERVO_MAX_US);

  Serial.println("READY");
}

float readAS5600Deg() {
  // 使用している AS5600 ライブラリが度で返す前提（前回と同じ）
  float deg = as5600.readAngle();
  // 0..360 に丸め
  if (deg < 0) deg += 360.0;
  if (deg >= 360.0) deg -= 360.0;
  return deg;
}

float readAS5600Avg(uint8_t samples, uint16_t delay_ms) {
  double sum = 0;
  for (uint8_t i = 0; i < samples; i++) {
    sum += readAS5600Deg();
    delay(delay_ms);
  }
  return (float)(sum / samples);
}

void commandGoto(int degTarget) {
  if (degTarget < 0)   degTarget = 0;
  if (degTarget > 180) degTarget = 180;

  // 角度(0..180) → μs(1000..2000) へ線形変換
  long us = map(degTarget, 0, 180, SERVO_MIN_US, SERVO_MAX_US);
  servo.writeMicroseconds(us);

  // 落ち着くのを少し待つ → AS5600 を複数回読んで平均
  delay(SETTLE_MS);
  float meas = readAS5600Avg(8, 10);

  // Python 側が読み取りやすい 1 行レスポンス
  Serial.print("REPORT target:");
  Serial.print(degTarget);
  Serial.print(", as5600:");
  Serial.println(meas, 2);
}

void loop() {
  // 行単位の簡易コマンドパーサ
  static String line = "";
  while (Serial.available()) {
    char c = Serial.read();
    if (c == '\r') continue;
    if (c == '\n') {
      line.trim();
      if (line.length() > 0) {
        int sp = line.indexOf(' ');
        String cmd = (sp == -1) ? "" : line.substring(0, sp);
        String arg = (sp == -1) ? line : line.substring(sp + 1);
        arg.trim();

        // "GOTO 90" / "SET 90" / "90" に対応
        if (cmd.equalsIgnoreCase("GOTO") || cmd.equalsIgnoreCase("SET") || cmd == "") {
          int degTarget = arg.toInt();
          commandGoto(degTarget);
        }
        // 角度の単発読み出し
        else if (cmd.equalsIgnoreCase("READ")) {
          float meas = readAS5600Avg(8, 5);
          Serial.print("AS5600 ");
          Serial.println(meas, 2);
        }
        // STEP 0,180,10 のような一括動作（おまけ）
        else if (cmd.equalsIgnoreCase("STEP")) {
          int p1=0, p2=180, p3=10;
          int c1 = arg.indexOf(',');
          int c2 = arg.indexOf(',', c1 + 1);
          if (c1 != -1 && c2 != -1) {
            p1 = arg.substring(0, c1).toInt();
            p2 = arg.substring(c1 + 1, c2).toInt();
            p3 = arg.substring(c2 + 1).toInt();
          }
          if (p3 <= 0) p3 = 10;
          if (p1 > p2) { int tmp=p1; p1=p2; p2=tmp; }
          for (int a = p1; a <= p2; a += p3) {
            commandGoto(a);
          }
        }
        else {
          Serial.print("ERR unknown:");
          Serial.println(line);
        }
      }
      line = "";
    } else {
      line += c;
    }
  }
}

