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
};
struct Counters {
  uint32_t valid = 0, timing = 0, length = 0;
  uint32_t manchester = 0, preamble = 0, checksum = 0;
};
class Decoder {
 public:
  // level is HELD during durationUs, not the new level after the edge.
  bool pulse(uint32_t durationUs, bool level, Frame &out) {
    if (durationUs >= 650) return finish(out);
    const unsigned width = durationUs >= 60 && durationUs <= 155 ? 1 :
                           durationUs >= 156 && durationUs <= 270 ? 2 : 0;
    if (!width || (haveLevel_ && level == lastLevel_)) {
      ++counters.timing;
      bad_ = true;
      return false;
    }
    haveLevel_ = true;
    lastLevel_ = level;
    if (count_ + width > sizeof(chips_)) {
      bad_ = true;
      return false;
    }
    for (unsigned i = 0; i < width; ++i) chips_[count_++] = level;
    return false;
  }
  bool finish(Frame &out) {
    const bool valid = !bad_ && decode(out);
    reset();
    return valid;
  }
  void reset() { count_ = 0; bad_ = false; haveLevel_ = false; }
  Counters counters;
 private:
  bool decode(Frame &out) {
    // A gap absorbs the first preamble half-bit, giving 191 rather than 192
    // chips. Skip only that incomplete PREAMBLE bit; never infer payload bits.
    if (count_ != 191 && count_ != 192) {
      if (count_) ++counters.length;
      return false;
    }
    const size_t phase = count_ == 191 ? 1 : 0;
    const size_t prefixBits = count_ == 191 ? 15 : 16;
    const bool invert = chips_[phase];
    Frame result;
    result.chips = count_;
    result.inverted = invert;
    size_t bit = 0;
    for (size_t i = phase; i + 1 < count_; i += 2, ++bit) {
      if (chips_[i] == chips_[i + 1]) {
        ++counters.manchester;
        return false;
      }
      const uint8_t decoded = chips_[i] ^ invert;
      if (bit < prefixBits) {
        if (decoded) { ++counters.preamble; return false; }
      } else {
        const size_t payloadBit = bit - prefixBits;
        result.bytes[payloadBit / 8] |= decoded << (payloadBit % 8);
      }
    }
    uint8_t sum = 0;
    for (unsigned i = 0; i < 9; ++i) sum += result.bytes[i];
    if (sum != result.bytes[9]) { ++counters.checksum; return false; }
    out = result;
    ++counters.valid;
    return true;
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
