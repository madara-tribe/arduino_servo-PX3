// ============================================================
//  water_timer.ino
//  RTC購入後: 下の1行のコメントアウトを外すだけ
// ============================================================

// #define USE_RTC   // ← RTC購入後ここを有効化

#ifdef USE_RTC
  #include <Wire.h>
  #include <RTClib.h>
  RTC_DS3231 rtc;
#endif

// ===== ピン設定 =====
const int SERVO_PIN  = 9
const int BUZZER_PIN = 12;

// ===== 給水設定 (set_time.py の CFG コマンドで上書き可能) =====
int  water_hour  = 7;     // 給水時刻（時）
int  water_min   = 0;     // 給水時刻（分）
int  servo_open  = 180;   // サーボOPEN角度
int  servo_close = 0;     // サーボCLOSE角度
long water_ms    = 2000;  // 給水時間 [ms]

// ===== テストモード設定 =====
#ifndef USE_RTC
  const unsigned long TEST_TRIGGER_SEC = 10;
#endif

// ===== 状態管理 =====
bool done_today = false;
int  last_day   = -1;

// ===== SimpleTime 構造体 (全関数より前に定義) =====
struct SimpleTime {
  int hour;
  int minute;
  int day;
};

// ===== サーボ制御 =====
void servoWrite(int pin, int angle) {
  int pulse = map(angle, 0, 180, 600, 2400);
  for (int i = 0; i < 30; i++) {
    digitalWrite(pin, HIGH);
    delayMicroseconds(pulse);
    digitalWrite(pin, LOW);
    delay(20);
  }
}

// ===== 給水実行 =====
void doWater() {
  Serial.println("[WATER] Start.");
  tone(BUZZER_PIN, 880, 500);
  delay(600);
  servoWrite(SERVO_PIN, servo_open);
  delay(water_ms);
  servoWrite(SERVO_PIN, servo_close);
  tone(BUZZER_PIN, 1320, 300);
  done_today = true;
  Serial.println("[WATER] Done.");
}

// ===== 時刻取得 =====
SimpleTime getTime() {
  SimpleTime t;
#ifdef USE_RTC
  DateTime now = rtc.now();
  t.hour   = now.hour();
  t.minute = now.minute();
  t.day    = now.day();
#else
  unsigned long sec = millis() / 1000;
  t.hour   = (int)(sec / 3600) % 24;
  t.minute = (int)((sec % 3600) / 60);
  t.day    = (int)(sec / 86400);
#endif
  return t;
}

// ===== CFGコマンド解析 =====
// フォーマット: "CFG,HH,mm,OPEN,CLOSE,MS\n"
void parseCFG(String cmd) {
  // カンマ区切りでパース
  int idx = 4; // "CFG," の後から
  auto nextVal = [&]() -> long {
    int comma = cmd.indexOf(',', idx);
    long val;
    if (comma == -1) {
      val = cmd.substring(idx).toInt();
      idx = cmd.length();
    } else {
      val = cmd.substring(idx, comma).toInt();
      idx = comma + 1;
    }
    return val;
  };

  int  h    = (int)nextVal();
  int  m    = (int)nextVal();
  int  opn  = (int)nextVal();
  int  cls  = (int)nextVal();
  long ms   = nextVal();

  // バリデーション
  if (h < 0 || h > 23 || m < 0 || m > 59 ||
      opn < 0 || opn > 180 || cls < 0 || cls > 180 || ms < 100) {
    Serial.println("[ERROR] CFG: invalid value");
    return;
  }

  water_hour  = h;
  water_min   = m;
  servo_open  = opn;
  servo_close = cls;
  water_ms    = ms;

  Serial.print("[ACK] CFG applied: ");
  Serial.print(water_hour); Serial.print(":");
  Serial.print(water_min);  Serial.print(" open=");
  Serial.print(servo_open); Serial.print("deg close=");
  Serial.print(servo_close);Serial.print("deg ms=");
  Serial.println(water_ms);
}

