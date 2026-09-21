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
