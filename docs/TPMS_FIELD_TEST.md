# TPMS field test — ESP32 + CC1101

Current priority: external TPMS only. OBD/CAN is paused.

## Wiring
| CC1101 | ESP32 |
|---|---|
| VCC | 3.3V only |
| GND | GND |
| SCK | GPIO18 |
| MISO | GPIO19 |
| MOSI | GPIO23 |
| CSN/SS | GPIO5 |
| GDO0 | GPIO4 |
| GDO2 | GPIO2 |

**Do not power the CC1101 from 5V.**

## First capture
1. Flash the artifact DarbakVehicleHub-ESP32-TPMS.
2. Connect the CC1101 and antenna.
3. Put one known sensor close to the receiver; keep other sensors farther away where practical.
4. On Windows install Python + pyserial: `py -m pip install pyserial`.
5. Capture three minutes: `py firmware/tools/tpms_capture.py --port COM3 --label front_left --seconds 180`
6. Repeat for front_right, rear_left, rear_right.
7. Keep captures separate for protocol analysis.

## Safety rule — stale pressure
A displayed pressure is never considered live merely because a numeric value exists. Each decoded sensor must have a fresh RF receive timestamp. After the real sensor cadence is measured, a conservative timeout will be chosen. Once stale, pressure and temperature become unavailable and sensor state becomes offline/stale. Last-known values are diagnostics only, never live dashboard values.

At boot, cached pressure must not become live until a fresh valid RF packet is received.

## Acceptance gate
Do not merge a production decoder until captures prove stable sensor ID mapping, pressure conversion against the existing TPMS display/gauge, temperature conversion where transmitted, battery/status interpretation where transmitted, integrity/checksum validation if present, and stale/offline behavior after RF stops.
