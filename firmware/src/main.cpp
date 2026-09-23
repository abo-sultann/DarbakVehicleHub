#include <Arduino.h>
#include <SPI.h>
#include <ELECHOUSE_CC1101_SRC_DRV.h>
#include "HubConfig.h"
#include "TpmsDecoder.h"

#ifndef TPMS_BUILD_SHA
#define TPMS_BUILD_SHA "local"
#endif

namespace {
constexpr size_t EDGE_CAPACITY = 4096;
constexpr uint32_t IDLE_US = 6000;
struct Edge { uint32_t us; uint8_t after; };
volatile Edge edges[EDGE_CAPACITY];
volatile size_t edgeRead = 0, edgeWrite = 0;
volatile uint32_t droppedEdges = 0, lastEdgeUs = 0;
portMUX_TYPE edgeMux = portMUX_INITIALIZER_UNLOCKED;
tpms::Decoder decoder;
tpms::Repeats repeats;
bool havePrevious = false;
Edge previous = {};
uint32_t handledDrops = 0, lastStatusMs = 0, frameSequence = 0;
uint32_t rawSequence = 0, lastRawMs = 0;
uint16_t rawDuration[200];
bool rawAfter[200];
size_t rawCount = 0;
bool rawOverflow = false;

void IRAM_ATTR onGdo0Edge() {
  const uint32_t now = micros();
  const uint8_t level = digitalRead(PIN_CC1101_GDO0);
  portENTER_CRITICAL_ISR(&edgeMux);
  lastEdgeUs = now;  // Update even on overflow.
  const size_t next = (edgeWrite + 1) % EDGE_CAPACITY;
  if (next != edgeRead) {
    edges[edgeWrite].us = now;
    edges[edgeWrite].after = level;
    edgeWrite = next;
  } else { ++droppedEdges; }
  portEXIT_CRITICAL_ISR(&edgeMux);
}

bool nextEdge(Edge &out) {
  portENTER_CRITICAL(&edgeMux);
  if (handledDrops != droppedEdges) {
    handledDrops = droppedEdges;
    edgeRead = edgeWrite;
    havePrevious = false;
    decoder.reset();
    rawCount = 0;
    rawOverflow = false;
  }
  const bool available = edgeRead != edgeWrite;
  if (available) {
    out.us = edges[edgeRead].us;
    out.after = edges[edgeRead].after;
    edgeRead = (edgeRead + 1) % EDGE_CAPACITY;
  }
  portEXIT_CRITICAL(&edgeMux);
  return available;
}

void emitFrame(const tpms::Frame &frame) {
  const uint16_t count = repeats.observe(frame, millis());
  char payload[21];
  for (unsigned i = 0; i < 10; ++i) snprintf(payload + 2*i, 3, "%02X", frame.bytes[i]);
  Serial.printf("{\"v\":3,\"type\":\"tpms_frame\",\"seq\":%lu,\"rx_ms\":%lu,"
                "\"protocol\":\"darbak_capture_80_lsb\",\"payload_hex\":\"%s\","
                "\"integrity\":\"SUM8\",\"repeats\":%u,\"repeat_confirmed\":%s,"
                "\"id_candidate\":\"%02X%02X%02X%02X\",\"id_candidate_range\":\"bytes_0_3\","
                "\"sensor_id\":null,\"pressure_psi\":null,\"temperature_c\":null,"
                "\"preamble_bits\":%u,\"gap_tail\":%s,\"raw_b5_b6\":%u,\"raw_b7\":%u,"
                "\"adaptive_timing\":%s,\"short_low_us\":%u,\"short_high_us\":%u,"
                "\"mapping_verified\":false}\n",
    (unsigned long)++frameSequence, (unsigned long)millis(), payload,
    count, count >= 2 ? "true" : "false",
    frame.bytes[0], frame.bytes[1], frame.bytes[2], frame.bytes[3],
    frame.preambleBits, frame.gapTail ? "true" : "false",
    (unsigned(frame.bytes[5]) << 8) | frame.bytes[6], unsigned(frame.bytes[7]),
    frame.adaptiveTiming ? "true" : "false", frame.shortLowUs, frame.shortHighUs);
}

void finishRaw(bool valid) {
  // Preserve the previous capture format: H/L label the level AFTER the edge.
  // Rate-limit full pulse dumps so Serial never permanently starves reception.
  const uint32_t now = millis();
  if (!rawOverflow && rawCount >= 100 && rawCount <= 192 &&
      (rawSequence == 0 || now - lastRawMs >= 1000)) {
    lastRawMs = now;
    Serial.printf("TPMS_CANDIDATE seq=%lu scope=packet decoded=%u levels=after_edge pulses=",
                  (unsigned long)++rawSequence, valid ? 1 : 0);
    for (size_t i = 0; i < rawCount; ++i)
      Serial.printf("%s%u%c", i ? "," : "", rawDuration[i], rawAfter[i] ? 'H' : 'L');
    Serial.println();
  }
  rawCount = 0;
  rawOverflow = false;
}

void processEdge(const Edge &edge) {
  if (havePrevious) {
    const uint32_t duration = edge.us - previous.us;
    tpms::Frame frame;
    // The previous edge defines the level actually held over this interval.
    const bool valid = decoder.pulse(duration, previous.after != 0, frame);
    if (duration >= 650) {
      if (valid) emitFrame(frame);
      finishRaw(valid);
    } else if (rawCount < 200) {
      rawDuration[rawCount] = duration;
      rawAfter[rawCount++] = edge.after != 0;
    } else { rawOverflow = true; }
    if (edge.after == previous.after) {
      // A missed edge must never be repaired by inventing a half-bit.
      decoder.reset();
      rawOverflow = true;
    }
  }
  previous = edge;
  havePrevious = true;
}

void printStatus() {
  const auto &c = decoder.counters;
  Serial.printf("{\"v\":3,\"type\":\"status\",\"mode\":\"tpms_frame_decoder\","
                "\"build\":\"%s\",\"rf_mhz\":433.92,\"valid_frames\":%lu,"
                "\"dropped_edges\":%lu,\"reject_timing\":%lu,\"reject_length\":%lu,"
                "\"timing_recovered\":%lu,"
                "\"reject_manchester\":%lu,\"reject_preamble\":%lu,\"reject_checksum\":%lu}\n",
    TPMS_BUILD_SHA, (unsigned long)c.valid, (unsigned long)handledDrops,
    (unsigned long)c.timing, (unsigned long)c.length,
    (unsigned long)c.timingRecovered,
    (unsigned long)c.manchester, (unsigned long)c.preamble, (unsigned long)c.checksum);
}

void initRadio() {
  // Preserve the proven receive profile. No RSSI acceptance/rejection gate.
  SPI.begin(PIN_CC1101_SCK, PIN_CC1101_MISO, PIN_CC1101_MOSI, PIN_CC1101_CSN);
  ELECHOUSE_cc1101.setSpiPin(PIN_CC1101_SCK, PIN_CC1101_MISO, PIN_CC1101_MOSI, PIN_CC1101_CSN);
  ELECHOUSE_cc1101.Init();
  ELECHOUSE_cc1101.setGDO0(PIN_CC1101_GDO0);
  ELECHOUSE_cc1101.setMHZ(TPMS_CENTER_MHZ);
  ELECHOUSE_cc1101.setModulation(2);
  ELECHOUSE_cc1101.setRxBW(325.0);
  ELECHOUSE_cc1101.setSyncMode(0);
  ELECHOUSE_cc1101.setPktFormat(3);
  ELECHOUSE_cc1101.SetRx();
  pinMode(PIN_CC1101_GDO0, INPUT);
  attachInterrupt(digitalPinToInterrupt(PIN_CC1101_GDO0), onGdo0Edge, CHANGE);
}
}  // namespace

void setup() {
  Serial.begin(SERIAL_BAUD);
  delay(500);
  Serial.println("{\"v\":3,\"type\":\"boot\",\"mode\":\"tpms_frame_decoder\","
                 "\"mapping_verified\":false,\"rssi_filter\":false}");
  initRadio();
  printStatus();
}

void loop() {
  Edge edge;
  for (size_t i = 0; i < EDGE_CAPACITY && nextEdge(edge); ++i) processEdge(edge);
  portENTER_CRITICAL(&edgeMux);
  const bool empty = edgeRead == edgeWrite;
  const uint32_t last = lastEdgeUs;
  portEXIT_CRITICAL(&edgeMux);
  if (empty && havePrevious && (uint32_t)(micros() - last) > IDLE_US) {
    tpms::Frame frame;
    const bool valid = decoder.finishGap(previous.after != 0, frame);
    if (valid) emitFrame(frame);
    finishRaw(valid);
    havePrevious = false;
  }
  if (millis() - lastStatusMs >= 10000) {
    lastStatusMs = millis();
    printStatus();
  }
  delay(1);
}
