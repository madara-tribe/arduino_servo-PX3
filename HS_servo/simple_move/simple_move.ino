// ID Scan + Sweep example for Waveshare ST3215-HS (STS series) using SCServo (SMS_STS)
// Board: Arduino Nano ESP32 (ESP32-S3)
// Connection (UART mode on Bus Servo Adapter(A)):
//   ESP32 TX1(D1) -> Adapter UART TX
//   ESP32 RX0(D0) -> Adapter UART RX
//   ESP32 GND     -> Adapter GND
//
// IMPORTANT:
// - Bus Servo Adapter jumper must be set to "A" (UART-SERVO)
// - Adapter must be powered by external 9~12.6V (e.g., 12V), USB alone is NOT enough for the servo
// - Common GND between ESP32 and adapter is required

#include <Arduino.h>
#include <SCServo.h>

SMS_STS st;

// Nano ESP32 header UART pins: D0=RX, D1=TX
static const int RX_PIN = 0;   // D0 (RX0)
static const int TX_PIN = 1;   // D1 (TX1)
static const long SERVO_BAUD = 1000000;

int g_servo_id = -1;  // will be set by scan

// Simple helper: scan IDs
void scanServoIDs() {
  Serial.println("Scanning servo IDs (0..253) ...");
  bool found = false;
  for (int id = 0; id <= 253; id++) {
    int ret = st.Ping(id);   // success => returns id, fail => -1
    if (ret != -1) {
      Serial.print("FOUND servo ID = ");
      Serial.println(ret);
      g_servo_id = ret;
      found = true;
      // If you want to find ALL servos, comment out the break
      break;
    }
    delay(15);
  }
  if (!found) {
    Serial.println("No servo found. Check wiring/power/baud/jumper.");
  }
}

void setup() {
  Serial.begin(115200);
  unsigned long t0 = millis();
  while (!Serial && (millis() - t0 < 3000)) { delay(10); }
  Serial.println("Serial connected! (waiting done)");
  delay(300);

  Serial.println();
  Serial.println("=== ST3215-HS SCServo ID Scan + Sweep ===");

  // Servo UART
  Serial1.begin(SERVO_BAUD, SERIAL_8N1, RX_PIN, TX_PIN);
  delay(200);
  Serial.printf("Serial1 ready (RX=%d, TX=%d, baud=%ld)\n", RX_PIN, TX_PIN, SERVO_BAUD);

  // Tell library which serial port to use
  st.pSerial = &Serial1;

  // Scan
  scanServoIDs();
}

void loop() {
  static unsigned long last_log_ms = 0;
  if (millis() - last_log_ms > 1000) {
    last_log_ms = millis();
    Serial.println("loop running");
  }

  if (g_servo_id < 0) {
    // re-scan every 3 seconds until found
    delay(3000);
    scanServoIDs();
    return;
  }

  // ---- Sweep positions (0 -> 180 -> 360) ----
  // For STS series, position often uses 0..4095 steps for 0..360 deg
  const int id = g_servo_id;

  // Move to 0
  st.WritePosEx(id, 0, 500, 0);   // (id, position, speed, acc)
  delay(1200);

  // Move to 180 deg (approx 2048)
  st.WritePosEx(id, 2048, 500, 0);
  delay(1200);

  // Move to 360 deg (approx 4095)
  st.WritePosEx(id, 4095, 500, 0);
  delay(1200);
}