#include <Arduino.h>
#include <driver/twai.h>
#include "HubConfig.h"

namespace {

bool canStarted = false;
uint32_t lastStatusMs = 0;

void printlnStatus(const char* canState, const char* tpmsState) {
  Serial.printf("{\"v\":1,\"type\":\"status\",\"can\":\"%s\",\"tpms\":\"%s\"}\n",
                canState, tpmsState);
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

void emitCanFrame(const twai_message_t& m) {
  Serial.printf("{\"v\":1,\"type\":\"can_raw\",\"id\":%lu,\"ext\":%s,\"dlc\":%u,\"data\":\"",
                static_cast<unsigned long>(m.identifier),
                m.extd ? "true" : "false",
                m.data_length_code);
  for (int i = 0; i < m.data_length_code; ++i) {
    if (m.data[i] < 0x10) Serial.print('0');
    Serial.print(m.data[i], HEX);
  }
  Serial.println("\"}");
}

} // namespace

void setup() {
  Serial.begin(SERIAL_BAUD);
  delay(300);

  canStarted = startCanListenOnly();
  printlnStatus(canStarted ? "listen_only" : "unavailable", "unavailable");
}

void loop() {
  if (canStarted) {
    twai_message_t msg{};
    if (twai_receive(&msg, pdMS_TO_TICKS(5)) == ESP_OK) {
      emitCanFrame(msg);
    }
  }

  const uint32_t now = millis();
  if (now - lastStatusMs >= 10000) {
    lastStatusMs = now;
    printlnStatus(canStarted ? "listen_only" : "unavailable", "unavailable");
  }
}
