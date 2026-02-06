// simple_move_gui.ino
// Move Waveshare ST3215-HS (STS series) from a PC Python GUI over USB Serial.
//
// Hardware:
//   Arduino Nano ESP32 (ESP32-S3) <-> Bus Servo Driver (Akizuki 131227 / Bus Servo Adapter A) <-> ST3215-HS
// Wiring (confirmed):
//   ESP32 GND       <-> Driver GND
//   ESP32 RX0 (D0)  <-> Driver RX
//   ESP32 TX1 (D1)  <-> Driver TX
// Jumper on driver: A mode (UART-SERVO) by shorting line1-line2 on BOTH columns.
//
// Protocol (USB Serial @115200):
//   DEG <0..360>            : move to angle in degrees
//   POS <0..4095>           : move to raw position steps (0..4095)
//   SPEED <0..2000>         : set speed (steps/s) used by DEG/POS
//   ACC <0..255>            : set acceleration used by DEG/POS
//   ID                      : print current servo ID
//   RESCAN                  : rescan servo IDs and pick first found
//   HELP                    : print help
//
// Notes:
// - Servo bus baud is 1,000,000 (1Mbps).
// - This sketch uses POSITION control (0..4095 steps ~ 0..360 deg).

#include <Arduino.h>
#include <SCServo.h>

SMS_STS st;

// UART pins to driver (per your wiring)
static const int RX_PIN = 0;   // D0 (RX0)
static const int TX_PIN = 1;   // D1 (TX1)

static const long SERVO_BAUD = 1000000;

int g_servo_id = -1;

// Motion parameters
int g_speed = 500;  // steps/s
int g_acc   = 0;    // 0..255

String g_line;

static int degToPos(float deg) {
  if (deg < 0.0f) deg = 0.0f;
  if (deg > 360.0f) deg = 360.0f;
  long pos = lroundf((deg / 360.0f) * 4095.0f);
  if (pos < 0) pos = 0;
  if (pos > 4095) pos = 4095;
  return (int)pos;
}

static void printHelp() {
  Serial.println("=== ST3215-HS USB Serial Control ===");
  Serial.println("Commands:");
  Serial.println("  DEG <0..360>      : move to angle deg (position mode)");
  Serial.println("  POS <0..4095>     : move to raw position steps");
  Serial.println("  SPEED <0..2000>   : set speed (steps/s)");
  Serial.println("  ACC <0..255>      : set acceleration");
  Serial.println("  ID                : print current servo ID");
  Serial.println("  RESCAN            : rescan IDs 0..253");
  Serial.println("  HELP              : show this help");
  Serial.println("Examples:");
  Serial.println("  DEG 180");
  Serial.println("  SPEED 800");
  Serial.println("  POS 2048");
}

static void scanServoIDs() {
  Serial.println("Scanning servo IDs (0..253) ...");
  g_servo_id = -1;
  for (int id = 0; id <= 253; id++) {
    int ret = st.Ping(id);
    if (ret != -1) {
      g_servo_id = ret;
      Serial.print("FOUND servo ID = ");
      Serial.println(g_servo_id);
      break;
    }
    delay(15);
  }
  if (g_servo_id < 0) {
    Serial.println("No servo found. Check wiring/power/baud/jumper.");
  }
}

static void movePos(int pos) {
  if (g_servo_id < 0) {
    Serial.println("ERR: servo ID not set (try RESCAN).");
    return;
  }
  if (pos < 0) pos = 0;
  if (pos > 4095) pos = 4095;
  st.WritePosEx(g_servo_id, pos, g_speed, g_acc);
  Serial.print("OK POS ");
  Serial.print(pos);
  Serial.print(" (speed=");
  Serial.print(g_speed);
  Serial.print(", acc=");
  Serial.print(g_acc);
  Serial.println(")");
}

static void handleCommand(const String& line) {
  String s = line;
  s.trim();
  if (s.length() == 0) return;

  int sp = s.indexOf(' ');
  String cmd = (sp < 0) ? s : s.substring(0, sp);
  String arg = (sp < 0) ? "" : s.substring(sp + 1);
  cmd.toUpperCase();
  arg.trim();

  if (cmd == "HELP" || cmd == "?") {
    printHelp();
    return;
  }
  if (cmd == "ID") {
    Serial.print("servo_id=");
    Serial.println(g_servo_id);
    return;
  }
  if (cmd == "RESCAN") {
    scanServoIDs();
    return;
  }
  if (cmd == "SPEED") {
    int v = arg.toInt();
    if (v < 0) v = 0;
    if (v > 2000) v = 2000;
    g_speed = v;
    Serial.print("OK SPEED ");
    Serial.println(g_speed);
    return;
  }
  if (cmd == "ACC") {
    int v = arg.toInt();
    if (v < 0) v = 0;
    if (v > 255) v = 255;
    g_acc = v;
    Serial.print("OK ACC ");
    Serial.println(g_acc);
    return;
  }
  if (cmd == "POS") {
    int pos = arg.toInt();
    movePos(pos);
    return;
  }
  if (cmd == "DEG") {
    float deg = arg.toFloat();
    int pos = degToPos(deg);
    movePos(pos);
    return;
  }

  Serial.print("ERR: unknown cmd: ");
  Serial.println(cmd);
  Serial.println("Type HELP");
}

void setup() {
  Serial.begin(115200);
  unsigned long t0 = millis();
  while (!Serial && (millis() - t0 < 3000)) { delay(10); }

  Serial.println();
  Serial.println("Boot: ST3215-HS GUI Controller (SCServo/SMS_STS)");
  Serial.println("USB Serial: 115200");
  Serial.printf("Servo UART: Serial1 baud=%ld RX=%d TX=%d\n", SERVO_BAUD, RX_PIN, TX_PIN);

  Serial1.begin(SERVO_BAUD, SERIAL_8N1, RX_PIN, TX_PIN);
  delay(200);

  st.pSerial = &Serial1;

  printHelp();
  scanServoIDs();

  Serial.println("Ready. Send commands like: DEG 180");
}

void loop() {
  while (Serial.available() > 0) {
    char c = (char)Serial.read();
    if (c == '\r') continue;
    if (c == '\n') {
      handleCommand(g_line);
      g_line = "";
    } else {
      if (g_line.length() < 80) g_line += c;
    }
  }
}
