// sg5010.ino  (Arduino UNO / SG5010)
// - float degrees: "90.5\n" や "D90.5\n" を受信 → writeMicroseconds() で駆動
// - microseconds:  "U1500\n" を受信 → そのまま駆動
// - UNO互換: atof() 使用（strtof() は使わない）

#include <Arduino.h>
#include <Servo.h>
#include <stdlib.h>  // atof()
#include <math.h>

#define SERVO_PIN      9
#define BAUD           115200   // ご指定
#define SERVO_MIN_US   500      // ご指定（必要なら 600 へ）
#define SERVO_MAX_US   2500     // ご指定（必要なら 2400 へ）
#define SERVO_MIN_DEG  0.0f
#define SERVO_MAX_DEG  180.0f

// PC側（Python）で反転するため、ここは false 固定
#define INVERT_INPUT   false

// 微小ノイズ抑制。厳密テスト時は 0 のまま推奨
#define DEADBAND_US    0

Servo servo_;
int last_us = -1;

static inline int degToUs(float deg) {
  if (INVERT_INPUT) deg = 180.0f - deg;
  if (deg < SERVO_MIN_DEG) deg = SERVO_MIN_DEG;
  if (deg > SERVO_MAX_DEG) deg = SERVO_MAX_DEG;
  float ratio = (deg - SERVO_MIN_DEG) / (SERVO_MAX_DEG - SERVO_MIN_DEG);
  int us = (int)(SERVO_MIN_US + ratio * (SERVO_MAX_US - SERVO_MIN_US) + 0.5f); // round
  return us;
}

void setup() {
  Serial.begin(BAUD);
  Serial.setTimeout(20);
  servo_.attach(SERVO_PIN, SERVO_MIN_US, SERVO_MAX_US);

  // center on boot
  int center = (SERVO_MIN_US + SERVO_MAX_US) / 2;
  servo_.writeMicroseconds(center);
  last_us = center;
  Serial.println(F("READY SG5010 µs-mode"));
}

void loop() {
  static char buf[32];
  static size_t idx = 0;

  while (Serial.available() > 0) {
    char c = Serial.read();
    if (c == '\r') continue;

    // accumulate until newline
    if (c != '\n') {
      if (idx < sizeof(buf) - 1) buf[idx++] = c; else idx = 0; // overflow guard
      continue;
    }

    // newline: parse
    buf[idx] = '\0';
    idx = 0;

    // trim leading spaces
    char* p = buf; while (*p==' ' || *p=='\t') ++p;
    if (*p == '\0') continue;

    bool microMode = false;
    if (*p=='u' || *p=='U') { microMode = true; ++p; if (*p==':' || *p==' ') ++p; }
    else if (*p=='d' || *p=='D') { ++p; if (*p==':' || *p==' ') ++p; }

    // UNO互換：atof()でfloat化（strtof不可）
    float val = atof(p);  // "90.5" or "1500"
    int target_us = microMode ? (int)(val + 0.5f) : degToUs(val);

    if (target_us < SERVO_MIN_US) target_us = SERVO_MIN_US;
    if (target_us > SERVO_MAX_US) target_us = SERVO_MAX_US;

    if (last_us < 0 || abs(target_us - last_us) > DEADBAND_US) {
      servo_.writeMicroseconds(target_us);
      last_us = target_us;
    }

    Serial.print(F("OK "));
    Serial.println(target_us);
  }
}

