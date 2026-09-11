# Darbak Hub serial protocol v1

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
