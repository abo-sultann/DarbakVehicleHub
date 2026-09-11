# Hardware V1

## ESP32 -> CC1101
- 3V3 -> VCC
- GND -> GND
- GPIO18 -> SCK
- GPIO19 -> MISO/GDO1
- GPIO23 -> MOSI
- GPIO5 -> CSN
- GPIO4 -> GDO0
- GPIO2 -> GDO2

## ESP32 -> SN65HVD230
- 3V3 -> 3.3V
- GND -> GND
- GPIO21 -> TX
- GPIO22 -> RX

## OBD-II -> SN65HVD230
- Pin 6 -> CANH
- Pin 14 -> CANL
- Pin 4/5 -> GND

Do not use OBD pin 16 to power the ESP32 in V1.
Open/remove the SN65HVD230 120-ohm termination jumper when connected to the vehicle CAN bus.
