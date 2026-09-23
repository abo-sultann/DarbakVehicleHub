#include "ToyotaTpmsObd.h"
#include <cassert>
#include <cstdio>
using toyota_obd::Receiver;
int main() {
  Receiver r;
  // Actual OBDb RAV4 2023 multi-frame reply, extended address included.
  const uint8_t first[]={0x2a,0x10,7,0x61,0x16,0x54,0x55,0x53};
  const uint8_t last[]={0x2a,0x21,0x53,0,0,0,0,0};
  r.begin(0x16);
  assert(r.feed(0x758,false,false,first,8)==1);
  assert(r.feed(0x758,false,false,last,8)==2);
  assert(r.size==7 && r.bytes[2]==84 && r.bytes[5]==83 && r.bytes[6]==0);
  // Different request echo, address and RTR/extended frames cannot enter a reply.
  r.begin(0x30); assert(r.feed(0x758,false,false,first,8)==0);
  r.begin(0x16); assert(r.feed(0x759,false,false,first,8)==0);
  assert(r.feed(0x758,true,false,first,8)==0);
  assert(r.feed(0x758,false,true,first,8)==0);
  uint8_t bad[8]; memcpy(bad,first,8); bad[0]=0x2b;
  assert(r.feed(0x758,false,false,bad,8)==0);
  // Wrong sequence, short frames, oversized length and unsolicited CF rejected.
  assert(r.feed(0x758,false,false,last,8)==0);
  assert(r.feed(0x758,false,false,first,8)==1);
  memcpy(bad,last,8); bad[1]=0x22;
  assert(r.feed(0x758,false,false,bad,8)==-1);
  assert(r.feed(0x758,false,false,last,8)==0);
  r.begin(0x16); assert(r.feed(0x758,false,false,first,6)==-1);
  r.begin(0x16); memcpy(bad,first,8); bad[2]=65;
  assert(r.feed(0x758,false,false,bad,8)==-1);
  r.begin(0x16); assert(r.feed(0x758,false,false,first,8)==1);
  assert(r.feed(0x758,false,false,last,3)==-1);
  const uint8_t nrc[]={0x2a,3,0x7f,0x21,0x12,0,0,0};
  r.begin(0x30); assert(r.feed(0x758,false,false,nrc,8)==2);
  assert(r.size==3 && r.bytes[2]==0x12);
  // Cancel/timeout does not permit late CF to become another request's data.
  r.begin(0x16); assert(r.feed(0x758,false,false,first,8)==1); r.cancel();
  assert(r.feed(0x758,false,false,last,8)==0);
  r.begin(0x30); assert(r.feed(0x758,false,false,last,8)==0);
  puts("OBD transport: recorded Toyota reply + malformed/foreign/late frames PASS");
}
