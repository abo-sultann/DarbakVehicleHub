#include <Arduino.h>
#include <driver/twai.h>
#include "HubConfig.h"
#include "ToyotaTpmsObd.h"
#ifndef TPMS_BUILD_SHA
#define TPMS_BUILD_SHA "local"
#endif
namespace {
toyota_obd::Receiver rx;
bool installed=false, active=false, stopped=false;
uint32_t frames=0, lastStatus=0, heartbeat=0, started=0, sent=0, deadline=0, requests=0;
uint8_t which=0;
String command;
void event(const char* name) {
  Serial.printf("{\"type\":\"obd_event\",\"ms\":%lu,\"event\":\"%s\"}\n",(unsigned long)millis(),name);
}
void stop(const char* why) {
  active=false; stopped=true; rx.cancel();
  if(installed) { twai_stop(); twai_driver_uninstall(); installed=false; }
  event(why);
}
bool init(twai_mode_t mode) {
  twai_general_config_t g=TWAI_GENERAL_CONFIG_DEFAULT((gpio_num_t)PIN_CAN_TX,(gpio_num_t)PIN_CAN_RX,mode);
  g.rx_queue_len=128; g.tx_queue_len=0;
  g.alerts_enabled=TWAI_ALERT_TX_FAILED|TWAI_ALERT_BUS_OFF|TWAI_ALERT_ERR_PASS|TWAI_ALERT_RX_QUEUE_FULL;
  twai_timing_config_t t=TWAI_TIMING_CONFIG_500KBITS();
  twai_filter_config_t f=TWAI_FILTER_CONFIG_ACCEPT_ALL();
  if(twai_driver_install(&g,&t,&f)!=ESP_OK) return false;
  installed=true;
  if(twai_start()!=ESP_OK) { twai_driver_uninstall(); installed=false; return false; }
  return true;
}
void logFrame(const char* dir,const twai_message_t& m) {
  Serial.printf("{\"type\":\"obd_can\",\"ms\":%lu,\"direction\":\"%s\",\"id\":%lu,\"data\":\"",(unsigned long)millis(),dir,(unsigned long)m.identifier);
  for(uint8_t i=0;i<m.data_length_code;i++) Serial.printf("%02X",m.data[i]);
  Serial.println("\"}");
}
bool send(bool flow, uint8_t pid=0) {
  if(!active) return false;
  twai_message_t m={}; m.identifier=0x750; m.data_length_code=8; m.ss=1;
  m.data[0]=0x2a; m.data[1]=flow?0x30:0x02;
  m.data[2]=flow?0x00:0x21; m.data[3]=flow?0x0a:pid;
  if(twai_transmit(&m,pdMS_TO_TICKS(20))!=ESP_OK) { stop("tx_failed"); return false; }
  logFrame("tx",m); return true;
}
void line(const String& s) {
  if(s=="STOP") { stop("host_stop"); return; }
  if(s=="PING") { heartbeat=millis(); return; }
  if(s!="START" || active || stopped) return;
  twai_status_info_t info={};
  if(!installed || twai_get_status_info(&info)!=ESP_OK || frames<20 ||
     info.bus_error_count || info.rx_missed_count || info.rx_overrun_count || info.rx_error_counter) {
    stop("preflight_failed_no_clean_can"); return;
  }
  twai_stop(); twai_driver_uninstall(); installed=false;
  if(!init(TWAI_MODE_NORMAL)) { stop("can_init_failed"); return; }
  active=true; heartbeat=started=millis(); sent=started-3000;
  event("started_read_only_tpms_candidate");
}
}
void setup() {
  Serial.begin(SERIAL_BAUD); command.reserve(32);
  if(!init(TWAI_MODE_LISTEN_ONLY)) stop("can_init_failed");
  event("ready_listen_only");
}
void loop() {
  uint32_t now=millis();
  while(Serial.available()) {
    char c=Serial.read();
    if(c=='\n') { line(command); command=""; }
    else if(c!='\r') { if(command.length()<31) command+=c; else command="INVALID"; }
  }
  now=millis();
  if(active && (now-heartbeat>4000 || now-started>180000)) stop("lease_expired");
  if(installed) {
    uint32_t alerts=0; twai_read_alerts(&alerts,0);
    if(active && alerts) stop("can_error_stop");
  }
  if(installed) {
    twai_message_t m;
    // Bound processing so heartbeat and stop are never starved by bus traffic.
    for(int i=0;i<128 && twai_receive(&m,0)==ESP_OK;i++) {
      frames++;
      if(m.extd || m.rtr || m.data_length_code>8) continue;
      if(m.identifier==0x750 && active) { logFrame("rx",m); stop("other_diagnostic_tester"); break; }
      if(m.identifier!=0x758) continue;
      logFrame("rx",m);
      int result=rx.feed(m.identifier,m.extd,m.rtr,m.data,m.data_length_code);
      if(result==1) { if(!send(true)) break; }
      if(result<0) event("invalid_isotp");
      if(result==2) {
        Serial.printf("{\"type\":\"obd_payload\",\"ms\":%lu,\"request_pid\":%u,\"payload_hex\":\"",(unsigned long)now,rx.pid);
        for(size_t j=0;j<rx.size;j++) Serial.printf("%02X",rx.bytes[j]);
        Serial.println("\",\"mapping_verified\":false,\"pressure_psi\":null,\"temperature_c\":null,\"sensor_id\":null}");
        if(rx.size>=3 && rx.bytes[0]==0x7f && rx.bytes[2]==0x78) {
          // Keep the original bounded deadline; no unbounded response-pending loop.
          uint8_t p=rx.pid; rx.begin(p);
        }
      }
    }
  }
  if(active && rx.waiting && (int32_t)(now-deadline)>=0) { rx.cancel(); event("response_timeout"); }
  if(active && !rx.waiting && now-sent>=3000) {
    static const uint8_t pids[]={0x30,0x16};
    uint8_t p=pids[which++%2]; rx.begin(p); sent=now; deadline=now+2000;
    if(send(false,p)) requests++;
  }
  if(now-lastStatus>=1000) {
    lastStatus=now;
    twai_status_info_t st={}; if(installed) twai_get_status_info(&st);
    Serial.printf("{\"type\":\"status\",\"mode\":\"obd_tpms\",\"build\":\"%s\",\"active\":%s,\"stopped\":%s,\"frames\":%lu,\"requests\":%lu,\"bus_errors\":%lu,\"rx_missed\":%lu,\"tx_pin\":%d,\"rx_pin\":%d,\"bitrate\":500000}\n",TPMS_BUILD_SHA,active?"true":"false",stopped?"true":"false",(unsigned long)frames,(unsigned long)requests,(unsigned long)st.bus_error_count,(unsigned long)st.rx_missed_count,PIN_CAN_TX,PIN_CAN_RX);
  }
  delay(1);
}
