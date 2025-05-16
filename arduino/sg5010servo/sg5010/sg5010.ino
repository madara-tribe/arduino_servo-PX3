#include <Servo.h>

Servo myservo;  // create servo object

void setup() {
  Serial.begin(9600);  // start serial communication
  myservo.attach(9);   // servo control pin D9
}

void loop() {
  if (Serial.available() > 0) {        // check if there is incoming data
    int angle = Serial.parseInt();     // read integer from serial
    if (angle >= 0 && angle <= 180) {  // valid range
      myservo.write(angle);            // move servo
    }
    // (Optional) clear any remaining data
    while (Serial.available() > 0) {
      Serial.read();
    }
  }
}
