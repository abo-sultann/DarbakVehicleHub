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
Manchester pair. Expected after the offline timing correction: 13 packets;
the packet containing a 25 us glitch remains rejected. Duty-cycle compensation
recovers the previously misclassified packet without changing any pulse or
payload bit. The three original fixtures still produce 10 packets.

The live fixture preserves 13 pulse dumps. All 13 now replay, versus 4 before
the correction. Seven recovered packets need separate HIGH/LOW timing centers;
two need the recorded 11-bit preamble. Every Manchester pair, the entire
preamble and SUM8 must still pass. The `.raw.jsonl` companion preserves the
original host timestamps and raw serial lines for those 13 packets. The
existing `.jsonl` frame/reference fixture remains unchanged.

`python3 firmware/tests/run_replay.py` checks all 36 recorded packets, negative
and biased-timing synthetic cases, and offline timestamp recovery. Replaying
an already emitted raw dump cannot create another calibration observation;
the recovery report must retain null units and the two-point evidence limit.
