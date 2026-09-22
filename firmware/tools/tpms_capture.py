#!/usr/bin/env python3
"""Flash the existing ESP32 app partition and collect one complete TPMS session."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import subprocess
import sys
import threading
import time
import zipfile

import serial
from tpms_calibration import analyze, feedback, read_records, split_records
from serial.tools import list_ports

USB_UART_VIDS = {0x10C4, 0x1A86, 0x0403, 0x303A}
STAGES = [
    ("ambient_off_valve",
     "Remove this sensor from the valve (if fitted), and leave it near the CC1101. "
     "Its battery must be installed now. Keep the same sensor throughout."),
    ("mounted",
     "Fit the same sensor normally to its tire valve. Keep the ESP32 nearby. "
     "The other three sensors may remain fitted; they are recorded separately by candidate ID."),
    ("warm_off_valve",
     "Remove the same sensor and hold its body in your closed hand for about 60 seconds. "
     "No display or reference reading is required. Do not guess measurements."),
]


def choose_port(requested):
    if requested:
        return requested
    ports = list(list_ports.comports())
    candidates = [p for p in ports if p.vid in USB_UART_VIDS]
    if len(candidates) == 1:
        return candidates[0].device
    if len(ports) == 1:
        return ports[0].device
    if not ports:
        raise RuntimeError("No serial port found. Connect the existing ESP32 by USB.")
    for p in ports:
        print(f"  {p.device}: {p.description}")
    chosen = input("ESP32 COM port: ").strip()
    if chosen not in {p.device for p in ports}:
        raise RuntimeError("That port is not in the detected list.")
    return chosen


def read_reference(text):
    text = text.strip()
    if text in {"", "-"}:
        return {"pressure_psi": None, "temperature_c": None, "fresh": False}
    parts = text.replace(",", " ").split()
    if len(parts) != 2:
        raise ValueError("Enter two numbers: PSI Celsius, or - for unavailable.")
    p, t = map(float, parts)
    if not all(map(math.isfinite, (p, t))) or not 0 <= p <= 100 or not -40 <= t <= 125:
        raise ValueError("Check units: pressure in PSI, temperature in Celsius.")
    return {"pressure_psi": p, "temperature_c": t, "fresh": True}


def verify_package(root):
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    for filename, expected in manifest["sha256"].items():
        path = root / filename
        if path.parent.resolve() != root.resolve():
            raise RuntimeError("Invalid package path.")
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        if actual != expected:
            raise RuntimeError(f"Package hash mismatch: {filename}")
    return manifest


def flash(port, root):
    manifest = verify_package(root)
    firmware = root / "DarbakVehicleHub-ESP32-TPMS.bin"
    if manifest.get("flash_offset") != "0x10000":
        raise RuntimeError("Unexpected app flash offset.")
    print(f"Flashing build {manifest['commit'][:12]} on {port}...")
    subprocess.run([
        sys.executable, "-m", "esptool", "--chip", "esp32", "--port", port,
        "--baud", "460800", "--before", "default_reset", "--after", "hard_reset",
        "write_flash", "--flash_size", "keep", "0x10000", str(firmware)
    ], check=True)
    return manifest


def ensure_firmware(port, baud, root):
    manifest = verify_package(root)
    # Status identifies the actual running image, not a remembered host file.
    probe = serial.Serial()
    probe.port, probe.baudrate, probe.timeout = port, baud, 0.2
    probe.dtr, probe.rts = False, False
    try:
        probe.open()
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            try:
                status = json.loads(probe.readline())
            except (ValueError, UnicodeError):
                continue
            if isinstance(status, dict) and status.get("type") == "status" and status.get("build") == manifest["commit"][:12]:
                print("Current packaged firmware is already installed; skipping flash.")
                return {**manifest, "flash_skipped": True}
    finally:
        probe.close()
    return flash(port, root)


class Capture:
    def __init__(self, port, baud, folder):
        self.folder = folder
        self.lock = threading.Lock()
        self.stop = threading.Event()
        self.stage = "startup"
        self.records = []
        self.frames = []
        self.error = None
        self.stream = (folder / "serial.jsonl").open("w", encoding="utf-8")
        self.binary = (folder / "serial.bin").open("wb")
        self.serial = serial.Serial()
        self.serial.port, self.serial.baudrate, self.serial.timeout = port, baud, 0.2
        self.serial.dtr, self.serial.rts = False, False
        try:
            self.serial.open()
        except Exception:
            self.stream.close()
            self.binary.close()
            raise
        self.thread = threading.Thread(target=self._read, daemon=True)
        self.thread.start()

    def event(self, kind, **fields):
        with self.lock:
            obj = {"host_unix_s": time.time(), "host_monotonic_s": time.monotonic(), "stage": self.stage, "event": kind, **fields}
            self.stream.write(json.dumps(obj, ensure_ascii=False) + "\n")
            self.stream.flush()
            self.records.append(obj)
            return obj

    def begin(self, stage):
        with self.lock:
            self.stage = stage
        return self.event("stage_start")

    def _read(self):
        pending = b""
        try:
            while not self.stop.is_set():
                raw = self.serial.readline()
                if not raw:
                    continue
                self.binary.write(raw)
                self.binary.flush()
                pending += raw
                while b"\n" in pending:
                    complete, pending = pending.split(b"\n", 1)
                    line = complete.decode("utf-8", "replace").rstrip("\r\n")
                    try:
                        decoded = json.loads(line)
                        if not isinstance(decoded, dict):
                            decoded = None
                    except json.JSONDecodeError:
                        decoded = None
                    record = self.event("serial", line=line, decoded=decoded)
                    if decoded and decoded.get("type") == "tpms_frame":
                        with self.lock:
                            self.frames.append(record)
                        print("\n" + time.strftime("%H:%M:%S") + " RF " + str(decoded.get("payload_hex")) +
                              "  SUM8=" + str(decoded.get("integrity") == "SUM8") +
                              "  repeats=" + str(decoded.get("repeats")), flush=True)
        except Exception as exc:
            self.error = str(exc)

    def confirmed_since(self, since):
        with self.lock:
            return any(f["host_unix_s"] >= since and
                       f["decoded"].get("repeat_confirmed") is True for f in self.frames)

    def wait_for_repeat(self, since, timeout=75):
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            if self.error:
                raise RuntimeError("Serial capture stopped: " + self.error)
            if self.confirmed_since(since):
                return True
            time.sleep(0.2)
        self.event("stage_timeout", confirmed_repeat=False)
        print("No confirmed repeat in this stage; its raw evidence is still saved.")
        return False

    def close(self):
        self.stop.set()
        self.thread.join(timeout=2)
        self.serial.close()
        self.stream.close()
        self.binary.close()


def archive(folder, capture, metadata, references):
    frames = capture.frames if capture else []
    packets = sorted({f["decoded"]["payload_hex"] for f in frames})
    changing = []
    valid_bytes = [bytes.fromhex(p) for p in packets if len(p) == 20]
    if valid_bytes:
        changing = [i for i in range(10) if len({p[i] for p in valid_bytes}) > 1]
    # Compare fields only within one stable prefix, never across mixed sensors.
    by_candidate = {}
    for payload in packets:
        by_candidate.setdefault(payload[:8], []).append(payload)
    groups = {}
    for key, values in by_candidate.items():
        payload_bytes = [bytes.fromhex(p) for p in values]
        groups[key] = {
            "id_verified": False, "wheel_position": None, "unique_payloads": values,
            "changing_byte_indices": [i for i in range(10)
                                      if len({p[i] for p in payload_bytes}) > 1],
        }
    summary = {
        **metadata, "references": references, "serial_error": capture.error if capture else None,
        "decoded_records": len(frames), "unique_payloads": packets,
        "changing_byte_indices": changing, "mapping_verified": False,
        "by_id_candidate": groups,
        "stage_labels_are_action_windows_not_sensor_attribution": True,
        "stage_confirmed_repeats": {
            name: sum(f["stage"] == name and f["decoded"].get("repeat_confirmed") is True
                      for f in frames) for name, _ in STAGES
        },
    }
    (folder / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    if metadata.get("live_calibration"):
        baseline_path = folder / "baseline.jsonl"
        baseline = read_records(baseline_path.read_text(encoding="utf-8-sig")) if baseline_path.exists() else []
        report = analyze(frames, references, baseline=baseline)
        (folder / "calibration.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(f"Calibration: {len(references)} new references, {report['baseline_references']} previous references; "
              f"{sum(x['status'] == 'linked' for x in report['links'])} unambiguous links. "
              "See calibration.json; firmware mapping remains unverified.")
        print(feedback(report))
    target = folder.with_suffix(".zip")
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as z:
        for p in sorted(folder.iterdir()):
            if p.is_file():
                z.write(p, p.name)
    print(f"\nSaved: {target.resolve()}\nSend this ONE ZIP file back.")
    return target


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--port")
    ap.add_argument("--baud", type=int, default=115200)
    modes = ap.add_mutually_exclusive_group()
    modes.add_argument("--guided", action="store_true")
    modes.add_argument("--live-calibration", action="store_true")
    ap.add_argument("--with-reference", action="store_true",
                    help="Optional: request readings only when a real reference instrument exists")
    ap.add_argument("--flash", action="store_true")
    ap.add_argument("--baseline", type=Path,
                    help="Previous evidence JSONL to continue live calibration; retained in the session ZIP")
    ap.add_argument("--label", default="one_sensor")
    ap.add_argument("--seconds", type=float, default=180)
    ap.add_argument("--out", type=Path, help="Output session directory")
    a = ap.parse_args()
    if a.baseline and not a.live_calibration:
        ap.error("--baseline requires --live-calibration")
    baseline_bytes = a.baseline.read_bytes() if a.baseline else None
    baseline = read_records(baseline_bytes.decode('utf-8-sig')) if baseline_bytes else []
    root = Path(__file__).resolve().parent
    port = choose_port(a.port)
    metadata = {"port": port, "baud": a.baud, "label": a.label, "python": sys.version, "live_calibration": a.live_calibration}
    if a.flash:
        metadata["firmware"] = ensure_firmware(port, a.baud, root)
    folder = a.out or Path.cwd() / time.strftime("TPMS_ONE_TEST_%Y%m%d_%H%M%S")
    folder.mkdir(parents=True, exist_ok=False)
    if baseline_bytes:
        (folder / "baseline.jsonl").write_bytes(baseline_bytes)
        metadata['baseline_sha256'] = hashlib.sha256(baseline_bytes).hexdigest()
    references, capture = [], None
    try:
        capture = Capture(port, a.baud, folder)
        if a.live_calibration:
            capture.begin("live_calibration")
            print("LIVE CALIBRATION: only the test sensor should be powered.\n"
                  "Enter PSI Celsius only after a confirmed fresh display update.\n"
                  "Example: 35.2 28   |   q then Enter (or Ctrl+C) saves and finishes.\n"
                  "RF capture continues while you type. No time limit.")
            if baseline:
                previous_frames, previous_refs = split_records(baseline)
                print(f"Continuing saved evidence: {len(previous_frames)} RF records, {len(previous_refs)} references. "
                      "Only new RF received in this session can match new entries.")
                print(feedback(analyze([], [], baseline=baseline), show_last_reference=False))
            while True:
                entry = input("Fresh PSI Celsius > ").strip()
                if capture.error:
                    raise RuntimeError(capture.error)
                if entry.lower() in {"q", "quit", "exit"}:
                    break
                try:
                    ref = read_reference(entry)
                    if not ref["fresh"]:
                        print("No reference saved. Enter two fresh measurements or q.")
                        continue
                except ValueError as exc:
                    print(exc)
                    continue
                references.append(capture.event("reference", **ref, source="original_tpms_display", freshness_basis="user_confirmed_update"))
                with capture.lock:
                    frames = list(capture.frames)
                report = analyze(frames, references, baseline=baseline)
                capture.event("calibration_feedback", reference_index=report['links'][-1]['reference_index'],
                              association_status=report["links"][-1]["status"],
                              duplicate_of=report["links"][-1].get("duplicate_of"))
                print(feedback(report))
        elif a.guided:
            print("\nONE session, three states of the SAME sensor. "
                  "Other fitted sensors may remain in place.\n"
                  "Capture runs during every prompt. No receiver display is assumed.")
            for number, (stage, instruction) in enumerate(STAGES, 1):
                start = capture.begin(stage)["host_unix_s"]
                print(f"\n{number}/3: {instruction}")
                if a.with_reference:
                    while True:
                        try:
                            ref = read_reference(input("Measured PSI Celsius (or - if unavailable): "))
                            break
                        except ValueError as exc:
                            print(exc)
                    references.append(capture.event("reference", **ref, source="user_reference"))
                else:
                    input("Press Enter when this action is complete: ")
                    capture.event("stage_action_complete", reference_available=False)
                capture.wait_for_repeat(start)
            time.sleep(2)  # Keep the end of the last RF burst, too.
            capture.begin("restore")
            print("\nRefit the sensor normally after the session. No tire deflation is needed.")
        else:
            capture.begin(a.label)
            print(f"\nListening for {a.seconds:g} seconds. Leave fitted sensors in place.\n"
                  "No reference display or tire manipulation is required.\n"
                  "Raw fields are not verified PSI/Celsius. Ctrl+C saves the session early.")
            end = time.monotonic() + a.seconds
            while time.monotonic() < end:
                if capture.error:
                    raise RuntimeError(capture.error)
                time.sleep(0.2)
    except (KeyboardInterrupt, EOFError):
        metadata["interrupted"] = True
    except Exception as exc:
        metadata["error"] = str(exc)
        print(f"Capture issue: {exc}", file=sys.stderr)
    finally:
        if capture:
            capture.close()
        archive(folder, capture, metadata, references)
    return 1 if metadata.get("error") else 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (RuntimeError, OSError, subprocess.CalledProcessError) as exc:
        print(f"Test could not start: {exc}", file=sys.stderr)
        sys.exit(1)
