/*
 * TomatoGuard ESP32 
 */

#include <WiFiManager.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>
#include "DHT.h"

#define DHTPIN    4
#define DHTTYPE   DHT11
#define SOIL_PIN  34

// Send every 15 minutes after first send
#define SEND_INTERVAL_MS  900000UL

const char* SERVER_URL = "https://c05-tomato-guard.hf.space/api/sensor";

DHT dht(DHTPIN, DHTTYPE);
WiFiManager wm;
char chipId[13];
unsigned long lastSendTime = 0;
bool firstSendDone = false;

void computeChipId() {
  uint64_t mac = ESP.getEfuseMac();
  snprintf(chipId, sizeof(chipId), "%012llX", (unsigned long long)mac);
}

void sendSensorData() {
  float temp = dht.readTemperature();
  float hum = dht.readHumidity();
  int rawSoil = analogRead(SOIL_PIN);
  int soilPercent = map(rawSoil, 4095, 1000, 0, 100);
  soilPercent = constrain(soilPercent, 0, 100);
  
  if (!isnan(temp) && !isnan(hum)) {
    
    Serial.println("\n📤 Sending Sensor Data");
    Serial.printf("Temp: %.1f°C, Humidity: %.1f%%, Soil: %d%%\n", temp, hum, soilPercent);
    
    String payload = "{";
    payload += "\"temperature\":" + String(temp) + ",";
    payload += "\"humidity\":" + String(hum) + ",";
    payload += "\"soil\":" + String(soilPercent) + ",";
    payload += "\"chip_id\":\"" + String(chipId) + "\"";
    payload += "}";
    
    HTTPClient http;
    http.begin(SERVER_URL);
    http.addHeader("Content-Type", "application/json");
    
    int code = http.POST(payload);
    Serial.print("Response: ");
    Serial.println(code);
    
    if (code == 200) {
      Serial.println("✅ Data sent!");
    }
    
    http.end();
  } else {
    Serial.println("❌ Sensor read failed");
  }
}

void setup() {
  Serial.begin(115200);
  delay(2000);
  
  computeChipId();
  dht.begin();
  analogReadResolution(12);
  
  Serial.println("\n=== TomatoGuard ESP32 ===");
  Serial.print("Chip ID: ");
  Serial.println(chipId);
  
  // Connect to WiFi
  wm.autoConnect("TomatoGuard-Setup");
  Serial.println("✅ WiFi Connected!");
  
  // Send data immediately on connection
  Serial.println("\n📡 Sending first reading immediately...");
  sendSensorData();
  lastSendTime = millis();
  firstSendDone = true;
}

void loop() {
  unsigned long now = millis();
  
  // After first send, wait SEND_INTERVAL_MS before next send
  if (firstSendDone && WiFi.status() == WL_CONNECTED && (now - lastSendTime >= SEND_INTERVAL_MS)) {
    lastSendTime = now;
    sendSensorData();
  }
  
  delay(1000);
}