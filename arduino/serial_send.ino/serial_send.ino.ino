void setup() {
  Serial.begin(9600);
}

void loop() {
  static int count = 0;
  Serial.println(count);  // println not print
  count++;
  if (count == 10)
    count = 0;
  delay(1000);
}
