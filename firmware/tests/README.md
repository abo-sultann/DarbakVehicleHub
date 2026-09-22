# Decoder replay fixtures

These are the original pulse-list lines from the owner's TPMS88_CAPTURE.txt,
TPMS89_CAPTURE.txt, and the final block of TPMS_RAW_CAPTURE.txt (2026-09-21).
Only unrelated boot/serial garbage and status lines were omitted. Pulse timing,
H/L labels, and truncated packet boundaries are retained exactly.

Legacy H/L denotes the level **after** an edge, so the pulse was held at the
opposite level. Do not treat these labels as the held level. Do not combine
separate raw-capture lines across unrecorded time.

Build and replay from the repository root:

```sh
g++ -std=c++11 -Wall -Wextra -Werror -Ifirmware/include firmware/tests/replay.cpp -o /tmp/tpms-replay
/tmp/tpms-replay firmware/tests/fixtures/*.txt
```

Host replay uses the very same header-only decoder included by ESP32 firmware.
No RF, field mapping, or production measurement claim is implied by a host test.

The 2026-09-22 fixture contains all 14 original packet-scoped pulse lines.
Its final level is observable: the firmware emitted each line at a gap/idle
boundary. Replay may therefore use that measured level to complete the last
Manchester pair. Expected: 12 packets; the 25 us glitch and the malformed
Manchester packet remain rejected. The shorter-preamble fix also recovers
one additional unchanged payload from the old RAW capture (10 old total).
