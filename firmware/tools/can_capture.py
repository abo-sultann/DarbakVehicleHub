import argparse
import json
import re
import time
from pathlib import Path

import serial

CAN_RE = re.compile(r'\{.*"type":"can_raw".*\}')

def valid_can_line(line: str) -> bool:
    m = CAN_RE.search(line)
    if not m:
        return False
    try:
        obj = json.loads(m.group(0))
        data = obj.get("data", "")
        dlc = int(obj.get("dlc", -1))
        return (
            obj.get("type") == "can_raw"
            and isinstance(obj.get("id"), int)
            and isinstance(data, str)
            and len(data) == dlc * 2
            and all(c in "0123456789abcdefABCDEF" for c in data)
        )
    except (ValueError, TypeError, json.JSONDecodeError):
        return False

def safe_name(name: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_-]+", "_", name.strip())
    return cleaned.strip("_") or "capture"

def main():
    p = argparse.ArgumentParser(description="Darbak Vehicle Hub CAN capture")
    p.add_argument("name", nargs="?", help="test name, e.g. lights_on")
    p.add_argument("--port", default="COM3")
    p.add_argument("--baud", type=int, default=115200)
    p.add_argument("--seconds", type=int, default=8)
    args = p.parse_args()

    name = safe_name(args.name or input("Test name: "))
    out = Path(f"can_{name}.txt")

    good = bad = 0
    print(f"Recording {args.seconds}s -> {out}")
    with serial.Serial(args.port, args.baud, timeout=1) as ser, out.open("w", encoding="utf-8") as f:
        ser.reset_input_buffer()
        end = time.monotonic() + args.seconds
        while time.monotonic() < end:
            raw = ser.readline().decode("utf-8", errors="ignore").strip()
            if not raw:
                continue
            m = CAN_RE.search(raw)
            if m and valid_can_line(raw):
                f.write(m.group(0) + "\n")
                good += 1
            elif "can_raw" in raw:
                bad += 1

    print(f"DONE | valid={good} | dropped_corrupt={bad} | saved={out}")

if __name__ == "__main__":
    main()
