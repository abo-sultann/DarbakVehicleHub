# Current TPMS decoder evidence

Scope: the existing external 433.92 MHz valve sensor, ESP32 and CC1101 only.
Receive proof is complete. The original ASK/OOK, 325 kHz RX bandwidth,
asynchronous GDO0 profile and wiring are retained. RSSI is not an acceptance
criterion, and is not sampled to reject a completed burst.

## Reproduced result

The production C++ decoder replays **nine complete, integrity-valid packets**
from three existing recordings. Fixtures preserve the original pulse lists.
Incomplete, glitched, and malformed packets are rejected.

| Recording | Complete accepted copies | Decoded bytes, in transmitted byte order |
|---|---:|---|
| TPMS88_CAPTURE | 3 | 15 B9 9A A4 01 C0 5C 20 1C 65 |
| TPMS89_CAPTURE | 4 | 15 B9 9A A4 01 C0 5C 21 1C 66 |
| TPMS_RAW_CAPTURE, final recorded block | 2 | 15 B9 9A A4 01 C0 5C 20 1C 65 |

These are two distinct payload values, not nine independent field-calibration
points. Repeated captures alone cannot establish pressure or temperature units.

## Derivation

1. The old ISR logs each edge timestamp and the **new** GDO0 level. In
   `103L`, the preceding 103 microseconds were HIGH. Using L as the held
   level would invert the waveform.
2. A short run is roughly 100 microseconds; a long run is roughly 200.
   The observed roughly 900-microsecond separators split repeated packets.
   Current guarded windows: 60–155 us, 156–270 us, and a separator >=650 us.
   The unobserved 271–649 us range, short glitches, repeated edge levels,
   and buffer overflow invalidate the partial packet.
3. Each clean segment contains 191 half-bit chips. The first LOW preamble
   half-bit is absorbed by the LOW separator. Skipping the remaining
   incomplete preamble half-bit leaves 15 complete preamble bits and 80
   data bits. A full 192-chip packet is also supported with all 16 preamble
   bits. No missing payload bit is supplied.
4. Every complete Manchester pair must contain opposite levels. The
   preamble establishes polarity. Normalized 01 is zero, 10 is one.
   The 80 data bits are grouped **least significant bit first** into ten
   bytes. No XOR whitening or pressure-dependent bit repair is used.
5. `sum(bytes[0:9]) & 0xff == bytes[9]` holds: 0x65 and 0x66 respectively.
   This is an additive SUM8 check, **not CRC**. The same checksum change
   tracks the single observed change in byte 7.
6. Two byte-identical valid frames within 1000 ms set `repeat_confirmed`.
   Four independent recent-payload slots avoid cross-confirming different
   payloads. This adds repeat evidence to the relatively weak SUM8 check.

The decoder is an independent implementation from project captures, not
copied third-party GPL decoder code.

## What is and is not established

| Property | Evidence/status |
|---|---|
| Manchester, packet length, byte order | Replayed from the saved waveforms |
| SUM8 integrity rule | Matches both distinct payloads and all nine accepted copies |
| `15B99AA4` | Stable bytes 0–3; **ID candidate only**, width/order not proven |
| Bytes 4–6 and 8 | Constant in these recordings; purpose unknown |
| Byte 7 | 0x20 -> 0x21; may be a measurement, status or counter |
| Pressure conversion | Not established; `pressure_psi: null` |
| Temperature conversion | Not established; `temperature_c: null` |
| Final sensor ID mapping | Not established; `sensor_id: null` |
| On-device reception of this new build | Requires the single field session |

The code never treats 0x20/0x21 as Celsius just because the numbers look
plausible, or borrows a pressure scale from a superficially similar sensor.
No normalized `type:tpms` measurement is emitted yet.

## Open-source protocol comparison

Inspected rtl_433 revision
[`bd9073191aff109d7ea013bdcb921992b4f5a11f`](https://github.com/merbanan/rtl_433/tree/bd9073191aff109d7ea013bdcb921992b4f5a11f/src/devices).
Relevant primary sources:

- [Tyreguard 400](https://github.com/merbanan/rtl_433/blob/bd9073191aff109d7ea013bdcb921992b4f5a11f/src/devices/tpms_tyreguard400.c):
  OOK, similar 100 us timing, but different preamble, 88-bit payload and CRC.
- [Schrader](https://github.com/merbanan/rtl_433/blob/bd9073191aff109d7ea013bdcb921992b4f5a11f/src/devices/schraeder.c):
  the EG53MA4 subtype has additive integrity, but a different preamble,
  framing and documented field layout.
- [EEZ RV](https://github.com/merbanan/rtl_433/blob/bd9073191aff109d7ea013bdcb921992b4f5a11f/src/devices/tpms_eezrv.c):
  different 50 us timing and eight-byte payload.
- [Steelmate](https://github.com/merbanan/rtl_433/blob/bd9073191aff109d7ea013bdcb921992b4f5a11f/src/devices/steelmate.c):
  different modulation/timing, nine-byte layout and integrity coverage.
- [External TPMS examples](https://github.com/andi38/TPMS):
  the CC1101 example uses FSK at 19200 baud and a different synchronization word.

None is a demonstrated full match for these captures. Their engineering units
are therefore not adopted. This documents bounded source comparison, not a
claim that no matching implementation exists anywhere.

## Single remaining experiment

One uninterrupted serial session records the same sensor off-valve at ambient
temperature, fitted normally, then off-valve warmed in a hand. Fresh pressure
and temperature from the existing receiver are recorded with host timestamps.
The script keeps raw bytes, text pulse dumps, every decoded packet, checksum
and repeat status, reference readings, and build identity in one ZIP.

Those measurements are needed to locate/validate the fields and conversion.
A short session cannot guarantee the sensor transmits a new temperature;
missing references remain explicitly unavailable. ID width/order may remain
unresolved even if a stable per-sensor candidate is corroborated.

## Verification

`python3 firmware/tests/run_replay.py` builds the exact ESP32 decoder header
with host g++ and asserts the exact packet counts and payloads above. Tests
also cover both polarities, full/partial preamble, timing jitter, checksum
corruption, malformed Manchester, bad preamble, truncated payload, glitch
rejection, resynchronization, stale-repeat expiry and clock wrap.

The serial test verifies that both legacy non-JSON pulse output and new JSON
are preserved; the previous capture tool silently discarded both.
GitHub Actions runs these checks before compiling the ESP32 firmware.
