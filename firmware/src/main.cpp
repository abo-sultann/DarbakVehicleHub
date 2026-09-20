#include <Arduino.h>
#include <driver/twai.h>
#include <SPIFFS.h>
#include "HubConfig.h"

namespace {

constexpr char CAPTURE_FILE[] = "/can_capture.txt";
constexpr size_t MAX_CAPTURE_BYTES = 384 * 1024;
constexpr uint32_t FLUSH_INTERVAL_MS = 1000;

bool canStarted = false;
bool captureEnabled = false;
File captureFile;
size_t captureBytes = 0;
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
      static_cast<unsigned>(captureBytes));
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
  char head[96];
  snprintf(head, sizeof(head),
           "{\"v\":1,\"type\":\"can_raw\",\"ms\":%lu,\"id\":%lu,\"ext\":%s,\"dlc\":%u,\"data\":\"",
           static_cast<unsigned long>(millis()),
           static_cast<unsigned long>(m.identifier),
           m.extd ? "true" : "false",
           m.data_length_code);
  String line(head);
  line.reserve(120);
  static const char HEX_DIGITS[] = "0123456789ABCDEF";
  for (uint8_t i = 0; i < m.data_length_code; ++i) {
    line += HEX_DIGITS[(m.data[i] >> 4) & 0x0F];
    line += HEX_DIGITS[m.data[i] & 0x0F];
  }
  line += "\"}";
  return line;
}

void storeFrame(const twai_message_t& m) {
  const String line = frameJson(m);
  Serial.println(line);
  if (!captureEnabled || !captureFile) return;

  const size_t needed = line.length() + 1;
  if (captureBytes + needed > MAX_CAPTURE_BYTES) {
    captureEnabled = false;
    captureFile.flush();
    Serial.println("{\"v\":1,\"type\":\"capture\",\"state\":\"full\"}");
    return;
  }

  const size_t written = captureFile.println(line);
  if (written > 0) {
    captureBytes += written;
    ++capturedFrames;
  } else {
    ++droppedFrames;
  }
}

bool initCapture() {
  if (!SPIFFS.begin(false)) {
    Serial.println("{\"v\":1,\"type\":\"capture\",\"state\":\"spiffs_mount_failed_formatting\"}");
    if (!SPIFFS.format() || !SPIFFS.begin(false)) {
      Serial.println("{\"v\":1,\"type\":\"capture\",\"state\":\"spiffs_unavailable\"}");
      return false;
    }
    Serial.println("{\"v\":1,\"type\":\"capture\",\"state\":\"spiffs_formatted\"}");
  }

  // Each power-up is a fresh field-test session. This prevents old CAN data\n  // from being mixed with the next vehicle capture.\n  if (SPIFFS.exists(CAPTURE_FILE)) SPIFFS.remove(CAPTURE_FILE);\n  captureBytes = 0;\n\n  captureFile = SPIFFS.open(CAPTURE_FILE, FILE_WRITE);
  if (!captureFile) {
    Serial.println("{\"v\":1,\"type\":\"capture\",\"state\":\"open_failed\"}");
    return false;
  }
  return true;
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
  uint8_t buf[128];
  while (f.available()) {
    const size_t n = f.read(buf, sizeof(buf));
    Serial.write(buf, n);
    delay(1);
  }
  Serial.println();
  f.close();
  Serial.println("{\"v\":1,\"type\":\"capture_dump\",\"state\":\"done\"}");
}

void eraseCapture() {
  captureEnabled = false;
  if (captureFile) captureFile.close();
  SPIFFS.remove(CAPTURE_FILE);
  captureBytes = 0;
  capturedFrames = 0;
  droppedFrames = 0;
  captureFile = SPIFFS.open(CAPTURE_FILE, FILE_WRITE);
  captureEnabled = static_cast<bool>(captureFile);
  Serial.println("{\"v\":1,\"type\":\"capture\",\"state\":\"erased\"}");
}

void handleSerialCommand() {
  if (!Serial.available()) return;
  String cmd = Serial.readStringUntil('\n');
  cmd.trim();
  cmd.toUpperCase();
  if (cmd == "DUMP") dumpCapture();
  else if (cmd == "ERASE") eraseCapture();
  else if (cmd == "STOP") {
    captureEnabled = false;
    if (captureFile) captureFile.flush();
    Serial.println("{\"v\":1,\"type\":\"capture\",\"state\":\"stopped\"}");
  } else if (cmd == "START") {
    captureEnabled = static_cast<bool>(captureFile) && captureBytes < MAX_CAPTURE_BYTES;
    Serial.println("{\"v\":1,\"type\":\"capture\",\"state\":\"started\"}");
  } else if (cmd == "STATUS") printStatus();
}

} // namespace

void setup() {
  Serial.begin(SERIAL_BAUD);
  delay(500);
  Serial.println("{\"v\":1,\"type\":\"boot\",\"stage\":\"start\"}");

  captureEnabled = initCapture();
  canStarted = startCanListenOnly();
  printStatus();
}

void loop() {
  handleSerialCommand();

  if (canStarted) {
    twai_message_t msg{};
    if (twai_receive(&msg, pdMS_TO_TICKS(5)) == ESP_OK) storeFrame(msg);
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
