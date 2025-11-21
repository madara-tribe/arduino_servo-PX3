#include <ESP8266WiFi.h>
#include <Servo.h>

const char* ssid = "aterm-1e967a-g";         // Wi-Fi SSID
const char* password = "00e13cbb72530";     // Wi-Fi Password

WiFiServer server(1234);
Servo myservo;

void setup() {
  Serial.begin(115200);
  WiFi.begin(ssid, password);

  Serial.print("Connecting to Wi-Fi");
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }

  Serial.println();
  Serial.print("Connected! IP address: ");
  Serial.println(WiFi.localIP());

  server.begin();
  myservo.attach(5);  // GPIO5
}

void loop() {
  WiFiClient client = server.available();
  if (client) {
    Serial.println("Client connected");

    String input = "";
    while (client.connected()) {
      while (client.available()) {
        char c = client.read();
        if (c == '\n') {
          int angle = input.toInt();
          angle = constrain(angle, 0, 180);
          myservo.write(angle);
          Serial.print("Set angle to: ");
          Serial.println(angle);
          client.println("OK");
          input = "";
        } else {
          input += c;
        }
      }
    }
    client.stop();
    Serial.println("Client disconnected");
  }
}
