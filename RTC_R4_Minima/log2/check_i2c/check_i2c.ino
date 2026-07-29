#include <Wire.h>
void setup() {
  Serial.begin(9600);
  while (!Serial && millis() < 3000);
  Wire.begin();
}
void loop() {
  Wire.beginTransmission(0x68);
  byte err = Wire.endTransmission();
  Serial.print("0x68 status: ");
  Serial.println(err == 0 ? "FOUND" : "NOT FOUND (err=" + String(err) + ")");
  delay(2000);
}
