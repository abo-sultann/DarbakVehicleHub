#!/usr/bin/env python3
"""Capture Darbak Vehicle Hub TPMS discovery packets from ESP32 serial.

Usage:
  python tpms_capture.py --port COM3 --label front_left
Press Ctrl+C to finish. Output is JSONL suitable for protocol analysis.
"""
import argparse, json, time
from pathlib import Path
import serial

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--port", required=True)
    ap.add_argument("--baud", type=int, default=115200)
    ap.add_argument("--label", default="unknown")
    ap.add_argument("--seconds", type=int, default=180)
    ap.add_argument("--out", default=None)
    a=ap.parse_args()
    stamp=time.strftime("%Y%m%d-%H%M%S")
    out=Path(a.out or f"tpms-{a.label}-{stamp}.jsonl")
    end=time.time()+a.seconds
    count=0
    with serial.Serial(a.port,a.baud,timeout=1) as s, out.open("w",encoding="utf-8") as f:
        print(f"Capturing {a.label} from {a.port} -> {out}")
        while time.time()<end:
            raw=s.readline().decode("utf-8","replace").strip()
            if not raw: continue
            try: obj=json.loads(raw)
            except json.JSONDecodeError: continue
            if obj.get("type")!="tpms_raw": continue
            obj["capture_label"]=a.label
            obj["host_time"]=time.time()
            f.write(json.dumps(obj,separators=(",",":"))+"\n")
            f.flush(); count+=1
            print(f"#{count} RSSI={obj.get('rssi')} len={obj.get('len')} {obj.get('data')}")
    print(f"Done: {count} packets -> {out}")

if __name__=="__main__":
    main()
