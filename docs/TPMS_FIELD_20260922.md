# Field session 2026-09-22: decoder correction

Source: TPMS_ONE_TEST_20260922_103605.zip, captured with build e068dc169d22.
The owner confirmed there is **no reference receiver/display**, and three
other sensors were already fitted on the vehicle. No wheel identity is assigned
from packet arrival order or stage labels.

## Actual contents

- 57 parsed status records, 14 packet-scoped raw pulse dumps, zero on-device
  decoded frame records.
- No host serial error and zero reported ISR dropped edges.
- All reference pressure/temperature entries are null.
- Final rejection counters: timing 15665, length 2298, Manchester 0,
  preamble 0, checksum 0. Most frames never reached payload validation.

This is a framing rejection in the previous decoder, not new evidence that
RF reception is absent. The saved raw pulse dumps allow an offline correction
without asking the owner to repeat the three physical stages.

## Reproduced cause and correction

The clean field segments contain 184 or 190 chips before a LOW separator.
Manchester decoding at phase 1 gives 12 or 15 complete zero preamble bits,
then 79 complete data bits and the first half of the final data bit. That
bit is 1, so its LOW second half continues directly into the LOW gap.

The former gate required exactly 191/192 chips and discarded the entire gap.
It could decode the old payloads whose last checksum bit was zero, but rejected
these payloads whose final checksum bit is one.

The corrected decoder uses **one half-bit from the observed gap level** and
checks the resulting entire Manchester payload and SUM8. It never tries both
invented tail values to make a checksum pass. Without observed gap information,
a missing final half-bit is rejected. Short-run acceptance is now 50–155 us,
supported by measured 50, 51 and 54 us runs; the 25 us glitch remains invalid.

## Exact recovered payloads

| Packet lines | Copies | Payload | Raw bytes 5–6 as BE integer | Raw byte 7 |
|---|---:|---|---:|---:|
| 1 | 1 | 15B9C58201005C1E1BAB | 92 | 30 |
| 3, 4 | 2 | 15B9C582010153221BA7 | 339 | 34 |
| 5, 6 | 2 | 15B9C582010153241BA9 | 339 | 36 |
| 7, 8 | 2 | 15B9C582010153261BAB | 339 | 38 |
| 9, 10, 12, 13, 14 | 5 | 15B9C58201005C271BB4 | 92 | 39 |

**12 of 14 preserved field packet dumps pass**. Packet 2 contains a 25 us
glitch; packet 11 has invalid Manchester pairs. Both are retained and rejected,
not silently repaired. The original old fixtures still decode, with one extra
shorter-preamble packet recovered: 10 old + 12 new = 22 total.

All 12 accepted new packets share candidate prefix **15B9C582**. The old
recordings contain **15B99AA4**. This does not establish four decoded sensors,
the exact final ID width, or a mapping to a particular wheel.

The 92 -> 339 -> 92 raw change supports locating a pressure-related field.
It does **not** establish its units, gain, zero offset, or flag-bit mask.
The byte-7 change 30 -> 39 could be temperature-related, but its numeric
plausibility is not calibration and a counter/status interpretation is not
ruled out by these data alone. No PSI or Celsius values are published.

Stage names mark a prompt/action window, not the precise instant the valve was
connected. In particular, packet 1 is logged under the mounted prompt while its
raw value remains 92. Do not assign every packet in that window to mounted
pressure, and do not combine fields from other sensor prefixes.

## Verification and next boundary

Host tests compile the exact ESP32 decoder and replay all four fixture files.
Additional tests cover both gap polarities, both observed preamble lengths,
incorrect/unobserved tail levels, unchanged old framing, invalid checksum and
Manchester, and interleaved repeat tracking for four sensors.
Capture summaries group candidate prefixes separately and keep wheel identity
and physical-unit mapping explicitly unknown.

The fixed firmware must still be confirmed on hardware; host replay is not
an on-device success claim. The existing field session is sufficient to test
this code correction offline. Do not request the same three-stage experiment
again merely to prove that correction. Physical units require an independently
supported protocol definition or real reference measurements.
