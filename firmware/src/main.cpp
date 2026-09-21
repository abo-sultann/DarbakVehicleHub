#include <Arduino.h>
#include <SPI.h>
#include <ELECHOUSE_CC1101_SRC_DRV.h>
#include "HubConfig.h"

namespace {
constexpr uint32_t STATUS_MS = 10000;
uint32_t lastStatus = 0;
uint32_t packetCount = 0;

void printStatus() {
  Serial.printf("{\"v\":1,\"type\":\"status\",\"mode\":\"tpms_only\",\"rf_mhz\":%.2f,\"packets\":%lu}\n",
                TPMS_CENTER_MHZ, (unsigned long)packetCount);
}

void printRaw(const byte* data, int len, int rssi, byte lqi) {
  Serial.printf("{\"v\":1,\"type\":\"tpms_raw\",\"ms\":%lu,\"rssi\":%d,\"lqi\":%u,\"len\":%d,\"data\":\"",
                (unsigned long)millis(), rssi, lqi, len);
  static const char hex[]="0123456789ABCDEF";
  for (int i=0;i<len;i++){ Serial.print(hex[(data[i]>>4)&15]); Serial.print(hex[data[i]&15]); }
  Serial.println("\"}");
}

void initRadio() {
  SPI.begin(PIN_CC1101_SCK, PIN_CC1101_MISO, PIN_CC1101_MOSI, PIN_CC1101_CSN);
  ELECHOUSE_cc1101.setSpiPin(PIN_CC1101_SCK, PIN_CC1101_MISO, PIN_CC1101_MOSI, PIN_CC1101_CSN);
  ELECHOUSE_cc1101.Init();
  ELECHOUSE_cc1101.setMHZ(TPMS_CENTER_MHZ);
  // Discovery profile. Modulation/rate will be tightened after captures from the purchased sensors.
  ELECHOUSE_cc1101.setModulation(2); // ASK/OOK
  ELECHOUSE_cc1101.setRxBW(325.0);
  ELECHOUSE_cc1101.SetRx();
}
}

void setup() {
  Serial.begin(SERIAL_BAUD);
  delay(500);
  Serial.println("{\"v\":1,\"type\":\"boot\",\"mode\":\"tpms_only\",\"obd\":\"disabled\",\"rf\":\"433.92MHz_discovery\"}");
  initRadio();
  printStatus();
}

void loop() {
  if (ELECHOUSE_cc1101.CheckRxFifo(100)) {
    byte buf[64]{};
    int len = ELECHOUSE_cc1101.ReceiveData(buf);
    if (len > 0) {
      ++packetCount;
      printRaw(buf, len, ELECHOUSE_cc1101.getRssi(), ELECHOUSE_cc1101.getLqi());
    }
    ELECHOUSE_cc1101.SetRx();
  }
  uint32_t now=millis();
  if(now-lastStatus>=STATUS_MS){lastStatus=now;printStatus();}
}
