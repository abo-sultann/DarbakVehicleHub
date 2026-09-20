#include <Arduino.h>
#include <driver/twai.h>
#include <SPIFFS.h>
#include "HubConfig.h"

namespace {

constexpr char CAPTURE_FILE[] = "/can_capture.txt";
constexpr size_t MAX_CAPTURE_BYTES = 512 * 1024;
constexpr uint32_t FLUSH_INTERVAL_MS = 1000;

bool canStarted = false;
bool captureEnabled = false;
File captureFile;
uint32_t lastStatusMs = 0;
uint32_t lastFlushMs = 0;
uint32_t capturedFrames = 0;
uint32_t droppedFrames = 0;

void printStatus() {
  Serial.printf(
      "{\"v\":1,\"type\":\"status\",\"can\":\"%s\",\"capture\":%s,"
      "\"frames\":%lu,\"dropped\":%lu,\"bytes\":%u}\n",
      canStarted ? "listen_only" : "unavailable",
      captureEnabled ? "true" : "false",
      static_cast<unsigned long>(capturedFrames),
      static_cast<unsigned long>(droppedFrames),
      captureFile ? static_cast<unsigned>(captureFile.size()) : 0U);
}

bool startCanListenOnly() {
  twai_general_config_t g = TWAI_GENERAL_CONFIG_DEFAULT(
      static_cast<gpio_num_t>(PIN_CAN_TX),
      static_cast<gpio_num_t>(PIN_CAN_RX),
      TWAI_MODE_LISTEN_ONLY);
  twai_timing_config_t t = TWAI_TIMING_CONFIG_500KBITS();
  twai_filter_config_t f = TWAI_FILTER_CONFIG_ACCEPT_ALL();

  if (twai_driver_install(&g, &t, &f) != ESP_OK) return false;
  if (twai_start() != ESP_OK) {
    twai_driver_uninstall();
    return false;
  }
  return true;
}

String frameJson(const twai_message_t& m) {
  String line;
  line.reserve(110);
  line += "{\"v\":1,\"type\":\"can_raw\",\"ms\":";
  line += millis();
  line += ",\"id\":";
  line += static_cast<unsigned long>(m.identifier);
  line += ",\"ext\":";
  line += m.extd ? "true" : "false";
  line += ",\"dlc\":";
  line += m.data_length_code;
  line += ",\"data\":\"";
  const char hex[] = "0123456789ABCDEF";
  for (int i = 0; i < m.data_length_code; ++i) {
    line += hex[(m.data[i] >> 4) & 0x0F];
    line += hex[m.data[i] & 0x0F];
  }
  line += "\"}";
  return line;
}

void storeFrame(const twai_message_t& m) {
  const String line = frameJson(m);
  Serial.println(line);

  if (!captureEnabled || !captureFile) return;

  const size_t needed = line.length() + 1;
  if (captureFile.size() + needed > MAX_CAPTURE_BYTES) {
    captureEnabled = false;
    captureFile.flush();
    Serial.println("{\"v\":1,\"type\":\"capture\",\"state\":\"full\"}");
    return;
  }

  if (captureFile.println(line) > 0) {
    ++capturedFrames;
  } else {
    ++droppedFrames;
  }
}

void dumpCapture() {
  if (captureFile) captureFile.flush();
  File f = SPIFFS.open(CAPTURE_FILE, FILE_READ);
  if (!f) {
    Serial.println("{\"v\":1,\"type\":\"capture\",\"state\":\"missing\"}");
    return;
  }
  Serial.printf("{\"v\":1,\"type\":\"capture_dump\",\"bytes\":%u}\n",
                static_cast<unsigned>(f.size()));
  while (f.available()) Serial.write(f.read());
  Serial.println();
  f.close();
  Serial.println("{\"v\":1,\"type\":\"capture_dump\",\"state\":\"done\"}");
}

void eraseCapture() {
  if (captureFile) captureFile.close();
  SPIFFS.remove(CAPTURE_FILE);
  captureFile = SPIFFS.open(CAPTURE_FILE, FILE_WRITE);
  captureEnabled = static_cast<bool>(captureFile);
  capturedFrames = 0;
  droppedFrames = 0;
  Serial.println("{\"v\":1,\"type\":\"capture\",\"state\":\"erased\"}");
}

void handleSerialCommand() {
  if (!Serial.available()) return;
  String cmd = Serial.readStringUntil('\n');
  cmd.trim();
  cmd.toUpperCase();

  if (cmd == "DUMP") {
    dumpCapture();
  } else if (cmd == "ERASE") {
    eraseCapture();
  } else if (cmd == "STOP") {
    captureEnabled = false;
    if (captureFile) captureFile.flush();
    Serial.println("{\"v\":1,\"type\":\"capture\",\"state\":\"stopped\"}");
  } else if (cmd == "START") {
    captureEnabled = static_cast<bool>(captureFile);
    Serial.println("{\"v\":1,\"type\":\"capture\",\"state\":\"started\"}");
  } else if (cmd == "STATUS") {
    printStatus();
  }
}

} // namespace

void setup() {
  Serial.begin(SERIAL_BAUD);
  delay(300);

  if (SPIFFS.begin(true)) {
    captureFile = SPIFFS.open(CAPTURE_FILE, FILE_APPEND);
    captureEnabled = static_cast<bool>(captureFile) &&
                     captureFile.size() < MAX_CAPTURE_BYTES;
  }

  canStarted = startCanListenOnly();
  printStatus();
}

void loop() {
  handleSerialCommand();

  if (canStarted) {
    twai_message_t msg{};
    if (twai_receive(&msg, pdMS_TO_TICKS(5)) == ESP_OK) {
      storeFrame(msg);
    }
  }

  const uint32_t now = millis();
  if (captureFile && now - lastFlushMs >= FLUSH_INTERVAL_MS) {
    lastFlushMs = now;
    captureFile.flush();
  }
  if (now - lastStatusMs >= 10000) {
    lastStatusMs = now;
    printStatus();
  }
}
