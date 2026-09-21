#include <Arduino.h>
#include <SPI.h>
#include <ELECHOUSE_CC1101_SRC_DRV.h>
#include "HubConfig.h"

namespace {
constexpr uint32_t STATUS_MS = 10000;
constexpr uint32_t FRAME_GAP_US = 6000;
constexpr size_t MAX_EDGES = 1024;

volatile uint32_t edgeUs[MAX_EDGES];
volatile uint8_t edgeLevel[MAX_EDGES];
volatile size_t edgeCount = 0;
volatile uint32_t lastEdgeUs = 0;
volatile bool overflowed = false;

uint32_t lastStatus = 0;
uint32_t rawFrameCount = 0;

void IRAM_ATTR onGdo0Edge() {
  uint32_t now = micros();
  size_t i = edgeCount;
  if (i < MAX_EDGES) {
    edgeUs[i] = now;
    edgeLevel[i] = (uint8_t)digitalRead(PIN_CC1101_GDO0);
    edgeCount = i + 1;
    lastEdgeUs = now;
  } else {
    overflowed = true;
  }
}

void printStatus() {
  Serial.printf("{\"v\":1,\"type\":\"status\",\"mode\":\"tpms_raw_async\",\"rf_mhz\":%.2f,\"raw_frames\":%lu}\n",
                TPMS_CENTER_MHZ, (unsigned long)rawFrameCount);
}

void emitFrame() {
  noInterrupts();
  size_t n = edgeCount;
  bool ov = overflowed;
  static uint32_t t[MAX_EDGES];
  static uint8_t l[MAX_EDGES];
  if (n > MAX_EDGES) n = MAX_EDGES;
  for (size_t i = 0; i < n; ++i) { t[i] = edgeUs[i]; l[i] = edgeLevel[i]; }
  edgeCount = 0;
  overflowed = false;
  interrupts();

  if (n < 8) return;
  ++rawFrameCount;
  Serial.printf("RAW_FRAME n=%u overflow=%u rssi=%d us=", (unsigned)n, ov ? 1 : 0, ELECHOUSE_cc1101.getRssi());
  for (size_t i = 1; i < n; ++i) {
    Serial.print((unsigned long)(t[i] - t[i - 1]));
    Serial.print(l[i] ? 'H' : 'L');
    if (i + 1 < n) Serial.print(',');
  }
  Serial.println();
}

void initRadio() {
  SPI.begin(PIN_CC1101_SCK, PIN_CC1101_MISO, PIN_CC1101_MOSI, PIN_CC1101_CSN);
  ELECHOUSE_cc1101.setSpiPin(PIN_CC1101_SCK, PIN_CC1101_MISO, PIN_CC1101_MOSI, PIN_CC1101_CSN);
  ELECHOUSE_cc1101.Init();
  ELECHOUSE_cc1101.setGDO0(PIN_CC1101_GDO0);
  ELECHOUSE_cc1101.setMHZ(TPMS_CENTER_MHZ);
  ELECHOUSE_cc1101.setModulation(2); // ASK/OOK discovery
  ELECHOUSE_cc1101.setRxBW(325.0);
  ELECHOUSE_cc1101.setSyncMode(0);   // no sync qualifier
  ELECHOUSE_cc1101.setPktFormat(3);  // asynchronous serial: demodulated data on GDO
  ELECHOUSE_cc1101.SetRx();

  pinMode(PIN_CC1101_GDO0, INPUT);
  attachInterrupt(digitalPinToInterrupt(PIN_CC1101_GDO0), onGdo0Edge, CHANGE);
}
}

void setup() {
  Serial.begin(SERIAL_BAUD);
  delay(500);
  Serial.println("{\"v\":1,\"type\":\"boot\",\"mode\":\"tpms_raw_async\",\"rf\":\"433.92MHz\",\"gdo0\":4}");
  initRadio();
  printStatus();
}

void loop() {
  uint32_t nowUs = micros();
  size_t n;
  uint32_t last;
  noInterrupts();
  n = edgeCount;
  last = lastEdgeUs;
  interrupts();

  if (n >= 8 && (uint32_t)(nowUs - last) > FRAME_GAP_US) emitFrame();

  uint32_t now = millis();
  if (now - lastStatus >= STATUS_MS) {
    lastStatus = now;
    printStatus();
  }
}
