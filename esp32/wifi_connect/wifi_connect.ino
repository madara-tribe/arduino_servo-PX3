
#include <WiFi.h>
#include <WebServer.h>
#include <ESPmDNS.h>

// Wi-Fi settings
const char* ssid = "aterm-1e967a-g";
const char* password = "00e13cbb72530";

// mDNS name -> http://esp32s3.local/
const char* mdnsName = "esp32s3";

WebServer server(80);

// Simple HTML page
String makeHtml() {
  String ip = WiFi.localIP().toString();
  long rssi = WiFi.RSSI();

  String html = "<!doctype html><html><head><meta charset='utf-8'>"
                "<meta name='viewport' content='width=device-width, initial-scale=1'>"
                "<title>ESP32-S3 Status</title></head><body style='font-family: sans-serif;'>"
                "<h2>ESP32-S3 Web Status</h2>";
  html += "<p><b>SSID:</b> " + String(ssid) + "</p>";
  html += "<p><b>IP:</b> " + ip + "</p>";
  html += "<p><b>RSSI:</b> " + String(rssi) + " dBm</p>";
  html += "<p><b>mDNS:</b> http://" + String(mdnsName) + ".local/</p>";
  html += "<hr><p>Endpoints: <code>/</code> <code>/json</code></p>";
  html += "</body></html>";
  return html;
}

void handleRoot() {
  server.send(200, "text/html; charset=utf-8", makeHtml());
}

void handleJson() {
  String json = "{";
  json += "\"ssid\":\"" + String(ssid) + "\",";
  json += "\"ip\":\"" + WiFi.localIP().toString() + "\",";
  json += "\"rssi\":" + String(WiFi.RSSI());
  json += "}";
  server.send(200, "application/json; charset=utf-8", json);
}

void setup() {
  Serial.begin(115200);
  unsigned long t0 = millis();
  while (!Serial && (millis() - t0 < 3000)) {
    delay(10);
  }

  Serial.println();
  Serial.println("Booted. Waiting 5 seconds before Wi-Fi connect...");
  delay(5000);  // (1) wait 5 seconds after launch

  WiFi.mode(WIFI_STA);
  Serial.print("Connecting to ");
  Serial.println(ssid);

  WiFi.begin(ssid, password);

  // Wait until connected
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }

  Serial.println();
  Serial.println("WiFi connected");
  Serial.print("IP address: ");
  Serial.println(WiFi.localIP());

  // (2) Start mDNS (optional, but useful)
  if (MDNS.begin(mdnsName)) {
    Serial.print("mDNS started: http://");
    Serial.print(mdnsName);
    Serial.println(".local/");
  } else {
    Serial.println("mDNS failed. Use IP address instead.");
  }

  // (2) Start Web Server
  server.on("/", handleRoot);
  server.on("/json", handleJson);
  server.begin();

  Serial.println("HTTP server started on port 80");
  Serial.println("Open in browser:");
  Serial.print("  http://");
  Serial.print(WiFi.localIP());
  Serial.println("/");
  Serial.print("  http://");
  Serial.print(mdnsName);
  Serial.println(".local/ (if supported)");
}

void loop() {
  server.handleClient();
}
