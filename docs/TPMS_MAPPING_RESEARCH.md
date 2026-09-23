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

## Further offline investigation — 2026-09-23

The live session now yields all 13 saved raw packets after fixing timing and
preamble handling. This adds nine repeated payloads, but no missing numeric
reference: the first recoverable packet is still 17.078 seconds after the
35 PSI / 35 C entry. The 32/32 and 25/36 entries still represent two independent
candidate observations. Do not turn duplicate entries into validation points.

Further primary implementation comparisons:

- [SP370 development examples](https://github.com/jerryxiee/TPMS-SP370-SP40-FXTH87-Programer-Development-Kit/blob/master/SP370/SP370%20Code/12.RF_ALL_V2/user/RF.c)
  use `00 00 15` Manchester framing, but the illustrated payload is 14 bytes,
  with 16-bit measurements and CRC-8 0x2F/init 0xAA. Shared framing is not a
  match for this 10-byte SUM8 protocol and cannot establish ID boundaries.
- [rtl_433 issue 3200](https://github.com/merbanan/rtl_433/issues/3200)
  concerns Steelmate's 72/73-bit layout and different measurement fields.
  Its experimentally revised pressure scale cannot be transferred here.
- [rtl_433 issue 1500](https://github.com/merbanan/rtl_433/issues/1500)
  has roughly 52 us OOK Manchester and a leading sum byte, unlike this capture.
- [rtl_433 issue 1820](https://github.com/merbanan/rtl_433/issues/1820)
  describes 50 us iMars/Jansite messages with transformed fields; its proposed
  formulas are not a verified mapping for the Darbak sensor.

No fully matching specification was found in these sources. Direct Celsius
from byte 7 fits the two delayed candidates but is still a hypothesis.
The firmware keeps physical units and final sensor ID null; no arbitrary
pressure line, assumed ambient offset or matching-prefix ID is promoted.

### Product-photo and additional protocol checks

The saved seller screenshots show a generic solar receiver and external valve
caps, without a readable manufacturer/model or sensor-chip marking. Their
advertised accuracy/range is not a protocol specification and does not justify
loosening the reference-fit tolerance. No new hardware session was requested.

- [Totem's published protocol](https://totemtek.com/products/tires-management/tpms/tpms-sensors-for-gps-tracker-tpms-mdvr-and-dashcam/)
  describes a 14-byte receiver interface with a 10-byte inner record. Its
  misleadingly named `crc_checksum` uses XOR, not addition; pressure occupies
  record bytes 4–5 and is shifted right four bits before subtracting 100 kPa.
  This is not a matching RF specification for the Darbak SUM8 frames. Do not
  transfer its conversion or ID layout merely because its inner length matches.
- [Milek7's receiver investigation](https://milek7.pl/tpmsreceiver/)
  covers Opel/Schrader EG53MA4: 125 us symbols, three leading non-ID bytes,
  then four ID bytes and one-byte pressure/temperature. That field order and
  timing differ from the observed Darbak candidates; the article itself leaves
  temperature conversion unresolved. Its pressure suggestion is not evidence
  for this sensor.
- [Comments on the 15B9 investigation](https://habr.com/ru/articles/516460/comments/)
  add an absolute-pressure explanation, but no matching SUM8 variant. An
  absolute-pressure hypothesis alone cannot establish the receiver's offset.

These checks do not resolve physical units or true ID boundaries. The last
firmware change remains the tested timing/preamble recovery; no speculative
conversion has been enabled.
