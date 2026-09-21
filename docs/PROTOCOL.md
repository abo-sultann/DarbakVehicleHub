# Darbak Hub serial protocol

## Current TPMS branch: diagnostic protocol v3

The current ESP32 firmware emits `boot`, `status`, and `tpms_frame` JSON lines.
`tpms_frame` contains `payload_hex`, `integrity: "SUM8"`, `repeats`,
`repeat_confirmed`, `rx_ms`, and an explicitly provisional `id_candidate`.
`sensor_id`, `pressure_psi`, and `temperature_c` remain null while their field
mapping is unverified. `mapping_verified` is false. These diagnostic records
must not be presented as live tire measurements.

Rate-limited `TPMS_CANDIDATE` text lines retain real pulse evidence. Their H/L
labels describe the level **after** each edge. All capture tools must preserve
these non-JSON lines too. See [decoder evidence](TPMS_DECODER.md).

## Original v1 design (not emitted by the current diagnostic firmware)

Transport: USB serial, 115200 baud, UTF-8, newline-delimited JSON.

## Message types

### status
Reports hub subsystem health.

### tpms
Normalized tire measurement. `pos` is one of FL, FR, RL, RR, UNKNOWN.

### vehicle
Normalized vehicle values once decoded.

### can_raw
Raw CAN frame for discovery/logging. Android should not expose this in the driving UI.

## Compatibility rule
Unknown fields must be ignored. `v` is the protocol major version.
