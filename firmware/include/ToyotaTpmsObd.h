#pragma once
#include <stdint.h>
#include <stddef.h>
#include <string.h>

// Toyota-family candidate only: 0x750 -> 0x758, extended address 0x2A.
// Exact Fortuner support must be established by the vehicle's replies.
namespace toyota_obd {
struct Receiver {
  uint8_t bytes[64] = {}, pid = 0, next = 1;
  size_t size = 0, total = 0;
  bool waiting = false, assembling = false;
  void begin(uint8_t p) { pid=p; size=total=0; next=1; waiting=true; assembling=false; }
  void cancel() { waiting=assembling=false; }
  bool matches(const uint8_t *p, size_t n) const {
    return n >= 2 && ((p[0]==0x61 && p[1]==pid) ||
                        (n>=3 && p[0]==0x7f && p[1]==0x21));
  }
  // 0 ignored, 1 send FC, 2 complete, -1 malformed/sequence failure.
  int feed(uint32_t id, bool ext, bool rtr, const uint8_t *d, size_t n) {
    if (!waiting || id!=0x758 || ext || rtr || n<2 || n>8 || d[0]!=0x2a) return 0;
    uint8_t kind=d[1]>>4;
    if (kind==0) {
      size_t count=d[1]&15;
      if (!count || count>6 || n<count+2) { cancel(); return -1; }
      if (!matches(d+2,count)) return 0;
      memcpy(bytes,d+2,count); size=total=count; cancel(); return 2;
    }
    if (kind==1) {
      if (n!=8) { cancel(); return -1; }
      size_t count=((d[1]&15)<<8)|d[2];
      if (!matches(d+3,5)) return 0;
      if (count<=6 || count>sizeof(bytes) || assembling) { cancel(); return -1; }
      total=count; size=5; next=1; memcpy(bytes,d+3,5); assembling=true; return 1;
    }
    if (kind==2 && assembling) {
      size_t count=total-size; if(count>6) count=6;
      if ((d[1]&15)!=next || n<count+2) { cancel(); return -1; }
      memcpy(bytes+size,d+2,count); size+=count; next=(next+1)&15;
      if(size==total) { cancel(); return 2; }
    }
    return 0;
  }
};
}