// ===== シリアルコマンド処理 =====
void handleSerial() {
  if (!Serial.available()) return;
  String cmd = Serial.readStringUntil('\n');
  cmd.trim();

  if (cmd.startsWith("SET,")) {
#ifdef USE_RTC
    int yr = cmd.substring(4,  8).toInt();
    int mo = cmd.substring(9,  11).toInt();
    int dy = cmd.substring(12, 14).toInt();
    int hr = cmd.substring(15, 17).toInt();
    int mn = cmd.substring(18, 20).toInt();
    int sc = cmd.substring(21, 23).toInt();
    rtc.adjust(DateTime(yr, mo, dy, hr, mn, sc));
    Serial.println("[ACK] Time set.");
#else
    Serial.println("[WARN] SET ignored: RTC not enabled");
#endif
  }
  else if (cmd.startsWith("CFG,")) {
    parseCFG(cmd);
  }
  else if (cmd == "TRIGGER") {
    // test_trigger.py からの手動トリガー (RTC無しテスト用)
    Serial.println("[TRIGGER] Manual trigger received.");
    doWater();
    done_today = false; // テスト用: 繰り返し実行できるようリセット
  }
  else if (cmd.length() > 0) {
    Serial.print("[WARN] Unknown command: ");
    Serial.println(cmd);
  }
}

// ===== Setup =====
void setup() {
  Serial.begin(9600);
  pinMode(SERVO_PIN,  OUTPUT);
  pinMode(BUZZER_PIN, OUTPUT);
  servoWrite(SERVO_PIN, servo_close);
  Serial.println("[INFO] Servo initialized: CLOSE");

#ifdef USE_RTC
  Wire.begin();
  if (!rtc.begin()) {
    Serial.println("[ERROR] RTC not found. Check wiring.");
    while (1);
  }

  // 起動後3秒間 SET/CFG コマンド待ち
  Serial.println("[INFO] Waiting for SET/CFG commands (3sec)...");
  unsigned long t0 = millis();
  while (millis() - t0 < 3000) {
    handleSerial();
  }

  DateTime now = rtc.now();
  Serial.print("[INFO] RTC time: ");
  Serial.print(now.year());  Serial.print("/");
  Serial.print(now.month()); Serial.print("/");
  Serial.print(now.day());   Serial.print(" ");
  Serial.print(now.hour());  Serial.print(":");
  Serial.print(now.minute());Serial.print(":");
  Serial.println(now.second());
  Serial.println("[INFO] RTC mode: ON");

#else
  // テストモードでも CFG は受け付ける（3秒待ち）
  Serial.println("[INFO] RTC mode: OFF (test mode)");
  Serial.println("[INFO] Waiting for CFG commands (3sec)...");
  unsigned long t0 = millis();
  while (millis() - t0 < 3000) {
    handleSerial();
  }
  Serial.print("[INFO] Water trigger in ");
  Serial.print(TEST_TRIGGER_SEC);
  Serial.println("sec after boot.");
#endif

  // 現在の設定をシリアルに表示
  Serial.print("[INFO] Config: ");
  Serial.print(water_hour); Serial.print(":");
  Serial.print(water_min);  Serial.print(" open=");
  Serial.print(servo_open); Serial.print("deg close=");
  Serial.print(servo_close);Serial.print("deg ms=");
  Serial.println(water_ms);
}

// ===== Loop =====
void loop() {
  // ループ中もシリアルコマンドを受け付け
  handleSerial();

  SimpleTime now = getTime();

#ifdef USE_RTC
  if (now.day != last_day) {
    done_today = false;
    last_day   = now.day;
    Serial.println("[INFO] New day. Reset done_today.");
  }
  if (now.hour == water_hour && now.minute == water_min && !done_today) {
    Serial.println("[WATER] Scheduled trigger fired.");
    doWater();
  }
  static unsigned long prev_log = 0;
  if (millis() - prev_log > 10000) {
    Serial.print("[TIME] ");
    Serial.print(now.hour);   Serial.print(":");
    Serial.print(now.minute); Serial.print("  done_today=");
    Serial.println(done_today ? "true" : "false");
    prev_log = millis();
  }
  delay(10000);

#else
  unsigned long elapsed = millis() / 1000;
  if (elapsed >= TEST_TRIGGER_SEC && !done_today) {
    Serial.print("[TEST] Trigger at elapsed=");
    Serial.print(elapsed);
    Serial.println("sec");
    doWater();
  }
  static unsigned long prev_log = 0;
  if (millis() - prev_log > 2000) {
    unsigned long el = millis() / 1000;
    long rem = (long)TEST_TRIGGER_SEC - (long)el;
    if (rem < 0) rem = 0;
    Serial.print("[TEST] elapsed=");
    Serial.print(el);
    Serial.print("s  trigger_in=");
    Serial.print(rem);
    Serial.print("s  done=");
    Serial.println(done_today ? "true" : "false");
    prev_log = millis();
  }
  delay(500);
#endif
}
