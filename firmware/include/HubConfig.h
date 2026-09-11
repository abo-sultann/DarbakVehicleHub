#pragma once

// CC1101 SPI wiring (ESP32 DevKit / WROOM-32)
static constexpr int PIN_CC1101_SCK  = 18;
static constexpr int PIN_CC1101_MISO = 19;
static constexpr int PIN_CC1101_MOSI = 23;
static constexpr int PIN_CC1101_CSN  = 5;
static constexpr int PIN_CC1101_GDO0 = 4;
static constexpr int PIN_CC1101_GDO2 = 2;

// ESP32 TWAI pins to SN65HVD230.
// These are intentionally separate from the SPI pins.
static constexpr int PIN_CAN_TX = 21;
static constexpr int PIN_CAN_RX = 22;

static constexpr uint32_t SERIAL_BAUD = 115200;
static constexpr bool CAN_LISTEN_ONLY_DEFAULT = true;
static constexpr float TPMS_CENTER_MHZ = 433.92f;
