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
| GDO0 (module pin 3) | GPIO4 |
| GDO2 (module pin 8) | GPIO2 |

Purchased module pinout confirmed from its product sheet: 1=GND, 2=VCC, 3=GDO0, 4=CSN, 5=SCK, 6=MOSI, 7=MISO/GDO1, 8=GDO2. Module supply range is 1.8–3.6V, so use ESP32 3.3V only. The board is a CC1101 433 MHz module with adjustable 387–464 MHz range; project target remains 433.92 MHz.

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


## Purchased TPMS sensor confirmed specifications
The supplied TPMS manual confirms the external valve sensor transmits at **433.92 MHz**. Other documented sensor specifications: pressure range 0–6.08 bar, pressure accuracy 0.18 bar, temperature accuracy ±2°C, transmit power ≤5 dBm, and CR1632 replaceable battery. This confirms the project radio center frequency is correct; modulation, symbol rate, framing and payload layout still require RF captures and must not be guessed.

The original receiver supports four wheel positions (F.L/F.R/R.L/R.R), pressure-unit selection (bar/psi), temperature-unit selection (°C/°F), configurable pressure/temperature alarms, tire exchange, and tire matching. These receiver features are useful behavioral references but do not define the RF packet format.


## Decoder evidence plan
Use the original solar receiver as the ground-truth display during RF capture. For one sensor at a time, record repeated packets at several known pressure states and note the receiver's displayed pressure and temperature at each state. Compare only packets with the same sensor ID candidate. A field is accepted as pressure/temperature only when its decoded change tracks the receiver across multiple captures. Wheel identity is learned from repeated per-wheel captures, not assumed from packet order.

Because the manual does not document RF modulation, data rate, sync word, encoding, packet length, sensor ID layout, checksum/CRC, or transmit cadence, none of these are production constants yet. The current CC1101 ASK/OOK profile is discovery-only and must be changed if real captures show otherwise.

### Minimum capture matrix
- FL: normal pressure, then a small controlled pressure change, then restored pressure.
- FR/RL/RR: at least one stable capture each for ID separation.
- One sensor: capture long enough to measure normal transmit cadence.
- One sensor: stop/remove its RF source long enough to validate stale/offline behavior.

Never intentionally reduce a tire below a safe operating pressure for protocol discovery. A small controlled change can be performed on an unmounted/test sensor arrangement or by using normal service procedures and the original receiver as reference.


## Early go/no-go gate (avoid wasted effort)
Before building any Android decoder/UI integration, prove the RF path first. GO requires repeatable packets attributable to the purchased sensor and observable changes when that same sensor transmits. If the current packet-mode profile yields no reliable packets, do not conclude the project failed: switch the CC1101 discovery method/profile (modulation, bandwidth/data-rate/sync, or raw/asynchronous GDO capture) and retest at the manual-confirmed 433.92 MHz. Only after repeatable sensor-specific RF is captured should decoder implementation proceed.

Stop conditions: do not spend time on Android integration, wheel UI, or production stale timers while RF capture is unproven. This keeps failure cheap and early.
