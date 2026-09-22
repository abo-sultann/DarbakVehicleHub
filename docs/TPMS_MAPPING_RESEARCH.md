# Mapping boundary — 2026-09-22

The matching prefix alone is insufficient to select a decoder. These primary
reverse-engineering reports were checked against the seven distinct payloads
recovered from this project's four pulse fixtures.

## Similar prefix, different protocol

https://habr.com/ru/articles/516460/ describes a 10-byte 15B9-prefixed family,
but validates CRC-8 poly 0x2F/init 0x43 over the first nine bytes. Its ID occupies
bytes 1–4 (zero-based), temperature byte 7 is signed Celsius, and pressure uses
the high bit of byte 5 and byte 6, with an offset. These are source-specific
findings, not a mapping for this project's sensor.

All seven Darbak payloads pass SUM8 and fail that CRC. Here the observed pressure
candidate changes in bit 0 of byte 5, rather than bit 7. Importing that pressure
formula would therefore discard the observed high bit. Do not publish its ID,
temperature or pressure interpretation as verified for Darbak.

https://github.com/merbanan/rtl_433/issues/2985 also documents a 15B9 family,
with CRC-8 and a different pressure scale/offset. It is further evidence that
the shared prefix is not a unique physical-unit specification.

## What existing recordings can and cannot establish

The new capture's raw byte-pair 5–6 changes 92 -> 339 -> 92 while byte 7 changes
30 -> 39. This locates candidate fields but cannot identify conversion gain,
offset, sign convention or flag masks. Neither plausible room temperature nor
recommended tire pressure is an independent measurement. The off-wheel state
alone cannot establish a scale.

No additional replay or firmware rebuild can create the missing physical-unit
evidence. The remaining boundary is a demonstrably matching protocol, or paired
fresh reference measurements across distinct pressures and temperatures.
Keep normalized values null until that boundary is crossed. Multiple sensors
must be separated before calibration; arrival order is not wheel identity.

The Windows kit now defaults to passive capture after flashing, avoiding an
accidental repeat of the already completed three-stage experiment.
