// Ghala node: DHT22 temperature + humidity -> signed HTTPS POST to /iot/readings.
// Store-and-forward: readings taken while offline are buffered (with their original
// timestamps) and uploaded when Wi-Fi returns.
//
// The API verifies HMAC-SHA256 over the JSON {"device_id","readings","seq","ts"} with
// sorted keys and no spaces, values printed with one decimal (e.g. 27.4, 60.0).
#include <Arduino.h>
#include <DHT.h>
#include <HTTPClient.h>
#include <WiFi.h>
#include <mbedtls/md.h>
#include <time.h>

#include "secrets.h"  // WIFI_SSID, WIFI_PASS, API_URL, DEVICE_ID, DEVICE_SECRET (never commit)

#define DHT_PIN 4
#define READ_EVERY_MS (15UL * 60UL * 1000UL)
#define BUFFER_SIZE 96  // 24 h at 15-minute intervals

DHT dht(DHT_PIN, DHT22);

struct Reading {
  char ts[21];
  float temperature;
  float humidity;
  uint32_t seq;
};
Reading buffer[BUFFER_SIZE];
int buffered = 0;
uint32_t seq = 0;

String hmacHex(const String &key, const String &msg) {
  byte out[32];
  mbedtls_md_context_t ctx;
  mbedtls_md_init(&ctx);
  mbedtls_md_setup(&ctx, mbedtls_md_info_from_type(MBEDTLS_MD_SHA256), 1);
  mbedtls_md_hmac_starts(&ctx, (const unsigned char *)key.c_str(), key.length());
  mbedtls_md_hmac_update(&ctx, (const unsigned char *)msg.c_str(), msg.length());
  mbedtls_md_hmac_finish(&ctx, out);
  mbedtls_md_free(&ctx);
  String hex;
  for (byte b : out) {
    char h[3];
    sprintf(h, "%02x", b);
    hex += h;
  }
  return hex;
}

bool upload(const Reading &r) {
  // Keys in sorted order, no spaces: must match the server's canonical form exactly.
  String readings = "{\"humidity_pct\":" + String(r.humidity, 1) + ",\"temperature_c\":" + String(r.temperature, 1) + "}";
  String signedPart = "{\"device_id\":\"" + String(DEVICE_ID) + "\",\"readings\":" + readings + ",\"seq\":" + String(r.seq) +
                      ",\"ts\":\"" + String(r.ts) + "\"}";
  String body = signedPart.substring(0, signedPart.length() - 1) + ",\"sig\":\"hmac-sha256:" + hmacHex(DEVICE_SECRET, signedPart) + "\"}";
  HTTPClient http;
  http.begin(String(API_URL) + "/iot/readings");
  http.addHeader("Content-Type", "application/json");
  int code = http.POST(body);
  http.end();
  return code == 201 || code == 409;  // 409 = already received (replay), safe to drop
}

void setup() {
  Serial.begin(115200);
  dht.begin();
  WiFi.begin(WIFI_SSID, WIFI_PASS);
  configTime(0, 0, "pool.ntp.org");
  seq = (uint32_t)time(nullptr);
}

void loop() {
  float t = dht.readTemperature();
  float h = dht.readHumidity();
  time_t now = time(nullptr);
  if (!isnan(t) && !isnan(h) && now > 1700000000) {
    Reading r;
    strftime(r.ts, sizeof(r.ts), "%Y-%m-%dT%H:%M:%SZ", gmtime(&now));
    r.temperature = t;
    r.humidity = h;
    r.seq = ++seq;
    if (buffered < BUFFER_SIZE) buffer[buffered++] = r;
  }
  if (WiFi.status() == WL_CONNECTED) {
    int sent = 0;
    while (sent < buffered && upload(buffer[sent])) sent++;
    memmove(buffer, buffer + sent, (buffered - sent) * sizeof(Reading));
    buffered -= sent;
  }
  delay(READ_EVERY_MS);
}
