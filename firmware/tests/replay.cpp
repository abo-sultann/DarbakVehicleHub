#include "TpmsDecoder.h"
#include <algorithm>
#include <array>
#include <cstdlib>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <regex>
#include <sstream>
#include <string>
#include <vector>

using Bytes = std::array<uint8_t, 10>;
void require(bool condition, const char *message) {
  if (!condition) { std::cerr << "FAIL: " << message << '\n'; std::exit(1); }
}
std::string hex(const tpms::Frame &f) {
  std::ostringstream s;
  for (auto b : f.bytes) s << std::uppercase << std::hex << std::setw(2)
                         << std::setfill('0') << unsigned(b);
  return s.str();
}
std::vector<bool> encode(const Bytes &bytes, bool invert = false, bool partial = true,
                         size_t prefixBits = 16) {
  std::vector<bool> chips;
  for (size_t i = 0; i < prefixBits + 80; ++i) {
    bool bit = i < prefixBits ? false : (bytes[(i-prefixBits)/8] >> ((i-prefixBits)%8)) & 1;
    chips.push_back(bit ^ invert);
    chips.push_back(!bit ^ invert);
  }
  if (partial) chips.erase(chips.begin());
  return chips;
}
bool receive(tpms::Decoder &decoder, const std::vector<bool> &chips, tpms::Frame &out,
             bool gapLevel = false, bool observedGap = true) {
  for (size_t i = 0; i < chips.size();) {
    size_t end = i + 1;
    while (end < chips.size() && chips[end] == chips[i]) ++end;
    // Uneven measured timing, including the 100/200 us classification tails.
    uint32_t duration = (end-i)*103 + (i%3 == 0 ? 18 : 0);
    decoder.pulse(duration, chips[i], out);
    i = end;
  }
  return observedGap ? decoder.pulse(925, gapLevel, out) : decoder.finish(out);
}
void selfTest() {
  const Bytes known = {0x15,0xB9,0x9A,0xA4,0x01,0xC0,0x5C,0x21,0x1C,0x66};
  tpms::Frame out;
  // Real field payload ends in checksum MSB=1: the last low half-bit merges
  // into the interpacket gap. The old 191/192-chip gate rejected every copy.
  const Bytes field = {0x15,0xB9,0xC5,0x82,0x01,0x01,0x53,0x22,0x1B,0xA7};
  for (bool invert : {false, true}) for (size_t prefix : {13u, 16u}) {
    auto chips = encode(field, invert, true, prefix);
    chips.pop_back();
    tpms::Decoder good, wrongGap, missingGap;
    require(receive(good, chips, out, invert), "measured gap supplies final half-bit");
    require(hex(out) == "15B9C582010153221BA7", "field payload exact");
    require(out.gapTail && out.preambleBits == prefix-1, "framing diagnostics");
    require(!receive(wrongGap, chips, out, !invert), "wrong gap level rejected");
    require(!receive(missingGap, chips, out, invert, false), "no invented tail without gap");
  }
  for (bool invert : {false, true}) for (bool partial : {false, true}) {
    tpms::Decoder d;
    require(receive(d, encode(known, invert, partial), out), "polarity/preamble/jitter");
    require(hex(out) == "15B99AA401C05C211C66", "LSB-first payload");
    require(out.inverted == invert, "polarity marker");
  }
  {
    tpms::Decoder d;
    auto wrong = known; wrong[6] ^= 1;
    require(!receive(d, encode(wrong), out), "checksum corruption rejected");
    require(d.counters.checksum == 1, "checksum rejection reason");
  }
  {
    tpms::Decoder d; auto chips = encode(known);
    chips[101] = chips[102];
    require(!receive(d, chips, out), "invalid Manchester rejected");
  }
  {
    tpms::Decoder d; auto chips = encode(known, false, false);
    chips[8] = true; chips[9] = false;
    require(!receive(d, chips, out), "broken preamble rejected");
  }
  {
    tpms::Decoder d; auto chips = encode(known);
    chips.erase(chips.begin()+60, chips.begin()+62);
    require(!receive(d, chips, out), "truncated payload rejected");
    require(receive(d, encode(known), out), "resync after rejected packet");
  }
  {
    tpms::Decoder d;
    d.pulse(27, false, out);
    require(!receive(d, encode(known), out), "short glitch never silently repaired");
    require(receive(d, encode(known), out), "gap clears glitch");
    d.pulse(103, false, out);
    d.reset(); // The ISR overflow path must discard the partial packet.
    require(!d.finish(out), "overflow cannot emit stale packet");
  }
  {
    tpms::Repeats r;
    tpms::Frame a, b;
    std::copy(known.begin(), known.end(), a.bytes);
    b = a; b.bytes[0] ^= 1;
    require(r.observe(a, 0xFFFFFFF0u) == 1, "first frame unconfirmed");
    require(r.observe(b, 0xFFFFFFF1u) == 1, "different sensor unconfirmed");
    require(r.observe(a, 20) == 2, "repeat across clock wrap");
    require(r.observe(a, 2021) == 1, "old data cannot confirm new burst");
  }
  {
    tpms::Repeats r;
    tpms::Frame sensors[4];
    for (unsigned i = 0; i < 4; ++i) {
      std::copy(field.begin(), field.end(), sensors[i].bytes);
      sensors[i].bytes[3] += i;
      require(r.observe(sensors[i], i*20) == 1, "four sensors separately unconfirmed");
    }
    for (unsigned i = 0; i < 4; ++i)
      require(r.observe(sensors[i], 100+i*20) == 2, "interleaved sensors separately confirmed");
  }
  std::cerr << "Decoder self-tests passed\n";
}
int main(int argc, char **argv) {
  selfTest();
  const std::regex token(R"((\d+)([HL]))");
  for (int arg = 1; arg < argc; ++arg) {
    std::ifstream input(argv[arg]);
    require(bool(input), "fixture open");
    std::string line;
    size_t lineNumber = 0;
    while (std::getline(input, line)) {
      ++lineNumber;
      auto start = line.find("pulses=");
      size_t skip = 7;
      if (start == std::string::npos) { start = line.find("us="); skip = 3; }
      if (start == std::string::npos) continue;
      const auto pulses = line.substr(start + skip);
      tpms::Decoder decoder; tpms::Frame frame;
      bool lastAfter = false;
      for (std::sregex_iterator i(pulses.begin(), pulses.end(), token), end; i != end; ++i) {
        lastAfter = (*i)[2] == "H";
        // Legacy labels describe the NEW level, opposite of the held level.
        if (decoder.pulse(std::stoul((*i)[1]), (*i)[2] == "L", frame))
          std::cout << argv[arg] << ':' << lineNumber << ' ' << hex(frame) << '\n';
      }
      // scope=packet is only emitted after a measured gap or sustained idle.
      const bool valid = line.find("scope=packet") != std::string::npos
          ? decoder.finishGap(lastAfter, frame) : decoder.finish(frame);
      if (valid)
        std::cout << argv[arg] << ':' << lineNumber << ' ' << hex(frame) << '\n';
    }
  }
}
