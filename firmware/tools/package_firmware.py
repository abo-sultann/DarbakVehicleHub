#!/usr/bin/env python3
"""Make an Actions artifact with explicit app offset and a single Windows entrypoint."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess

root = Path(__file__).resolve().parents[2]
out = root / "dist"
out.mkdir(exist_ok=True)
build = root / "firmware/.pio/build/esp32dev"
files = {
    build / "firmware.bin": "DarbakVehicleHub-ESP32-TPMS.bin",
    build / "bootloader.bin": "bootloader.bin",
    build / "partitions.bin": "partitions.bin",
    root / "firmware/tools/tpms_capture.py": "tpms_capture.py",
    root / "firmware/tools/tpms_calibration.py": "tpms_calibration.py",
    root / "firmware/tools/Test-TPMS.ps1": "Test-TPMS.ps1",
    root / "docs/TPMS_FIELD_TEST.md": "READ_ME.md",
    root / "docs/TPMS_DECODER.md": "TPMS_DECODER.md",
    root / "docs/TPMS_FIELD_20260922.md": "TPMS_FIELD_20260922.md",
    root / "docs/TPMS_LIVE_20260922.md": "TPMS_LIVE_20260922.md",
    root / "firmware/tests/fixtures/TPMS_LIVE_20260922.jsonl": "calibration-baseline.jsonl",
}
for source, name in files.items():
    shutil.copyfile(source, out / name)
commit = os.environ.get("TPMS_BUILD_COMMIT") or subprocess.check_output(
    ["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
manifest = {
    "commit": commit,
    "protocol": "darbak_capture_80_lsb",
    "mapping_verified": False,
    "flash_offset": "0x10000",
    "flash_scope": "application_only_existing_esp32_installation",
    "sha256": {name: hashlib.sha256((out / name).read_bytes()).hexdigest()
               for name in files.values()},
}
(out / "manifest.json").write_text(json.dumps(manifest, indent=2)+"\n", encoding="utf-8")
print(f"Packaged ESP32 build {commit[:12]} with verified-pulse decoder and one-session test.")
