#pragma once
#include <stddef.h>
#include <stdint.h>
#include <string.h>

// Independently derived from this project's captures; see TPMS_DECODER.md.
namespace tpms {
struct Frame {
  uint8_t bytes[10] = {};
  uint16_t chips = 0;
  bool inverted = false;
  uint8_t preambleBits = 0;
  bool gapTail = false;
};
struct Counters {
  uint32_t valid = 0, timing = 0, length = 0;
  uint32_t manchester = 0, preamble = 0, checksum = 0;
};
class Decoder {
 public:
  // level is HELD during durationUs, not the level after the edge.
  bool pulse(uint32_t durationUs, bool level, Frame &out) {
    if (durationUs >= 650) return finishGap(level, out);
    const unsigned width = durationUs >= 50 && durationUs <= 155 ? 1 :
                           durationUs >= 156 && durationUs <= 270 ? 2 : 0;
    if (!width || (haveLevel_ && level == lastLevel_)) {
      ++counters.timing;
      bad_ = true;
      return false;
    }
    haveLevel_ = true;
    lastLevel_ = level;
    if (count_ + width > sizeof(chips_)) { bad_ = true; return false; }
    for (unsigned i = 0; i < width; ++i) chips_[count_++] = level;
    return false;
  }
  // No observed gap: cannot supply the last half-bit of a truncated payload.
  bool finish(Frame &out) { return complete(false, false, out); }
  // The gap level was measured, either as a long run or sustained idle.
  // Its first half-bit may belong to the final Manchester data pair.
  bool finishGap(bool gapLevel, Frame &out) { return complete(true, gapLevel, out); }
  void reset() { count_ = 0; bad_ = false; haveLevel_ = false; }
  Counters counters;
 private:
  enum Error { LENGTH, MANCHESTER, PREAMBLE, CHECKSUM, VALID };
  Error decode(size_t phase, bool tail, bool gapLevel, Frame &out) {
    const size_t count = count_ + (tail ? 1 : 0);
    if (count < phase || (count - phase) % 2) return LENGTH;
    const size_t bits = (count - phase) / 2;
    // The field capture proves 12 and 15 visible zero preamble bits;
    // a complete untruncated preamble has 16. Never slide across payload.
    if (bits < 92 || bits > 96) return LENGTH;
    const size_t prefixBits = bits - 80;
    const bool invert = chips_[phase];
    Frame result;
    result.chips = count_;
    result.inverted = invert;
    result.preambleBits = prefixBits;
    result.gapTail = tail;
    size_t bit = 0;
    for (size_t i = phase; i + 1 < count; i += 2, ++bit) {
      const bool a = chips_[i];
      const bool b = i + 1 == count_ ? gapLevel : chips_[i + 1];
      if (a == b) return MANCHESTER;
      const uint8_t decoded = a ^ invert;
      if (bit < prefixBits) {
        if (decoded) return PREAMBLE;
      } else {
        const size_t p = bit - prefixBits;
        result.bytes[p / 8] |= decoded << (p % 8);
      }
    }
    uint8_t sum = 0;
    for (unsigned i = 0; i < 9; ++i) sum += result.bytes[i];
    if (sum != result.bytes[9]) return CHECKSUM;
    out = result;
    return VALID;
  }
  bool complete(bool haveGap, bool gapLevel, Frame &out) {
    Error reason = LENGTH;
    bool found = false, ambiguous = false;
    Frame result;
    if (!bad_) {
      for (unsigned tail = 0; tail <= (haveGap ? 1u : 0u); ++tail)
        for (size_t phase = 0; phase < 2; ++phase) {
          Frame candidate;
          const Error error = decode(phase, tail != 0, gapLevel, candidate);
          if (error == VALID) {
            if (found && memcmp(result.bytes, candidate.bytes, 10) != 0) ambiguous = true;
            if (!found) result = candidate;
            found = true;
          } else if (error > reason) { reason = error; }
        }
      if (found && !ambiguous) { out = result; ++counters.valid; }
      else if (count_) {
        switch (reason) {
          case LENGTH: ++counters.length; break;
          case MANCHESTER: ++counters.manchester; break;
          case PREAMBLE: ++counters.preamble; break;
          default: ++counters.checksum; break;
        }
      }
    }
    reset();
    return found && !ambiguous;
  }
  uint8_t chips_[192] = {};
  size_t count_ = 0;
  bool lastLevel_ = false, haveLevel_ = false, bad_ = false;
};
// Checksum alone is weak: track independent, identical repeats within a burst.
class Repeats {
 public:
  uint16_t observe(const Frame &frame, uint32_t nowMs) {
    size_t target = 0;
    uint32_t oldestAge = 0;
    bool foundUnused = false;
    for (size_t i = 0; i < 4; ++i) {
      const uint32_t age = nowMs - slots_[i].lastMs;
      if (slots_[i].used && age <= 1000 &&
          memcmp(slots_[i].bytes, frame.bytes, 10) == 0) {
        slots_[i].lastMs = nowMs;
        if (slots_[i].count < 65535) ++slots_[i].count;
        return slots_[i].count;
      }
      if (!slots_[i].used) { target = i; foundUnused = true; }
      else if (!foundUnused && age >= oldestAge) { target = i; oldestAge = age; }
    }
    Slot &slot = slots_[target];
    memcpy(slot.bytes, frame.bytes, 10);
    slot.lastMs = nowMs;
    slot.count = 1;
    slot.used = true;
    return 1;
  }
 private:
  struct Slot {
    uint8_t bytes[10] = {};
    uint32_t lastMs = 0;
    uint16_t count = 0;
    bool used = false;
  } slots_[4];
};
}  // namespace tpms
