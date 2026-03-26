/**
 * PIR Sensor Node for PX System (SeamlessTrack-PX4.2)
 * 
 * Hardware: SB612B (秋月電子 114064)
 * Board: Arduino Uno
 * 
 * Protocol: JSON over Serial (115200 baud)
 * Output format: {"event":"<type>","state":<0|1>,"ts":<millis>,"dur":<ms>}
 */

const int PIR_PIN = 2;          // PIR sensor OUT -> D2
const int LED_PIN = 13;         // Built-in LED for visual feedback
const int SENSOR_ID = 1;        // Sensor identifier (for multi-sensor setup)

// Timing constants
const unsigned long DEBOUNCE_MS = 50;       // Debounce time
const unsigned long HEARTBEAT_MS = 5000;    // Heartbeat interval

// State variables
int currentState = LOW;
int lastStableState = LOW;
unsigned long lastChangeTime = 0;
unsigned long detectionStartTime = 0;
unsigned long lastHeartbeat = 0;
bool inDetection = false;

void setup() {
  pinMode(PIR_PIN, INPUT);
  pinMode(LED_PIN, OUTPUT);
  
  Serial.begin(115200);
  
  // Wait for sensor stabilization (SB612B needs ~30s warm-up)
  delay(1000);
  
  // Send init message
  sendEvent("init", 0, 0);
  
  // Initial state read
  lastStableState = digitalRead(PIR_PIN);
}

void loop() {
  unsigned long now = millis();
  int rawState = digitalRead(PIR_PIN);
  
  // Debounce logic
  if (rawState != currentState) {
    lastChangeTime = now;
    currentState = rawState;
  }
  
  // State transition after debounce period
  if ((now - lastChangeTime) > DEBOUNCE_MS && currentState != lastStableState) {
    lastStableState = currentState;
    
    if (currentState == HIGH) {
      // Detection started
      inDetection = true;
      detectionStartTime = now;
      digitalWrite(LED_PIN, HIGH);
      sendEvent("detect_start", 1, 0);
      
    } else {
      // Detection ended
      unsigned long duration = now - detectionStartTime;
      inDetection = false;
      digitalWrite(LED_PIN, LOW);
      sendEvent("detect_end", 0, duration);
    }
  }
  
  // Periodic heartbeat (confirms sensor is alive)
  if ((now - lastHeartbeat) >= HEARTBEAT_MS) {
    lastHeartbeat = now;
    sendHeartbeat();
  }
  
  delay(10);  // Small delay for stability
}

/**
 * Send structured event as JSON
 */
void sendEvent(const char* eventType, int state, unsigned long duration) {
  Serial.print("{\"event\":\"");
  Serial.print(eventType);
  Serial.print("\",\"sensor_id\":");
  Serial.print(SENSOR_ID);
  Serial.print(",\"state\":");
  Serial.print(state);
  Serial.print(",\"ts\":");
  Serial.print(millis());
  Serial.print(",\"dur\":");
  Serial.print(duration);
  Serial.println("}");
}

/**
 * Send heartbeat with current state
 */
void sendHeartbeat() {
  unsigned long dur = 0;
  if (inDetection) {
    dur = millis() - detectionStartTime;
  }
  
  Serial.print("{\"event\":\"heartbeat\",\"sensor_id\":");
  Serial.print(SENSOR_ID);
  Serial.print(",\"state\":");
  Serial.print(lastStableState);
  Serial.print(",\"ts\":");
  Serial.print(millis());
  Serial.print(",\"dur\":");
  Serial.print(dur);
  Serial.println("}");
}
