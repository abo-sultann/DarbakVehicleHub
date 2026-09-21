#include <Arduino.h>
#include <SPI.h>
#include <ELECHOUSE_CC1101_SRC_DRV.h>
#include "HubConfig.h"

namespace {
constexpr uint32_t STATUS_MS = 10000;
constexpr uint32_t FRAME_GAP_US = 6000;
constexpr size_t MAX_EDGES = 1024;
constexpr size_t MIN_BURST_EDGES = 16;
constexpr int STRONG_RSSI_DBM = -70; // diagnostic only; RSSI is sampled after burst

volatile uint32_t edgeUs[MAX_EDGES];
volatile uint8_t edgeLevel[MAX_EDGES];
volatile size_t edgeCount = 0;
volatile uint32_t lastEdgeUs = 0;
volatile bool overflowed = false;

uint32_t lastStatus = 0, candidateCount = 0, rejectedCount = 0;

void IRAM_ATTR onGdo0Edge() {
  uint32_t now = micros(); size_t i = edgeCount;
  if (i < MAX_EDGES) {
    edgeUs[i] = now; edgeLevel[i] = (uint8_t)digitalRead(PIN_CC1101_GDO0);
    edgeCount = i + 1; lastEdgeUs = now;
  } else overflowed = true;
}

void printStatus() {
  Serial.printf("{\"v\":2,\"type\":\"status\",\"mode\":\"tpms_burst_analyzer\",\"rf_mhz\":%.2f,\"candidates\":%lu,\"rejected\":%lu}\n",
    TPMS_CENTER_MHZ,(unsigned long)candidateCount,(unsigned long)rejectedCount);
}

void analyzeBurst() {
  static uint32_t t[MAX_EDGES]; static uint8_t l[MAX_EDGES];
  noInterrupts(); size_t n=edgeCount; bool ov=overflowed;
  if(n>MAX_EDGES)n=MAX_EDGES;
  for(size_t i=0;i<n;++i){t[i]=edgeUs[i];l[i]=edgeLevel[i];}
  edgeCount=0; overflowed=false; interrupts();
  if(n<8)return;

  int rssi=ELECHOUSE_cc1101.getRssi();
  if(n<MIN_BURST_EDGES){++rejectedCount;return;}

  uint32_t bins[6]={0}; uint32_t minUs=0xFFFFFFFF,maxUs=0,sum=0; size_t usable=0;
  for(size_t i=1;i<n;++i){
    uint32_t d=t[i]-t[i-1]; if(d<20 || d>5000)continue;
    minUs=min(minUs,d); maxUs=max(maxUs,d); sum+=d; ++usable;
    if(d<75)bins[0]++; else if(d<150)bins[1]++; else if(d<250)bins[2]++;
    else if(d<500)bins[3]++; else if(d<1000)bins[4]++; else bins[5]++;
  }
  if(usable<12){++rejectedCount;return;}
  ++candidateCount;
  Serial.printf("TPMS_CANDIDATE seq=%lu n=%u rssi=%d min=%lu max=%lu avg=%lu bins=%lu,%lu,%lu,%lu,%lu,%lu pulses=",
    (unsigned long)candidateCount,(unsigned)n,rssi,(unsigned long)minUs,(unsigned long)maxUs,
    (unsigned long)(sum/usable),(unsigned long)bins[0],(unsigned long)bins[1],(unsigned long)bins[2],
    (unsigned long)bins[3],(unsigned long)bins[4],(unsigned long)bins[5]);
  for(size_t i=1;i<n;++i){
    uint32_t d=t[i]-t[i-1]; if(d<20 || d>5000)continue;
    Serial.print(d); Serial.print(l[i]?'H':'L'); if(i+1<n)Serial.print(',');
  }
  Serial.println();
}

void initRadio(){
  SPI.begin(PIN_CC1101_SCK,PIN_CC1101_MISO,PIN_CC1101_MOSI,PIN_CC1101_CSN);
  ELECHOUSE_cc1101.setSpiPin(PIN_CC1101_SCK,PIN_CC1101_MISO,PIN_CC1101_MOSI,PIN_CC1101_CSN);
  ELECHOUSE_cc1101.Init(); ELECHOUSE_cc1101.setGDO0(PIN_CC1101_GDO0);
  ELECHOUSE_cc1101.setMHZ(TPMS_CENTER_MHZ); ELECHOUSE_cc1101.setModulation(2);
  ELECHOUSE_cc1101.setRxBW(325.0); ELECHOUSE_cc1101.setSyncMode(0); ELECHOUSE_cc1101.setPktFormat(3);
  ELECHOUSE_cc1101.SetRx(); pinMode(PIN_CC1101_GDO0,INPUT);
  attachInterrupt(digitalPinToInterrupt(PIN_CC1101_GDO0),onGdo0Edge,CHANGE);
}
}

void setup(){
  Serial.begin(SERIAL_BAUD); delay(500);
  Serial.println("{\"v\":2,\"type\":\"boot\",\"mode\":\"tpms_burst_analyzer\",\"rf\":\"433.92MHz\",\"filter\":\"n>=16,rssi>=-70\"}");
  initRadio(); printStatus();
}
void loop(){
  uint32_t nowUs=micros(),last; size_t n;
  noInterrupts(); n=edgeCount; last=lastEdgeUs; interrupts();
  if(n>=8 && (uint32_t)(nowUs-last)>FRAME_GAP_US)analyzeBurst();
  uint32_t now=millis(); if(now-lastStatus>=STATUS_MS){lastStatus=now;printStatus();}
}
