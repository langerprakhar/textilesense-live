#include <WiFi.h>
#include <WiFiClientSecure.h>
#include <HTTPClient.h>
#include "settings.h"

char bootId[9];
uint32_t seq = 0;

void setup() {
  Serial.begin(115200);
  snprintf(bootId, sizeof(bootId), "%08lx", (unsigned long)esp_random());
  analogReadResolution(12);
  WiFi.mode(WIFI_STA);
  WiFi.setAutoReconnect(true);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  configTime(0, 0, "pool.ntp.org");
}

void loop() {
  if (WiFi.status() == WL_CONNECTED) {
    WiFiClientSecure client;
    client.setCACert(ROOT_CA);
    HTTPClient http;
    if (http.begin(client, PROBE_URL)) {
      http.addHeader("Content-Type", "application/json");
      http.addHeader("Authorization", String("Bearer ") + PROBE_TOKEN);
      char payload[180];
      snprintf(payload, sizeof(payload),
               "{\"source\":\"physical FSR\",\"boot\":\"%s\",\"seq\":%lu,\"adc\":%d,\"uptime_ms\":%lu}",
               bootId, (unsigned long)seq++, analogRead(34), millis());
      int status = http.POST(String(payload));
      Serial.printf("sample HTTP status %d\n", status);
      http.end();
    }
  }
  delay(1000);
}
