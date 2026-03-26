const int SENSOR_PIN = 2;   // IR sensor OUT -> D2
const int LED_PIN = 13;     // Uno built-in LED

int lastState = -1;

void setup() {
  pinMode(SENSOR_PIN, INPUT);
  pinMode(LED_PIN, OUTPUT);

  Serial.begin(115200);
  delay(1000);

  Serial.println("IR sensor test start");
}

void loop() {
  int state = digitalRead(SENSOR_PIN);

  if (state != lastState) {
    lastState = state;

    if (state == HIGH) {
      digitalWrite(LED_PIN, HIGH);
      Serial.println("DETECTED");
    } else {
      digitalWrite(LED_PIN, LOW);
      Serial.println("NOT_DETECTED");
    }
  }

  delay(20);
}