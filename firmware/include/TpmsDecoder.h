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
  bool adaptiveTiming = false;
  uint16_t shortLowUs = 0, shortHighUs = 0;
};
struct Counters {
  uint32_t valid = 0, timing = 0, length = 0;
  uint32_t manchester = 0, preamble = 0, checksum = 0;
  uint32_t timingRecovered = 0;
};
class Decoder {
 public:
  // level is HELD during durationUs, not the level after the edge.
  bool pulse(uint32_t durationUs, bool level, Frame &out) {
    if (durationUs >= 650) return finishGap(level, out);
    if (bad_) return false;
    // Keep measured durations until the separator. A single fixed threshold
    // confuses short LOW and long HIGH runs when the slicer distorts duty cycle.
    // No short glitch, missing edge or overlong data run is silently repaired.
    if (durationUs < 40 || durationUs > 310 ||
        (haveLevel_ && level == lastLevel_) || pulseCount_ >= 192) {
      ++counters.timing;
      bad_ = true;
      return false;
    }
    if (!haveLevel_) firstLevel_ = level;
    haveLevel_ = true;
    lastLevel_ = level;
    durations_[pulseCount_++] = durationUs;
    return false;
  }
  // No observed gap: cannot supply the last half-bit of a truncated payload.
  bool finish(Frame &out) { return complete(false, false, out); }
  // The gap level was measured, either as a long run or sustained idle.
  // Its first half-bit may belong to the final Manchester data pair.
  bool finishGap(bool gapLevel, Frame &out) { return complete(true, gapLevel, out); }
  void reset() { count_ = pulseCount_ = 0; bad_ = false; haveLevel_ = false; }
  Counters counters;
 private:
  enum Error { TIMING, LENGTH, MANCHESTER, PREAMBLE, CHECKSUM, VALID };
  static uint16_t median10(uint16_t *values) {
    for (unsigned i = 1; i < 10; ++i) {
      const uint16_t value = values[i];
      unsigned j = i;
      while (j && values[j-1] > value) { values[j] = values[j-1]; --j; }
      values[j] = value;
    }
    return (values[4] + values[5] + 1) / 2;
  }
  Error buildChips(bool adaptive, uint16_t (&centers)[2]) {
    count_ = 0;
    unsigned chipUs = 0;
    if (adaptive) {
      if (pulseCount_ < 22) return LENGTH;
      // Runs 2..21 are within the shortest observed zero preamble (11 bits).
      // Estimate both levels BEFORE looking at payload bits or its checksum.
      // The first two runs may include receiver startup, so do not train on them.
      uint16_t values[2][10];
      for (unsigned i = 2; i < 22; ++i)
        values[firstLevel_ ^ (i & 1)][(i-2)/2] = durations_[i];
      centers[0] = median10(values[0]);
      centers[1] = median10(values[1]);
      chipUs = (centers[0] + centers[1] + 1) / 2;
      if (chipUs < 90 || chipUs > 115 || centers[0] < 50 || centers[0] > 165 ||
          centers[1] < 50 || centers[1] > 165) return TIMING;
      for (unsigned i = 2; i < 22; ++i) {
        const int difference = int(durations_[i]) - centers[firstLevel_ ^ (i & 1)];
        if (difference < -35 || difference > 35) return TIMING;
      }
    }
    for (size_t i = 0; i < pulseCount_; ++i) {
      const bool level = firstLevel_ ^ (i & 1);
      const unsigned duration = durations_[i];
      unsigned width;
      if (adaptive) {
        width = duration * 2 < centers[level] * 2 + chipUs ? 1 : 2;
        const int difference = int(duration) - int(centers[level] + (width-1)*chipUs);
        // Disjoint windows: no checksum-guided selection of ambiguous widths.
        if (difference < -40 || difference > 40) return TIMING;
      } else {
        width = duration >= 50 && duration <= 155 ? 1 :
                duration >= 156 && duration <= 270 ? 2 : 0;
        if (!width) return TIMING;
      }
      if (count_ + width > sizeof(chips_)) return LENGTH;
      for (unsigned n = 0; n < width; ++n) chips_[count_++] = level;
    }
    return VALID;
  }
  Error decode(size_t phase, bool tail, bool gapLevel, Frame &out) {
    const size_t count = count_ + (tail ? 1 : 0);
    if (count < phase || (count - phase) % 2) return LENGTH;
    const size_t bits = (count - phase) / 2;
    // Saved 183-chip packets prove 11 complete zero preamble bits after phase
    // alignment; full packets have 16. Never slide across payload, invent a
    // preamble, or fill missing data.
    if (bits < 91 || bits > 96) return LENGTH;
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
    Error reason = TIMING;
    bool found = false, ambiguous = false;
    Frame result;
    if (!bad_) {
      for (unsigned model = 0; model < 2; ++model) {
        uint16_t centers[2] = {};
        const Error timing = buildChips(model != 0, centers);
        if (timing != VALID) {
          if (timing > reason) reason = timing;
          continue;
        }
        for (unsigned tail = 0; tail <= (haveGap ? 1u : 0u); ++tail)
          for (size_t phase = 0; phase < 2; ++phase) {
            Frame candidate;
            const Error error = decode(phase, tail != 0, gapLevel, candidate);
            if (error == VALID) {
              candidate.adaptiveTiming = model != 0;
              candidate.shortLowUs = centers[0];
              candidate.shortHighUs = centers[1];
              if (found && memcmp(result.bytes, candidate.bytes, 10) != 0) ambiguous = true;
              if (!found) result = candidate;
              found = true;
            } else if (error > reason) { reason = error; }
          }
      }
      if (found && !ambiguous) {
        out = result; ++counters.valid;
        if (out.adaptiveTiming) ++counters.timingRecovered;
      }
      else if (pulseCount_) {
        if (ambiguous) reason = CHECKSUM;
        switch (reason) {
          case TIMING: ++counters.timing; break;
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
  uint16_t durations_[192] = {};
  size_t count_ = 0, pulseCount_ = 0;
  bool firstLevel_ = false, lastLevel_ = false, haveLevel_ = false, bad_ = false;
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
