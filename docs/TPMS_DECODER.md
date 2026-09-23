# Current TPMS decoder evidence

Scope: the existing external 433.92 MHz valve sensor, ESP32 and CC1101 only.
RF reception and repeated digital bursts have already been proved. The known
ASK/OOK, 325 kHz bandwidth and asynchronous GDO0 profile are unchanged. RSSI
is not an acceptance criterion.

## Offline correction — 2026-09-23

The production decoder now replays **36 recorded packets** across all five
pulse fixtures: 10 from the original captures, 13/14 from the morning field
session, and 13/13 from the live session (previously 4/13). The original pulse
fixtures and live frame/reference fixture are unchanged. The morning packet
containing a 25 us glitch remains rejected.

The live recording shows duty-cycle distortion: a nominal 100 us HIGH run
can measure near 53 us while a nominal 100 us LOW run measures near 158 us.
One shared 155 us threshold then misclassifies both levels. The correction
estimates a separate short-run duration for each level from 20 preamble runs,
before reading the payload or checksum. Their average must be 90–115 us.
Double-run centers are one chip period beyond those short-run centers.
Timing windows are disjoint; ambiguous widths are rejected, not selected
using a checksum. The original fixed timing model remains available, and
conflicting valid payloads from the two models are rejected.

Saved 183-chip packets additionally establish 11 complete zero preamble bits
after alignment. The length gate now covers 11–16 complete preamble bits;
all 80 payload bits must still be present. Every Manchester pair, zero
preamble and SUM8 check must pass. A measured gap may supply the final
half-bit only when its observed level completes the pair. `finish()` cannot
invent an unobserved tail. Glitches, missing edges and buffer overflow still
invalidate a packet. No payload bit repair or sensor whitelist is used.

The JSON diagnostics identify `adaptive_timing`, `short_low_us`,
`short_high_us` and cumulative `timing_recovered`. Short centers are zero
when the fixed model supplied the result. The firmware adds 384 bytes for
saved pulse durations and performs classification outside the ISR.

## Recorded protocol and current boundaries

Legacy H/L labels refer to the level **after** an edge, the opposite of the
level held during the preceding duration. After Manchester decoding, bits
within each byte are least significant first. Ten bytes are transmitted;
`sum(bytes[0:9]) & 0xff == bytes[9]`. This is SUM8, not CRC-8.
Two identical valid payloads received within one second set
`repeat_confirmed`; four recent-payload slots keep separate sensors apart.

| Property | Current evidence |
| --- | --- |
| Frame integrity and byte order | Replayed from all five recorded fixtures |
| Live frame records | 32 originally emitted; nine additional raw packets recovered offline |
| Stable prefix | `15B99AA4`, bytes 0–3; candidate only |
| Pressure field candidate | `((b5 & 1) << 8) | b6`; unverified mask and units |
| Temperature field candidate | b7 equals 32 and 36 at the two delayed reference candidates |
| Final ID boundaries | Not established; `sensor_id: null` |
| Physical conversions | Not established; `pressure_psi` and `temperature_c` remain null |
| New firmware on hardware | Compiled/replayed offline; not a claim of a new hardware run |

The owner used an original display in the live session. Five entered
references represent two independent candidate observations; the first
reference predates the earliest recoverable RF by 17.078 seconds. Recovered
copies cannot create another physical measurement or fix that missing link.
See [live evidence](TPMS_LIVE_20260922.md) and
[protocol comparisons](TPMS_MAPPING_RESEARCH.md). The current instruction is
to continue offline without another hardware test.

## Verification

`python3 firmware/tests/run_replay.py` compiles the exact ESP32 decoder
header with host g++, asserts all recorded payloads/counts, checks both
polarities and timing bias, and rejects malformed Manchester, bad preambles,
truncation, glitches and bad checksums. It also checks original timestamp
preservation, replay deduplication, reference association and capture tools.
GitHub Actions runs these checks before building ESP32 firmware.

For a saved ZIP, developers can run:

```sh
python3 firmware/tools/tpms_reprocess.py session.zip --out new-recovery.json
```

This needs Python and g++, opens no serial port, and preserves the source.
The report retains the raw lines, timestamps, payloads and recovery details.
No engineering-unit mapping is automatically enabled. The decoder is derived
independently from these captures; third-party GPL decoder code was not copied.
