# Darbak Vehicle Hub — approved project decisions

Updated: 2026-09-11
Owner identity: Darbak / AbuSultan

## Target hardware
- Toyota Android head unit, Allwinner T3 class.
- Android 7.1 / API 25 baseline.
- 1024x600 landscape, Arabic RTL.
- Low RAM/CPU: native Android, minimal animation, offline-first.

## V1 hardware
- Existing ESP32 DevKit / WROOM-32 class board.
- CC1101 433 MHz with antenna, tuned to 433.92 MHz for the external TPMS sensors.
- SN65HVD230 3.3 V CAN transceiver.
- OBD-II male breakout/extension to open wires.
- ESP32 powered from the head-unit USB; OBD pin 16 is not used for V1 power.
- SN65HVD230 120-ohm termination jumper remains open when attached to the vehicle bus.

## Safety policy
- CAN begins in listen-only mode.
- No vehicle control frames are transmitted during discovery.
- No cutting factory vehicle wiring; use OBD-II breakout.
- New sensors are added only when the vehicle does not already expose the required data.

## Product scope
Darbak Vehicle Hub is the vehicle-data gateway for the Darbak ecosystem, not just a TPMS app.
It will normalize and share TPMS + CAN/OBD telemetry with Launcher 2026, maintenance,
diagnostics and future Darbak apps.

## UI identity — Darbak 2.0
- Dark navy/black automotive canvas.
- Blue/neon accents, subtle glass panels, thin luminous borders.
- White primary text and muted blue-gray secondary text.
- Large touch targets designed for 1024x600.
- No unnecessary permanent bottom bar.
- Arabic RTL first.
- About/ownership language follows Darbak identity: "دربك", "طريقك أسهل", "تصميم وتطوير • أبوسلطان".
- Internal screens should remain visually consistent with the approved Darbak 2.0 settings/about language.

## Development before hardware arrival
- Simulator-first Android dashboard.
- Stable serial protocol between ESP32 and Android.
- CAN raw-frame discovery pipeline.
- TPMS raw-packet discovery path prepared for CC1101 integration.
- Real vehicle/TPMS decoding is completed only after hardware arrives and captures are available.
